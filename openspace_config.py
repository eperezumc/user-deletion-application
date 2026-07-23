"""OpenSpace web API settings (org admin session)."""

import env_loader  # noqa: F401
from env_loader import env_value, reload_env

DEFAULT_BASE_URL = "https://openspace.ai"
DEFAULT_DELETE_PATH = "/api/v3/users/delete"

# This will be used to get the openspace settings
def get_openspace_settings():
    reload_env()
    return {
        "label": "OpenSpace",
        "base_url": env_value("OPENSPACE_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "org_id": env_value("OPENSPACE_ORG_ID"),
        "session_cookie": env_value("OPENSPACE_SESSION_COOKIE") or env_value("OPENSPACE_COOKIE"),
        "api_key": env_value("OPENSPACE_API_KEY"),
        "external_api_base_url": env_value(
            "OPENSPACE_EXTERNAL_API_BASE_URL", "https://api.us.openspace.ai"
        ).rstrip("/"),
        "delete_path": env_value("OPENSPACE_DELETE_USERS_PATH", DEFAULT_DELETE_PATH),
        "members_list_path": env_value("OPENSPACE_MEMBERS_LIST_PATH"),
        "members_search_path": env_value("OPENSPACE_MEMBERS_SEARCH_PATH"),
    }

# This will be used to check if the openspace is configured
def openspace_configured():
    settings = get_openspace_settings()
    return bool(settings["session_cookie"] and settings["org_id"])

# This will be used to check if the openspace is missing any settings
def openspace_missing_settings():
    settings = get_openspace_settings()
    missing = []
    if not settings["session_cookie"]:
        missing.append("OPENSPACE_SESSION_COOKIE (or OPENSPACE_COOKIE)")
    if not settings["org_id"]:
        missing.append("OPENSPACE_ORG_ID")
    return missing
