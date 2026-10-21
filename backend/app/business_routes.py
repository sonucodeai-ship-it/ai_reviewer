from fastapi import APIRouter, Header, HTTPException
from mysql.connector import Error

from app.database import get_db
from app.auth import get_current_user_id
from app.main import format_datetime
from app.schemas import (
    BusinessInfoRequest,
    BusinessInfoResponse,
)


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/api/business",
    tags=["Business Information"],
)


# =========================================================
# CREATE / UPDATE BUSINESS INFORMATION
# =========================================================

@router.post(
    "/info",
    response_model=BusinessInfoResponse,
)
def save_business_info(
    request: BusinessInfoRequest,
    authorization: str = Header(...),
):
    """
    Create or update the authenticated user's business
    information.

    Each user can have one business profile.
    """

    # -----------------------------------------------------
    # Validate authentication token
    # -----------------------------------------------------

    user_id = get_current_user_id(
        authorization
    )

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:
        # -------------------------------------------------
        # Check whether business information already exists
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                business_id
            FROM business_info
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )

        existing_business = cursor.fetchone()

        # -------------------------------------------------
        # Update existing business profile
        # -------------------------------------------------

        if existing_business:

            cursor.execute(
                """
                UPDATE business_info
                SET
                    business_name = %s,
                    business_type = %s,
                    about_business = %s,
                    year_established = %s,
                    google_review_link = %s
                WHERE user_id = %s
                """,
                (
                    request.business_name,
                    request.business_type,
                    request.about_business,
                    request.year_established,
                    str(request.google_review_link),
                    user_id,
                ),
            )

            business_id = existing_business["business_id"]

            message = (
                "Business information updated successfully."
            )

        # -------------------------------------------------
        # Create new business profile
        # -------------------------------------------------

        else:

            cursor.execute(
                """
                INSERT INTO business_info (
                    user_id,
                    business_name,
                    business_type,
                    about_business,
                    year_established,
                    google_review_link
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    user_id,
                    request.business_name,
                    request.business_type,
                    request.about_business,
                    request.year_established,
                    str(request.google_review_link),
                ),
            )

            business_id = cursor.lastrowid

            message = (
                "Business information saved successfully."
            )

        # -------------------------------------------------
        # Commit transaction
        # -------------------------------------------------

        connection.commit()

        cursor.execute(
            """
            SELECT
                updated_at
            FROM business_info
            WHERE business_id = %s
            LIMIT 1
            """,
            (business_id,),
        )

        saved_business = cursor.fetchone()

        return {
            "success": True,
            "message": message,
            "business_id": business_id,
            "business_name": request.business_name,
            "business_type": request.business_type,
            "about_business": request.about_business,
            "year_established": request.year_established,
            "google_review_link": str(request.google_review_link),
            "updated_at": (
                saved_business["updated_at"].isoformat()
                if saved_business and saved_business["updated_at"]
                else None
            ),
            "updated_at_formatted": (
                format_datetime(saved_business["updated_at"])
                if saved_business and saved_business["updated_at"]
                else None
            ),
        }

    except Error as error:

        connection.rollback()

        print(
            f"Business information database error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save business information. "
                "Please try again."
            ),
        ) from error

    except Exception as error:

        connection.rollback()

        print(
            f"Business information error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save business information. "
                "Please try again."
            ),
        ) from error

    finally:
        cursor.close()
        connection.close()


# =========================================================
# GET BUSINESS INFORMATION
# =========================================================

@router.get(
    "/info",
    response_model=BusinessInfoResponse,
)
def get_business_info(
    authorization: str = Header(...),
):
    """
    Return the authenticated user's business information.
    """

    # -----------------------------------------------------
    # Validate authentication token
    # -----------------------------------------------------

    user_id = get_current_user_id(
        authorization
    )

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                business_id,
                business_name,
                business_type,
                about_business,
                year_established,
                google_review_link,
                updated_at
            FROM business_info
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )

        business = cursor.fetchone()

        # -------------------------------------------------
        # Business profile does not exist yet
        # -------------------------------------------------

        if not business:
            return {
                "success": True,
                "message": "Business information not found.",
                "business_id": None,
                "business_name": None,
                "business_type": None,
                "about_business": None,
                "year_established": None,
                "google_review_link": None,
                "updated_at": None,
                "updated_at_formatted": None,
            }

        # -------------------------------------------------
        # Return business information
        # -------------------------------------------------

        return {
            "success": True,
            "message": "Business information retrieved successfully.",
            "business_id": business["business_id"],
            "business_name": business["business_name"],
            "business_type": business["business_type"],
            "about_business": business["about_business"],
            "year_established": business["year_established"],
            "google_review_link": business["google_review_link"],
            "updated_at": (
                business["updated_at"].isoformat()
                if business["updated_at"]
                else None
            ),
            "updated_at_formatted": (
                format_datetime(business["updated_at"])
                if business["updated_at"]
                else None
            ),
        }

    except Error as error:

        print(
            f"Business information database error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to retrieve business information."
            ),
        ) from error

    except Exception as error:

        print(
            f"Business information error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to retrieve business information."
            ),
        ) from error

    finally:
        cursor.close()
        connection.close()