import secrets
import re

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user_id
from app.database import get_db
from app.coin_routes import authorize_usage

from .schemas import WebsiteGenerateRequest
from .website_builder import (
    generate_website_html,
    generate_website_image_queries,
    generate_website_questions,
)
from .image_search import search_website_images


router = APIRouter(
    prefix="/api/your-website",
    tags=["Business Customer Showcase"],
)


# ============================================================
# HELPERS
# ============================================================


def _normalize_color(value: str | None) -> str | None:
    """Normalize an optional hex color. None means AI chooses the color."""
    if value is None:
        return None

    value = str(value).strip().upper()
    if not value:
        return None

    if not re.fullmatch(r"#[0-9A-F]{6}", value):
        raise HTTPException(
            status_code=400,
            detail="Theme colors must be valid 6-digit hex colors such as #1F4E78.",
        )

    return value



def _get_business(
    cursor,
    user_id: int,
) -> dict:
    """
    Get the business information belonging to the
    authenticated user.
    """

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
        ORDER BY business_id ASC
        LIMIT 1
        """,
        (user_id,),
    )

    business = cursor.fetchone()

    if not business:
        raise HTTPException(
            status_code=404,
            detail=(
                "Business information not found. "
                "Please complete Business Info first."
            ),
        )

    return business


def _generate_public_url_id() -> str:
    """
    Generate a short, URL-safe public website identifier.

    Uniqueness is additionally protected by the database
    UNIQUE constraint on website_version.public_url_id.
    """

    return secrets.token_urlsafe(18).replace(
        "-",
        "",
    ).replace(
        "_",
        "",
    )


def _get_website(
    cursor,
    user_id: int,
    business_id: int,
) -> dict | None:
    """
    Get the single website workspace belonging to
    this user and business.

    The website table represents the permanent workspace.
    """

    cursor.execute(
        """
        SELECT
            website_id,
            user_id,
            business_id,
            created_at,
            updated_at
        FROM website
        WHERE user_id = %s
          AND business_id = %s
        LIMIT 1
        """,
        (
            user_id,
            business_id,
        ),
    )

    return cursor.fetchone()


def _get_active_version(
    cursor,
    website_id: int,
) -> dict | None:
    """
    Get the currently active website version.

    The active version is the version currently being
    edited or most recently generated.
    """

    cursor.execute(
        """
        SELECT
            website_version_id,
            website_id,
            version_number,
            public_url_id,
            html_code,
            created_at,
            is_active
        FROM website_version
        WHERE website_id = %s
          AND is_active = TRUE
        ORDER BY website_version_id DESC
        LIMIT 1
        """,
        (website_id,),
    )

    return cursor.fetchone()


def _get_version(
    cursor,
    website_version_id: int,
) -> dict | None:
    """
    Get one website version.
    """

    cursor.execute(
        """
        SELECT
            website_version_id,
            website_id,
            version_number,
            public_url_id,
            html_code,
            created_at,
            is_active
        FROM website_version
        WHERE website_version_id = %s
        LIMIT 1
        """,
        (website_version_id,),
    )

    return cursor.fetchone()


def _serialize_version(
    cursor,
    website_version_id: int,
) -> dict | None:
    """
    Load one complete website version.

    Hierarchy:

        website
            ↓
        website_version
            ↓
        website_question
            ↓
        website_answer
    """

    # --------------------------------------------------------
    # VERSION
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            v.website_version_id,
            v.website_id,
            v.version_number,
            v.public_url_id,
            v.html_code,
            v.color_theme_1,
            v.color_theme_2,
            v.created_at,
            v.is_active,

            w.user_id,
            w.business_id

        FROM website_version AS v

        INNER JOIN website AS w
            ON w.website_id = v.website_id

        WHERE v.website_version_id = %s
        LIMIT 1
        """,
        (website_version_id,),
    )

    version = cursor.fetchone()

    if not version:
        return None

    # --------------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            question_id,
            website_version_id,
            question_order,
            question_key,
            question_text,
            input_type,
            required,
            placeholder,
            helper_text,
            created_at
        FROM website_question
        WHERE website_version_id = %s
        ORDER BY question_order ASC
        """,
        (website_version_id,),
    )

    questions = cursor.fetchall() or []

    # --------------------------------------------------------
    # ANSWERS
    # --------------------------------------------------------

    if questions:

        question_ids = [
            question["question_id"]
            for question in questions
        ]

        placeholders = ", ".join(
            ["%s"] * len(question_ids)
        )

        cursor.execute(
            f"""
            SELECT
                answer_id,
                question_id,
                answer_text,
                created_at,
                updated_at
            FROM website_answer
            WHERE question_id IN ({placeholders})
            """,
            tuple(question_ids),
        )

        answer_rows = cursor.fetchall() or []

    else:
        answer_rows = []

    answers = {
        str(row["question_id"]): row["answer_text"] or ""
        for row in answer_rows
    }

    return {
        **version,
        "questions": questions,
        "answers": answers,
    }


def _create_website_workspace(
    cursor,
    user_id: int,
    business_id: int,
) -> int:
    """
    Create the single website workspace for a business.

    This table does NOT contain public_url_id.
    """

    cursor.execute(
        """
        INSERT INTO website
        (
            user_id,
            business_id
        )
        VALUES
        (
            %s,
            %s
        )
        """,
        (
            user_id,
            business_id,
        ),
    )

    return int(cursor.lastrowid)


def _get_next_version_number(
    cursor,
    website_id: int,
) -> int:
    """
    Return the next version number for a website workspace.
    """

    cursor.execute(
        """
        SELECT
            COALESCE(
                MAX(version_number),
                0
            ) AS latest_version
        FROM website_version
        WHERE website_id = %s
          AND html_code <> ''
        """,
        (website_id,),
    )

    row = cursor.fetchone()

    return int(
        row["latest_version"] or 0
    ) + 1


def _get_draft_version(
    cursor,
    website_id: int,
):
    """Return the single unsaved questionnaire draft, if one exists."""

    cursor.execute(
        """
        SELECT
            website_version_id,
            website_id,
            version_number,
            public_url_id,
            html_code,
            created_at,
            is_active
        FROM website_version
        WHERE website_id = %s
          AND html_code = ''
        ORDER BY website_version_id DESC
        LIMIT 1
        """,
        (website_id,),
    )

    return cursor.fetchone()


def _delete_draft_version(
    cursor,
    website_id: int,
) -> None:
    """Delete questionnaire-only draft versions after publication."""

    cursor.execute(
        """
        DELETE FROM website_version
        WHERE website_id = %s
          AND html_code = ''
        """,
        (website_id,),
    )


def _create_version(
    cursor,
    website_id: int,
    version_number: int,
    public_url_id: str,
    html_code: str,
    color_theme_1: str | None = None,
    color_theme_2: str | None = None,
    is_active: bool = True,
) -> int:
    """
    Create one website version.
    """

    cursor.execute(
        """
        INSERT INTO website_version
        (
            website_id,
            version_number,
            public_url_id,
            html_code,
            color_theme_1,
            color_theme_2,
            is_active
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            website_id,
            version_number,
            public_url_id,
            html_code,
            color_theme_1,
            color_theme_2,
            is_active,
        ),
    )

    return int(cursor.lastrowid)


