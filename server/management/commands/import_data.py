import csv
import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils.regex_helper import _lazy_re_compile
from django.utils.text import slugify
from server.models import Guardian, Membership, Player, User, Vaccination

User = get_user_model()


date_re = _lazy_re_compile(r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})$")


def parse_date_custom(date_str):
    date = parse_date(date_str)
    if date is None:
        if match := date_re.match(date_str):
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
        with open(csv_file, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                row = {key.strip(): value.strip() for key, value in row.items()}
                email = row["Personal Email ID"]
                first_name = row["First/Given Name"]
                last_name = row["Last Name or Initial"]
                if not email.strip():
                    name = f"{first_name} {last_name}"
                    email = slugify(name)
                    print(f"Adding user with slugified username: {email}")

                # Create or get the User instance
                user, created = User.objects.get_or_create(
                    username=email,
                    defaults={
                        "email": email,
                        "phone": row["Personal Phone Number"],
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
                    date_of_birth=parse_date_custom(row["Date of Birth"]),
                    gender=row["Gender"],
                    city=row["City"],
                    state_ut=row["State / UT (in India)"],
                    team_name=row["Team Name / Association to India Ultimate"],
                    occupation=row["Occupation"],
                    india_ultimate_profile=row[
                        "Please add the link (URL) to your www.indiaultimate.org Profile here"
                    ],
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
                    is_annual=row["Type of UPAI Membership"] == "Full Member (INR 600/person)",
                    start_date="2022-04-01",  # FIXME: Check with Ops Team
                    end_date="2022-03-31",  # FIXME: Check with Ops Team
                    is_active=False,
                )

                # Create the Vaccination instance
                is_vaccinated = row["Are you fully vaccinated against Covid-19?"] == "Yes"
                explanation_key = "Please give an explanation to your selected reasons for not being vaccinated against Covid-19"
                reason = row["Please select/mention your reasons"]
                explanation = f"{reason}\n{row[explanation_key]}".strip()
                certificate = row["Upload your final (full) vaccination Certificate here"]
                vaccination = Vaccination.objects.create(
                    player=player,
                    is_vaccinated=is_vaccinated,
                    vaccination_name=row["Name of the vaccination"],
                    explain_not_vaccinated=explanation,
                    # FIXME: Actually upload the image and store the ID/path?
                    # vaccination_certificate = certificate,
                )

                self.stdout.write(self.style.SUCCESS("Data imported successfully."))
