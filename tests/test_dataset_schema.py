"""Dataset schema and loader tests — deterministic, no LLM calls.

Why these tests matter more than they look: the loader is the only barrier
between a hand-edited JSONL file and every metric the platform reports.
Each test encodes one failure mode we refuse to let through silently.
"""

from pathlib import Path

import pytest

from aep.dataset.loader import DatasetError, load_dataset
from aep.dataset.schema import GoldenCase
from aep.dataset.stats import coverage

GOLDEN_DIR = Path(__file__).parent.parent / "datasets" / "golden"


def write_dataset(tmp_path: Path, name: str, lines: list[str]) -> Path:
    (tmp_path / f"{name}.jsonl").write_text("\n".join(lines))
    return tmp_path


VALID_CASE = (
    '{"id": "net-case-001", "category": "networking", "difficulty": "basic", '
    '"input": "q?", "expected": {"answer": "a", "required_points": ["p1"]}}'
)


class TestLoaderRejections:
    def test_unknown_field_fails_loudly(self, tmp_path: Path) -> None:
        bad = VALID_CASE.replace('"category"', '"caregory"')
        with pytest.raises(DatasetError, match="schema violation"):
            load_dataset("bad", write_dataset(tmp_path, "bad", [bad]))

    def test_invalid_json_reports_line_number(self, tmp_path: Path) -> None:
        with pytest.raises(DatasetError, match=":2:"):
            load_dataset("bad", write_dataset(tmp_path, "bad", [VALID_CASE, "{not json"]))

    def test_duplicate_ids_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DatasetError, match="duplicate id"):
            load_dataset("bad", write_dataset(tmp_path, "bad", [VALID_CASE, VALID_CASE]))

    def test_unknown_difficulty_rejected(self, tmp_path: Path) -> None:
        bad = VALID_CASE.replace('"basic"', '"impossible"')
        with pytest.raises(DatasetError, match="schema violation"):
            load_dataset("bad", write_dataset(tmp_path, "bad", [bad]))

    def test_missing_dataset_lists_available(self, tmp_path: Path) -> None:
        write_dataset(tmp_path, "exists", [VALID_CASE])
        with pytest.raises(DatasetError, match="Available.*exists"):
            load_dataset("nope", tmp_path)

    def test_empty_dataset_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DatasetError, match="empty"):
            load_dataset("bad", write_dataset(tmp_path, "bad", [""]))


class TestCommittedDatasets:
    """The shipped golden datasets must themselves satisfy the contract."""

    def test_rag_qa_loads_with_minimum_size(self) -> None:
        cases = load_dataset("rag_qa", GOLDEN_DIR)
        assert len(cases) >= 30

    def test_rag_qa_covers_three_difficulties(self) -> None:
        cases = load_dataset("rag_qa", GOLDEN_DIR)
        assert {c.difficulty for c in cases} == {"basic", "intermediate", "advanced"}

    def test_rag_qa_cases_are_auditable(self) -> None:
        """Every case needs required_points (judge input) and a source."""
        for case in load_dataset("rag_qa", GOLDEN_DIR):
            assert case.expected.required_points, f"{case.id} has no required_points"
            assert case.expected.source, f"{case.id} has no source"
            assert case.context, f"{case.id} has no ground-truth context"

    def test_agent_tasks_have_trajectories_with_forbidden_tools(self) -> None:
        for case in load_dataset("agent_tasks", GOLDEN_DIR):
            assert case.trajectory is not None, f"{case.id} has no trajectory"
            assert case.trajectory.forbidden_tools, f"{case.id} forbids nothing"

    def test_coverage_reports_all_categories(self) -> None:
        cases = load_dataset("rag_qa", GOLDEN_DIR)
        table = coverage(cases)
        assert sum(sum(c.values()) for c in table.values()) == len(cases)


def test_golden_case_roundtrip() -> None:
    case = GoldenCase.model_validate_json(VALID_CASE)
    assert case.id == "net-case-001"
    assert case.trajectory is None
