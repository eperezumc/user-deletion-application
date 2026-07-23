"""Calls the Stratus company-admin internal API (session cookie auth)."""

import threading
import time

import env_loader  # noqa: F401
import requests

from stratus_config import extract_company_id_from_cookie, get_stratus_environment

USER_STATUS_ACTIVE = "1"
USER_STATUS_DISABLED = "2"
ROLE_LIST_CACHE_TTL_SECONDS = 300
_role_list_cache = {}
_role_list_locks = {}
_role_list_inflight = {}

ENABLE_STEPS = [("userStatusTypeEnumValue", USER_STATUS_ACTIVE)]


class StratusUserNotFoundError(LookupError):
    pass


class StratusConfigError(ValueError):
    pass


# This will be used to get the disable steps.
def get_disable_steps(environment=None):
    env = (
        environment
        if isinstance(environment, dict) and "key" in environment
        else get_stratus_environment(environment)
    )
    return [
        ("userStatusTypeEnumValue", USER_STATUS_DISABLED),
        ("defaultProjectRoleId", env["disable_default_project_role_id"]),
        ("group", env["former_employee_group"]),
    ]


# This will be used to get the company admin URLs.
def _company_admin_urls(env):
    base = env["base_url"].rstrip("/")
    return (
        f"{base}/companyadmin/get-all-company-user-roles",
        f"{base}/companyadmin/update-company-user-role-value?",
    )


# This will be used to get the session environment.
def _session_env(session):
    env = getattr(session, "stratus_env", None)
    if env is None:
        raise StratusConfigError(
            "Stratus session is missing environment context. "
            "Build the session with build_stratus_session(environment=...)."
        )
    return env


# This will be used to check the stratus session health.
def check_stratus_session_health(environment=None, session=None):
    try:
        env = get_stratus_environment(environment)
    except ValueError as exc:
        return {
            "ok": False,
            "configured": False,
            "environment": environment,
            "message": str(exc),
        }

    if not env["session_cookie"]:
        return {
            "ok": False,
            "configured": False,
            "environment": env["key"],
            "label": env["label"],
            "base_url": env["base_url"],
            "message": (
                f"{env['label']} is not configured on this server. "
                "Contact IT to set up the connection."
            ),
            "admin_hint": (
                f"IT: add {env['session_cookie_env_var']} to the server .env file "
                "(not in source code)."
            ),
        }

    try:
        client = session or build_stratus_session(env)
        users = get_all_company_user_roles(client)
        user_count = len(users)
        return {
            "ok": True,
            "configured": True,
            "environment": env["key"],
            "label": env["label"],
            "base_url": env["base_url"],
            "company_id": extract_company_id_from_cookie(env["session_cookie"]),
            "user_count": user_count,
            "message": f"{env['label']} connected ({user_count} users).",
        }
    except StratusConfigError as exc:
        return {
            "ok": False,
            "configured": True,
            "environment": env["key"],
            "label": env["label"],
            "base_url": env["base_url"],
            "message": f"{env['label']} session expired or invalid.",
            "admin_hint": (
                f"IT: log into {env['base_url']} as the service admin, copy a fresh "
                f"Cookie from DevTools, and update {env['session_cookie_env_var']} in "
                "the server .env file, then restart the app."
            ),
            "detail": str(exc),
        }
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return {
            "ok": False,
            "configured": True,
            "environment": env["key"],
            "label": env["label"],
            "base_url": env["base_url"],
            "message": f"{env['label']} session check failed.",
            "admin_hint": (
                f"IT: verify {env['session_cookie_env_var']} in the server .env file."
            ),
            "detail": detail,
        }

# This will be used to build the stratus session.
def build_stratus_session(environment=None, cookie_header=None):
    env = (
        environment
        if isinstance(environment, dict) and "key" in environment
        else get_stratus_environment(environment)
    )
    cookie = cookie_header or env["session_cookie"]
    if not cookie:
        raise StratusConfigError(
            f"{env['session_cookie_env_var']} is not configured. "
            f"Log into {env['base_url']} as a company admin, copy the Cookie header "
            "from DevTools, and add it to your .env file."
        )

    base = env["base_url"].rstrip("/")
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Origin": base,
            "Referer": f"{base}/companyadmin",
            "Cookie": cookie,
        }
    )
    session.stratus_env = env
    return session


