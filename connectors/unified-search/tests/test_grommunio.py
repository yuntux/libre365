"""Real protocol-level test for the Grommunio IMAP search source: a minimal
fake IMAP server (asyncio TCP, no TLS) that speaks just enough of the wire
protocol - CAPABILITY, AUTHENTICATE XOAUTH2, SELECT, SEARCH, FETCH, LOGOUT -
to exercise ``search_grommunio``'s real parsing logic end to end, rather than
mocking the ``aioimaplib`` client class (which would only prove the code
calls the right methods, not that it parses their responses correctly).
"""

from __future__ import annotations

import asyncio
import base64
import json

import pytest
from aioimaplib import IMAP4

from app.sources.grommunio import search_grommunio


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    writer.write(b"* OK IMAP4rev1 fake server ready\r\n")
    await writer.drain()
    while True:
        line = await reader.readline()
        if not line:
            break
        tag, _, rest = line.decode().strip().partition(" ")
        cmd, _, _ = rest.partition(" ")
        cmd = cmd.upper()

        if cmd == "CAPABILITY":
            writer.write(b"* CAPABILITY IMAP4rev1 AUTH=XOAUTH2\r\n")
            writer.write(f"{tag} OK CAPABILITY completed.\r\n".encode())
        elif cmd == "AUTHENTICATE":
            writer.write(f"{tag} OK AUTHENTICATE completed.\r\n".encode())
        elif cmd == "SELECT":
            writer.write(b"* 2 EXISTS\r\n* 0 RECENT\r\n")
            writer.write(f"{tag} OK [READ-WRITE] SELECT completed.\r\n".encode())
        elif cmd == "SEARCH":
            writer.write(b"* SEARCH 1 2\r\n")
            writer.write(f"{tag} OK SEARCH completed.\r\n".encode())
        elif cmd == "FETCH":
            header = b"Subject: Hello world\r\nDate: Mon, 01 Sep 2026 10:00:00 +0000\r\n\r\n"
            writer.write(f"* 1 FETCH (RFC822.HEADER {{{len(header)}}}\r\n".encode())
            writer.write(header)
            writer.write(b")\r\n")
            writer.write(f"{tag} OK FETCH completed.\r\n".encode())
        elif cmd == "LOGOUT":
            writer.write(b"* BYE logging out\r\n")
            writer.write(f"{tag} OK LOGOUT completed.\r\n".encode())
            await writer.drain()
            break
        else:
            writer.write(f"{tag} BAD unknown command\r\n".encode())
        await writer.drain()
    writer.close()


@pytest.fixture
async def fake_imap_server():
    server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        task = asyncio.ensure_future(server.serve_forever())
        try:
            yield port
        finally:
            task.cancel()


def _fake_jwt(preferred_username: str) -> str:
    payload = (
        base64.urlsafe_b64encode(json.dumps({"preferred_username": preferred_username}).encode())
        .decode()
        .rstrip("=")
    )
    return f"header.{payload}.sig"


async def test_search_grommunio_parses_real_imap_responses(fake_imap_server):
    port = fake_imap_server

    results = await search_grommunio(
        "hello",
        _fake_jwt("alice"),
        client_factory=lambda: IMAP4(host="127.0.0.1", port=port, timeout=5),
    )

    assert [r.id for r in results] == ["1", "2"]
    assert all(r.source == "grommunio" for r in results)
    assert all(r.title == "Hello world" for r in results)
    assert all(r.timestamp == "2026-09-01T10:00:00+00:00" for r in results)
    assert results[0].url.endswith("#eml=1")


async def test_search_grommunio_requires_a_token():
    with pytest.raises(RuntimeError, match="missing user token"):
        await search_grommunio("hello", "")
