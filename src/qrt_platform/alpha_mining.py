from __future__ import annotations

from dataclasses import dataclass
from math import sqrt, tanh
from random import Random
from statistics import mean
from typing import Literal

from .backtest import run_backtest
from .models import BacktestConfig, BacktestResult, Bar

FactorKind = Literal[
    "momentum",
    "mean_reversion",
    "vol_adj_momentum",
    "breakout",
    "zscore_reversion",
]


@dataclass(frozen=True, slots=True)
class FactorSpec:
    name: str
    kind: FactorKind
    window: int
    scale: float = 1.0
    invert: bool = False


@dataclass(frozen=True, slots=True)
class FactorMetrics:
    strength: float
    consistency: float
    efficiency: float
    diversity: float
    score: float


@dataclass(frozen=True, slots=True)
class EvaluatedFactor:
    spec: FactorSpec
    metrics: FactorMetrics
    signal: list[float | None]
    positions: list[float]
    backtest: BacktestResult


@dataclass(frozen=True, slots=True)
class FactorThresholds:
    min_strength: float = 0.02
    min_consistency: float = 0.05
    min_efficiency: float = 0.35
    min_diversity: float = 0.05


@dataclass(frozen=True, slots=True)
class AlphaMiningConfig:
    rounds: int = 5
    generation_batch: int = 8
    optimization_steps: int = 3
    max_new_per_round: int = 5
    max_effective_pool: int = 25
    top_k: int = 8
    signal_horizon: int = 1
    thresholds: FactorThresholds = FactorThresholds()
    backtest: BacktestConfig = BacktestConfig(initial_cash=100_000.0, transaction_cost_bps=2.0)


@dataclass(frozen=True, slots=True)
class AlphaMiningReport:
    effective_factors: list[EvaluatedFactor]
    deprecated_factors: list[EvaluatedFactor]
    integrated_backtest: BacktestResult | None


