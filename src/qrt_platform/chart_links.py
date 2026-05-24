from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

ChartProvider = Literal["yahoo", "tradingview"]


@dataclass(frozen=True, slots=True)
class ChartLink:
    ticker: str
    provider: ChartProvider
    url: str


def build_chart_link(ticker: str, provider: ChartProvider = "yahoo") -> ChartLink:
    normalized = ticker.strip().upper()
    if provider == "yahoo":
        url = f"https://finance.yahoo.com/quote/{quote(normalized)}/chart"
    elif provider == "tradingview":
        # Exchange-agnostic symbol page avoids incorrect hardcoded exchange prefixes.
        url = f"https://www.tradingview.com/symbols/{quote(normalized)}/"
    else:  # pragma: no cover - defensive branch for type-unsafe runtime calls
        raise ValueError(f"Unsupported provider: {provider}")
    return ChartLink(ticker=normalized, provider=provider, url=url)


def build_chart_links(tickers: list[str], provider: ChartProvider = "yahoo") -> dict[str, str]:
    return {ticker: build_chart_link(ticker, provider).url for ticker in tickers}
