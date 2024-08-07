import csv
from io import StringIO
from pathlib import Path
from typing import Any

from server.core.models import Player

EMAIL_HEADER_NAME = "email"


def read_csv_with_emails(bank_statement: Path | StringIO) -> dict[str, dict[str, Any]] | None:
    with open(bank_statement) if isinstance(bank_statement, Path) else bank_statement as csvfile:
        # Skip empty lines at the beginning of the file
        seek = 0
        while True:
            line = csvfile.readline().strip()
            if line:
                headers = next(csv.reader(StringIO(line)))
                break
            else:
                seek += len(line) + 1

        csvfile.seek(seek)
        headers = [key.strip() for key in headers]
        if EMAIL_HEADER_NAME not in {key.lower() for key in headers}:
            return None

        email_header = next(key for key in headers if key.lower() == EMAIL_HEADER_NAME)
        reader = csv.DictReader(csvfile, skipinitialspace=True)
        data = {}

        for row_ in reader:
            email = row_[email_header].lower()
            row = {
                key.strip(): val.strip() if val is not None else ""
                for key, val in row_.items()
                if key is not None
            }

            data[email] = row

    return data


def get_membership_status(input_csv: Path | StringIO) -> dict[str, Any] | None:
    csv_data = read_csv_with_emails(input_csv)
    if csv_data is None:
        print(f"Could not find CSV header: {EMAIL_HEADER_NAME}")
        return None

    membership_statuses = dict(Player.objects.values_list("user__email", "membership__is_active"))

    for email, row in csv_data.items():
        row["membership_status"] = bool(membership_statuses.get(email, False))

    return csv_data
