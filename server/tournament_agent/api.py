import json
from collections.abc import Iterator
from typing import Any

from django.http import HttpRequest, StreamingHttpResponse
from ninja import Router

from server.core.models import User
from server.tournament_agent.catalog import default_model_id, models_for_api
from server.tournament_agent.models import AgentProposal, AgentQuestion, TournamentAgentSession
from server.tournament_agent.proposals import ProposalApplyError, apply_proposal, reject_proposal
from server.tournament_agent.schema import (
    AgentResponseSchema,
    AnswerQuestionSchema,
    ConfirmResultSchema,
    ErrorSchema,
    HistorySchema,
    ModelsResponseSchema,
    SendMessageSchema,
    SetModelSchema,
    SuccessSchema,
)
from server.tournament_agent.service import TournamentAgentService

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


def _staff_or_401(request: AuthenticatedHttpRequest) -> dict[str, str] | None:
    if not request.user.is_staff:
        return {"message": "Staff only"}
    return None


def _sse_frame(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _sse_body(events: Iterator[dict[str, Any]]) -> Iterator[str]:
    """Wrap agent events as SSE frames.

    Headers are already sent once streaming starts, so a failure mid-turn cannot
    become an HTTP error status - it is delivered as a terminal `error` frame.
    """
    yield ": open\n\n"
    try:
        for event in events:
            yield _sse_frame(str(event.get("type") or "message"), event)
    except Exception as exc:  # noqa: BLE001 — must reach the client as an error frame
        yield _sse_frame("error", {"type": "error", "message": str(exc)[:500]})


def _sse_response(events: Iterator[dict[str, Any]]) -> StreamingHttpResponse:
    response = StreamingHttpResponse(_sse_body(events), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    # Defeats nginx proxy_buffering even where the location block is missed.
    response["X-Accel-Buffering"] = "no"
    return response


def _sse_error(message: str, status: int) -> StreamingHttpResponse:
    def one() -> Iterator[dict[str, Any]]:
        yield {"type": "error", "message": message}

    response = _sse_response(one())
    response.status_code = status
    return response


@router.get("/models", response={200: ModelsResponseSchema, 401: ErrorSchema})
def list_models(request: AuthenticatedHttpRequest) -> dict[str, Any] | tuple[int, dict[str, str]]:
    err = _staff_or_401(request)
    if err:
        return 401, err
    return {"models": models_for_api(), "default_model_id": default_model_id()}


@router.get("/history", response={200: HistorySchema, 400: ErrorSchema, 401: ErrorSchema})
def get_history(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    err = _staff_or_401(request)
    if err:
        return 401, err
    service = TournamentAgentService(request.user)
    try:
        session = service.get_or_create_session(tournament_id)
        return service.history(session)
    except TournamentAgentSession.DoesNotExist:
        return 400, {"message": "Session not found"}
    except Exception as exc:  # noqa: BLE001
        return 400, {"message": str(exc)}


@router.post(
    "/send_message",
    response={200: AgentResponseSchema, 400: ErrorSchema, 401: ErrorSchema, 500: ErrorSchema},
)
def send_message(
    request: AuthenticatedHttpRequest, data: SendMessageSchema
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    err = _staff_or_401(request)
    if err:
        return 401, err
    service = TournamentAgentService(request.user)
    try:
        session = service.get_or_create_session(data.tournament_id, model_id=data.model_id)
        return service.process_message(session, data.message)
    except ValueError as exc:
        return 400, {"message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return 500, {"message": str(exc)}


@router.post("/stream_message")
def stream_message(
    request: AuthenticatedHttpRequest, data: SendMessageSchema
) -> StreamingHttpResponse:
    """Same turn as send_message, delivered as Server-Sent Events."""
    err = _staff_or_401(request)
    if err:
        return _sse_error(err["message"], 401)
    service = TournamentAgentService(request.user, streaming=True)
    try:
        session = service.get_or_create_session(data.tournament_id, model_id=data.model_id)
    except ValueError as exc:
        return _sse_error(str(exc), 400)
    except Exception as exc:  # noqa: BLE001
        return _sse_error(str(exc), 400)
    return _sse_response(service.process_message_events(session, data.message))


@router.post("/questions/{question_id}/answer_stream")
def answer_question_stream(
    request: AuthenticatedHttpRequest, question_id: int, data: AnswerQuestionSchema
) -> StreamingHttpResponse:
    """Same turn as answer_question, delivered as Server-Sent Events."""
    err = _staff_or_401(request)
    if err:
        return _sse_error(err["message"], 401)
    try:
        question = AgentQuestion.objects.select_related("session").get(id=question_id)
    except AgentQuestion.DoesNotExist:
        return _sse_error("Question not found", 400)
    if question.session.user_id != request.user.id:
        return _sse_error("Not your session", 401)
    service = TournamentAgentService(request.user, streaming=True)
    try:
        # Validates and records the answer eagerly, so a bad answer is a 400 rather
        # than an error frame on an already-committed 200 stream.
        events = service.answer_question_events(
            question.session,
            question_id,
            selected_ids=data.selected_ids,
            other_text=data.other_text,
            skip=data.skip,
        )
    except ValueError as exc:
        return _sse_error(str(exc), 400)
    return _sse_response(events)


@router.post(
    "/questions/{question_id}/answer",
    response={200: AgentResponseSchema, 400: ErrorSchema, 401: ErrorSchema, 500: ErrorSchema},
)
def answer_question(
    request: AuthenticatedHttpRequest, question_id: int, data: AnswerQuestionSchema
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    err = _staff_or_401(request)
    if err:
        return 401, err
    try:
        question = AgentQuestion.objects.select_related("session").get(id=question_id)
    except AgentQuestion.DoesNotExist:
        return 400, {"message": "Question not found"}
    if question.session.user_id != request.user.id:
        return 401, {"message": "Not your session"}
    service = TournamentAgentService(request.user)
    try:
        return service.answer_question(
            question.session,
            question_id,
            selected_ids=data.selected_ids,
            other_text=data.other_text,
            skip=data.skip,
        )
    except ValueError as exc:
        return 400, {"message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return 500, {"message": str(exc)}


@router.post(
    "/proposals/{proposal_id}/confirm",
    response={200: ConfirmResultSchema, 400: ErrorSchema, 401: ErrorSchema},
)
def confirm_proposal(
    request: AuthenticatedHttpRequest, proposal_id: int
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    err = _staff_or_401(request)
    if err:
        return 401, err
    try:
        proposal = AgentProposal.objects.select_related("session").get(id=proposal_id)
    except AgentProposal.DoesNotExist:
        return 400, {"message": "Proposal not found"}
    if proposal.session.user_id != request.user.id and not request.user.is_superuser:
        return 401, {"message": "Not your proposal"}
    try:
        result = apply_proposal(proposal)
        return {"message": "Proposal confirmed", "result": result}
    except ProposalApplyError as exc:
        return 400, {"message": str(exc)}


@router.post(
    "/proposals/{proposal_id}/reject",
    response={200: SuccessSchema, 400: ErrorSchema, 401: ErrorSchema},
)
def reject_proposal_endpoint(
    request: AuthenticatedHttpRequest, proposal_id: int
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    err = _staff_or_401(request)
    if err:
        return 401, err
    try:
        proposal = AgentProposal.objects.select_related("session").get(id=proposal_id)
    except AgentProposal.DoesNotExist:
        return 400, {"message": "Proposal not found"}
    if proposal.session.user_id != request.user.id and not request.user.is_superuser:
        return 401, {"message": "Not your proposal"}
    try:
        reject_proposal(proposal)
        return {"message": "Proposal rejected"}
    except ProposalApplyError as exc:
        return 400, {"message": str(exc)}


@router.post("/set_model", response={200: SuccessSchema, 400: ErrorSchema, 401: ErrorSchema})
def set_model(
    request: AuthenticatedHttpRequest, data: SetModelSchema
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    err = _staff_or_401(request)
    if err:
        return 401, err
    service = TournamentAgentService(request.user)
    try:
        session = service.get_or_create_session(data.tournament_id)
        service.set_model(session, data.model_id)
        return {"message": f"Model set to {data.model_id}"}
    except ValueError as exc:
        return 400, {"message": str(exc)}


@router.post("/clear_history", response={200: SuccessSchema, 400: ErrorSchema, 401: ErrorSchema})
def clear_history(
    request: AuthenticatedHttpRequest, tournament_id: int
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    err = _staff_or_401(request)
    if err:
        return 401, err
    service = TournamentAgentService(request.user)
    try:
        session = service.get_or_create_session(tournament_id)
        service.clear_session(session)
        return {"message": "History cleared"}
    except Exception as exc:  # noqa: BLE001
        return 400, {"message": str(exc)}
