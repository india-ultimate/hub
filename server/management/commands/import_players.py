import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandParser
from django.utils.text import slugify

from server.models import Accreditation, Guardianship, Player, UCPerson, User, Vaccination

GENDERS = {t.label: t for t in Player.GenderTypes}
STATE_UT = {t.label: t for t in Player.StatesUTs}
OCCUPATIONS = {t.label: t for t in Player.OccupationTypes}
RELATIONS = {t.label: str(t) for t in Guardianship.Relation}
ACCREDITATIONS = {t.label: str(t) for t in Accreditation.AccreditationLevel}
VACCINATIONS = {t.label: str(t) for t in Vaccination.VaccinationName}
DATE_FORMAT = "%Y-%m-%d"


class Command(BaseCommand):
    help = "Import data from CSV file and create Player and User objects"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
        parser.add_argument("--date-format", "-d", default=DATE_FORMAT, help="Date format used")
        parser.add_argument(
            "--guardian-email-optional",
            default=False,
            action="store_true",
            help="Make Guardian email an optional value",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        csv_file = options["csv_file"]
        certificate_dir = csv_file.parent.joinpath("certificates")
        vaccination_dir = csv_file.parent.joinpath("vaccinations")

        with open(csv_file) as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Process each row of the CSV file
                email = row["email"].strip().lower()
                user_data = {
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "email": email,
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

                guardian_email = row["guardian.email"].strip().lower()
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

                if row["uc.email"]:
                    try:
                        uc_person = UCPerson.objects.get(email=row["uc.email"].strip().lower())
                        player.ultimate_central_id = uc_person.id
                    except UCPerson.DoesNotExist:
                        pass

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

                # Import accreditation information
                accreditation_fields = ("date", "level", "wfdf_id")
                accreditation_data = {
                    field: row.get(f"accreditation.{field}") for field in accreditation_fields
                }
                has_accreditation_data = all(accreditation_data.values())
                doa = accreditation_data["date"]  # to make the type checker happy
                if has_accreditation_data and doa is not None:
                    accreditation_data["level"] = ACCREDITATIONS.get(
                        row["accreditation.level"], None
                    )
                    try:
                        acc_date = datetime.strptime(doa, options["date_format"])  # noqa: DTZ007
                        accreditation_data["date"] = acc_date.date()
                        accreditation_data["is_valid"] = True
                    except ValueError:
                        self.stderr.write(self.style.ERROR(f"Invalid date: {doa}"))
                        continue

                    certificate = self.find_certificate_file(row, certificate_dir)
                    if certificate:
                        accreditation_data["certificate"] = certificate
                        accreditation, created = Accreditation.objects.get_or_create(
                            player=player, defaults=accreditation_data
                        )
                        if not created:
                            for key, value in accreditation_data.items():
                                setattr(accreditation, key, value)
                            accreditation.save()
                    else:
                        print("Not creating accreditation: no certificate")

                # Import vaccination information
                has_vaccination_data = "vaccination.is_vaccinated" in row
                if has_vaccination_data:
                    is_vaccinated = row["vaccination.is_vaccinated"].upper() == "Y"
                    vaccination_data = (
                        {
                            "is_vaccinated": is_vaccinated,
                            "name": VACCINATIONS.get(row["vaccination.name"], None),
                        }
                        if is_vaccinated
                        else {
                            "is_vaccinated": is_vaccinated,
                            "explain_not_vaccinated": VACCINATIONS.get(
                                row["vaccination.explain_not_vaccinated"], "No explanation"
                            ),
                        }
                    )
                    filename, contents = self.find_vaccination_file(
                        row["vaccination.certificate_file_name"], vaccination_dir
                    )
                    if is_vaccinated and not filename:
                        self.stderr.write(self.style.ERROR(f"Missing vaccination file: {email}"))
                        continue
                    vaccination, created = Vaccination.objects.get_or_create(
                        player=player, defaults=vaccination_data
                    )
                    if not created:
                        for key, value in vaccination_data.items():
                            setattr(vaccination, key, value)
                        vaccination.save()
                    if filename and contents:
                        vaccination.certificate.save(filename, contents)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully imported data for user {user.get_full_name()}"
                    )
                )

    def find_certificate_file(
        self, row: dict[str, str], certificate_dir: Path
    ) -> ContentFile[bytes] | None:
        filename = row.get("accreditation.certificate_file_name")
        wfdf_id = row.get("accreditation.wfdf_id")

        if not filename and not wfdf_id:
            return None
        elif not filename:
            certificates = list(certificate_dir.glob(f"{wfdf_id}.*"))
            if not certificates:
                return None
            certificate_path = certificates[0]
            filename = certificate_path.name
        elif filename:
            certificate_path = certificate_dir.joinpath(filename)
            if not certificate_path.exists():
                return None

        with certificate_path.open("rb") as f:
            name = slugify(certificate_path.stem) + certificate_path.suffix
            return ContentFile(f.read(), name=name)

    def find_vaccination_file(
        self, filename: str, vaccination_dir: Path
    ) -> tuple[str | None, ContentFile[bytes] | None]:
        if not filename:
            return None, None
        else:
            vaccination_path = vaccination_dir.joinpath(filename)
            if not vaccination_path.exists():
                return None, None

        with vaccination_path.open("rb") as f:
            return filename, ContentFile(f.read())
