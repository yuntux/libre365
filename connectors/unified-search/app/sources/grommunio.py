"""Mail search via IMAP SEARCH on the Grommunio side (study 2.2 line 391).

Grommunio does not expose a generic REST search API like Matrix/Seafile/
Vikunja: IMAP is the protocol to query. The "token" relayed here is NOT a
Keycloak JWT passed directly to IMAP (IMAP does not speak OAuth Bearer
natively) but an XOAUTH2 access token exchangeable via SASL, see RFC 7628 -
Grommunio (like most modern IMAP servers) supports XOAUTH2 authentication by
relaying the same Keycloak token issued for the user, which respects the
spirit of line 391 (no re-authentication/service account on the connector
side) without reinventing the IMAP protocol.

Implemented with ``aioimaplib`` (async IMAP4 client). The exact shape of its
``Response.lines`` for a FETCH command is not documented in its public API,
so the parsing below (see ``_extract_fetch_literal``) was verified against a
minimal fake IMAP server speaking the real wire protocol, not just against
mocks of the client class.
"""

from __future__ import annotations

import json
import os
import re
from base64 import urlsafe_b64decode
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from typing import Callable, Optional

from aioimaplib import IMAP4_SSL

from app.types import SearchResultItem

IMAP_HOST = os.environ.get("GROMMUNIO_IMAP_HOST", "mail.example.org")
IMAP_PORT = int(os.environ.get("GROMMUNIO_IMAP_PORT", "993"))
IMAP_TIMEOUT_SECONDS = float(os.environ.get("GROMMUNIO_IMAP_TIMEOUT_SECONDS", "10"))
WEBMAIL_BASE_URL = os.environ.get(
    "GROMMUNIO_WEBMAIL_BASE_URL", "https://mail.example.org/webapp"
)

# Matches aioimaplib's untagged FETCH opening line, e.g.
# b'1 FETCH (RFC822.HEADER {123}' - the literal payload is the very next
# element of Response.lines (verified empirically, see module docstring).
_FETCH_LITERAL_OPENING_RE = re.compile(rb"^\d+ FETCH \(.*\{\d+\}\s*$")


def _extract_username(user_token: str) -> str:
    """Best-effort extraction of a mailbox-routing hint (JWT
    `preferred_username`/`email` claim) for XOAUTH2's `user=` field, WITHOUT
    validating the token's signature - validation is the SSO provider's job;
    Grommunio authenticates the request from the token itself (RFC 7628),
    this is only a hint some servers use for logging/routing."""
    try:
        payload_b64 = user_token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        claims = json.loads(urlsafe_b64decode(padded))
        return claims.get("preferred_username") or claims.get("email") or "unknown"
    except Exception:
        return "unknown"


def _extract_fetch_literal(lines: list) -> Optional[bytes]:
    for i, line in enumerate(lines):
        if isinstance(line, (bytes, bytearray)) and _FETCH_LITERAL_OPENING_RE.match(bytes(line)):
            if i + 1 < len(lines):
                return bytes(lines[i + 1])
    return None


def _parse_header(raw: bytes) -> tuple[str, Optional[str]]:
    message = message_from_bytes(raw)
    subject = message.get("Subject") or "(no subject)"
    date_header = message.get("Date")
    timestamp: Optional[str] = None
    if date_header:
        try:
            timestamp = parsedate_to_datetime(date_header).isoformat()
        except (TypeError, ValueError):
            timestamp = None
    return subject, timestamp


async def search_grommunio(
    query: str,
    user_token: str,
    client_factory: Optional[Callable[[], object]] = None,
) -> list[SearchResultItem]:
    if not user_token:
        raise RuntimeError("missing user token for IMAP XOAUTH2 authentication")

    client = (
        client_factory
        or (lambda: IMAP4_SSL(host=IMAP_HOST, port=IMAP_PORT, timeout=IMAP_TIMEOUT_SECONDS))
    )()

    await client.wait_hello_from_server()
    try:
        auth_response = await client.xoauth2(_extract_username(user_token), user_token)
        if auth_response.result != "OK":
            raise RuntimeError(
                f"Grommunio IMAP XOAUTH2 authentication failed: {auth_response.result}"
            )

        select_response = await client.select("INBOX")
        if select_response.result != "OK":
            raise RuntimeError(f"Grommunio IMAP SELECT failed: {select_response.result}")

        search_response = await client.search(f'TEXT "{query}"')
        if search_response.result != "OK":
            raise RuntimeError(f"Grommunio IMAP SEARCH failed: {search_response.result}")

        sequence_numbers = (
            search_response.lines[0].split()
            if search_response.lines and search_response.lines[0]
            else []
        )

        results: list[SearchResultItem] = []
        for seq in sequence_numbers:
            seq_str = seq.decode() if isinstance(seq, (bytes, bytearray)) else str(seq)
            fetch_response = await client.fetch(seq_str, "(RFC822.HEADER)")
            if fetch_response.result != "OK":
                continue
            header_bytes = _extract_fetch_literal(fetch_response.lines)
            subject, timestamp = (
                _parse_header(header_bytes) if header_bytes else ("(no subject)", None)
            )
            results.append(
                SearchResultItem(
                    source="grommunio",
                    id=seq_str,
                    title=subject,
                    url=f"{WEBMAIL_BASE_URL}/index.html#eml={seq_str}",
                    timestamp=timestamp,
                )
            )

        return results
    finally:
        try:
            await client.logout()
        except Exception:
            pass
