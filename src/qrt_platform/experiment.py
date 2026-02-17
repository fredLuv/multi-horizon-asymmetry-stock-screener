from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Literal

from .backtest import run_backtest
from .models import BacktestConfig, BacktestResult, Bar
from .strategy import Strategy

RunMode = Literal["thread", "process"]


@dataclass(frozen=True, slots=True)
class StrategySpec:
    name: str
    strategy_cls: type[Strategy]
    params: dict[str, Any] = field(default_factory=dict)

    def build(self) -> Strategy:
        return self.strategy_cls(**self.params)


@dataclass(frozen=True, slots=True)
class ExperimentRow:
    name: str
    result: BacktestResult


def run_experiment(
    strategy_specs: Iterable[StrategySpec],
    bars: list[Bar],
    config: BacktestConfig,
) -> list[ExperimentRow]:
    rows: list[ExperimentRow] = []
    for spec in strategy_specs:
        result = run_backtest(spec.build(), bars, config)
        rows.append(ExperimentRow(name=spec.name, result=result))

    rows.sort(key=lambda row: row.result.sharpe, reverse=True)
    return rows


def run_experiment_parallel(
    strategy_specs: Iterable[StrategySpec],
    bars: list[Bar],
    config: BacktestConfig,
    max_workers: int = 4,
    mode: RunMode = "thread",
) -> list[ExperimentRow]:
    specs = list(strategy_specs)
    if not specs:
        return []

    worker_count = max(1, min(max_workers, len(specs)))

    if mode == "thread":
        rows = _run_threaded(specs, bars, config, worker_count)
    elif mode == "process":
        rows = _run_process(specs, bars, config, worker_count)
    else:
        raise ValueError("mode must be 'thread' or 'process'")

    rows.sort(key=lambda row: row.result.sharpe, reverse=True)
    return rows


def _run_threaded(
    specs: list[StrategySpec],
    bars: list[Bar],
    config: BacktestConfig,
    max_workers: int,
) -> list[ExperimentRow]:
    rows: list[ExperimentRow] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_run_one, spec, bars, config) for spec in specs]
        for future in as_completed(futures):
            rows.append(future.result())
    return rows


def _run_process(
    specs: list[StrategySpec],
    bars: list[Bar],
    config: BacktestConfig,
    max_workers: int,
) -> list[ExperimentRow]:
    rows: list[ExperimentRow] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_run_one, spec, bars, config) for spec in specs]
        for future in as_completed(futures):
            rows.append(future.result())
    return rows


def _run_one(spec: StrategySpec, bars: list[Bar], config: BacktestConfig) -> ExperimentRow:
    result = run_backtest(spec.build(), bars, config)
    return ExperimentRow(name=spec.name, result=result)
