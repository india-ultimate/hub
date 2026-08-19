from typing import Any

from ninja import Schema


class ErrorSchema(Schema):
    message: str


class SuccessSchema(Schema):
    message: str


class ModelInfoSchema(Schema):
    id: str
    label: str
    hint: str
    is_default: bool
    req_per_5h: int = 0


class ModelsResponseSchema(Schema):
    models: list[ModelInfoSchema]
    default_model_id: str


class SendMessageSchema(Schema):
    tournament_id: int
    message: str
    model_id: str | None = None


class AnswerQuestionSchema(Schema):
    selected_ids: list[str] = []
    other_text: str | None = None
    skip: bool = False


class SetModelSchema(Schema):
    tournament_id: int
    model_id: str


class AgentMessageSchema(Schema):
    id: int
    role: str
    content: str
    message_kind: str
    payload: dict[str, Any]
    model_id: str
    created_at: str


class QuestionSchema(Schema):
    id: int
    prompt: str
    context: str
    selection_mode: str
    options: list[dict[str, Any]]
    allow_other: bool
    allow_skip: bool
    status: str
    answer: dict[str, Any]


class ProposalSchema(Schema):
    id: int
    tool_name: str
    summary: str
    payload: dict[str, Any]
    # Resolved names for player ids in the payload (spirit MVP/MSP). Kept off the
    # payload itself so confirm still replays bare ids.
    player_names: dict[str, str] = {}
    status: str
    created_at: str


class HistorySchema(Schema):
    session_id: int
    tournament_id: int
    model_id: str
    messages: list[AgentMessageSchema]
    pending_question: QuestionSchema | None
    pending_proposals: list[ProposalSchema]


class AgentResponseSchema(Schema):
    response: str
    session_id: int
    model_id: str
    pending_question: QuestionSchema | None = None
    pending_proposals: list[ProposalSchema] = []
    tool_events: list[dict[str, Any]] = []


class ConfirmResultSchema(Schema):
    message: str
    result: dict[str, Any] = {}
