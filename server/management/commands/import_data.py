import csv
import datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date
from django.utils.regex_helper import _lazy_re_compile
from django.utils.text import slugify
from server.models import Guardian, Membership, Player, User, Vaccination

User = get_user_model()


DATE_RE = _lazy_re_compile(r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})$")


ADULTS_COLUMNS = {
    # User
    "email": "Personal Email ID",
    "phone": "Personal Phone Number",
    # Player
    "first_name": "First/Given Name",
    "last_name": "Last Name or Initial",
    "dob": "Date of Birth",
    "gender": "Gender",
    "city": "City",
    "state_ut": "State / UT (in India)",
    "team_name": "Team Name / Association to India Ultimate",
    "occupation": "Occupation",
    "india_ultimate_profile": "Please add the link (URL) to your www.indiaultimate.org Profile here",
    # Guardian
    # Membership
    "membership_type": "Type of UPAI Membership",
    # Vaccination
    "is_vaccinated": "Are you fully vaccinated against Covid-19?",
    "vaccination_name": "Name of the vaccination",
    "not_vaccinated_reason": "Please select/mention your reasons",
    "not_vaccinated_explanation": "Please give an explanation to your selected reasons for not being vaccinated against Covid-19",
    "certificate": "Upload your final (full) vaccination Certificate here",
}


MINORS_COLUMNS = {
    # User
    "phone": "Personal  phone number of the Minor",
    # Player
    "first_name": "First/Given Name of Minor",
    "last_name": "Last Name or Initial of Minor",
    "dob": "Date of Birth of the Minor",
    "gender": "Gender of the Minor",
    "city": "City of residence of the Minor",
    "state_ut": "State / UT (in India)",
    "team_name": "Name of the Club/College the Minor is associated with/ association of the Minor with Indian Ultimate",
    "occupation": "Occupation",
    "educational_institution": "Name of the educational institution the Minor is associated with",
    "india_ultimate_profile": "Please add the link to your son/ daughter or ward's  www.indiaultimate.org Profile here",
    # Guardian
    "guardian_email": "Personal Email ID of the parent/ guardian",
    "guardian_phone": "Personal Phone Number of the parent/ guardian",
    "guardian_name": "Name of parent/ guardian of the Minor",
    "guardian_relation": "Relationship with the minor",
    # Membership
    "membership_type": "Type of UPAI Membership you are opting for your son/ daughter or ward",
    # Vaccination
    "is_vaccinated": "Is your son/ daughter or ward fully vaccinated against Covid-19?",
    "vaccination_name": "Name of the Vaccination",
    "not_vaccinated_reason": "If your son/ daughter or ward is NOT Vaccinated, please share reasons below",
    "certificate": "Upload the final (full) vaccination Certificate of your son/ daughter or ward (if applicable)",
}


def parse_date_custom(date_str):
    date = parse_date(date_str)
    if date is None:
        if match := DATE_RE.match(date_str):
            kw = {k: int(v) for k, v in match.groupdict().items()}
            return datetime.date(**kw)
    return None


