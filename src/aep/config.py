"""Central configuration, loaded from the environment.

Why: every runtime value (endpoints, deployment names, keys, prices) must be
changeable without touching code — the platform is consumed by four other
projects with different .env files. Prices live here and not in code paths
because cost-per-request is a first-class metric of this platform, and a
wrong or stale price silently corrupts it; keeping the table in one visible
place makes review of a price change a one-line diff.
"""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelPrice(BaseModel):
    """USD per 1M tokens. Source: Azure OpenAI pricing page at the date noted."""

    input_per_1m: float
    output_per_1m: float

    def cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_per_1m + output_tokens * self.output_per_1m
        ) / 1_000_000


# Keyed by the *model name* reported in API responses, not the deployment name:
# deployments are renameable aliases, price follows the underlying model.
# Prices checked 2026-08 (Azure OpenAI, Global Standard, eastus2).
DEFAULT_PRICES: dict[str, ModelPrice] = {
    "gpt-5-mini": ModelPrice(input_per_1m=0.25, output_per_1m=2.00),
    "text-embedding-3-small": ModelPrice(input_per_1m=0.02, output_per_1m=0.0),
}


class Settings(BaseSettings):
    """All environment-driven settings. See .env.example for documentation."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Azure — auth is DefaultAzureCredential, so no API key field exists.
    azure_openai_endpoint: str = Field(alias="AZURE_OPENAI_ENDPOINT")

    sut_deployment: str = Field(default="gpt-small", alias="AEP_SUT_DEPLOYMENT")
    judge_deployment: str = Field(default="gpt-small", alias="AEP_JUDGE_DEPLOYMENT")
    embeddings_deployment: str = Field(default="embeddings", alias="AEP_EMBEDDINGS_DEPLOYMENT")

    # Langfuse Cloud, reached via plain OTLP/HTTP — no vendor SDK (see ADR-0001).
    langfuse_public_key: str = Field(alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_HOST")

    max_concurrency: int = Field(default=4, alias="AEP_MAX_CONCURRENCY")

    prices: dict[str, ModelPrice] = DEFAULT_PRICES

    def price_for(self, model_name: str) -> ModelPrice | None:
        """Look up price by response model name, tolerating versioned names.

        Azure sometimes reports 'gpt-5-mini-2025-08-07' where the table has
        'gpt-5-mini'. Unknown models return None: the caller records cost as
        unknown rather than as zero, because a silent $0 is a lie in a cost
        metric.
        """
        if model_name in self.prices:
            return self.prices[model_name]
        for known, price in self.prices.items():
            if model_name.startswith(known):
                return price
        return None


def get_settings() -> Settings:
    """Build settings fresh from the environment.

    Deliberately not cached: the eval runner and tests mutate the environment
    (e.g. pointing the judge at a different deployment), and a cached singleton
    would make those changes silently invisible.
    """
    return Settings()  # type: ignore[call-arg]  # fields come from env at runtime
