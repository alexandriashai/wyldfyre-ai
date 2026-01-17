"""
FastAPI dependencies for dependency injection.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from ai_messaging import RedisClient, get_redis_client

from .config import APIConfig, get_api_config
from .database import get_db_session
from .services.auth_service import AuthService, TokenPayload

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_config() -> APIConfig:
    """Get API configuration."""
    return get_api_config()


async def get_redis() -> RedisClient:
    """Get Redis client."""
    return await get_redis_client()


async def get_auth_service(
    db: AsyncSession = Depends(get_db_session),
    config: APIConfig = Depends(get_config),
) -> AuthService:
    """Get authentication service."""
    return AuthService(db, config)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPayload | None:
    """
    Get current user from JWT token if provided.

    Returns None if no token is provided (for public endpoints).
    """
    if credentials is None:
        return None

    try:
        payload = auth_service.verify_token(credentials.credentials)
        return payload
    except Exception as e:
        logger.warning("Token verification failed", error=str(e))
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPayload:
    """
    Get current user from JWT token.

    Raises 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = auth_service.verify_token(credentials.credentials)
        return payload
    except Exception as e:
        logger.warning("Token verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_admin_user(
    current_user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """
    Get current user and verify they are an admin.

    Raises 403 if user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


# Type aliases for cleaner dependency injection
ConfigDep = Annotated[APIConfig, Depends(get_config)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
RedisDep = Annotated[RedisClient, Depends(get_redis)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CurrentUserDep = Annotated[TokenPayload, Depends(get_current_user)]
CurrentUserOptionalDep = Annotated[TokenPayload | None, Depends(get_current_user_optional)]
AdminUserDep = Annotated[TokenPayload, Depends(get_current_admin_user)]
