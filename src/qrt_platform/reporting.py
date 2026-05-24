from __future__ import annotations

import csv
import json
from dataclasses import asdict
from io import TextIOWrapper
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import TracebackType

from .alpha_formula_mining import EvaluatedFormula, FormulaMiningReport
from .experiment import ExperimentRow
from .stock_picker import StockPickerRunResult


def write_experiment_json(rows: list[ExperimentRow], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = [
        {
            "strategy": row.name,
            **asdict(row.result),
        }
        for row in rows
    ]

    _atomic_write_text(path, json.dumps(payload, indent=2))


def write_experiment_csv(rows: list[ExperimentRow], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "strategy",
        "total_return",
        "annualized_return",
        "volatility",
        "sharpe",
        "max_drawdown",
        "win_rate",
        "turnover",
        "final_equity",
    ]

    with _atomic_open_csv(path) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "strategy": row.name,
                    "total_return": row.result.total_return,
                    "annualized_return": row.result.annualized_return,
                    "volatility": row.result.volatility,
                    "sharpe": row.result.sharpe,
                    "max_drawdown": row.result.max_drawdown,
                    "win_rate": row.result.win_rate,
                    "turnover": row.result.turnover,
                    "final_equity": row.result.final_equity,
                }
            )


def write_formula_factors_json(
    report: FormulaMiningReport, output_path: str | Path, top_n: int = 20
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "effective_count": len(report.effective_factors),
        "deprecated_count": len(report.deprecated_factors),
        "integrated_backtest": (
            asdict(report.integrated_backtest) if report.integrated_backtest is not None else None
        ),
        "effective_factors": [_factor_to_json(row) for row in report.effective_factors[:top_n]],
    }
    _atomic_write_text(path, json.dumps(payload, indent=2))


def write_formula_factors_csv(
    report: FormulaMiningReport, output_path: str | Path, top_n: int = 50
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "name",
        "expression",
        "invert",
        "score",
        "strength",
        "consistency",
        "efficiency",
        "diversity",
        "backtest_sharpe",
        "backtest_total_return",
        "backtest_turnover",
    ]
    with _atomic_open_csv(path) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report.effective_factors[:top_n]:
            writer.writerow(
                {
                    "name": row.spec.name,
                    "expression": row.spec.expression,
                    "invert": row.spec.invert,
                    "score": row.metrics.score,
                    "strength": row.metrics.strength,
                    "consistency": row.metrics.consistency,
                    "efficiency": row.metrics.efficiency,
                    "diversity": row.metrics.diversity,
                    "backtest_sharpe": row.backtest.sharpe,
                    "backtest_total_return": row.backtest.total_return,
                    "backtest_turnover": row.backtest.turnover,
                }
            )


def _factor_to_json(row: EvaluatedFormula) -> dict[str, object]:
    return {
        "name": row.spec.name,
        "expression": row.spec.expression,
        "invert": row.spec.invert,
        "metrics": asdict(row.metrics),
        "backtest": asdict(row.backtest),
    }


def write_stock_picker_json(result: StockPickerRunResult, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "latest_date": result.latest_date,
        "latest_picks": result.latest_picks,
        "latest_weights": result.latest_weights,
        "latest_chart_links": result.latest_chart_links,
        "latest_tradingview_links": result.latest_tradingview_links,
        "backtest": asdict(result.backtest),
    }
    _atomic_write_text(path, json.dumps(payload, indent=2))


def write_stock_picker_csv(result: StockPickerRunResult, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["ticker", "weight", "yahoo_chart", "tradingview_chart"]
    with _atomic_open_csv(path) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for ticker in result.latest_picks:
            writer.writerow(
                {
                    "ticker": ticker,
                    "weight": result.latest_weights[ticker],
                    "yahoo_chart": result.latest_chart_links[ticker],
                    "tradingview_chart": result.latest_tradingview_links[ticker],
                }
            )


def _atomic_write_text(path: Path, content: str) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


class _atomic_open_csv:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: TextIOWrapper | None = None
        self._tmp_path: Path | None = None

    def __enter__(self) -> TextIOWrapper:
        tmp_file = NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=self._path.parent,
            delete=False,
        )
        self._tmp_path = Path(tmp_file.name)
        tmp_file.close()
        self._handle = self._tmp_path.open("w", encoding="utf-8", newline="")
        return self._handle

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._handle is None or self._tmp_path is None:
            return
        self._handle.close()
        if exc_type is None:
            self._tmp_path.replace(self._path)
        else:
            self._tmp_path.unlink(missing_ok=True)
