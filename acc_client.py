"""Autodesk API authentication."""

import os

import env_loader 
import requests

AUTODESK_CLIENT_ID = os.getenv("AUTODESK_CLIENT_ID")
AUTODESK_CLIENT_SECRET = os.getenv("AUTODESK_CLIENT_SECRET")
AUTODESK_BASE_URL = os.getenv("AUTODESK_BASE_URL", "https://developer.api.autodesk.com")
AUTODESK_IMPERSONATION_USER_ID = os.getenv("AUTODESK_IMPERSONATION_USER_ID")



# This will be used to get the Autodesk access token.
def get_autodesk_access_token():
    auth_url = f"{AUTODESK_BASE_URL}/authentication/v2/token"
    payload = {
        "client_id": AUTODESK_CLIENT_ID,
        "client_secret": AUTODESK_CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": "account:read account:write data:read data:write",
    }
    response = requests.post(
        auth_url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]

