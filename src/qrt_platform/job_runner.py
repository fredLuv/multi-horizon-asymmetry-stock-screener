from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .data import CsvBarLoader
from .experiment import RunMode, StrategySpec, run_experiment_parallel
from .alpha_formula_mining import FormulaChainOfAlpha, FormulaMiningConfig, FormulaThresholds
from .models import BacktestConfig
from .reporting import (
    write_experiment_csv,
    write_experiment_json,
    write_formula_factors_csv,
    write_formula_factors_json,
    write_stock_picker_csv,
    write_stock_picker_json,
)
from .stock_picker import (
    SECTOR_ETF_BY_GICS,
    StockPickerConfig,
    fetch_filtered_universe,
    fetch_nasdaq_nyse_universe,
    fetch_prices_yfinance_batched,
    fetch_sp500_sector_map,
    load_price_cache,
    run_trend_continuation_strategy,
    save_price_cache,
)
from .strategies import BuyAndHoldStrategy, FlatStrategy, MovingAverageCrossStrategy


def run_job() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    log = logging.getLogger("qrt_platform.job")

    data_path = Path(os.getenv("DATA_SOURCE_PATH", "data/raw/spy_us_daily.csv"))
    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    run_mode_raw = os.getenv("RUN_MODE", "thread")
    run_mode: RunMode = "process" if run_mode_raw == "process" else "thread"
    max_workers = int(os.getenv("MAX_WORKERS", "4"))
    job_kind = os.getenv("JOB_KIND", "experiment").strip().lower()

    if job_kind != "stock_picker" and not data_path.exists():
        log.error("Data file not found: %s", data_path)
        return 2

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        if job_kind == "alpha_mining":
            _run_alpha_mining_job(data_path, output_dir, ts, log)
        elif job_kind == "stock_picker":
            _run_stock_picker_job(output_dir, ts, log)
        elif job_kind == "stock_picker_prep":
            _run_stock_picker_prep_job(output_dir, log)
        else:
            _run_experiment_job(data_path, output_dir, run_mode, max_workers, ts, log)
        return 0
    except Exception:  # pragma: no cover - defensive production boundary
        log.exception("Job failed")
        return 1


def _strategy_specs() -> list[StrategySpec]:
    return [
        StrategySpec("flat", FlatStrategy),
        StrategySpec("buy_and_hold", BuyAndHoldStrategy),
        StrategySpec(
            "ma_10_50", MovingAverageCrossStrategy, {"short_window": 10, "long_window": 50}
        ),
        StrategySpec(
            "ma_20_100", MovingAverageCrossStrategy, {"short_window": 20, "long_window": 100}
        ),
        StrategySpec(
            "ma_50_200", MovingAverageCrossStrategy, {"short_window": 50, "long_window": 200}
        ),
    ]


