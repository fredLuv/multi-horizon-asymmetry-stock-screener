from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Bar:
    ts: datetime
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    vwap: float | None = None
    amount: float | None = None


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_cash: float = 1_000_000.0
    transaction_cost_bps: float = 1.0
    periods_per_year: int = 252

    def transaction_cost_rate(self) -> float:
        return self.transaction_cost_bps / 10_000.0


@dataclass(frozen=True, slots=True)
class BacktestResult:
    total_return: float
    annualized_return: float
    max_drawdown: float
    turnover: float
    final_equity: float
    volatility: float
    sharpe: float
    win_rate: float
