from __future__ import annotations

from dataclasses import dataclass
from math import tanh
from random import Random
from statistics import mean

from .backtest import run_backtest
from .factor_dsl import FactorDslEngine
from .models import BacktestConfig, BacktestResult, Bar


@dataclass(frozen=True, slots=True)
class FormulaSpec:
    name: str
    expression: str
    invert: bool = False


@dataclass(frozen=True, slots=True)
class FormulaMetrics:
    strength: float
    consistency: float
    efficiency: float
    diversity: float
    score: float


@dataclass(frozen=True, slots=True)
class EvaluatedFormula:
    spec: FormulaSpec
    metrics: FormulaMetrics
    signal: list[float | None]
    positions: list[float]
    backtest: BacktestResult


@dataclass(frozen=True, slots=True)
class FormulaThresholds:
    min_strength: float = 0.02
    min_consistency: float = 0.05
    min_efficiency: float = 0.30
    min_diversity: float = 0.03


@dataclass(frozen=True, slots=True)
class FormulaMiningConfig:
    rounds: int = 6
    generation_batch: int = 10
    optimization_steps: int = 3
    max_effective_pool: int = 30
    top_k: int = 10
    signal_horizon: int = 1
    thresholds: FormulaThresholds = FormulaThresholds()
    backtest: BacktestConfig = BacktestConfig(initial_cash=1_000_000.0, transaction_cost_bps=2.0)


@dataclass(frozen=True, slots=True)
class FormulaMiningReport:
    effective_factors: list[EvaluatedFormula]
    deprecated_factors: list[EvaluatedFormula]
    integrated_backtest: BacktestResult | None


class FormulaChainOfAlpha:
    def __init__(self, config: FormulaMiningConfig | None = None, seed: int = 17) -> None:
        self.config = config or FormulaMiningConfig()
        self._random = Random(seed)
        self._engine = FactorDslEngine()
        self._seed_formulas = _seed_formulas()

    def run(self, bars: list[Bar]) -> FormulaMiningReport:
        if len(bars) < 260:
            raise ValueError("bars must contain at least 260 entries")
        effective: list[EvaluatedFormula] = []
        deprecated: list[EvaluatedFormula] = []
        used: set[tuple[str, bool]] = set()

        for round_idx in range(self.config.rounds):
            generated = self._generate(round_idx, effective, deprecated, used)
            for spec in generated:
                used.add((spec.expression, spec.invert))
                best = self._evaluate(spec, bars, effective)
                current = spec
                for _ in range(self.config.optimization_steps):
                    candidate = _mutate_spec(current, self._random)
                    if (candidate.expression, candidate.invert) in used:
                        continue
                    used.add((candidate.expression, candidate.invert))
                    evaluated = self._evaluate(candidate, bars, effective)
                    if evaluated.metrics.score > best.metrics.score:
                        best = evaluated
                        current = candidate
                if _is_effective(best.metrics, self.config.thresholds):
                    effective.append(best)
                    effective.sort(key=lambda row: row.metrics.score, reverse=True)
                    effective = effective[: self.config.max_effective_pool]
                else:
                    deprecated.append(best)

        effective.sort(key=lambda row: row.metrics.score, reverse=True)
        top = effective[: self.config.top_k]
        integrated = _integrated_backtest(top, bars, self.config.backtest)
        return FormulaMiningReport(
            effective_factors=top,
            deprecated_factors=deprecated,
            integrated_backtest=integrated,
        )

    def _generate(
        self,
        round_idx: int,
        effective: list[EvaluatedFormula],
        deprecated: list[EvaluatedFormula],
        used: set[tuple[str, bool]],
    ) -> list[FormulaSpec]:
        if round_idx == 0:
            return [row for row in self._seed_formulas[: self.config.generation_batch]]

        out: list[FormulaSpec] = []
        for row in effective[:3]:
            mutated = _mutate_spec(row.spec, self._random)
            if (mutated.expression, mutated.invert) not in used:
                out.append(mutated)

        while len(out) < self.config.generation_batch:
            base = self._seed_formulas[self._random.randrange(0, len(self._seed_formulas))]
            candidate = _mutate_spec(base, self._random)
            if (candidate.expression, candidate.invert) in used:
                continue
            if _is_deprecated_like(candidate, deprecated):
                continue
            out.append(candidate)
        return out[: self.config.generation_batch]

    def _evaluate(
        self, spec: FormulaSpec, bars: list[Bar], effective: list[EvaluatedFormula]
    ) -> EvaluatedFormula:
        signal = self._engine.evaluate(spec.expression, bars)
        if spec.invert:
            signal = [(-x if x is not None else None) for x in signal]
        positions = _signal_to_positions(signal, z_window=20)
        backtest = run_backtest(_PositionSeriesStrategy(positions), bars, self.config.backtest)
        forward = _forward_returns(bars, self.config.signal_horizon)

        strength = abs(_corr(signal, forward))
        consistency = _consistency(signal, forward)
        efficiency = _efficiency(backtest, len(bars))
        diversity = _diversity(signal, [row.signal for row in effective])

        metrics = FormulaMetrics(
            strength=strength,
            consistency=consistency,
            efficiency=efficiency,
            diversity=diversity,
            score=(0.40 * strength + 0.25 * consistency + 0.20 * efficiency + 0.15 * diversity),
        )
        return EvaluatedFormula(
            spec=spec,
            metrics=metrics,
            signal=signal,
            positions=positions,
            backtest=backtest,
        )


