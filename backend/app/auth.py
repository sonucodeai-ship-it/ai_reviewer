import os
from datetime import datetime, timedelta

from fastapi import Header, HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_db
from app.main import ensure_utc, now_utc


# =========================================================
# CONFIGURATION
# =========================================================

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

JWT_EXPIRE_MINUTES = int(
    os.getenv("JWT_EXPIRE_MINUTES", "1440")
)


# JWT secret must be sufficiently strong.
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET must be configured and contain at least 32 characters."
    )


# =========================================================
# PASSWORD HASHING
# =========================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        password: Plain-text password.

    Returns:
        Secure bcrypt password hash.
    """

    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify a plain-text password against a stored hash.

    Args:
        plain_password: Password entered by the user.
        hashed_password: Password hash stored in the database.

    Returns:
        True if the password matches, otherwise False.
    """

    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


# =========================================================
# JWT TOKEN MANAGEMENT
# =========================================================

def create_access_token(
    user_id: int,
) -> tuple[str, datetime]:
    """
    Create a JWT access token for an authenticated user.

    Args:
        user_id: Database ID of the authenticated user.

    Returns:
        Tuple containing:
        - JWT token
        - UTC expiration datetime
    """

    expires_at = now_utc() + timedelta(
        minutes=JWT_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    return token, expires_at


def decode_access_token(token: str) -> int:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string.

    Returns:
        User ID stored in the token.

    Raises:
        HTTPException: If the token is invalid or expired.
    """

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token.",
            )

        return int(user_id)

    except (JWTError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        ) from error


# =========================================================
# CURRENT USER AUTHENTICATION
# =========================================================

def get_current_user_id(
    authorization: str = Header(...),
) -> int:
    """
    Validate the Authorization header and return the
    authenticated user's ID.

    Expected format:

        Authorization: Bearer <JWT_TOKEN>
    """

    # -----------------------------------------------------
    # Validate Authorization header
    # -----------------------------------------------------

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required.",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Bearer token required.",
        )

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
    # Decode JWT
    # -----------------------------------------------------

    user_id = decode_access_token(token)

    # -----------------------------------------------------
    # Verify token against database
    # -----------------------------------------------------

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                u.user_id,
                u.is_active,
                t.is_revoked,
                t.expires_at
            FROM auth_token AS t
            INNER JOIN users AS u
                ON u.user_id = t.user_id
            WHERE t.jwt_token = %s
              AND t.user_id = %s
            LIMIT 1
            """,
            (
                token,
                user_id,
            ),
        )

        token_data = cursor.fetchone()

        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="Authentication token not found.",
            )

        # -------------------------------------------------
        # Check token revocation
        # -------------------------------------------------

        if token_data["is_revoked"]:
            raise HTTPException(
                status_code=401,
                detail="Authentication token has been revoked.",
            )

        # -------------------------------------------------
        # Check user account status
        # -------------------------------------------------

        if not token_data["is_active"]:
            raise HTTPException(
                status_code=401,
                detail="User account is inactive.",
            )

        # -------------------------------------------------
        # Check database token expiry
        # -------------------------------------------------

        expires_at = ensure_utc(token_data["expires_at"])

        if expires_at is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication token expiry is invalid.",
            )

        if now_utc() >= expires_at:
            raise HTTPException(
                status_code=401,
                detail="Authentication token has expired.",
            )

        return user_id

    finally:
        cursor.close()
        connection.close()


# =========================================================
# TOKEN REVOCATION / LOGOUT
# =========================================================

def revoke_token(token: str) -> None:
    """
    Revoke a JWT token in the database.

    Args:
        token: JWT token to revoke.
    """

    connection = get_db()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE auth_token
            SET is_revoked = TRUE
            WHERE jwt_token = %s
            """,
            (token,),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()