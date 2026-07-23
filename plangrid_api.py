"""
PlanGrid integration.

Preferred auth (what you found in DevTools):
  GET https://app.plangrid.com/proxy/aapi2/organizations/{org_id}/users
  Cookie session from Admin Console + x-requested-by: enterprise-app

Optional legacy auth:
  https://io.plangrid.com with PLANGRID_API_KEY (project remove APIs).
"""

import json

import requests

import env_loader  # noqa: F401
from env_loader import reload_env
from plangrid_config import (
    get_plangrid_settings,
    plangrid_configured,
    plangrid_enterprise_configured,
    plangrid_legacy_configured,
    plangrid_missing_settings,
)


class PlanGridConfigError(ValueError):
    pass


class PlanGridUserNotFoundError(LookupError):
    pass


class PlanGridApiError(ValueError):
    pass


# This will be used to normalize the email.
def _normalize_email(email):
    return (email or "").strip().lower()


# This will be used to extract the page items.
def _page_items(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "users", "projects", "items", "results", "content"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


# This will be used to get the user email.
def _user_email(user):
    if not isinstance(user, dict):
        return ""
    for key in ("email", "Email"):
        value = user.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    for nested_key in ("user_profile", "profile", "user"):
        nested = user.get(nested_key)
        if isinstance(nested, dict):
            email = nested.get("email")
            if isinstance(email, str) and email.strip():
                return email.strip().lower()
    return ""


# This will be used to get the user name.
def _user_name(user):
    if not isinstance(user, dict):
        return ""
    profile = user.get("user_profile") or user.get("profile") or {}
    if isinstance(profile, dict):
        first = (profile.get("first_name") or "").strip()
        last = (profile.get("last_name") or "").strip()
        full = f"{first} {last}".strip()
        if full:
            return full
        name = profile.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    name = user.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return ""


# This will be used to get the user uid.
def _user_uid(user):
    if not isinstance(user, dict):
        return ""
    for key in ("user_id", "uid", "user_uid", "id"):
        value = user.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    nested = user.get("user")
    if isinstance(nested, dict):
        return _user_uid(nested)
    return ""



# This will be used to get the enterprise headers.
def _enterprise_headers(settings):
    return {
        "Cookie": settings["session_cookie"],
        "Accept": "application/json, */*",
        "Referer": (
            f"{settings['app_base_url']}/enterprise/organizations/"
            f"{settings['org_id']}/users"
        ),
        "Origin": settings["app_base_url"],
        "x-requested-by": "enterprise-app",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        ),
    }


# This will be used to require the enterprise settings.
def _require_enterprise():
    reload_env()
    if not plangrid_enterprise_configured():
        missing = ", ".join(plangrid_missing_settings())
        raise PlanGridConfigError(
            f"PlanGrid Admin Console is not configured. Set {missing} in .env. "
            "Sign in at app.plangrid.com/enterprise, open Network tab, copy Cookie."
        )
    return get_plangrid_settings()


# This will be used to require the legacy settings.
def _require_legacy():
    reload_env()
    settings = get_plangrid_settings()
    if not settings["api_key"]:
        raise PlanGridConfigError(
            "PlanGrid legacy API key is not set (PLANGRID_API_KEY). "
            "Org user listing uses the Admin Console session instead."
        )
    return settings



# This will be used to make the enterprise request.
def _enterprise_request(method, path, *, params=None, json_body=None, timeout=45):
    settings = _require_enterprise()
    url = f"{settings['app_base_url']}{path}"
    headers = _enterprise_headers(settings)
    data = None
    if json_body is not None:
        # Admin Console sends JSON as text/plain (see DevTools DELETE).
        data = json.dumps(json_body, separators=(",", ":"))
        headers = dict(headers)
        headers["Content-Type"] = "text/plain;charset=UTF-8"
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            data=data,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise PlanGridApiError(f"PlanGrid request failed: {exc}") from exc

    if response.status_code in (401, 403):
        raise PlanGridConfigError(
            f"PlanGrid session rejected (HTTP {response.status_code}). "
            "Sign in again at app.plangrid.com and refresh PLANGRID_SESSION_COOKIE."
        )
    if response.status_code == 404:
        raise PlanGridUserNotFoundError("PlanGrid resource not found (404).")
    if response.status_code >= 400:
        snippet = (response.text or "").replace("\n", " ").strip()[:240]
        raise PlanGridApiError(
            f"PlanGrid HTTP {response.status_code}"
            f"{f': {snippet}' if snippet else ''}"
        )

    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise PlanGridApiError("PlanGrid returned non-JSON.") from exc


