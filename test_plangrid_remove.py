"""
Test PlanGrid Admin Console user listing (the DevTools route you found).

Setup:
  1. Sign in at https://app.plangrid.com/enterprise/.../users
  2. DevTools → Network → find:
       GET /proxy/aapi2/organizations/<ORG_ID>/users?...
  3. Copy:
       - org id from the URL path
       - full Cookie request header
  4. Add to .env:
       PLANGRID_ORG_ID=81d80f0c-984d-42d7-bd11-a3c6caa9c523
       PLANGRID_SESSION_COOKIE=<paste cookie>

Usage:
  python test_plangrid_remove.py --health
  python test_plangrid_remove.py --list-org-users
  python test_plangrid_remove.py --email someone@umci.com
  python test_plangrid_remove.py --remove-org --email someone@umci.com --dry-run
  python test_plangrid_remove.py --remove-org --email someone@umci.com
"""

from __future__ import annotations

import argparse
import json
import sys

import env_loader  # noqa: F401
from plangrid_api import (
    PlanGridApiError,
    PlanGridConfigError,
    PlanGridUserNotFoundError,
    _user_email,
    _user_uid,
    check_plangrid_health,
    find_organization_user_by_email,
    list_organization_users,
    list_project_users,
    list_projects,
    remove_organization_user_by_email,
    remove_user_from_project_by_email,
)



# This will be used to main function.
def main():
    parser = argparse.ArgumentParser(description="PlanGrid Admin Console / remove test")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--list-org-users", action="store_true")
    parser.add_argument("--email", default="", help="Look up one org user by email")
    parser.add_argument(
        "--remove-org",
        action="store_true",
        help="Remove from org via DELETE /proxy/aapi1/organization/.../users",
    )
    parser.add_argument("--list-projects", action="store_true", help="Legacy API key mode")
    parser.add_argument("--project", default="", help="Project uid (legacy remove)")
    parser.add_argument("--list-users", action="store_true")
    parser.add_argument("--remove", action="store_true", help="Legacy project remove")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        if args.health:
            print(json.dumps(check_plangrid_health(), indent=2))
            return 0

        if args.list_org_users:
            users = list_organization_users(limit=500)
            print(f"Found {len(users)} org user(s):\n")
            for user in users:
                print(f"  {_user_uid(user)}\t{_user_email(user)}")
            return 0

        if args.remove_org:
            if not args.email:
                print("--email is required with --remove-org", file=sys.stderr)
                return 2
            result = remove_organization_user_by_email(
                args.email,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, indent=2, default=str))
            return 0

        if args.email and not args.remove:
            user = find_organization_user_by_email(args.email)
            print(json.dumps(user, indent=2, default=str))
            return 0

        if args.list_projects:
            projects = list_projects(limit=100)
            print(f"Found {len(projects)} project(s):\n")
            for project in projects:
                uid = project.get("uid") or project.get("id")
                name = project.get("name") or project.get("title") or "(unnamed)"
                print(f"  {uid}\n    {name}")
            return 0

        if args.list_users:
            if not args.project:
                print("--project is required with --list-users", file=sys.stderr)
                return 2
            users = list_project_users(args.project)
            print(f"Found {len(users)} user(s) on project {args.project}:\n")
            for user in users:
                print(f"  {_user_uid(user)}\t{_user_email(user)}")
            return 0

        if args.remove:
            if not args.project or not args.email:
                print("--project and --email are required with --remove", file=sys.stderr)
                return 2
            result = remove_user_from_project_by_email(
                args.project,
                args.email,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, indent=2, default=str))
            return 0

        parser.print_help()
        return 2
    except (PlanGridConfigError, PlanGridApiError, PlanGridUserNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
