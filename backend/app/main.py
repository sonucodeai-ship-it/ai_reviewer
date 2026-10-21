from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware



# =========================================================
# APPLICATION DATE/TIME POLICY
# =========================================================
#
# SINGLE SOURCE OF TRUTH:
#     This module (main.py) owns application datetime logic.
#
# RULES:
#     1. Current application time -> now_utc()
#     2. Normalize DB datetimes -> ensure_utc()
#     3. API machine timestamps -> serialize_datetime()
#     4. User-facing timestamps -> format_datetime()
#     5. MySQL created_at/updated_at -> CURRENT_TIMESTAMP with
#        every DB session explicitly configured to UTC.
#
# Never introduce datetime.now(), datetime.utcnow(), or local
# server-time calculations in feature routes/services.
# React should consume *_formatted values for business display.
# =========================================================

# =========================================================
# CENTRAL DATE/TIME MANAGEMENT
# =========================================================

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# APPLICATION TIMEZONE
# ---------------------------------------------------------
#
# Database timestamps are ALWAYS stored in UTC.
#
# This timezone is used only for displaying timestamps
# to the current application's users.
#
# Later, this can come from the user's profile/settings.
# ---------------------------------------------------------

DEFAULT_TIMEZONE = "Asia/Kolkata"


# ---------------------------------------------------------
# CURRENT UTC TIME
# ---------------------------------------------------------

def now_utc() -> datetime:
    """
    Return the current application time in UTC.

    IMPORTANT:
        This is the ONLY function that application code
        should use when it needs the current datetime.
    """

    return datetime.now(timezone.utc)


# ---------------------------------------------------------
# NORMALIZE DATETIME TO UTC
# ---------------------------------------------------------

def ensure_utc(
    value: datetime | None,
) -> datetime | None:
    """
    Ensure a datetime is timezone-aware and represents UTC.

    MySQL TIMESTAMP values may sometimes be returned as
    naive datetime objects depending on the connection/session.
    In that case, they are interpreted as UTC.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


# ---------------------------------------------------------
# MACHINE-READABLE UTC DATETIME
# ---------------------------------------------------------

def serialize_datetime(
    value: datetime | None,
) -> str | None:
    """
    Convert a datetime into a machine-readable UTC
    ISO-8601 string.

    Example:
        2026-09-24T12:16:00+00:00
    """

    value = ensure_utc(value)

    if value is None:
        return None

    return value.isoformat()


# ---------------------------------------------------------
# USER-FACING DATETIME
# ---------------------------------------------------------

def format_datetime(
    value: datetime | None,
    user_timezone: str = DEFAULT_TIMEZONE,
) -> str:
    """
    Convert a UTC datetime into the user's timezone and
    return the application's standard display format.

    Example:
        24 sep 26 at 17:46

    IMPORTANT:
        All user-facing datetime values must use this
        function.
    """

    value = ensure_utc(value)

    if value is None:
        return ""

    try:
        local_value = value.astimezone(
            ZoneInfo(user_timezone)
        )
    except Exception:
        # Safety fallback for invalid timezone values.
        local_value = value.astimezone(
            ZoneInfo(DEFAULT_TIMEZONE)
        )

    return (
        f"{local_value.day} "
        f"{local_value.strftime('%b').lower()} "
        f"{local_value.strftime('%y')} "
        f"at "
        f"{local_value.strftime('%H:%M')}"
    )

# =========================================================
# APPLICATION SCHEMAS / SERVICES
# =========================================================

from app.schemas import (
    ReviewRequest,
    ReviewResponse,
    ReviewSubmitStatusRequest,
)

from app.review_generator import generate_review
from app.database import get_db
from app.coin_routes import authorize_usage


# =========================================================
# APPLICATION ROUTERS
# =========================================================

from app.auth_routes import router as auth_router
from app.business_routes import router as business_router
from app.query_routes import router as query_router
from app.dashboard_routes import router as dashboard_router
from app.ai_review_reply.router import router as ai_review_reply_router
from app.your_websie_backend.router import router as your_website_router
from app.coin_routes import router as coin_router
from app.qr_backend.routes import router as qr_router

# Admin router
from app.Admin_backend.admin_routes import router as admin_router


# =========================================================
# APPLICATION
# =========================================================

app = FastAPI(
    title="AI Review Generator",
    description="AI-powered business review generation API",
    version="1.0.0",
)


# =========================================================
# AUTHENTICATION ROUTES
# =========================================================

app.include_router(auth_router)


# =========================================================
# BUSINESS INFORMATION ROUTES
# =========================================================

app.include_router(business_router)


# =========================================================
# QUERY MAKER ROUTES
# =========================================================

app.include_router(query_router)


# =========================================================
# DASHBOARD ROUTES
# =========================================================

app.include_router(dashboard_router)


# =========================================================
# AI REVIEW REPLY ROUTES
# =========================================================

app.include_router(ai_review_reply_router)


# =========================================================
# YOUR WEBSITE ROUTES
# =========================================================

app.include_router(your_website_router)
app.include_router(coin_router)
app.include_router(qr_router)


# =========================================================
# ADMIN ROUTES
# =========================================================
#
# Admin authentication and administration are completely
# separate from the normal customer/business-owner
# authentication system.
#
# Endpoints are exposed under:
#
#     /api/admin/...
#
# The admin_routes.py file is responsible for enforcing
# admin authentication and Super Admin permissions.
#
# =========================================================

app.include_router(admin_router)



# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ai-reviewer-0ssx.onrender.com",
        "https://ai-reviewer-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": "AI Review Generator API is running",
    }


# =========================================================
# GENERATE REVIEW
# =========================================================


@app.post(
    "/api/reviews/generate",
    response_model=ReviewResponse,
)
def generate_review_api(
    request: ReviewRequest,
):
    """Generate a review with centralized coin authorization.

    Public customer flow:
      1. Validate dashboard ownership through coin_routes.py.
      2. Run a read-only billing preflight BEFORE Gemini.
      3. Generate the review only when authorized.
      4. Persist the review and finalize the coin charge in one DB transaction.

    The review feature never calculates coin costs or implements balance/
    membership error handling itself.
    """

    # ------------------------------------------------------------
    # PHASE 1: BILLING PREFLIGHT
    # ------------------------------------------------------------
    if request.dashboard_id is not None:
        preflight_db = None
        preflight_cursor = None

        try:
            preflight_db = get_db()
            preflight_cursor = preflight_db.cursor(dictionary=True)

            authorize_usage(
                cursor=preflight_cursor,
                rule_no=1,
                dashboard_id=int(request.dashboard_id),
                phase="preflight",
            )

        except HTTPException:
            raise

        except Exception as error:
            print(f"Review billing preflight error: {error}")
            raise HTTPException(
                status_code=500,
                detail="Unable to authorize review generation.",
            ) from error

        finally:
            if preflight_cursor:
                preflight_cursor.close()
            if preflight_db:
                preflight_db.close()

    # ------------------------------------------------------------
    # PHASE 2: EXPENSIVE AI WORK
    # ------------------------------------------------------------
    try:
        review = generate_review(
            answers=request.answers,
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    # ------------------------------------------------------------
    # PHASE 3: FINAL DB TRANSACTION + BILLING
    # ------------------------------------------------------------
    review_id = None

    if request.dashboard_id is not None:
        db = None
        cursor = None

        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT dashboard_id
                FROM dashboard
                WHERE dashboard_id = %s
                LIMIT 1
                """,
                (request.dashboard_id,),
            )

            dashboard = cursor.fetchone()

            if not dashboard:
                raise HTTPException(
                    status_code=404,
                    detail="Dashboard not found.",
                )

            cursor.execute(
                """
                INSERT INTO `review`
                (
                    dashboard_id,
                    review_text,
                    regenerate_status
                )
                VALUES (%s, %s, %s)
                """,
                (
                    request.dashboard_id,
                    review,
                    request.regenerate_status,
                ),
            )

            review_id = int(cursor.lastrowid)

            coin_charge = authorize_usage(
                cursor=cursor,
                rule_no=1,
                dashboard_id=int(request.dashboard_id),
                reference_id=review_id,
                phase="finalize",
            )

            db.commit()

        except HTTPException:
            if db:
                db.rollback()
            raise

        except Exception as db_error:
            if db:
                db.rollback()

            print(f"Review persistence error: {db_error}")

            raise HTTPException(
                status_code=500,
                detail="Review was generated but could not be saved.",
            ) from db_error

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    return {
        "success": True,
        "review": review,
        "review_id": review_id,
    }

