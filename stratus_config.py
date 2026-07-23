"""Stratus environment settings (dev vs prod)."""

import os

import env_loader  # noqa: F401
from env_loader import reload_env

DEFAULT_BASE_URL = "https://www.gtpstratus.com"

ENVIRONMENTS = {
    "dev": {
        "label": "Stratus Dev",
        "session_cookie_env_var": "STRATUS_DEV_SESSION_COOKIE",
        "base_url_env_var": "STRATUS_DEV_BASE_URL",
        "former_employee_group_env_var": "STRATUS_DEV_FORMER_EMPLOYEE_GROUP",
        "disable_role_id_env_var": "STRATUS_DEV_DISABLE_DEFAULT_PROJECT_ROLE_ID",
        "default_former_employee_group": "Custom",
        "default_disable_role_id": "",
    },
    "prod": {
        "label": "Stratus Production",
        "session_cookie_env_var": "STRATUS_PROD_SESSION_COOKIE",
        "base_url_env_var": "STRATUS_PROD_BASE_URL",
        "former_employee_group_env_var": "STRATUS_PROD_FORMER_EMPLOYEE_GROUP",
        "disable_role_id_env_var": "STRATUS_PROD_DISABLE_DEFAULT_PROJECT_ROLE_ID",
        "default_former_employee_group": "(Former Employee)",
        "default_disable_role_id": "",
    },
}

# Older single-env variable names (prod fallback).
LEGACY_SESSION_COOKIE = "STRATUS_SESSION_COOKIE"
LEGACY_FORMER_EMPLOYEE_GROUP = "STRATUS_FORMER_EMPLOYEE_GROUP"


# This will be used to get the session cookie.
def _session_cookie(env_key):
    reload_env()
    env_var = ENVIRONMENTS[env_key]["session_cookie_env_var"]
    cookie = (os.getenv(env_var) or "").strip()
    if cookie:
        return cookie, env_var
    legacy = (os.getenv(LEGACY_SESSION_COOKIE) or "").strip()
    if legacy:
        return legacy, LEGACY_SESSION_COOKIE
    return "", env_var



# This will be used to get the former employee group.
def _former_employee_group(env_key):
    env_var = ENVIRONMENTS[env_key]["former_employee_group_env_var"]
    group = (os.getenv(env_var) or "").strip()
    if group:
        return group, env_var
    if env_key == "prod":
        legacy = (os.getenv(LEGACY_FORMER_EMPLOYEE_GROUP) or "").strip()
        if legacy:
            return legacy, LEGACY_FORMER_EMPLOYEE_GROUP
    return ENVIRONMENTS[env_key]["default_former_employee_group"], env_var



# This will be used to get the disable role id.
def _disable_role_id(env_key):
    meta = ENVIRONMENTS[env_key]
    env_var = meta["disable_role_id_env_var"]
    raw = os.getenv(env_var)
    if raw is None:
        return meta["default_disable_role_id"], env_var
    return raw.strip(), env_var


# This will be used to extract the company id from the cookie.
def extract_company_id_from_cookie(cookie):
    for part in cookie.split(";"):
        piece = part.strip()
        if piece.startswith("GTPUserCompany="):
            return piece.split("=", 1)[1].strip()
    return None



# This will be used to get the stratus environment.
def get_stratus_environment(key=None):
    env_key = (
        key
        or os.getenv("STRATUS_ENVIRONMENT")
        or os.getenv("ACC_ENVIRONMENT")
        or "dev"
    ).strip().lower()
    if env_key not in ENVIRONMENTS:
        raise ValueError(f"Unknown Stratus environment: {env_key}")

    meta = ENVIRONMENTS[env_key]
    session_cookie, session_cookie_env_var = _session_cookie(env_key)
    former_employee_group, former_employee_group_env_var = _former_employee_group(env_key)
    disable_role_id, disable_role_id_env_var = _disable_role_id(env_key)
    base_url = (
        os.getenv(meta["base_url_env_var"]) or DEFAULT_BASE_URL
    ).strip().rstrip("/")

    return {
        "key": env_key,
        "label": meta["label"],
        "base_url": base_url,
        "session_cookie": session_cookie,
        "session_cookie_env_var": session_cookie_env_var,
        "former_employee_group": former_employee_group,
        "former_employee_group_env_var": former_employee_group_env_var,
        "disable_default_project_role_id": disable_role_id,
        "disable_default_project_role_id_env_var": disable_role_id_env_var,
        "configured": bool(session_cookie),
    }


# This will be used to list the stratus environments.
def list_stratus_environments():
    return [get_stratus_environment(key) for key in ENVIRONMENTS]
