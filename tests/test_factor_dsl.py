import unittest
from datetime import datetime, timedelta

from qrt_platform import Bar, FactorDslEngine, FormulaParseError


def _bars(n: int = 40) -> list[Bar]:
    start = datetime(2025, 1, 1)
    bars: list[Bar] = []
    px = 100.0
    for i in range(n):
        px *= 1.0 + (0.001 if i % 2 == 0 else -0.0005)
        bars.append(
            Bar(
                ts=start + timedelta(days=i),
                close=px,
                high=px * 1.01,
                low=px * 0.99,
                volume=1_000_000 + i * 1_000,
            )
        )
    return bars


class FactorDslTests(unittest.TestCase):
    def test_elementwise_expression(self) -> None:
        engine = FactorDslEngine()
        signal = engine.evaluate("Div(Sub($close, Ref($close, 1)), Ref($close, 1))", _bars())
        self.assertEqual(len(signal), 40)
        self.assertIsNone(signal[0])
        self.assertIsNotNone(signal[-1])

    def test_rolling_corr_expression(self) -> None:
        engine = FactorDslEngine()
        signal = engine.evaluate(
            "Corr(Rank(Delta($close,1), 5), Rank(Delta($volume,1), 5), 5)",
            _bars(),
        )
        self.assertEqual(len(signal), 40)
        self.assertIsNone(signal[3])
        self.assertIsNotNone(signal[-1])

    def test_unknown_function_rejected(self) -> None:
        engine = FactorDslEngine()
        with self.assertRaises(FormulaParseError):
            engine.evaluate("Foo($close, 5)", _bars())


if __name__ == "__main__":
    unittest.main()
