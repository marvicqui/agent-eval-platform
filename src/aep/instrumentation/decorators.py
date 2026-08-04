"""Tracing decorators: the only instrumentation API agent code should touch.

Why decorators: the systems under test (projects 02-05) must be instrumentable
without scattering OTel calls through their logic. Decorating the three kinds
of operation an agent performs — LLM calls, tool calls, the run itself — keeps
the observability concern in one visible line per function.

Contract for @traced_llm_call: the wrapped function must return the raw
OpenAI SDK response (chat completion or embeddings response). The decorator
reads `.model` and `.usage` from it to record tokens and compute cost. That
contract is narrower than "any function", and that is intentional: it makes
token/cost capture automatic and impossible to forget.
"""

import functools
import inspect
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from opentelemetry import trace

from aep.config import get_settings
from aep.instrumentation import conventions as c
from aep.instrumentation import cost as cost_tracking

P = ParamSpec("P")
R = TypeVar("R")

_tracer = trace.get_tracer("agent-eval-platform")


def _record_llm_response(span: trace.Span, response: Any) -> None:
    """Extract model/tokens from an OpenAI response and attach cost.

    Defensive on purpose: chat responses carry prompt/completion tokens,
    embeddings only prompt tokens. A missing field records nothing rather
    than crashing the traced call — observability must never break the SUT.
    """
    model = getattr(response, "model", None)
    usage = getattr(response, "usage", None)
    if model:
        span.set_attribute(c.GEN_AI_RESPONSE_MODEL, model)
    if usage is None:
        return

    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    span.set_attribute(c.GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
    span.set_attribute(c.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)

    price = get_settings().price_for(model) if model else None
    cost_usd = None if price is None else price.cost_usd(input_tokens, output_tokens)
    if cost_usd is None:
        # Unknown price must surface as unknown, never as $0.00.
        span.set_attribute(c.AEP_COST_UNKNOWN, True)
    else:
        span.set_attribute(c.AEP_COST_USD, cost_usd)
    # Feed the per-case accumulator so the runner can attribute spend.
    cost_tracking.record(model or "unknown", input_tokens, output_tokens, cost_usd)


def _traced(
    span_name: str, attributes: dict[str, Any], on_result: Callable[[trace.Span, Any], None] | None
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Shared wrapper factory handling both sync and async functions."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                with _tracer.start_as_current_span(span_name, attributes=attributes) as span:
                    result = await func(*args, **kwargs)
                    if on_result is not None:
                        on_result(span, result)
                    return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with _tracer.start_as_current_span(span_name, attributes=attributes) as span:
                result = func(*args, **kwargs)
                if on_result is not None:
                    on_result(span, result)
                return result

        return sync_wrapper

    return decorator


def traced_llm_call(
    *, operation: str = c.OP_CHAT, request_model: str
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Trace a function that returns a raw OpenAI response.

    `request_model` is the *deployment* name we asked for; the response model
    reported by the API is recorded separately, because the two diverging
    (e.g. a deployment alias silently upgraded) is exactly the kind of thing
    a regression investigation needs to see.
    """
    return _traced(
        span_name=f"{operation} {request_model}",
        attributes={
            c.GEN_AI_SYSTEM: c.SYSTEM_AZURE_OPENAI,
            c.GEN_AI_OPERATION_NAME: operation,
            c.GEN_AI_REQUEST_MODEL: request_model,
        },
        on_result=_record_llm_response,
    )


def traced_tool_call(*, tool_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Trace a tool execution. The trajectory evaluator (phase 3) reads these
    spans to reconstruct which tools ran and in what order, so every tool a
    SUT exposes must wear this decorator — an untraced tool is invisible to
    the oracle."""
    return _traced(
        span_name=f"{c.OP_EXECUTE_TOOL} {tool_name}",
        attributes={
            c.GEN_AI_OPERATION_NAME: c.OP_EXECUTE_TOOL,
            c.GEN_AI_TOOL_NAME: tool_name,
        },
        on_result=None,
    )


def traced_agent_run(*, agent_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Trace one end-to-end agent invocation as the root span all LLM and
    tool spans nest under. One run = one trace in Langfuse."""
    return _traced(
        span_name=f"{c.OP_INVOKE_AGENT} {agent_name}",
        attributes={c.GEN_AI_OPERATION_NAME: c.OP_INVOKE_AGENT},
        on_result=None,
    )


__all__ = ["traced_llm_call", "traced_tool_call", "traced_agent_run"]
