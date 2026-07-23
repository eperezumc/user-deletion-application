"""Symetri My Symetri backend API settings (license admin bearer token)."""

import env_loader  # noqa: F401
from env_loader import env_value, reload_env

DEFAULT_API_BASE_URL = "https://backend.my.symetri.com"
DEFAULT_WEB_ORIGIN = "https://my.symetri.com"
DEFAULT_USERS_LIST_PATH = "/v1/AccountUsers/{account_id}"
DEFAULT_DELETE_PATH = "/v1/AccountUsers/{account_id}/{user_id}"

# This will be used to get the symetri settings
def get_symetri_settings():
    reload_env()
    return {
        "label": "Symetri",
        "api_base_url": env_value("SYMETRI_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/"),
        "web_origin": env_value("SYMETRI_WEB_ORIGIN", DEFAULT_WEB_ORIGIN).rstrip("/"),
        "account_id": env_value("SYMETRI_ACCOUNT_ID"),
        "bearer_token": env_value("SYMETRI_BEARER_TOKEN") or env_value("SYMETRI_ACCESS_TOKEN"),
        "users_list_path": env_value("SYMETRI_USERS_LIST_PATH"),
        "delete_path": env_value("SYMETRI_DELETE_USER_PATH"),
    }


# This will be used to check if the symetri is configured
def symetri_configured():
    settings = get_symetri_settings()
    return bool(settings["bearer_token"] and settings["account_id"])


# This will be used to get the missing settings
def symetri_missing_settings():
    settings = get_symetri_settings()
    missing = []
    if not settings["bearer_token"]:
        missing.append("SYMETRI_BEARER_TOKEN")
    if not settings["account_id"]:
        missing.append("SYMETRI_ACCOUNT_ID")
    return missing
