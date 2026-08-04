"""Bias-mitigation tests with synthetic judges — zero LLM calls.

The point of these tests: prove the mitigation MACHINERY works, using judges
with known, programmed biases. A position-biased judge must be caught by the
both-orders check; an honest judge must pass it; the self-preference guard
must refuse an indefensible configuration. Real-model bias numbers come from
`aep calibrate` and the scorecard — these tests guarantee the instruments
measuring them are not broken.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from aep.config import Settings
from aep.dataset.schema import Expected, GoldenCase
from aep.evaluators.judge import (
    JudgeConfigError,
    JudgeEvaluator,
    check_self_preference_guard,
    verbosity_correlation,
)


def make_settings(**overrides: object) -> Settings:
    values: dict = {
        "AZURE_OPENAI_ENDPOINT": "https://example.invalid/",
        "LANGFUSE_PUBLIC_KEY": "pk-test",
        "LANGFUSE_SECRET_KEY": "sk-test",
        "AEP_SUT_DEPLOYMENT": "gpt-small",
        "AEP_JUDGE_DEPLOYMENT": "gpt-judge",
        "_env_file": None,  # tests must not read the developer's .env
    }
    values.update(overrides)
    return Settings(**values)


class ScriptedJudgeClient:
    """Stands in for AsyncAzureOpenAI; `script` maps a call index to content."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self.calls: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: object) -> object:
        prompt = str(kwargs.get("messages"))
        self.calls.append(prompt)
        content = json.dumps(self._responses[min(len(self.calls) - 1, len(self._responses) - 1)])
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


CASE = GoldenCase(
    id="bias-case-001",
    category="networking",
    difficulty="basic",
    input="Which topology does CAF recommend?",
    expected=Expected(
        answer="Hub-spoke with shared services in the hub.",
        required_points=["hub-spoke", "shared services in hub"],
    ),
)


class TestPositionBias:
    def test_position_biased_judge_is_caught_as_flip(self) -> None:
        """A judge that always prefers the FIRST answer flips when the order
        reverses — the mitigation must convert that into a tie + flip."""
        biased = ScriptedJudgeClient(
            [
                {"winner": "A", "rationale": "prefers whatever came first"},
                {"winner": "A", "rationale": "prefers whatever came first"},
            ]
        )
        judge = JudgeEvaluator(make_settings(), biased, "azure_architecture_qa")  # type: ignore[arg-type]
        verdict = asyncio.run(judge.compare_pairwise(CASE, "answer one", "answer two"))
        assert verdict["flipped"] is True
        assert verdict["winner"] == "tie"

    def test_consistent_judge_is_not_flagged(self) -> None:
        """An honest judge picks the same underlying answer in both orders:
        first run says A (=first answer), reversed run says B (=first answer
        again, which is the same underlying text)."""
        honest = ScriptedJudgeClient(
            [
                {"winner": "A", "rationale": "answer one is better"},
                {"winner": "B", "rationale": "answer one is better (now shown as B)"},
            ]
        )
        judge = JudgeEvaluator(make_settings(), honest, "azure_architecture_qa")  # type: ignore[arg-type]
        verdict = asyncio.run(judge.compare_pairwise(CASE, "answer one", "answer two"))
        assert verdict["flipped"] is False
        assert verdict["winner"] == "A"

    def test_both_orders_are_actually_asked(self) -> None:
        client = ScriptedJudgeClient([{"winner": "tie", "rationale": "equal"}])
        judge = JudgeEvaluator(make_settings(), client, "azure_architecture_qa")  # type: ignore[arg-type]
        asyncio.run(judge.compare_pairwise(CASE, "AAA-marker", "BBB-marker"))
        assert len(client.calls) == 2
        first, second = client.calls
        assert first.index("AAA-marker") < first.index("BBB-marker")
        assert second.index("BBB-marker") < second.index("AAA-marker")


class TestSelfPreferenceGuard:
    def test_same_judge_and_sut_model_is_refused(self) -> None:
        settings = make_settings(AEP_JUDGE_DEPLOYMENT="gpt-small")
        with pytest.raises(JudgeConfigError, match="Self-preference"):
            check_self_preference_guard(settings)

    def test_explicit_override_is_allowed(self) -> None:
        settings = make_settings(AEP_JUDGE_DEPLOYMENT="gpt-small", AEP_ALLOW_SAME_JUDGE="1")
        check_self_preference_guard(settings)  # must not raise

    def test_distinct_models_pass(self) -> None:
        check_self_preference_guard(make_settings())  # judge=gpt-judge, sut=gpt-small


class TestVerbosityCorrelation:
    def test_length_rewarding_judge_shows_high_correlation(self) -> None:
        pairs = [(float(length), length * 10.0) for length in range(1, 11)]
        r = verbosity_correlation(pairs)
        assert r is not None and r > 0.99

    def test_length_blind_judge_shows_low_correlation(self) -> None:
        scores = [3.0, 5.0, 1.0, 4.0, 2.0, 4.0, 3.0, 5.0, 1.0, 2.0]
        pairs = [(score, float(100 + i)) for i, score in enumerate(scores)]
        r = verbosity_correlation(pairs)
        assert r is not None and abs(r) < 0.3

    def test_too_few_points_returns_none(self) -> None:
        assert verbosity_correlation([(1.0, 2.0)]) is None

    def test_constant_scores_return_none(self) -> None:
        assert verbosity_correlation([(3.0, 10.0), (3.0, 20.0), (3.0, 30.0)]) is None
