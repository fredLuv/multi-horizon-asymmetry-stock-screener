"""
==========================================================================================
QRT PLATFORM CORE SYSTEM - INGESTION, CACHING, & STRATEGY ENGINE
Module Name: qrt_platform.stock_picker
Repository Context: multi-horizon-asymmetry-stock-screener

DESIGN RATIONALE:
Historically named 'stock_picker.py' as part of the initial QRT quantitative track demo models,
this module has evolved into the unified Core Market Data Ingestion, Database Caching, and 
Algorithmic Allocation Engine of the 'multi-horizon-asymmetry-stock-screener' repository.

CORE RESPONSIBILITIES:
1. EXCHANGE REGISTRY INGESTION:
   - fetch_nasdaq_nyse_universe(): Downloads and parses official listings directories from exchange directories.
   - fetch_filtered_universe(mode): Scrapes Wikipedia sector listings to compile S&P 500, 400, 600 (or S&P 1500).
2. PARALLEL BATCH MARKET DATA INGESTION:
   - fetch_prices_yfinance_batched(): Core high-throughput parallel downloader that fetches historical OHLCV 
     market data in throttled batches to fully bypass Yahoo Finance API rate limits.
3. CACHING OPERATIONS:
   - save_price_cache() & load_price_cache(): Standardized local CSV database operations to preserve bandwidth.
4. QUANTITATIVE STRATEGY RUNNER:
   - run_trend_continuation_strategy(): Executes our multi-factor alpha strategy ranking momentum, trend quality,
     and volatility-adjusted efficiency to output weighted target portfolios.
==========================================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Sequence
import re
import time
from io import StringIO

from .chart_links import build_chart_links

SECTOR_ETF_BY_GICS: dict[str, str] = {
    "Information Technology": "XLK",
    "Health Care": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Materials": "XLB",
    "Real Estate": "XLRE",
}


@dataclass(frozen=True, slots=True)
class StockPickerConfig:
    top_n: int = 12
    rebalance_every_days: int = 5
    min_price: float = 10.0
    market_filter_symbol: str = "SPY"
    market_filter_window: int = 200
    max_weight_per_stock: float = 0.10
    transaction_cost_bps: float = 10.0
    top_sector_count: int = 4


@dataclass(frozen=True, slots=True)
class StockPickerBacktestResult:
    total_return: float
    annualized_return: float
    volatility: float
    sharpe: float
    max_drawdown: float
    turnover: float
    win_rate: float
    periods: int


@dataclass(frozen=True, slots=True)
class StockPickerRunResult:
    latest_date: str
    latest_picks: list[str]
    latest_weights: dict[str, float]
    latest_chart_links: dict[str, str]
    latest_tradingview_links: dict[str, str]
    backtest: StockPickerBacktestResult


def fetch_filtered_universe(mode: str = "sp1500") -> list[str]:  # pragma: no cover
    normalized_mode = mode.strip().lower()
    if normalized_mode == "all_us":
        return fetch_nasdaq_nyse_universe()
    if normalized_mode == "sp500":
        return _fetch_wikipedia_symbols("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    if normalized_mode == "nasdaq100":
        return _fetch_wikipedia_symbols("https://en.wikipedia.org/wiki/Nasdaq-100")
    if normalized_mode == "sp1500":
        symbols = set()
        symbols.update(
            _fetch_wikipedia_symbols("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        )
        symbols.update(
            _fetch_wikipedia_symbols("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")
        )
        symbols.update(
            _fetch_wikipedia_symbols("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies")
        )
        symbols.add("SPY")
        return sorted(symbols)
    raise ValueError("mode must be one of: all_us, sp500, sp1500, nasdaq100")


def fetch_sp500_sector_map() -> dict[str, str]:  # pragma: no cover
    import pandas as pd  # type: ignore[import-not-found]
    import requests  # type: ignore[import-not-found]

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; qrt-platform/1.0; +https://example.org)"}
    html = requests.get(url, headers=headers, timeout=30).text
    tables = pd.read_html(StringIO(html))
    if not tables:
        raise RuntimeError("Failed to fetch S&P 500 sector map")
    table = tables[0]
    symbol_col = None
    sector_col = None
    for col in table.columns:
        name = str(col).lower()
        if name in {"symbol", "ticker", "ticker symbol"}:
            symbol_col = col
        if "gics sector" in name or "sector" == name:
            sector_col = col
    if symbol_col is None or sector_col is None:
        raise RuntimeError("Could not find symbol/sector columns in S&P 500 table")
    out: dict[str, str] = {}
    for symbol, sector in zip(table[symbol_col], table[sector_col]):
        ticker = _normalize_ticker(str(symbol))
        if ticker is None:
            continue
        out[ticker] = str(sector).strip()
    return out


def fetch_nasdaq_nyse_universe(
    include_nyse_arca: bool = True,
    include_nyse_american: bool = True,
) -> list[str]:  # pragma: no cover - runtime network integration
    import requests  # type: ignore[import-not-found]

    nasdaq_url = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
    other_url = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

    nasdaq_txt = requests.get(nasdaq_url, timeout=30).text
    other_txt = requests.get(other_url, timeout=30).text

    symbols: set[str] = set()
    symbols.update(_parse_nasdaq_listed(nasdaq_txt))
    symbols.update(
        _parse_other_listed(
            other_txt,
            include_nyse_arca=include_nyse_arca,
            include_nyse_american=include_nyse_american,
        )
    )

    symbols.add("SPY")
    return sorted(symbols)


def save_price_cache(close, volume, cache_dir: str | Path, prefix: str = "stock_picker") -> tuple[str, str]:
    path = Path(cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    close_path = path / f"{prefix}_close.csv"
    volume_path = path / f"{prefix}_volume.csv"
    close.to_csv(close_path)
    volume.to_csv(volume_path)
    return str(close_path), str(volume_path)


def load_price_cache(cache_dir: str | Path, prefix: str = "stock_picker"):  # pragma: no cover
    import pandas as pd  # type: ignore[import-not-found]

    path = Path(cache_dir)
    close_path = path / f"{prefix}_close.csv"
    volume_path = path / f"{prefix}_volume.csv"
    if not close_path.exists() or not volume_path.exists():
        raise FileNotFoundError(f"Cache files not found in: {path}")
    close = pd.read_csv(close_path, index_col=0, parse_dates=True).sort_index()
    volume = pd.read_csv(volume_path, index_col=0, parse_dates=True).sort_index()
    return close, volume


def fetch_prices_yfinance(
    tickers: Sequence[str], start: str, end: str
):  # pragma: no cover - runtime network integration
    try:
        import pandas as pd  # type: ignore[import-not-found]
        import yfinance as yf  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install with: pip install pandas yfinance") from exc

    frame = yf.download(
        list(tickers),
        start=start,
        end=end,
        auto_adjust=False,
        progress=False,
        group_by="column",
        threads=True,
    )
    if frame.empty:
        raise ValueError("No data returned from Yahoo Finance")

    close = frame["Close"].copy()
    volume = frame["Volume"].copy()
    if not isinstance(close, pd.DataFrame):
        # Single ticker fallback.
        close = close.to_frame(name=tickers[0])
        volume = volume.to_frame(name=tickers[0])

    close = close.sort_index()
    volume = volume.sort_index()
    return close, volume


def fetch_prices_yfinance_batched(
    tickers: Sequence[str],
    start: str,
    end: str,
    batch_size: int = 200,
    min_history_rows: int = 260,
    max_retries: int = 3,
    retry_sleep_seconds: float = 1.0,
) -> tuple[object, object]:  # pragma: no cover - runtime network integration
    import pandas as pd  # type: ignore[import-not-found]

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    unique = []
    seen: set[str] = set()
    for ticker in tickers:
        normalized = ticker.strip().upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    if not unique:
        raise ValueError("tickers must be non-empty")

    close_frames = []
    volume_frames = []
    for i in range(0, len(unique), batch_size):
        batch = unique[i : i + batch_size]
        close_part = None
        volume_part = None
        for attempt in range(max_retries):
            try:
                c_part, v_part = fetch_prices_yfinance(batch, start, end)
            except Exception:
                time.sleep(retry_sleep_seconds * (attempt + 1))
                continue
            valid_cols = [col for col in c_part.columns if c_part[col].count() >= min_history_rows]
            if not valid_cols:
                time.sleep(retry_sleep_seconds * (attempt + 1))
                continue
            close_part = c_part[valid_cols]
            volume_part = v_part[valid_cols]
            break
        if close_part is None or volume_part is None:
            continue
        close_frames.append(close_part)
        volume_frames.append(volume_part)
        time.sleep(max(0.0, retry_sleep_seconds))
    if not close_frames:
        raise ValueError("No batch returned usable data from Yahoo Finance")
    close = pd.concat(close_frames, axis=1)
    volume = pd.concat(volume_frames, axis=1)
    close = close.loc[:, ~close.columns.duplicated()]
    volume = volume.loc[:, ~volume.columns.duplicated()]
    return close, volume


def run_trend_continuation_strategy(
    close,
    volume,
    config: StockPickerConfig,
    sector_map: dict[str, str] | None = None,
    sector_etf_map: dict[str, str] | None = None,
) -> StockPickerRunResult:
    import pandas as pd  # type: ignore[import-not-found]

    if len(close.index) < 260:
        raise ValueError("Need at least 260 rows of price history")
    if config.top_n <= 0:
        raise ValueError("top_n must be positive")

    tickers = [col for col in close.columns if col != config.market_filter_symbol]
    if config.market_filter_symbol not in close.columns:
        raise ValueError(f"{config.market_filter_symbol} must be included in close columns")

    returns = close.pct_change().fillna(0.0)
    mom20 = close / close.shift(20) - 1.0
    mom60 = close / close.shift(60) - 1.0
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    vol20 = returns.rolling(20).std()

    # Composite score with trend and efficiency.
    trend_quality = (close - ma50) / ma50
    efficiency = mom20 / (vol20 * sqrt(20))
    raw_score = 0.40 * mom60 + 0.25 * mom20 + 0.20 * trend_quality + 0.15 * efficiency

    avg_dollar_vol20 = (close * volume).rolling(20).mean()
    tradable = (
        (close > config.min_price)
        & (ma50 > ma200)
        & (close > ma50)
        & (avg_dollar_vol20 > 20_000_000.0)
    )

    spy = close[config.market_filter_symbol]
    spy_ma = spy.rolling(config.market_filter_window).mean()
    market_on = spy > spy_ma

    active_sector_etf = sector_etf_map or SECTOR_ETF_BY_GICS
    etf_by_sector = {
        sector: etf for sector, etf in active_sector_etf.items() if etf in close.columns
    }
    sector_allowed_by_date: dict[object, set[str]] = {}
    if sector_map and etf_by_sector:
        sector_to_tickers: dict[str, list[str]] = {}
        for ticker in tickers:
            sector = sector_map.get(ticker)
            if sector is None:
                continue
            sector_to_tickers.setdefault(sector, []).append(ticker)
        etf_cols = list(etf_by_sector.values())
        etf_close = close[etf_cols]
        etf_returns = etf_close.pct_change().fillna(0.0)
        etf_mom20 = etf_close / etf_close.shift(20) - 1.0
        etf_mom60 = etf_close / etf_close.shift(60) - 1.0
        etf_ma50 = etf_close.rolling(50).mean()
        etf_ma200 = etf_close.rolling(200).mean()
        etf_vol20 = etf_returns.rolling(20).std()
        etf_trend = (etf_close - etf_ma50) / etf_ma50
        etf_score = 0.40 * etf_mom60 + 0.25 * etf_mom20 + 0.20 * etf_trend + 0.15 * (
            etf_mom20 / (etf_vol20 * sqrt(20))
        )
        for dt in close.index:
            ranked: list[tuple[str, float]] = []
            for sector, etf in etf_by_sector.items():
                score = etf_score.at[dt, etf]
                if score != score:  # NaN check
                    continue
                if not (
                    etf_close.at[dt, etf] > etf_ma50.at[dt, etf]
                    and etf_ma50.at[dt, etf] > etf_ma200.at[dt, etf]
                    and etf_mom20.at[dt, etf] > 0
                    and etf_mom60.at[dt, etf] > 0
                ):
                    continue
                ranked.append((sector, float(score)))
            ranked.sort(key=lambda row: row[1], reverse=True)
            selected_sectors = [row[0] for row in ranked[: max(1, config.top_sector_count)]]
            allowed: set[str] = set()
            for sector in selected_sectors:
                allowed.update(sector_to_tickers.get(sector, []))
            sector_allowed_by_date[dt] = allowed

    weights = pd.DataFrame(0.0, index=close.index, columns=tickers)
    last_weights = pd.Series(0.0, index=tickers, dtype=float)
    turnover = 0.0

    start_idx = max(200, 60)
    rebalance_every = max(1, config.rebalance_every_days)

    for i, dt in enumerate(close.index):
        if i < start_idx:
            continue
        if i % rebalance_every != 0:
            weights.loc[dt] = last_weights
            continue

        if not bool(market_on.loc[dt]):
            new_weights = pd.Series(0.0, index=tickers, dtype=float)
        else:
            row_score = raw_score.loc[dt, tickers]
            row_mask = tradable.loc[dt, tickers]
            if sector_allowed_by_date:
                allowed = sector_allowed_by_date.get(dt, set())
                if allowed:
                    row_mask = row_mask & pd.Series(
                        [ticker in allowed for ticker in tickers], index=tickers
                    )
            eligible = row_score[row_mask].dropna()
            if eligible.empty:
                new_weights = pd.Series(0.0, index=tickers, dtype=float)
            else:
                picked = eligible.sort_values(ascending=False).head(config.top_n).index.tolist()
                w = min(config.max_weight_per_stock, 1.0 / len(picked))
                new_weights = pd.Series(0.0, index=tickers, dtype=float)
                for ticker in picked:
                    new_weights.loc[ticker] = w
                # normalize if cap forced under-investment.
                total = float(new_weights.sum())
                if total > 0.0:
                    new_weights = new_weights / total

        turnover += float((new_weights - last_weights).abs().sum())
        last_weights = new_weights
        weights.loc[dt] = last_weights

    # One-day delayed execution assumption.
    shifted = weights.shift(1).fillna(0.0)
    gross_daily = (shifted * returns[tickers]).sum(axis=1)
    trading_cost = shifted.diff().abs().sum(axis=1).fillna(0.0) * (config.transaction_cost_bps / 10_000.0)
    net_daily = gross_daily - trading_cost
    net_daily = net_daily.loc[close.index[start_idx:]]

    equity = (1.0 + net_daily).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    periods = len(net_daily)
    annualized_return = float((1.0 + total_return) ** (252 / periods) - 1.0) if periods > 0 else 0.0
    volatility = float(net_daily.std(ddof=1) * sqrt(252)) if periods > 1 else 0.0
    sharpe = float(annualized_return / volatility) if volatility > 0 else 0.0
    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = float(-drawdown.min()) if len(drawdown) else 0.0
    win_rate = float((net_daily > 0).mean()) if periods > 0 else 0.0

    latest_date = str(close.index[-1].date())
    latest_weights = weights.iloc[-1]
    latest_picks = latest_weights[latest_weights > 0].sort_values(ascending=False).index.tolist()
    latest_weight_map = {ticker: float(latest_weights[ticker]) for ticker in latest_picks}
    latest_chart_links = build_chart_links(latest_picks, provider="yahoo")
    latest_tradingview_links = build_chart_links(latest_picks, provider="tradingview")

    return StockPickerRunResult(
        latest_date=latest_date,
        latest_picks=latest_picks,
        latest_weights=latest_weight_map,
        latest_chart_links=latest_chart_links,
        latest_tradingview_links=latest_tradingview_links,
        backtest=StockPickerBacktestResult(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            turnover=turnover,
            win_rate=win_rate,
            periods=periods,
        ),
    )


def _parse_nasdaq_listed(content: str) -> set[str]:
    symbols: set[str] = set()
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return symbols
    for line in lines[1:]:
        if line.startswith("File Creation Time"):
            continue
        parts = line.split("|")
        if len(parts) < 7:
            continue
        symbol = parts[0].strip().upper()
        security_name = parts[1].strip()
        test_issue = parts[3].strip().upper()
        etf = parts[6].strip().upper()
        if test_issue == "Y":
            continue
        if etf == "Y":
            continue
        if not _is_common_stock_name(security_name):
            continue
        normalized = _normalize_ticker(symbol)
        if normalized is not None:
            symbols.add(normalized)
    return symbols


def _fetch_wikipedia_symbols(url: str) -> list[str]:
    import pandas as pd  # type: ignore[import-not-found]
    import requests  # type: ignore[import-not-found]

    headers = {"User-Agent": "Mozilla/5.0 (compatible; qrt-platform/1.0; +https://example.org)"}
    html = requests.get(url, headers=headers, timeout=30).text
    if "Please set a user-agent" in html:
        raise RuntimeError(f"Wikipedia blocked request for {url}")
    tables = pd.read_html(StringIO(html))
    symbols: set[str] = set()
    for table in tables:
        cols = [str(c) for c in table.columns]
        symbol_col = None
        for col in cols:
            if col.lower() in {"symbol", "ticker", "ticker symbol"}:
                symbol_col = col
                break
        if symbol_col is None:
            continue
        for raw in table[symbol_col].astype(str):
            ticker = _normalize_ticker(raw)
            if ticker is not None:
                symbols.add(ticker)
        if symbols:
            break
    if not symbols:
        raise RuntimeError(f"Could not extract symbols from {url}")
    return sorted(symbols)


def _parse_other_listed(
    content: str,
    include_nyse_arca: bool,
    include_nyse_american: bool,
) -> set[str]:
    symbols: set[str] = set()
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return symbols
    allowed_exchanges = {"N"}
    if include_nyse_american:
        allowed_exchanges.add("A")
    if include_nyse_arca:
        allowed_exchanges.add("P")
    for line in lines[1:]:
        if line.startswith("File Creation Time"):
            continue
        parts = line.split("|")
        if len(parts) < 7:
            continue
        symbol = parts[0].strip().upper()
        security_name = parts[1].strip()
        exchange = parts[2].strip().upper()
        etf = parts[4].strip().upper()
        test_issue = parts[6].strip().upper()
        if exchange not in allowed_exchanges:
            continue
        if etf == "Y":
            continue
        if test_issue == "Y":
            continue
        if not _is_common_stock_name(security_name):
            continue
        normalized = _normalize_ticker(symbol)
        if normalized is not None:
            symbols.add(normalized)
    return symbols


_VALID_TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:-[A-Z]{1,2})?$")


def _normalize_ticker(symbol: str) -> str | None:
    # Nasdaq Trader uses dot notation for some share classes, Yahoo uses hyphen.
    normalized = symbol.replace(".", "-").replace("$", "").strip().upper()
    if not _VALID_TICKER_RE.match(normalized):
        return None
    if "-" in normalized:
        suffix = normalized.split("-", 1)[1]
        if suffix in {"W", "WS", "WD", "WT", "U", "R", "RT"}:
            return None
    if len(normalized) == 5 and normalized[-1] in {"W", "R", "U", "V", "X"}:
        return None
    return normalized


def _is_common_stock_name(security_name: str) -> bool:
    name = security_name.upper()
    if "ETF" in name or "EXCHANGE TRADED FUND" in name:
        return False
    blocked = [
        "WARRANT",
        "RIGHT",
        "UNIT",
        "PREFERRED",
        "TRUST",
        "FUND",
        "NOTE",
        "BOND",
        "DEBENTURE",
        "INDEX",
        "ETN",
    ]
    if any(token in name for token in blocked):
        return False
    keep = ["COMMON STOCK", "COMMON SHARES", "ORDINARY SHARES", "CLASS A", "CLASS B", "CLASS C"]
    return any(token in name for token in keep)
