import hashlib
import logging
import re
from datetime import datetime
from typing import Any

import requests
from django.conf import settings

from server.core.models import User

HTTP_SUCCESS = 200
HTTP_UNPROCESSABLE_ENTITY = 422
MIN_NAME_PARTS_FOR_FULL_NAME = 2

logger = logging.getLogger(__name__)


def _get_flarum_base_url() -> str:
    """Get Flarum base URL from settings or environment variable."""
    return getattr(settings, "FLARUM_BASE_URL", "")


def _get_flarum_api_key() -> str:
    """Get Flarum API key from settings or environment variable."""
    return getattr(settings, "FLARUM_API_KEY", "")


def _get_api_key_headers(user_id: int | None = None) -> dict[str, str]:
    """
    Get headers with API key authentication.

    Args:
        user_id: Optional user ID to act as. If None, only the API key is used.

    Returns:
        Dictionary with Authorization header
    """
    api_key = _get_flarum_api_key()
    if not api_key:
        return {}

    auth_header = f"Token {api_key}"
    if user_id is not None:
        auth_header += f"; userId={user_id}"

    return {"Authorization": auth_header}


def _encode_timestamp_to_password(timestamp: datetime) -> str:
    """
    Encode a timestamp into a password string.

    Uses SHA256 hash of the ISO format timestamp string to create a deterministic password.
    """
    timestamp_str = timestamp.isoformat()
    hash_obj = hashlib.sha256(timestamp_str.encode())
    return hash_obj.hexdigest()[:40]  # Use first 40 characters for password


def _generate_username_from_full_name(full_name: str, suffix: int | None = None) -> str:
    """
    Generate a username from full name by removing spaces, special characters, and numbers.

    Args:
        full_name: Full name (e.g., "John Doe" or "First Last")
        suffix: Optional numeric suffix to append (for retries)

    Returns:
        Generated username (e.g., "JohnDoe" or "JohnDoe1")
    """
    # Split into parts and take first and last
    parts = full_name.strip().split()
    if not parts:
        return "user"

    # Take first and last name if available, otherwise just first
    if len(parts) >= MIN_NAME_PARTS_FOR_FULL_NAME:
        first_name = parts[0]
        last_name = parts[-1]
    else:
        first_name = parts[0]
        last_name = ""

    # Remove all non-alphabetic characters and convert to lowercase
    first_clean = re.sub(r"[^a-zA-Z]", "", first_name).lower()
    last_clean = re.sub(r"[^a-zA-Z]", "", last_name).lower()

    # Combine first and last name
    username = first_clean + last_clean if last_clean else first_clean

    # If username is empty after cleaning, use a default
    if not username:
        username = "user"

    # Append suffix if provided
    if suffix is not None:
        username = f"{username}{suffix}"

    return username


def _is_username_taken_error(response: requests.Response) -> bool:
    """
    Check if the response indicates a username already taken error.

    Args:
        response: HTTP response object

    Returns:
        True if username is already taken, False otherwise
    """
    if response.status_code != HTTP_UNPROCESSABLE_ENTITY:
        return False

    try:
        error_data = response.json()
        errors = error_data.get("errors", [])
        for error in errors:
            if error.get("code") == "validation_error":
                source = error.get("source", {})
                pointer = source.get("pointer", "")
                if "/data/attributes/username" in pointer:
                    detail = error.get("detail", "").lower()
                    if "username" in detail and ("taken" in detail or "already" in detail):
                        return True
    except (ValueError, KeyError):
        pass

    return False


def get_flarum_token(identification: str, creation_timestamp: datetime) -> dict[str, Any] | None:
    """
    Get a session_remember access token from Flarum API.

    Args:
        identification: Username or email for authentication
        creation_timestamp: Timestamp when the user was created (used to generate password)

    Returns:
        Dictionary with 'token' and 'userId' keys, or None if request fails
    """
    base_url = _get_flarum_base_url()
    if not base_url:
        logger.error("FLARUM_BASE_URL not configured")
        return None

    api_key = _get_flarum_api_key()
    if not api_key:
        logger.error("FLARUM_API_KEY not configured")
        return None

    # Generate password from timestamp
    password = _encode_timestamp_to_password(creation_timestamp)

    url = f"{base_url}/api/token"
    data = {
        "identification": identification,
        "password": password,
        "remember": 1,  # Request session_remember token (expires after 5 years)
    }

    headers = _get_api_key_headers(1)

    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        logger.error("Failed to get Flarum access token: %s", e)
        return None

    if response.status_code != HTTP_SUCCESS:
        logger.error(
            "Failed to get Flarum access token: Server returned %s, error: %s",
            response.status_code,
            response.text,
        )
        return None

    try:
        result = response.json()
        logger.info("Successfully obtained Flarum access token")
        return result
    except ValueError as e:
        logger.error("Failed to parse Flarum token response: %s", e)
        return None


