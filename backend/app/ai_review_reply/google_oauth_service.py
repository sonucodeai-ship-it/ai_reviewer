import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

from app.database import get_db
from .config import (
    GOOGLE_ACCOUNT_API, GOOGLE_AUTHORIZATION_URL, GOOGLE_BUSINESS_SCOPE,
    GOOGLE_FRONTEND_URL, GOOGLE_LOCATION_API, GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REDIRECT_URI, GOOGLE_TOKEN_URL,
    OAUTH_STATE_MINUTES,
)
from .google_token_service import encrypt_token, decrypt_token


def validate_oauth_configuration():
    missing = []
    for name, value in (
        ("GOOGLE_OAUTH_CLIENT_ID", GOOGLE_OAUTH_CLIENT_ID),
        ("GOOGLE_OAUTH_CLIENT_SECRET", GOOGLE_OAUTH_CLIENT_SECRET),
        ("GOOGLE_OAUTH_REDIRECT_URI", GOOGLE_OAUTH_REDIRECT_URI),
        ("GOOGLE_FRONTEND_URL", GOOGLE_FRONTEND_URL),
    ):
        if not value:
            missing.append(name)
    if missing:
        raise RuntimeError("Google OAuth is not configured. Missing: " + ", ".join(missing))


def create_oauth_state(user_id: int, business_id: int) -> str:
    state = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OAUTH_STATE_MINUTES)
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """INSERT INTO google_oauth_state
               (state_token, user_id, business_id, expires_at)
               VALUES (%s, %s, %s, %s)""",
            (state, user_id, business_id, expires_at.replace(tzinfo=None)),
        )
        db.commit()
        return state
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()


def consume_oauth_state(state: str):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT state_id, user_id, business_id, expires_at, used_at
               FROM google_oauth_state
               WHERE state_token = %s LIMIT 1""",
            (state,),
        )
        record = cursor.fetchone()
        if not record or record["used_at"] is not None:
            return None
        expires_at = record["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires_at:
            return None
        cursor.execute(
            "UPDATE google_oauth_state SET used_at = %s WHERE state_id = %s",
            (datetime.now(timezone.utc).replace(tzinfo=None), record["state_id"]),
        )
        db.commit()
        return record
    finally:
        cursor.close()
        db.close()


def build_authorization_url(state: str) -> str:
    validate_oauth_configuration()
    params = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_BUSINESS_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    validate_oauth_configuration()
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    data = response.json()
    if not response.ok:
        raise RuntimeError(
            data.get("error_description") or data.get("error") or response.text
        )
    if not data.get("access_token"):
        raise RuntimeError("Google did not return an access token.")
    return data


def get_google_accounts(access_token: str) -> list[dict]:
    response = requests.get(
        f"{GOOGLE_ACCOUNT_API}/accounts",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    data = response.json()
    if not response.ok:
        raise RuntimeError(
            data.get("error", {}).get("message")
            or "Unable to retrieve Google Business Profile accounts."
        )
    return data.get("accounts", [])


def get_google_locations(access_token: str, account_name: str) -> list[dict]:
    """Fetch all locations for a GBP account, including pagination."""
    locations: list[dict] = []
    page_token: str | None = None

    while True:
        params = {
            "readMask": "name,title,storefrontAddress,websiteUri",
            "pageSize": 100,
        }
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(
            f"{GOOGLE_LOCATION_API}/{account_name}/locations",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        try:
            data = response.json()
        except ValueError:
            data = {}

        if not response.ok:
            error = data.get("error") or {}
            message = (
                error.get("message")
                if isinstance(error, dict)
                else None
            )
            raise RuntimeError(
                message
                or "Unable to retrieve Google Business Profile locations."
            )

        locations.extend(data.get("locations") or [])
        page_token = data.get("nextPageToken")

        if not page_token:
            break

    return locations


def save_google_connection(*, user_id, business_id, account, access_token,
                           refresh_token, expires_in):
    expires_at = None
    if expires_in:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        ).replace(tzinfo=None)

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """INSERT INTO google_business_connection
               (business_id, user_id, google_account_name, google_account_id,
                access_token_encrypted, refresh_token_encrypted,
                access_token_expires_at, connection_status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'oauth_connected')
               ON DUPLICATE KEY UPDATE
                 user_id=VALUES(user_id),
                 google_account_name=VALUES(google_account_name),
                 google_account_id=VALUES(google_account_id),
                 access_token_encrypted=VALUES(access_token_encrypted),
                 refresh_token_encrypted=COALESCE(
                     VALUES(refresh_token_encrypted), refresh_token_encrypted),
                 access_token_expires_at=VALUES(access_token_expires_at),
                 connection_status='oauth_connected',
                 updated_at=CURRENT_TIMESTAMP""",
            (
                business_id, user_id, account.get("name"), account.get("accountId"),
                encrypt_token(access_token),
                encrypt_token(refresh_token) if refresh_token else None,
                expires_at,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()


def get_connection(user_id, business_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT connection_id,business_id,user_id,google_account_name,
                      google_account_id,google_location_name,google_location_id,
                      google_location_title,connection_status,
                      access_token_expires_at,created_at,updated_at
               FROM google_business_connection
               WHERE user_id=%s AND business_id=%s LIMIT 1""",
            (user_id, business_id),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()


def get_connection_with_tokens(user_id, business_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM google_business_connection WHERE user_id=%s AND business_id=%s LIMIT 1",
            (user_id, business_id),
        )
        record = cursor.fetchone()
        if not record:
            return None
        record["access_token"] = decrypt_token(record["access_token_encrypted"])
        record["refresh_token"] = (
            decrypt_token(record["refresh_token_encrypted"])
            if record.get("refresh_token_encrypted") else None
        )
        return record
    finally:
        cursor.close()
        db.close()


def update_selected_location(*, user_id, business_id, location):
    location_name = location.get("name", "")
    location_id = location_name.split("/")[-1]
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """UPDATE google_business_connection
               SET google_location_name=%s, google_location_id=%s,
                   google_location_title=%s, connection_status='connected',
                   updated_at=CURRENT_TIMESTAMP
               WHERE user_id=%s AND business_id=%s""",
            (location_name, location_id, location.get("title"), user_id, business_id),
        )
        if cursor.rowcount == 0:
            raise RuntimeError("Google connection was not found for this business.")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()
