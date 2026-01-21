"""
Browser automation configuration constants for the QA Agent.

Provides default settings for Playwright browser automation,
resource limits, and common selectors for wyld-core applications.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BrowserType(str, Enum):
    """Supported browser types."""

    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class WaitState(str, Enum):
    """Page wait states for navigation."""

    LOAD = "load"
    DOMCONTENTLOADED = "domcontentloaded"
    NETWORKIDLE = "networkidle"
    COMMIT = "commit"


@dataclass(frozen=True)
class BrowserResourceLimits:
    """Resource limits for browser pool management."""

    max_browsers: int = 3
    max_contexts_per_browser: int = 5
    max_pages_per_context: int = 10
    browser_timeout: int = 300  # 5 min idle before cleanup
    context_timeout: int = 180  # 3 min idle before cleanup
    page_timeout: int = 60  # 1 min idle before cleanup
    max_memory_mb: int = 2048
    cleanup_interval: int = 30  # Run cleanup every 30 seconds


@dataclass(frozen=True)
class BrowserDefaults:
    """Default browser launch and page options."""

    default_browser: str = "chromium"
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    default_timeout: int = 30000  # 30 seconds in milliseconds
    navigation_timeout: int = 30000
    action_timeout: int = 5000
    slow_mo: int = 0  # Slow down operations by this many ms
    ignore_https_errors: bool = False
    locale: str = "en-US"
    timezone: str = "America/New_York"
    color_scheme: str = "light"
    device_scale_factor: float = 1.0


@dataclass(frozen=True)
class ScreenshotDefaults:
    """Default screenshot options."""

    full_page: bool = False
    output_dir: str = "/tmp/qa_screenshots"
    format: str = "png"  # png or jpeg
    quality: int = 80  # For JPEG only (0-100)
    animations: str = "disabled"  # disabled or allow
    caret: str = "hide"  # hide or initial


@dataclass(frozen=True)
class VideoDefaults:
    """Default video recording options."""

    output_dir: str = "/tmp/qa_videos"
    width: int = 1280
    height: int = 720


@dataclass(frozen=True)
class TraceDefaults:
    """Default trace options."""

    output_dir: str = "/tmp/qa_traces"
    screenshots: bool = True
    snapshots: bool = True
    sources: bool = True


@dataclass
class WyldSelectors:
    """Common selectors for wyld-core web applications."""

    # Authentication
    LOGIN_EMAIL: str = "[data-testid='email-input']"
    LOGIN_PASSWORD: str = "[data-testid='password-input']"
    LOGIN_SUBMIT: str = "[data-testid='login-button']"
    LOGOUT_BUTTON: str = "[data-testid='logout-button']"

    # Registration
    REGISTER_NAME: str = "[data-testid='name-input']"
    REGISTER_EMAIL: str = "[data-testid='email-input']"
    REGISTER_PASSWORD: str = "[data-testid='password-input']"
    REGISTER_CONFIRM: str = "[data-testid='confirm-password-input']"
    REGISTER_SUBMIT: str = "[data-testid='register-button']"

    # Chat interface
    CHAT_INPUT: str = "[data-testid='chat-input']"
    SEND_BUTTON: str = "[data-testid='send-button']"
    MESSAGE_LIST: str = "[data-testid='message-list']"
    MESSAGE_ITEM: str = "[data-testid='message-item']"

    # Navigation
    NAV_HOME: str = "[data-testid='nav-home']"
    NAV_PROJECTS: str = "[data-testid='nav-projects']"
    NAV_SETTINGS: str = "[data-testid='nav-settings']"
    NAV_PROFILE: str = "[data-testid='nav-profile']"

    # Common UI elements
    LOADING_SPINNER: str = "[data-testid='loading-spinner']"
    TOAST_MESSAGE: str = "[data-testid='toast-message']"
    TOAST_SUCCESS: str = "[data-testid='toast-success']"
    TOAST_ERROR: str = "[data-testid='toast-error']"
    MODAL_OVERLAY: str = "[data-testid='modal-overlay']"
    MODAL_CLOSE: str = "[data-testid='modal-close']"
    CONFIRM_DIALOG: str = "[data-testid='confirm-dialog']"
    CONFIRM_YES: str = "[data-testid='confirm-yes']"
    CONFIRM_NO: str = "[data-testid='confirm-no']"

    # Forms
    FORM_ERROR: str = "[data-testid='form-error']"
    FIELD_ERROR: str = "[data-testid='field-error']"
    SUBMIT_BUTTON: str = "[type='submit']"


@dataclass
class NetworkMockDefaults:
    """Default options for network mocking."""

    default_status: int = 200
    default_content_type: str = "application/json"
    delay_ms: int = 0


# Singleton instances
RESOURCE_LIMITS = BrowserResourceLimits()
BROWSER_DEFAULTS = BrowserDefaults()
SCREENSHOT_DEFAULTS = ScreenshotDefaults()
VIDEO_DEFAULTS = VideoDefaults()
TRACE_DEFAULTS = TraceDefaults()
WYLD_SELECTORS = WyldSelectors()
NETWORK_MOCK_DEFAULTS = NetworkMockDefaults()


def get_browser_launch_args(browser_type: BrowserType = BrowserType.CHROMIUM) -> dict[str, Any]:
    """
    Get browser launch arguments for the specified browser type.

    Args:
        browser_type: The type of browser to get args for

    Returns:
        Dictionary of launch arguments
    """
    base_args = {
        "headless": BROWSER_DEFAULTS.headless,
        "slow_mo": BROWSER_DEFAULTS.slow_mo,
    }

    if browser_type == BrowserType.CHROMIUM:
        base_args["args"] = [
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
    elif browser_type == BrowserType.FIREFOX:
        base_args["firefox_user_prefs"] = {
            "media.navigator.streams.fake": True,
            "media.navigator.permission.disabled": True,
        }

    return base_args


def get_context_options(
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    storage_state: str | dict | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Get browser context options.

    Args:
        viewport_width: Custom viewport width
        viewport_height: Custom viewport height
        storage_state: Path to storage state or dict
        **kwargs: Additional options

    Returns:
        Dictionary of context options
    """
    options = {
        "viewport": {
            "width": viewport_width or BROWSER_DEFAULTS.viewport_width,
            "height": viewport_height or BROWSER_DEFAULTS.viewport_height,
        },
        "ignore_https_errors": BROWSER_DEFAULTS.ignore_https_errors,
        "locale": BROWSER_DEFAULTS.locale,
        "timezone_id": BROWSER_DEFAULTS.timezone,
        "color_scheme": BROWSER_DEFAULTS.color_scheme,
        "device_scale_factor": BROWSER_DEFAULTS.device_scale_factor,
    }

    if storage_state:
        options["storage_state"] = storage_state

    options.update(kwargs)
    return options


# Encryption configuration for credential storage
ENCRYPTION_KEY_ENV_VAR = "CREDENTIAL_ENCRYPTION_KEY"
ENCRYPTION_ALGORITHM = "AES-256-GCM"
DEFAULT_CREDENTIAL_ROTATION_DAYS = 30


# Session storage configuration
SESSION_STORAGE_DIR = "/tmp/qa_sessions"
SESSION_MAX_AGE_DAYS = 7
