from typing import Any

from django.db import migrations
from django.utils.text import slugify

COMMITTEES = [
    "Executive Board",
    "Competitions",
    "Operations",
    "Tech",
    "Finance",
    "Governance",
    "Safeguarding",
    "College",
    "Development",
    "NTC",
    "Project GameChangers",
]

ROUTES = {
    "Competitions": ["Competitions"],
    "Tournament": ["Competitions"],
    "Tech": ["Tech"],
    "Account": ["Operations"],
    "Payment": ["Operations"],
    "Subscription": ["Operations"],
    "Other": ["Operations"],
}


def seed(apps: Any, schema_editor: Any) -> None:
    Committee = apps.get_model("server", "Committee")
    TicketRoute = apps.get_model("server", "TicketRoute")
    for order, name in enumerate(COMMITTEES):
        Committee.objects.get_or_create(name=name, defaults={"slug": slugify(name), "order": order})
    for category, names in ROUTES.items():
        for name in names:
            TicketRoute.objects.get_or_create(
                category=category, committee=Committee.objects.get(name=name)
            )


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0174_ticket_assignees_from_assigned_to"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
