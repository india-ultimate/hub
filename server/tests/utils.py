import re
from typing import Any

import zulip


class EmailLinkFound(Exception):  # noqa: N818
    def __init__(self, link: str) -> None:
        self.link = link


def zulip_get_email_link() -> str:
    client = zulip.Client()
    try:
        client.call_on_each_message(_find_sign_up_link)
    except EmailLinkFound as e:
        return e.link
    return ""


def _find_sign_up_link(message: dict[str, Any]) -> None:
    email = "From: noreply@india-ultimate-hub.firebaseapp.com"
    if not message["content"].startswith(email):
        return
    content = message["content"].replace("\n", "")
    if match := re.search(r"\((https://.*)\)", content):
        link = match.group(1)
        raise EmailLinkFound(link)
    return
