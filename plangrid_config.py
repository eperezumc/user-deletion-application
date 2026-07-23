"""PlanGrid settings — Admin Console session (preferred) or legacy API key."""

import env_loader  # noqa: F401
from env_loader import env_value, reload_env

DEFAULT_APP_BASE_URL = "https://app.plangrid.com"
DEFAULT_LEGACY_BASE_URL = "https://io.plangrid.com"
LEGACY_ACCEPT = "application/vnd.plangrid+json; version=1"
DEFAULT_ORG_USERS_PATH = "/proxy/aapi2/organizations/{org_id}/users"
DEFAULT_ORG_REMOVE_PATH = "/proxy/aapi1/organization/{org_id}/users"


def get_plangrid_settings():
    reload_env()
    return {
        "label": "PlanGrid",
        "app_base_url": env_value("PLANGRID_APP_BASE_URL", DEFAULT_APP_BASE_URL).rstrip("/"),
        "org_id": env_value("PLANGRID_ORG_ID"),
        "session_cookie": env_value("PLANGRID_SESSION_COOKIE") or env_value("PLANGRID_COOKIE"),
        "org_users_path": env_value("PLANGRID_ORG_USERS_PATH", DEFAULT_ORG_USERS_PATH),
        "org_remove_path": env_value("PLANGRID_ORG_REMOVE_PATH", DEFAULT_ORG_REMOVE_PATH),
        # Optional legacy public API (io.plangrid.com) for project-level remove.
        "legacy_base_url": env_value("PLANGRID_BASE_URL", DEFAULT_LEGACY_BASE_URL).rstrip("/"),
        "api_key": env_value("PLANGRID_API_KEY"),
        "legacy_accept": LEGACY_ACCEPT,
    }


def plangrid_enterprise_configured():
    settings = get_plangrid_settings()
    return bool(settings["session_cookie"] and settings["org_id"])


def plangrid_legacy_configured():
    return bool(get_plangrid_settings()["api_key"])


def plangrid_configured():
    return plangrid_enterprise_configured() or plangrid_legacy_configured()


def plangrid_missing_settings():
    missing = []
    if not get_plangrid_settings()["org_id"]:
        missing.append("PLANGRID_ORG_ID")
    if not get_plangrid_settings()["session_cookie"]:
        missing.append("PLANGRID_SESSION_COOKIE")
    return missing