# This will be used to make the legacy request
def _legacy_request(method, path, *, params=None, timeout=30):
    settings = _require_legacy()
    url = f"{settings['legacy_base_url']}{path}"
    try:
        response = requests.request(
            method,
            url,
            auth=(settings["api_key"], ""),
            headers={"Accept": settings["legacy_accept"]},
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise PlanGridApiError(f"PlanGrid legacy request failed: {exc}") from exc

    if response.status_code == 204:
        return None
    if response.status_code == 401:
        raise PlanGridConfigError("PlanGrid API key is missing or rejected (401).")
    if response.status_code == 403:
        raise PlanGridApiError(
            "PlanGrid returned 403 — this key/account may not have permission "
            "for that project action."
        )
    if response.status_code == 404:
        raise PlanGridUserNotFoundError("PlanGrid project or user was not found (404).")
    if response.status_code >= 400:
        snippet = (response.text or "").replace("\n", " ").strip()[:240]
        raise PlanGridApiError(
            f"PlanGrid HTTP {response.status_code}"
            f"{f': {snippet}' if snippet else ''}"
        )

    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise PlanGridApiError("PlanGrid returned non-JSON.") from exc


# This will be used to list the organization users.
def list_organization_users(
    *,
    include_license=True,
    include_profile=True,
    include_projects=False,
    limit=500,
):
    """
    List org users from Admin Console (the route you found).

    Query params (same as DevTools):
      include_license, include_profile, include_projects, limit, skip
    """
    settings = _require_enterprise()
    path = settings["org_users_path"].format(org_id=settings["org_id"])
    items = []
    skip = 0
    page_size = 50
    while len(items) < limit:
        payload = _enterprise_request(
            "GET",
            path,
            params={
                "include_license": "true" if include_license else "false",
                "include_profile": "true" if include_profile else "false",
                "include_projects": "true" if include_projects else "false",
                "limit": page_size,
                "skip": skip,
            },
        )
        batch = _page_items(payload)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < page_size:
            break
        skip += page_size
    return items[:limit]


# This will be used to find the organization user by email.
def find_organization_user_by_email(email):
    needle = _normalize_email(email)
    if not needle:
        raise ValueError("email is required.")
    for user in list_organization_users(limit=5000):
        if _user_email(user) == needle:
            return user
    raise PlanGridUserNotFoundError(f"No PlanGrid org user with email {needle}.")


# This will be used to remove the organization users.
def remove_organization_users(user_ids, *, unlink_org_project=True, dry_run=False):
    """
    Remove users from the organization (Admin Console delete).

    DELETE /proxy/aapi1/organization/{org_id}/users
    Body: {"user_ids":[...], "unlink_org_project": true}
    """
    ids = [str(uid).strip() for uid in (user_ids or []) if str(uid).strip()]
    if not ids:
        raise ValueError("user_ids is required.")

    settings = _require_enterprise()
    path = settings["org_remove_path"].format(org_id=settings["org_id"])
    body = {
        "user_ids": ids,
        "unlink_org_project": bool(unlink_org_project),
    }
    if dry_run:
        return {
            "platform": "plangrid",
            "dry_run": True,
            "path": path,
            "body": body,
            "message": f"Dry run: would remove {len(ids)} PlanGrid user(s) from the org.",
        }

    response = _enterprise_request("DELETE", path, json_body=body)
    return {
        "platform": "plangrid",
        "dry_run": False,
        "user_ids": ids,
        "unlink_org_project": bool(unlink_org_project),
        "response": response,
        "message": f"Removed {len(ids)} PlanGrid user(s) from the organization.",
    }


# This will be used to remove the organization user by email.
def remove_organization_user_by_email(email, *, unlink_org_project=True, dry_run=False):
    """Look up an org user by email, then DELETE them from the organization."""
    user = find_organization_user_by_email(email)
    user_id = (user.get("user_id") or "").strip()
    if not user_id:
        raise PlanGridApiError("PlanGrid user record is missing user_id.")

    result = remove_organization_users(
        [user_id],
        unlink_org_project=unlink_org_project,
        dry_run=dry_run,
    )
    result["email"] = _normalize_email(email)
    result["name"] = _user_name(user)
    result["status_before"] = user.get("status")
    if dry_run:
        result["message"] = (
            f"Dry run: would remove {result['email']} ({user_id}) from PlanGrid org."
        )
    else:
        result["message"] = f"Removed {result['email']} from PlanGrid organization."
    return result


# This will be used to list the projects.
def list_projects(limit=50, skip=0):
    """Legacy API: projects visible to PLANGRID_API_KEY."""
    items = []
    current_skip = skip
    page_size = min(max(limit, 1), 50)
    while True:
        payload = _legacy_request(
            "GET",
            "/projects",
            params={"limit": page_size, "skip": current_skip},
        )
        batch = _page_items(payload)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < page_size or len(items) >= limit:
            break
        current_skip += page_size
    return items[:limit]



# This will be used to list the project users.
def list_project_users(project_uid, limit=200):
    """Legacy API: users on one project team."""
    project_uid = (project_uid or "").strip()
    if not project_uid:
        raise ValueError("project_uid is required.")

    items = []
    skip = 0
    page_size = 50
    while len(items) < limit:
        payload = _legacy_request(
            "GET",
            f"/projects/{project_uid}/users",
            params={"limit": page_size, "skip": skip},
        )
        batch = _page_items(payload)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < page_size:
            break
        skip += page_size
    return items[:limit]



# This will be used to find the user on the project.
def find_user_on_project(project_uid, email):
    needle = _normalize_email(email)
    if not needle:
        raise ValueError("email is required.")
    for user in list_project_users(project_uid):
        if _user_email(user) == needle:
            return user
    raise PlanGridUserNotFoundError(
        f"No PlanGrid user with email {needle} on project {project_uid}."
    )



# This will be used to remove the user from the project.
def remove_user_from_project(project_uid, user_uid):
    """Legacy DELETE /projects/{project_uid}/users/{user_uid}."""
    project_uid = (project_uid or "").strip()
    user_uid = (user_uid or "").strip()
    if not project_uid or not user_uid:
        raise ValueError("project_uid and user_uid are required.")

    _legacy_request("DELETE", f"/projects/{project_uid}/users/{user_uid}")
    return {
        "platform": "plangrid",
        "project_uid": project_uid,
        "user_uid": user_uid,
        "message": f"Removed user {user_uid} from PlanGrid project {project_uid}.",
    }


# This will be used to remove the user from the project by email.
def remove_user_from_project_by_email(project_uid, email, *, dry_run=False):
    user = find_user_on_project(project_uid, email)
    user_uid = _user_uid(user)
    if not user_uid:
        raise PlanGridApiError("PlanGrid user record is missing a uid.")

    result = {
        "platform": "plangrid",
        "project_uid": project_uid,
        "email": _normalize_email(email),
        "user_uid": user_uid,
        "user": user,
        "dry_run": bool(dry_run),
    }
    if dry_run:
        result["message"] = (
            f"Dry run: would remove {result['email']} ({user_uid}) "
            f"from project {project_uid}."
        )
        return result

    remove_user_from_project(project_uid, user_uid)
    result["message"] = (
        f"Removed {result['email']} from PlanGrid project {project_uid}."
    )
    return result


# This will be used to check the plangrid health.
def check_plangrid_health():
    settings = get_plangrid_settings()
    label = settings["label"]
    if not plangrid_configured():
        return {
            "ok": False,
            "configured": False,
            "label": label,
            "message": (
                "PlanGrid not configured. Add PLANGRID_ORG_ID and PLANGRID_SESSION_COOKIE "
                "from Admin Console DevTools (the /proxy/aapi2/.../users request)."
            ),
        }

    if plangrid_enterprise_configured():
        try:
            users = list_organization_users(limit=50)
            return {
                "ok": True,
                "configured": True,
                "label": label,
                "auth": "enterprise_session",
                "user_count_sample": len(users),
                "org_id": settings["org_id"],
                "message": (
                    f"PlanGrid connected via Admin Console "
                    f"({len(users)} user(s) in first page)."
                ),
            }
        except (PlanGridConfigError, PlanGridApiError) as exc:
            return {
                "ok": False,
                "configured": True,
                "label": label,
                "auth": "enterprise_session",
                "message": str(exc),
            }

    try:
        projects = list_projects(limit=5)
        return {
            "ok": True,
            "configured": True,
            "label": label,
            "auth": "legacy_api_key",
            "project_count_sample": len(projects),
            "message": f"PlanGrid connected via API key ({len(projects)} project(s) in sample).",
        }
    except (PlanGridConfigError, PlanGridApiError) as exc:
        return {
            "ok": False,
            "configured": True,
            "label": label,
            "auth": "legacy_api_key",
            "message": str(exc),
        }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="PlanGrid API helpers")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--list-org-users", action="store_true")
    parser.add_argument("--email", default="", help="Find one org user by email")
    parser.add_argument(
        "--remove-org",
        action="store_true",
        help="Remove user from org (DELETE aapi1/organization/.../users)",
    )
    parser.add_argument("--list-projects", action="store_true")
    parser.add_argument("--project", default="", help="Project uid (legacy)")
    parser.add_argument("--list-users", action="store_true")
    parser.add_argument("--remove", action="store_true", help="Legacy project remove")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.health:
        print(json.dumps(check_plangrid_health(), indent=2))
    elif args.list_org_users:
        for user in list_organization_users(limit=500):
            print(f"{_user_uid(user)}\t{_user_email(user)}")
    elif args.remove_org:
        if not args.email:
            raise SystemExit("--email is required with --remove-org")
        print(
            json.dumps(
                remove_organization_user_by_email(args.email, dry_run=args.dry_run),
                indent=2,
                default=str,
            )
        )
    elif args.email and not args.remove:
        user = find_organization_user_by_email(args.email)
        print(json.dumps(user, indent=2, default=str))
    elif args.list_projects:
        for project in list_projects(limit=100):
            uid = project.get("uid") or project.get("id")
            name = project.get("name") or project.get("title") or ""
            print(f"{uid}\t{name}")
    elif args.list_users:
        if not args.project:
            raise SystemExit("--project is required with --list-users")
        for user in list_project_users(args.project):
            print(f"{_user_uid(user)}\t{_user_email(user)}")
    elif args.remove:
        if not args.project or not args.email:
            raise SystemExit("--project and --email are required with --remove")
        print(
            json.dumps(
                remove_user_from_project_by_email(
                    args.project, args.email, dry_run=args.dry_run
                ),
                indent=2,
                default=str,
            )
        )
    else:
        parser.print_help()