def _copy_questions(
    cursor,
    source_version_id: int,
    target_version_id: int,
) -> dict[int, int]:
    """
    Copy questions from one version to another.

    Returns:

        {
            old_question_id: new_question_id
        }

    This mapping is important because answers reference
    question_id directly.
    """

    cursor.execute(
        """
        SELECT
            question_id,
            question_order,
            question_key,
            question_text,
            input_type,
            required,
            placeholder,
            helper_text
        FROM website_question
        WHERE website_version_id = %s
        ORDER BY question_order ASC
        """,
        (source_version_id,),
    )

    questions = cursor.fetchall() or []

    question_mapping = {}

    for question in questions:

        cursor.execute(
            """
            INSERT INTO website_question
            (
                website_version_id,
                question_order,
                question_key,
                question_text,
                input_type,
                required,
                placeholder,
                helper_text
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                target_version_id,
                question["question_order"],
                question["question_key"],
                question["question_text"],
                question["input_type"],
                question["required"],
                question["placeholder"],
                question["helper_text"],
            ),
        )

        new_question_id = int(
            cursor.lastrowid
        )

        question_mapping[
            int(question["question_id"])
        ] = new_question_id

    return question_mapping


def _copy_answers(
    cursor,
    source_version_id: int,
    question_mapping: dict[int, int],
) -> None:
    """
    Copy answers from the source version to the
    newly created version.

    The answer is re-linked to the new question_id.
    """

    if not question_mapping:
        return

    source_question_ids = list(
        question_mapping.keys()
    )

    placeholders = ", ".join(
        ["%s"] * len(source_question_ids)
    )

    cursor.execute(
        f"""
        SELECT
            question_id,
            answer_text
        FROM website_answer
        WHERE question_id IN ({placeholders})
        """,
        tuple(source_question_ids),
    )

    answers = cursor.fetchall() or []

    for answer in answers:

        old_question_id = int(
            answer["question_id"]
        )

        new_question_id = question_mapping.get(
            old_question_id
        )

        if not new_question_id:
            continue

        cursor.execute(
            """
            INSERT INTO website_answer
            (
                question_id,
                answer_text
            )
            VALUES
            (
                %s,
                %s
            )
            """,
            (
                new_question_id,
                answer["answer_text"],
            ),
        )


def _deactivate_versions(
    cursor,
    website_id: int,
) -> None:
    """
    Make all previous versions inactive.
    """

    cursor.execute(
        """
        UPDATE website_version
        SET is_active = FALSE
        WHERE website_id = %s
        """,
        (website_id,),
    )


# ============================================================
# GET CURRENT WEBSITE SETUP
# ============================================================


@router.get("")
def get_website_setup(
    user_id: int = Depends(get_current_user_id),
):
    """
    Load the current website workspace.

    IMPORTANT:

    This endpoint never generates AI questions.

    It only reads the currently active website version.
    """

    db = None
    cursor = None

    try:

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # ----------------------------------------------------
        # BUSINESS
        # ----------------------------------------------------

        business = _get_business(
            cursor,
            user_id,
        )

        # ----------------------------------------------------
        # WEBSITE WORKSPACE
        # ----------------------------------------------------

        website = _get_website(
            cursor,
            user_id,
            business["business_id"],
        )

        if not website:

            return {
                "success": True,
                "business": business,
                "website": None,
                "website_version": None,
                "questions": [],
                "answers": {},
            }

        # ----------------------------------------------------
        # ACTIVE VERSION
        # ----------------------------------------------------

        version = _get_active_version(
            cursor,
            website["website_id"],
        )

        if not version:

            return {
                "success": True,
                "business": business,
                "website": website,
                "website_version": None,
                "questions": [],
                "answers": {},
            }

        version = _serialize_version(
            cursor,
            version["website_version_id"],
        )

        return {
            "success": True,
            "business": business,
            "website": website,
            "website_version": version,
            "questions": version["questions"],
            "answers": version["answers"],
        }

    except HTTPException:
        raise

    except Exception as error:

        print(
            f"Website setup loading error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load your website setup. "
                "Please try again."
            ),
        ) from error

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# GENERATE / REGENERATE QUESTIONS
# ============================================================


@router.post("/questions/generate")
def create_website_questions(
    user_id: int = Depends(get_current_user_id),
):
    """Generate or replace the current questionnaire draft.

    Questionnaire drafts are deliberately NOT counted as website versions.
    They use version_number=0 and are removed after a real website is published.
    Published websites therefore remain cleanly numbered 1, 2, 3, ... .
    """

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        business = _get_business(cursor, user_id)
        generated_questions = generate_website_questions(business)

        if not generated_questions:
            raise HTTPException(
                status_code=500,
                detail="AI did not generate any website questions.",
            )

        website = _get_website(
            cursor,
            user_id,
            business["business_id"],
        )

        if not website:
            website_id = _create_website_workspace(
                cursor,
                user_id,
                business["business_id"],
            )
            website = _get_website(
                cursor,
                user_id,
                business["business_id"],
            )
        else:
            website_id = int(website["website_id"])

        # Never create version 1, 2, 3... just because questions changed.
        # Reuse the one questionnaire draft (version 0) whenever possible.
        draft = _get_draft_version(cursor, website_id)

        if draft:
            website_version_id = int(draft["website_version_id"])
            public_url_id = draft["public_url_id"]

            # Keep exactly one draft and normalize it to version 0.
            cursor.execute(
                """
                DELETE FROM website_version
                WHERE website_id = %s
                  AND html_code = ''
                  AND website_version_id <> %s
                """,
                (website_id, website_version_id),
            )

            _deactivate_versions(cursor, website_id)

            cursor.execute(
                """
                UPDATE website_version
                SET
                    version_number = 0,
                    is_active = TRUE
                WHERE website_version_id = %s
                """,
                (website_version_id,),
            )

            cursor.execute(
                """
                DELETE FROM website_question
                WHERE website_version_id = %s
                """,
                (website_version_id,),
            )
        else:
            public_url_id = _generate_public_url_id()
            website_version_id = _create_version(
                cursor=cursor,
                website_id=website_id,
                version_number=0,
                public_url_id=public_url_id,
                html_code="",
                is_active=True,
            )

        for question in generated_questions:
            cursor.execute(
                """
                INSERT INTO website_question
                (
                    website_version_id,
                    question_order,
                    question_key,
                    question_text,
                    input_type,
                    required,
                    placeholder,
                    helper_text
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    website_version_id,
                    question["question_order"],
                    question["question_key"],
                    question["question_text"],
                    question["input_type"],
                    question["required"],
                    question["placeholder"],
                    question["helper_text"],
                ),
            )

        cursor.execute(
            """
            UPDATE website
            SET updated_at = CURRENT_TIMESTAMP
            WHERE website_id = %s
              AND user_id = %s
            """,
            (website_id, user_id),
        )

        db.commit()

        version = _serialize_version(cursor, website_version_id)

        return {
            "success": True,
            "message": "Website questions generated successfully.",
            "business": business,
            "website": website,
            "website_version": version,
            "website_id": website_id,
            "website_version_id": website_version_id,
            "version_number": 0,
            "public_url_id": public_url_id,
            "questions": version["questions"],
            "answers": {},
        }

    except HTTPException:
        if db:
            db.rollback()
        raise
    except Exception as error:
        if db:
            db.rollback()
        print(f"Website question generation error: {error}")
        raise HTTPException(status_code=500, detail=str(error)) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# GENERATE COMPLETE WEBSITE
