"""The public contract between this platform and any system under test.

This is the API projects 02-05 implement, so it is deliberately minimal and
deliberately *blind*: a SUT receives only the question, never the GoldenCase.
If the SUT could see `expected`, a lazy implementation (or a lazy agent)
could leak ground truth into the answer and every metric would be theater.

A SUT returns everything the three evaluator families need:
- `answer` for the judge,
- `retrieved_contexts` for the RAG metrics,
- `tool_calls` (ordered) for the deterministic trajectory oracle.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class SUTResult(BaseModel):
    """What one SUT invocation produced."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    retrieved_contexts: list[str] = []
    # Tool names in invocation order, e.g. ["retrieve", "retrieve", "summarize"].
    tool_calls: list[str] = []


@runtime_checkable
class SystemUnderTest(Protocol):
    """Implemented by every evaluated system.

    `name` identifies the SUT in reports and traces. `run` must be safe to
    call concurrently (the runner fires several cases at once) and should let
    exceptions propagate — retry policy belongs to the runner, not the SUT.
    """

    name: str

    async def run(self, question: str) -> SUTResult: ...
