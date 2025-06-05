from typing import Any

import groq
from django.conf import settings
from django.http import HttpRequest
from ninja import Router

from server.core.models import User

from .llm import ChatService
from .schema import (
    ChatHistorySchema,
    ErrorSchema,
    MessageResponseSchema,
    MessageSchema,
    SuccessSchema,
)

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


groq_client = groq.Client(api_key=settings.GROQ_API_KEY)


@router.post(
    "/send_message", response={200: MessageResponseSchema, 400: ErrorSchema, 500: ErrorSchema}
)
def send_message(
    request: AuthenticatedHttpRequest, data: MessageSchema
) -> dict[str, Any] | tuple[int, dict[str, str]]:
    """Send a message to the chat service and get a response."""
    chat_service = ChatService(groq_client, request.user)
    try:
        response = chat_service.process_message(request.user, data.message)
        return {"response": response}
    except Exception as e:
        return 500, {"message": str(e)}


@router.get("/history", response={200: ChatHistorySchema, 500: ErrorSchema})
def get_history(request: AuthenticatedHttpRequest) -> dict[str, Any] | tuple[int, dict[str, str]]:
    """Get the chat history for the current user."""
    chat_service = ChatService(groq_client, request.user)
    try:
        history = chat_service.get_session_history(request.user)
        return history
    except Exception as e:
        return 500, {"message": str(e)}


@router.post("/clear_history", response={200: SuccessSchema, 404: ErrorSchema, 500: ErrorSchema})
def clear_history(request: AuthenticatedHttpRequest) -> dict[str, Any] | tuple[int, dict[str, str]]:
    """Clear the chat history for the current user."""
    chat_service = ChatService(groq_client, request.user)
    try:
        success = chat_service.clear_session(request.user)
        if success:
            return {"message": "Chat history cleared successfully"}
        return 404, {"message": "No active chat session found"}
    except Exception as e:
        return 500, {"message": str(e)}
