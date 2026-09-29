import functools
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.http import HttpRequest
from ninja import Router

from server.core.models import User

from .schema import (
    ChatHistorySchema,
    ErrorSchema,
    MessageResponseSchema,
    MessageSchema,
    SuccessSchema,
)

if TYPE_CHECKING:
    import groq

    from .llm import ChatService

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


@functools.cache
def _groq_client() -> "groq.Client":
    # Lazy: groq pulls httpx/anyio/trio, ~11MB in every worker.
    import groq

    return groq.Client(api_key=settings.GROQ_API_KEY)


def _chat_service(user: User) -> "ChatService":
    from .llm import ChatService

    return ChatService(_groq_client(), user)


@router.post(
    "/send_message", response={200: MessageResponseSchema, 400: ErrorSchema, 500: ErrorSchema}
)
def send_message(
    request: AuthenticatedHttpRequest, data: MessageSchema
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    """Send a message to the chat service and get a response."""
    chat_service = _chat_service(request.user)
    try:
        response = chat_service.process_message(request.user, data.message)
        return {"response": response}
    except Exception as e:
        return 500, {"message": str(e)}


@router.get("/history", response={200: ChatHistorySchema, 500: ErrorSchema})
def get_history(request: AuthenticatedHttpRequest) -> dict[str, Any] | tuple[int, dict[str, str]]:
    """Get the chat history for the current user."""
    chat_service = _chat_service(request.user)
    try:
        history = chat_service.get_session_history(request.user)
        return history
    except Exception as e:
        return 500, {"message": str(e)}


@router.post("/clear_history", response={200: SuccessSchema, 404: ErrorSchema, 500: ErrorSchema})
def clear_history(request: AuthenticatedHttpRequest) -> dict[str, Any] | tuple[int, dict[str, str]]:
    """Clear the chat history for the current user."""
    chat_service = _chat_service(request.user)
    try:
        success = chat_service.clear_session(request.user)
        if success:
            return {"message": "Chat history cleared successfully"}
        return 404, {"message": "No active chat session found"}
    except Exception as e:
        return 500, {"message": str(e)}
