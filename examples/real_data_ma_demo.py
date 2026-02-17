from collections import deque
from pathlib import Path

from qrt_platform import BacktestConfig, Bar, CsvBarLoader, run_backtest


class MovingAverageCrossStrategy:
    def __init__(self, short_window: int = 50, long_window: int = 200) -> None:
        if short_window <= 0 or long_window <= 0:
            raise ValueError("windows must be positive")
        if short_window >= long_window:
            raise ValueError("short_window must be < long_window")
        self._short = short_window
        self._long = long_window
        self._history: deque[float] = deque(maxlen=long_window)

    def target_position(self, bar: Bar) -> float:
        self._history.append(bar.close)
        if len(self._history) < self._long:
            return 0.0

        long_ma = sum(self._history) / self._long
        short_slice = list(self._history)[-self._short :]
        short_ma = sum(short_slice) / self._short
        return 1.0 if short_ma > long_ma else 0.0


def main() -> None:
    base = Path(__file__).resolve().parents[1]
    csv_path = base / "data" / "raw" / "spy_us_daily.csv"

    loader = CsvBarLoader(ts_col="Date", close_col="Close")
    bars = loader.load(csv_path)

    strategy = MovingAverageCrossStrategy(short_window=50, long_window=200)
    config = BacktestConfig(initial_cash=1_000_000, transaction_cost_bps=1.0, periods_per_year=252)

    result = run_backtest(strategy, bars, config)

    print(f"Dataset:      {csv_path.name} ({len(bars)} bars)")
    print("Strategy:     MA Cross (50/200)")
    print(f"Total return: {result.total_return:.2%}")
    print(f"CAGR:         {result.annualized_return:.2%}")
    print(f"Volatility:   {result.volatility:.2%}")
    print(f"Sharpe:       {result.sharpe:.3f}")
    print(f"Max Drawdown: {result.max_drawdown:.2%}")
    print(f"Win Rate:     {result.win_rate:.2%}")
    print(f"Turnover:     {result.turnover:.2f}")
    print(f"Final Equity: {result.final_equity:,.2f}")


if __name__ == "__main__":
    main()
