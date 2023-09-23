import csv
from datetime import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.models import Guardianship, Player, User

GENDERS = {t.label: t for t in Player.GenderTypes}
STATE_UT = {t.label: t for t in Player.StatesUTs}
OCCUPATIONS = {t.label: t for t in Player.OccupationTypes}
RELATIONS = {t.label: str(t) for t in Guardianship.Relation}


class Command(BaseCommand):
    help = "Import data from CSV file and create Player and User objects"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")

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
                    dob = datetime.strptime(date_of_birth, "%d/%m/%Y")  # noqa: DTZ007
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

                try:
                    player = Player.objects.get(user=user)
                    for key, value in player_data.items():
                        setattr(player, key, value)
                except Player.DoesNotExist:
                    player = Player(**player_data)

                player.full_clean()

                has_guardian = row["guardian.email"] and row["guardian.relation"]
                if player.is_minor and not has_guardian:
                    raise RuntimeError(f"Missing Guardian information for {email}")

                player.save()

                if has_guardian and not player.is_minor:
                    print(f"Ignoring guardian information for major: {email}")

                elif has_guardian and player.is_minor:
                    guardian_data = {
                        "first_name": row["guardian.first_name"],
                        "last_name": row["guardian.last_name"],
                        "email": row["guardian.email"],
                        "phone": row["guardian.phone"],
                    }
                    guardian_email = guardian_data["email"]
                    guardian_user, _ = User.objects.get_or_create(
                        username=guardian_email, email=guardian_email, defaults=guardian_data
                    )

                    relation = RELATIONS.get(row["guardian.relation"], None)
                    guardianship_data = {"relation": relation, "user": guardian_user}
                    try:
                        guardian = Guardianship.objects.get(player=player)
                        for key, value in guardianship_data.items():
                            setattr(guardian, key, value)
                    except Guardianship.DoesNotExist:
                        guardian = Guardianship(user=guardian_user, player=player, relation=relation)  # type: ignore[misc]
                        guardian.full_clean()

                    guardian.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully imported data for user {user.get_full_name()}"
                    )
                )
