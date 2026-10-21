from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.auth import get_current_user_id
from app.database import get_db
from .config import GOOGLE_FRONTEND_URL
from .google_oauth_service import (
    build_authorization_url, consume_oauth_state, create_oauth_state,
    exchange_code_for_tokens, get_connection, get_connection_with_tokens,
    get_google_accounts, get_google_locations, save_google_connection,
    update_selected_location,
)

router = APIRouter(prefix="/api/ai-review-reply/google", tags=["AI Review Reply - Google"])


def _get_user_business(cursor, user_id):
    cursor.execute(
        """SELECT business_id,business_name,google_review_link
           FROM business_info WHERE user_id=%s
           ORDER BY business_id ASC LIMIT 1""",
        (user_id,),
    )
    business = cursor.fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business information not found.")
    return business


@router.get("/status")
def status(user_id: int = Depends(get_current_user_id)):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        business = _get_user_business(cursor, user_id)
        connection = get_connection(user_id, business["business_id"])
        return {
            "success": True,
            "business": business,
            "connected": bool(connection and connection["connection_status"] == "connected"),
            "connection": connection,
        }
    finally:
        cursor.close()
        db.close()


@router.get("/connect")
def connect(user_id: int = Depends(get_current_user_id)):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        business = _get_user_business(cursor, user_id)
    finally:
        cursor.close()
        db.close()

    state = create_oauth_state(user_id, business["business_id"])
    return {"success": True, "authorization_url": build_authorization_url(state)}


@router.get("/callback")
def callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(
            f"{GOOGLE_FRONTEND_URL}/google-business?google_oauth=denied&reason={quote(error)}"
        )
    if not code or not state:
        return RedirectResponse(
            f"{GOOGLE_FRONTEND_URL}/google-business?google_oauth=failed&reason=missing_callback_data"
        )

    state_record = consume_oauth_state(state)
    if not state_record:
        return RedirectResponse(
            f"{GOOGLE_FRONTEND_URL}/google-business?google_oauth=failed&reason=invalid_or_expired_state"
        )

    try:
        token_data = exchange_code_for_tokens(code)
        accounts = get_google_accounts(token_data["access_token"])
        if not accounts:
            return RedirectResponse(
                f"{GOOGLE_FRONTEND_URL}/google-business?google_oauth=failed&reason=no_business_profile_accounts"
            )

        save_google_connection(
            user_id=state_record["user_id"],
            business_id=state_record["business_id"],
            account=accounts[0],
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
        )
        return RedirectResponse(
            f"{GOOGLE_FRONTEND_URL}/google-business?google_oauth=success"
        )
    except Exception as error:
        print(f"Google OAuth callback error: {error}")
        return RedirectResponse(
            f"{GOOGLE_FRONTEND_URL}/google-business?google_oauth=failed&reason=oauth_processing_error"
        )


@router.get("/locations")
def locations(user_id: int = Depends(get_current_user_id)):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        business = _get_user_business(cursor, user_id)
    finally:
        cursor.close()
        db.close()

    connection = get_connection_with_tokens(user_id, business["business_id"])
    if not connection:
        raise HTTPException(status_code=404, detail="Google Business Profile is not connected.")
    try:
        items = get_google_locations(
            connection["access_token"], connection["google_account_name"]
        )
        return {
            "success": True,
            "locations": [
                {
                    "name": item.get("name"),
                    "location_id": item.get("name", "").split("/")[-1],
                    "title": item.get("title"),
                    "storefront_address": item.get("storefrontAddress"),
                    "website_uri": item.get("websiteUri"),
                }
                for item in items
            ],
        }
    except Exception as error:
        print(f"Google location retrieval error: {error}")
        raise HTTPException(status_code=502, detail="Unable to retrieve Google Business locations.") from error


@router.post("/select-location")
def select_location(payload: dict, user_id: int = Depends(get_current_user_id)):
    location_name = str(payload.get("location_name", "")).strip()
    if not location_name.startswith("locations/"):
        raise HTTPException(status_code=400, detail="A valid Google location is required.")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        business = _get_user_business(cursor, user_id)
    finally:
        cursor.close()
        db.close()

    connection = get_connection_with_tokens(user_id, business["business_id"])
    if not connection:
        raise HTTPException(status_code=404, detail="Google Business Profile is not connected.")

    try:
        items = get_google_locations(
            connection["access_token"], connection["google_account_name"]
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="Unable to validate the Google location.") from error

    selected = next((item for item in items if item.get("name") == location_name), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Selected Google location was not found.")

    update_selected_location(
        user_id=user_id, business_id=business["business_id"], location=selected
    )
    return {
        "success": True,
        "message": "Google Business Profile connected successfully.",
        "location": {
            "name": selected.get("name"),
            "location_id": location_name.split("/")[-1],
            "title": selected.get("title"),
        },
    }
