from __future__ import annotations
import hashlib, os
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import Header, HTTPException
from jose import JWTError, jwt
from app.database import get_db

JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
ADMIN_JWT_EXPIRE_MINUTES = int(os.getenv("ADMIN_JWT_EXPIRE_MINUTES", "480"))
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be configured and contain at least 32 characters.")

def hash_admin_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_admin_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_admin_access_token(admin_user_id: int, role_name: str):
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ADMIN_JWT_EXPIRE_MINUTES)
    payload = {"sub": str(admin_user_id), "admin": True, "role": role_name, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expires_at

def _extract_bearer_token(authorization: str) -> str:
    if not authorization:
        raise HTTPException(401, "Admin authorization header required.")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer admin token required.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, "Admin token is missing.")
    return token

def _decode_admin_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("admin") is not True:
            raise HTTPException(401, "Invalid admin authentication token.")
        admin_id, role = payload.get("sub"), str(payload.get("role") or "").strip()
        if not admin_id or not role:
            raise HTTPException(401, "Invalid admin authentication token.")
        return int(admin_id), role
    except HTTPException:
        raise
    except (JWTError, ValueError, TypeError) as exc:
        raise HTTPException(401, "Invalid or expired admin authentication token.") from exc

def get_current_admin(authorization: str = Header(...)):
    token = _extract_bearer_token(authorization)
    admin_id, token_role = _decode_admin_token(token)
    db, cursor = get_db(), None
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""SELECT au.admin_user_id,au.full_name,au.email,au.is_active,au.last_login_at,
            ar.role_id,ar.role_name,ar.description AS role_description
            FROM admin_user au INNER JOIN admin_role ar ON ar.role_id=au.role_id
            WHERE au.admin_user_id=%s LIMIT 1""", (admin_id,))
        admin = cursor.fetchone()
        if not admin: raise HTTPException(401, "Admin account not found.")
        if not admin["is_active"]: raise HTTPException(403, "This admin account is inactive.")
        cursor.execute("""SELECT admin_token_id FROM admin_auth_token
            WHERE admin_user_id=%s AND token_hash=%s AND is_revoked=FALSE AND expires_at>UTC_TIMESTAMP() LIMIT 1""",
            (admin_id, hash_token(token)))
        if not cursor.fetchone(): raise HTTPException(401, "Admin session is no longer valid.")
        admin["token_role"] = token_role
        return admin
    finally:
        cursor.close(); db.close()

def require_admin_permission(admin: dict, permission_key: str):
    db, cursor = get_db(), None
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""SELECT 1 FROM admin_role_permission arp
            INNER JOIN admin_permission ap ON ap.permission_id=arp.permission_id
            WHERE arp.role_id=%s AND ap.permission_key=%s LIMIT 1""",
            (admin["role_id"], permission_key))
        if not cursor.fetchone():
            raise HTTPException(403, "You do not have permission to perform this action.")
    finally:
        cursor.close(); db.close()

def require_super_admin(admin: dict):
    if admin["role_name"] != "super_admin":
        raise HTTPException(403, "Only the Super Administrator can manage staff.")

def revoke_admin_token(raw_token: str):
    db, cursor = get_db(), None
    cursor = db.cursor()
    try:
        cursor.execute("""UPDATE admin_auth_token SET is_revoked=TRUE,revoked_at=UTC_TIMESTAMP()
            WHERE token_hash=%s AND is_revoked=FALSE""", (hash_token(raw_token),))
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        cursor.close(); db.close()

def extract_raw_admin_token(authorization: str) -> str:
    return _extract_bearer_token(authorization)
