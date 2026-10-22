from typing import Any

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from server.mcp.models import McpNonce


class Command(BaseCommand):
    help = "Delete MCP confirmation nonces that have expired"

    def handle(self, *args: Any, **options: Any) -> None:
        deleted, _ = McpNonce.objects.filter(expires_at__lt=now()).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired MCP nonces"))
