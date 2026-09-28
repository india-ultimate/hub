"""A receipt's table: one row per item bought at one price."""

from typing import Any

Row = dict[str, Any]


def person_label(first: str, last: str, username: str, iu_id: str | None) -> str:
    name = f"{first} {last}".strip() or username
    return f"{name} ({iu_id})" if iu_id else name


def group(items: list[tuple[str, str | None, int, int]]) -> list[Row]:
    """items are (particulars, person, amount, line id), one per line of an
    order. `line_ids` runs parallel to `people`, so a refund of one line can
    find its person on the row even if the player is later renamed."""
    grouped: dict[tuple[str, int], Row] = {}
    for particulars, person, amount, line_id in items:
        row = grouped.setdefault(
            (particulars, amount),
            {
                "particulars": particulars,
                "people": [],
                "line_ids": [],
                "quantity": 0,
                "rate": amount,
                "amount": 0,
            },
        )
        if person:
            row["people"].append(person)
            row["line_ids"].append(line_id)
        row["quantity"] += 1
        row["amount"] += amount
    return list(grouped.values())


def legacy_row(season_name: str | None, people: list[str], total: int) -> Row:
    """An order from before per-person amounts: one row for all of it."""
    quantity = max(len(people), 1)
    return {
        "particulars": f"Subscription, {season_name}" if season_name else "Subscription",
        "people": people,
        "quantity": quantity,
        "rate": total // quantity if total % quantity == 0 else None,
        "amount": total,
    }


def summary(rows: list[Row]) -> str:
    """One line for a list: "Regular Subscription x 2 — Season 2026-2027"."""
    items, seasons = [], set()
    for row in rows:
        item, _, season = row["particulars"].partition(", ")
        items.append(f"{item} × {row['quantity']}")  # noqa: RUF001
        seasons.add(season)
    text = ", ".join(items)
    if len(seasons) == 1 and "" not in seasons:
        text += f" — {seasons.pop()}"
    return text
