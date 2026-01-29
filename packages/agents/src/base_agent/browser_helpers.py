"""
Browser Helpers - Reusable site-specific automation helpers.

Stores and applies:
- Cookies to set (bypass consent banners)
- Actions to perform (dismiss popups)
- Selectors to wait for

Helpers are stored per-domain and can be auto-applied when navigating.
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ai_core import get_logger

logger = get_logger(__name__)

# Storage location for helpers
HELPERS_FILE = Path("/home/wyld-core/pai/browser_helpers.json")


@dataclass
class CookieConfig:
    """Cookie to set on a site."""
    name: str
    value: str
    domain: str | None = None  # If None, uses current domain
    path: str = "/"
    secure: bool = False
    http_only: bool = False
    same_site: str = "Lax"  # Strict, Lax, None
    expires: int | None = None  # Unix timestamp, None = session


@dataclass
class DismissAction:
    """Action to dismiss a popup/banner."""
    type: str  # "click", "set_cookie", "execute_js"
    selector: str | None = None  # CSS selector for click
    cookie: CookieConfig | None = None  # Cookie to set
    js_code: str | None = None  # JavaScript to execute
    wait_after: int = 500  # ms to wait after action
    description: str = ""


@dataclass
class SiteHelper:
    """Helper configuration for a specific site."""
    domain: str
    name: str
    description: str

    # Cookies to set before/after page load
    cookies: list[CookieConfig] = field(default_factory=list)

    # Actions to dismiss popups
    dismiss_actions: list[DismissAction] = field(default_factory=list)

    # Selectors that indicate popups are present
    popup_selectors: list[str] = field(default_factory=list)

    # When to apply: "before_load", "after_load", "on_popup"
    apply_timing: str = "after_load"

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_used: str | None = None
    use_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert nested dataclasses
        data["cookies"] = [asdict(c) if isinstance(c, CookieConfig) else c for c in self.cookies]
        data["dismiss_actions"] = [asdict(a) if isinstance(a, DismissAction) else a for a in self.dismiss_actions]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SiteHelper":
        """Create from dictionary."""
        cookies = [
            CookieConfig(**c) if isinstance(c, dict) else c
            for c in data.get("cookies", [])
        ]
        dismiss_actions = []
        for a in data.get("dismiss_actions", []):
            if isinstance(a, dict):
                if a.get("cookie") and isinstance(a["cookie"], dict):
                    a["cookie"] = CookieConfig(**a["cookie"])
                dismiss_actions.append(DismissAction(**a))
            else:
                dismiss_actions.append(a)

        return cls(
            domain=data["domain"],
            name=data["name"],
            description=data.get("description", ""),
            cookies=cookies,
            dismiss_actions=dismiss_actions,
            popup_selectors=data.get("popup_selectors", []),
            apply_timing=data.get("apply_timing", "after_load"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_used=data.get("last_used"),
            use_count=data.get("use_count", 0),
        )


class BrowserHelpersStore:
    """
    Manages storage and retrieval of browser helpers.

    Helpers are stored in a JSON file and can be:
    - Listed by domain
    - Applied automatically when navigating
    - Created from recorded actions
    """

    def __init__(self, storage_path: Path = HELPERS_FILE):
        self._storage_path = storage_path
        self._helpers: dict[str, SiteHelper] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Load helpers from storage if not already loaded."""
        if self._loaded:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                for domain, helper_data in data.get("helpers", {}).items():
                    self._helpers[domain] = SiteHelper.from_dict(helper_data)
                logger.info("Loaded browser helpers", count=len(self._helpers))
            except Exception as e:
                logger.error("Failed to load browser helpers", error=str(e))

        self._loaded = True

    def _save(self) -> None:
        """Save helpers to storage."""
        try:
            data = {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "helpers": {
                    domain: helper.to_dict()
                    for domain, helper in self._helpers.items()
                }
            }
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save browser helpers", error=str(e))

    def get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def get_helper(self, url_or_domain: str) -> SiteHelper | None:
        """Get helper for a domain."""
        self._ensure_loaded()

        domain = self.get_domain(url_or_domain) if "://" in url_or_domain else url_or_domain

        # Try exact match first
        if domain in self._helpers:
            return self._helpers[domain]

        # Try parent domain (e.g., sub.example.com -> example.com)
        parts = domain.split(".")
        if len(parts) > 2:
            parent = ".".join(parts[-2:])
            if parent in self._helpers:
                return self._helpers[parent]

        return None

    def add_helper(self, helper: SiteHelper) -> None:
        """Add or update a helper."""
        self._ensure_loaded()
        self._helpers[helper.domain] = helper
        self._save()
        logger.info("Added browser helper", domain=helper.domain, name=helper.name)

    def remove_helper(self, domain: str) -> bool:
        """Remove a helper."""
        self._ensure_loaded()
        if domain in self._helpers:
            del self._helpers[domain]
            self._save()
            return True
        return False

    def list_helpers(self) -> list[SiteHelper]:
        """List all helpers."""
        self._ensure_loaded()
        return list(self._helpers.values())

    def record_use(self, domain: str) -> None:
        """Record that a helper was used."""
        self._ensure_loaded()
        if domain in self._helpers:
            self._helpers[domain].last_used = datetime.now(timezone.utc).isoformat()
            self._helpers[domain].use_count += 1
            self._save()


