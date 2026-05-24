import unittest
from datetime import datetime, timedelta

from qrt_platform import FormulaChainOfAlpha, FormulaMiningConfig, FormulaThresholds
from qrt_platform.models import BacktestConfig, Bar


def _bars(n: int = 420) -> list[Bar]:
    start = datetime(2023, 1, 1)
    price = 100.0
    bars: list[Bar] = []
    for i in range(n):
        regime = 0.0008 if (i // 120) % 2 == 0 else -0.0002
        cycle = 0.003 * ((i % 10) - 5) / 5.0
        ret = regime + cycle
        price *= 1.0 + ret
        bars.append(
            Bar(
                ts=start + timedelta(days=i),
                close=max(1.0, price),
                high=price * 1.01,
                low=price * 0.99,
                volume=500_000 + (i % 15) * 3_000,
            )
        )
    return bars


class FormulaMiningTests(unittest.TestCase):
    def test_formula_chain_runs_end_to_end(self) -> None:
        config = FormulaMiningConfig(
            rounds=3,
            generation_batch=6,
            optimization_steps=2,
            top_k=5,
            thresholds=FormulaThresholds(
                min_strength=0.005,
                min_consistency=0.01,
                min_efficiency=0.20,
                min_diversity=0.0,
            ),
            backtest=BacktestConfig(initial_cash=10_000.0, transaction_cost_bps=1.0),
        )
        report = FormulaChainOfAlpha(config=config, seed=29).run(_bars())
        self.assertLessEqual(len(report.effective_factors), 5)
        self.assertGreaterEqual(len(report.deprecated_factors), 0)
        if report.effective_factors:
            self.assertIsNotNone(report.integrated_backtest)


if __name__ == "__main__":
    unittest.main()
