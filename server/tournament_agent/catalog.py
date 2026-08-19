"""Curated OpenCode Go model allowlist for the tournament agent."""

from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Any, Literal

from django.conf import settings

ApiStyle = Literal["openai", "anthropic", "responses"]


@dataclass(frozen=True)
class AgentModel:
    id: str
    label: str
    hint: str
    api_style: ApiStyle
    # OpenCode Go published request quotas (approx). Used for bakeoff value ranking.
    req_per_5h: int = 0
    is_default: bool = False


# Only these appear in the UI picker. Keep models that scored 90%+ on the
# capability bakeoff. Default is GPT-5.6 Luna: it ties for the top score (100.0)
# and answers in roughly a quarter of the time of the other two that matched it,
# which matters more than quota headroom for a tool staff use during a live event.
AGENT_MODELS: tuple[AgentModel, ...] = (
    AgentModel(
        id="gpt-5.6-luna",
        label="GPT-5.6 Luna",
        # Note: the Responses API path in `clients.opencode` buffers — this model
        # does not stream incrementally, so replies land in one piece.
        hint="Top score, fastest",
        api_style="responses",
        req_per_5h=2050,
        is_default=True,
    ),
    AgentModel(
        id="glm-5.2",
        label="GLM 5.2",
        hint="Top score, slower",
        api_style="openai",
        req_per_5h=880,
    ),
    AgentModel(
        id="minimax-m3",
        label="MiniMax M3",
        hint="Fast",
        api_style="anthropic",
        req_per_5h=3200,
    ),
    AgentModel(
        id="hy3",
        label="Hy3",
        hint="Top score, high quota",
        api_style="openai",
        req_per_5h=4300,
    ),
)

_MODEL_BY_ID = {m.id: m for m in AGENT_MODELS}


def get_model(model_id: str) -> AgentModel | None:
    return _MODEL_BY_ID.get(model_id)


def is_allowed_model(model_id: str) -> bool:
    return model_id in _MODEL_BY_ID


def default_model_id() -> str:
    """The curated default: whichever model the bakeoff put `is_default` on."""
    for m in AGENT_MODELS:
        if m.is_default:
            return m.id
    return AGENT_MODELS[0].id


def configured_default_model_id() -> str:
    """The default a new session gets, honouring a deploy-time override.

    The catalog is the source of truth — it is what the eval suite actually scored,
    and it is the one place to change the default. `OPENCODE_GO_DEFAULT_MODEL` stays
    as an operational escape hatch for switching without a deploy, but it only wins
    when it names a model that is still in the allowlist. A stale or misspelt value
    is ignored rather than raising, because the alternative is every session failing
    to open until someone fixes the environment.
    """
    override = str(getattr(settings, "OPENCODE_GO_DEFAULT_MODEL", "") or "").strip()
    if override and is_allowed_model(override):
        return override
    return default_model_id()


def value_score(suite_score: float, model_id: str) -> float:
    """Capability x log(quota) so high score + usable limits win over peak-only models."""
    model = get_model(model_id)
    quota = max(int(model.req_per_5h) if model else 1, 1)
    return float(suite_score) * log10(quota + 1)


def recommend_balanced_default(model_results: dict[str, Any]) -> str:
    """Pick default from bakeoff: maximize value_score, then pass^k, then lower latency."""

    def key(item: tuple[str, Any]) -> tuple[float, float, float]:
        mid, result = item
        return (
            value_score(float(result.get("suite_score") or 0.0), mid),
            float(result.get("pass_hat_k") or 0.0),
            -float(result.get("mean_latency_s") or 0.0),
        )

    return max(model_results.items(), key=key)[0]


def models_for_api() -> list[dict[str, str | bool | int]]:
    return [
        {
            "id": m.id,
            "label": m.label,
            "hint": m.hint,
            "is_default": m.is_default,
            "req_per_5h": m.req_per_5h,
        }
        for m in AGENT_MODELS
    ]
