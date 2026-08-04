"""Evaluation pipeline: apply every applicable evaluator to every case run.

Which evaluators apply is decided per case by what the case declares:
- judge: the case has required_points (there is something to grade against)
- rag: the SUT returned retrieved contexts (there was retrieval to measure)
- trajectory: the case declares a trajectory expectation

Concurrency is capped with the same semaphore discipline as the runner —
evaluator LLM calls hit the same Foundry TPM budget the SUT does.
"""

import asyncio

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from aep.config import Settings
from aep.dataset.schema import GoldenCase
from aep.evaluators.base import Score
from aep.evaluators.judge import JudgeEvaluator
from aep.evaluators.rag import RagEvaluator
from aep.evaluators.trajectory import TrajectoryEvaluator
from aep.runner.executor import CaseRun

DEFAULT_RUBRIC = "azure_architecture_qa"


def build_azure_client(settings: Settings) -> AsyncAzureOpenAI:
    """Entra-authenticated async client — the only way this repo talks to Azure."""
    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_ad_token_provider=get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        ),
        api_version="2024-10-21",
    )


async def evaluate_all(
    settings: Settings,
    cases: list[GoldenCase],
    runs: list[CaseRun],
    rubric: str = DEFAULT_RUBRIC,
) -> list[Score]:
    client = build_azure_client(settings)
    judge = JudgeEvaluator(settings, client, rubric)
    rag = RagEvaluator(settings, client)
    trajectory = TrajectoryEvaluator()

    runs_by_id = {run.case_id: run for run in runs}
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def evaluate_case(case: GoldenCase) -> list[Score]:
        run = runs_by_id.get(case.id)
        if run is None or run.result is None:
            return []
        async with semaphore:
            scores: list[Score] = []
            scores.extend(await trajectory.evaluate(case, run))
            if case.expected.required_points:
                scores.extend(await judge.evaluate(case, run))
            if run.result.retrieved_contexts:
                scores.extend(await rag.evaluate(case, run))
            return scores

    nested = await asyncio.gather(*(evaluate_case(case) for case in cases))
    return [score for scores in nested for score in scores]