class _PositionSeriesStrategy:
    def __init__(self, positions: list[float]) -> None:
        self._positions = positions
        self._idx = 0

    def target_position(self, bar: Bar) -> float:
        if self._idx >= len(self._positions):
            return self._positions[-1]
        value = self._positions[self._idx]
        self._idx += 1
        return value


def _seed_formulas() -> list[FormulaSpec]:
    seeds: list[FormulaSpec] = []
    windows = [3, 5, 8, 13, 21, 34, 55]
    for n in windows:
        seeds.extend(
            [
                FormulaSpec(
                    name=f"mom_n{n}",
                    expression=f"Div(Sub($close, Ref($close, {n})), Ref($close, {n}))",
                ),
                FormulaSpec(
                    name=f"mean_dev_n{n}",
                    expression=f"Div(Sub($close, Mean($close, {n})), Add(Std($close, {n}), 0.000001))",
                ),
                FormulaSpec(
                    name=f"breakout_n{n}",
                    expression=(
                        f"Sub(Div(Sub($close, Min($low, {n})), "
                        f"Add(Sub(Max($high, {n}), Min($low, {n})), 0.000001)), 0.5)"
                    ),
                ),
                FormulaSpec(
                    name=f"vol_adj_n{n}",
                    expression=(
                        f"Div(Div(Sub($close, Ref($close, {n})), Ref($close, {n})), "
                        f"Add(Std(Delta($close, 1), {n}), 0.000001))"
                    ),
                ),
                FormulaSpec(
                    name=f"price_vol_corr_n{n}",
                    expression=f"Corr(Rank(Delta($close, 1), {n}), Rank(Delta($volume, 1), {n}), {n})",
                ),
            ]
        )
    return seeds


def _mutate_spec(spec: FormulaSpec, random: Random) -> FormulaSpec:
    expression = spec.expression
    windows = _extract_int_literals(expression)
    if windows:
        old = windows[random.randrange(0, len(windows))]
        new = max(2, min(120, old + random.choice([-3, -2, -1, 1, 2, 3, 5, -5])))
        expression = expression.replace(f"{old}", f"{new}", 1)
    invert = spec.invert if random.random() > 0.2 else not spec.invert
    return FormulaSpec(name=f"{spec.name}_m", expression=expression, invert=invert)


def _extract_int_literals(text: str) -> list[int]:
    out: list[int] = []
    token = ""
    for ch in text:
        if ch.isdigit():
            token += ch
        else:
            if token:
                out.append(int(token))
                token = ""
    if token:
        out.append(int(token))
    return out


