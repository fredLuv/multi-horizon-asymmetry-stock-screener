from __future__ import annotations

import os
from datetime import date, timedelta

from qrt_platform.stock_picker import (
    StockPickerConfig,
    fetch_nasdaq_nyse_universe,
    fetch_prices_yfinance_batched,
    run_trend_continuation_strategy,
)


def main() -> None:
    end = date.today()
    start = end - timedelta(days=365 * 5)
    limit_raw = os.getenv("STOCK_UNIVERSE_LIMIT")
    limit = int(limit_raw) if limit_raw else None
    tickers = fetch_nasdaq_nyse_universe()
    if limit is not None and limit > 0:
        tickers = tickers[:limit]
    if "SPY" not in tickers:
        tickers.append("SPY")
    close, volume = fetch_prices_yfinance_batched(
        tickers=tickers,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        batch_size=200,
    )

    config = StockPickerConfig(
        top_n=12,
        rebalance_every_days=5,
        min_price=10.0,
        market_filter_symbol="SPY",
        market_filter_window=200,
        max_weight_per_stock=0.10,
        transaction_cost_bps=10.0,
    )
    result = run_trend_continuation_strategy(close, volume, config)
    bt = result.backtest

    print(f"universe_size={len(tickers)}")
    print(f"latest_date={result.latest_date}")
    print("latest_picks")
    for ticker in result.latest_picks:
        print(
            f"{ticker}|weight={result.latest_weights[ticker]:.4f}"
            f"|yahoo={result.latest_chart_links[ticker]}"
            f"|tradingview={result.latest_tradingview_links[ticker]}"
        )
    print(
        "backtest|"
        f"total_return={bt.total_return:.4f}|annualized_return={bt.annualized_return:.4f}|"
        f"volatility={bt.volatility:.4f}|sharpe={bt.sharpe:.4f}|max_drawdown={bt.max_drawdown:.4f}|"
        f"win_rate={bt.win_rate:.4f}|turnover={bt.turnover:.2f}|periods={bt.periods}"
    )


if __name__ == "__main__":
    main()
