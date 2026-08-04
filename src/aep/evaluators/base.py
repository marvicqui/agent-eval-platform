"""The evaluator contract: every evaluator turns (case, run) into Scores.

Why one flat Score type instead of per-evaluator result classes: the
scorecard aggregates across evaluator families (RAG, judge, trajectory) and
must be able to threshold any metric uniformly. A metric is a name and a
number; anything richer belongs in `detail` for humans, not in the type
system.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from aep.dataset.schema import GoldenCase
from aep.runner.executor import CaseRun


class Score(BaseModel):
    """One measured value for one case.

    `value=None` means the evaluator itself failed (e.g. judge output never
    validated). Kept separate from a low score on purpose: an evaluator error
    must not drag the metric average down or up — it is missing data, and the
    scorecard reports it as such.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    metric: str
    value: float | None
    detail: str | None = None


@runtime_checkable
class Evaluator(Protocol):
    """Implemented by each evaluator family (rag, judge, trajectory)."""

    name: str

    async def evaluate(self, case: GoldenCase, run: CaseRun) -> list[Score]: ...
