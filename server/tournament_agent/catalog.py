"""Curated OpenCode Go model allowlist for the tournament agent."""

from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Any, Literal

ApiStyle = Literal["openai", "anthropic"]


@dataclass(frozen=True)
class AgentModel:
    id: str
    label: str
    hint: str
    api_style: ApiStyle
    # OpenCode Go published request quotas (approx). Used for bakeoff value ranking.
    req_per_5h: int = 0
    is_default: bool = False


# Only these appear in the UI picker. Update when Go roster / quotas change.
# Default = best bakeoff capability × quota balance (not raw score alone).
# MiniMax M3 led the hardened suite (~96) at 3,200 req/5h; GLM scored well
# but is ~4× more quota-constrained (880). Flash/MiMo base maximize quota.
AGENT_MODELS: tuple[AgentModel, ...] = (
    AgentModel(
        id="minimax-m3",
        label="MiniMax M3",
        hint="Best balance",
        api_style="anthropic",
        req_per_5h=3200,
        is_default=True,
    ),
    AgentModel(
        id="glm-5.2",
        label="GLM 5.2",
        hint="Strong, tight limits",
        api_style="openai",
        req_per_5h=880,
    ),
    AgentModel(
        id="kimi-k2.7-code",
        label="Kimi K2.7 Code",
        hint="Solid tools",
        api_style="openai",
        req_per_5h=1350,
    ),
    AgentModel(
        id="deepseek-v4-pro",
        label="DeepSeek V4 Pro",
        hint="Strong reasoning",
        api_style="openai",
        req_per_5h=3450,
    ),
    AgentModel(
        id="qwen3.7-plus",
        label="Qwen3.7 Plus",
        hint="More quota",
        api_style="anthropic",
        req_per_5h=4300,
    ),
    AgentModel(
        id="mimo-v2.5-pro",
        label="MiMo V2.5 Pro",
        hint="Capable mid-tier",
        api_style="openai",
        req_per_5h=3250,
    ),
    AgentModel(
        id="deepseek-v4-flash",
        label="DeepSeek V4 Flash",
        hint="Highest quota",
        api_style="openai",
        req_per_5h=31650,
    ),
)

_MODEL_BY_ID = {m.id: m for m in AGENT_MODELS}


def get_model(model_id: str) -> AgentModel | None:
    return _MODEL_BY_ID.get(model_id)


def is_allowed_model(model_id: str) -> bool:
    return model_id in _MODEL_BY_ID


def default_model_id() -> str:
    for m in AGENT_MODELS:
        if m.is_default:
            return m.id
    return AGENT_MODELS[0].id


def value_score(suite_score: float, model_id: str) -> float:
    """Capability × log(quota) so high score + usable limits win over peak-only models."""
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
