from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import Error
import secrets

from app.database import get_db
from app.auth import get_current_user_id
from app.main import format_datetime

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboards"],
)


def _get_business(cursor, user_id: int):
    cursor.execute(
        """
        SELECT
            business_id,
            business_name,
            business_type,
            year_established
        FROM business_info
        WHERE user_id = %s
        LIMIT 1
        """,
        (user_id,),
    )
    return cursor.fetchone()


def _get_owned_dashboard(cursor, dashboard_id: int, user_id: int):
    cursor.execute(
        """
        SELECT
            d.dashboard_id,
            d.user_id,
            d.public_url_id,
            d.business_id,
            d.dashboard_name,
            d.created_at,
            d.updated_at,
            b.business_name,
            b.business_type,
            b.year_established
        FROM dashboard d
        INNER JOIN business_info b
            ON b.business_id = d.business_id
        WHERE d.dashboard_id = %s
          AND d.user_id = %s
        LIMIT 1
        """,
        (dashboard_id, user_id),
    )
    dashboard = cursor.fetchone()

    if dashboard:
        dashboard["updated_at_formatted"] = format_datetime(
            dashboard.get("updated_at")
        )

    return dashboard


@router.get("")
def list_dashboards(
    user_id: int = Depends(get_current_user_id),
):
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        business = _get_business(cursor, user_id)
        if not business:
            raise HTTPException(
                status_code=404,
                detail="Business information not found.",
            )

        cursor.execute(
            """
            SELECT
                d.dashboard_id,
                d.public_url_id,
                d.user_id,
                d.business_id,
                d.dashboard_name,
                d.created_at,
                d.updated_at,
                COUNT(DISTINCT q.query_id) AS question_count,
                COUNT(DISTINCT r.review_id) AS review_count
            FROM dashboard d
            LEFT JOIN `query` q
                ON q.dashboard_id = d.dashboard_id
            LEFT JOIN `review` r
                ON r.dashboard_id = d.dashboard_id
            WHERE d.user_id = %s
              AND d.business_id = %s
            GROUP BY
                d.dashboard_id,
                d.public_url_id,
                d.user_id,
                d.business_id,
                d.dashboard_name,
                d.created_at,
                d.updated_at
            ORDER BY d.created_at ASC, d.dashboard_id ASC
            """,
            (user_id, business["business_id"]),
        )

        dashboards = cursor.fetchall()

        for dashboard in dashboards:
            dashboard["updated_at_formatted"] = format_datetime(
                dashboard.get("updated_at")
            )

        return {
            "success": True,
            "business": business,
            "dashboards": dashboards,
        }

    except HTTPException:
        raise
    except Error as error:
        print(f"Dashboard list database error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to load dashboards.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.post("")
def create_dashboard(
    payload: dict,
    user_id: int = Depends(get_current_user_id),
):
    dashboard_name = str(payload.get("dashboard_name", "")).strip()

    if len(dashboard_name) < 2 or len(dashboard_name) > 150:
        raise HTTPException(
            status_code=400,
            detail="Dashboard name must be between 2 and 150 characters.",
        )

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        business = _get_business(cursor, user_id)
        if not business:
            raise HTTPException(
                status_code=404,
                detail="Business information not found.",
            )

        cursor.execute(
            """
            SELECT dashboard_id
            FROM dashboard
            WHERE user_id = %s
              AND business_id = %s
              AND dashboard_name = %s
            LIMIT 1
            """,
            (user_id, business["business_id"], dashboard_name),
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="A dashboard with this name already exists.",
            )

        public_url_id = secrets.token_hex(16)

        cursor.execute(
            """
            INSERT INTO dashboard
            (
                public_url_id,
                user_id,
                business_id,
                dashboard_name
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                public_url_id,
                user_id,
                business["business_id"],
                dashboard_name,
            ),
        )

        dashboard_id = cursor.lastrowid
        db.commit()

        dashboard = _get_owned_dashboard(
            cursor,
            dashboard_id,
            user_id,
        )

        return {
            "success": True,
            "message": "Dashboard created successfully.",
            "dashboard": dashboard,
        }

    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as error:
        if db:
            db.rollback()

        if getattr(error, "errno", None) == 1062:
            raise HTTPException(
                status_code=409,
                detail="A dashboard with this name already exists.",
            ) from error

        print(f"Dashboard creation database error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to create dashboard.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()



@router.get("/public/{public_url_id}")
def get_public_dashboard(public_url_id: str):
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                d.dashboard_id,
                d.public_url_id,
                d.business_id,
                d.dashboard_name,
                d.created_at,
                b.business_name,
                b.business_type,
                b.year_established,
                b.google_review_link
            FROM dashboard d
            INNER JOIN business_info b
                ON b.business_id = d.business_id
            WHERE d.public_url_id = %s
            LIMIT 1
            """,
            (public_url_id,),
        )

        dashboard = cursor.fetchone()

        if not dashboard:
            raise HTTPException(
                status_code=404,
                detail="Dashboard not found.",
            )

        cursor.execute(
            """
            SELECT COUNT(*) AS question_count
            FROM `query`
            WHERE dashboard_id = %s
            """,
            (dashboard["dashboard_id"],),
        )

        dashboard["question_count"] = cursor.fetchone()["question_count"]

        return {
            "success": True,
            "dashboard": dashboard,
        }

    except HTTPException:
        raise

    except Error as error:
        print(f"Public dashboard retrieval error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to load dashboard.",
        ) from error

    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()





@router.get("/public/{public_url_id}/questions")
def get_public_dashboard_questions(public_url_id: str):
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT dashboard_id
            FROM dashboard
            WHERE public_url_id = %s
            LIMIT 1
            """,
            (public_url_id,),
        )

        dashboard = cursor.fetchone()

        if not dashboard:
            raise HTTPException(
                status_code=404,
                detail="Dashboard not found.",
            )

        dashboard_id = dashboard["dashboard_id"]

        cursor.execute(
            """
            SELECT
                q.query_id,
                q.query_text
            FROM `query` q
            WHERE q.dashboard_id = %s
            ORDER BY q.query_id ASC
            """,
            (dashboard_id,),
        )

        questions = cursor.fetchall()

        for question in questions:
            cursor.execute(
                """
                SELECT
                    option_id,
                    option_text
                FROM `option`
                WHERE query_id = %s
                ORDER BY option_id ASC
                """,
                (question["query_id"],),
            )

            options = cursor.fetchall()

            question["question"] = question.pop("query_text")
            question["options"] = [
                {
                    "option_id": option["option_id"],
                    "text": option["option_text"],
                }
                for option in options
            ]

        return {
            "success": True,
            "questions": questions,
        }

    except HTTPException:
        raise

    except Error as error:
        print(f"Public questions retrieval error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to load questions.",
        ) from error

    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()




@router.get("/{dashboard_id}/history")
def get_dashboard_review_history(
    dashboard_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Return all reviews belonging to an authenticated user's dashboard.

    Ownership is verified before any review records are returned.
    """
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        dashboard = _get_owned_dashboard(
            cursor,
            dashboard_id,
            user_id,
        )

        if not dashboard:
            raise HTTPException(
                status_code=404,
                detail="Dashboard not found.",
            )

        cursor.execute(
            """
            SELECT
                review_id,
                review_text,
                created_time,
                submit_status,
                regenerate_status
            FROM `review`
            WHERE dashboard_id = %s
            ORDER BY created_time DESC, review_id DESC
            """,
            (dashboard_id,),
        )

        reviews = cursor.fetchall()

        for review in reviews:
            review["created_time_formatted"] = format_datetime(
                review.get("created_time")
            )

        return {
            "success": True,
            "dashboard_id": dashboard_id,
            "reviews": reviews,
        }

    except HTTPException:
        raise
    except Error as error:
        print(f"Review history database error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to load review history.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.get("/{dashboard_id}")
def get_dashboard(
    dashboard_id: int,
    user_id: int = Depends(get_current_user_id),
):
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        dashboard = _get_owned_dashboard(
            cursor,
            dashboard_id,
            user_id,
        )

        if not dashboard:
            raise HTTPException(
                status_code=404,
                detail="Dashboard not found.",
            )

        cursor.execute(
            """
            SELECT COUNT(*) AS question_count
            FROM `query`
            WHERE dashboard_id = %s
            """,
            (dashboard_id,),
        )

        dashboard["question_count"] = cursor.fetchone()["question_count"]

        return {
            "success": True,
            "dashboard": dashboard,
        }

    except HTTPException:
        raise
    except Error as error:
        print(f"Dashboard retrieval database error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to load dashboard.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.put("/{dashboard_id}")
def rename_dashboard(
    dashboard_id: int,
    payload: dict,
    user_id: int = Depends(get_current_user_id),
):
    dashboard_name = str(payload.get("dashboard_name", "")).strip()

    if len(dashboard_name) < 2 or len(dashboard_name) > 150:
        raise HTTPException(
            status_code=400,
            detail="Dashboard name must be between 2 and 150 characters.",
        )

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        dashboard = _get_owned_dashboard(
            cursor,
            dashboard_id,
            user_id,
        )

        if not dashboard:
            raise HTTPException(
                status_code=404,
                detail="Dashboard not found.",
            )

        cursor.execute(
            """
            SELECT dashboard_id
            FROM dashboard
            WHERE user_id = %s
              AND business_id = %s
              AND dashboard_name = %s
              AND dashboard_id <> %s
            LIMIT 1
            """,
            (
                user_id,
                dashboard["business_id"],
                dashboard_name,
                dashboard_id,
            ),
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="A dashboard with this name already exists.",
            )

        cursor.execute(
            """
            UPDATE dashboard
            SET dashboard_name = %s
            WHERE dashboard_id = %s
              AND user_id = %s
            """,
            (
                dashboard_name,
                dashboard_id,
                user_id,
            ),
        )

        db.commit()

        dashboard = _get_owned_dashboard(
            cursor,
            dashboard_id,
            user_id,
        )

        return {
            "success": True,
            "message": "Dashboard renamed successfully.",
            "dashboard": dashboard,
        }

    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as error:
        if db:
            db.rollback()

        if getattr(error, "errno", None) == 1062:
            raise HTTPException(
                status_code=409,
                detail="A dashboard with this name already exists.",
            ) from error

        print(f"Dashboard rename database error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to rename dashboard.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.delete("/{dashboard_id}")
def delete_dashboard(
    dashboard_id: int,
    user_id: int = Depends(get_current_user_id),
):
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        dashboard = _get_owned_dashboard(
            cursor,
            dashboard_id,
            user_id,
        )

        if not dashboard:
            raise HTTPException(
                status_code=404,
                detail="Dashboard not found.",
            )

        cursor.execute(
            """
            DELETE FROM dashboard
            WHERE dashboard_id = %s
              AND user_id = %s
            """,
            (dashboard_id, user_id),
        )

        db.commit()

        return {
            "success": True,
            "message": "Dashboard deleted successfully.",
        }

    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as error:
        if db:
            db.rollback()

        print(f"Dashboard deletion database error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete dashboard.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()