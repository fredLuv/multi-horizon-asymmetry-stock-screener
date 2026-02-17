from __future__ import annotations

import csv
import json
from dataclasses import asdict
from io import TextIOWrapper
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import TracebackType

from .experiment import ExperimentRow


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
