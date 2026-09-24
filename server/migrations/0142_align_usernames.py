from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def align_usernames(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Make username the casefolded email, which is what creates it already.

    Sign in looks username up exactly, so the few rows that drifted from
    their address, or kept their capitals, have to be brought in line. A
    username whose target another account already holds is left alone: that
    pair is a duplicate, and the merge flow is what resolves it.

    Repeated until nothing moves, because one pass is order dependent: a row
    whose target is held by a row not reached yet is skipped, and that target
    is free once the other row is renamed. Each pass aligns at least one more
    account, so this ends.
    """
    User = apps.get_model("server", "User")  # noqa: N806
    taken = set(User.objects.values_list("username", flat=True))

    moved = True
    while moved:
        moved = False
        for user in list(User.objects.only("id", "username", "email")):
            target = (user.email or user.username).strip().lower()
            if not target or target == user.username or target in taken:
                continue
            taken.discard(user.username)
            taken.add(target)
            user.username = target
            user.save(update_fields=["username"])
            moved = True


class Migration(migrations.Migration):
    dependencies = [("server", "0141_agent_session_history_cleared_at")]

    operations = [migrations.RunPython(align_usernames, migrations.RunPython.noop)]
