from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import Bar


class BarLoader(Protocol):
    def load(self, source: str | Path) -> list[Bar]:
        """Load bars sorted by timestamp."""


class CsvBarLoader:
    def __init__(self, ts_col: str = "ts", close_col: str = "close") -> None:
        self._ts_col = ts_col
        self._close_col = close_col

    def load(self, source: str | Path) -> list[Bar]:
        path = Path(source)
        bars: list[Bar] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                ts_raw = row.get(self._ts_col)
                close_raw = row.get(self._close_col)
                if not ts_raw or not close_raw:
                    raise ValueError("CSV must contain ts and close columns")
                bars.append(Bar(ts=datetime.fromisoformat(ts_raw), close=float(close_raw)))

        bars.sort(key=lambda bar: bar.ts)
        return bars


class YFinanceLoader:
    """Optional loader. Requires `pip install yfinance pandas`."""

    def load(self, symbol: str, period: str = "max", interval: str = "1d") -> list[Bar]:
        try:
            import yfinance as yf  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "yfinance is not installed. Install with: pip install yfinance pandas"
            ) from exc

        df = yf.download(
            symbol, period=period, interval=interval, auto_adjust=False, progress=False
        )
        if df.empty:
            raise ValueError(f"No data returned for symbol: {symbol}")

        bars: list[Bar] = []
        for ts, row in df.iterrows():
            close = float(row["Close"])
            bars.append(Bar(ts=ts.to_pydatetime(), close=close))

        bars.sort(key=lambda bar: bar.ts)
        return bars
