"""Handing the turn back to staff when the agent must not guess."""

from __future__ import annotations

from typing import Any

from server.tournament_agent.models import (
    AgentQuestion,
    QuestionSelectionMode,
    QuestionStatus,
)
from server.tournament_agent.tools.context import ToolContext

MIN_OPTIONS = 2
MAX_OPTIONS = 8


class AskUserPause(Exception):  # noqa: N818 — a pause, not an error
    """Raised when ask_user creates a pending question and the agent loop should stop."""

    def __init__(self, question: AgentQuestion) -> None:
        self.question = question
        super().__init__("Waiting for user answer")


def ask_user(
    ctx: ToolContext,
    prompt: str,
    selection_mode: str,
    options: list[dict[str, Any]],
    allow_other: bool = False,
    allow_skip: bool = False,
    context: str = "",
) -> dict[str, Any]:
    if selection_mode not in (QuestionSelectionMode.SINGLE, QuestionSelectionMode.MULTI):
        return {"error": "selection_mode must be 'single' or 'multi'"}
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        return {
            "error": f"options must be a list of {MIN_OPTIONS}-{MAX_OPTIONS} items "
            "with id and label"
        }
    clean_opts = []
    for opt in options:
        if "id" not in opt or "label" not in opt:
            return {"error": "each option needs id and label"}
        clean_opts.append(
            {
                "id": str(opt["id"]),
                "label": str(opt["label"]),
                "description": str(opt.get("description") or ""),
            }
        )

    AgentQuestion.objects.filter(session=ctx.session, status=QuestionStatus.PENDING).update(
        status=QuestionStatus.SUPERSEDED
    )
    question = AgentQuestion.objects.create(
        session=ctx.session,
        prompt=prompt,
        context=context,
        selection_mode=selection_mode,
        options=clean_opts,
        allow_other=bool(allow_other),
        allow_skip=bool(allow_skip),
        status=QuestionStatus.PENDING,
        created_by_message=ctx.assistant_message,
    )
    raise AskUserPause(question)
