from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from .config import GOOGLE_TOKEN_ENCRYPTION_KEY


def _fernet() -> Fernet:
    if not GOOGLE_TOKEN_ENCRYPTION_KEY:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is not configured.")
    try:
        return Fernet(GOOGLE_TOKEN_ENCRYPTION_KEY.encode())
    except Exception as error:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is invalid.") from error


def encrypt_token(token: str) -> str:
    if not token:
        raise ValueError("Token cannot be empty.")
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    if not token:
        raise ValueError("Encrypted token cannot be empty.")
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as error:
        raise HTTPException(
            status_code=500,
            detail="Stored Google authorization data could not be decrypted.",
        ) from error
