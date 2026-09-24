from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def align_usernames(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Lowercase and strip usernames that are their own address spelled
    differently, which is what creates a username already.

    The Hub's sign in (/api/login, /api/otp-login) lowercases and strips
    what it is given before looking the username up exactly, so a username
    like "Rahul@X.com" or " rahul@x.com" can never be matched there. Only
    those are renamed: a username whose stripped, lowercased form is the
    account's stripped, lowercased address (or, with no address, its own).

    A username that is a genuinely different address or handle is left
    alone, even where the account's address has drifted from it. Renaming
    it would take away the way in it still is - the old address, or a
    staff handle for password sign in - and the next sign in with it would
    quietly make a new, empty account. Those are duplicates, and the merge
    flow resolves them with proof of who holds which inbox. A username whose
    target another account already holds is left alone for the same reason.

    One pass is enough: a target is only ever held by a username that is
    already its own lowercase form, and that account never moves.

    Each rename is printed as old -> new, so the deploy log is the record
    of what changed. The reverse is a no-op: it cannot restore the old
    spellings, which are kept nowhere but that log, and the Hub's sign in
    could not match them anyway. Django's own admin sign in is the one
    place a username is taken as typed; there the new spelling is the one
    to type.
    """
    User = apps.get_model("server", "User")  # noqa: N806
    taken = set(User.objects.values_list("username", flat=True))

    for user in User.objects.only("id", "username", "email").order_by("pk"):
        target = (user.email or user.username).strip().lower()
        if not target or target == user.username or target in taken:
            continue
        if user.username.strip().lower() != target:
            continue
        taken.discard(user.username)
        taken.add(target)
        print(f"  0142: user {user.pk} username {user.username!r} -> {target!r}")
        user.username = target
        user.save(update_fields=["username"])


class Migration(migrations.Migration):
    dependencies = [("server", "0141_agent_session_history_cleared_at")]

    operations = [migrations.RunPython(align_usernames, migrations.RunPython.noop)]
