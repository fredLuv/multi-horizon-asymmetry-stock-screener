from __future__ import annotations

from collections import deque

from .models import Bar


class BuyAndHoldStrategy:
    def target_position(self, bar: Bar) -> float:
        return 1.0


class FlatStrategy:
    def target_position(self, bar: Bar) -> float:
        return 0.0


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
        short_vals = list(self._history)[-self._short :]
        short_ma = sum(short_vals) / self._short
        return 1.0 if short_ma > long_ma else 0.0
