from __future__ import annotations

from datetime import datetime, timedelta

from qrt_platform import AlphaMiningConfig, ChainOfAlphaLite, FactorThresholds


def build_demo_bars(n: int = 500):
    price = 100.0
    start = datetime(2023, 1, 1)
    for i in range(n):
        trend = 0.0008 if i < 200 else (0.0003 if i < 350 else -0.0002)
        seasonal = 0.004 * ((i % 10) - 4) / 5.0
        price *= 1.0 + trend + seasonal
        yield start + timedelta(days=i), max(1.0, price)


def main() -> None:
    # Build bars as dataclasses from the library to keep example self-contained.
    from qrt_platform import Bar

    bars = [Bar(ts=ts, close=close) for ts, close in build_demo_bars()]

    config = AlphaMiningConfig(
        rounds=4,
        generation_batch=8,
        optimization_steps=2,
        max_new_per_round=5,
        top_k=6,
        thresholds=FactorThresholds(
            min_strength=0.01,
            min_consistency=0.02,
            min_efficiency=0.20,
            min_diversity=0.02,
        ),
    )

    report = ChainOfAlphaLite(config=config, seed=13).run(bars)
    print(f"effective_factors={len(report.effective_factors)}")
    print(f"deprecated_factors={len(report.deprecated_factors)}")
    for row in report.effective_factors[:5]:
        print(
            f"{row.spec.name} | score={row.metrics.score:.4f} "
            f"| strength={row.metrics.strength:.4f} | consistency={row.metrics.consistency:.4f} "
            f"| efficiency={row.metrics.efficiency:.4f} | diversity={row.metrics.diversity:.4f}"
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
