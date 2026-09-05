"""Faithful port of test/fanout.test.ts.

Verifies the fan-out, the per-service timeout that does not block the other
responses, error isolation, and above all the exact relay of the user token.
"""

from __future__ import annotations

import asyncio

import pytest

from app.fanout import fan_out_search, merge_results
from app.types import SearchResultItem


async def delayed(value, seconds: float):
    await asyncio.sleep(seconds)
    return value


async def test_aggregates_results_from_sources_that_respond_in_time():
    calls = {"matrix": None, "seafile": None}

    async def matrix(query: str, user_token: str):
        calls["matrix"] = (query, user_token)
        return await delayed(
            [
                SearchResultItem(
                    source="matrix",
                    id="1",
                    title="hello",
                    url="http://x",
                    timestamp="2026-01-01T00:00:00Z",
                )
            ],
            0.005,
        )

    async def seafile(query: str, user_token: str):
        calls["seafile"] = (query, user_token)
        return await delayed(
            [
                SearchResultItem(
                    source="seafile",
                    id="2",
                    title="doc.docx",
                    url="http://y",
                    timestamp="2026-02-01T00:00:00Z",
                )
            ],
            0.005,
        )

    async def empty(query: str, user_token: str):
        return []

    outcomes = await fan_out_search(
        "hello",
        "user-token-abc",
        {"matrix": matrix, "seafile": seafile, "vikunja": empty, "grommunio": empty},
        100,
    )

    assert all(o.ok for o in outcomes)
    assert calls["matrix"] == ("hello", "user-token-abc")
    assert calls["seafile"] == ("hello", "user-token-abc")

    merged = merge_results(outcomes)
    assert len(merged) == 2
    # Sorted by date desc: seafile (February) should appear before matrix (January).
    assert merged[0].source == "seafile"


async def test_isolates_a_slow_service_via_timeout_without_blocking_others():
    async def fast(query: str, user_token: str):
        return await delayed(
            [SearchResultItem(source="vikunja", id="1", title="task", url="http://x")], 0.01
        )

    async def slow(query: str, user_token: str):
        return await delayed([], 0.5)

    async def empty(query: str, user_token: str):
        return []

    outcomes = await fan_out_search(
        "q",
        "token",
        {"matrix": empty, "seafile": empty, "vikunja": fast, "grommunio": slow},
        50,
    )

    vikunja_outcome = next(o for o in outcomes if o.source == "vikunja")
    grommunio_outcome = next(o for o in outcomes if o.source == "grommunio")

    assert vikunja_outcome.ok is True
    assert grommunio_outcome.ok is False
    assert "timeout" in grommunio_outcome.error


async def test_a_rejection_from_one_source_does_not_prevent_aggregating_the_others():
    async def failing(query: str, user_token: str):
        raise RuntimeError("service unavailable")

    async def ok(query: str, user_token: str):
        return [SearchResultItem(source="matrix", id="1", title="ok", url="http://x")]

    async def empty(query: str, user_token: str):
        return []

    outcomes = await fan_out_search(
        "q",
        "token",
        {"matrix": ok, "seafile": failing, "vikunja": empty, "grommunio": empty},
        100,
    )

    seafile_outcome = next(o for o in outcomes if o.source == "seafile")
    assert seafile_outcome.ok is False
    assert seafile_outcome.error == "service unavailable"
    assert next(o for o in outcomes if o.source == "matrix").ok is True


async def test_relays_the_same_user_token_to_all_sources_without_modifying_it():
    received_tokens = []

    async def spy(query: str, user_token: str):
        received_tokens.append(user_token)
        return []

    await fan_out_search(
        "q",
        "the-users-own-keycloak-token",
        {"matrix": spy, "seafile": spy, "vikunja": spy, "grommunio": spy},
        100,
    )

    for token in received_tokens:
        assert token == "the-users-own-keycloak-token"