@app.patch(
    "/api/reviews/{review_id}/submit-status",
)
def update_review_submit_status(
    review_id: int,
    request: ReviewSubmitStatusRequest,
):
    """
    Record the Google hand-off status for a generated review.

    Important:

        submit_status = 1
            The browser successfully opened the Google
            review URL.

        submit_status = 0
            The browser could not open the Google review URL,
            typically because the popup was blocked.

    This endpoint does not claim that a Google review was
    actually submitted.

    The Google page is cross-origin, so the application
    cannot verify the customer's final submission from
    this flow.
    """

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT review_id
            FROM `review`
            WHERE review_id = %s
            LIMIT 1
            """,
            (review_id,),
        )

        existing_review = cursor.fetchone()

        if not existing_review:
            raise HTTPException(
                status_code=404,
                detail="Review record not found.",
            )

        # -----------------------------------------------------
        # Update review text as well when supplied.
        # -----------------------------------------------------

        if request.review_text is not None:
            review_text = request.review_text.strip()

            if not review_text:
                raise HTTPException(
                    status_code=400,
                    detail="Review text cannot be empty.",
                )

            cursor.execute(
                """
                UPDATE `review`
                SET
                    review_text = %s,
                    submit_status = %s
                WHERE review_id = %s
                """,
                (
                    review_text,
                    request.submit_status,
                    review_id,
                ),
            )

        else:
            cursor.execute(
                """
                UPDATE `review`
                SET submit_status = %s
                WHERE review_id = %s
                """,
                (
                    request.submit_status,
                    review_id,
                ),
            )

        db.commit()

        return {
            "success": True,
            "review_id": review_id,
            "submit_status": request.submit_status,
        }

    except HTTPException:
        if db:
            db.rollback()

        raise

    except Exception as error:
        if db:
            db.rollback()

        print(
            f"Review submit status error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to update review submit status.",
        ) from error

    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()
