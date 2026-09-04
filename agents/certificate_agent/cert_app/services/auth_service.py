from datetime import datetime, timedelta
from typing import Optional
import hashlib
import hmac

import bcrypt
from jose import JWTError, jwt

from cert_app.config import get_settings
from cert_app.db.database import get_connection

settings = get_settings()


def _prepare_password(password: str) -> bytes:
    """Pre-hash password with SHA-256 to safely handle any length before bcrypt."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def get_password_hash(password: str) -> str:
    hashed = bcrypt.hashpw(_prepare_password(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prepare_password(plain), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def register_user(name: str, email: str, password: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            raise ValueError("Email already registered")

        hashed = get_password_hash(password)
        cursor.execute(
            "INSERT INTO users (name, email, hashed_password) VALUES (%s, %s, %s)",
            (name, email, hashed)
        )
        conn.commit()
        uid = cursor.lastrowid
        cursor.execute("SELECT id, name, email, is_active, created_at FROM users WHERE id = %s", (uid,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s AND is_active = TRUE", (email,))
        user = cursor.fetchone()
        if not user or not verify_password(password, user["hashed_password"]):
            return None
        return user
    finally:
        cursor.close()
        conn.close()