class Command(BaseCommand):
    help = "Import data from CSV"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
        parser.add_argument(
            "--minors",
            action="store_true",
            default=False,
            help="Specify that the CSV file has data for minors",
        )
        parser.add_argument(
            "--gdrive-map-csv",
            type=Path,
            help="Path to CSV file mapping downloaded file paths to GDrive IDs",
        )
        parser.add_argument(
            "--download-path", type=Path, help="Path of parent directory containing downloaded data"
        )

    def handle(self, *args, **options):
        gdrive_map_csv = options["gdrive_map_csv"]
        download_path = options["download_path"]
        gdrive_map = {}
        if not gdrive_map_csv and not download_path:
            self.stdout.write(self.style.WARNING("Not uploading any media files."))
        elif not gdrive_map_csv or not download_path:
            raise CommandError(f"Please set both --gdrive-map-csv and --download-path.")
        else:
            with gdrive_map_csv.open("r") as file:
                reader = csv.DictReader(file)
                gdrive_map = {row["File ID"]: download_path / row["File Path"] for row in reader}

        minors = options["minors"]
        csv_file = options["csv_file"]
        columns = MINORS_COLUMNS if minors else ADULTS_COLUMNS
        if not csv_file.exists():
            raise CommandError(f"'{csv_file}' does not exist.")
        with csv_file.open("r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                row = {key.strip(): value.strip() for key, value in row.items()}
                email = row[columns["email"]] if not minors else ""
                first_name = row[columns["first_name"]]
                last_name = row[columns["last_name"]]
                if not email.strip():
                    name = f"{first_name} {last_name}"
                    email = slugify(name)
                    print(f"Adding user with slugified username: {email}")

                # Create or get the User instance
                user, created = User.objects.get_or_create(
                    username=email,
                    defaults={
                        "email": email,
                        "phone": row[columns["phone"]],
                        "is_player": not minors,
                        "is_guardian": False,
                    },
                )

                if not created:
                    # Use the data from the first available row
                    continue

                # Create the Player instance
                player = Player.objects.create(
                    user=user,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=parse_date_custom(row[columns["dob"]]),
                    gender=row[columns["gender"]],
                    city=row[columns["city"]],
                    state_ut=row[columns["state_ut"]],
                    team_name=row[columns["team_name"]],
                    occupation=row[columns["occupation"]] if not minors else None,
                    educational_institution=row[columns["educational_institution"]]
                    if minors
                    else None,
                    # FIXME: Do we need a URL here? Or the ID? Can we get the
                    # ID using an API from the URL?
                    india_ultimate_profile=row[columns["india_ultimate_profile"]],
                )

                # Create or get the Guardian instance if applicable
                if minors:
                    guardian_email = row[columns["guardian_email"]]
                    guardian_name = row[columns["guardian_name"]]
                    if not guardian_email:
                        guardian_email = slugify(guardian_name)
                    guardian_user, created = User.objects.get_or_create(
                        username=guardian_email,
                        defaults={
                            "email": guardian_email,
                            "phone": row[columns["guardian_phone"]],
                            "is_guardian": True,
                        },
                    )
                    guardian, _ = Guardian.objects.get_or_create(
                        user=guardian_user,
                        defaults={
                            "full_name": guardian_name,
                            "relation": row[columns["guardian_relation"]],
                        },
                    )
                    player.guardian = guardian
                    player.save()

                # Create the Membership instance
                membership = Membership.objects.create(
                    player=player,
                    is_annual=row[columns["membership_type"]] == "Full Member (INR 600/person)",
                    start_date="2022-04-01",
                    end_date="2022-03-31",
                    is_active=False,
                )

                # Create the Vaccination instance
                is_vaccinated = row[columns["is_vaccinated"]] == "Yes"
                reason = row[columns["not_vaccinated_reason"]]
                if minors:
                    explanation = reason
                else:
                    explanation = row[columns["not_vaccinated_explanation"]]
                    explanation = f"{reason}\n{explanation}".strip()
                vaccination = Vaccination.objects.create(
                    player=player,
                    is_vaccinated=is_vaccinated,
                    vaccination_name=row[columns["vaccination_name"]],
                    explain_not_vaccinated=explanation,
                )
                certificate_url = row[columns["certificate"]]
                name, content = self.find_vaccination_file(certificate_url, gdrive_map)
                if name and content:
                    vaccination.vaccination_certificate.save(name, content)
                uploading_media = bool(name)

                msg = (
                    "Data imported successfully."
                    if uploading_media
                    else "Data imported successfully (without media)."
                )
                self.stdout.write(self.style.SUCCESS(msg))

    def find_vaccination_file(self, url, gdrive_map):
        if not url:
            return None, None
        drive_id = url.split("=")[1]
        if drive_id not in gdrive_map:
            return drive_id, None
        path = gdrive_map[drive_id]
        with path.open("rb") as f:
            name = slugify(path.stem) + path.suffix
            return name, ContentFile(f.read())
