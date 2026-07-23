"""Sync Autodesk ACC data into local SQLite databases."""

import sqlite3
from datetime import datetime, timezone

from acc_api import (
    build_auth_headers,
    fetch_account_users,
    fetch_project_users,
    fetch_projects,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    name TEXT,
    status TEXT,
    job_number TEXT,
    synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    status TEXT,
    synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_user_roles (
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    synced_at TEXT NOT NULL,
    PRIMARY KEY (project_id, user_id, role)
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    project_count INTEGER DEFAULT 0,
    user_count INTEGER DEFAULT 0,
    error TEXT
);
"""

# This is the function that initialized the database
def init_db(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "status" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN status TEXT")
        conn.commit()


# This is the function that searches for users in the database
def search_users(db_path, query, limit=10):
    term = f"%{query.strip()}%"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT user_id, first_name, last_name, email, status
            FROM users
            WHERE email LIKE ?
               OR first_name LIKE ?
               OR last_name LIKE ?
               OR (first_name || ' ' || last_name) LIKE ?
            ORDER BY email
            LIMIT ?
            """,
            (term, term, term, term, limit),
        ).fetchall()
    return [dict(row) for row in rows]



# This is the function that searches for a user by email
def get_user_by_email(db_path, email):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT user_id, first_name, last_name, email, status
            FROM users
            WHERE lower(email) = lower(?)
            LIMIT 1
            """,
            (email.strip(),),
        ).fetchone()
    return dict(row) if row else None


# This is the function that gets the sync status
def get_sync_status(db_path, environment):
    if not db_path.exists():
        return {
            "environment": environment,
            "synced": False,
            "project_count": 0,
            "user_count": 0,
            "last_sync": None,
            "last_status": None,
        }

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        last_run = conn.execute(
            """
            SELECT started_at, finished_at, status, project_count, user_count, error
            FROM sync_runs
            WHERE environment = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (environment,),
        ).fetchone()

    return {
        "environment": environment,
        "synced": user_count > 0,
        "project_count": project_count,
        "user_count": user_count,
        "last_sync": last_run["finished_at"] if last_run else None,
        "last_status": last_run["status"] if last_run else None,
        "last_error": last_run["error"] if last_run else None,
    }


# This is the function that gets the current UTC time
def _utc_now():
    return datetime.now(timezone.utc).isoformat()


# This is the function that syncs the environment
def sync_environment(env, base_url, get_access_token, impersonation_user_id=None):
    init_db(env["db_path"])
    started_at = _utc_now()

    with sqlite3.connect(env["db_path"]) as conn:
        run_id = conn.execute(
            """
            INSERT INTO sync_runs (environment, started_at, status)
            VALUES (?, ?, 'running')
            """,
            (env["key"], started_at),
        ).lastrowid
        conn.commit()

    try:
        if not env["account_id"]:
            raise ValueError(
                f"Account ID is not configured for {env['label']}. "
                f"Set {env['account_id_env_var']} in a .env file in the project folder."
            )

        access_token = get_access_token()
        headers = build_auth_headers(access_token, impersonation_user_id)
        synced_at = _utc_now()

        users_by_id = {}
        for account_user in fetch_account_users(base_url, env["account_id"], headers):
            user_id = account_user.get("id")
            if not user_id:
                continue
            users_by_id[user_id] = {
                "user_id": user_id,
                "first_name": account_user.get("first_name") or "",
                "last_name": account_user.get("last_name") or "",
                "email": account_user.get("email") or "",
                "status": account_user.get("status") or "",
                "synced_at": synced_at,
            }

        projects = fetch_projects(base_url, env["account_id"], headers)
        project_user_rows = []

        for project in projects:
            project_id = project.get("id") or project.get("projectId")
            if not project_id:
                continue

            project_users = fetch_project_users(base_url, project_id, headers)
            for project_user in project_users:
                user_id = (
                    project_user.get("id")
                    or project_user.get("autodeskId")
                    or project_user.get("userId")
                )
                if not user_id:
                    continue

                if user_id not in users_by_id:
                    users_by_id[user_id] = {
                        "user_id": user_id,
                        "first_name": (
                            project_user.get("firstName")
                            or project_user.get("first_name")
                            or ""
                        ),
                        "last_name": (
                            project_user.get("lastName")
                            or project_user.get("last_name")
                            or ""
                        ),
                        "email": project_user.get("email") or "",
                        "status": "",
                        "synced_at": synced_at,
                    }
                role = (
                    project_user.get("role")
                    or project_user.get("accessLevel")
                    or ""
                )
                project_user_rows.append((project_id, user_id, role, synced_at))

        with sqlite3.connect(env["db_path"]) as conn:
            conn.execute("DELETE FROM project_user_roles")
            conn.execute("DELETE FROM users")
            conn.execute("DELETE FROM projects")

            for project in projects:
                project_id = project.get("id") or project.get("projectId")
                if not project_id:
                    continue
                conn.execute(
                    """
                    INSERT INTO projects (project_id, account_id, name, status, job_number, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        env["account_id"],
                        project.get("name"),
                        project.get("status"),
                        project.get("jobNumber") or project.get("job_number"),
                        synced_at,
                    ),
                )

            conn.executemany(
                """
                INSERT INTO users (user_id, first_name, last_name, email, status, synced_at)
                VALUES (:user_id, :first_name, :last_name, :email, :status, :synced_at)
                """,
                users_by_id.values(),
            )
            conn.executemany(
                """
                INSERT INTO project_user_roles (project_id, user_id, role, synced_at)
                VALUES (?, ?, ?, ?)
                """,
                project_user_rows,
            )
            conn.execute(
                """
                UPDATE sync_runs
                SET finished_at = ?, status = 'success', project_count = ?, user_count = ?
                WHERE id = ?
                """,
                (_utc_now(), len(projects), len(users_by_id), run_id),
            )
            conn.commit()

        return {
            "environment": env["key"],
            "status": "success",
            "project_count": len(projects),
            "user_count": len(users_by_id),
            "synced_at": synced_at,
        }
    except Exception as exc:
        with sqlite3.connect(env["db_path"]) as conn:
            conn.execute(
                """
                UPDATE sync_runs
                SET finished_at = ?, status = 'error', error = ?
                WHERE id = ?
                """,
                (_utc_now(), str(exc), run_id),
            )
            conn.commit()
        raise
