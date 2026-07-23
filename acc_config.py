"""ACC environment settings (dev vs prod) and local SQLite paths."""

import os
from pathlib import Path

import env_loader  # noqa: F401
from env_loader import PROJECT_ROOT

BASE_DIR = PROJECT_ROOT

ENVIRONMENTS = {
    "dev": {
        "label": "Dev Hub",
        "db_path": BASE_DIR / "acc_dev_users.db",
        "account_id_env_var": "AUTODESK_DEV_ACCOUNT_ID",
    },
    "prod": {
        "label": "Production",
        "db_path": BASE_DIR / "acc_users.db",
        "account_id_env_var": "AUTODESK_PROD_ACCOUNT_ID",
    },
}


# This will be used to get the environment.
def get_environment(key=None):
    env_key = (key or os.getenv("ACC_ENVIRONMENT") or "dev").strip().lower()
    if env_key not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {env_key}")

    meta = ENVIRONMENTS[env_key]
    account_id_var = meta["account_id_env_var"]
    return {
        "key": env_key,
        "label": meta["label"],
        "account_id": (os.getenv(account_id_var) or "").strip(),
        "db_path": meta["db_path"],
        "account_id_env_var": account_id_var,
    }


# This will be used to list the environments.
def list_environments():
    return [get_environment(key) for key in ENVIRONMENTS]
