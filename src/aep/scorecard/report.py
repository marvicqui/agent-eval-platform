"""Render the scorecard: markdown for humans/PR comments, JSON for baselines.

The markdown table is what lands in the PR conversation — it must be
readable at a glance: metric, value, threshold, baseline delta, verdict.
The JSON baseline is the committed regression reference the next run is
compared against.
"""

import json
from pathlib import Path

from aep.scorecard.aggregate import MetricAggregate
from aep.scorecard.thresholds import GateResult, ThresholdRule

BASELINE_FILE = Path("evals/baseline.json")


def load_baseline(path: Path = BASELINE_FILE) -> dict[str, float]:
    """Metric -> mean from the committed baseline. Empty if none exists yet."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    means: dict[str, float] = data.get("means", {})
    return means


def write_baseline(
    aggregates: dict[str, MetricAggregate],
    derived: dict[str, float | None],
    meta: dict[str, object],
    path: Path = BASELINE_FILE,
) -> None:
    payload = {
        "meta": meta,
        "means": {name: round(agg.mean, 4) for name, agg in sorted(aggregates.items())},
        "derived": {k: (round(v, 4) if v is not None else None) for k, v in derived.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def render_markdown(
    aggregates: dict[str, MetricAggregate],
    derived: dict[str, float | None],
    rules: dict[str, ThresholdRule],
    baseline_means: dict[str, float],
    gate: GateResult,
    meta: dict[str, object],
) -> str:
    lines = [
        f"## Eval scorecard — `{meta.get('dataset', '?')}` vs `{meta.get('sut', '?')}`",
        "",
        f"**Gate: {'✅ PASS' if gate.passed else '❌ FAIL'}** · "
        f"{meta.get('cases', '?')} cases · "
        f"${meta.get('total_cost_usd', 0):.4f} · {meta.get('wall_seconds', 0):.0f}s wall",
        "",
        "| Metric | Mean | Min/Max seen | Threshold | Baseline | Δ | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in sorted(aggregates):
        aggregate = aggregates[name]
        rule = rules.get(name)
        threshold = ""
        if rule is not None:
            parts = []
            if rule.min is not None:
                parts.append(f"≥ {rule.min}")
            if rule.max is not None:
                parts.append(f"≤ {rule.max}")
            threshold = ", ".join(parts)
        baseline = baseline_means.get(name)
        delta = f"{aggregate.mean - baseline:+.3f}" if baseline is not None else "—"
        lines.append(
            f"| {name} | {aggregate.mean:.3f} "
            f"| {aggregate.minimum:.2f}/{aggregate.maximum:.2f} "
            f"| {threshold or '—'} "
            f"| {f'{baseline:.3f}' if baseline is not None else '—'} "
            f"| {delta} | {aggregate.errors or ''} |"
        )

    lines += ["", "### Judge bias monitors", ""]
    flip = derived.get("position_flip_rate")
    verbosity = derived.get("verbosity_correlation")
    lines.append(
        f"- `position_flip_rate`: "
        f"{f'{flip:.3f}' if flip is not None else 'n/a'} (target < 0.10)"
    )
    lines.append(
        f"- `verbosity_correlation`: "
        f"{f'{verbosity:.3f}' if verbosity is not None else 'n/a'} (target |r| < 0.30)"
    )

    if not gate.passed:
        lines += ["", "### Failures", ""]
        for failure in gate.failures:
            lines.append(f"- **{failure.metric}**: {failure.reason}")
    return "\n".join(lines) + "\n"
