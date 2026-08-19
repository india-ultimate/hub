"""Load agent skills from markdown, selecting the ones relevant to this turn.

The markdown lives in `tournament_agent/skills/`, one file per skill — that is the
directory to add to, and nothing here needs changing to pick a new file up.

Each of those files starts with a YAML-ish front-matter block:

    ---
    name: live_progression
    status: active            # `draft` files are never loaded
    always: false             # true -> always in the prompt
    when_status: [LIV]        # Tournament.Status values this applies to
    triggers: [score, advance]
    requires_tools: [propose_match_score]
    priority: 20              # lower loads first when the budget is tight
    ---

Only the keys above are understood; the parser is deliberately tiny rather than a
YAML dependency, because the format is fixed and lives in this repo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# The markdown is package data, not a sibling of this loader: it sits at the top of
# `tournament_agent/` so the skills are findable without reading this file first.
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# Skills are dense; this caps how much of the context window they can take.
DEFAULT_BUDGET_CHARS = 32_000

_LIST_RE = re.compile(r"^\[(.*)\]$")


@dataclass
class Skill:
    name: str
    body: str
    status: str = "active"
    always: bool = False
    priority: int = 50
    when_status: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    requires_tools: list[str] = field(default_factory=list)


def _parse_value(raw: str) -> str | bool | int | list[str]:
    value = raw.strip()
    listed = _LIST_RE.match(value)
    if listed:
        return [item.strip() for item in listed.group(1).split(",") if item.strip()]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def _parse(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        # A skill without front-matter is always-on, so old files keep working.
        return Skill(name=path.stem, body=text, always=True)

    _, _, rest = text.partition("---")
    front, sep, body = rest.partition("---")
    if not sep:
        return None

    fields: dict[str, object] = {}
    pending_key: str | None = None
    buffer = ""
    for line in front.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if pending_key is None:
            key, _, raw = stripped.partition(":")
            pending_key, buffer = key.strip(), raw.strip()
        else:
            # A list may wrap over several lines; keep collecting until it closes.
            buffer = f"{buffer} {stripped}".strip()
        if not buffer:
            continue  # `key:` with the value on the following line(s)
        if buffer.startswith("[") and not buffer.endswith("]"):
            continue  # list still open
        fields[pending_key] = _parse_value(buffer)
        pending_key, buffer = None, ""

    known = {f: fields[f] for f in Skill.__dataclass_fields__ if f in fields}
    known.pop("body", None)
    return Skill(**{**known, "name": str(fields.get("name") or path.stem), "body": body.strip()})  # type: ignore[arg-type]


def load_skills(directory: Path | None = None) -> list[Skill]:
    skills = []
    for path in sorted((directory or SKILLS_DIR).glob("*.md")):
        skill = _parse(path)
        if skill and skill.status != "draft":
            skills.append(skill)
    return skills


def select_skills(
    skills: list[Skill],
    *,
    tournament_status: str,
    user_text: str = "",
    budget_chars: int = DEFAULT_BUDGET_CHARS,
) -> list[Skill]:
    """Pick the skills relevant to this turn, most relevant first.

    Ordering matters as much as selection: when the budget bites, what gets dropped
    should be the skill the turn did not ask for. A skill the staff member's own
    words invoked outranks one pulled in by tournament status alone.
    """
    text = user_text.lower()

    def relevance(skill: Skill) -> int | None:
        if skill.always:
            return 0
        if any(trigger.lower() in text for trigger in skill.triggers):
            return 1
        if skill.when_status and tournament_status in skill.when_status:
            return 2
        return None

    scored = [(rank, skill) for skill in skills if (rank := relevance(skill)) is not None]
    chosen = [
        skill for _rank, skill in sorted(scored, key=lambda rs: (rs[0], rs[1].priority, rs[1].name))
    ]

    kept: list[Skill] = []
    spent = 0
    for skill in chosen:
        if spent + len(skill.body) > budget_chars and not skill.always:
            continue
        kept.append(skill)
        spent += len(skill.body)
    return kept


def render_skills(skills: list[Skill]) -> str:
    return "\n\n".join(skill.body for skill in skills)
