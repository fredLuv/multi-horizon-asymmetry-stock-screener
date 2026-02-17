from datetime import datetime, timedelta

from qrt_platform import BacktestConfig, Bar, run_backtest


class BuyAndHold:
    def target_position(self, bar: Bar) -> float:
        return 1.0


def make_bars() -> list[Bar]:
    start = datetime(2025, 1, 1)
    closes = [100.0, 101.0, 102.0, 101.5, 103.0, 104.0]
    return [Bar(ts=start + timedelta(days=i), close=px) for i, px in enumerate(closes)]


def main() -> None:
    config = BacktestConfig(initial_cash=1_000_000, transaction_cost_bps=1.0, periods_per_year=252)
    result = run_backtest(BuyAndHold(), make_bars(), config)

    print(f"Total return:      {result.total_return:.4%}")
    print(f"Annualized return: {result.annualized_return:.4%}")
    print(f"Volatility:        {result.volatility:.4%}")
    print(f"Sharpe:            {result.sharpe:.4f}")
    print(f"Max drawdown:      {result.max_drawdown:.4%}")
    print(f"Win rate:          {result.win_rate:.2%}")
    print(f"Turnover:          {result.turnover:.2f}")
    print(f"Final equity:      {result.final_equity:,.2f}")


if __name__ == "__main__":
    main()
