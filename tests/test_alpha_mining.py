import unittest
from datetime import datetime, timedelta

from qrt_platform import (
    AlphaMiningConfig,
    BacktestConfig,
    Bar,
    ChainOfAlphaLite,
    FactorThresholds,
)


def _build_bars(n: int = 420) -> list[Bar]:
    start = datetime(2023, 1, 1)
    bars: list[Bar] = []
    price = 100.0
    for i in range(n):
        regime = 0.0007 if (i // 80) % 2 == 0 else -0.0003
        cycle = 0.003 * ((i % 7) - 3) / 3.0
        ret = regime + cycle
        price *= 1.0 + ret
        bars.append(Bar(ts=start + timedelta(days=i), close=max(1.0, price)))
    return bars


class ChainOfAlphaLiteTests(unittest.TestCase):
    def test_chain_returns_effective_pool_and_integrated_backtest(self) -> None:
        config = AlphaMiningConfig(
            rounds=3,
            generation_batch=6,
            optimization_steps=2,
            max_new_per_round=4,
            max_effective_pool=12,
            top_k=5,
            thresholds=FactorThresholds(
                min_strength=0.005,
                min_consistency=0.01,
                min_efficiency=0.20,
                min_diversity=0.0,
            ),
            backtest=BacktestConfig(initial_cash=10_000.0, transaction_cost_bps=1.0),
        )
        chain = ChainOfAlphaLite(config=config, seed=11)
        report = chain.run(_build_bars())

        self.assertGreater(len(report.effective_factors), 0)
        self.assertLessEqual(len(report.effective_factors), 5)
        self.assertIsNotNone(report.integrated_backtest)
        assert report.integrated_backtest is not None
        self.assertGreater(report.integrated_backtest.final_equity, 0.0)

    def test_chain_is_deterministic_for_same_seed(self) -> None:
        config = AlphaMiningConfig(
            rounds=2,
            generation_batch=5,
            optimization_steps=1,
            top_k=3,
            thresholds=FactorThresholds(
                min_strength=0.001,
                min_consistency=0.001,
                min_efficiency=0.0,
                min_diversity=0.0,
            ),
        )
        bars = _build_bars()
        left = ChainOfAlphaLite(config=config, seed=19).run(bars)
        right = ChainOfAlphaLite(config=config, seed=19).run(bars)
        self.assertEqual(
            [row.spec.name for row in left.effective_factors],
            [row.spec.name for row in right.effective_factors],
        )

    def test_strict_threshold_can_yield_empty_effective_pool(self) -> None:
        config = AlphaMiningConfig(
            rounds=2,
            generation_batch=5,
            optimization_steps=1,
            top_k=5,
            thresholds=FactorThresholds(
                min_strength=0.9,
                min_consistency=0.9,
                min_efficiency=0.9,
                min_diversity=0.9,
            ),
        )
        report = ChainOfAlphaLite(config=config, seed=7).run(_build_bars())
        self.assertEqual(len(report.effective_factors), 0)
        self.assertIsNone(report.integrated_backtest)


if __name__ == "__main__":
    unittest.main()
