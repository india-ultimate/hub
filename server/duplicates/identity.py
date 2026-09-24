"""Turning what people typed into something comparable.

Used by detection, by the merge and by sign in, so it holds no models and
imports nothing from the rest of the package."""

import re
import unicodedata

from django.template.defaultfilters import slugify

from server.utils import mask_string

# Only Gmail treats dots in the local part as insignificant.
DOTLESS_DOMAINS = frozenset({"gmail.com", "googlemail.com"})
PHONE_DIGITS = 10


def normalize_email(email: str) -> str:
    """Casefold, and drop dots for Gmail only.

    A +tag is kept. One adult often holds the accounts of several children -
    an NGO worker with worker+arjun@ and worker+meera@ - and the tag is the
    only thing telling those children apart. Dropping it collapsed all of
    them, and the adult, into one person. Dots are safe to fold because
    removing them keeps every distinguishing character; removing a tag does
    not. Someone who really does use a tag for a second account of their own
    still has the same name and birthday, which name+dob catches.
    """
    email = (email or "").strip().casefold()
    local, sep, domain = email.rpartition("@")
    if not sep:
        return email
    if domain in DOTLESS_DOMAINS:
        local = local.replace(".", "")
    return f"{local}@{domain}"


def normalize_phone(phone: str) -> str:
    """Last ten digits, collapsing +91, a leading 0 and any spacing."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-PHONE_DIGITS:] if len(digits) >= PHONE_DIGITS else ""


def _name_tokens(text: str) -> list[str]:
    """Accent-folded, lowercase words in any script.

    Letters, marks and digits are kept whatever the script: matching only
    [a-z0-9] turned a name typed in Devanagari or Tamil into nothing, and an
    empty name reads as no disagreement, which switched the name check off.
    """
    decomposed = unicodedata.normalize("NFKD", text or "")
    folded = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    return "".join(c if unicodedata.category(c)[0] in "LMN" else " " for c in folded).split()


def normalize_name(first_name: str, last_name: str) -> str:
    """Sorted, accent-folded, lowercase tokens, so a swapped order matches."""
    return " ".join(sorted(_name_tokens(f"{first_name or ''} {last_name or ''}")))


def name_slug(first_name: str, last_name: str) -> str:
    """The username register_ward and import_players fall back to."""
    return slugify(f"{first_name} {last_name}")


def mask_email(email: str) -> str:
    """Mask the local part, keep the domain: the half people recognise."""
    local, sep, domain = email.partition("@")
    return f"{mask_string(local)}@{domain}" if sep else mask_string(local)


# Above this, two names are one person's: for grouping and for keeping a
# group together. One number, so the two can never disagree.
NAME_SIMILARITY = 95


def names_agree(left: tuple[str, str], right: tuple[str, str]) -> bool:
    """Whether two (first, last) names can belong to one person.

    The same test decides a fuzzy match and a name mismatch. Held apart they
    contradict each other: a fuzzy match is two names that are not identical,
    which an equality test then reads as two different people, so every fuzzy
    cluster would be found and immediately refused.

    Only the surname may be spelled differently. The given name is what tells
    two people apart - Arun and Tarun, Ashwin and Ashwini - and a whole-name
    ratio cannot see that: a long shared surname dilutes a one-letter change
    to the given name until it scores 97. Those pairs are also what twins look
    like, so a given name has to match exactly.
    """
    from thefuzz import fuzz

    whole_left, whole_right = normalize_name(*left), normalize_name(*right)
    if whole_left == whole_right:
        return True
    given = _name_tokens(left[0])
    if not given or given != _name_tokens(right[0]):
        return False
    return fuzz.token_sort_ratio(whole_left, whole_right) >= NAME_SIMILARITY
