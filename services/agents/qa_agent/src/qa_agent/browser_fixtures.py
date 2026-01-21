"""
Test fixture management for E2E browser testing.

Provides utilities for:
- Test user creation and cleanup
- Database state management
- Test environment setup/teardown
- Consistent test data generation
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_core import get_logger

from .browser_manager import get_browser_manager
from .credential_store import get_credential_store

logger = get_logger(__name__)


@dataclass
class TestUser:
    """Test user data."""

    id: str
    email: str
    username: str
    password: str
    role: str
    created_at: datetime
    extra_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestContext:
    """Test execution context with resources."""

    test_name: str
    browser_id: str | None = None
    context_id: str | None = None
    page_id: str | None = None
    test_users: list[TestUser] = field(default_factory=list)
    created_resources: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class FixtureManager:
    """
    Test fixture management for consistent E2E testing.

    Provides methods for:
    - Creating and cleaning up test users
    - Managing database state
    - Setting up complete test environments
    """

    def __init__(self, db_session_factory=None, api_client=None) -> None:
        """
        Initialize fixture manager.

        Args:
            db_session_factory: Async database session factory
            api_client: HTTP client for API operations
        """
        self._db_session_factory = db_session_factory
        self._api_client = api_client
        self._active_contexts: dict[str, TestContext] = {}

    async def create_test_user(
        self,
        role: str = "user",
        app_name: str = "wyld-web",
        email_prefix: str = "test",
        password: str | None = None,
        extra_data: dict | None = None,
        use_api: bool = True,
    ) -> TestUser:
        """
        Create a test user for E2E testing.

        Args:
            role: User role (admin, user, guest)
            app_name: Application name for credential storage
            email_prefix: Prefix for generated email
            password: Custom password (generated if not provided)
            extra_data: Additional user data
            use_api: If True, create via API; if False, create directly in DB

        Returns:
            TestUser with credentials
        """
        # Generate unique identifiers
        unique_id = str(uuid.uuid4())[:8]
        email = f"{email_prefix}_{unique_id}@test.example.com"
        username = f"{email_prefix}_{unique_id}"
        password = password or f"TestPass_{unique_id}!"

        test_user = TestUser(
            id=unique_id,
            email=email,
            username=username,
            password=password,
            role=role,
            created_at=datetime.now(timezone.utc),
            extra_data=extra_data or {},
        )

        if use_api and self._api_client:
            # Create user via registration API
            try:
                response = await self._api_client.post(
                    "/api/auth/register",
                    json={
                        "email": email,
                        "username": username,
                        "password": password,
                        "role": role,
                        **test_user.extra_data,
                    },
                )
                if response.status_code == 201:
                    user_data = response.json()
                    test_user.id = user_data.get("id", unique_id)
            except Exception as e:
                logger.warning("Failed to create user via API", error=str(e))

        elif self._db_session_factory:
            # Create user directly in database
            try:
                from database.models import User
                from passlib.hash import bcrypt

                async with self._db_session_factory() as session:
                    user = User(
                        id=unique_id,
                        email=email,
                        username=username,
                        password_hash=bcrypt.hash(password),
                        is_active=True,
                        is_admin=(role == "admin"),
                    )
                    session.add(user)
                    await session.commit()
                    test_user.id = user.id
            except Exception as e:
                logger.warning("Failed to create user in DB", error=str(e))

        logger.info(
            "Test user created",
            email=email,
            role=role,
            user_id=test_user.id,
        )

        return test_user

    async def cleanup_test_user(
        self,
        user_id: str,
        use_api: bool = True,
    ) -> bool:
        """
        Clean up a test user.

        Args:
            user_id: User ID to delete
            use_api: Use API for deletion

        Returns:
            True if deleted successfully
        """
        if use_api and self._api_client:
            try:
                response = await self._api_client.delete(f"/api/admin/users/{user_id}")
                return response.status_code == 200
            except Exception as e:
                logger.warning("Failed to delete user via API", user_id=user_id, error=str(e))

        if self._db_session_factory:
            try:
                from database.models import User
                from sqlalchemy import delete

                async with self._db_session_factory() as session:
                    await session.execute(delete(User).where(User.id == user_id))
                    await session.commit()
                    logger.info("Test user deleted", user_id=user_id)
                    return True
            except Exception as e:
                logger.warning("Failed to delete user from DB", user_id=user_id, error=str(e))

        return False

    async def setup_test_environment(
        self,
        test_name: str,
        create_browser: bool = True,
        create_context: bool = True,
        create_page: bool = True,
        browser_type: str = "chromium",
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ) -> TestContext:
        """
        Set up a complete test environment with browser resources.

        Args:
            test_name: Name for this test
            create_browser: Create browser instance
            create_context: Create browser context
            create_page: Create page
            browser_type: Type of browser
            viewport_width: Viewport width
            viewport_height: Viewport height

        Returns:
            TestContext with all resources
        """
        context = TestContext(test_name=test_name)

        if create_browser:
            manager = get_browser_manager()
            context.browser_id = await manager.launch_browser(
                browser_type=browser_type,
                task_id=test_name,
            )

            if create_context:
                context.context_id = await manager.create_context(
                    browser_id=context.browser_id,
                    viewport_width=viewport_width,
                    viewport_height=viewport_height,
                    task_id=test_name,
                )

                if create_page:
                    context.page_id = await manager.new_page(
                        context_id=context.context_id,
                        task_id=test_name,
                    )

        self._active_contexts[test_name] = context

        logger.info(
            "Test environment set up",
            test_name=test_name,
            browser_id=context.browser_id,
            context_id=context.context_id,
            page_id=context.page_id,
        )

        return context

    async def teardown_test_environment(
        self,
        test_context: TestContext,
        cleanup_users: bool = True,
    ) -> None:
        """
        Tear down a test environment and clean up all resources.

        Args:
            test_context: Test context to tear down
            cleanup_users: Clean up test users
        """
        # Clean up test users
        if cleanup_users:
            for user in test_context.test_users:
                await self.cleanup_test_user(user.id)

        # Clean up browser resources
        if test_context.browser_id:
            manager = get_browser_manager()
            await manager.close_browser(test_context.browser_id)

        # Remove from active contexts
        if test_context.test_name in self._active_contexts:
            del self._active_contexts[test_context.test_name]

        logger.info(
            "Test environment torn down",
            test_name=test_context.test_name,
            users_cleaned=len(test_context.test_users),
        )

    async def with_test_user(
        self,
        test_context: TestContext,
        role: str = "user",
        app_name: str = "wyld-web",
        store_credentials: bool = True,
    ) -> TestUser:
        """
        Add a test user to a test context.

        Args:
            test_context: Test context to add user to
            role: User role
            app_name: Application name
            store_credentials: Store credentials in credential store

        Returns:
            Created TestUser
        """
        user = await self.create_test_user(role=role, app_name=app_name)
        test_context.test_users.append(user)

        if store_credentials:
            try:
                store = get_credential_store()
                await store.store_credential(
                    app_name=app_name,
                    credential_type="basic",
                    username=user.email,
                    password=user.password,
                    user_id=user.id,
                    role=role,
                )
            except Exception as e:
                logger.warning("Failed to store test credentials", error=str(e))

        return user

    def get_active_context(self, test_name: str) -> TestContext | None:
        """Get an active test context by name."""
        return self._active_contexts.get(test_name)

    async def cleanup_all(self) -> int:
        """
        Clean up all active test environments.

        Returns:
            Number of environments cleaned up
        """
        count = 0
        for context in list(self._active_contexts.values()):
            await self.teardown_test_environment(context)
            count += 1

        logger.info("All test environments cleaned up", count=count)
        return count


# Singleton fixture manager
_fixture_manager: FixtureManager | None = None


def get_fixture_manager(
    db_session_factory=None,
    api_client=None,
) -> FixtureManager:
    """Get the singleton FixtureManager instance."""
    global _fixture_manager
    if _fixture_manager is None:
        _fixture_manager = FixtureManager(
            db_session_factory=db_session_factory,
            api_client=api_client,
        )
    return _fixture_manager


# Test data generators
class TestDataGenerator:
    """Generate consistent test data."""

    @staticmethod
    def email(prefix: str = "test") -> str:
        """Generate a test email."""
        unique = str(uuid.uuid4())[:8]
        return f"{prefix}_{unique}@test.example.com"

    @staticmethod
    def username(prefix: str = "user") -> str:
        """Generate a test username."""
        unique = str(uuid.uuid4())[:8]
        return f"{prefix}_{unique}"

    @staticmethod
    def password(length: int = 16) -> str:
        """Generate a test password."""
        import secrets
        import string

        chars = string.ascii_letters + string.digits + "!@#$%"
        return "".join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def phone() -> str:
        """Generate a test phone number."""
        import random

        return f"+1555{random.randint(1000000, 9999999)}"

    @staticmethod
    def address() -> dict:
        """Generate a test address."""
        unique = str(uuid.uuid4())[:4]
        return {
            "street": f"123 Test St #{unique}",
            "city": "Testville",
            "state": "TS",
            "zip": "12345",
            "country": "US",
        }

    @staticmethod
    def credit_card_test() -> dict:
        """Generate a test credit card (Stripe test card)."""
        return {
            "number": "4242424242424242",
            "exp_month": "12",
            "exp_year": "2030",
            "cvc": "123",
        }


# Commonly used fixtures
WYLD_FIXTURES = {
    "admin_user": {
        "email": "admin@test.example.com",
        "password": "AdminTestPass123!",
        "role": "admin",
    },
    "regular_user": {
        "email": "user@test.example.com",
        "password": "UserTestPass123!",
        "role": "user",
    },
    "guest_user": {
        "email": "guest@test.example.com",
        "password": "GuestTestPass123!",
        "role": "guest",
    },
}
