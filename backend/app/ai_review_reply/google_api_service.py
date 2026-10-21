from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from .config import GOOGLE_TOKEN_URL, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
from .google_oauth_service import get_connection_with_tokens
from .google_token_service import encrypt_token
from app.database import get_db


class GoogleApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def _error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text or "Google API request failed."
    return (
        data.get("error", {}).get("message")
        if isinstance(data.get("error"), dict)
        else data.get("error_description")
        or data.get("error")
        or response.text
        or "Google API request failed."
    )


def refresh_access_token(connection: dict) -> str:
    refresh_token = connection.get("refresh_token")
    if not refresh_token:
        raise GoogleApiError("Google authorization has expired. Please reconnect Google Business Profile.")

    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )

    if not response.ok:
        message = _error_message(response)
        if response.status_code in (400, 401):
            _mark_connection_reauthorization_required(connection["connection_id"])
        raise GoogleApiError(message, response.status_code)

    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise GoogleApiError("Google did not return a refreshed access token.")

    expires_in = int(data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            UPDATE google_business_connection
            SET access_token_encrypted=%s,
                access_token_expires_at=%s,
                connection_status='connected',
                updated_at=CURRENT_TIMESTAMP
            WHERE connection_id=%s
            """,
            (encrypt_token(access_token), expires_at.replace(tzinfo=None), connection["connection_id"]),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return access_token


def _mark_connection_reauthorization_required(connection_id: int) -> None:
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            UPDATE google_business_connection
            SET connection_status='reauthorization_required',
                updated_at=CURRENT_TIMESTAMP
            WHERE connection_id=%s
            """,
            (connection_id,),
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        cursor.close()
        db.close()


def get_valid_access_token(
    user_id: int,
    business_id: int,
    *,
    require_location: bool = True,
) -> tuple[dict, str]:
    """Return a valid access token, refreshing it when necessary.

    ``require_location=False`` is used only during the OAuth ->
    location-selection step, before the owner has selected a GBP location.
    """
    connection = get_connection_with_tokens(user_id, business_id)
    if not connection:
        raise GoogleApiError("Google Business Profile is not connected.", 404)

    if require_location and not connection.get("google_location_name"):
        raise GoogleApiError(
            "A Google Business Profile location has not been selected.",
            400,
        )

    expires_at = connection.get("access_token_expires_at")
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if expires_at and now >= expires_at - timedelta(minutes=2):
        return connection, refresh_access_token(connection)

    return connection, connection["access_token"]


def google_request(
    *,
    user_id: int,
    business_id: int,
    method: str,
    url: str,
    params: dict | None = None,
    json: dict | None = None,
    timeout: int = 30,
) -> dict:
    connection, access_token = get_valid_access_token(user_id, business_id)

    response = requests.request(
        method,
        url,
        params=params,
        json=json,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=timeout,
    )

    if response.status_code == 401:
        # Retry once with a freshly refreshed token.
        access_token = refresh_access_token(connection)
        response = requests.request(
            method,
            url,
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
        )

    if not response.ok:
        raise GoogleApiError(_error_message(response), response.status_code)

    if response.status_code == 204 or not response.content:
        return {}

    try:
        return response.json()
    except ValueError as error:
        raise GoogleApiError("Google returned an invalid response.", response.status_code) from error