# This will be used to parse the JSON response.
def _parse_json_response(response, context, env):
    try:
        return response.json()
    except requests.JSONDecodeError:
        snippet = (response.text or "").strip()[:200]
        if "sign you in" in snippet.lower() or "login" in snippet.lower():
            raise StratusConfigError(
                f"{env['label']} session expired or invalid. Log in again at "
                f"{env['base_url']}, copy a fresh Cookie header from DevTools, and "
                f"update {env['session_cookie_env_var']} in .env."
            ) from None
        raise StratusConfigError(
            f"{env['label']} {context} returned non-JSON (HTTP {response.status_code}). "
            f"Your {env['session_cookie_env_var']} may be expired."
        ) from None


# This will be used to fetch the company user roles.
def _fetch_company_user_roles(client, env):
    list_url, _ = _company_admin_urls(env)
    response = client.get(list_url, timeout=60)
    response.raise_for_status()
    payload = _parse_json_response(response, context="user list", env=env)
    if not isinstance(payload, list):
        raise ValueError("Unexpected Stratus users response shape.")
    return payload



# This will be used to get all the company user roles.
def get_all_company_user_roles(session=None, environment=None, use_cache=True):
    client = session or build_stratus_session(environment)
    env = _session_env(client)
    cache_key = env["key"]
    now = time.time()

    if use_cache and not session:
        cached = _role_list_cache.get(cache_key)
        if cached and now - cached["fetched_at"] < ROLE_LIST_CACHE_TTL_SECONDS:
            return list(cached["users"])

    if session:
        return _fetch_company_user_roles(client, env)

    lock = _role_list_locks.setdefault(cache_key, threading.Lock())
    with lock:
        cached = _role_list_cache.get(cache_key)
        if use_cache and cached and now - cached["fetched_at"] < ROLE_LIST_CACHE_TTL_SECONDS:
            return list(cached["users"])

        inflight = _role_list_inflight.get(cache_key)
        if inflight is None:
            inflight = {"event": threading.Event(), "users": None, "error": None}
            _role_list_inflight[cache_key] = inflight
            is_owner = True
        else:
            is_owner = False

    if is_owner:
        try:
            users = _fetch_company_user_roles(client, env)
            inflight["users"] = users
            _role_list_cache[cache_key] = {"fetched_at": time.time(), "users": users}
        except Exception as exc:
            inflight["error"] = exc
            raise
        finally:
            with lock:
                _role_list_inflight.pop(cache_key, None)
                inflight["event"].set()
        return list(users)

    inflight["event"].wait(timeout=90)
    if inflight["error"] is not None:
        raise inflight["error"]
    if inflight["users"] is None:
        raise TimeoutError(f"Timed out waiting for {env['label']} user list.")
    return list(inflight["users"])



# This will be used to get the users matching the email.
def _users_matching_email(users, email):
    target = email.strip().lower()
    return [
        row for row in users
        if (row.get("email") or "").strip().lower() == target
    ]



# This will be used to get all the company users by email.
def get_all_company_users_by_email(email, session=None, environment=None):
    users = get_all_company_user_roles(session, environment=environment)
    matches = _users_matching_email(users, email)
    if not matches:
        raise StratusUserNotFoundError(f"No Stratus user found for {email}.")
    return matches


# This will be used to get the company user by email.
def get_company_user_by_email(email, session=None, environment=None):
    matches = get_all_company_users_by_email(email, session=session, environment=environment)
    return matches[0]



# This will be used to get the company user by pk.
def _user_by_pk(users, pk):
    target = pk.strip()
    for row in users:
        if (row.get("id") or "").strip() == target:
            return row
    return None


# This will be used to get the company user by pk.
def get_company_user_by_pk(pk, session=None, environment=None):
    users = get_all_company_user_roles(session, environment=environment)
    user = _user_by_pk(users, pk)
    if not user:
        raise StratusUserNotFoundError(f"No Stratus user found for pk {pk}.")
    return user


# This will be used to format the form value.
def _format_form_value(value):
    return "" if value is None else str(value)



