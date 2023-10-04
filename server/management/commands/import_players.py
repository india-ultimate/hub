import csv
from datetime import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils.text import slugify

from server.models import Guardianship, Player, User

GENDERS = {t.label: t for t in Player.GenderTypes}
STATE_UT = {t.label: t for t in Player.StatesUTs}
OCCUPATIONS = {t.label: t for t in Player.OccupationTypes}
RELATIONS = {t.label: str(t) for t in Guardianship.Relation}

DATE_FORMAT = "%Y-%m-%d"


class Command(BaseCommand):
    help = "Import data from CSV file and create Player and User objects"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")
        parser.add_argument("--date-format", "-d", default=DATE_FORMAT, help="Date format used")
        parser.add_argument(
            "--guardian-email-optional",
            default=False,
            action="store_true",
            help="Make Guardian email an optional value",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        csv_file = options["csv_file"]

        with open(csv_file) as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Process each row of the CSV file
                email = row["email"]
                user_data = {
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "email": row["email"],
                    "phone": row["phone"],
                }
                user, created = User.objects.get_or_create(
                    username=email, email=email, defaults=user_data
                )

                date_of_birth = row["date_of_birth"]

                try:
                    dob = datetime.strptime(date_of_birth, options["date_format"])  # noqa: DTZ007
                except ValueError:
                    self.stderr.write(self.style.ERROR(f"Invalid date format: {date_of_birth}"))
                    continue

                player_data = {
                    "user": user,
                    "date_of_birth": dob.strftime("%Y-%m-%d"),
                    "gender": GENDERS.get(row["gender"], Player.GenderTypes.OTHER),
                    "other_gender": row["other_gender"] if row["other_gender"] != "-" else None,
                    "city": row["city"],
                    "state_ut": STATE_UT.get(row["state_ut"], None),
                    "not_in_india": row["not_in_india"].upper() == "Y",
                    "occupation": OCCUPATIONS.get(row["occupation"], None),
                    "educational_institution": row["educational_institution"],
                }
                if player_data["gender"] != Player.GenderTypes.OTHER:
                    player_data["match_up"] = player_data["gender"]

                try:
                    player = Player.objects.get(user=user)
                    for key, value in player_data.items():
                        setattr(player, key, value)
                except Player.DoesNotExist:
                    player = Player(**player_data)

                player.full_clean()

                guardian_email = row["guardian.email"]
                if (
                    not guardian_email
                    and row["guardian.relation"]
                    and options["guardian_email_optional"]
                ):
                    guardian_first_name = row["guardian.first_name"]
                    guardian_last_name = row["guardian.last_name"]
                    guardian_email = slugify(f"{guardian_first_name} {guardian_last_name}")

                has_guardian = guardian_email and row["guardian.relation"]
                if player.is_minor and not has_guardian:
                    raise RuntimeError(f"Missing Guardian information for {email}")

                player.save()

                if has_guardian and not player.is_minor:
                    print(f"Ignoring guardian information for major: {email}")

                elif has_guardian and player.is_minor:
                    guardian_data = {
                        "first_name": row["guardian.first_name"],
                        "last_name": row["guardian.last_name"],
                        "email": guardian_email,
                        "phone": row["guardian.phone"],
                    }
                    guardian_user, created = User.objects.get_or_create(
                        username=guardian_email, defaults=guardian_data
                    )
                    if not created:
                        for key, value in guardian_data.items():
                            setattr(guardian_user, key, value)
                        guardian_user.save()

                    relation = RELATIONS.get(row["guardian.relation"], None)
                    guardianship_data = {"relation": relation, "user": guardian_user}
                    try:
                        guardianship = Guardianship.objects.get(player=player)
                        for key, value in guardianship_data.items():
                            setattr(guardianship, key, value)
                    except Guardianship.DoesNotExist:
                        guardianship = Guardianship(user=guardian_user, player=player, relation=relation)  # type: ignore[misc]
                        guardianship.full_clean()

                    guardianship.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully imported data for user {user.get_full_name()}"
                    )
                )
