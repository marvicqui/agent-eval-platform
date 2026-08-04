"""RAG metrics as thin wrappers over RAGAS, configured for Azure OpenAI.

Why wrap instead of calling RAGAS directly from the scorecard: RAGAS's API
has changed shape three times in two years (metrics -> collections, wrapper
LLM types). This module is the only file allowed to know RAGAS's current
API; everything else sees the stable Evaluator protocol. When RAGAS breaks
again, one file changes.

What each metric answers (thresholds live in evals/thresholds.yaml):
- faithfulness:      is the answer supported by the retrieved context?
- answer_relevancy:  does the answer address the question?
- context_precision: was the retrieved context relevant to the question?
- context_recall:    did retrieval find what the reference answer needs?
"""

from openai import AsyncAzureOpenAI

from aep.config import Settings
from aep.dataset.schema import GoldenCase
from aep.evaluators.base import Score
from aep.runner.executor import CaseRun


class RagEvaluator:
    name = "rag"

    def __init__(self, settings: Settings, client: AsyncAzureOpenAI) -> None:
        # Imported here so that trajectory-only users never pay the heavy
        # ragas/langchain import chain.
        from ragas.embeddings import OpenAIEmbeddings
        from ragas.llms import llm_factory
        from ragas.metrics.collections import (
            AnswerRelevancy,
            ContextPrecisionWithReference,
            ContextRecall,
            Faithfulness,
        )

        # provider stays "openai" (instructor's OpenAI adapter handles Azure
        # clients; ragas's "azure" adapter does not). The deployment must be
        # named after the model: see the ragas_deployment comment in config.py.
        # max_tokens=8192: reasoning models spend completion budget on hidden
        # reasoning; ragas's 1024 default truncates context_recall output.
        llm = llm_factory(settings.ragas_deployment, client=client, max_tokens=8192)
        embeddings = OpenAIEmbeddings(client=client, model=settings.embeddings_deployment)
        self._faithfulness = Faithfulness(llm=llm)
        self._answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)
        self._context_precision = ContextPrecisionWithReference(llm=llm)
        self._context_recall = ContextRecall(llm=llm)

    async def evaluate(self, case: GoldenCase, run: CaseRun) -> list[Score]:
        if run.result is None:
            return []
        question = case.input
        answer = run.result.answer
        contexts = run.result.retrieved_contexts
        reference = case.expected.answer

        scores: list[Score] = []

        async def score(metric_name: str, coro) -> None:  # type: ignore[no-untyped-def]
            # A metric error is recorded as missing data (value None), never
            # as a zero that would silently poison the average.
            try:
                result = await coro
                scores.append(Score(case_id=case.id, metric=metric_name, value=result.value))
            except Exception as exc:  # noqa: BLE001 — evaluator errors must not kill the run
                scores.append(
                    Score(
                        case_id=case.id,
                        metric=metric_name,
                        value=None,
                        detail=f"evaluator error: {type(exc).__name__}: {exc}",
                    )
                )

        if contexts:
            await score(
                "faithfulness",
                self._faithfulness.ascore(
                    user_input=question, response=answer, retrieved_contexts=contexts
                ),
            )
        await score(
            "answer_relevancy",
            self._answer_relevancy.ascore(user_input=question, response=answer),
        )
        if contexts and reference:
            await score(
                "context_precision",
                self._context_precision.ascore(
                    user_input=question, reference=reference, retrieved_contexts=contexts
                ),
            )
            await score(
                "context_recall",
                self._context_recall.ascore(
                    user_input=question, retrieved_contexts=contexts, reference=reference
                ),
            )
        return scores
