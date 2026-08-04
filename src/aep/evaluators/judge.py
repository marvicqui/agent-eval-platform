"""LLM-as-Judge with explicit rubric and measured bias mitigation.

The judge is the platform's most powerful and least trustworthy evaluator,
so it is never trusted blindly. Three documented failure modes and what this
module does about each (full discussion: docs/judge-failure-modes.md):

- **Position bias** (prefers the first option shown): pairwise comparisons
  run in BOTH orders; if the verdict flips with the order, the comparison is
  a tie and the flip is counted. `position_flip_rate` is a reported metric.
- **Verbosity bias** (prefers longer answers): the rubric scores coverage of
  the case's required points, never length; answer length is recorded per
  case so the score-vs-length Pearson correlation is a reported metric.
- **Self-preference** (prefers its own model family): judging with the same
  deployment as the SUT raises an error unless explicitly allowed via
  AEP_ALLOW_SAME_JUDGE=1 — a conscious, documented decision, not a default.

The judge must return JSON that validates against JudgeVerdict. One retry
with the validation error in context; after that the case is marked
`judge_error` (value None) so broken judging never contaminates the metric.
"""

from pathlib import Path
from typing import Literal

import yaml
from openai import AsyncAzureOpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

from aep.config import Settings
from aep.dataset.schema import GoldenCase
from aep.evaluators.base import Score
from aep.runner.executor import CaseRun

RUBRICS_DIR = Path(__file__).parent / "rubrics"


class JudgeConfigError(Exception):
    """Raised when the judge configuration is indefensible (see self-preference)."""


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    weight: float
    description: str
    anchors: dict[int, str] = {}


class Rubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: int
    scale: tuple[int, int]
    criteria: list[Criterion]

    @classmethod
    def load(cls, name: str) -> "Rubric":
        rubric = cls.model_validate(yaml.safe_load((RUBRICS_DIR / f"{name}.yaml").read_text()))
        total_weight = sum(c.weight for c in rubric.criteria)
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(f"Rubric '{name}' weights sum to {total_weight}, not 1.0")
        return rubric


class JudgeVerdict(BaseModel):
    """What the judge model must return. Validated, never trusted raw.

    `overall` is deliberately NOT produced by the model: it is computed here
    as the weighted sum, because arithmetic is not something to delegate to
    an LLM.
    """

    model_config = ConfigDict(extra="forbid")

    scores: dict[str, float]
    rationale: str


class PairwiseVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    winner: Literal["A", "B", "tie"]
    rationale: str


def check_self_preference_guard(settings: Settings) -> None:
    """Refuse judge == SUT model unless explicitly overridden.

    With only one deployment available (gpt-5-mini until gpt-large quota
    lands), the override is legitimate — but it must be a visible choice
    recorded in config, because self-preference bias is then a known
    limitation of every judge score produced.
    """
    if settings.judge_deployment == settings.sut_deployment and not settings.allow_same_judge:
        raise JudgeConfigError(
            f"Judge deployment '{settings.judge_deployment}' == SUT deployment. "
            "Self-preference bias makes these scores structurally suspect. "
            "Deploy a different judge model, or set AEP_ALLOW_SAME_JUDGE=1 to "
            "accept and document the limitation."
        )


def render_rubric_prompt(rubric: Rubric, case: GoldenCase, answer: str) -> str:
    """One prompt template, visible and versioned with the rubric."""
    lines = [
        "You are a strict evaluation judge for Azure architecture answers.",
        f"Score the answer on each criterion from {rubric.scale[0]} to {rubric.scale[1]}.",
        "Score coverage of the required points — NEVER reward length itself.",
        "",
        "## Criteria",
    ]
    for criterion in rubric.criteria:
        lines.append(f"- {criterion.id}: {criterion.description}")
        for level, anchor in sorted(criterion.anchors.items()):
            lines.append(f"    score {level}: {anchor}")
    lines += [
        "",
        "## Question",
        case.input,
        "",
        "## Required points a complete answer must cover",
        *[f"- {point}" for point in case.expected.required_points],
        "",
        "## Answer to evaluate",
        answer,
        "",
        "Return ONLY a JSON object: "
        '{"scores": {<criterion_id>: <number>, ...}, "rationale": "<short reason>"}',
    ]
    return "\n".join(lines)


