"""Turn the ids the agent handles back into names, on the way out to staff.

The model is only ever given player ids, and writes `{{player:<id>}}` where it wants
to name someone (see `skills/spirit_and_roster.md`). This module is the one place
those tokens become names. It runs on serialization only: what is *stored* keeps the
raw token, because stored messages are replayed into model context, and a name that
reached this module must never travel back the other way.

Resolution is scoped to the tournament's own event, so a token the model invented
resolves to nothing rather than reading out an arbitrary row of the Player table.
"""

from __future__ import annotations

import re
from typing import Any

from server.tournament.models import Registration, Tournament
from server.tournament_agent.privacy.mask import ID_ONLY_KEYS

PLAYER_TOKEN_RE = re.compile(r"\{\{player:(\d+)\}\}")

# A trailing fragment that could still grow into a token once more text arrives:
# "{", "{{play", "{{player:81", "{{player:812}". Used to hold back the tail of a
# streamed chunk instead of flushing half a token to the browser.
PARTIAL_TOKEN_RE = re.compile(r"\{\{?p?l?a?y?e?r?:?\d*\}?$")


def _placeholder(player_id: str) -> str:
    return f"Player {player_id}"


def lookup_names(
    ids: set[str], tournament: Tournament, cache: dict[str, str] | None = None
) -> dict[str, str]:
    """id -> full name, for the players registered for this tournament's event."""
    wanted = {i for i in ids if cache is None or i not in cache}
    names: dict[str, str] = dict(cache or {})
    if not wanted:
        return names
    for reg in Registration.objects.filter(
        event=tournament.event, player_id__in=[int(i) for i in wanted]
    ).select_related("player__user"):
        names[str(reg.player_id)] = reg.player.user.get_full_name()
    # Anything not on this event's rosters stays a placeholder rather than being
    # looked up across the whole table.
    for i in wanted:
        names.setdefault(i, _placeholder(i))
    if cache is not None:
        cache.update(names)
    return names


def _collect_token_ids(value: Any, found: set[str]) -> None:
    if isinstance(value, str):
        found.update(PLAYER_TOKEN_RE.findall(value))
    elif isinstance(value, dict):
        for item in value.values():
            _collect_token_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_token_ids(item, found)


def _substitute(value: Any, names: dict[str, str]) -> Any:
    if isinstance(value, str):
        return PLAYER_TOKEN_RE.sub(lambda m: names.get(m[1], _placeholder(m[1])), value)
    if isinstance(value, dict):
        return {k: _substitute(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, names) for v in value]
    return value


def resolve_player_tokens(
    value: Any, tournament: Tournament, cache: dict[str, str] | None = None
) -> Any:
    """Replace every `{{player:<id>}}` in a JSON-like value with the player's name.

    Costs one query when a token is present anywhere in `value`, and none at all
    when there is not — which is the overwhelmingly common case, so this is cheap
    to apply blanket-fashion to whole payloads.
    """
    found: set[str] = set()
    _collect_token_ids(value, found)
    if not found:
        return value
    return _substitute(value, lookup_names(found, tournament, cache))


def _collect_person_ids(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in ID_ONLY_KEYS and isinstance(item, int | str):
                text = str(item)
                if text.isdigit():
                    found.add(text)
            _collect_person_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_person_ids(item, found)


def player_names_for_payload(payload: Any, tournament: Tournament) -> dict[str, str]:
    """id -> name for every person id in a proposal payload.

    Proposal payloads carry bare ids (`mvp_id`, `msp_id`) rather than tokens, because
    they are replayed into the applier verbatim. Serializing this alongside lets the
    card show a name without the payload itself ever holding one.
    """
    found: set[str] = set()
    _collect_person_ids(payload, found)
    return lookup_names(found, tournament) if found else {}


class TokenTextStream:
    """Resolve tokens in streamed text, across chunk boundaries.

    A token can arrive split over two deltas ("…{{play" / "er:812}} played well"),
    so anything that could still become one is held back until the next chunk or
    the final `flush`.
    """

    def __init__(self, tournament: Tournament) -> None:
        self._tournament = tournament
        self._buffer = ""
        self._cache: dict[str, str] = {}

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        partial = PARTIAL_TOKEN_RE.search(self._buffer)
        cut = partial.start() if partial else len(self._buffer)
        ready, self._buffer = self._buffer[:cut], self._buffer[cut:]
        return resolve_player_tokens(ready, self._tournament, self._cache)

    def flush(self) -> str:
        ready, self._buffer = self._buffer, ""
        return resolve_player_tokens(ready, self._tournament, self._cache)
