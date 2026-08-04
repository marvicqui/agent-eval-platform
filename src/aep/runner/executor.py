"""Async runner: executes a golden dataset against a system under test.

Design points, each of which is a deliberate choice:
- Concurrency is capped with a semaphore (default 4) because the shared
  Foundry deployment has a TPM budget; an uncapped gather() turns an eval
  run into a self-inflicted 429 storm.
- Retries apply ONLY to transient failures (429 / 5xx). A validation error
  or a bug in the SUT must fail the case immediately — retrying it wastes
  money to hide a real defect.
- Cost and latency are captured per case via the contextvar accumulator the
  tracing decorators feed. Each case runs in its own asyncio task, so
  attribution is exact even under concurrency.
"""

import asyncio
import time

from openai import APIStatusError
from pydantic import BaseModel, ConfigDict

from aep.dataset.schema import GoldenCase
from aep.instrumentation import cost as cost_tracking
from aep.runner.types import SUTResult, SystemUnderTest

# Waits between attempts: ~2s then ~6s. Two retries is enough for transient
# throttling; anything needing more is an availability problem to surface.
RETRY_WAITS_SECONDS = [2.0, 6.0]


class CaseRun(BaseModel):
    """Outcome of one case: the SUT result or an error, plus cost/latency."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    result: SUTResult | None = None
    error: str | None = None
    attempts: int = 1
    latency_seconds: float = 0.0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    unknown_price_calls: int = 0

    @property
    def succeeded(self) -> bool:
        return self.result is not None


def _is_transient(exc: Exception) -> bool:
    """Only 429 and 5xx are worth retrying; everything else is a real bug."""
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


async def _run_one(sut: SystemUnderTest, case: GoldenCase) -> CaseRun:
    accumulator = cost_tracking.start_tracking()
    started = time.perf_counter()
    last_error = ""

    for attempt, wait in enumerate([0.0, *RETRY_WAITS_SECONDS], start=1):
        if wait:
            await asyncio.sleep(wait)
        try:
            result = await sut.run(case.input)
            return CaseRun(
                case_id=case.id,
                result=result,
                attempts=attempt,
                latency_seconds=time.perf_counter() - started,
                cost_usd=accumulator.usd,
                input_tokens=accumulator.input_tokens,
                output_tokens=accumulator.output_tokens,
                unknown_price_calls=accumulator.unknown_price_calls,
            )
        except Exception as exc:  # noqa: BLE001 — the runner is the error boundary
            last_error = f"{type(exc).__name__}: {exc}"
            if not _is_transient(exc):
                break

    return CaseRun(
        case_id=case.id,
        error=last_error,
        attempts=attempt,
        latency_seconds=time.perf_counter() - started,
        cost_usd=accumulator.usd,
        input_tokens=accumulator.input_tokens,
        output_tokens=accumulator.output_tokens,
        unknown_price_calls=accumulator.unknown_price_calls,
    )


async def run_dataset(
    sut: SystemUnderTest, cases: list[GoldenCase], max_concurrency: int = 4
) -> list[CaseRun]:
    """Run every case against the SUT, at most `max_concurrency` at a time.

    Results come back in dataset order regardless of completion order, so
    diffs between two runs line up case by case.
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def bounded(case: GoldenCase) -> CaseRun:
        async with semaphore:
            return await _run_one(sut, case)

    return list(await asyncio.gather(*(bounded(case) for case in cases)))