def _run_experiment_job(
    data_path: Path,
    output_dir: Path,
    run_mode: RunMode,
    max_workers: int,
    ts: str,
    log: logging.Logger,
) -> None:
    bars = CsvBarLoader(ts_col="Date", close_col="Close").load(data_path)
    config = BacktestConfig(initial_cash=1_000_000, transaction_cost_bps=1.0, periods_per_year=252)
    specs = _strategy_specs()

    log.info(
        "Starting experiment: bars=%d strategies=%d mode=%s workers=%d",
        len(bars),
        len(specs),
        run_mode,
        max_workers,
    )
    rows = run_experiment_parallel(
        specs,
        bars,
        config,
        max_workers=max_workers,
        mode=run_mode,
    )
    csv_path = output_dir / f"experiment_{ts}.csv"
    json_path = output_dir / f"experiment_{ts}.json"
    summary_path = output_dir / f"summary_{ts}.json"
    write_experiment_csv(rows, csv_path)
    write_experiment_json(rows, json_path)

    summary = {
        "timestamp": ts,
        "job_kind": "experiment",
        "data_source": str(data_path),
        "mode": run_mode,
        "max_workers": max_workers,
        "strategy_count": len(rows),
        "best": {
            "name": rows[0].name,
            **asdict(rows[0].result),
        },
        "artifacts": {
            "csv": str(csv_path),
            "json": str(json_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("Run complete. Best strategy=%s sharpe=%.3f", rows[0].name, rows[0].result.sharpe)
    log.info("Artifacts: %s %s %s", csv_path, json_path, summary_path)


def _run_alpha_mining_job(
    data_path: Path,
    output_dir: Path,
    ts: str,
    log: logging.Logger,
) -> None:
    bars = CsvBarLoader(ts_col="Date", close_col="Close").load(data_path)
    config = FormulaMiningConfig(
        rounds=int(os.getenv("ALPHA_ROUNDS", "6")),
        generation_batch=int(os.getenv("ALPHA_GENERATION_BATCH", "10")),
        optimization_steps=int(os.getenv("ALPHA_OPT_STEPS", "3")),
        top_k=int(os.getenv("ALPHA_TOP_K", "10")),
        signal_horizon=int(os.getenv("ALPHA_SIGNAL_HORIZON", "1")),
        thresholds=FormulaThresholds(
            min_strength=float(os.getenv("ALPHA_MIN_STRENGTH", "0.02")),
            min_consistency=float(os.getenv("ALPHA_MIN_CONSISTENCY", "0.05")),
            min_efficiency=float(os.getenv("ALPHA_MIN_EFFICIENCY", "0.30")),
            min_diversity=float(os.getenv("ALPHA_MIN_DIVERSITY", "0.03")),
        ),
    )
    seed = int(os.getenv("ALPHA_SEED", "17"))
    miner = FormulaChainOfAlpha(config=config, seed=seed)
    log.info(
        "Starting alpha mining: bars=%d rounds=%d generation_batch=%d top_k=%d",
        len(bars),
        config.rounds,
        config.generation_batch,
        config.top_k,
    )
    report = miner.run(bars)
    csv_path = output_dir / f"alpha_factors_{ts}.csv"
    json_path = output_dir / f"alpha_factors_{ts}.json"
    summary_path = output_dir / f"alpha_summary_{ts}.json"
    write_formula_factors_csv(report, csv_path, top_n=100)
    write_formula_factors_json(report, json_path, top_n=100)

    best = report.effective_factors[0] if report.effective_factors else None
    summary = {
        "timestamp": ts,
        "job_kind": "alpha_mining",
        "data_source": str(data_path),
        "bars": len(bars),
        "effective_count": len(report.effective_factors),
        "deprecated_count": len(report.deprecated_factors),
        "best_factor": (
            {
                "name": best.spec.name,
                "expression": best.spec.expression,
                "invert": best.spec.invert,
                "metrics": asdict(best.metrics),
                "backtest": asdict(best.backtest),
            }
            if best is not None
            else None
        ),
        "integrated_backtest": (
            asdict(report.integrated_backtest) if report.integrated_backtest is not None else None
        ),
        "artifacts": {"csv": str(csv_path), "json": str(json_path)},
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info(
        "Alpha mining complete. effective=%d deprecated=%d",
        len(report.effective_factors),
        len(report.deprecated_factors),
    )
    log.info("Artifacts: %s %s %s", csv_path, json_path, summary_path)


def _run_stock_picker_job(output_dir: Path, ts: str, log: logging.Logger) -> None:
    from datetime import date, timedelta

    years = int(os.getenv("STOCK_PICKER_YEARS", "5"))
    top_n = int(os.getenv("STOCK_PICKER_TOP_N", "12"))
    rebalance_days = int(os.getenv("STOCK_PICKER_REBALANCE_DAYS", "5"))
    min_price = float(os.getenv("STOCK_PICKER_MIN_PRICE", "10"))
    max_weight = float(os.getenv("STOCK_PICKER_MAX_WEIGHT", "0.10"))
    cost_bps = float(os.getenv("STOCK_PICKER_COST_BPS", "10"))
    batch_size = int(os.getenv("STOCK_PICKER_BATCH_SIZE", "50"))
    max_retries = int(os.getenv("STOCK_PICKER_MAX_RETRIES", "3"))
    retry_sleep = float(os.getenv("STOCK_PICKER_RETRY_SLEEP", "0.5"))
    universe_mode = os.getenv("STOCK_UNIVERSE_MODE", "sp1500").strip().lower()
    top_down = os.getenv("STOCK_PICKER_TOP_DOWN", "1").strip() == "1"
    cache_dir = Path(os.getenv("STOCK_PICKER_CACHE_DIR", str(output_dir / "cache")))
    use_cache = os.getenv("STOCK_PICKER_USE_CACHE", "1").strip() == "1"
    save_cache = os.getenv("STOCK_PICKER_SAVE_CACHE", "1").strip() == "1"
    universe_limit_raw = os.getenv("STOCK_UNIVERSE_LIMIT")
    universe_limit = int(universe_limit_raw) if universe_limit_raw else None

    end = date.today()
    start = end - timedelta(days=365 * years)
    close = None
    volume = None
    tickers: list[str] = []
    if use_cache:
        try:
            close, volume = load_price_cache(cache_dir, prefix="stock_picker")
            tickers = list(close.columns)
            log.info("Loaded cached prices from %s", cache_dir)
        except FileNotFoundError:
            pass

    sector_map: dict[str, str] | None = None
    if top_down:
        try:
            sector_map = fetch_sp500_sector_map()
        except Exception:
            sector_map = None

    if close is None or volume is None:
        tickers = _build_universe(universe_mode, universe_limit)
        if top_down:
            tickers = sorted(set(tickers).union(SECTOR_ETF_BY_GICS.values()))
        log.info(
            "Starting stock picker: universe=%d mode=%s top_down=%s years=%d top_n=%d rebalance_days=%d",
            len(tickers),
            universe_mode,
            top_down,
            years,
            top_n,
            rebalance_days,
        )
        close, volume = fetch_prices_yfinance_batched(
            tickers=tickers,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            batch_size=batch_size,
            max_retries=max_retries,
            retry_sleep_seconds=retry_sleep,
        )
        if save_cache:
            save_price_cache(close, volume, cache_dir, prefix="stock_picker")
            log.info("Saved price cache to %s", cache_dir)

    if "SPY" not in close.columns:
        raise ValueError("SPY column missing in downloaded market data")
    result = run_trend_continuation_strategy(
        close=close,
        volume=volume,
        config=StockPickerConfig(
            top_n=top_n,
            rebalance_every_days=rebalance_days,
            min_price=min_price,
            max_weight_per_stock=max_weight,
            transaction_cost_bps=cost_bps,
            market_filter_symbol="SPY",
            market_filter_window=200,
        ),
        sector_map=sector_map if top_down else None,
        sector_etf_map=SECTOR_ETF_BY_GICS if top_down else None,
    )

    csv_path = output_dir / f"stock_picks_{ts}.csv"
    json_path = output_dir / f"stock_picks_{ts}.json"
    summary_path = output_dir / f"stock_picker_summary_{ts}.json"
    write_stock_picker_csv(result, csv_path)
    write_stock_picker_json(result, json_path)

    summary = {
        "timestamp": ts,
        "job_kind": "stock_picker",
        "latest_date": result.latest_date,
        "universe_size": len([col for col in close.columns if col != "SPY"]),
        "universe_mode": universe_mode,
        "top_down": top_down,
        "picked_count": len(result.latest_picks),
        "latest_picks": result.latest_picks,
        "backtest": asdict(result.backtest),
        "artifacts": {"csv": str(csv_path), "json": str(json_path)},
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info(
        "Stock picker complete. picks=%d sharpe=%.3f",
        len(result.latest_picks),
        result.backtest.sharpe,
    )
    log.info("Artifacts: %s %s %s", csv_path, json_path, summary_path)


def _run_stock_picker_prep_job(output_dir: Path, log: logging.Logger) -> None:
    from datetime import date, timedelta

    years = int(os.getenv("STOCK_PICKER_YEARS", "5"))
    batch_size = int(os.getenv("STOCK_PICKER_BATCH_SIZE", "50"))
    max_retries = int(os.getenv("STOCK_PICKER_MAX_RETRIES", "3"))
    retry_sleep = float(os.getenv("STOCK_PICKER_RETRY_SLEEP", "0.5"))
    universe_mode = os.getenv("STOCK_UNIVERSE_MODE", "sp1500").strip().lower()
    universe_limit_raw = os.getenv("STOCK_UNIVERSE_LIMIT")
    universe_limit = int(universe_limit_raw) if universe_limit_raw else None
    cache_dir = Path(os.getenv("STOCK_PICKER_CACHE_DIR", str(output_dir / "cache")))

    end = date.today()
    start = end - timedelta(days=365 * years)
    tickers = _build_universe(universe_mode, universe_limit)
    top_down = os.getenv("STOCK_PICKER_TOP_DOWN", "1").strip() == "1"
    if top_down:
        tickers = sorted(set(tickers).union(SECTOR_ETF_BY_GICS.values()))
    log.info("Starting stock picker prep: universe=%d mode=%s", len(tickers), universe_mode)
    close, volume = fetch_prices_yfinance_batched(
        tickers=tickers,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        batch_size=batch_size,
        max_retries=max_retries,
        retry_sleep_seconds=retry_sleep,
    )
    save_price_cache(close, volume, cache_dir, prefix="stock_picker")
    log.info("Stock picker prep complete. cache_dir=%s columns=%d", cache_dir, len(close.columns))


def _build_universe(universe_mode: str, universe_limit: int | None) -> list[str]:
    if universe_mode == "all_us":
        tickers = fetch_nasdaq_nyse_universe()
    else:
        tickers = fetch_filtered_universe(universe_mode)
    if universe_limit is not None and universe_limit > 0:
        tickers = tickers[:universe_limit]
    if "SPY" not in tickers:
        tickers.append("SPY")
    return tickers
