from __future__ import annotations

from django.db import models

from server.core.models import User
from server.tournament.models import Tournament
from server.tournament_agent.catalog import default_model_id


class TournamentAgentSession(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="tournament_agent_sessions"
    )
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="agent_sessions"
    )
    model_id = models.CharField(max_length=64, default=default_model_id)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "tournament"]),
        ]

    def __str__(self) -> str:
        return f"TournamentAgentSession {self.id} (t={self.tournament_id})"


class MessageKind(models.TextChoices):
    TEXT = "text", "Text"
    QUESTION = "question", "Question"
    ANSWER = "answer", "Answer"
    PROPOSAL_REF = "proposal_ref", "Proposal reference"


class MessageRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    SYSTEM = "system", "System"


class TournamentAgentMessage(models.Model):
    session = models.ForeignKey(
        TournamentAgentSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=16, choices=MessageRole.choices)
    content = models.TextField(blank=True, default="")
    message_kind = models.CharField(
        max_length=32, choices=MessageKind.choices, default=MessageKind.TEXT
    )
    model_id = models.CharField(max_length=64, blank=True, default="")
    # Structured payload for questions/answers/proposal refs (display + resume).
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"AgentMessage {self.id} ({self.role}/{self.message_kind})"


class QuestionSelectionMode(models.TextChoices):
    SINGLE = "single", "Single"
    MULTI = "multi", "Multi"


class QuestionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ANSWERED = "answered", "Answered"
    SKIPPED = "skipped", "Skipped"
    SUPERSEDED = "superseded", "Superseded"


class AgentQuestion(models.Model):
    session = models.ForeignKey(
        TournamentAgentSession, on_delete=models.CASCADE, related_name="questions"
    )
    prompt = models.TextField()
    context = models.TextField(blank=True, default="")
    selection_mode = models.CharField(
        max_length=16, choices=QuestionSelectionMode.choices, default=QuestionSelectionMode.SINGLE
    )
    options = models.JSONField(default=list)  # [{id, label, description?}]
    allow_other = models.BooleanField(default=False)
    allow_skip = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16, choices=QuestionStatus.choices, default=QuestionStatus.PENDING
    )
    answer = models.JSONField(default=dict, blank=True)  # {selected_ids, other_text?}
    created_by_message = models.ForeignKey(
        TournamentAgentMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_questions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AgentQuestion {self.id} ({self.status})"


class ProposalStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    # Staff decided. Kept distinct from EXPIRED so "how often is the agent turned
    # down?" stays an answerable question.
    REJECTED = "rejected", "Rejected"
    # Retired without anyone deciding: replaced by a newer plan from the same tool,
    # or the conversation it belonged to was cleared.
    EXPIRED = "expired", "Expired"


class AgentProposal(models.Model):
    session = models.ForeignKey(
        TournamentAgentSession, on_delete=models.CASCADE, related_name="proposals"
    )
    tool_name = models.CharField(max_length=64)
    summary = models.TextField()
    payload = models.JSONField(default=dict)  # canonical JSON with real DB ids
    status = models.CharField(
        max_length=16, choices=ProposalStatus.choices, default=ProposalStatus.PENDING
    )
    created_by_message = models.ForeignKey(
        TournamentAgentMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_proposals",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AgentProposal {self.id} ({self.tool_name}/{self.status})"
