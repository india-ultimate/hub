import re
import shutil
from pathlib import Path
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


def create_empty_directory(directory_path: Path) -> None:
    shutil.rmtree(directory_path, ignore_errors=True)
    directory_path.mkdir(exist_ok=True)


def get_otp_from_email_logs(directory_path: Path) -> str:
    files = list(directory_path.glob("*"))

    if not files:
        raise ValueError("File not found")

    html_content = files[0].read_text()

    # Use regular expression to find content between <strong> tags
    strong_contents = re.findall(
        r'<strong style="font-size: 130%">(.*?)</strong>', html_content, re.DOTALL
    )

    return strong_contents[0]
