from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import Error

from app.database import get_db
from app.auth import get_current_user_id
from app.query_generator import generate_questions

router = APIRouter(
    prefix="/api/query",
    tags=["Query Maker"],
)


def _get_owned_dashboard(cursor, dashboard_id: int, user_id: int):
    cursor.execute(
        """
        SELECT
            d.dashboard_id,
            d.user_id,
            d.business_id,
            d.dashboard_name,
            d.created_at,
            b.business_name,
            b.business_type,
            b.about_business,
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
    return cursor.fetchone()


def _get_business(cursor, user_id: int):
    cursor.execute(
        """
        SELECT
            business_id,
            business_name,
            business_type,
            about_business,
            year_established
        FROM business_info
        WHERE user_id = %s
        LIMIT 1
        """,
        (user_id,),
    )
    return cursor.fetchone()


@router.post("/generate")
def generate_query_questions(
    payload: dict,
    user_id: int = Depends(get_current_user_id),
):
    dashboard_id = payload.get("dashboard_id")

    try:
        dashboard_id = int(dashboard_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="A valid dashboard_id is required.",
        )

    question_count = payload.get("question_count", 4)

    try:
        question_count = int(question_count)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Question count must be a number.",
        )

    if question_count < 2 or question_count > 8:
        raise HTTPException(
            status_code=400,
            detail="Question count must be between 2 and 8.",
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

        questions = generate_questions(
            business_name=dashboard["business_name"],
            business_type=dashboard["business_type"],
            about_business=dashboard["about_business"],
            year_established=dashboard["year_established"],
            question_count=question_count,
        )

        return {
            "success": True,
            "dashboard_id": dashboard_id,
            "questions": questions,
        }

    except HTTPException:
        raise
    except Exception as error:
        print(f"Query generation error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to generate questions.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.get("/questions")
def get_saved_questions(
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
            SELECT
                q.query_id,
                q.dashboard_id,
                q.business_id,
                q.query_text,
                o.option_id,
                o.option_text
            FROM `query` q
            LEFT JOIN `option` o
                ON q.query_id = o.query_id
            WHERE q.dashboard_id = %s
              AND q.user_id = %s
            ORDER BY q.query_id ASC,
                     o.option_id ASC
            """,
            (dashboard_id, user_id),
        )

        rows = cursor.fetchall()
        questions_map = {}

        for row in rows:
            query_id = row["query_id"]

            if query_id not in questions_map:
                questions_map[query_id] = {
                    "query_id": query_id,
                    "dashboard_id": row["dashboard_id"],
                    "business_id": row["business_id"],
                    "question": row["query_text"],
                    "options": [],
                }

            if row["option_id"] is not None:
                questions_map[query_id]["options"].append(
                    {
                        "option_id": row["option_id"],
                        "text": row["option_text"],
                    }
                )

        return {
            "success": True,
            "dashboard": dashboard,
            "questions": list(questions_map.values()),
        }

    except HTTPException:
        raise
    except Error as error:
        print(f"Question loading database error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to load questions.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.post("/questions")
def save_questions(
    payload: dict,
    user_id: int = Depends(get_current_user_id),
):
    dashboard_id = payload.get("dashboard_id")

    try:
        dashboard_id = int(dashboard_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="A valid dashboard_id is required.",
        )

    questions = payload.get("questions")

    if not isinstance(questions, list):
        raise HTTPException(
            status_code=400,
            detail="Questions must be a list.",
        )

    if len(questions) < 2 or len(questions) > 8:
        raise HTTPException(
            status_code=400,
            detail="You must save between 2 and 8 questions.",
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

        for index, question in enumerate(questions, start=1):
            question_text = str(
                question.get("question", "")
            ).strip()

            options = question.get("options")

            if not question_text:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {index} cannot be empty.",
                )

            if len(question_text) > 500:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {index} cannot exceed 500 characters.",
                )

            if not isinstance(options, list) or len(options) < 2:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {index} must have at least 2 options.",
                )

            if len(options) > 8:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {index} cannot have more than 8 options.",
                )

            cleaned_options = [
                str(option).strip()
                for option in options
            ]

            if any(not option for option in cleaned_options):
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {index} contains an empty option.",
                )

            if any(len(option) > 500 for option in cleaned_options):
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {index} has an option exceeding 500 characters.",
                )

        # Replace only this dashboard's questionnaire.
        cursor.execute(
            """
            DELETE FROM `query`
            WHERE dashboard_id = %s
              AND user_id = %s
            """,
            (dashboard_id, user_id),
        )

        saved_questions = []

        for question in questions:
            question_text = str(
                question["question"]
            ).strip()

            cursor.execute(
                """
                INSERT INTO `query`
                (
                    user_id,
                    business_id,
                    dashboard_id,
                    query_text
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    user_id,
                    dashboard["business_id"],
                    dashboard_id,
                    question_text,
                ),
            )

            query_id = cursor.lastrowid
            saved_options = []

            for option in question["options"]:
                option_text = str(option).strip()

                cursor.execute(
                    """
                    INSERT INTO `option`
                    (
                        query_id,
                        option_text
                    )
                    VALUES (%s, %s)
                    """,
                    (
                        query_id,
                        option_text,
                    ),
                )

                saved_options.append(
                    {
                        "option_id": cursor.lastrowid,
                        "text": option_text,
                    }
                )

            saved_questions.append(
                {
                    "query_id": query_id,
                    "dashboard_id": dashboard_id,
                    "question": question_text,
                    "options": saved_options,
                }
            )

        # ---------------------------------------------------------
        # TOUCH DASHBOARD UPDATED TIMESTAMP
        # ---------------------------------------------------------
        # Saving questions/options changes child tables, not the
        # dashboard row itself. Therefore MySQL's ON UPDATE rule
        # does not automatically change dashboard.updated_at.
        cursor.execute(
            """
            UPDATE dashboard
            SET updated_at = CURRENT_TIMESTAMP
            WHERE dashboard_id = %s
              AND user_id = %s
            """,
            (
                dashboard_id,
                user_id,
            ),
        )

        db.commit()

        return {
            "success": True,
            "message": "Questions and options saved successfully.",
            "dashboard_id": dashboard_id,
            "questions": saved_questions,
        }

    except HTTPException:
        if db:
            db.rollback()
        raise
    except Error as error:
        if db:
            db.rollback()

        print(f"MySQL query save error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to save questions.",
        ) from error
    except Exception as error:
        if db:
            db.rollback()

        print(f"Question save error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to save questions.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
