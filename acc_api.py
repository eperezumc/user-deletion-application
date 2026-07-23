"""Autodesk Construction Cloud API calls."""

import requests

from acc_client import AUTODESK_BASE_URL, get_autodesk_access_token



# This will be used to normalize the project id.
def normalize_project_id(project_id):
    return project_id[2:] if project_id.startswith("b.") else project_id



# This will be used to build the authentication headers.
def build_auth_headers(access_token, user_id=None):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    if user_id:
        headers["User-Id"] = user_id
    return headers



# This will be used to get the paginated results.
def paginated_get(url, headers, results_key="results"):
    items = []
    offset = 0
    limit = 100
    

    while True:
        response = requests.get(
            url,
            headers=headers,
            params={"offset": offset, "limit": limit},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get(results_key) or payload.get("data") or []
        if not isinstance(batch, list):
            break

        items.extend(batch)
        if len(batch) < limit:
            break

        offset += limit

    return items



# This will be used to fetch the projects.
def fetch_projects(base_url, account_id, headers):
    url = f"{base_url}/construction/admin/v1/accounts/{account_id}/projects"
    return paginated_get(url, headers)


# This will be used to fetch the project users.
def fetch_project_users(base_url, project_id, headers):
    normalized_id = normalize_project_id(project_id)
    url = f"{base_url}/construction/admin/v1/projects/{normalized_id}/users"
    return paginated_get(url, headers)



# This will be used to fetch the account users.
def fetch_account_users(base_url, account_id, headers):
    """All account members, including inactive/disabled users."""
    url = f"{base_url}/hq/v1/accounts/{account_id}/users"
    items = []
    offset = 0
    limit = 100

    while True:
        response = requests.get(
            url,
            headers=headers,
            params={"offset": offset, "limit": limit},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            batch = payload
        elif isinstance(payload, dict):
            batch = payload.get("results") or payload.get("data") or []
        else:
            break

        if not batch:
            break

        items.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    return items


# This will be used to set the user account status.
def set_user_account_status(
    email,
    user_id,
    account_id,
    status,
    base_url=AUTODESK_BASE_URL,
    access_token=None,
):
    token = access_token or get_autodesk_access_token()
    url = f"{base_url}/hq/v1/accounts/{account_id}/users/{user_id}"
    headers = build_auth_headers(token)

    response = requests.patch(
        url, headers=headers, json={"status": status}, timeout=30
    )
    response.raise_for_status()

    return {
        "email": email,
        "user_id": user_id,
        "account_id": account_id,
        "status": status,
        "http_status": response.status_code,
        "response": response.json() if response.content else {},
    }
