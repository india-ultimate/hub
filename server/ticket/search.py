"""Ranked word search over ticket titles and descriptions.

Each word scores 2 when it is in the title and 1 when it is in the
description. icontains keeps partial words matching ("subscr" finds
"subscription"), which the create page's suggestions rely on, and it behaves
the same on Postgres and on SQLite under the tests.
"""

import re

from django.db.models import Case, Expression, IntegerField, QuerySet, Value, When

from server.ticket.models import Ticket

# Words so common they would match nearly every ticket.
FILLER = frozenset(
    "the and for with not can cant but are was has have this that from you your "
    "our how why what when where who its all any get got".split()
)
MAX_WORDS = 8
MIN_LENGTH = 3


def search_words(q: str) -> list[str]:
    """The distinct words of `q` worth searching for, in order, at most 8."""
    words: list[str] = []
    for word in re.split(r"[\W_]+", q.lower()):
        if len(word) >= MIN_LENGTH and word not in FILLER and word not in words:
            words.append(word)
    return words[:MAX_WORDS]


def ranked(tickets: QuerySet[Ticket], words: list[str]) -> QuerySet[Ticket]:
    """`tickets` matching at least one of `words`, each with a `score`."""
    # ponytail: an unindexed icontains scan per word, fine at a few thousand
    # tickets; add pg_trgm GIN indexes on title and description if it slows.
    score: Expression = Value(0)
    for word in words:
        score = (
            score
            + Case(
                When(title__icontains=word, then=Value(2)),
                default=Value(0),
                output_field=IntegerField(),
            )
            + Case(
                When(description__icontains=word, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    return tickets.annotate(score=score).filter(score__gt=0)
