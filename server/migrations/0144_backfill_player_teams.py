from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def link_players_to_the_teams_they_were_rostered_on(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Give `Player.teams` the rosters it has never been told about.

    Until now the field only ever held what the Ultimate Central import put
    there, so a player rostered on the Hub shows no teams at all. From here the
    roster signals keep it current; this is the one-time catch-up.

    Only adds. Links with no roster row behind them are Ultimate Central
    history and stay, which is also why the reverse is a no-op -- afterwards
    nothing says which of the two put a given row there.
    """
    Player = apps.get_model("server", "Player")  # noqa: N806
    Registration = apps.get_model("server", "Registration")  # noqa: N806
    SeriesRegistration = apps.get_model("server", "SeriesRegistration")  # noqa: N806
    Link = Player.teams.through  # noqa: N806

    pairs = set(Registration.objects.values_list("player_id", "team_id"))
    pairs |= set(SeriesRegistration.objects.values_list("player_id", "team_id"))
    pairs -= set(Link.objects.values_list("player_id", "team_id"))

    Link.objects.bulk_create(
        [Link(player_id=player_id, team_id=team_id) for player_id, team_id in sorted(pairs)],
        batch_size=1000,
        ignore_conflicts=True,
    )
    print(f"  0144: linked {len(pairs)} player-team pairs from rosters")


class Migration(migrations.Migration):
    dependencies = [("server", "0143_duplicate_accounts")]

    operations = [
        migrations.RunPython(
            code=link_players_to_the_teams_they_were_rostered_on,
            reverse_code=migrations.RunPython.noop,
        )
    ]
