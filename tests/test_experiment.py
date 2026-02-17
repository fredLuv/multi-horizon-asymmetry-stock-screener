import unittest
from datetime import datetime, timedelta

from qrt_platform import (
    BacktestConfig,
    Bar,
    BuyAndHoldStrategy,
    FlatStrategy,
    StrategySpec,
    run_experiment,
)


class ExperimentTests(unittest.TestCase):
    def test_experiment_sorts_by_sharpe_desc(self) -> None:
        start = datetime(2025, 1, 1)
        closes = [100.0, 101.0, 102.0, 103.0, 104.0]
        bars = [Bar(ts=start + timedelta(days=i), close=px) for i, px in enumerate(closes)]

        specs = [
            StrategySpec("flat", FlatStrategy),
            StrategySpec("buy_hold", BuyAndHoldStrategy),
        ]

        rows = run_experiment(
            specs, bars, BacktestConfig(initial_cash=1000.0, transaction_cost_bps=0.0)
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].name, "buy_hold")
        self.assertEqual(rows[1].name, "flat")


if __name__ == "__main__":
    unittest.main()
