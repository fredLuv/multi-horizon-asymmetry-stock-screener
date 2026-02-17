# QRT Python Track

A learning project focused on Python skills needed for quant research-platform roles:

- typed API design
- deterministic backtesting
- reusable strategy/data abstractions
- experiment orchestration (sequential + parallel)
- testing, CI, and reliability
- deployment-facing cloud integration patterns

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
cd /Users/fred/Desktop/IMC-Java-Code/python_research_platform
./scripts/check.sh
```

This runs:

- unit tests (`unittest`)
- `ruff` lint (if installed)
- `mypy` type-check (if installed)

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
cd /Users/fred/Desktop/IMC-Java-Code/python_research_platform
PYTHONPATH=src python3 examples/basic_backtest_demo.py
```

### 2) Real market data (SPY daily)

```bash
cd /Users/fred/Desktop/IMC-Java-Code/python_research_platform
PYTHONPATH=src python3 examples/real_data_ma_demo.py
```

### 3) Multi-strategy comparison (sequential)

```bash
cd /Users/fred/Desktop/IMC-Java-Code/python_research_platform
PYTHONPATH=src python3 examples/strategy_comparison_demo.py
```

### 4) Parallel experiment + artifacts (CSV/JSON)

```bash
cd /Users/fred/Desktop/IMC-Java-Code/python_research_platform
PYTHONPATH=src python3 examples/parallel_experiment_demo.py
```

### 5) Thread vs Process scaling benchmark

```bash
cd /Users/fred/Desktop/IMC-Java-Code/python_research_platform
PYTHONPATH=src python3 examples/concurrency_benchmark_demo.py
```

## Deployment-facing setup

### Run as a container

```bash
cd /Users/fred/Desktop/IMC-Java-Code/python_research_platform
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

## Optional data loader dependencies

```bash
pip install yfinance pandas
```