# ============================================================


@router.post("/generate")
def generate_website(
    request: WebsiteGenerateRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Generate and publish one customer showcase website version.

    Billing architecture:
      1. Validate the request and collect the current questionnaire.
      2. Ask the centralized coin service for a READ-ONLY preflight.
      3. If balance/membership is insufficient, stop before Gemini/Unsplash.
      4. Run expensive AI + image generation with no DB transaction held.
      5. Open a fresh DB transaction.
      6. Create the website version and finalize the SAME centralized
         coin operation atomically.
      7. Commit website data + coin ledger together.

    The feature route does not know coin prices, membership rules, wallet
    locking, or billing error semantics. All of those remain in coin_routes.py.
    """

    # ------------------------------------------------------------------
    # PHASE 1: request validation + BILLING PREFLIGHT
    # ------------------------------------------------------------------
    preflight_db = None
    preflight_cursor = None

    try:
        preflight_db = get_db()
        preflight_cursor = preflight_db.cursor(dictionary=True)

        business = _get_business(preflight_cursor, user_id)

        website = _get_website(
            preflight_cursor,
            user_id,
            business["business_id"],
        )

        if not website:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Customer showcase setup not found. "
                    "Please generate the showcase questions first."
                ),
            )

        website_id = int(website["website_id"])
        active_version = _get_active_version(
            preflight_cursor,
            website_id,
        )

        if not active_version:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No active customer showcase questionnaire exists. "
                    "Please regenerate the questions."
                ),
            )

        active_version_id = int(active_version["website_version_id"])

        preflight_cursor.execute(
            """
            SELECT
                question_id,
                website_version_id,
                question_order,
                question_text,
                question_key,
                input_type,
                required
            FROM website_question
            WHERE website_version_id = %s
            ORDER BY question_order ASC
            """,
            (active_version_id,),
        )
        questions = preflight_cursor.fetchall() or []

        if not questions:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No showcase questions are available. "
                    "Please regenerate the questions first."
                ),
            )

        submitted_answers = {
            int(item.question_id): str(item.answer or "").strip()
            for item in request.answers
            if item.question_id is not None
        }

        answer_map = {
            int(question["question_id"]): submitted_answers.get(
                int(question["question_id"]),
                "",
            )
            for question in questions
        }

        missing_required = [
            int(question["question_id"])
            for question in questions
            if question["required"]
            and not answer_map.get(int(question["question_id"]), "")
        ]

        if missing_required:
            raise HTTPException(
                status_code=400,
                detail="Please answer all required showcase questions.",
            )

        color_theme_1 = _normalize_color(request.color_theme_1)
        color_theme_2 = _normalize_color(request.color_theme_2)

        ai_answers = [
            {
                "question": question["question_text"],
                "answer": answer_map[int(question["question_id"])],
            }
            for question in questions
            if answer_map[int(question["question_id"])]
        ]

        if not ai_answers:
            raise HTTPException(
                status_code=400,
                detail="No showcase answers were provided.",
            )

        # Single source of truth for all coin/balance/membership errors.
        # This function does not deduct anything.
        authorize_usage(
            cursor=preflight_cursor,
            rule_no=2,
            user_id=user_id,
            business_id=int(business["business_id"]),
            phase="preflight",
        )

    except HTTPException:
        raise
    except Exception as error:
        print(f"Website billing preflight error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to authorize website generation.",
        ) from error
    finally:
        if preflight_cursor:
            preflight_cursor.close()
        if preflight_db:
            preflight_db.close()

    # ------------------------------------------------------------------
    # PHASE 2: EXPENSIVE AI / EXTERNAL WORK
    # ------------------------------------------------------------------
    # No database transaction is held while Gemini or Unsplash is running.
    # If the account had insufficient coins, this code is never reached.
    try:
        image_queries = generate_website_image_queries(
            business,
            ai_answers,
        )

        image_assets = search_website_images(
            image_queries,
            max_images=5,
        )

        html_code = generate_website_html(
            business,
            ai_answers,
            image_assets=image_assets,
            color_theme_1=color_theme_1,
            color_theme_2=color_theme_2,
        )

        if not html_code:
            raise RuntimeError(
                "AI returned empty customer showcase HTML."
            )

    except HTTPException:
        raise
    except Exception as error:
        print(f"Website AI generation error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Website generation failed before publication.",
        ) from error

    # ------------------------------------------------------------------
    # PHASE 3: FINAL DB TRANSACTION + AUTHORITATIVE BILLING
    # ------------------------------------------------------------------
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Re-validate the business/workspace ownership immediately before
        # committing the generated version.
        current_business = _get_business(cursor, user_id)

        if int(current_business["business_id"]) != int(
            business["business_id"]
        ):
            raise HTTPException(
                status_code=409,
                detail="Business context changed. Please generate again.",
            )

        current_website = _get_website(
            cursor,
            user_id,
            int(business["business_id"]),
        )

        if not current_website:
            raise HTTPException(
                status_code=404,
                detail="Customer showcase setup no longer exists.",
            )

        current_website_id = int(current_website["website_id"])

        # Ensure the questionnaire version used to build the site still
        # belongs to this workspace.
        source_version = _get_version(
            cursor,
            active_version_id,
        )

        if not source_version or int(source_version["website_id"]) != current_website_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The showcase questionnaire changed while the website "
                    "was being generated. Please generate again."
                ),
            )

        version_number = _get_next_version_number(
            cursor,
            current_website_id,
        )
        public_url_id = _generate_public_url_id()

        _deactivate_versions(
            cursor,
            current_website_id,
        )

        new_version_id = _create_version(
            cursor=cursor,
            website_id=current_website_id,
            version_number=version_number,
            public_url_id=public_url_id,
            html_code=html_code,
            color_theme_1=color_theme_1,
            color_theme_2=color_theme_2,
            is_active=True,
        )

        # ONE canonical billing API.
        #
        # This final call is authoritative and wallet-locked. It protects
        # against concurrent requests spending the same balance while the
        # expensive AI generation was running.
        #
        # Website publication and the coin ledger are committed together.
        coin_charge = authorize_usage(
            cursor=cursor,
            rule_no=2,
            user_id=user_id,
            business_id=int(business["business_id"]),
            reference_id=new_version_id,
            phase="finalize",
        )

        # Store the image metadata used by this exact published version.
        for image in image_assets:
            cursor.execute(
                """
                INSERT INTO website_image_asset
                (
                    website_version_id,
                    provider,
                    provider_image_id,
                    search_query,
                    image_purpose,
                    image_url,
                    source_url,
                    photographer_name,
                    photographer_url,
                    image_width,
                    image_height
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    new_version_id,
                    image.get("provider", "unsplash"),
                    image.get("provider_image_id", ""),
                    image.get("query", ""),
                    image.get("purpose", "section"),
                    image.get("image_url", ""),
                    image.get("source_url", ""),
                    image.get("photographer", ""),
                    image.get("photographer_url", ""),
                    image.get("width") or None,
                    image.get("height") or None,
                ),
            )

        question_mapping = _copy_questions(
            cursor=cursor,
            source_version_id=active_version_id,
            target_version_id=new_version_id,
        )

        if not question_mapping:
            raise RuntimeError(
                "Website version was created without questions."
            )

        for old_question_id, new_question_id in question_mapping.items():
            answer = answer_map.get(old_question_id, "")

            if not answer:
                continue

            cursor.execute(
                """
                INSERT INTO website_answer
                (question_id, answer_text)
                VALUES (%s, %s)
                """,
                (new_question_id, answer),
            )

        # Remove the temporary questionnaire draft only after the published
        # version, answers, image metadata, and billing are all ready.
        cursor.execute(
            """
            DELETE FROM website_version
            WHERE website_version_id = %s
              AND html_code = ''
            """,
            (active_version_id,),
        )

        cursor.execute(
            """
            UPDATE website
            SET updated_at = CURRENT_TIMESTAMP
            WHERE website_id = %s
              AND user_id = %s
            """,
            (current_website_id, user_id),
        )

        db.commit()

        return {
            "success": True,
            "website_id": current_website_id,
            "website_version_id": new_version_id,
            "version_number": version_number,
            "public_url_id": public_url_id,
            "coin_transaction": coin_charge,
            "message": "Website generated successfully.",
        }

    except HTTPException:
        if db:
            db.rollback()
        raise

    except Exception as error:
        if db:
            db.rollback()

        print(f"Website generation persistence error: {error}")

        raise HTTPException(
            status_code=500,
            detail="Website could not be published.",
        ) from error

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# WEBSITE HISTORY
# ============================================================


