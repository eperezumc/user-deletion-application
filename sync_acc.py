#!/usr/bin/env python3
"""Sync ACC projects and users from Autodesk into the local environment database."""

import argparse

import env_loader  # noqa: F401
from acc_client import AUTODESK_BASE_URL, AUTODESK_IMPERSONATION_USER_ID, get_autodesk_access_token
from acc_config import get_environment
from acc_sync import sync_environment

# This will be used to sync the ACC projects and the users.
def main():
    parser = argparse.ArgumentParser(description="Sync ACC projects and users from Autodesk.")
    parser.add_argument(
        "--environment",
        choices=["dev", "prod"],
        default="dev",
        help="Target environment database (default: dev)",
    )
    args = parser.parse_args()

    env = get_environment(args.environment)
    result = sync_environment(
        env,
        base_url=AUTODESK_BASE_URL,
        get_access_token=get_autodesk_access_token,
        impersonation_user_id=AUTODESK_IMPERSONATION_USER_ID,
    )
    print(result)


if __name__ == "__main__":
    main()
