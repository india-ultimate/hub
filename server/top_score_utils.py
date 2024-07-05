import logging
import os
from json import JSONDecodeError
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

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
        per_page: int = 500,
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
            headers = {
                "User-Agent": "Python:hub (by /fly)",
            }
            response = requests.post(
                f"{self.site_url}/api/oauth/server", json=data, headers=headers, timeout=15
            )
        except requests.exceptions.RequestException as e:
            logger.error("Failed to get access token: %s", e)
            return None

        if response.status_code != HTTP_SUCCESS:
            logger.error(
                "Failed to get access token: Server returned %s, error: %s",
                response.status_code,
                response.text,
            )
            return None

        logger.info("Fetched access token")
        access_token = response.json()["access_token"]
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Python:hub (by /fly)",
        }

    def get_person(self) -> dict[str, Any] | None:
        if self.headers is None:
            self.refresh_access_token()

        url = f"{self.site_url}/api/me"
        data = self._request(url)
        if data is None:
            logger.error("Failed to events")
            return None

        info = data.get("result")
        if not info:
            logger.error("Failed to get person_id: No 'result' data")
            return None

        return info[0]

    def get_events(
        self,
        n: int | None = None,
        order_by: str = "date_desc",
        fields: str = "Location",
    ) -> list[dict[str, Any]] | None:
        url = f"{self.site_url}/api/events?order_by={order_by}"
        for each in fields.split(","):
            url += f"&fields[]={each}"
        events = self._paginated_request(url, n)
        if events is None:
            logger.error("Failed to fetch events")
        return events

    def get_registrations(
        self,
        event_id: int,
        fields: str = "Person,Team",
        n: int | None = None,
        order_by: str = "date_desc",
    ) -> list[dict[str, Any]] | None:
        if self.headers is None:
            self.refresh_access_token()
        url = f"{self.site_url}/api/registrations?event_id={event_id}"
        for each in fields.split(","):
            url += f"&fields[]={each}"
        registrations = self._paginated_request(url, n)
        if registrations is None:
            logger.error("Failed to fetch events")
        return registrations

    def _request(self, url: str) -> Any | None:
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
        except requests.exceptions.RequestException as e:
            logger.error("Failed to get data: %s", e)
            return None

        if response.status_code != HTTP_SUCCESS:
            logger.error(
                "Failed to get data: Server returned %s, error: %s",
                response.status_code,
                response.text,
            )
            return None

        try:
            data = response.json()
        except JSONDecodeError:
            logger.error("Failed to get person_id: Invalid JSON")
            return None

        return data

    def _paginated_request(self, url: str, page_size: int | None = None) -> Any | None:
        if page_size is None:
            page_size = self.per_page

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        qs["per_page"] = [str(page_size)]

        page = 1
        all_results = []
        while True:
            qs["page"] = [str(page)]
            q = urlencode(qs, doseq=True)
            url = urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, q, parsed.fragment)
            )
            data = self._request(url)
            if data is None:
                return data

            results = data["result"]
            all_results.extend(results)
            n = len(all_results)
            count = data.get("count", n)
            if n < count:
                page += 1
            else:
                return all_results