@router.get("/history")
def get_website_history(
    user_id: int = Depends(get_current_user_id),
):
    """
    Return every generated website version.

    Each website version is treated as one historical
    customer-facing website.

    Draft versions with empty HTML are excluded.
    """

    db = None
    cursor = None

    try:

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # ----------------------------------------------------
        # BUSINESS
        # ----------------------------------------------------

        business = _get_business(
            cursor,
            user_id,
        )

        # ----------------------------------------------------
        # WEBSITE WORKSPACE
        # ----------------------------------------------------

        website = _get_website(
            cursor,
            user_id,
            business["business_id"],
        )

        if not website:

            return {
                "success": True,
                "business": business,
                "websites": [],
                "total": 0,
            }

        # ----------------------------------------------------
        # ALL GENERATED VERSIONS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                w.website_id,
                w.user_id,
                w.business_id,

                v.website_version_id,
                v.version_number,
                v.public_url_id,
                v.html_code,
                v.color_theme_1,
                v.color_theme_2,
                v.created_at,
                v.is_active

            FROM website AS w

            INNER JOIN website_version AS v
                ON v.website_id = w.website_id

            WHERE w.website_id = %s
              AND w.user_id = %s
              AND v.html_code <> ''

            ORDER BY
                v.created_at DESC,
                v.website_version_id DESC
            """,
            (
                website["website_id"],
                user_id,
            ),
        )

        rows = cursor.fetchall() or []

        websites = []

        for row in rows:

            websites.append(
                {
                    "website_id": row[
                        "website_id"
                    ],
                    "website_version_id": row[
                        "website_version_id"
                    ],
                    "version_number": row[
                        "version_number"
                    ],
                    "public_url_id": row[
                        "public_url_id"
                    ],
                    "html_code": row[
                        "html_code"
                    ],
                    "color_theme_1": row["color_theme_1"],
                    "color_theme_2": row["color_theme_2"],
                    "created_at": row[
                        "created_at"
                    ],
                    "is_active": bool(
                        row["is_active"]
                    ),
                    "business_name": business[
                        "business_name"
                    ],
                    "business_type": business[
                        "business_type"
                    ],
                    "about_business": business[
                        "about_business"
                    ],
                    "year_established": business[
                        "year_established"
                    ],
                }
            )

        return {
            "success": True,
            "business": business,
            "websites": websites,
            "total": len(websites),
        }

    except HTTPException:
        raise

    except Exception as error:

        print(
            f"Website history loading error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load website histories."
            ),
        ) from error

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()




# ============================================================
# EDIT EXISTING WEBSITE VERSION
# ============================================================

@router.get("/edit/{website_version_id}")
def get_website_version_for_edit(
    website_version_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Load one owned published version with its saved questions/answers."""

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        version = _serialize_version(cursor, website_version_id)

        if not version or int(version["user_id"]) != int(user_id):
            raise HTTPException(
                status_code=404,
                detail="Customer showcase version not found.",
            )

        if not version.get("html_code"):
            raise HTTPException(
                status_code=400,
                detail="This website version is not available for editing.",
            )

        business = _get_business(cursor, user_id)

        return {
            "success": True,
            "business": business,
            "website_version": version,
            "questions": version["questions"],
            "answers": version["answers"],
        }

    except HTTPException:
        raise
    except Exception as error:
        print(f"Website edit loading error: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to load this website for editing.",
        ) from error
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


