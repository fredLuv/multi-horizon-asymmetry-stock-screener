from pathlib import Path

from qrt_platform import (
    BacktestConfig,
    BuyAndHoldStrategy,
    CsvBarLoader,
    FlatStrategy,
    MovingAverageCrossStrategy,
    StrategySpec,
    run_experiment,
)


def main() -> None:
    base = Path(__file__).resolve().parents[1]
    csv_path = base / "data" / "raw" / "spy_us_daily.csv"

    bars = CsvBarLoader(ts_col="Date", close_col="Close").load(csv_path)
    config = BacktestConfig(initial_cash=1_000_000, transaction_cost_bps=1.0, periods_per_year=252)

    specs = [
        StrategySpec("flat", FlatStrategy),
        StrategySpec("buy_and_hold", BuyAndHoldStrategy),
        StrategySpec(
            "ma_20_100", MovingAverageCrossStrategy, {"short_window": 20, "long_window": 100}
        ),
        StrategySpec(
            "ma_50_200", MovingAverageCrossStrategy, {"short_window": 50, "long_window": 200}
        ),
    ]

    rows = run_experiment(specs, bars, config)

    print(f"Dataset: {csv_path.name} ({len(bars)} bars)")
    print("Ranked by Sharpe:\n")
    print(f"{'strategy':<14} {'sharpe':>8} {'cagr':>10} {'mdd':>10} {'turnover':>10}")
    print("-" * 58)
    for row in rows:
        r = row.result
        print(
            f"{row.name:<14} {r.sharpe:>8.3f} {r.annualized_return:>9.2%} "
            f"{r.max_drawdown:>9.2%} {r.turnover:>10.2f}"
        )


if __name__ == "__main__":
    main()
