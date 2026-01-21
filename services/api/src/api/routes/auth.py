"""
Authentication routes.
"""

from fastapi import APIRouter, Cookie, Header, HTTPException, Response, status

from ai_core import get_logger

from ..dependencies import AuthServiceDep, CurrentUserDep, CurrentUserOptionalDep
from ..schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    SuccessResponse,
    UpdatePasswordRequest,
    UpdateProfileRequest,
    UserResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _generate_username_from_email(email: str) -> str:
    """Generate a username from an email address."""
    import re
    import uuid

    # Take the part before @ and sanitize it
    local_part = email.split("@")[0]
    # Remove any characters that don't match the username pattern
    username = re.sub(r"[^a-zA-Z0-9_-]", "", local_part)
    # Ensure minimum length
    if len(username) < 3:
        username = username + str(uuid.uuid4().hex[:6])
    # Truncate to max length
    return username[:50]


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    auth_service: AuthServiceDep,
) -> LoginResponse:
    """
    Register a new user.

    Returns access and refresh tokens on successful registration.
    Username is optional - if not provided, it will be derived from email.
    """
    try:
        # Generate username from email if not provided
        username = request.username
        if not username:
            username = _generate_username_from_email(request.email)
            # If the generated username is taken, append a random suffix
            existing = await auth_service.get_user_by_username(username)
            if existing:
                import uuid

                username = f"{username[:44]}_{uuid.uuid4().hex[:5]}"

        user = await auth_service.create_user(
            email=request.email,
            username=username,
            password=request.password,
            display_name=request.display_name,
        )

        tokens = auth_service.create_token_pair(
            user_id=user.id,
            email=user.email,
            username=user.username,
            is_admin=user.is_admin,
        )

        return LoginResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
            user=UserResponse.model_validate(user),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    auth_service: AuthServiceDep,
) -> LoginResponse:
    """
    Authenticate user and return tokens.
    """
    user = await auth_service.authenticate_user(
        email=request.email,
        password=request.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    tokens = auth_service.create_token_pair(
        user_id=user.id,
        email=user.email,
        username=user.username,
        is_admin=user.is_admin,
    )

    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    request: RefreshRequest,
    auth_service: AuthServiceDep,
) -> LoginResponse:
    """
    Refresh access token using refresh token.
    """
    try:
        # Verify refresh token
        payload = auth_service.verify_token(request.refresh_token, token_type="refresh")

        # Get user to ensure they still exist and get latest data
        user = await auth_service.get_user_by_id(payload.sub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Create new token pair
        tokens = auth_service.create_token_pair(
            user_id=user.id,
            email=user.email,
            username=user.username,
            is_admin=user.is_admin,
        )

        return LoginResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
            user=UserResponse.model_validate(user),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/logout")
async def logout(
    current_user: CurrentUserDep,
) -> dict[str, str]:
    """
    Logout user (client should discard tokens).

    Note: JWT tokens are stateless, so this endpoint just acknowledges
    the logout. The client is responsible for discarding tokens.
    For true token invalidation, implement a token blacklist.
    """
    logger.info("User logged out", user_id=current_user.sub)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> UserResponse:
    """
    Get current authenticated user information.
    """
    user = await auth_service.get_user_by_id(current_user.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> UserResponse:
    """
    Update current user's profile.
    """
    try:
        user = await auth_service.update_profile(
            user_id=current_user.sub,
            display_name=request.display_name,
        )
        return UserResponse.model_validate(user)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/password", response_model=SuccessResponse)
async def update_password(
    request: UpdatePasswordRequest,
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> SuccessResponse:
    """
    Update current user's password.
    """
    try:
        await auth_service.update_password(
            user_id=current_user.sub,
            current_password=request.current_password,
            new_password=request.new_password,
        )
        return SuccessResponse(message="Password updated successfully")

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/validate", include_in_schema=False)
async def validate_token(
    response: Response,
    current_user: CurrentUserOptionalDep,
    auth_token: str | None = Cookie(None, alias="auth_token"),
    authorization: str | None = Header(None),
) -> Response:
    """
    Validate authentication token for nginx auth_request.

    Used by nginx to validate tokens and get user info for SSO.
    Returns 200 with X-Auth-User header if valid, 401 if not.

    Checks both:
    - Authorization header (Bearer token)
    - auth_token cookie
    """
    if current_user:
        # User is authenticated - return success with user info headers
        response.status_code = 200
        response.headers["X-Auth-User"] = current_user.email
        response.headers["X-Auth-User-Id"] = current_user.sub
        response.headers["X-Auth-Username"] = current_user.username or current_user.email
        response.headers["X-Auth-Is-Admin"] = "true" if current_user.is_admin else "false"
        return response

    # Not authenticated
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
