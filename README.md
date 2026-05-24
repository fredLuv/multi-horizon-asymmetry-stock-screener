# QRT Quantitative Research Platform

A production-grade quantitative research and stock ingestion platform designed for asset allocation, fundamental margins analysis, and volatility-skew option execution.

---

## 📖 Strategy & Playbook

For a comprehensive review of our quantitative and fundamental framework, read the **[Modern Quantitative & Fundamental Asymmetry Playbook (stock_analysis_flow.md)](stock_analysis_flow.md)**. It covers:
*   **Multi-Horizon Price-Path Asymmetry ($MHC\_QAS$):** Statistical skew calculations that eliminate lookback bias.
*   **Warren Buffett-Style Cash Filters:** Owner's earnings and Net-Net overrides.
*   **Options Premium Execution:** Optimal DTE, Delta range, and technical floor mappings.
*   **Defensive Option Rolling Matrix:** Step-by-step procedures for pre-emptive, ATM, and calendar rolls.

---

## 🚀 Quickstart

Initialize a fresh environment and run local quality gates:

```bash
git clone git@github.com:fredLuv/multi-horizon-asymmetry-stock-screener.git
cd multi-horizon-asymmetry-stock-screener
./scripts/bootstrap.sh
source .venv/bin/activate
./scripts/check.sh
```

---

## 🛠 Core Executables

The platform provides a suite of high-performance quantitative tools inside the `scripts/` directory:

### 1. Incremental Daily Ingestion & Screening Pipeline
Downloads incremental price updates, filters for highly active liquid listings ($ADV > 100k$ shares), compiles the asymmetry leaderboard, and charts cumulative returns:
```bash
python scripts/run_daily_pipeline.py
```
*   **Leaderboard:** `outputs/daily_pipeline_leaderboard.csv`
*   **Chart:** `outputs/asymmetry_leaders_performance.png`

### 2. Individual Stock Financials & Margins Dashboard
Analyzes trailing revenues, gross margins, net margins, FCF margins, and Net Cash trends:
```bash
python scripts/analyze_stock.py --ticker TICKER_A
```

### 3. Black-Scholes Options Greeks & Premium Yield Calculator
Calculates premium yields, annualized returns, Delta, Gamma, Theta, and Vega for cash-secured puts:
```bash
python scripts/analyze_options.py --ticker TICKER_D --strike 195.00 --dte 45 --iv 0.509
```

### 4. Multi-Ticker 3-Year Trailing Trend Comparison
Analyzes and compares margin, debt, and cash flow trajectories across multiple companies side-by-side:
```bash
python scripts/analyze_trends.py --tickers TICKER_A,TICKER_B,TICKER_C
```

---

## 📂 Repository Structure

```
├── README.md                      # Platform entry overview (This file)
├── stock_analysis_flow.md         # Master Quant & Options Playbook
├── src/qrt_platform/              # Core algorithmic backtesting & strategy engine
├── scripts/                       # Executable ingestion & analytical scripts
├── tests/                         # Full unit-testing suite
├── deploy/                        # Cloud deployment templates (AWS Batch / Docker)
└── outputs/                       # Database price cache, leaderboards, and charts
```

---

## ⚙️ CI & Deployment

*   **Quality Gates:** Evaluates testing (`unittest`), linting (`ruff`), and static types (`mypy`) via `./scripts/check.sh`.
*   **GitHub Actions:** Monitored automatically via `.github/workflows/python-ci.yml`.
*   **Docker Container:** Run as a containerized job:
    ```bash
    docker build -t qrt-platform:latest .
    docker run --rm qrt-platform:latest
    ```
