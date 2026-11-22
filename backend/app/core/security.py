import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

password_hasher = PasswordHasher()
COMMON_PASSWORDS = {
    "password",
    "password123",
    "1234567890",
    "qwertyuiop",
    "letmein123",
    "admin12345",
}


def validate_password(password: str) -> str:
    if not 10 <= len(password) <= 128:
        raise ValueError("Password must be between 10 and 128 characters")
    if password.casefold() in COMMON_PASSWORDS:
        raise ValueError("Password is too common")
    return password


def hash_password(password: str) -> str:
    return password_hasher.hash(validate_password(password))


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


DUMMY_PASSWORD_HASH = password_hasher.hash("dummy-password-that-is-never-valid")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
