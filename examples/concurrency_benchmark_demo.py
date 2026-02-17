from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from time import perf_counter

from qrt_platform import (
    BacktestConfig,
    Bar,
    BuyAndHoldStrategy,
    CsvBarLoader,
    FlatStrategy,
    MovingAverageCrossStrategy,
    StrategySpec,
    run_experiment_parallel,
)


def _specs() -> list[StrategySpec]:
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


def _time_mode(mode: str, bars: list[Bar], config: BacktestConfig, repeats: int = 3) -> float:
    durations: list[float] = []
    for _ in range(repeats):
        start = perf_counter()
        run_experiment_parallel(_specs(), bars, config, max_workers=4, mode=mode)
        durations.append(perf_counter() - start)
    return sum(durations) / len(durations)


def _scaled_bars(base_bars: list[Bar], multiplier: int) -> list[Bar]:
    if multiplier <= 1:
        return list(base_bars)

    out: list[Bar] = []
    n = len(base_bars)
    for block in range(multiplier):
        shift_days = block * n
        for bar in base_bars:
            out.append(Bar(ts=bar.ts + timedelta(days=shift_days), close=bar.close))
    return out


def main() -> None:
    base = Path(__file__).resolve().parents[1]
    csv_path = base / "data" / "raw" / "spy_us_daily.csv"

    base_bars = CsvBarLoader(ts_col="Date", close_col="Close").load(csv_path)
    config = BacktestConfig(initial_cash=1_000_000, transaction_cost_bps=1.0, periods_per_year=252)

    scales = [1, 5, 20, 60]

    print(f"Dataset: {csv_path.name} (base={len(base_bars)} bars)")
    print("Average wall time over 3 runs:")
    print(f"{'bars':>8} {'thread(s)':>12} {'process(s)':>12} {'thread/process':>15}")
    print("-" * 52)

    for scale in scales:
        bars = _scaled_bars(base_bars, scale)
        thread_avg = _time_mode("thread", bars, config)
        process_avg = _time_mode("process", bars, config)
        ratio = thread_avg / process_avg if process_avg > 0 else float("inf")
        print(f"{len(bars):>8} {thread_avg:>12.4f} {process_avg:>12.4f} {ratio:>15.3f}x")


if __name__ == "__main__":
    main()
