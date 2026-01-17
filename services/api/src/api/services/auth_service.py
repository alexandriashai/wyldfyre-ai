"""
Authentication service for user management and JWT tokens.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger

from ..config import APIConfig

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # User ID
    email: str
    username: str
    is_admin: bool = False
    exp: datetime
    iat: datetime
    token_type: str = "access"


class TokenPair(BaseModel):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession, config: APIConfig):
        self.db = db
        self.config = config

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self,
        user_id: str,
        email: str,
        username: str,
        is_admin: bool = False,
    ) -> str:
        """Create a JWT access token."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self.config.jwt_access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "email": email,
            "username": username,
            "is_admin": is_admin,
            "exp": expires,
            "iat": now,
            "token_type": "access",
        }

        return jwt.encode(
            payload,
            self.config.jwt_secret_key,
            algorithm=self.config.jwt_algorithm,
        )

    def create_refresh_token(
        self,
        user_id: str,
        email: str,
        username: str,
        is_admin: bool = False,
    ) -> str:
        """Create a JWT refresh token."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self.config.jwt_refresh_token_expire_days)

        payload = {
            "sub": user_id,
            "email": email,
            "username": username,
            "is_admin": is_admin,
            "exp": expires,
            "iat": now,
            "token_type": "refresh",
        }

        return jwt.encode(
            payload,
            self.config.jwt_secret_key,
            algorithm=self.config.jwt_algorithm,
        )

    def create_token_pair(
        self,
        user_id: str,
        email: str,
        username: str,
        is_admin: bool = False,
    ) -> TokenPair:
        """Create both access and refresh tokens."""
        return TokenPair(
            access_token=self.create_access_token(user_id, email, username, is_admin),
            refresh_token=self.create_refresh_token(user_id, email, username, is_admin),
            expires_in=self.config.jwt_access_token_expire_minutes * 60,
        )

    def verify_token(self, token: str, token_type: str = "access") -> TokenPayload:
        """
        Verify and decode a JWT token.

        Args:
            token: The JWT token string
            token_type: Expected token type ("access" or "refresh")

        Returns:
            TokenPayload with decoded claims

        Raises:
            ValueError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm],
            )

            # Verify token type
            if payload.get("token_type") != token_type:
                raise ValueError(f"Invalid token type, expected {token_type}")

            return TokenPayload(
                sub=payload["sub"],
                email=payload["email"],
                username=payload["username"],
                is_admin=payload.get("is_admin", False),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                token_type=payload["token_type"],
            )

        except JWTError as e:
            logger.warning("JWT decode error", error=str(e))
            raise ValueError("Invalid token") from e

    async def get_user_by_email(self, email: str) -> Any | None:
        """Get a user by email address."""
        # Import here to avoid circular imports
        from database.models import User

        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> Any | None:
        """Get a user by ID."""
        from database.models import User

        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Any | None:
        """Get a user by username."""
        from database.models import User

        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        username: str,
        password: str,
        is_admin: bool = False,
    ) -> Any:
        """
        Create a new user.

        Args:
            email: User email
            username: User username
            password: Plain text password (will be hashed)
            is_admin: Whether user is an admin

        Returns:
            Created User object

        Raises:
            ValueError: If email or username already exists
        """
        from database.models import User

        # Check for existing user
        existing = await self.get_user_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        existing = await self.get_user_by_username(username)
        if existing:
            raise ValueError("Username already taken")

        # Create user
        user = User(
            email=email,
            username=username,
            password_hash=self.hash_password(password),
            is_admin=is_admin,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        logger.info("User created", user_id=user.id, username=username)
        return user

    async def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> Any | None:
        """
        Authenticate a user with email and password.

        Args:
            email: User email
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        user = await self.get_user_by_email(email)
        if not user:
            return None

        if not self.verify_password(password, user.password_hash):
            logger.warning("Failed login attempt", email=email)
            return None

        logger.info("User authenticated", user_id=user.id)
        return user
