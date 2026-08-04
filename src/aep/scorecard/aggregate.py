"""Aggregate per-case scores into run-level metrics.

Rules that keep the aggregates honest:
- `None` scores (evaluator errors) are EXCLUDED from means and counted in
  `evaluator_error_rate` instead. Averaging in zeros for broken evaluations
  is how eval suites lie to their owners.
- Derived bias metrics are computed here, from raw per-case data:
  position_flip_rate (mean of position_flip) and verbosity_correlation
  (Pearson r between judge_overall and answer_length across cases).
"""

from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from aep.evaluators.base import Score
from aep.evaluators.judge import verbosity_correlation


class MetricAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    mean: float
    count: int  # cases with a real value
    errors: int  # cases where the evaluator failed (value None)
    minimum: float
    maximum: float


def aggregate_scores(scores: list[Score]) -> dict[str, MetricAggregate]:
    """Collapse per-case scores into one aggregate per metric name."""
    values: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    for score in scores:
        if score.value is None:
            errors[score.metric] += 1
        else:
            values[score.metric].append(score.value)

    aggregates: dict[str, MetricAggregate] = {}
    for metric in set(values) | set(errors):
        metric_values = values.get(metric, [])
        if not metric_values:
            continue  # metric errored on every case; error rate covers it
        aggregates[metric] = MetricAggregate(
            metric=metric,
            mean=sum(metric_values) / len(metric_values),
            count=len(metric_values),
            errors=errors.get(metric, 0),
            minimum=min(metric_values),
            maximum=max(metric_values),
        )
    return aggregates


def derived_bias_metrics(scores: list[Score]) -> dict[str, float | None]:
    """Bias metrics that only exist at run level.

    position_flip_rate: fraction of pairwise checks whose verdict flipped
    with presentation order (target < 0.10).
    verbosity_correlation: Pearson r between judge_overall and answer length
    (target |r| < 0.3). None when there is not enough data to say anything.
    """
    by_case_judge: dict[str, float] = {}
    by_case_length: dict[str, float] = {}
    flips: list[float] = []
    for score in scores:
        if score.value is None:
            continue
        if score.metric == "judge_overall":
            by_case_judge[score.case_id] = score.value
        elif score.metric == "answer_length":
            by_case_length[score.case_id] = score.value
        elif score.metric == "position_flip":
            flips.append(score.value)

    pairs = [
        (by_case_judge[cid], by_case_length[cid]) for cid in by_case_judge if cid in by_case_length
    ]
    return {
        "position_flip_rate": (sum(flips) / len(flips)) if flips else None,
        "verbosity_correlation": verbosity_correlation(pairs),
    }
