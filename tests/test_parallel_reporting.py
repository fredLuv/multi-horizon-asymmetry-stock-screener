import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from qrt_platform import (
    BacktestConfig,
    Bar,
    BuyAndHoldStrategy,
    FlatStrategy,
    StrategySpec,
    run_experiment,
    run_experiment_parallel,
    write_experiment_csv,
    write_experiment_json,
    write_stock_picker_csv,
    write_stock_picker_json,
)
from qrt_platform.stock_picker import StockPickerBacktestResult, StockPickerRunResult


class ParallelAndReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        start = datetime(2025, 1, 1)
        closes = [100.0, 101.0, 102.0, 103.0, 104.0]
        self.bars = [Bar(ts=start + timedelta(days=i), close=px) for i, px in enumerate(closes)]
        self.config = BacktestConfig(initial_cash=1000.0, transaction_cost_bps=0.0)
        self.specs = [
            StrategySpec("flat", FlatStrategy),
            StrategySpec("buy_hold", BuyAndHoldStrategy),
        ]

    def test_parallel_thread_matches_sequential_order(self) -> None:
        seq = run_experiment(self.specs, self.bars, self.config)
        par = run_experiment_parallel(
            self.specs, self.bars, self.config, max_workers=2, mode="thread"
        )
        self.assertEqual([row.name for row in seq], [row.name for row in par])

    def test_parallel_process_matches_sequential_order(self) -> None:
        seq = run_experiment(self.specs, self.bars, self.config)
        par = run_experiment_parallel(
            self.specs, self.bars, self.config, max_workers=2, mode="process"
        )
        self.assertEqual([row.name for row in seq], [row.name for row in par])

    def test_reporting_writes_csv_and_json(self) -> None:
        rows = run_experiment_parallel(
            self.specs, self.bars, self.config, max_workers=2, mode="thread"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            csv_path = tmp / "result.csv"
            json_path = tmp / "result.json"

            write_experiment_csv(rows, csv_path)
            write_experiment_json(rows, json_path)

            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())

            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn("strategy,", csv_text)
            self.assertIn("buy_hold", csv_text)

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIsInstance(payload, list)
            self.assertGreaterEqual(len(payload), 1)
            self.assertIn("strategy", payload[0])
            self.assertIn("sharpe", payload[0])

    def test_stock_picker_reporting_writes_csv_and_json(self) -> None:
        result = StockPickerRunResult(
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            csv_path = tmp / "picks.csv"
            json_path = tmp / "picks.json"
            write_stock_picker_csv(result, csv_path)
            write_stock_picker_json(result, json_path)
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
            self.assertIn("yahoo_chart", csv_path.read_text(encoding="utf-8"))
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("latest_picks", payload)


if __name__ == "__main__":
    unittest.main()
