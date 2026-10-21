from __future__ import annotations

from datetime import datetime

from app.database import get_db

from .google_api_service import GoogleApiError, google_request

GOOGLE_REVIEW_API = "https://mybusiness.googleapis.com/v4"


def _location_resource(connection: dict) -> str:
    account_name = connection["google_account_name"]
    location_name = connection["google_location_name"]
    account_id = account_name.split("/")[-1]
    location_id = location_name.split("/")[-1]
    return f"accounts/{account_id}/locations/{location_id}"


def _normalize_review(review: dict) -> dict:
    reviewer = review.get("reviewer") or {}
    reply = review.get("reviewReply") or {}

    return {
        "google_review_name": review.get("name"),
        "google_review_id": review.get("reviewId") or (review.get("name", "").split("/")[-1] or None),
        "reviewer_name": reviewer.get("displayName"),
        "reviewer_profile_url": reviewer.get("profilePhotoUrl"),
        "star_rating": review.get("starRating"),
        "comment": review.get("comment"),
        "google_create_time": review.get("createTime"),
        "google_update_time": review.get("updateTime"),
        "reply_comment": reply.get("comment"),
        "reply_update_time": reply.get("updateTime"),
    }


def list_google_reviews(user_id: int, business_id: int) -> list[dict]:
    connection, _ = _connection_and_token(user_id, business_id)
    resource = _location_resource(connection)

    reviews: list[dict] = []
    page_token = None

    while True:
        params = {"pageSize": 50, "orderBy": "updateTime desc"}
        if page_token:
            params["pageToken"] = page_token

        data = google_request(
            user_id=user_id,
            business_id=business_id,
            method="GET",
            url=f"{GOOGLE_REVIEW_API}/{resource}/reviews",
            params=params,
        )

        reviews.extend(data.get("reviews", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return reviews


def _connection_and_token(user_id: int, business_id: int):
    # Access-token validation is intentionally centralized in google_api_service.
    from .google_api_service import get_valid_access_token
    connection, token = get_valid_access_token(user_id, business_id)
    return connection, token


def sync_reviews(user_id: int, business_id: int) -> dict:
    raw_reviews = list_google_reviews(user_id, business_id)
    now = datetime.utcnow()

    db = get_db()
    cursor = db.cursor()
    inserted = 0
    updated = 0

    try:
        for raw in raw_reviews:
            review = _normalize_review(raw)
            cursor.execute(
                "SELECT review_id FROM google_review WHERE business_id=%s AND google_review_name=%s LIMIT 1",
                (business_id, review["google_review_name"]),
            )
            existing = cursor.fetchone()

            cursor.execute(
                """
                INSERT INTO google_review
                (business_id, connection_id, google_review_name, google_review_id,
                 reviewer_name, reviewer_profile_url, star_rating, comment,
                 google_create_time, google_update_time, reply_comment,
                 reply_update_time, last_synced_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    google_review_id=VALUES(google_review_id),
                    reviewer_name=VALUES(reviewer_name),
                    reviewer_profile_url=VALUES(reviewer_profile_url),
                    star_rating=VALUES(star_rating),
                    comment=VALUES(comment),
                    google_create_time=VALUES(google_create_time),
                    google_update_time=VALUES(google_update_time),
                    reply_comment=VALUES(reply_comment),
                    reply_update_time=VALUES(reply_update_time),
                    last_synced_at=VALUES(last_synced_at),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    business_id,
                    _get_connection_id(cursor, business_id),
                    review["google_review_name"],
                    review["google_review_id"],
                    review["reviewer_name"],
                    review["reviewer_profile_url"],
                    review["star_rating"],
                    review["comment"],
                    review["google_create_time"],
                    review["google_update_time"],
                    review["reply_comment"],
                    review["reply_update_time"],
                    now,
                ),
            )
            if existing:
                updated += 1
            else:
                inserted += 1

        cursor.execute(
            "UPDATE google_business_connection SET last_review_sync_at=%s WHERE business_id=%s",
            (now, business_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return {"total": len(raw_reviews), "inserted": inserted, "updated": updated}


def _get_connection_id(cursor, business_id: int) -> int:
    cursor.execute(
        "SELECT connection_id FROM google_business_connection WHERE business_id=%s LIMIT 1",
        (business_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise GoogleApiError("Google Business Profile is not connected.", 404)
    return row[0]


def get_local_reviews(user_id: int, business_id: int) -> list[dict]:
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT review_id, google_review_name, google_review_id,
                   reviewer_name, reviewer_profile_url, star_rating,
                   comment, google_create_time, google_update_time,
                   reply_comment, reply_update_time, last_synced_at,
                   created_at, updated_at
            FROM google_review
            WHERE business_id=%s
            ORDER BY COALESCE(google_update_time, google_create_time) DESC, review_id DESC
            """,
            (business_id,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def reply_to_google_review(user_id: int, business_id: int, review_id: int, comment: str) -> dict:
    comment = comment.strip()
    if not comment:
        raise ValueError("Reply cannot be empty.")
    if len(comment) > 4096:
        raise ValueError("Reply is too long.")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT google_review_name FROM google_review WHERE review_id=%s AND business_id=%s LIMIT 1",
            (review_id, business_id),
        )
        review = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not review:
        raise GoogleApiError("Review not found.", 404)

    resource = review["google_review_name"]
    data = google_request(
        user_id=user_id,
        business_id=business_id,
        method="PUT",
        url=f"{GOOGLE_REVIEW_API}/{resource}/reply",
        json={"comment": comment},
    )

    reply = data.get("comment", comment)
    reply_update_time = data.get("updateTime")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE google_review SET reply_comment=%s, reply_update_time=%s, updated_at=CURRENT_TIMESTAMP WHERE review_id=%s AND business_id=%s",
            (reply, reply_update_time, review_id, business_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return {"review_id": review_id, "reply_comment": reply, "reply_update_time": reply_update_time}


def delete_google_review_reply(user_id: int, business_id: int, review_id: int) -> None:
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT google_review_name FROM google_review WHERE review_id=%s AND business_id=%s LIMIT 1",
            (review_id, business_id),
        )
        review = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not review:
        raise GoogleApiError("Review not found.", 404)

    google_request(
        user_id=user_id,
        business_id=business_id,
        method="DELETE",
        url=f"{GOOGLE_REVIEW_API}/{review['google_review_name']}/reply",
    )

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE google_review SET reply_comment=NULL, reply_update_time=NULL, updated_at=CURRENT_TIMESTAMP WHERE review_id=%s AND business_id=%s",
            (review_id, business_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()
