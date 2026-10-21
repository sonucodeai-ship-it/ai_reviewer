from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from mysql.connector import Error

from app.database import get_db
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_id,
    revoke_token,
)
from app.otp_service import (
    generate_otp,
    send_signup_otp,
    get_otp_expiry,
)
from app.schemas import (
    SignupRequest,
    SignupVerifyRequest,
    LoginRequest,
    LoginResponse,
    AuthUserResponse,
    MessageResponse,
)


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


# =========================================================
# SIGNUP - SEND OTP
# =========================================================

@router.post(
    "/signup/send-otp",
    response_model=MessageResponse,
)
def send_signup_otp_api(request: SignupRequest):
    """
    Generate and store a signup OTP, then send it to the
    user's email address.

    Every OTP request is permanently stored in signup_otp
    for signup history and audit purposes.

    Previous OTP records are intentionally NOT deleted.
    """

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:
        # -------------------------------------------------
        # Check whether email already has an account
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE email_id = %s
            LIMIT 1
            """,
            (request.email,),
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="An account with this email already exists.",
            )

        # -------------------------------------------------
        # Check whether mobile already has an account
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE mobile = %s
            LIMIT 1
            """,
            (request.mobile,),
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="An account with this mobile number already exists.",
            )

        # -------------------------------------------------
        # Generate secure 6-digit OTP
        # -------------------------------------------------

        otp = generate_otp()

        # -------------------------------------------------
        # Hash password before storing signup information
        # -------------------------------------------------

        password_hash = hash_password(
            request.password
        )

        # -------------------------------------------------
        # Calculate OTP expiry time
        # -------------------------------------------------

        expires_at = get_otp_expiry()

        # -------------------------------------------------
        # Store OTP permanently
        #
        # IMPORTANT:
        # Do NOT delete previous OTP records.
        #
        # Every signup OTP request gets its own row so that
        # signup activity can be tracked historically.
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO signup_otp (
                email,
                mobile,
                business_name,
                password_hash,
                otp,
                expires_at
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
                request.email,
                request.mobile,
                request.business_name,
                password_hash,
                otp,
                expires_at.replace(tzinfo=None),
            ),
        )

        # -------------------------------------------------
        # Commit OTP history before sending email
        # -------------------------------------------------

        connection.commit()

        # -------------------------------------------------
        # Send OTP email
        # -------------------------------------------------

        send_signup_otp(
            email=request.email,
            business_name=request.business_name,
            otp=otp,
        )

        return {
            "success": True,
            "message": "OTP sent successfully to your email.",
        }

    except HTTPException:
        connection.rollback()
        raise

    except Error as error:
        connection.rollback()

        print(
            f"Signup OTP database error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to process signup. Please try again.",
        ) from error

    except Exception as error:
        connection.rollback()

        print(
            f"Signup OTP error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to send OTP. Please try again.",
        ) from error

    finally:
        cursor.close()
        connection.close()


# =========================================================
# SIGNUP - VERIFY OTP
# =========================================================

