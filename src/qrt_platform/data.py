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
    def __init__(
        self,
        ts_col: str = "ts",
        close_col: str = "close",
        open_col: str | None = None,
        high_col: str | None = None,
        low_col: str | None = None,
        volume_col: str | None = None,
        vwap_col: str | None = None,
        amount_col: str | None = None,
    ) -> None:
        self._ts_col = ts_col
        self._close_col = close_col
        self._open_col = open_col
        self._high_col = high_col
        self._low_col = low_col
        self._volume_col = volume_col
        self._vwap_col = vwap_col
        self._amount_col = amount_col

    def load(self, source: str | Path) -> list[Bar]:
        path = Path(source)
        bars: list[Bar] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = list(reader.fieldnames or [])
            for row in reader:
                ts_raw = row.get(self._ts_col)
                close_raw = row.get(self._close_col)
                if not ts_raw or not close_raw:
                    raise ValueError("CSV must contain ts and close columns")
                close = float(close_raw)
                open_px = self._parse_optional(
                    row, self._open_col, headers, ["Open", "open", "OPEN"]
                )
                high_px = self._parse_optional(
                    row, self._high_col, headers, ["High", "high", "HIGH"]
                )
                low_px = self._parse_optional(row, self._low_col, headers, ["Low", "low", "LOW"])
                volume = self._parse_optional(
                    row, self._volume_col, headers, ["Volume", "volume", "VOL", "vol"]
                )
                vwap = self._parse_optional(row, self._vwap_col, headers, ["VWAP", "vwap"])
                amount = self._parse_optional(
                    row, self._amount_col, headers, ["Amount", "amount", "turnover", "Turnover"]
                )
                bars.append(
                    Bar(
                        ts=datetime.fromisoformat(ts_raw),
                        close=close,
                        open=open_px,
                        high=high_px,
                        low=low_px,
                        volume=volume,
                        vwap=vwap,
                        amount=amount,
                    )
                )

        bars.sort(key=lambda bar: bar.ts)
        return bars

    @staticmethod
    def _parse_optional(
        row: dict[str, str],
        preferred: str | None,
        headers: list[str],
        candidates: list[str],
    ) -> float | None:
        keys: list[str] = []
        if preferred:
            keys.append(preferred)
        keys.extend([key for key in candidates if key in headers])
        for key in keys:
            raw = row.get(key)
            if raw in (None, ""):
                continue
            try:
                return float(raw)
            except ValueError:
                continue
        return None


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
