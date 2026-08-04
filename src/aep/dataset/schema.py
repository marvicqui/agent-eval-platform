"""Schema of a golden-dataset case.

Why pydantic with extra="forbid": the dataset is the contract every evaluator
runs against. A typo in a field name ("dificulty") must explode at load time
with a line number, not silently produce a case that no evaluator scores.
Schema drift is the classic slow death of eval suites.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Difficulty = Literal["basic", "intermediate", "advanced"]


class TrajectoryExpectation(BaseModel):
    """What an *acceptable* agent execution looks like, tool-wise.

    This is the deterministic oracle of the platform: no LLM is involved in
    checking it. `forbidden_tools` exists because "the agent never called a
    write operation" is a security property (blast radius), and any violation
    is a hard scorecard failure regardless of answer quality.
    """

    model_config = ConfigDict(extra="forbid")

    required_tools: set[str] = set()
    forbidden_tools: set[str] = set()
    max_steps: int = Field(default=10, gt=0)
    # Each inner list is one acceptable ordering of the required tools.
    # None means any order is fine.
    ordering: list[list[str]] | None = None


class Expected(BaseModel):
    """Ground truth for a case.

    `required_points` is the anti-verbosity device: the judge scores coverage
    of these points, not answer length. `source` keeps every fact auditable —
    a golden case whose answer can't be traced to a document is an opinion.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str | None = None
    required_points: list[str] = []
    source: str | None = None


class GoldenCase(BaseModel):
    """One evaluation case. Lives as one JSON line in datasets/golden/*.jsonl."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    category: str
    difficulty: Difficulty
    input: str
    expected: Expected
    # Ground-truth contexts for RAG metrics (context recall needs them).
    context: list[str] | None = None
    trajectory: TrajectoryExpectation | None = None
    tags: list[str] = []
