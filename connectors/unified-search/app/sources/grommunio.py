"""Mail search via IMAP SEARCH on the Grommunio side (study 2.2 line 391).

Grommunio does not expose a generic REST search API like Matrix/Seafile/
Vikunja: IMAP is the protocol to query. The "token" relayed here is NOT a
Keycloak JWT passed directly to IMAP (IMAP does not speak OAuth Bearer
natively) but an XOAUTH2 access token exchangeable via SASL, see RFC 7628 -
Grommunio (like most modern IMAP servers) supports XOAUTH2 authentication by
relaying the same Keycloak token issued for the user, which respects the
spirit of line 391 (no re-authentication/service account on the connector
side) without reinventing the IMAP protocol.

Simplified implementation: an async IMAP library (e.g. ``aioimaplib``, to be
added as a production dependency) would allow a full IMAP connection. Here,
the structure of the call and the result parsing are laid out, but the actual
IMAP connection is left as an explicit TODO, staying within the scope of "at
least the call and the connector's structure, even if the actual IMAP parsing
is simplified" (task instruction).
"""

from __future__ import annotations

import asyncio
import os

from app.types import SearchResultItem

IMAP_HOST = os.environ.get("GROMMUNIO_IMAP_HOST", "mail.example.org")
IMAP_PORT = int(os.environ.get("GROMMUNIO_IMAP_PORT", "993"))


async def search_grommunio(query: str, user_token: str) -> list[SearchResultItem]:
    # TODO(aioimaplib): replace this stub with a real IMAP connection.
    #
    # from aioimaplib import IMAP4_SSL
    # client = IMAP4_SSL(host=IMAP_HOST, port=IMAP_PORT)
    # await client.wait_hello_from_server()
    # await client.xoauth2(extract_user_from_token(user_token), user_token)
    # await client.select("INBOX")
    # _, data = await client.search(f'TEXT "{query}"')
    # results: list[SearchResultItem] = []
    # for uid in data[0].split():
    #     _, msg_data = await client.fetch(uid, "(RFC822.HEADER)")
    #     # ... parse envelope/subject/date from msg_data ...
    #     results.append(
    #         SearchResultItem(
    #             source="grommunio",
    #             id=str(uid),
    #             title=subject or "(no subject)",
    #             url=f"https://mail.example.org/webapp/index.html#eml={uid}",
    #             timestamp=date_iso,
    #         )
    #     )
    # await client.logout()
    # return results

    if not user_token:
        raise RuntimeError("missing user token for IMAP XOAUTH2 authentication")

    # Simulates the network call (latency + IMAP connection) so the overall
    # fan-out and its timeouts can be exercised end to end even without an
    # available IMAP server.
    await asyncio.sleep(0.01)

    return [
        SearchResultItem(
            source="grommunio",
            id="stub-imap-result",
            title=f'Simulated IMAP result for "{query}" (host: {IMAP_HOST}:{IMAP_PORT})',
            url="https://mail.example.org/webapp/",
            timestamp=None,
        )
    ]