@router.post("/edit/{website_version_id}/generate")
def generate_edited_website(
    website_version_id: int,
    request: WebsiteGenerateRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Regenerate and UPDATE exactly the selected website version.

    Version policy for editing:
        V3 edited -> V3 updated
        V4 edited -> V4 updated

    This endpoint NEVER creates a new website_version row.
    The existing version_number and public_url_id remain unchanged.
    """

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # --------------------------------------------------------
        # LOAD + VERIFY THE EXACT VERSION
        # --------------------------------------------------------

        business = _get_business(cursor, user_id)
        source = _serialize_version(cursor, website_version_id)

        if not source or int(source["user_id"]) != int(user_id):
            raise HTTPException(
                status_code=404,
                detail="Customer showcase version not found.",
            )

        questions = source.get("questions") or []

        if not source.get("html_code") or not questions:
            raise HTTPException(
                status_code=400,
                detail="This customer showcase version cannot be edited.",
            )

        # --------------------------------------------------------
        # MERGE SUBMITTED VALUES WITH THE VERSION'S CURRENT VALUES
        #
        # The frontend normally sends every question. Keeping the
        # existing value as fallback also makes the endpoint safe if
        # a future frontend sends only changed fields.
        # --------------------------------------------------------

        submitted = {
            int(item.question_id): str(item.answer or "").strip()
            for item in request.answers
            if item.question_id is not None
        }

        answer_map = {
            int(question["question_id"]): submitted.get(
                int(question["question_id"]),
                str(
                    source["answers"].get(
                        str(question["question_id"]),
                        "",
                    )
                    or ""
                ).strip(),
            )
            for question in questions
        }

        # --------------------------------------------------------
        # VALIDATE REQUIRED VALUES
        # --------------------------------------------------------

        missing_required = [
            int(question["question_id"])
            for question in questions
            if question["required"]
            and not answer_map.get(
                int(question["question_id"]),
                "",
            )
        ]

        if missing_required:
            raise HTTPException(
                status_code=400,
                detail="Please answer all required showcase questions.",
            )

        color_theme_1 = _normalize_color(request.color_theme_1)
        color_theme_2 = _normalize_color(request.color_theme_2)

        ai_answers = [
            {
                "question": question["question_text"],
                "answer": answer_map[
                    int(question["question_id"])
                ],
            }
            for question in questions
            if answer_map[
                int(question["question_id"])
            ]
        ]

        if not ai_answers:
            raise HTTPException(
                status_code=400,
                detail="No showcase answers were provided.",
            )

        # --------------------------------------------------------
        # GENERATE EVERYTHING BEFORE TOUCHING THE DATABASE
        #
        # If Gemini or Unsplash fails, the existing version is left
        # completely untouched.
        # --------------------------------------------------------

        image_queries = generate_website_image_queries(
            business,
            ai_answers,
        )

        image_assets = search_website_images(
            image_queries,
            max_images=5,
        )

        html_code = generate_website_html(
            business,
            ai_answers,
            image_assets=image_assets,
            color_theme_1=color_theme_1,
            color_theme_2=color_theme_2,
        )

        if not html_code:
            raise RuntimeError(
                "AI returned empty customer showcase HTML."
            )

        # --------------------------------------------------------
        # UPDATE THE EXISTING WEBSITE VERSION
        #
        # IMPORTANT:
        # - same website_version_id
        # - same version_number
        # - same public_url_id
        # - same created_at
        # - same history card
        # --------------------------------------------------------

        cursor.execute(
            """
            UPDATE website_version
            SET
                html_code = %s,
                color_theme_1 = %s,
                color_theme_2 = %s
            WHERE website_version_id = %s
              AND website_id = %s
            """,
            (
                html_code,
                color_theme_1,
                color_theme_2,
                website_version_id,
                source["website_id"],
            ),
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "The selected website version could not be updated."
            )

        # --------------------------------------------------------
        # UPDATE EXISTING ANSWERS
        #
        # Questions themselves are intentionally NOT recreated.
        # Their IDs remain stable because answers reference them.
        # --------------------------------------------------------

        for question in questions:
            question_id = int(question["question_id"])
            answer_text = answer_map.get(question_id, "")

            cursor.execute(
                """
                SELECT answer_id
                FROM website_answer
                WHERE question_id = %s
                LIMIT 1
                """,
                (question_id,),
            )

            existing_answer = cursor.fetchone()

            if existing_answer:
                cursor.execute(
                    """
                    UPDATE website_answer
                    SET
                        answer_text = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE answer_id = %s
                    """,
                    (
                        answer_text,
                        existing_answer["answer_id"],
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO website_answer
                    (
                        question_id,
                        answer_text
                    )
                    VALUES
                    (
                        %s,
                        %s
                    )
                    """,
                    (
                        question_id,
                        answer_text,
                    ),
                )

        # --------------------------------------------------------
        # REPLACE ONLY THIS VERSION'S IMAGE METADATA
        #
        # The old image records belong to this same version, so they
        # are replaced without affecting any other history version.
        # --------------------------------------------------------

        cursor.execute(
            """
            DELETE FROM website_image_asset
            WHERE website_version_id = %s
            """,
            (website_version_id,),
        )

        for image in image_assets:
            cursor.execute(
                """
                INSERT INTO website_image_asset
                (
                    website_version_id,
                    provider,
                    provider_image_id,
                    search_query,
                    image_purpose,
                    image_url,
                    source_url,
                    photographer_name,
                    photographer_url,
                    image_width,
                    image_height
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    website_version_id,
                    image.get("provider", "unsplash"),
                    image.get("provider_image_id", ""),
                    image.get("query", ""),
                    image.get("purpose", "section"),
                    image.get("image_url", ""),
                    image.get("source_url", ""),
                    image.get("photographer", ""),
                    image.get("photographer_url", ""),
                    image.get("width") or None,
                    image.get("height") or None,
                ),
            )

        # --------------------------------------------------------
        # UPDATE WORKSPACE TIMESTAMP ONLY
        # --------------------------------------------------------

        cursor.execute(
            """
            UPDATE website
            SET updated_at = CURRENT_TIMESTAMP
            WHERE website_id = %s
              AND user_id = %s
            """,
            (
                source["website_id"],
                user_id,
            ),
        )

        db.commit()

        return {
            "success": True,
            "message": (
                f"V{source['version_number']} updated successfully."
            ),
            "website_id": int(source["website_id"]),
            "website_version_id": int(website_version_id),
            "version_number": int(source["version_number"]),
            "public_url_id": source["public_url_id"],
        }

    except HTTPException:
        if db:
            db.rollback()
        raise

    except Exception as error:
        if db:
            db.rollback()

        print(
            f"Website edit generation error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to update this website version. "
                "The existing version was not changed."
            ),
        ) from error

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# ============================================================
# DELETE SINGLE WEBSITE VERSION
# ============================================================


@router.delete("/version/{website_version_id}")
def delete_website_version(
    website_version_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Delete exactly one published website version.

    Website History displays website_version rows, so deletion is scoped
    to website_version_id rather than the parent website workspace.

    Ownership is verified through:
        website_version -> website -> user_id

    The parent website workspace is NEVER deleted by this endpoint.
    """

    db = None
    cursor = None

    try:

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # --------------------------------------------------------
        # FIND EXACT VERSION + VERIFY OWNERSHIP
        # --------------------------------------------------------

        cursor.execute(
            """
            SELECT
                v.website_version_id,
                v.website_id,
                v.version_number,
                v.is_active
            FROM website_version AS v
            INNER JOIN website AS w
                ON w.website_id = v.website_id
            WHERE v.website_version_id = %s
              AND w.user_id = %s
              AND v.html_code <> ''
            LIMIT 1
            """,
            (
                website_version_id,
                user_id,
            ),
        )

        version = cursor.fetchone()

        if not version:
            raise HTTPException(
                status_code=404,
                detail="Customer showcase version not found.",
            )

        website_id = int(
            version["website_id"]
        )

        was_active = bool(
            version["is_active"]
        )

        # --------------------------------------------------------
        # DELETE ANSWERS FOR THIS VERSION'S QUESTIONS
        # --------------------------------------------------------

        cursor.execute(
            """
            DELETE FROM website_answer
            WHERE question_id IN (
                SELECT question_id
                FROM (
                    SELECT question_id
                    FROM website_question
                    WHERE website_version_id = %s
                ) AS version_questions
            )
            """,
            (
                website_version_id,
            ),
        )

        # --------------------------------------------------------
        # DELETE QUESTIONS
        # --------------------------------------------------------

        cursor.execute(
            """
            DELETE FROM website_question
            WHERE website_version_id = %s
            """,
            (
                website_version_id,
            ),
        )

        # --------------------------------------------------------
        # DELETE IMAGE METADATA FOR THIS VERSION
        # --------------------------------------------------------

        cursor.execute(
            """
            DELETE FROM website_image_asset
            WHERE website_version_id = %s
            """,
            (
                website_version_id,
            ),
        )

        # --------------------------------------------------------
        # DELETE ONLY THIS VERSION
        # --------------------------------------------------------

        cursor.execute(
            """
            DELETE FROM website_version
            WHERE website_version_id = %s
            """,
            (
                website_version_id,
            ),
        )

        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=404,
                detail="Website version could not be deleted.",
            )

        # --------------------------------------------------------
        # MAINTAIN A VALID ACTIVE VERSION
        #
        # If the deleted version was active, make the newest
        # remaining published version active.
        # --------------------------------------------------------

        replacement_version_id = None

        if was_active:

            cursor.execute(
                """
                SELECT
                    website_version_id
                FROM website_version
                WHERE website_id = %s
                  AND html_code <> ''
                ORDER BY
                    created_at DESC,
                    website_version_id DESC
                LIMIT 1
                """,
                (
                    website_id,
                ),
            )

            replacement = cursor.fetchone()

            if replacement:

                replacement_version_id = int(
                    replacement["website_version_id"]
                )

                cursor.execute(
                    """
                    UPDATE website_version
                    SET is_active = TRUE
                    WHERE website_version_id = %s
                    """,
                    (
                        replacement_version_id,
                    ),
                )

        # --------------------------------------------------------
        # UPDATE WORKSPACE TIMESTAMP
        # --------------------------------------------------------

        cursor.execute(
            """
            UPDATE website
            SET updated_at = CURRENT_TIMESTAMP
            WHERE website_id = %s
              AND user_id = %s
            """,
            (
                website_id,
                user_id,
            ),
        )

        db.commit()

        return {
            "success": True,
            "website_version_id": website_version_id,
            "website_id": website_id,
            "replacement_active_version_id": (
                replacement_version_id
            ),
            "message": "Website version deleted successfully.",
        }

    except HTTPException:

        if db:
            db.rollback()

        raise

    except Exception as error:

        if db:
            db.rollback()

        print(
            f"Website version deletion error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to delete this website version."
            ),
        ) from error

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


