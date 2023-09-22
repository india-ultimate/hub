import datetime
import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils.timezone import now

from server.models import Event, Player, Team, UCPerson, UCRegistration
from server.top_score_utils import TopScoreClient


def to_date(date: str) -> datetime.date:
    return datetime.datetime.strptime(date, "%Y-%m-%d").date()  # noqa: DTZ007


class Command(BaseCommand):
    help = "Import registrations data from UC"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--all",
            default=False,
            action="store_true",
            help="Fetch registrations only for all events.",
        )
        parser.add_argument(
            "--since",
            default=None,
            type=to_date,
            help="Fetch registrations since specified date.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        since = options["since"]
        all_reg = options["all"]

        if all_reg and since:
            raise CommandError("--since and --all are exclusive options; choose one!")

        if all_reg:
            events = Event.objects.filter()

        elif since:
            events = Event.objects.filter(start_date__gte=since)

        else:
            today = now().date()
            events = Event.objects.filter(start_date__gte=today)

        n = events.count()
        self.stdout.write(self.style.WARNING(f"Fetching registrations for {n} events"))

        username = os.environ["TOPSCORE_USERNAME"]
        password = os.environ["TOPSCORE_PASSWORD"]
        client = TopScoreClient(username, password)
        for event in events:
            self.stdout.write(
                self.style.WARNING(f"Fetching registrations for event: {event.title}")
            )
            if event.ultimate_central_id is None:
                continue
            registrations = client.get_registrations(event.ultimate_central_id)
            if registrations is None:
                self.stdout.write(
                    self.style.ERROR(f"Fetched no registrations for event: {event.title}")
                )
                continue
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Fetched {len(registrations)} registrations for {event.title}"
                    )
                )

            self.stdout.write(
                self.style.WARNING(
                    f"Creating persons, teams and registrations for event: {event.title}"
                )
            )
            persons_data = [registration["Person"] for registration in registrations]
            persons_data_by_id = {person["id"]: person for person in persons_data if person}
            persons = [
                UCPerson(
                    id=person["id"],
                    email=person["email_canonical"],
                    dominant_hand=person["dominant_hand"] or "",
                    image_url=person["images"]["200"],
                    first_name=person["first_name"],
                    last_name=person["last_name"],
                    slug=person["slug"],
                )
                for person_id, person in persons_data_by_id.items()
            ]
            persons = UCPerson.objects.bulk_create(
                persons,
                update_conflicts=True,
                update_fields=[
                    "first_name",
                    "last_name",
                    "image_url",
                    "email",
                    "slug",
                    "dominant_hand",
                ],
                unique_fields=["id"],
            )

            teams_data = [registration["Team"] for registration in registrations]
            # NOTE: We ignore registrations without an associated team
            teams_data = [t for t in teams_data if t is not None]
            teams_data_by_id = {t["id"]: t for t in teams_data}
            teams = [
                Team(
                    ultimate_central_id=team_id,
                    ultimate_central_creator_id=team["creator_id"],
                    ultimate_central_slug=team["slug"],
                    facebook_url=team["facebook_url"],
                    image_url=team["images"]["200"],
                    name=team["name"],
                )
                for team_id, team in teams_data_by_id.items()
            ]
            teams = Team.objects.bulk_create(
                teams,
                update_conflicts=True,
                update_fields=[
                    "name",
                    "image_url",
                    "facebook_url",
                    "ultimate_central_slug",
                    "ultimate_central_creator_id",
                ],
                unique_fields=["ultimate_central_id"],
            )
            team_ids = {team.ultimate_central_id for team in teams}
            uc_id_to_team_id = dict(
                Team.objects.filter(ultimate_central_id__in=team_ids).values_list(
                    "ultimate_central_id", "id"
                )
            )

            registration_objs = [
                UCRegistration(
                    id=registration["id"],
                    event=event,
                    team_id=uc_id_to_team_id[registration["Team"]["id"]],
                    person_id=registration["Person"]["id"],
                    roles=registration["roles"],
                )
                for registration in registrations
                if registration["Team"] is not None
            ]
            UCRegistration.objects.bulk_create(
                registration_objs,
                update_conflicts=True,
                update_fields=[
                    "team_id",
                    "roles",
                ],
                unique_fields=["id"],
            )

            # Add Team to registered Players
            player_uc_ids_to_team_uc_ids = {
                registration["person_id"]: registration["team_id"]
                for registration in registrations
                if registration["team_id"] is not None
            }
            players = Player.objects.filter(
                ultimate_central_id__in=list(player_uc_ids_to_team_uc_ids.keys())
            )
            for player in players:
                team_uc_id = player_uc_ids_to_team_uc_ids[player.ultimate_central_id]
                team_id = uc_id_to_team_id[team_uc_id]
                player.teams.add(team_id)
