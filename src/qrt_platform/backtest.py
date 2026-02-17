from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

from .models import BacktestConfig, BacktestResult, Bar
from .strategy import Strategy


def run_backtest(strategy: Strategy, bars: Sequence[Bar], config: BacktestConfig) -> BacktestResult:
    if len(bars) < 2:
        raise ValueError("bars must contain at least 2 entries")
    if config.initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    if config.periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")

    cost_rate = config.transaction_cost_rate()
    if cost_rate < 0:
        raise ValueError("transaction_cost_bps must be non-negative")

    equity = config.initial_cash
    peak = equity
    max_drawdown = 0.0
    turnover = 0.0

    period_returns: list[float] = []
    win_periods = 0

    prev_close = bars[0].close
    prev_position = _clamp_position(strategy.target_position(bars[0]))

    for bar in bars[1:]:
        if bar.close <= 0 or prev_close <= 0:
            raise ValueError("bar.close must be positive")

        current_position = _clamp_position(strategy.target_position(bar))
        bar_return = (bar.close / prev_close) - 1.0
        gross_pnl = equity * prev_position * bar_return

        traded_notional_frac = abs(current_position - prev_position)
        trading_cost = equity * traded_notional_frac * cost_rate

        period_pnl = gross_pnl - trading_cost
        period_return = period_pnl / equity

        equity += period_pnl
        turnover += traded_notional_frac
        period_returns.append(period_return)

        if period_return > 0:
            win_periods += 1

        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown

        prev_close = bar.close
        prev_position = current_position

    total_return = (equity / config.initial_cash) - 1.0
    annualized_return = _annualize(total_return, len(period_returns), config.periods_per_year)

    volatility = _annualized_volatility(period_returns, config.periods_per_year)
    sharpe = _sharpe(annualized_return, volatility)
    win_rate = win_periods / len(period_returns)

    return BacktestResult(
        total_return=total_return,
        annualized_return=annualized_return,
        max_drawdown=max_drawdown,
        turnover=turnover,
        final_equity=equity,
        volatility=volatility,
        sharpe=sharpe,
        win_rate=win_rate,
    )


def _clamp_position(position: float) -> float:
    if position != position:
        raise ValueError("position cannot be NaN")
    if position > 1.0:
        return 1.0
    if position < -1.0:
        return -1.0
    return position


def _annualize(total_return: float, periods: int, periods_per_year: int) -> float:
    if periods <= 0:
        return 0.0
    growth = 1.0 + total_return
    if growth <= 0.0:
        return -1.0
    return growth ** (periods_per_year / periods) - 1.0


def _annualized_volatility(period_returns: Sequence[float], periods_per_year: int) -> float:
    n = len(period_returns)
    if n <= 1:
        return 0.0

    mean = sum(period_returns) / n
    variance = sum((ret - mean) ** 2 for ret in period_returns) / (n - 1)
    if variance <= 0.0:
        return 0.0
    return sqrt(variance) * sqrt(periods_per_year)


def _sharpe(
    annualized_return: float, annualized_volatility: float, risk_free_rate: float = 0.0
) -> float:
    if annualized_volatility == 0.0:
        return 0.0
    return (annualized_return - risk_free_rate) / annualized_volatility
