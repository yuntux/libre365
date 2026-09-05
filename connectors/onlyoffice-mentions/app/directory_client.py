"""
Simple directory stub via the Keycloak Admin API (study 2.7: "onRequestUsers must
query the directory -- simple stub: Keycloak Admin API to list the
realm's users"). A Keycloak service account with the `view-users` role
supplies `KEYCLOAK_ADMIN_TOKEN` (client_credentials, not implemented here to stay
a simple stub -- to be completed with the OAuth2 client-credentials flow in production).
"""

from __future__ import annotations

import os

import httpx

from app.types import DirectoryUser

KEYCLOAK_BASE_URL = os.environ.get("KEYCLOAK_BASE_URL", "https://auth.example.org")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "libre365")
KEYCLOAK_ADMIN_TOKEN = os.environ.get("KEYCLOAK_ADMIN_TOKEN", "")


async def list_realm_users(client: httpx.AsyncClient | None = None) -> list[DirectoryUser]:
    owns_client = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.get(
            f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_REALM}/users",
            params={"max": 1000},
            headers={"Authorization": f"Bearer {KEYCLOAK_ADMIN_TOKEN}"},
        )
    finally:
        if owns_client:
            await client.aclose()

    if response.status_code >= 400:
        raise RuntimeError(f"Keycloak admin API failed with status {response.status_code}")

    data = response.json() or []

    return [
        {
            "id": u.get("id") or "",
            "username": u.get("username") or "",
            "email": u.get("email") or "",
            "firstName": u.get("firstName"),
            "lastName": u.get("lastName"),
        }
        for u in data
        if u.get("enabled") is not False
    ]
