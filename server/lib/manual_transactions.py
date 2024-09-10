import csv
from io import StringIO
from pathlib import Path
from typing import Any

from server.transaction.models import ManualTransaction


def read_bank_statement(bank_statement: Path | StringIO) -> dict[str, Any]:
    data = {}
    with open(bank_statement) if isinstance(bank_statement, Path) else bank_statement as csvfile:
        # Skip empty lines at the beginning of the file
        seek = 0
        while True:
            line = csvfile.readline()
            if line.strip():
                break
            else:
                seek += len(line) + 1

        csvfile.seek(seek)

        reader = csv.DictReader(csvfile, skipinitialspace=True)
        for row_ in reader:
            row = {
                key.strip(): val.strip() if val is not None else ""
                for key, val in row_.items()
                if key is not None
            }
            reference_number = row["Chq/Ref Number"].lstrip(
                "0"
            )  # FIXME: Should we strip the DC chars on the right?
            credit_amount = float(row["Credit Amount"])
            data[reference_number] = credit_amount

    return data


def validate_manual_transactions(bank_statement: Path | StringIO) -> dict[str, int]:
    bank_statement_data = read_bank_statement(bank_statement)
    total = len(bank_statement_data)
    validated = invalid_found = 0

    for transaction in ManualTransaction.objects.filter(validated=False):
        tid = transaction.transaction_id.lstrip("0")

        if tid in bank_statement_data:
            invalid_found += 1
            bank_amount = bank_statement_data[tid]  # Amount in rupees (float)
            user_amount = transaction.amount  # Amount in paise
            if bank_amount * 100 == user_amount:
                transaction.validated = True
                transaction.save(update_fields=["validated"])
                validated += 1

    return {"total": total, "invalid_found": invalid_found, "validated": validated}
