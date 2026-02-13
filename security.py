from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.
    """
    # Truncate password to 72 characters to match bcrypt's limit
    truncated_password = plain_password[:72]
    return pwd_context.verify(truncated_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password.
    """
    # Truncate password to 72 characters to match bcrypt's limit
    truncated_password = password[:72]
    return pwd_context.hash(truncated_password)
