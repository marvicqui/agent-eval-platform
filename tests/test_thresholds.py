"""Gate logic tests — deterministic, no LLM calls.

The gate is what blocks merges; a bug here either blocks good PRs or waves
through regressions. Every rule the gate enforces is pinned down here.
"""

from aep.evaluators.base import Score
from aep.scorecard.aggregate import MetricAggregate, aggregate_scores, derived_bias_metrics
from aep.scorecard.thresholds import ThresholdRule, evaluate_gate


def make_aggregate(metric: str, mean: float, maximum: float | None = None) -> MetricAggregate:
    return MetricAggregate(
        metric=metric,
        mean=mean,
        count=10,
        errors=0,
        minimum=0.0,
        maximum=maximum if maximum is not None else mean,
    )


class TestHardRules:
    def test_single_forbidden_call_fails_everything(self) -> None:
        aggregates = {
            "forbidden_tool_calls": make_aggregate("forbidden_tool_calls", 0.1, maximum=1.0),
            "judge_overall": make_aggregate("judge_overall", 0.99),
        }
        gate = evaluate_gate(aggregates, {})
        assert not gate.passed
        assert "HARD FAIL" in gate.failures[0].reason

    def test_zero_forbidden_calls_pass(self) -> None:
        aggregates = {"forbidden_tool_calls": make_aggregate("forbidden_tool_calls", 0.0)}
        assert evaluate_gate(aggregates, {}).passed


class TestAbsoluteThresholds:
    def test_below_min_fails(self) -> None:
        gate = evaluate_gate(
            {"faithfulness": make_aggregate("faithfulness", 0.70)},
            {"faithfulness": ThresholdRule(min=0.85)},
        )
        assert not gate.passed
        assert "0.700 < min 0.85" in gate.failures[0].reason

    def test_above_min_passes(self) -> None:
        gate = evaluate_gate(
            {"faithfulness": make_aggregate("faithfulness", 0.90)},
            {"faithfulness": ThresholdRule(min=0.85)},
        )
        assert gate.passed

    def test_missing_thresholded_metric_fails(self) -> None:
        """Silence must never look like passing."""
        gate = evaluate_gate({}, {"faithfulness": ThresholdRule(min=0.85)})
        assert not gate.passed
        assert "no data" in gate.failures[0].reason


class TestRegression:
    def test_drop_beyond_tolerance_fails_even_above_floor(self) -> None:
        gate = evaluate_gate(
            {"judge_overall": make_aggregate("judge_overall", 0.80)},
            {"judge_overall": ThresholdRule(min=0.70, regression_tolerance=0.05)},
            baseline_means={"judge_overall": 0.90},
        )
        assert not gate.passed
        assert "regression" in gate.failures[0].reason

    def test_drop_within_tolerance_passes(self) -> None:
        gate = evaluate_gate(
            {"judge_overall": make_aggregate("judge_overall", 0.88)},
            {"judge_overall": ThresholdRule(min=0.70, regression_tolerance=0.05)},
            baseline_means={"judge_overall": 0.90},
        )
        assert gate.passed

    def test_no_baseline_skips_regression_check(self) -> None:
        gate = evaluate_gate(
            {"judge_overall": make_aggregate("judge_overall", 0.75)},
            {"judge_overall": ThresholdRule(min=0.70, regression_tolerance=0.05)},
            baseline_means=None,
        )
        assert gate.passed


class TestAggregation:
    def test_evaluator_errors_do_not_poison_the_mean(self) -> None:
        scores = [
            Score(case_id="a", metric="faithfulness", value=0.9),
            Score(case_id="b", metric="faithfulness", value=None, detail="boom"),
            Score(case_id="c", metric="faithfulness", value=0.7),
        ]
        aggregates = aggregate_scores(scores)
        assert aggregates["faithfulness"].mean == 0.8  # not dragged down by None
        assert aggregates["faithfulness"].errors == 1

    def test_derived_bias_metrics(self) -> None:
        scores = []
        for i, (overall, length, flip) in enumerate(
            [(0.9, 300.0, 0.0), (0.5, 100.0, 1.0), (0.7, 200.0, 0.0), (0.6, 150.0, 0.0)]
        ):
            case = f"case-{i}"
            scores += [
                Score(case_id=case, metric="judge_overall", value=overall),
                Score(case_id=case, metric="answer_length", value=length),
                Score(case_id=case, metric="position_flip", value=flip),
            ]
        derived = derived_bias_metrics(scores)
        assert derived["position_flip_rate"] == 0.25
        assert derived["verbosity_correlation"] is not None
        assert derived["verbosity_correlation"] > 0.9  # synthetic data is length-correlated
