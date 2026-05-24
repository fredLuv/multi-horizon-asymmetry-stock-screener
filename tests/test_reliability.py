import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from qrt_platform import (
    BacktestConfig,
    Bar,
    BuyAndHoldStrategy,
    StrategySpec,
    run_experiment_parallel,
    run_job,
)
from qrt_platform.stock_picker import StockPickerBacktestResult, StockPickerRunResult


class ReliabilityTests(unittest.TestCase):
    def test_invalid_parallel_mode_rejected(self) -> None:
        bars = [
            Bar(ts=__import__("datetime").datetime(2025, 1, 1), close=100.0),
            Bar(ts=__import__("datetime").datetime(2025, 1, 2), close=101.0),
        ]
        specs = [StrategySpec("buy", BuyAndHoldStrategy)]
        with self.assertRaisesRegex(ValueError, "mode"):
            run_experiment_parallel(specs, bars, BacktestConfig(), mode="bad")  # type: ignore[arg-type]

    def test_job_runner_returns_2_when_data_missing(self) -> None:
        old_data_path = os.environ.get("DATA_SOURCE_PATH")
        old_output = os.environ.get("OUTPUT_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["DATA_SOURCE_PATH"] = os.path.join(tmp, "does-not-exist.csv")
                os.environ["OUTPUT_DIR"] = tmp
                rc = run_job()
                self.assertEqual(rc, 2)
        finally:
            if old_data_path is None:
                os.environ.pop("DATA_SOURCE_PATH", None)
            else:
                os.environ["DATA_SOURCE_PATH"] = old_data_path
            if old_output is None:
                os.environ.pop("OUTPUT_DIR", None)
            else:
                os.environ["OUTPUT_DIR"] = old_output

    def test_alpha_mining_job_writes_artifacts(self) -> None:
        old_data_path = os.environ.get("DATA_SOURCE_PATH")
        old_output = os.environ.get("OUTPUT_DIR")
        old_kind = os.environ.get("JOB_KIND")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                data_path = Path(tmp) / "bars.csv"
                self._write_ohlcv_csv(data_path)
                os.environ["DATA_SOURCE_PATH"] = str(data_path)
                os.environ["OUTPUT_DIR"] = tmp
                os.environ["JOB_KIND"] = "alpha_mining"
                os.environ["ALPHA_ROUNDS"] = "2"
                os.environ["ALPHA_GENERATION_BATCH"] = "4"
                os.environ["ALPHA_OPT_STEPS"] = "1"
                os.environ["ALPHA_TOP_K"] = "4"
                os.environ["ALPHA_MIN_STRENGTH"] = "0.001"
                os.environ["ALPHA_MIN_CONSISTENCY"] = "0.001"
                os.environ["ALPHA_MIN_EFFICIENCY"] = "0.0"
                os.environ["ALPHA_MIN_DIVERSITY"] = "0.0"
                rc = run_job()
                self.assertEqual(rc, 0)
                files = [p.name for p in Path(tmp).iterdir()]
                self.assertTrue(any(name.startswith("alpha_factors_") and name.endswith(".csv") for name in files))
                self.assertTrue(any(name.startswith("alpha_factors_") and name.endswith(".json") for name in files))
                self.assertTrue(any(name.startswith("alpha_summary_") and name.endswith(".json") for name in files))
        finally:
            if old_data_path is None:
                os.environ.pop("DATA_SOURCE_PATH", None)
            else:
                os.environ["DATA_SOURCE_PATH"] = old_data_path
            if old_output is None:
                os.environ.pop("OUTPUT_DIR", None)
            else:
                os.environ["OUTPUT_DIR"] = old_output
            if old_kind is None:
                os.environ.pop("JOB_KIND", None)
            else:
                os.environ["JOB_KIND"] = old_kind
            for key in [
                "ALPHA_ROUNDS",
                "ALPHA_GENERATION_BATCH",
                "ALPHA_OPT_STEPS",
                "ALPHA_TOP_K",
                "ALPHA_MIN_STRENGTH",
                "ALPHA_MIN_CONSISTENCY",
                "ALPHA_MIN_EFFICIENCY",
                "ALPHA_MIN_DIVERSITY",
            ]:
                os.environ.pop(key, None)

    def test_stock_picker_job_writes_artifacts(self) -> None:
        old_output = os.environ.get("OUTPUT_DIR")
        old_kind = os.environ.get("JOB_KIND")
        old_limit = os.environ.get("STOCK_UNIVERSE_LIMIT")
        old_mode = os.environ.get("STOCK_UNIVERSE_MODE")
        old_use_cache = os.environ.get("STOCK_PICKER_USE_CACHE")
        old_save_cache = os.environ.get("STOCK_PICKER_SAVE_CACHE")
        old_top_down = os.environ.get("STOCK_PICKER_TOP_DOWN")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["OUTPUT_DIR"] = tmp
                os.environ["JOB_KIND"] = "stock_picker"
                os.environ["STOCK_UNIVERSE_LIMIT"] = "20"
                os.environ["STOCK_UNIVERSE_MODE"] = "all_us"
                os.environ["STOCK_PICKER_USE_CACHE"] = "0"
                os.environ["STOCK_PICKER_SAVE_CACHE"] = "0"
                os.environ["STOCK_PICKER_TOP_DOWN"] = "0"

                with patch("qrt_platform.job_runner.fetch_nasdaq_nyse_universe") as p_uni, patch(
                    "qrt_platform.job_runner.fetch_prices_yfinance_batched"
                ) as p_prices, patch("qrt_platform.job_runner.run_trend_continuation_strategy") as p_run:
                    p_uni.return_value = ["SPY", "AAPL", "MSFT", "NVDA"]
                    p_prices.return_value = (
                        SimpleNamespace(columns=["SPY", "AAPL", "MSFT", "NVDA"]),
                        SimpleNamespace(columns=["SPY", "AAPL", "MSFT", "NVDA"]),
                    )
                    p_run.return_value = StockPickerRunResult(
                        latest_date="2026-02-19",
                        latest_picks=["AAPL", "MSFT"],
                        latest_weights={"AAPL": 0.5, "MSFT": 0.5},
                        latest_chart_links={
                            "AAPL": "https://finance.yahoo.com/quote/AAPL/chart",
                            "MSFT": "https://finance.yahoo.com/quote/MSFT/chart",
                        },
                        latest_tradingview_links={
                            "AAPL": "https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL",
                            "MSFT": "https://www.tradingview.com/chart/?symbol=NASDAQ%3AMSFT",
                        },
                        backtest=StockPickerBacktestResult(
                            total_return=0.1,
                            annualized_return=0.08,
                            volatility=0.12,
                            sharpe=0.67,
                            max_drawdown=0.14,
                            turnover=10.0,
                            win_rate=0.55,
                            periods=700,
                        ),
                    )

                    rc = run_job()
                    self.assertEqual(rc, 0)
                    files = [p.name for p in Path(tmp).iterdir()]
                    self.assertTrue(any(name.startswith("stock_picks_") and name.endswith(".csv") for name in files))
                    self.assertTrue(any(name.startswith("stock_picks_") and name.endswith(".json") for name in files))
                    self.assertTrue(
                        any(name.startswith("stock_picker_summary_") and name.endswith(".json") for name in files)
                    )
                    self.assertTrue(p_uni.called)
                    self.assertTrue(p_prices.called)
                    self.assertTrue(p_run.called)
        finally:
            if old_output is None:
                os.environ.pop("OUTPUT_DIR", None)
            else:
                os.environ["OUTPUT_DIR"] = old_output
            if old_kind is None:
                os.environ.pop("JOB_KIND", None)
            else:
                os.environ["JOB_KIND"] = old_kind
            if old_limit is None:
                os.environ.pop("STOCK_UNIVERSE_LIMIT", None)
            else:
                os.environ["STOCK_UNIVERSE_LIMIT"] = old_limit
            if old_mode is None:
                os.environ.pop("STOCK_UNIVERSE_MODE", None)
            else:
                os.environ["STOCK_UNIVERSE_MODE"] = old_mode
            if old_use_cache is None:
                os.environ.pop("STOCK_PICKER_USE_CACHE", None)
            else:
                os.environ["STOCK_PICKER_USE_CACHE"] = old_use_cache
            if old_save_cache is None:
                os.environ.pop("STOCK_PICKER_SAVE_CACHE", None)
            else:
                os.environ["STOCK_PICKER_SAVE_CACHE"] = old_save_cache
            if old_top_down is None:
                os.environ.pop("STOCK_PICKER_TOP_DOWN", None)
            else:
                os.environ["STOCK_PICKER_TOP_DOWN"] = old_top_down

    @staticmethod
    def _write_ohlcv_csv(path: Path, n: int = 320) -> None:
        start = datetime(2024, 1, 1)
        price = 100.0
        lines = ["Date,Open,High,Low,Close,Volume\n"]
        for i in range(n):
            ret = 0.0006 + 0.003 * ((i % 7) - 3) / 3.0
            price *= 1.0 + ret
            open_px = price * 0.999
            high_px = price * 1.01
            low_px = price * 0.99
            close_px = price
            volume = 1_000_000 + (i % 20) * 25_000
            ts = (start + timedelta(days=i)).date().isoformat()
            lines.append(
                f"{ts},{open_px:.4f},{high_px:.4f},{low_px:.4f},{close_px:.4f},{volume}\n"
            )
        path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
