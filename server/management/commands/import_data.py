import csv
import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
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
    # Parent
    # Membership
    "membership_type": "Type of UPAI Membership",
    # Vaccination
    "is_vaccinated": "Are you fully vaccinated against Covid-19?",
    "vaccination_name": "Name of the vaccination",
    "not_vaccinated_reason": "Please select/mention your reasons",
    "not_vaccinated_explanation": "Please give an explanation to your selected reasons for not being vaccinated against Covid-19",
    "certificate": "Upload your final (full) vaccination Certificate here",
}


MINORS_COLUMNS = {}


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
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")
        parser.add_argument(
            "--minors",
            action="store_true",
            default=False,
            help="Specify that the CSV file has data for minors",
        )

    def handle(self, *args, **options):
        minors = options["minors"]
        csv_file = options["csv_file"]
        columns = MINORS_COLUMNS if minors else ADULTS_COLUMNS
        with open(csv_file, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                row = {key.strip(): value.strip() for key, value in row.items()}
                email = row[columns["email"]]
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
                    occupation=row[columns["occupation"]],
                    # FIXME: Do we need a URL here? Or the ID? Can we get the
                    # ID using an API from the URL?
                    india_ultimate_profile=row[columns["india_ultimate_profile"]],
                )

                # Create or get the Guardian instance if applicable
                if minors:
                    guardian_user, _ = User.objects.get_or_create(
                        username=row["guardian_username"],
                        defaults={
                            "email": row["guardian_email"],
                            "phone": row["guardian_phone_number"],
                            "is_guardian": True,
                        },
                    )
                    guardian = Guardian.objects.create(
                        user=guardian_user,
                        first_name=row["guardian_first_name"],
                        last_name=row["guardian_last_name"],
                    )
                    player.guardian = guardian
                    player.save()

                # Create the Membership instance
                membership = Membership.objects.create(
                    player=player,
                    is_annual=row[columns["membership_type"]] == "Full Member (INR 600/person)",
                    start_date="2022-04-01",  # FIXME: Check with Ops Team
                    end_date="2022-03-31",  # FIXME: Check with Ops Team
                    is_active=False,
                )

                # Create the Vaccination instance
                is_vaccinated = row[columns["is_vaccinated"]] == "Yes"
                reason = row[columns["not_vaccinated_reason"]]
                explanation = row[columns["not_vaccinated_explanation"]]
                explanation = f"{reason}\n{explanation}".strip()
                certificate = row[columns["certificate"]]
                vaccination = Vaccination.objects.create(
                    player=player,
                    is_vaccinated=is_vaccinated,
                    vaccination_name=row[columns["vaccination_name"]],
                    explain_not_vaccinated=explanation,
                    # FIXME: Actually upload the image and store the ID/path?
                    # vaccination_certificate = certificate,
                )

                self.stdout.write(self.style.SUCCESS("Data imported successfully."))
