# QRT Python Track

A learning project focused on Python skills needed for quant research-platform roles:

- typed API design
- deterministic backtesting
- reusable strategy/data abstractions
- experiment orchestration (sequential + parallel)
- testing, CI, and reliability
- deployment-facing cloud integration patterns

## Quickstart (fresh clone)

```bash
git clone git@github.com:fredLuv/python_research_platform_gpt_assisted.git
cd python_research_platform_gpt_assisted
./scripts/bootstrap.sh
source .venv/bin/activate
./scripts/check.sh
```

## Layout

- `src/qrt_platform/` core library
- `tests/` unit tests
- `examples/` runnable demos
- `scripts/` local/CI entry scripts
- `.github/workflows/` CI pipeline
- `deploy/` cloud deployment templates
- `data/raw/` local market datasets
- `outputs/` generated experiment artifacts

## Quality gates (local)

```bash
./scripts/check.sh
```

This runs:

- unit tests (`unittest`)
- `ruff` lint
- `mypy` type-check

## CI

GitHub Actions workflow:

- `.github/workflows/python-ci.yml`

Pipeline stages:

1. install package + dev deps
2. run unit tests
3. run `ruff`
4. run `mypy`

## Demos

### 1) Minimal synthetic demo

```bash
PYTHONPATH=src python examples/basic_backtest_demo.py
```

### 2) Real market data (SPY daily)

```bash
PYTHONPATH=src python examples/real_data_ma_demo.py
```

### 3) Multi-strategy comparison (sequential)

```bash
PYTHONPATH=src python examples/strategy_comparison_demo.py
```

### 4) Parallel experiment + artifacts (CSV/JSON)

```bash
PYTHONPATH=src python examples/parallel_experiment_demo.py
```

### 5) Thread vs Process scaling benchmark

```bash
PYTHONPATH=src python examples/concurrency_benchmark_demo.py
```

### 6) Chain-of-Alpha Lite (non-LLM) factor mining demo

```bash
PYTHONPATH=src python examples/chain_of_alpha_lite_demo.py
```

### 7) Formula DSL alpha mining demo

```bash
PYTHONPATH=src python examples/formula_alpha_mining_demo.py
```

### 8) Real stock picker (NASDAQ + NYSE universe)

```bash
PYTHONPATH=src python examples/real_stock_picker_demo.py
```

Optional:

```bash
STOCK_UNIVERSE_LIMIT=1500 PYTHONPATH=src python examples/real_stock_picker_demo.py
```

### Live SOL App (Moved)

SOL-USD live market terminal is now maintained separately in:

- `/Users/fred/Desktop/IMC-Java-Code/sol_live_update`

## Production-style job run

```bash
PYTHONPATH=src python scripts/run_job.py
```

Config is environment-driven:

- `DATA_SOURCE_PATH` (default: `data/raw/spy_us_daily.csv`)
- `OUTPUT_DIR` (default: `outputs`)
- `RUN_MODE` (`thread` or `process`, default: `thread`)
- `MAX_WORKERS` (default: `4`)
- `LOG_LEVEL` (default: `INFO`)

### Formula Alpha Mining Job

Run a production-style factor mining job with expression DSL and artifact outputs:

```bash
PYTHONPATH=src \
JOB_KIND=alpha_mining \
DATA_SOURCE_PATH=data/raw/spy_us_daily.csv \
OUTPUT_DIR=outputs \
python scripts/run_job.py
```

Optional knobs:

- `ALPHA_ROUNDS` (default `6`)
- `ALPHA_GENERATION_BATCH` (default `10`)
- `ALPHA_OPT_STEPS` (default `3`)
- `ALPHA_TOP_K` (default `10`)
- `ALPHA_SIGNAL_HORIZON` (default `1`)
- `ALPHA_MIN_STRENGTH`, `ALPHA_MIN_CONSISTENCY`, `ALPHA_MIN_EFFICIENCY`, `ALPHA_MIN_DIVERSITY`

Artifacts:

- `alpha_factors_<timestamp>.csv`
- `alpha_factors_<timestamp>.json`
- `alpha_summary_<timestamp>.json`

### Stock Picker Job

```bash
PYTHONPATH=src \
JOB_KIND=stock_picker \
OUTPUT_DIR=outputs \
python scripts/run_job.py
```

This job pulls all listed NASDAQ + NYSE symbols, downloads batched Yahoo Finance OHLCV history,
runs the trend-continuation stock picker, and writes:

- `stock_picks_<timestamp>.csv` (weights + chart links)
- `stock_picks_<timestamp>.json`
- `stock_picker_summary_<timestamp>.json`

Optional knobs:

- `STOCK_UNIVERSE_MODE` (`sp1500` default; options: `sp500`, `sp1500`, `nasdaq100`, `all_us`)
- `STOCK_PICKER_TOP_DOWN` (`1` default): rank sector ETFs first, then pick stocks within leading sectors
- `STOCK_PICKER_YEARS` (default `5`)
- `STOCK_PICKER_TOP_N` (default `12`)
- `STOCK_PICKER_REBALANCE_DAYS` (default `5`)
- `STOCK_PICKER_MIN_PRICE` (default `10`)
- `STOCK_PICKER_MAX_WEIGHT` (default `0.10`)
- `STOCK_PICKER_COST_BPS` (default `10`)
- `STOCK_PICKER_BATCH_SIZE` (default `50`)
- `STOCK_PICKER_MAX_RETRIES` (default `3`)
- `STOCK_PICKER_RETRY_SLEEP` (default `0.5`)
- `STOCK_UNIVERSE_LIMIT` (optional safety cap for runtime control)
- `STOCK_PICKER_USE_CACHE` (default `1`)
- `STOCK_PICKER_SAVE_CACHE` (default `1`)
- `STOCK_PICKER_CACHE_DIR` (default `outputs/cache`)

### Stock Picker Background Prep Job

Use this to pre-download and cache market data, then run `JOB_KIND=stock_picker` fast from cache:

```bash
PYTHONPATH=src \
JOB_KIND=stock_picker_prep \
OUTPUT_DIR=outputs \
python scripts/run_job.py
```

## Deployment-facing setup

### Run as a container

```bash
docker build -t qrt-platform:latest .
docker run --rm -e RUN_MODE=thread -e MAX_WORKERS=4 qrt-platform:latest
```

### Cloud template

- `deploy/aws_batch_job.template.json`
- `deploy/README.md`

## Reliability patterns implemented

- explicit process exit code from job runner
- env-driven runtime config for orchestration systems
- atomic CSV/JSON output writes to avoid partial artifacts
- deterministic ranking/sorting of experiment outputs

## Optional online data loader dependencies

```bash
pip install yfinance pandas
```

## Simple PDF Rendering (Chrome)

For bilingual CJK + English text, this route is the most reliable and least stylized:

```bash
python scripts/render_pdf_via_chrome.py \
  --input outputs/internet_ai_expression_action_verbatim.txt \
  --output outputs/internet_ai_expression_action_stable.pdf \
  --title "The Internet and Generative AI"
```
