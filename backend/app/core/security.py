import bcrypt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from backend.app.core.config import settings

ALGORITHM = "HS256"

def get_password_hash(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

def create_access_token(subject: str, expires_delta: timedelta = None) -> str:
    """Generates a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"sub": subject, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def generate_raw_token() -> str:
    """Generates a cryptographically secure random token (e.g., for invites/resets)."""
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    """Computes a SHA-256 hash of a raw token."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