# This will be used to get the user field snapshot.
def _user_field_snapshot(user):
    return {
        "group": user.get("group"),
        "default_project_role_id": user.get("defaultProjectRoleId"),
        "status": user.get("userStatusTypeEnumValue"),
        "is_quick_pass": user.get("isQuickPass"),
        "license_type": user.get("userLicenseTypeEnumValue"),
    }



# This will be used to get the stratus environment record.
def _stratus_env_record(environment=None):
    if isinstance(environment, dict) and "former_employee_group" in environment:
        return environment
    return get_stratus_environment(environment)



# This will be used to check if the stratus user is disabled.
def is_stratus_user_disabled(user, environment=None):
    """Detect disabled Stratus users even when the display name is stale."""
    value = str(user.get("userStatusTypeEnumValue") or "").strip()
    if value == USER_STATUS_DISABLED:
        return True

    name = (user.get("userStatusTypeEnumName") or "").strip().lower()
    if "disabled" in name or "inactive" in name:
        return True

    if environment is not None:
        env = _stratus_env_record(environment)
        group = (user.get("group") or "").strip()
        former_group = (env.get("former_employee_group") or "").strip()
        if former_group and group == former_group:
            return True

    return False


# This will be used to get the stratus membership status.
def stratus_membership_status(user, environment=None):
    return "disabled" if is_stratus_user_disabled(user, environment) else "active"



# This will be used to get the stratus status label.
def stratus_status_label(user, environment=None):
    if is_stratus_user_disabled(user, environment):
        return "Disabled"
    return (user.get("userStatusTypeEnumName") or "").strip() or "Active"



# This will be used to update the company user field.
def update_company_user_field(pk, name, value, session=None, environment=None):
    client = session or build_stratus_session(environment)
    env = _session_env(client)
    _, update_url = _company_admin_urls(env)
    response = client.put(
        update_url,
        files={
            "pk": (None, pk),
            "name": (None, name),
            "value": (None, _format_form_value(value)),
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.status_code



# This will be used to apply the steps.
def _apply_steps(pk, steps, session):
    user = get_company_user_by_pk(pk, session=session)
    before = _user_field_snapshot(user)
    applied_steps = []

    for step_name, step_value in steps:
        status_code = update_company_user_field(
            pk, step_name, step_value, session=session
        )
        applied_steps.append(
            {
                "name": step_name,
                "value": _format_form_value(step_value),
                "http_status": status_code,
            }
        )

    after_user = get_company_user_by_pk(pk, session=session)
    after = _user_field_snapshot(after_user)
    env = _session_env(session)

    return {
        "email": user.get("email"),
        "pk": pk,
        "user_id": user.get("userId"),
        "user_name": user.get("userName"),
        "environment": env["key"],
        "before": before,
        "after": after,
        "steps": applied_steps,
    }



# This will be used to disable the stratus user by pk.
def disable_stratus_user_by_pk(pk, session=None, environment=None, steps=None):
    client = session or build_stratus_session(environment)
    env = _session_env(client)
    disable_steps = steps or get_disable_steps(env)
    return _apply_steps(pk, disable_steps, client)


# This will be used to disable the stratus user by email.
def disable_stratus_user(email, session=None, environment=None, steps=None, all_matches=False):
    client = session or build_stratus_session(environment)
    if all_matches:
        users = get_all_company_users_by_email(email, session=client)
        return [
            disable_stratus_user_by_pk(user["id"], session=client, steps=steps)
            for user in users
        ]
    user = get_company_user_by_email(email, session=client)
    return disable_stratus_user_by_pk(user["id"], session=client, steps=steps)



# This will be used to enable the stratus user by pk.
def enable_stratus_user_by_pk(pk, session=None, environment=None, steps=None):
    client = session or build_stratus_session(environment)
    return _apply_steps(pk, steps or ENABLE_STEPS, client)



# This will be used to enable the stratus user by email.
def enable_stratus_user(email, session=None, environment=None, steps=None, all_matches=False):
    client = session or build_stratus_session(environment)
    if all_matches:
        users = get_all_company_users_by_email(email, session=client)
        return [
            enable_stratus_user_by_pk(user["id"], session=client, steps=steps)
            for user in users
        ]
    user = get_company_user_by_email(email, session=client)
    return enable_stratus_user_by_pk(user["id"], session=client, steps=steps)




