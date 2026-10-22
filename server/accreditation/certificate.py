import datetime
import re
import unicodedata
from typing import IO, NamedTuple

from server.accreditation.models import Accreditation
from server.core.models import User

# No \b at the ends: a value can run straight into the next label, as in
# "2 February 2028Date of Expiry:".
CODE = re.compile(r"(?<![0-9])[0-9]{10}[A-Z0-9]{2}(?![0-9])")
LEVEL = re.compile(r"(Standard|Advanced)\s+Accreditation")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE = re.compile(rf"(?<![0-9])[0-9]{{1,2}}\s+(?:{MONTHS})\s+[0-9]{{4}}(?![0-9])")


def name_words(name: str) -> set[str]:
    """The words of a name, without case or accents; initials don't count.

    "D'Souza" gives "dsouza" as well as "souza", so it matches either way
    it was typed.
    """
    plain = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    words = set()
    for word in re.split(r"[\s.,]+", plain.casefold()):
        words.add(re.sub(r"['\u2019-]", "", word))
        words.update(re.split(r"['\u2019-]", word))
    return {word for word in words if len(word) > 1}


class Certificate(NamedTuple):
    name: str
    code: str
    level: Accreditation.AccreditationLevel
    issued: datetime.date
    expires: datetime.date

    def is_for(self, user: User) -> bool:
        """Whether the name on it shares at least one word with the user's."""
        return bool(name_words(self.name) & name_words(f"{user.first_name} {user.last_name}"))


def read_certificate(pdf: IO[bytes]) -> Certificate | None:
    """The details on a WFDF Academy certificate, or None if it isn't one.

    pypdf reads the labels out apart from their values, so each value is
    found by its shape instead, and the earlier of the two dates is the
    date of issue. The name is the first line.
    """
    from pypdf import PdfReader

    try:
        pages = PdfReader(pdf).pages
        if len(pages) != 1:
            return None
        text = pages[0].extract_text()
        name = text.strip().split("\n")[0].strip()
        codes = set(CODE.findall(text))
        levels = set(LEVEL.findall(text))
        found = {" ".join(date.split()) for date in DATE.findall(text)}
        parsed = [datetime.datetime.strptime(d, "%d %B %Y") for d in found]  # noqa: DTZ007
        dates = sorted(d.date() for d in parsed)
    # Anything at all: the PDF is an upload, and pypdf raises more than its own errors.
    except Exception:
        return None

    if len(codes) != 1 or len(levels) != 1 or len(dates) != 2:  # noqa: PLR2004
        return None

    level = (
        Accreditation.AccreditationLevel.ADVANCED
        if levels == {"Advanced"}
        else Accreditation.AccreditationLevel.STANDARD
    )
    return Certificate(name, codes.pop(), level, dates[0], dates[1])
