from django.db import models


class McpNonce(models.Model):
    key = models.CharField(max_length=32, unique=True)
    expires_at = models.DateTimeField(db_index=True)