# ============================================================
# PUBLIC WEBSITE
# ============================================================


@router.get("/public/{public_url_id}")
def get_public_website(
    public_url_id: str,
):
    """
    Load the exact website version identified by
    public_url_id.

    IMPORTANT:

    public_url_id belongs to website_version.

    Therefore the URL always points to one exact
    historical website version.
    """

    db = None
    cursor = None

    try:

        db = get_db()
        cursor = db.cursor(dictionary=True)

        safe_public_url_id = (
            str(public_url_id or "")
            .strip()
        )

        if (
            not safe_public_url_id
            or safe_public_url_id == "undefined"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid public website URL."
                ),
            )

        # ----------------------------------------------------
        # FIND EXACT VERSION
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                v.website_version_id,
                v.website_id,
                v.version_number,
                v.public_url_id,
                v.html_code,
                v.color_theme_1,
                v.color_theme_2,

                w.user_id,
                w.business_id,

                b.business_name,
                b.business_type,
                b.about_business,
                b.year_established

            FROM website_version AS v

            INNER JOIN website AS w
                ON w.website_id = v.website_id

            INNER JOIN business_info AS b
                ON b.business_id = w.business_id

            WHERE v.public_url_id = %s
              AND v.html_code <> ''

            LIMIT 1
            """,
            (safe_public_url_id,),
        )

        version = cursor.fetchone()

        if not version:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Published website not found."
                ),
            )

        # ----------------------------------------------------
        # RETURN EXACT VERSION
        # ----------------------------------------------------

        return {
            "success": True,

            "website_id": version[
                "website_id"
            ],

            "website_version_id": version[
                "website_version_id"
            ],

            "version_number": version[
                "version_number"
            ],

            "public_url_id": version[
                "public_url_id"
            ],

            "business": {
                "business_id": version[
                    "business_id"
                ],
                "business_name": version[
                    "business_name"
                ],
                "business_type": version[
                    "business_type"
                ],
                "about_business": version[
                    "about_business"
                ],
                "year_established": version[
                    "year_established"
                ],
            },

            "html_code": version[
                "html_code"
            ],

            "color_theme_1": version["color_theme_1"],
            "color_theme_2": version["color_theme_2"],
        }

    except HTTPException:
        raise

    except Exception as error:

        print(
            f"Public website loading error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load the public website."
            ),
        ) from error

    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()