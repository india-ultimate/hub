import json
import logging
from typing import NamedTuple

import jwt
import requests
from django.conf import settings

BASE_URL = "https://passkeys.hanko.io/"
HTTP_SUCCESS = 200

logger = logging.getLogger(__name__)


class ClientResponse(NamedTuple):
    data: str = ""
    error: str = ""
    user_id: str = ""


class PassKeyClient:
    def __init__(self) -> None:
        self.api_key = settings.PASSKEY_SECRET_API_KEY
        self.url = f"{BASE_URL}{settings.PASSKEY_TENANT_ID}"
        self.headers = {"apiKey": self.api_key, "Content-Type": "application/json"}

    def start_registration(self, user_id: str, username: str) -> ClientResponse:
        data = {
            "user_id": user_id,
            "username": username,
        }

        try:
            response = requests.post(
                f"{self.url}/registration/initialize",
                headers=self.headers,
                data=json.dumps(data),
                timeout=15,
            )
        except requests.exceptions.RequestException as e:
            logger.error("Failed to initialise passkey: %s", e)
            return ClientResponse(error="Failed to initialise passkey")

        if response.status_code != HTTP_SUCCESS:
            logger.error(
                "Failed to initialise passkey: Hanko returned %s with error: %s",
                response.status_code,
                response.text,
            )
            return ClientResponse(error="Failed to initialise passkey")

        return ClientResponse(data=json.dumps(response.json()))

    def finish_registration(self, body: str) -> ClientResponse:
        try:
            response = requests.post(
                f"{self.url}/registration/finalize", headers=self.headers, data=body, timeout=15
            )
        except requests.exceptions.RequestException as e:
            logger.error("Failed to finalize passkey: %s", e)
            return ClientResponse(error="Failed to finalize passkey")

        if response.status_code != HTTP_SUCCESS:
            logger.error(
                "Failed to finalize passkey: Hanko returned %s with error: %s",
                response.status_code,
                response.text,
            )
            return ClientResponse(error="Failed to finalize passkey")

        return ClientResponse(data=json.dumps(response.json()))

    def start_login(self) -> ClientResponse:
        try:
            response = requests.post(
                f"{self.url}/login/initialize", headers=self.headers, timeout=15
            )
        except requests.exceptions.RequestException as e:
            logger.error("Failed to initialise login passkey: %s", e)
            return ClientResponse(error="Failed to initialise login passkey")

        if response.status_code != HTTP_SUCCESS:
            logger.error(
                "Failed to initialise login passkey: Hanko returned %s with error: %s",
                response.status_code,
                response.text,
            )
            return ClientResponse(error="Failed to initialise login passkey")

        return ClientResponse(data=json.dumps(response.json()))

    def finish_login(self, body: str) -> ClientResponse:
        try:
            response = requests.post(
                f"{self.url}/login/finalize", headers=self.headers, data=body, timeout=15
            )
        except requests.exceptions.RequestException as e:
            logger.error("Failed to finalize login passkey: %s", e)
            return ClientResponse(error="Failed to finalize login passkey")

        if response.status_code != HTTP_SUCCESS:
            logger.error(
                "Failed to finalize login passkey: Hanko returned %s with error: %s",
                response.status_code,
                response.text,
            )
            return ClientResponse(error="Failed to finalize login passkey")

        data = response.json()
        decoded = jwt.decode(data["token"], options={"verify_signature": False})

        return ClientResponse(user_id=decoded["sub"], data=json.dumps(response.json()))
