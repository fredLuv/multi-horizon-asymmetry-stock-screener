import os
import tempfile
import unittest

from qrt_platform import (
    BacktestConfig,
    Bar,
    BuyAndHoldStrategy,
    StrategySpec,
    run_experiment_parallel,
    run_job,
)


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


if __name__ == "__main__":
    unittest.main()