@router.post(
    "/signup/verify-otp",
    response_model=MessageResponse,
)
def verify_signup_otp(
    request: SignupVerifyRequest,
):
    """
    Verify the latest OTP for an email address.

    When verification succeeds:

    1. A new user account is created.
    2. The OTP history record is preserved.
    3. The newly created user_id is linked to that OTP record.

    The OTP record is NEVER deleted.
    """

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:
        # -------------------------------------------------
        # Get the latest OTP record for this email
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                email,
                mobile,
                business_name,
                password_hash,
                otp,
                expires_at,
                user_id
            FROM signup_otp
            WHERE email = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (request.email,),
        )

        signup_data = cursor.fetchone()

        # -------------------------------------------------
        # OTP record not found
        # -------------------------------------------------

        if not signup_data:
            raise HTTPException(
                status_code=400,
                detail="OTP not found. Please request a new OTP.",
            )

        # -------------------------------------------------
        # Check whether this OTP has already been used
        # -------------------------------------------------

        if signup_data["user_id"] is not None:
            raise HTTPException(
                status_code=400,
                detail="This signup OTP has already been verified.",
            )

        # -------------------------------------------------
        # Verify OTP
        # -------------------------------------------------

        if signup_data["otp"] != request.otp:
            raise HTTPException(
                status_code=400,
                detail="Invalid OTP.",
            )

        # -------------------------------------------------
        # Check OTP expiry
        # -------------------------------------------------

        expires_at = signup_data["expires_at"]

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        if datetime.now(timezone.utc) >= expires_at:
            raise HTTPException(
                status_code=400,
                detail="OTP has expired. Please request a new OTP.",
            )

        # -------------------------------------------------
        # Check email/mobile again
        #
        # This protects against another account being
        # created between OTP generation and verification.
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE email_id = %s
               OR mobile = %s
            LIMIT 1
            """,
            (
                signup_data["email"],
                signup_data["mobile"],
            ),
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="An account with this email or mobile already exists.",
            )

        # -------------------------------------------------
        # Create user account
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO users (
                email_id,
                business_name,
                mobile,
                password_hash,
                is_active
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                TRUE
            )
            """,
            (
                signup_data["email"],
                signup_data["business_name"],
                signup_data["mobile"],
                signup_data["password_hash"],
            ),
        )

        # -------------------------------------------------
        # Get newly created user ID
        # -------------------------------------------------

        user_id = cursor.lastrowid

        # -------------------------------------------------
        # Link OTP history record to the created user
        #
        # IMPORTANT:
        # The OTP record is NOT deleted.
        #
        # user_id now tells us that this OTP resulted in
        # a successfully created account.
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE signup_otp
            SET user_id = %s
            WHERE id = %s
            """,
            (
                user_id,
                signup_data["id"],
            ),
        )

        # -------------------------------------------------
        # Commit user creation + OTP history update
        # as one database transaction.
        # -------------------------------------------------

        connection.commit()

        return {
            "success": True,
            "message": "Account created successfully. You can now sign in.",
        }

    except HTTPException:
        connection.rollback()
        raise

    except Error as error:
        connection.rollback()

        print(
            f"Signup verification database error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to create account. Please try again.",
        ) from error

    except Exception as error:
        connection.rollback()

        print(
            f"Signup verification error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to verify OTP. Please try again.",
        ) from error

    finally:
        cursor.close()
        connection.close()


# =========================================================
# LOGIN
# =========================================================

@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
):
    """
    Authenticate an existing user and create a JWT token.
    """

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:
        # -------------------------------------------------
        # Find user by email
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                user_id,
                email_id,
                business_name,
                mobile,
                password_hash,
                is_active
            FROM users
            WHERE email_id = %s
            LIMIT 1
            """,
            (request.email,),
        )

        user = cursor.fetchone()

        # -------------------------------------------------
        # User not found
        # -------------------------------------------------

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password.",
            )

        # -------------------------------------------------
        # Check active status
        # -------------------------------------------------

        if not user["is_active"]:
            raise HTTPException(
                status_code=403,
                detail="Your account is inactive.",
            )

        # -------------------------------------------------
        # Verify password
        # -------------------------------------------------

        if not verify_password(
            request.password,
            user["password_hash"],
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password.",
            )

        # -------------------------------------------------
        # Create JWT access token
        # -------------------------------------------------

        token, expires_at = create_access_token(
            user["user_id"]
        )

        # -------------------------------------------------
        # Store JWT token in database
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO auth_token (
                user_id,
                jwt_token,
                expires_at,
                is_revoked
            )
            VALUES (
                %s,
                %s,
                %s,
                FALSE
            )
            """,
            (
                user["user_id"],
                token,
                expires_at.replace(tzinfo=None),
            ),
        )

        connection.commit()

        # -------------------------------------------------
        # Return authentication response
        # -------------------------------------------------

        return {
            "success": True,
            "message": "Login successful.",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": user["user_id"],
                "email_id": user["email_id"],
                "business_name": user["business_name"],
                "mobile": user["mobile"],
                "is_active": bool(user["is_active"]),
            },
        }

    except HTTPException:
        connection.rollback()
        raise

    except Error as error:
        connection.rollback()

        print(
            f"Login database error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to login. Please try again.",
        ) from error

    except Exception as error:
        connection.rollback()

        print(
            f"Login error: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to login. Please try again.",
        ) from error

    finally:
        cursor.close()
        connection.close()


# =========================================================
# CURRENT USER
# =========================================================

@router.get(
    "/me",
    response_model=AuthUserResponse,
)
def get_me(
    authorization: str = Header(...),
):
    """
    Return the currently authenticated user's information.
    """

    # -----------------------------------------------------
    # Validate JWT and get user ID
    # -----------------------------------------------------

    user_id = get_current_user_id(
        authorization
    )

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:
        # -------------------------------------------------
        # Fetch user
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                user_id,
                email_id,
                business_name,
                mobile,
                is_active
            FROM users
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found.",
            )

        return {
            "user_id": user["user_id"],
            "email_id": user["email_id"],
            "business_name": user["business_name"],
            "mobile": user["mobile"],
            "is_active": bool(user["is_active"]),
        }

    finally:
        cursor.close()
        connection.close()


# =========================================================
# LOGOUT
# =========================================================

@router.post(
    "/logout",
    response_model=MessageResponse,
)
def logout(
    authorization: str = Header(...),
):
    """
    Revoke the current JWT token.
    """

    # -----------------------------------------------------
    # Validate Authorization header
    # -----------------------------------------------------

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Bearer token required.",
        )

    # -----------------------------------------------------
    # Extract token
    # -----------------------------------------------------

    token = authorization.split(
        " ",
        1,
    )[1].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication token required.",
        )

    # -----------------------------------------------------
    # Revoke token
    # -----------------------------------------------------

    revoke_token(token)

    return {
        "success": True,
        "message": "Logout successful.",
    }
