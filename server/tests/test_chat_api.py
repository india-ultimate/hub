import json
from typing import Any
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase

from server.chat.models import ChatMessage, ChatMessageType, ChatSession
from server.core.models import User

# Test-specific constants
TEST_PASSWORD = "test_password_123"  # nosec B105


class ChatAPITestCase(TestCase):
    def setUp(self) -> None:
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=TEST_PASSWORD
        )
        self.client.force_login(self.user)
        self.chat_session = ChatSession.objects.create(user=self.user)
        ChatMessage.objects.create(
            session=self.chat_session, message="Hello", type=ChatMessageType.USER
        )
        ChatMessage.objects.create(
            session=self.chat_session, message="Hi there!", type=ChatMessageType.ASSISTANT
        )

    def tearDown(self) -> None:
        ChatSession.objects.all().delete()
        ChatMessage.objects.all().delete()

    @patch("server.chat.llm.groq.Client")
    @patch("server.chat.api.ChatService")
    def test_send_message_success(self, mock_chat_service: Any, mock_groq_client: Any) -> None:
        """Test successful message sending."""
        mock_chat_service.return_value.process_message = MagicMock(
            return_value="This is a test response"
        )
        response = self.client.post(
            "/api/chat/send_message",
            data=json.dumps({"message": "Test message"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"response": "This is a test response"})
        mock_chat_service.return_value.process_message.assert_called_once_with(
            self.user, "Test message"
        )

    @patch("server.chat.llm.groq.Client")
    @patch("server.chat.api.ChatService")
    def test_send_message_error(self, mock_chat_service: Any, mock_groq_client: Any) -> None:
        """Test message sending with error."""
        mock_chat_service.return_value.process_message = MagicMock(
            side_effect=Exception("Test error")
        )
        response = self.client.post(
            "/api/chat/send_message",
            data=json.dumps({"message": "Test message"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.content), {"message": "Test error"})

    @patch("server.chat.llm.groq.Client")
    def test_get_history_success(self, mock_groq_client: Any) -> None:
        """Test successful history retrieval."""
        response = self.client.get("/api/chat/history")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("session_id", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
        self.assertIn("messages", data)
        messages = data["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["type"], "USER")
        self.assertEqual(messages[0]["message"], "Hello")
        self.assertEqual(messages[1]["type"], "ASSISTANT")
        self.assertEqual(messages[1]["message"], "Hi there!")

    @patch("server.chat.llm.groq.Client")
    @patch("server.chat.api.ChatService")
    def test_get_history_error(self, mock_chat_service: Any, mock_groq_client: Any) -> None:
        """Test history retrieval with error."""
        mock_chat_service.return_value.get_session_history.side_effect = Exception("Test error")
        response = self.client.get("/api/chat/history")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.content), {"message": "Test error"})

    @patch("server.chat.llm.groq.Client")
    def test_clear_history_success(self, mock_groq_client: Any) -> None:
        """Test successful history clearing."""
        response = self.client.post("/api/chat/clear_history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content), {"message": "Chat history cleared successfully"}
        )
        exists = ChatSession.objects.filter(user=self.user).exists()
        self.assertFalse(exists)

    @patch("server.chat.llm.groq.Client")
    def test_clear_history_no_session(self, mock_groq_client: Any) -> None:
        """Test clearing history when no session exists."""
        self.chat_session.delete()
        response = self.client.post("/api/chat/clear_history")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content), {"message": "No active chat session found"})

    @patch("server.chat.llm.groq.Client")
    @patch("server.chat.api.ChatService")
    def test_clear_history_error(self, mock_chat_service: Any, mock_groq_client: Any) -> None:
        """Test history clearing with error."""
        mock_chat_service.return_value.clear_session.side_effect = Exception("Test error")
        response = self.client.post("/api/chat/clear_history")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.content), {"message": "Test error"})

    @patch("server.chat.llm.groq.Client")
    def test_authentication_required(self, mock_groq_client: Any) -> None:
        """Test that authentication is required for all endpoints."""
        self.client.logout()
        response = self.client.post(
            "/api/chat/send_message",
            data=json.dumps({"message": "Test message"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        response = self.client.get("/api/chat/history")
        self.assertEqual(response.status_code, 401)
        response = self.client.post("/api/chat/clear_history")
        self.assertEqual(response.status_code, 401)
