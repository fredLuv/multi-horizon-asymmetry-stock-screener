from __future__ import annotations

from datetime import datetime, timedelta

from qrt_platform import FormulaChainOfAlpha, FormulaMiningConfig, FormulaThresholds
from qrt_platform.models import Bar


def build_demo_bars(n: int = 500) -> list[Bar]:
    start = datetime(2023, 1, 1)
    price = 100.0
    bars: list[Bar] = []
    for i in range(n):
        trend = 0.0008 if i < 200 else (0.0004 if i < 350 else -0.0002)
        cycle = 0.004 * ((i % 9) - 4) / 4.0
        ret = trend + cycle
        price *= 1.0 + ret
        bars.append(
            Bar(
                ts=start + timedelta(days=i),
                close=max(1.0, price),
                high=price * 1.01,
                low=price * 0.99,
                volume=800_000 + (i % 17) * 10_000,
            )
        )
    return bars


def main() -> None:
    bars = build_demo_bars()
    config = FormulaMiningConfig(
        rounds=4,
        generation_batch=8,
        optimization_steps=2,
        top_k=6,
        thresholds=FormulaThresholds(
            min_strength=0.01,
            min_consistency=0.02,
            min_efficiency=0.2,
            min_diversity=0.02,
        ),
    )
    report = FormulaChainOfAlpha(config=config, seed=23).run(bars)
    print(f"effective_factors={len(report.effective_factors)}")
    print(f"deprecated_factors={len(report.deprecated_factors)}")
    for row in report.effective_factors[:5]:
        print(
            f"{row.spec.name} | expr={row.spec.expression} | score={row.metrics.score:.4f} "
            f"| sharpe={row.backtest.sharpe:.4f}"
        )
    if report.integrated_backtest is not None:
        r = report.integrated_backtest
        print(
            "integrated_backtest: "
            f"total_return={r.total_return:.4f}, annualized_return={r.annualized_return:.4f}, "
            f"sharpe={r.sharpe:.4f}, max_drawdown={r.max_drawdown:.4f}"
        )


if __name__ == "__main__":
    main()