class JudgeEvaluator:
    """Rubric scoring plus a both-orders pairwise check against the reference."""

    name = "judge"

    def __init__(self, settings: Settings, client: AsyncAzureOpenAI, rubric_name: str) -> None:
        check_self_preference_guard(settings)
        self._settings = settings
        self._client = client
        self._rubric = Rubric.load(rubric_name)

    async def _ask_json(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._settings.judge_deployment,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    async def _score_once(self, case: GoldenCase, answer: str) -> JudgeVerdict | None:
        """Ask, validate, retry once with the error, then give up (None)."""
        prompt = render_rubric_prompt(self._rubric, case, answer)
        raw = await self._ask_json(prompt)
        for _attempt in range(2):
            try:
                verdict = JudgeVerdict.model_validate_json(raw)
                self._check_verdict(verdict)
                return verdict
            except (ValidationError, ValueError) as exc:
                raw = await self._ask_json(
                    f"{prompt}\n\nYour previous output was invalid: {exc}\n"
                    "Return only the corrected JSON object."
                )
        return None

    def _check_verdict(self, verdict: JudgeVerdict) -> None:
        expected_ids = {c.id for c in self._rubric.criteria}
        if set(verdict.scores) != expected_ids:
            raise ValueError(f"scores keys {set(verdict.scores)} != rubric criteria {expected_ids}")
        low, high = self._rubric.scale
        for cid, score in verdict.scores.items():
            if not (low <= score <= high):
                raise ValueError(f"score {cid}={score} outside scale [{low}, {high}]")

    def _overall(self, verdict: JudgeVerdict) -> float:
        """Weighted sum, normalized to 0-1 so thresholds are scale-agnostic."""
        low, high = self._rubric.scale
        weighted = sum(c.weight * verdict.scores[c.id] for c in self._rubric.criteria)
        return (weighted - low) / (high - low)

    async def compare_pairwise(
        self, case: GoldenCase, answer_a: str, answer_b: str
    ) -> dict[str, str | bool | None]:
        """Both-orders pairwise comparison — the position-bias mitigation.

        Returns the de-biased verdict plus whether the raw verdicts flipped
        with presentation order. A flip means the judge was answering "which
        came first?" instead of "which is better?" — the case counts as a tie
        and the flip feeds `position_flip_rate`.
        """

        async def ask(first: str, second: str) -> PairwiseVerdict | None:
            prompt = (
                "You are a strict evaluation judge. Two answers to the same Azure "
                "architecture question. Judge which better covers the required "
                "points. Length itself is NOT quality.\n\n"
                f"## Question\n{case.input}\n\n"
                "## Required points\n"
                + "\n".join(f"- {p}" for p in case.expected.required_points)
                + f"\n\n## Answer A\n{first}\n\n## Answer B\n{second}\n\n"
                'Return ONLY JSON: {"winner": "A"|"B"|"tie", "rationale": "<short>"}'
            )
            raw = await self._ask_json(prompt)
            try:
                return PairwiseVerdict.model_validate_json(raw)
            except ValidationError:
                return None

        forward = await ask(answer_a, answer_b)
        backward = await ask(answer_b, answer_a)
        if forward is None or backward is None:
            return {"winner": None, "flipped": False, "judge_error": True}

        # Map the reversed run back to the original labels.
        backward_winner = {"A": "B", "B": "A", "tie": "tie"}[backward.winner]
        flipped = forward.winner != backward_winner
        return {
            "winner": "tie" if flipped else forward.winner,
            "flipped": flipped,
            "judge_error": False,
        }

    async def evaluate(self, case: GoldenCase, run: CaseRun) -> list[Score]:
        if run.result is None:
            return []
        answer = run.result.answer
        scores: list[Score] = []

        verdict = await self._score_once(case, answer)
        if verdict is None:
            scores.append(
                Score(case_id=case.id, metric="judge_error", value=1.0, detail="invalid JSON twice")
            )
        else:
            scores.append(
                Score(
                    case_id=case.id,
                    metric="judge_overall",
                    value=self._overall(verdict),
                    detail=verdict.rationale,
                )
            )
            for cid, value in verdict.scores.items():
                scores.append(Score(case_id=case.id, metric=f"judge_{cid}", value=value))

        # Verbosity-bias raw data: length is recorded so the run-level
        # correlation (score vs length) can be computed and reported.
        scores.append(Score(case_id=case.id, metric="answer_length", value=float(len(answer))))

        # Position-bias measurement on real data: compare the SUT answer
        # against the golden reference in both orders.
        if case.expected.answer:
            pairwise = await self.compare_pairwise(case, answer, case.expected.answer)
            if not pairwise["judge_error"]:
                scores.append(
                    Score(
                        case_id=case.id,
                        metric="position_flip",
                        value=1.0 if pairwise["flipped"] else 0.0,
                        detail=f"debiased winner vs reference: {pairwise['winner']}",
                    )
                )
        return scores


def verbosity_correlation(pairs: list[tuple[float, float]]) -> float | None:
    """Pearson r between judge score and answer length across a run.

    Pure function (testable without an LLM). |r| >= 0.3 in the scorecard
    means the judge is likely rewarding length — exactly what the rubric is
    supposed to prevent — and the run report flags it.
    """
    n = len(pairs)
    if n < 3:
        return None
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return float(cov / (var_x**0.5 * var_y**0.5))
