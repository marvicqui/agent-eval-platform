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

import math

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from openai.types.chat import ChatCompletion
from openai.types.create_embedding_response import CreateEmbeddingResponse
from rich import print as rprint

from aep.config import get_settings
from aep.instrumentation import (
    flush,
    init_tracing,
    traced_agent_run,
    traced_llm_call,
    traced_tool_call,
)

# A deliberately tiny corpus: public Microsoft Learn excerpts (paraphrased,
# with source URLs). Real corpora arrive with projects 02-03; the point here
# is the instrumentation, not retrieval quality.
CORPUS: list[dict[str, str]] = [
    {
        "text": (
            "An Azure landing zone is an environment that follows key design "
            "principles across eight design areas, enabling application migration, "
            "modernization and innovation at scale. Platform landing zones provide "
            "shared services (identity, connectivity, management) and application "
            "landing zones host workloads."
        ),
        "source": "https://learn.microsoft.com/azure/cloud-adoption-framework/ready/landing-zone/",
    },
    {
        "text": (
            "Hub-spoke is the recommended network topology: the hub virtual network "
            "hosts shared services such as Azure Firewall, ExpressRoute/VPN gateways "
            "and DNS, while spoke virtual networks host workloads and peer to the hub. "
            "Spokes should not be peered to each other directly unless traffic "
            "inspection is not required."
        ),
        "source": "https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/hub-spoke-network-topology",
    },
    {
        "text": (
            "The Azure Well-Architected Framework rests on five pillars: reliability, "
            "security, cost optimization, operational excellence and performance "
            "efficiency. Each pillar has design principles and a review checklist."
        ),
        "source": "https://learn.microsoft.com/azure/well-architected/pillars",
    },
    {
        "text": (
            "Management groups organize subscriptions into a hierarchy for unified "
            "policy and access management. Azure Policy assignments at a management "
            "group scope are inherited by all child subscriptions, which is how "
            "landing-zone guardrails are enforced at scale."
        ),
        "source": "https://learn.microsoft.com/azure/governance/management-groups/overview",
    },
]

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

    Re-embedding the corpus on every call is wasteful and fine: four chunks,
    fractions of a cent, zero index-management code to explain.
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


def main() -> None:
    init_tracing(settings)
    for question in QUESTIONS:
        rprint(f"[bold cyan]Q:[/bold cyan] {question}")
        rprint(f"[bold green]A:[/bold green] {answer(question)}\n")
    flush()  # short-lived script: export spans before exit
    rprint("[dim]Traces exported to Langfuse — check the project dashboard.[/dim]")


if __name__ == "__main__":
    main()
