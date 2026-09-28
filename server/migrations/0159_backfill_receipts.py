"""Receipts for every subscription paid before receipts existed.

The work lives in server/receipts/backfill.py, so the `issue_missing_receipts`
command can run it again for orders the old release captured after this
migration took its snapshot. It works through `apps.get_model` throughout, so
this migration keeps running against a fresh database with historical models.
Its signature must stay compatible with these calls, or be inlined here before
it changes.
"""

from typing import Any

from django.db import migrations

from server.receipts import backfill as module


def backfill(apps: Any, schema_editor: Any) -> None:
    module.backfill(apps, schema_editor)


def unbackfill(apps: Any, schema_editor: Any) -> None:
    module.unbackfill(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [("server", "0158_receipts")]

    operations = [migrations.RunPython(backfill, unbackfill)]
