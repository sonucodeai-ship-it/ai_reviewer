"""Authenticated QR management and public QR resolver/analytics endpoints.

This module intentionally does not use the coin billing service: QR creation
and downloads are free by product requirement.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from mysql.connector import Error
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.database import get_db

router = APIRouter(tags=["QR Codes"])


class QRCreateRequest(BaseModel):
    qr_name: str = Field(min_length=2, max_length=120)
    dashboard_id: int = Field(gt=0)
    website_version_id: int = Field(gt=0)


class QRUpdateRequest(BaseModel):
    qr_name: str | None = Field(default=None, min_length=2, max_length=120)
    dashboard_id: int | None = Field(default=None, gt=0)
    website_version_id: int | None = Field(default=None, gt=0)


class QREventRequest(BaseModel):
    event_type: Literal["review_click", "showcase_click"]
    session_id: str | None = Field(default=None, max_length=80)


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _clean_row(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {key: _json_value(value) for key, value in row.items()}


def _get_business(cursor, user_id: int) -> dict:
    cursor.execute(
        """SELECT business_id, business_name, business_type
           FROM business_info WHERE user_id = %s
           ORDER BY business_id ASC LIMIT 1""",
        (user_id,),
    )
    business = cursor.fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business information not found. Complete Business Info first.")
    return business


def _owned_qr(cursor, qr_id: int, user_id: int, include_deleted: bool = False) -> dict:
    deleted_clause = "" if include_deleted else " AND q.is_deleted = FALSE"
    cursor.execute(
        f"""SELECT q.qr_id, q.user_id, q.business_id, q.qr_token, q.qr_name,
                   q.dashboard_id, q.website_version_id, q.is_active, q.is_deleted,
                   q.created_at, q.updated_at, d.dashboard_name, d.public_url_id AS dashboard_public_url_id,
                   v.version_number, v.public_url_id AS website_public_url_id,
                   b.business_name
            FROM business_qr_code q
            INNER JOIN dashboard d ON d.dashboard_id = q.dashboard_id
            INNER JOIN website_version v ON v.website_version_id = q.website_version_id
            INNER JOIN business_info b ON b.business_id = q.business_id
            WHERE q.qr_id = %s AND q.user_id = %s {deleted_clause}
            LIMIT 1""",
        (qr_id, user_id),
    )
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="QR code not found.")
    return result


def _validate_destinations(cursor, user_id: int, dashboard_id: int, website_version_id: int, business_id: int) -> tuple[dict, dict]:
    cursor.execute(
        """SELECT dashboard_id, dashboard_name, public_url_id
           FROM dashboard WHERE dashboard_id = %s AND user_id = %s AND business_id = %s LIMIT 1""",
        (dashboard_id, user_id, business_id),
    )
    dashboard = cursor.fetchone()
    if not dashboard:
        raise HTTPException(status_code=400, detail="Select a review dashboard belonging to your business.")

    cursor.execute(
        """SELECT v.website_version_id, v.version_number, v.public_url_id, v.website_id
           FROM website_version v
           INNER JOIN website w ON w.website_id = v.website_id
           WHERE v.website_version_id = %s AND w.user_id = %s AND w.business_id = %s
           LIMIT 1""",
        (website_version_id, user_id, business_id),
    )
    version = cursor.fetchone()
    if not version:
        raise HTTPException(status_code=400, detail="Select a showcase version belonging to your business.")
    return dashboard, version


@router.get("/api/qr-codes/resources")
def list_qr_resources(user_id: int = Depends(get_current_user_id)):
    """Return the current user's dashboards and all available showcase versions."""
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        business = _get_business(cursor, user_id)
        cursor.execute(
            """SELECT dashboard_id, dashboard_name, public_url_id
               FROM dashboard WHERE user_id = %s AND business_id = %s
               ORDER BY created_at DESC, dashboard_id DESC""",
            (user_id, business["business_id"]),
        )
        dashboards = cursor.fetchall()
        cursor.execute(
            """SELECT v.website_version_id, v.version_number, v.public_url_id,
                      v.created_at, v.is_active, w.website_id
               FROM website_version v
               INNER JOIN website w ON w.website_id = v.website_id
               WHERE w.user_id = %s AND w.business_id = %s
               ORDER BY v.website_id DESC, v.version_number DESC""",
            (user_id, business["business_id"]),
        )
        versions = cursor.fetchall()
        return {
            "success": True,
            "business": _clean_row(business),
            "dashboards": [_clean_row(row) for row in dashboards],
            "website_versions": [_clean_row(row) for row in versions],
        }
    except HTTPException:
        raise
    except Error as exc:
        print(f"QR resources database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to load QR setup options.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.post("/api/qr-codes", status_code=status.HTTP_201_CREATED)
def create_qr(payload: QRCreateRequest, user_id: int = Depends(get_current_user_id)):
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        business = _get_business(cursor, user_id)
        _validate_destinations(cursor, user_id, payload.dashboard_id, payload.website_version_id, business["business_id"])
        token = secrets.token_urlsafe(32)
        cursor.execute(
            """INSERT INTO business_qr_code
               (user_id, business_id, qr_token, qr_name, dashboard_id, website_version_id, is_active, is_deleted)
               VALUES (%s, %s, %s, %s, %s, %s, TRUE, FALSE)""",
            (user_id, business["business_id"], token, payload.qr_name.strip(), payload.dashboard_id, payload.website_version_id),
        )
        qr_id = cursor.lastrowid
        db.commit()
        return {"success": True, "qr": _clean_row(_owned_qr(cursor, qr_id, user_id))}
    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as exc:
        if db:
            db.rollback()
        print(f"QR creation database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to create QR code.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.get("/api/qr-codes")
def list_qr_codes(user_id: int = Depends(get_current_user_id)):
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """SELECT q.qr_id, q.qr_name, q.qr_token, q.dashboard_id, q.website_version_id,
                      q.is_active, q.created_at, q.updated_at,
                      d.dashboard_name, d.public_url_id AS dashboard_public_url_id,
                      v.version_number, v.public_url_id AS website_public_url_id,
                      b.business_name,
                      COALESCE(a.scans, 0) AS scans,
                      COALESCE(a.review_clicks, 0) AS review_clicks,
                      COALESCE(a.showcase_clicks, 0) AS showcase_clicks
               FROM business_qr_code q
               INNER JOIN dashboard d ON d.dashboard_id = q.dashboard_id
               INNER JOIN website_version v ON v.website_version_id = q.website_version_id
               INNER JOIN business_info b ON b.business_id = q.business_id
               LEFT JOIN (
                 SELECT qr_id,
                   SUM(event_type = 'scan') AS scans,
                   SUM(event_type = 'review_click') AS review_clicks,
                   SUM(event_type = 'showcase_click') AS showcase_clicks
                 FROM qr_analytics_event GROUP BY qr_id
               ) a ON a.qr_id = q.qr_id
               WHERE q.user_id = %s AND q.is_deleted = FALSE
               ORDER BY q.created_at DESC, q.qr_id DESC""",
            (user_id,),
        )
        return {"success": True, "qr_codes": [_clean_row(row) for row in cursor.fetchall()]}
    except Error as exc:
        print(f"QR list database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to load QR codes.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.get("/api/qr-codes/{qr_id}")
def get_qr(qr_id: int, user_id: int = Depends(get_current_user_id)):
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        return {"success": True, "qr": _clean_row(_owned_qr(cursor, qr_id, user_id))}
    except HTTPException:
        raise
    except Error as exc:
        print(f"QR detail database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to load QR code.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.patch("/api/qr-codes/{qr_id}")
def update_qr(qr_id: int, payload: QRUpdateRequest, user_id: int = Depends(get_current_user_id)):
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        current = _owned_qr(cursor, qr_id, user_id)
        business = _get_business(cursor, user_id)
        dashboard_id = payload.dashboard_id or int(current["dashboard_id"])
        website_version_id = payload.website_version_id or int(current["website_version_id"])
        _validate_destinations(cursor, user_id, dashboard_id, website_version_id, business["business_id"])
        qr_name = (payload.qr_name.strip() if payload.qr_name is not None else current["qr_name"])
        if len(qr_name) < 2 or len(qr_name) > 120:
            raise HTTPException(status_code=400, detail="QR name must be between 2 and 120 characters.")
        cursor.execute(
            """UPDATE business_qr_code SET qr_name = %s, dashboard_id = %s,
               website_version_id = %s, updated_at = CURRENT_TIMESTAMP
               WHERE qr_id = %s AND user_id = %s AND is_deleted = FALSE""",
            (qr_name, dashboard_id, website_version_id, qr_id, user_id),
        )
        db.commit()
        # qr_token is intentionally never modified: printed QR remains stable.
        return {"success": True, "qr": _clean_row(_owned_qr(cursor, qr_id, user_id))}
    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as exc:
        if db:
            db.rollback()
        print(f"QR update database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to update QR code.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.patch("/api/qr-codes/{qr_id}/status")
def set_qr_status(qr_id: int, payload: dict, user_id: int = Depends(get_current_user_id)):
    active = payload.get("is_active")
    if not isinstance(active, bool):
        raise HTTPException(status_code=400, detail="is_active must be true or false.")
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        _owned_qr(cursor, qr_id, user_id)
        cursor.execute(
            "UPDATE business_qr_code SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE qr_id = %s AND user_id = %s AND is_deleted = FALSE",
            (active, qr_id, user_id),
        )
        db.commit()
        return {"success": True, "qr": _clean_row(_owned_qr(cursor, qr_id, user_id))}
    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as exc:
        if db:
            db.rollback()
        print(f"QR status database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to update QR status.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.delete("/api/qr-codes/{qr_id}")
def delete_qr(qr_id: int, user_id: int = Depends(get_current_user_id)):
    """Soft-delete to preserve historical analytics; public access is disabled."""
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        _owned_qr(cursor, qr_id, user_id)
        cursor.execute(
            "UPDATE business_qr_code SET is_active = FALSE, is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP WHERE qr_id = %s AND user_id = %s",
            (qr_id, user_id),
        )
        db.commit()
        return {"success": True, "message": "QR code deleted."}
    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as exc:
        if db:
            db.rollback()
        print(f"QR delete database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to delete QR code.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.get("/api/qr-codes/{qr_id}/analytics")
def qr_analytics(qr_id: int, user_id: int = Depends(get_current_user_id)):
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        qr = _owned_qr(cursor, qr_id, user_id)
        cursor.execute(
            """SELECT event_type, COUNT(*) AS event_count, MAX(occurred_at) AS last_event_at
               FROM qr_analytics_event WHERE qr_id = %s GROUP BY event_type""",
            (qr_id,),
        )
        events = [_clean_row(row) for row in cursor.fetchall()]
        return {"success": True, "qr": {"qr_id": qr_id, "qr_name": qr["qr_name"]}, "events": events}
    except HTTPException:
        raise
    except Error as exc:
        print(f"QR analytics database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to load QR analytics.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.get("/api/public/qr/{qr_token}")
def resolve_public_qr(qr_token: str):
    """Resolve a public token and count each landing-page visit as a scan."""
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """SELECT q.qr_id, q.qr_name, q.is_active, q.is_deleted,
                      d.dashboard_name, d.public_url_id AS dashboard_public_url_id,
                      v.version_number, v.public_url_id AS website_public_url_id,
                      b.business_name, b.business_type
               FROM business_qr_code q
               INNER JOIN dashboard d ON d.dashboard_id = q.dashboard_id
               INNER JOIN website_version v ON v.website_version_id = q.website_version_id
               INNER JOIN business_info b ON b.business_id = q.business_id
               WHERE q.qr_token = %s LIMIT 1""",
            (qr_token,),
        )
        qr = cursor.fetchone()
        if not qr or not qr["is_active"] or qr["is_deleted"]:
            raise HTTPException(status_code=404, detail="This QR code is unavailable or has been disabled.")
        cursor.execute(
            "INSERT INTO qr_analytics_event (qr_id, event_type) VALUES (%s, 'scan')",
            (qr["qr_id"],),
        )
        db.commit()
        return {
            "success": True,
            "qr_name": qr["qr_name"],
            "business_name": qr["business_name"],
            "business_type": qr.get("business_type"),
            "dashboard_name": qr["dashboard_name"],
            "dashboard_public_url_id": qr["dashboard_public_url_id"],
            "website_public_url_id": qr["website_public_url_id"],
            "website_version_number": qr["version_number"],
        }
    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as exc:
        if db:
            db.rollback()
        print(f"Public QR resolver database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to open this QR code right now.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.post("/api/public/qr/{qr_token}/events")
def track_public_qr_event(qr_token: str, payload: QREventRequest):
    db = cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT qr_id FROM business_qr_code WHERE qr_token = %s AND is_active = TRUE AND is_deleted = FALSE LIMIT 1",
            (qr_token,),
        )
        qr = cursor.fetchone()
        if not qr:
            raise HTTPException(status_code=404, detail="This QR code is unavailable.")
        cursor.execute(
            "INSERT INTO qr_analytics_event (qr_id, event_type, session_id) VALUES (%s, %s, %s)",
            (qr["qr_id"], payload.event_type, payload.session_id),
        )
        db.commit()
        return {"success": True}
    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as exc:
        if db:
            db.rollback()
        print(f"Public QR event database error: {exc}")
        raise HTTPException(status_code=500, detail="Unable to record QR interaction.") from exc
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
