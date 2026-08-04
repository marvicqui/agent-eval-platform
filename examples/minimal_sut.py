"""Minimal instrumented RAG system-under-test.

Why this exists: the platform must be runnable standalone, without any of the
four downstream projects. This tiny RAG answers Azure landing-zone questions
over a handful of public Microsoft Learn excerpts, wearing the three tracing
decorators exactly the way a real SUT should. Running it end-to-end is the
acceptance test of phase 1: traces with tokens and cost must appear in
Langfuse Cloud.

Auth is DefaultAzureCredential — run `az login` first. No API keys.

Usage:
    uv run python examples/minimal_sut.py
"""

import asyncio
import math

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from openai.types.chat import ChatCompletion
from openai.types.create_embedding_response import CreateEmbeddingResponse
from rich import print as rprint

from aep.config import get_settings
from aep.dataset.loader import load_dataset
from aep.instrumentation import (
    flush,
    init_tracing,
    traced_agent_run,
    traced_llm_call,
    traced_tool_call,
)
from aep.runner.types import SUTResult

# The corpus is the pool of ground-truth context chunks from the golden
# dataset — the same documents a real landing-zone knowledge base would hold.
# Deriving it from the dataset (contexts only, never expected answers) makes
# retrieval genuinely measurable: the retriever must find the right chunk
# among ~30, not among 4 toys.


def _build_corpus() -> list[dict[str, str]]:
    corpus: list[dict[str, str]] = []
    seen: set[str] = set()
    for case in load_dataset("rag_qa"):
        for chunk in case.context or []:
            if chunk not in seen:
                seen.add(chunk)
                corpus.append({"text": chunk, "source": case.expected.source or "unknown"})
    return corpus


CORPUS: list[dict[str, str]] = _build_corpus()

QUESTIONS = [
    "What network topology does the Cloud Adoption Framework recommend, "
    "and where do shared services live?",
    "How are governance guardrails enforced across many subscriptions in a landing zone?",
]

settings = get_settings()

_client = AzureOpenAI(
    azure_endpoint=settings.azure_openai_endpoint,
    azure_ad_token_provider=get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    ),
    api_version="2024-10-21",
)


@traced_llm_call(operation="embeddings", request_model=settings.embeddings_deployment)
def embed(texts: list[str]) -> CreateEmbeddingResponse:
    return _client.embeddings.create(model=settings.embeddings_deployment, input=texts)


@traced_llm_call(request_model=settings.sut_deployment)
def complete(question: str, context_chunks: list[str]) -> ChatCompletion:
    context = "\n\n".join(context_chunks)
    return _client.chat.completions.create(
        model=settings.sut_deployment,
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer strictly from the provided context. If the context does "
                    "not contain the answer, say so instead of guessing."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.hypot(*a) * math.hypot(*b))


@traced_tool_call(tool_name="retrieve")
def retrieve(question: str, top_k: int = 2) -> list[dict[str, str]]:
    """Embed the question and the corpus, return the top_k closest chunks.

    Re-embedding the ~30 chunks on every call is wasteful and fine: one
    embeddings request, fractions of a cent, zero index-management code to
    explain. A vector store here would be complexity theater.
    """
    response = embed([question] + [doc["text"] for doc in CORPUS])
    vectors = [item.embedding for item in response.data]
    question_vec, doc_vecs = vectors[0], vectors[1:]
    ranked = sorted(
        zip(CORPUS, doc_vecs, strict=True),
        key=lambda pair: _cosine(question_vec, pair[1]),
        reverse=True,
    )
    return [doc for doc, _vec in ranked[:top_k]]


@traced_agent_run(agent_name="minimal-rag")
def answer(question: str) -> str:
    chunks = retrieve(question)
    response = complete(question, [c["text"] for c in chunks])
    sources = ", ".join(c["source"] for c in chunks)
    return f"{response.choices[0].message.content}\n[sources: {sources}]"


class MinimalRagSUT:
    """SystemUnderTest adapter so `aep run` can evaluate this example.

    The underlying OpenAI client is sync; asyncio.to_thread keeps the async
    protocol honest without an async client rewrite. contextvars propagate
    into the thread, so per-case cost attribution still works.
    """

    name = "minimal-rag"

    async def run(self, question: str) -> SUTResult:
        return await asyncio.to_thread(self._run_sync, question)

    @traced_agent_run(agent_name="minimal-rag")
    def _run_sync(self, question: str) -> SUTResult:
        chunks = retrieve(question)
        response = complete(question, [c["text"] for c in chunks])
        return SUTResult(
            answer=response.choices[0].message.content or "",
            retrieved_contexts=[c["text"] for c in chunks],
            tool_calls=["retrieve"],
        )


def build_sut() -> MinimalRagSUT:
    """Factory the `aep run --sut` convention requires."""
    return MinimalRagSUT()


def main() -> None:
    init_tracing(settings)
    for question in QUESTIONS:
        rprint(f"[bold cyan]Q:[/bold cyan] {question}")
        rprint(f"[bold green]A:[/bold green] {answer(question)}\n")
    flush()  # short-lived script: export spans before exit
    rprint("[dim]Traces exported to Langfuse — check the project dashboard.[/dim]")


if __name__ == "__main__":
    main()
