from __future__ import annotations

from typing import Protocol

from .models import Bar


class Strategy(Protocol):
    def target_position(self, bar: Bar) -> float:
        """Return target position in [-1, 1] for current bar."""