def _is_deprecated_like(spec: FormulaSpec, deprecated: list[EvaluatedFormula]) -> bool:
    for row in deprecated[:25]:
        if row.spec.expression == spec.expression and row.spec.invert == spec.invert:
            return True
    return False


def _is_effective(metrics: FormulaMetrics, thresholds: FormulaThresholds) -> bool:
    return (
        metrics.strength >= thresholds.min_strength
        and metrics.consistency >= thresholds.min_consistency
        and metrics.efficiency >= thresholds.min_efficiency
        and metrics.diversity >= thresholds.min_diversity
    )


def _signal_to_positions(signal: list[float | None], z_window: int) -> list[float]:
    out: list[float] = [0.0] * len(signal)
    values: list[float] = []
    for idx, value in enumerate(signal):
        if value is None:
            out[idx] = 0.0
            continue
        values.append(value)
        window = values[-z_window:]
        mu = mean(window)
        std = _std(window)
        if std <= 1e-9:
            out[idx] = 0.0
            continue
        z = (value - mu) / std
        out[idx] = _clip(z / 2.0, -1.0, 1.0)
    return out


def _forward_returns(bars: list[Bar], horizon: int) -> list[float | None]:
    closes = [bar.close for bar in bars]
    out: list[float | None] = [None] * len(closes)
    for i in range(len(closes) - horizon):
        base = closes[i]
        nxt = closes[i + horizon]
        out[i] = (nxt / base) - 1.0 if base > 0 else None
    return out


def _corr(a: list[float | None], b: list[float | None]) -> float:
    x: list[float] = []
    y: list[float] = []
    for va, vb in zip(a, b):
        if va is None or vb is None:
            continue
        x.append(va)
        y.append(vb)
    return _pearson(x, y)


def _pearson(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    mx = mean(x)
    my = mean(y)
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 1e-12 or vy <= 1e-12:
        return 0.0
    return cov / (vx * vy) ** 0.5


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mu = mean(values)
    var = sum((x - mu) ** 2 for x in values) / (len(values) - 1)
    if var <= 0:
        return 0.0
    return var**0.5


def _consistency(signal: list[float | None], forward: list[float | None]) -> float:
    pairs: list[tuple[float, float]] = []
    for s, fwd in zip(signal, forward):
        if s is None or fwd is None:
            continue
        pairs.append((s, fwd))
    if len(pairs) < 30:
        return 0.0
    chunk = max(10, len(pairs) // 6)
    chunk_ics: list[float] = []
    for i in range(0, len(pairs), chunk):
        sample = pairs[i : i + chunk]
        if len(sample) < 6:
            continue
        x = [row[0] for row in sample]
        y = [row[1] for row in sample]
        chunk_ics.append(_pearson(x, y))
    if not chunk_ics:
        return 0.0
    mu = mean(chunk_ics)
    sigma = _std(chunk_ics)
    if sigma <= 1e-9:
        return 0.0
    return max(0.0, min(1.0, tanh(abs(mu / sigma))))


def _efficiency(backtest: BacktestResult, bars_len: int) -> float:
    if bars_len <= 1:
        return 0.0
    turnover_per_bar = backtest.turnover / (bars_len - 1)
    return 1.0 / (1.0 + 4.0 * turnover_per_bar)


def _diversity(signal: list[float | None], accepted: list[list[float | None]]) -> float:
    if not accepted:
        return 1.0
    distances = [1.0 - abs(_corr(signal, other)) for other in accepted]
    if not distances:
        return 0.0
    return _clip(min(distances), 0.0, 1.0)


def _integrated_backtest(
    effective: list[EvaluatedFormula], bars: list[Bar], config: BacktestConfig
) -> BacktestResult | None:
    if not effective:
        return None
    count = len(effective)
    positions: list[float] = []
    for idx in range(len(bars)):
        avg = sum(row.positions[idx] for row in effective) / count
        positions.append(_clip(avg, -1.0, 1.0))
    return run_backtest(_PositionSeriesStrategy(positions), bars, config)


def _clip(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
