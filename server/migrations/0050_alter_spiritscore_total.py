from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def generate_spirit_score_total(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Generate sprit score total"""
    SpiritScore = apps.get_model("server", "SpiritScore")  # noqa: N806

    spirit_scores = SpiritScore.objects.all()
    for spirit_score in spirit_scores:
        spirit_score.total = (
            spirit_score.rules
            + spirit_score.fouls
            + spirit_score.fair
            + spirit_score.positive
            + spirit_score.communication
        )

    SpiritScore.objects.bulk_update(spirit_scores, ["total"])


def remove_spirit_score_totals(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    SpiritScore = apps.get_model("server", "SpiritScore")  # noqa: N806

    spirit_scores = SpiritScore.objects.all()

    for spirit_score in spirit_scores:
        spirit_score.total = 0

    SpiritScore.objects.bulk_update(spirit_scores, ["total"])


class Migration(migrations.Migration):
    dependencies = [("server", "0049_spiritscore_total")]

    operations = [
        migrations.RunPython(
            code=generate_spirit_score_total, reverse_code=remove_spirit_score_totals
        )
    ]
