import logging
import os
from json import JSONDecodeError
from typing import Any

import requests

UPAI_BASE_URL = "https://upai.usetopscore.com/"
HTTP_SUCCESS = 200

logger = logging.getLogger(__name__)


class TopScoreClient:
    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        site_slug: str | None = None,
        per_page: int = 200,
    ) -> None:
        self.username = username
        self.password = password
        if username is None:
            self.authenticated = False

        if client_id is None:
            client_id = os.environ["TOPSCORE_CLIENT_ID"]
        self.client_id = client_id

        if client_secret is None:
            client_secret = os.environ["TOPSCORE_CLIENT_SECRET"]
        self.client_secret = client_secret

        if site_slug is None:
            site_slug = os.environ["TOPSCORE_SITE_SLUG"]
        self.site_url = f"https://{site_slug}.usetopscore.com"

        self.headers = None  # type: dict[str, str] | None
        self.per_page = per_page

    def refresh_access_token(self) -> None:
        data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
        }
        logger.debug("Fetching user access token")
        try:
            response = requests.post(f"{self.site_url}/api/oauth/server", data=data, timeout=15)
        except requests.exceptions.RequestException as e:
            logger.error("Failed to get access token: %s", e)
            return None

        if response.status_code != HTTP_SUCCESS:
            logger.error("Failed to get access token: Server returned %s", response.status_code)
            return None

        logger.info("Fetched access token")
        access_token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def get_person(self) -> dict[str, Any] | None:
        if self.headers is None:
            self.refresh_access_token()

        url = f"{self.site_url}/api/me"

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
        except requests.exceptions.RequestException as e:
            logger.error("Failed to get person_id: %s", e)
            return None

        if response.status_code != HTTP_SUCCESS:
            logger.error("Failed to get person_id: Server returned %s", response.status_code)
            return None

        try:
            info = response.json().get("result")
        except JSONDecodeError:
            logger.error("Failed to get person_id: Invalid JSON")
            return None

        if not info:
            logger.error("Failed to get person_id: No 'result' data")
            return None

        return info[0]

    def get_events(
        self, n: int | None = None, order_by: str = "date_desc"
    ) -> list[dict[str, Any]] | None:
        if n is None:
            n = self.per_page
        url = f"{self.site_url}/api/events?per_page={n}&order_by={order_by}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
        except requests.exceptions.RequestException as e:
            logger.error("Failed to get events: %s", e)
            return None

        if response.status_code != HTTP_SUCCESS:
            logger.error("Failed to get events: Server returned %s", response.status_code)
            return None

        data = response.json()
        count = min(data["count"], n)
        events = data["result"]
        if len(events) < count:
            print("WARNING: Need to add pagination")

        return events
