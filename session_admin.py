"""Save and validate platform session cookies (IT-only)."""

import os

import env_loader
from env_loader import reload_env, set_env_key
from stratus_config import ENVIRONMENTS, LEGACY_SESSION_COOKIE

STRATUS_LOGIN_URLS = {
    "dev": "https://www.gtpstratus.com",
    "prod": "https://www.gtpstratus.com",
}
REVIZTO_LOGIN_URL = "https://ws.revizto.com"
# Access code page (exchanged for API access/refresh tokens) — not Active Sessions.
REVIZTO_ACCESS_CODE_URL = "https://ws.revizto.com/login?request=accessCode"
SYMETRI_LOGIN_URL = "https://my.symetri.com"



# This will be used to check if the session admin is enabled.
def session_admin_enabled():
    return bool((os.getenv("SESSION_ADMIN_KEY") or "").strip())



# This will be used to verify the session admin key.
def verify_session_admin_key(provided_key):
    expected = (os.getenv("SESSION_ADMIN_KEY") or "").strip()
    if not expected:
        return False
    return provided_key == expected



# This will be used to get the stratus cookie environment variable
def _stratus_cookie_env_var(environment):
    env_key = (environment or "prod").strip().lower()
    if env_key not in ENVIRONMENTS:
        raise ValueError(f"Unknown Stratus environment: {environment}")
    return ENVIRONMENTS[env_key]["session_cookie_env_var"]



# This will be used to write the environment variable.
def _write_env(key, value):
    os.environ[key] = value
    set_env_key(key, value)
    reload_env()


# This will be used to save the stratus session cookie.
def save_stratus_session_cookie(cookie, environment="prod", validate=True):
    cookie = (cookie or "").strip()
    if not cookie:
        raise ValueError("Cookie header is empty.")

    env_key = (environment or "prod").strip().lower()
    env_var = _stratus_cookie_env_var(env_key)
    message = "Stratus session cookie saved."

    if validate:
        from stratus_api import build_stratus_session, get_all_company_user_roles
        from stratus_config import get_stratus_environment

        env = get_stratus_environment(env_key)
        try:
            session = build_stratus_session(env, cookie_header=cookie)
            user_count = len(get_all_company_user_roles(session))
            message = f"{env['label']} connected ({user_count} users)."
        except Exception as exc:
            raise ValueError(f"Stratus cookie validation failed: {exc}") from exc

    _write_env(env_var, cookie)
    if env_key == "prod" and not os.getenv(LEGACY_SESSION_COOKIE):
        _write_env(LEGACY_SESSION_COOKIE, cookie)

    return {
        "platform": "stratus",
        "environment": env_key,
        "env_var": env_var,
        "message": message,
    }


# This will be used to save the revizto session cookie.
def save_revizto_session_cookie(cookie, validate=True):
    cookie = (cookie or "").strip()
    if not cookie:
        raise ValueError("Cookie header is empty.")

    message = "Revizto session cookie saved."

    if validate:
        from revisto_api import (
            get_current_user_licenses,
            get_revizto_access_token,
            revizto_configured,
            revizto_session_cookie_usable,
        )

        if not revizto_session_cookie_usable(cookie):
            raise ValueError(
                "Revizto cookie does not look like a completed sign-in. "
                "Finish logging into ws.revizto.com, then try again."
            )

        previous = os.environ.get("REVIZTO_SESSION_COOKIE")
        os.environ["REVIZTO_SESSION_COOKIE"] = cookie
        try:
            from revisto_api import reconnect_revizto_from_session

            try:
                get_revizto_access_token()
                licenses = get_current_user_licenses()
                license_name = licenses[0].get("name") if licenses else "license"
                message = f"Revizto connected ({license_name})."
            except Exception:
                result = reconnect_revizto_from_session(cookie)
                message = result.get("message") or "Revizto connected."
        except Exception as exc:
            raise ValueError(
                f"Revizto reconnect failed: {exc}. "
                "Sign in at ws.revizto.com in the browser window opened by Reconnect."
            ) from exc
        finally:
            if previous is None:
                os.environ.pop("REVIZTO_SESSION_COOKIE", None)
            else:
                os.environ["REVIZTO_SESSION_COOKIE"] = previous

    _write_env("REVIZTO_SESSION_COOKIE", cookie)

    return {
        "platform": "revizto",
        "env_var": "REVIZTO_SESSION_COOKIE",
        "message": message,
    }



# This will be used to save the symetri bearer token.
def save_symetri_bearer_token(token, validate=True):
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        raise ValueError("Bearer token is empty.")

    message = "Symetri bearer token saved."

    if validate:
        from symetri_api import SymetriApiError, _list_account_users, bearer_token_usable
        from symetri_config import get_symetri_settings, symetri_configured, symetri_missing_settings

        if not bearer_token_usable(token):
            raise ValueError(
                "Symetri bearer token is expired or not a valid JWT. "
                "Sign in at my.symetri.com and capture a fresh token."
            )

        if not symetri_configured():
            missing = ", ".join(symetri_missing_settings())
            if "SYMETRI_ACCOUNT_ID" in missing:
                raise ValueError("Set SYMETRI_ACCOUNT_ID in .env before saving a bearer token.")

        settings = get_symetri_settings()
        settings = dict(settings)
        settings["bearer_token"] = token
        try:
            user_count = len(_list_account_users(settings))
            message = f"Symetri connected (account {settings['account_id']}, {user_count} users)."
        except SymetriApiError as exc:
            raise ValueError(f"Symetri bearer token validation failed: {exc}") from exc

    _write_env("SYMETRI_BEARER_TOKEN", token)

    return {
        "platform": "symetri",
        "env_var": "SYMETRI_BEARER_TOKEN",
        "message": message,
    }