class ChainOfAlphaLite:
    def __init__(self, config: AlphaMiningConfig | None = None, seed: int = 7) -> None:
        self.config = config or AlphaMiningConfig()
        self._random = Random(seed)
        self._seed_specs = self._build_seed_specs()

    def run(self, bars: list[Bar]) -> AlphaMiningReport:
        if len(bars) < 260:
            raise ValueError("bars must contain at least 260 entries for factor mining")
        if self.config.signal_horizon <= 0:
            raise ValueError("signal_horizon must be positive")

        effective: list[EvaluatedFactor] = []
        deprecated: list[EvaluatedFactor] = []
        used_specs: set[tuple[FactorKind, int, float, bool]] = set()

        for round_idx in range(self.config.rounds):
            candidates = self._generation_chain(round_idx, effective, deprecated, used_specs)
            for spec in candidates:
                used_specs.add(self._spec_key(spec))
                best_eval = self._evaluate_spec(spec, bars, effective)
                current = spec
                for _ in range(self.config.optimization_steps):
                    mutated = self._mutate(current)
                    if self._spec_key(mutated) in used_specs:
                        continue
                    used_specs.add(self._spec_key(mutated))
                    mutated_eval = self._evaluate_spec(mutated, bars, effective)
                    if mutated_eval.metrics.score > best_eval.metrics.score:
                        best_eval = mutated_eval
                        current = mutated

                if self._is_effective(best_eval.metrics):
                    effective.append(best_eval)
                    effective.sort(key=lambda row: row.metrics.score, reverse=True)
                    effective = effective[: self.config.max_effective_pool]
                else:
                    deprecated.append(best_eval)

        effective.sort(key=lambda row: row.metrics.score, reverse=True)
        top = effective[: self.config.top_k]
        integrated = self._integrated_backtest(top, bars)
        return AlphaMiningReport(
            effective_factors=top,
            deprecated_factors=deprecated,
            integrated_backtest=integrated,
        )

    def _generation_chain(
        self,
        round_idx: int,
        effective: list[EvaluatedFactor],
        deprecated: list[EvaluatedFactor],
        used_specs: set[tuple[FactorKind, int, float, bool]],
    ) -> list[FactorSpec]:
        if round_idx == 0:
            return [spec for spec in self._seed_specs[: self.config.generation_batch]]

        candidates: list[FactorSpec] = []
        # Reuse winners first, then mutate for diversity.
        winners = effective[: min(3, len(effective))]
        for row in winners:
            for _ in range(2):
                candidate = self._mutate(row.spec)
                if self._spec_key(candidate) not in used_specs:
                    candidates.append(candidate)

        while len(candidates) < self.config.generation_batch:
            base = self._seed_specs[self._random.randrange(0, len(self._seed_specs))]
            candidate = self._mutate(base)
            if self._spec_key(candidate) in used_specs:
                continue
            # Avoid repeating obvious failures.
            if self._too_similar_to_deprecated(candidate, deprecated):
                continue
            candidates.append(candidate)

        return candidates[: self.config.generation_batch]

    def _too_similar_to_deprecated(
        self, spec: FactorSpec, deprecated: list[EvaluatedFactor], max_checks: int = 20
    ) -> bool:
        for row in deprecated[:max_checks]:
            if (
                row.spec.kind == spec.kind
                and abs(row.spec.window - spec.window) <= 1
                and row.spec.invert == spec.invert
            ):
                return True
        return False

    def _evaluate_spec(
        self, spec: FactorSpec, bars: list[Bar], effective: list[EvaluatedFactor]
    ) -> EvaluatedFactor:
        signal = _build_signal(spec, bars)
        positions = _signal_to_positions(signal, bars, z_window=max(10, spec.window))
        backtest = run_backtest(_PositionSeriesStrategy(positions), bars, self.config.backtest)
        forward = _forward_returns(bars, horizon=self.config.signal_horizon)

        strength = abs(_corr(signal, forward))
        consistency = _consistency(signal, forward)
        efficiency = _efficiency_from_backtest(backtest, len(bars))
        diversity = _diversity(signal, [row.signal for row in effective])

        score = (
            0.40 * strength + 0.25 * consistency + 0.20 * efficiency + 0.15 * diversity
        )
        metrics = FactorMetrics(
            strength=strength,
            consistency=consistency,
            efficiency=efficiency,
            diversity=diversity,
            score=score,
        )
        return EvaluatedFactor(
            spec=spec,
            metrics=metrics,
            signal=signal,
            positions=positions,
            backtest=backtest,
        )

    def _is_effective(self, metrics: FactorMetrics) -> bool:
        t = self.config.thresholds
        return (
            metrics.strength >= t.min_strength
            and metrics.consistency >= t.min_consistency
            and metrics.efficiency >= t.min_efficiency
            and metrics.diversity >= t.min_diversity
        )

    def _mutate(self, spec: FactorSpec) -> FactorSpec:
        window = max(2, min(120, spec.window + self._random.choice([-3, -2, -1, 1, 2, 3])))
        kind = spec.kind
        if self._random.random() < 0.25:
            all_kinds: list[FactorKind] = [
                "momentum",
                "mean_reversion",
                "vol_adj_momentum",
                "breakout",
                "zscore_reversion",
            ]
            kind = all_kinds[self._random.randrange(0, len(all_kinds))]
        scale = max(0.25, min(3.0, spec.scale * self._random.choice([0.75, 1.0, 1.25])))
        invert = spec.invert if self._random.random() > 0.2 else not spec.invert
        name = f"{kind}_w{window}_s{scale:.2f}_{'inv' if invert else 'norm'}"
        return FactorSpec(name=name, kind=kind, window=window, scale=scale, invert=invert)

    def _integrated_backtest(
        self, effective: list[EvaluatedFactor], bars: list[Bar]
    ) -> BacktestResult | None:
        if not effective:
            return None

        count = len(effective)
        blended: list[float] = []
        for idx in range(len(bars)):
            avg = sum(row.positions[idx] for row in effective) / count
            blended.append(_clip(avg, -1.0, 1.0))
        return run_backtest(_PositionSeriesStrategy(blended), bars, self.config.backtest)

    @staticmethod
    def _spec_key(spec: FactorSpec) -> tuple[FactorKind, int, float, bool]:
        return (spec.kind, spec.window, round(spec.scale, 4), spec.invert)

    @staticmethod
    def _build_seed_specs() -> list[FactorSpec]:
        seeds: list[FactorSpec] = []
        windows = [3, 5, 8, 13, 21, 34, 55]
        kinds: list[FactorKind] = [
            "momentum",
            "mean_reversion",
            "vol_adj_momentum",
            "breakout",
            "zscore_reversion",
        ]
        for kind in kinds:
            for window in windows:
                name = f"{kind}_w{window}_s1.00_norm"
                seeds.append(FactorSpec(name=name, kind=kind, window=window))
        return seeds


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


