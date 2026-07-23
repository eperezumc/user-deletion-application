"""TrackVia API settings (API key + auth token)."""

import os

import env_loader  # noqa: F401
from env_loader import env_value, reload_env

DEFAULT_BASE_URL = "https://umci.trackvia.com"
DEFAULT_VIEW_ID = "993"
DEFAULT_OPENAPI_BASE_URL = "https://go.trackvia.com"


def get_trackvia_settings():
    reload_env()
    base_url = env_value("TRACKVIA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    account_id = env_value("TRACKVIA_ACCOUNT_ID")
    openapi_override = env_value("TRACKVIA_OPENAPI_BASE_URL").rstrip("/")
    if openapi_override:
        openapi_base_url = openapi_override
    elif account_id:
        # Sandbox Open API calls use go.trackvia.com + account-id header.
        openapi_base_url = DEFAULT_OPENAPI_BASE_URL
    else:
        openapi_base_url = base_url
    return {
        "label": "TrackVia",
        "base_url": base_url,
        "openapi_base_url": openapi_base_url,
        "api_key": env_value("TRACKVIA_API_KEY"),
        "access_token": env_value("TRACKVIA_ACCESS_TOKEN"),
        "view_id": env_value("TRACKVIA_VIEW_ID", DEFAULT_VIEW_ID),
        "account_id": account_id,
        "email_field": env_value("TRACKVIA_EMAIL_FIELD", "Email From Viewpoint"),
        "status_field": env_value("TRACKVIA_STATUS_FIELD", "TrackVia Usage"),
        "status_active": env_value("TRACKVIA_STATUS_ACTIVE", "Existing TrackVia User"),
        "status_disabled": env_value("TRACKVIA_STATUS_DISABLED", "Deactivated TrackVia User"),
        "disable_action_value": env_value("TRACKVIA_DISABLE_ACTION", "Deactivate Now"),
    }


# This will be used to check if the TrackVia is configured
def trackvia_configured():
    settings = get_trackvia_settings()
    return bool(settings["api_key"] and settings["access_token"] and settings["view_id"])



# This will be used to check if the TrackVia is missing any settings
def trackvia_missing_settings():
    settings = get_trackvia_settings()
    missing = []
    if not settings["api_key"]:
        missing.append("TRACKVIA_API_KEY")
    if not settings["access_token"]:
        missing.append("TRACKVIA_ACCESS_TOKEN")
    if not settings["view_id"]:
        missing.append("TRACKVIA_VIEW_ID")
    return missing