def create_flarum_user(user: User) -> dict[str, Any] | None:
    """
    Create a user in Flarum.

    Generates username from full name by removing spaces, special characters, and numbers.
    If username is already taken, appends a number and retries up to 5 times.
    Stores the Flarum user ID in the User model's forum_id field.

    Args:
        user: User instance to create in Flarum

    Returns:
        Dictionary with user data, or None if request fails
    """
    base_url = _get_flarum_base_url()
    if not base_url:
        logger.error("FLARUM_BASE_URL not configured")
        return None

    # Extract user information
    full_name = user.get_full_name()
    email = user.username
    creation_timestamp = user.date_joined

    # Generate password from timestamp
    password = _encode_timestamp_to_password(creation_timestamp)

    api_key = _get_flarum_api_key()
    if not api_key:
        logger.error("FLARUM_API_KEY not configured")
        return None

    url = f"{base_url}/api/users"
    headers = _get_api_key_headers(1)

    # Try creating user with generated username, retry with suffix if username is taken
    max_retries = 5
    for attempt in range(max_retries):
        # Generate username (with suffix for retries)
        suffix = None if attempt == 0 else attempt
        username = _generate_username_from_full_name(full_name, suffix=suffix)

        data = {
            "data": {
                "attributes": {
                    "username": username,
                    "email": email,
                    "password": password,
                }
            }
        }

        try:
            response = requests.post(url, json=data, headers=headers, timeout=15)
        except requests.exceptions.RequestException as e:
            logger.error("Failed to create Flarum user: %s", e)
            return None

        # Success case
        if response.status_code in (200, 201):
            try:
                result = response.json()
                flarum_user_id = result.get("data", {}).get("id")

                # Store Flarum user ID in User model
                if flarum_user_id:
                    try:
                        user.forum_id = int(flarum_user_id)
                        user.save(update_fields=["forum_id"])
                        logger.info(
                            "Stored Flarum user ID %s in User.forum_id for user %s",
                            flarum_user_id,
                            user.username,
                        )
                    except (ValueError, AttributeError) as e:
                        logger.warning("Failed to store Flarum user ID in User model: %s", e)

                logger.info(
                    "Successfully created Flarum user: %s (username: %s, id: %s)",
                    full_name,
                    username,
                    flarum_user_id,
                )
                return result
            except ValueError as e:
                logger.error("Failed to parse Flarum user creation response: %s", e)
                return None

        # Check if username is already taken
        if _is_username_taken_error(response):
            if attempt < max_retries - 1:
                logger.debug(
                    "Username '%s' already taken, retrying with suffix %s",
                    username,
                    attempt + 1,
                )
                continue
            else:
                logger.error(
                    "Failed to create Flarum user: Username conflict after %d attempts. Last error: %s",
                    max_retries,
                    response.text,
                )
                return None

        # Other error (not username conflict)
        logger.error(
            "Failed to create Flarum user: Server returned %s, error: %s",
            response.status_code,
            response.text,
        )
        return None

    # Should not reach here, but just in case
    logger.error("Failed to create Flarum user after %d attempts", max_retries)
    return None


def create_flarum_discussion(
    title: str,
    content: str,
    tag_ids: list[int] | None = None,
    user_id: int = 1,
) -> str | None:
    """
    Create a discussion in Flarum.

    Args:
        title: Title of the discussion
        content: Content/body of the first post in the discussion
        tag_ids: Optional list of tag IDs to associate with the discussion
        user_id: User ID to create the discussion as (default: 1)

    Returns:
        Discussion ID as string if successful, None if request fails
    """
    base_url = _get_flarum_base_url()
    if not base_url:
        logger.error("FLARUM_BASE_URL not configured")
        return None

    api_key = _get_flarum_api_key()
    if not api_key:
        logger.error("FLARUM_API_KEY not configured")
        return None

    url = f"{base_url}/api/discussions"
    headers = _get_api_key_headers(user_id)

    data: dict[str, Any] = {
        "data": {
            "type": "discussions",
            "attributes": {
                "title": title,
                "content": content,
            },
        }
    }

    # Add tags relationship if provided
    if tag_ids:
        data["data"]["relationships"] = {
            "tags": {"data": [{"type": "tags", "id": str(tag_id)} for tag_id in tag_ids]}
        }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        logger.error("Failed to create Flarum discussion: %s", e)
        return None

    if response.status_code not in (200, 201):
        logger.error(
            "Failed to create Flarum discussion: Server returned %s, error: %s",
            response.status_code,
            response.text,
        )
        return None

    try:
        result = response.json()
        discussion_id = result.get("data", {}).get("id")
        if discussion_id:
            logger.info("Successfully created Flarum discussion: %s (id: %s)", title, discussion_id)
            return str(discussion_id)
        else:
            logger.error("Flarum discussion created but no ID in response: %s", result)
            return None
    except (ValueError, KeyError) as e:
        logger.error("Failed to parse Flarum discussion creation response: %s", e)
        return None
