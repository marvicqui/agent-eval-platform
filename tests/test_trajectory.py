"""Trajectory oracle tests — fully deterministic, zero LLM calls.

These tests are the executable specification of the platform's hard oracle.
If a behavior isn't pinned here, it doesn't exist.
"""

from aep.dataset.schema import TrajectoryExpectation
from aep.evaluators.trajectory import check_ordering, detect_loop, evaluate_trajectory


def expectation(**overrides: object) -> TrajectoryExpectation:
    defaults: dict = {
        "required_tools": {"retrieve"},
        "forbidden_tools": {"write_config", "delete_resource"},
        "max_steps": 5,
        "ordering": None,
    }
    defaults.update(overrides)
    return TrajectoryExpectation(**defaults)


class TestPrecisionRecall:
    def test_perfect_trajectory(self) -> None:
        result = evaluate_trajectory(expectation(), ["retrieve"])
        assert result.tool_precision == 1.0
        assert result.tool_recall == 1.0
        assert result.forbidden_tool_calls == 0

    def test_missing_required_tool_lowers_recall(self) -> None:
        result = evaluate_trajectory(
            expectation(required_tools={"retrieve", "summarize"}), ["retrieve"]
        )
        assert result.tool_recall == 0.5

    def test_unexpected_tool_lowers_precision(self) -> None:
        result = evaluate_trajectory(expectation(), ["retrieve", "unrelated_tool"])
        assert result.tool_precision == 0.5
        assert result.tool_recall == 1.0

    def test_no_tools_called(self) -> None:
        result = evaluate_trajectory(expectation(), [])
        assert result.tool_precision == 1.0  # nothing wrong was called
        assert result.tool_recall == 0.0  # but the required tool never ran


class TestForbiddenTools:
    def test_forbidden_call_is_counted(self) -> None:
        result = evaluate_trajectory(expectation(), ["retrieve", "write_config"])
        assert result.forbidden_tool_calls == 1

    def test_every_forbidden_call_counts(self) -> None:
        result = evaluate_trajectory(
            expectation(), ["write_config", "write_config", "delete_resource"]
        )
        assert result.forbidden_tool_calls == 3


class TestLoopsAndSteps:
    def test_max_steps_exceeded(self) -> None:
        result = evaluate_trajectory(expectation(max_steps=2), ["retrieve"] * 3)
        assert result.max_steps_exceeded

    def test_single_tool_loop_detected(self) -> None:
        assert detect_loop(["retrieve", "retrieve", "retrieve"])

    def test_alternating_loop_detected(self) -> None:
        assert detect_loop(["a", "b", "a", "b", "a", "b"])

    def test_two_calls_is_not_a_loop(self) -> None:
        assert not detect_loop(["retrieve", "retrieve"])

    def test_varied_trajectory_is_not_a_loop(self) -> None:
        assert not detect_loop(["a", "b", "c", "a", "d"])


class TestOrdering:
    def test_no_constraint_always_ok(self) -> None:
        assert check_ordering(None, ["b", "a"])

    def test_matching_order_ok(self) -> None:
        assert check_ordering([["retrieve", "summarize"]], ["retrieve", "summarize"])

    def test_wrong_order_fails(self) -> None:
        assert not check_ordering([["retrieve", "summarize"]], ["summarize", "retrieve"])

    def test_any_accepted_ordering_passes(self) -> None:
        orderings = [["a", "b"], ["b", "a"]]
        assert check_ordering(orderings, ["b", "a"])

    def test_repeated_calls_use_first_occurrence(self) -> None:
        assert check_ordering([["retrieve", "summarize"]], ["retrieve", "retrieve", "summarize"])

    def test_tools_outside_constraint_are_ignored(self) -> None:
        assert check_ordering([["retrieve", "summarize"]], ["log", "retrieve", "summarize"])