def _build_signal(spec: FactorSpec, bars: list[Bar]) -> list[float | None]:
    closes = [bar.close for bar in bars]
    signal: list[float | None] = [None] * len(closes)
    n = spec.window
    for i in range(len(closes)):
        if i < n:
            continue
        close_now = closes[i]
        close_prev = closes[i - n]
        momentum = (close_now / close_prev) - 1.0 if close_prev > 0 else 0.0
        vol = _std_pct_changes(closes, i - n + 1, i)
        rolling_max = max(closes[i - n : i + 1])
        rolling_min = min(closes[i - n : i + 1])
        rolling_mean = mean(closes[i - n : i + 1])
        rolling_std = _std(closes[i - n : i + 1])

        raw = 0.0
        if spec.kind == "momentum":
            raw = momentum
        elif spec.kind == "mean_reversion":
            raw = -momentum
        elif spec.kind == "vol_adj_momentum":
            raw = momentum / vol if vol > 1e-8 else 0.0
        elif spec.kind == "breakout":
            denom = (rolling_max - rolling_min)
            raw = ((close_now - rolling_min) / denom) - 0.5 if denom > 1e-8 else 0.0
        elif spec.kind == "zscore_reversion":
            raw = -((close_now - rolling_mean) / rolling_std) if rolling_std > 1e-8 else 0.0
        value = raw * spec.scale
        signal[i] = -value if spec.invert else value
    return signal


def _signal_to_positions(signal: list[float | None], bars: list[Bar], z_window: int) -> list[float]:
    positions: list[float] = [0.0] * len(bars)
    values: list[float] = []
    for i, value in enumerate(signal):
        if value is None:
            positions[i] = 0.0
            continue
        values.append(value)
        window_values = values[-z_window:]
        mu = mean(window_values)
        sigma = _std(window_values)
        if sigma <= 1e-8:
            positions[i] = 0.0
            continue
        z = (value - mu) / sigma
        positions[i] = _clip(z / 2.0, -1.0, 1.0)
    return positions


def _forward_returns(bars: list[Bar], horizon: int) -> list[float | None]:
    closes = [bar.close for bar in bars]
    out: list[float | None] = [None] * len(closes)
    for i in range(len(closes) - horizon):
        base = closes[i]
        nxt = closes[i + horizon]
        out[i] = (nxt / base) - 1.0 if base > 0 else None
    return out


def _consistency(signal: list[float | None], forward: list[float | None], chunks: int = 6) -> float:
    pairs: list[tuple[float, float]] = []
    for s, fwd in zip(signal, forward):
        if s is None or fwd is None:
            continue
        pairs.append((s, fwd))
    if len(pairs) < 30:
        return 0.0

    size = max(5, len(pairs) // chunks)
    ics: list[float] = []
    for i in range(0, len(pairs), size):
        piece = pairs[i : i + size]
        if len(piece) < 5:
            continue
        x = [row[0] for row in piece]
        y = [row[1] for row in piece]
        ics.append(_pearson(x, y))
    if not ics:
        return 0.0
    m = mean(ics)
    std = _std(ics)
    if std <= 1e-8:
        return 0.0
    return max(0.0, min(1.0, tanh(abs(m / std))))


def _efficiency_from_backtest(backtest: BacktestResult, periods: int) -> float:
    if periods <= 1:
        return 0.0
    turnover_per_bar = backtest.turnover / (periods - 1)
    return 1.0 / (1.0 + 4.0 * turnover_per_bar)


def _diversity(signal: list[float | None], accepted_signals: list[list[float | None]]) -> float:
    if not accepted_signals:
        return 1.0
    distances: list[float] = []
    for other in accepted_signals:
        corr = _corr(signal, other)
        distances.append(1.0 - abs(corr))
    if not distances:
        return 0.0
    return max(0.0, min(1.0, min(distances)))


def _corr(a: list[float | None], b: list[float | None]) -> float:
    x: list[float] = []
    y: list[float] = []
    for va, vb in zip(a, b):
        if va is None or vb is None:
            continue
        x.append(va)
        y.append(vb)
    if len(x) < 5:
        return 0.0
    return _pearson(x, y)


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n != len(y) or n < 2:
        return 0.0
    mx = mean(x)
    my = mean(y)
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    vx = sum((xi - mx) ** 2 for xi in x)
    vy = sum((yi - my) ** 2 for yi in y)
    if vx <= 1e-12 or vy <= 1e-12:
        return 0.0
    return cov / sqrt(vx * vy)


def _std(values: list[float]) -> float:
    n = len(values)
    if n <= 1:
        return 0.0
    m = mean(values)
    var = sum((x - m) ** 2 for x in values) / (n - 1)
    if var <= 0:
        return 0.0
    return sqrt(var)


def _std_pct_changes(values: list[float], start_idx: int, end_idx: int) -> float:
    if end_idx - start_idx < 2:
        return 0.0
    rets: list[float] = []
    for i in range(max(1, start_idx), end_idx + 1):
        prev = values[i - 1]
        if prev <= 0:
            continue
        rets.append(values[i] / prev - 1.0)
    return _std(rets) if rets else 0.0


def _clip(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
