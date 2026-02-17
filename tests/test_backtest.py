import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from qrt_platform import BacktestConfig, Bar, CsvBarLoader, run_backtest


class FlatStrategy:
    def target_position(self, bar: Bar) -> float:
        return 0.0


class BuyAndHold:
    def target_position(self, bar: Bar) -> float:
        return 1.0


class AlternatingStrategy:
    def __init__(self) -> None:
        self.sign = 1.0

    def target_position(self, bar: Bar) -> float:
        self.sign *= -1.0
        return self.sign


class BacktestTests(unittest.TestCase):
    def setUp(self) -> None:
        start = datetime(2025, 1, 1)
        closes = [100.0, 101.0, 102.0, 101.0, 103.0]
        self.bars = [Bar(ts=start + timedelta(days=i), close=px) for i, px in enumerate(closes)]

    def test_flat_strategy_has_zero_return(self) -> None:
        result = run_backtest(
            FlatStrategy(), self.bars, BacktestConfig(initial_cash=1000.0, transaction_cost_bps=0.0)
        )
        self.assertAlmostEqual(result.total_return, 0.0, places=9)
        self.assertAlmostEqual(result.final_equity, 1000.0, places=9)
        self.assertAlmostEqual(result.volatility, 0.0, places=9)
        self.assertAlmostEqual(result.sharpe, 0.0, places=9)

    def test_buy_and_hold_positive_when_price_up(self) -> None:
        result = run_backtest(
            BuyAndHold(), self.bars, BacktestConfig(initial_cash=1000.0, transaction_cost_bps=0.0)
        )
        self.assertGreater(result.total_return, 0.0)
        self.assertGreater(result.final_equity, 1000.0)
        self.assertGreaterEqual(result.win_rate, 0.0)
        self.assertLessEqual(result.win_rate, 1.0)

    def test_turnover_increases_with_repositioning(self) -> None:
        flat = run_backtest(
            FlatStrategy(), self.bars, BacktestConfig(initial_cash=1000.0, transaction_cost_bps=0.0)
        )
        alt = run_backtest(
            AlternatingStrategy(),
            self.bars,
            BacktestConfig(initial_cash=1000.0, transaction_cost_bps=0.0),
        )
        self.assertGreater(alt.turnover, flat.turnover)

    def test_invalid_input_requires_two_bars(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 2"):
            run_backtest(FlatStrategy(), self.bars[:1], BacktestConfig())

    def test_invalid_price_rejected(self) -> None:
        bad_bars = list(self.bars)
        bad_bars[2] = Bar(ts=bad_bars[2].ts, close=0.0)
        with self.assertRaisesRegex(ValueError, "positive"):
            run_backtest(FlatStrategy(), bad_bars, BacktestConfig())

    def test_csv_loader_reads_and_sorts(self) -> None:
        loader = CsvBarLoader()

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "bars.csv"
            path.write_text(
                "ts,close\n"
                "2025-01-03T00:00:00,103\n"
                "2025-01-01T00:00:00,101\n"
                "2025-01-02T00:00:00,102\n",
                encoding="utf-8",
            )

            bars = loader.load(path)

        self.assertEqual(len(bars), 3)
        self.assertLess(bars[0].ts, bars[1].ts)
        self.assertLess(bars[1].ts, bars[2].ts)
        self.assertEqual(bars[0].close, 101.0)


if __name__ == "__main__":
    unittest.main()
