import os
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal

SECRET_KEY = os.environ.get("SECRET_KEY", "honmonit-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a random API key."""
    return secrets.token_urlsafe(32)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def extract_token_from_header(authorization: str) -> Optional[str]:
    """Extract token from Authorization header."""
    try:
        scheme, token = authorization.split()
        if scheme.lower() == "bearer":
            return token
    except ValueError:
        pass
    return None
