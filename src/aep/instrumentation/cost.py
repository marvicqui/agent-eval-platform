"""Per-context cost accumulation.

Why contextvars: the runner executes many cases concurrently in one process.
Cost is computed inside the tracing decorators, several stack frames below
the runner, and must be attributed to *the case that caused it*. A contextvar
is copied per asyncio task, so each case's task accumulates only its own
spend — no globals, no locks, no plumbing cost through every return value.
"""

import contextvars
from dataclasses import dataclass, field


@dataclass
class CostAccumulator:
    """Running totals for one tracked scope (typically one eval case)."""

    usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    unknown_price_calls: int = 0
    calls: list[str] = field(default_factory=list)  # response model names, in order


_current: contextvars.ContextVar[CostAccumulator | None] = contextvars.ContextVar(
    "aep_cost_accumulator", default=None
)


def start_tracking() -> CostAccumulator:
    """Begin accumulating in the current context and return the accumulator."""
    accumulator = CostAccumulator()
    _current.set(accumulator)
    return accumulator


def record(
    model: str, input_tokens: int, output_tokens: int, cost_usd: float | None
) -> None:
    """Called by the tracing decorators after every LLM response.

    A None cost means the model was missing from the price table; it is
    counted separately so a stale table shows up as `unknown_price_calls > 0`
    instead of an understated total.
    """
    accumulator = _current.get()
    if accumulator is None:
        return  # nothing is tracking (e.g. ad-hoc script) — that's fine
    accumulator.calls.append(model)
    accumulator.input_tokens += input_tokens
    accumulator.output_tokens += output_tokens
    if cost_usd is None:
        accumulator.unknown_price_calls += 1
    else:
        accumulator.usd += cost_usd