# Global store instance
_helpers_store: BrowserHelpersStore | None = None


def get_helpers_store() -> BrowserHelpersStore:
    """Get the global helpers store."""
    global _helpers_store
    if _helpers_store is None:
        _helpers_store = BrowserHelpersStore()
    return _helpers_store


# ============================================================================
# Common Helper Templates
# ============================================================================

def create_cookie_consent_helper(
    domain: str,
    cookie_name: str = "cookieConsent",
    cookie_value: str = "accepted",
    name: str | None = None,
) -> SiteHelper:
    """Create a helper that sets a cookie consent cookie."""
    return SiteHelper(
        domain=domain,
        name=name or f"{domain} Cookie Consent",
        description=f"Sets {cookie_name} cookie to bypass consent banner",
        cookies=[
            CookieConfig(
                name=cookie_name,
                value=cookie_value,
                path="/",
            )
        ],
        apply_timing="before_load",
    )


def create_click_dismiss_helper(
    domain: str,
    selector: str,
    name: str | None = None,
    description: str | None = None,
) -> SiteHelper:
    """Create a helper that clicks to dismiss a popup."""
    return SiteHelper(
        domain=domain,
        name=name or f"{domain} Popup Dismiss",
        description=description or f"Clicks {selector} to dismiss popup",
        dismiss_actions=[
            DismissAction(
                type="click",
                selector=selector,
                description=f"Click {selector}",
            )
        ],
        popup_selectors=[selector],
        apply_timing="after_load",
    )


def create_gdpr_helper(domain: str) -> SiteHelper:
    """Create a helper for common GDPR consent banners."""
    return SiteHelper(
        domain=domain,
        name=f"{domain} GDPR Consent",
        description="Handles common GDPR consent patterns",
        dismiss_actions=[
            # Try common accept buttons
            DismissAction(
                type="click",
                selector='button[id*="accept"], button[class*="accept"], [data-testid*="accept"]',
                description="Click accept button",
                wait_after=500,
            ),
            DismissAction(
                type="click",
                selector='button:has-text("Accept"), button:has-text("I agree"), button:has-text("OK")',
                description="Click accept by text",
                wait_after=500,
            ),
        ],
        popup_selectors=[
            '[class*="cookie"], [class*="consent"], [class*="gdpr"]',
            '[id*="cookie"], [id*="consent"], [id*="gdpr"]',
            '[role="dialog"][class*="modal"]',
        ],
        apply_timing="on_popup",
    )


# ============================================================================
# Pre-defined helpers for common sites
# ============================================================================

COMMON_HELPERS = [
    # Google
    SiteHelper(
        domain="google.com",
        name="Google Consent",
        description="Accept Google's cookie consent",
        dismiss_actions=[
            DismissAction(
                type="click",
                selector='button[id="L2AGLb"], button:has-text("Accept all")',
                description="Accept all cookies",
            )
        ],
        popup_selectors=['[role="dialog"]', '#consent'],
        apply_timing="on_popup",
    ),

    # YouTube
    SiteHelper(
        domain="youtube.com",
        name="YouTube Consent",
        description="Accept YouTube's cookie consent",
        dismiss_actions=[
            DismissAction(
                type="click",
                selector='button[aria-label*="Accept"], tp-yt-paper-button:has-text("Accept all")',
                description="Accept all cookies",
            )
        ],
        popup_selectors=['ytd-consent-bump-v2-lightbox'],
        apply_timing="on_popup",
    ),

    # Generic CookieBot
    SiteHelper(
        domain="cookiebot",  # Matches sites using CookieBot
        name="CookieBot Handler",
        description="Handles CookieBot consent banners",
        dismiss_actions=[
            DismissAction(
                type="click",
                selector='#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, a#CybotCookiebotDialogBodyButtonAccept',
                description="Accept all via CookieBot",
            )
        ],
        popup_selectors=['#CybotCookiebotDialog'],
        apply_timing="on_popup",
    ),
]


def initialize_common_helpers() -> None:
    """Initialize common helpers if not already present."""
    store = get_helpers_store()
    for helper in COMMON_HELPERS:
        if not store.get_helper(helper.domain):
            store.add_helper(helper)
