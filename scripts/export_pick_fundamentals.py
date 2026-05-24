from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yfinance as yf


def _latest_pick_file(outputs_dir: Path) -> Path:
    files = sorted(outputs_dir.glob("stock_picks_*.csv"))
    if not files:
        raise FileNotFoundError("No stock_picks_*.csv found in outputs/")
    return files[-1]


def _fetch_with_retries(ticker: str, retries: int = 4, sleep_seconds: float = 2.0) -> dict[str, object]:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            info = yf.Ticker(ticker).info or {}
            return info
        except Exception as exc:  # pragma: no cover - network boundary
            last_exc = exc
            time.sleep(sleep_seconds * (attempt + 1))
    return {"_error": str(last_exc) if last_exc else "unknown error"}


def main() -> None:
    outputs_dir = Path("/Users/fred/Desktop/IMC-Java-Code/python_research_platform/outputs")
    picks_path = _latest_pick_file(outputs_dir)
    tickers = pd.read_csv(picks_path)["ticker"].dropna().astype(str).str.upper().tolist()

    fields = [
        "longName",
        "sector",
        "industry",
        "marketCap",
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "enterpriseToEbitda",
        "returnOnEquity",
        "profitMargins",
        "revenueGrowth",
        "earningsGrowth",
        "debtToEquity",
        "currentRatio",
        "targetMeanPrice",
        "recommendationKey",
        "numberOfAnalystOpinions",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
        "currentPrice",
        "beta",
    ]

    rows: list[dict[str, object]] = []
    for ticker in tickers:
        info = _fetch_with_retries(ticker)
        row: dict[str, object] = {"ticker": ticker}
        for field in fields:
            row[field] = info.get(field)
        if "_error" in info:
            row["fetch_error"] = info["_error"]
        rows.append(row)

    df = pd.DataFrame(rows)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = outputs_dir / f"fundamentals_{ts}.json"
    csv_path = outputs_dir / f"fundamentals_{ts}.csv"
    md_path = outputs_dir / f"fundamentals_report_{ts}.md"

    df.to_json(json_path, orient="records", indent=2)
    df.to_csv(csv_path, index=False)

    lines: list[str] = []
    lines.append("# Stock Fundamentals Snapshot")
    lines.append("")
    lines.append(f"- Generated: `{ts}`")
    lines.append(f"- Picks source: `{picks_path.name}`")
    lines.append("")
    lines.append("## Quick Quality/Valuation Notes")
    lines.append("")
    for _, row in df.iterrows():
        ticker = str(row["ticker"])
        name = row.get("longName") if pd.notna(row.get("longName")) else ticker
        pe_fwd = row.get("forwardPE")
        roe = row.get("returnOnEquity")
        growth = row.get("revenueGrowth")
        margin = row.get("profitMargins")
        rec = row.get("recommendationKey")
        err = row.get("fetch_error")
        if pd.notna(err):
            lines.append(f"- **{ticker}** ({name}): fetch error `{err}`")
            continue
        lines.append(
            "- **{ticker}** ({name}): fwdPE={fwd}, ROE={roe}, revGrowth={growth}, "
            "margin={margin}, analyst={rec}".format(
                ticker=ticker,
                name=name,
                fwd=_fmt_num(pe_fwd),
                roe=_fmt_pct(roe),
                growth=_fmt_pct(growth),
                margin=_fmt_pct(margin),
                rec=rec if pd.notna(rec) else "n/a",
            )
        )

    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append(f"- JSON: `{json_path}`")
    lines.append(f"- CSV: `{csv_path}`")
    lines.append(f"- MD: `{md_path}`")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "md": str(md_path)}, indent=2))


def _fmt_num(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def _fmt_pct(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return str(value)


if __name__ == "__main__":
    main()
