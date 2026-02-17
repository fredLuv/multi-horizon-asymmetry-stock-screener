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
