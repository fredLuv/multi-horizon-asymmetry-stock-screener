from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .data import CsvBarLoader
from .experiment import RunMode, StrategySpec, run_experiment_parallel
from .models import BacktestConfig
from .reporting import write_experiment_csv, write_experiment_json
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

    if not data_path.exists():
        log.error("Data file not found: %s", data_path)
        return 2

    try:
        bars = CsvBarLoader(ts_col="Date", close_col="Close").load(data_path)
        config = BacktestConfig(
            initial_cash=1_000_000, transaction_cost_bps=1.0, periods_per_year=252
        )
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

        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        csv_path = output_dir / f"experiment_{ts}.csv"
        json_path = output_dir / f"experiment_{ts}.json"
        summary_path = output_dir / f"summary_{ts}.json"

        write_experiment_csv(rows, csv_path)
        write_experiment_json(rows, json_path)

        summary = {
            "timestamp": ts,
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
