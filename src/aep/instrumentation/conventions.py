"""OpenTelemetry GenAI semantic convention attribute names — the single source.

Why: the whole point of instrumenting with OTel instead of a vendor SDK is
portability (ADR-0001). That only holds if attribute names follow the public
GenAI semantic conventions and are never retyped inline — a typo in an
attribute name fails silently (the backend just shows nothing). Every span in
this codebase must take its attribute names from here.

Spec: https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""

# --- Official GenAI semantic conventions -----------------------------------
GEN_AI_SYSTEM = "gen_ai.system"  # e.g. "az.ai.openai"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"  # "chat" | "embeddings" | ...
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"  # deployment name we asked for
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"  # model the API reports back
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_TOOL_NAME = "gen_ai.tool.name"

# Operation name values defined by the spec that we use.
OP_CHAT = "chat"
OP_EMBEDDINGS = "embeddings"
OP_EXECUTE_TOOL = "execute_tool"
OP_INVOKE_AGENT = "invoke_agent"

# Value for gen_ai.system when talking to Azure OpenAI.
SYSTEM_AZURE_OPENAI = "az.ai.openai"

# --- Platform extensions (aep.* namespace) ---------------------------------
# Cost has no official semconv attribute yet, so it lives in our own
# namespace. It is computed client-side from the price table in config.py.
AEP_COST_USD = "aep.usage.cost_usd"
# True when the response model was missing from the price table — cost is
# then *unknown*, which is different from zero and must be visible.
AEP_COST_UNKNOWN = "aep.usage.cost_unknown"
