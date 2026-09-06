"""Verifies the Keycloak access token the app-portal banner's own silent-SSO
client (study 2.3, `libre365-portal` - a public/PKCE client, see
infra/ansible/roles/keycloak_realm/defaults/main.yml) sends with every call
to this connector's `/portal/apps` endpoint.

Real signature verification (RS256 against Keycloak's own JWKS, cached) and
issuer check - not just a naive base64 decode of the payload, which would let
anyone forge a token claiming to be in any group. `PyJWT`'s `PyJWKClient`
handles JWKS fetch/cache/key-rotation itself.
"""

from __future__ import annotations

import os
from typing import List, Optional

import jwt
from jwt import PyJWKClient

KEYCLOAK_ISSUER = os.environ.get("KEYCLOAK_ISSUER", "https://sso.example.org/realms/libre365")

_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs")
    return _jwks_client


class InvalidToken(Exception):
    pass


def verify_token(bearer_header: str) -> dict:
    """Raises InvalidToken on any failure (missing header, bad signature,
    expired, wrong issuer). Returns the decoded claims on success."""
    if not bearer_header.lower().startswith("bearer "):
        raise InvalidToken("missing Authorization: Bearer <token> header")
    token = bearer_header[7:]

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=KEYCLOAK_ISSUER,
            # No `audience` check: this token is a generic Keycloak access
            # token (default `aud: "account"`), not minted for this
            # connector specifically - the issuer check already scopes it
            # to this realm, which is the actual trust boundary here.
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as err:
        raise InvalidToken(str(err)) from err

    return claims


def groups_from_claims(claims: dict) -> List[str]:
    """Keycloak's "Group Membership" mapper (see the Ansible role) emits
    group PATHS ("/consultants"), not bare names - stripped here so callers
    can compare against platform.yaml's plain group names."""
    return [g.lstrip("/") for g in claims.get("groups") or []]
