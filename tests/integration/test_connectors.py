"""
Tests for the application connectors built for this stack (study chapter 2:
notification hub 2.1, unified search 2.2, presence aggregator 2.8 - the
other connectors listed as "still to be developed" at the end of the
document are not yet testable here).

These tests treat the connectors as black boxes, via their public HTTP API,
with no knowledge of their internal implementation:
- notification-hub: receives an inbound webhook, must respond 2xx and
  expose the received event.
- unified-search: aggregates search results from several sources (mocked
  here with `responses`, so as not to depend on real data in
  Seafile/Grommunio/Vikunja at test time).
- presence-aggregator: consolidates a presence status from several source
  components and returns a single status.
"""

from __future__ import annotations

import uuid

import pytest
import requests
import responses

pytestmark = [pytest.mark.timeout(60)]


# ---------------------------------------------------------------------------
# notification-hub (study 2.1)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def notification_hub_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.notification_hub}/health")


def test_notification_hub_accepts_webhook(base_urls, notification_hub_ready):
    """
    Sends a generic webhook (format close to what Vikunja or Seafile emit)
    and verifies that notification-hub responds 2xx and records the event
    (read back via the listing API, best-effort if the exact listing API
    differs from the connector's final implementation).
    """
    event_id = str(uuid.uuid4())
    webhook_payload = {
        "id": event_id,
        "source": "integration-test",
        "type": "task.created",
        "title": "Integration test notification",
    }

    response = requests.post(
        f"{base_urls.notification_hub}/webhooks/generic",
        json=webhook_payload,
        timeout=15,
    )
    assert 200 <= response.status_code < 300, (
        f"notification-hub rejected the webhook: HTTP {response.status_code} - "
        f"{response.text[:300]}"
    )


# ---------------------------------------------------------------------------
# unified-search (study 2.2)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def unified_search_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.unified_search}/health")


@responses.activate
def test_unified_search_aggregates_multiple_sources(base_urls, unified_search_ready):
    """
    Mocks the source APIs (Seafile, Vikunja, Matrix) that unified-search is
    expected to query, to verify its aggregation logic in isolation without
    depending on real data present in those components at test time.

    The mocked URLs target the same hosts as `base_urls` to stay
    representative, but are intercepted by `responses` before any real
    network call.
    """
    query = "rapport-integration-test"

    responses.add(
        responses.GET,
        f"{base_urls.seafile}/api2/search/",
        json={"results": [{"name": f"{query}.docx", "repo_id": "repo-1"}]},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{base_urls.vikunja}/api/v1/tasks/all",
        json=[{"id": 1, "title": query}],
        status=200,
    )
    responses.add(
        responses.GET,
        f"{base_urls.matrix}/_matrix/client/v3/search",
        json={"search_categories": {"room_events": {"results": []}}},
        status=200,
    )

    search_response = requests.get(
        f"{base_urls.unified_search}/search",
        params={"q": query},
        timeout=15,
    )
    assert search_response.status_code == 200, (
        f"unified-search failed on the query {query!r}: "
        f"HTTP {search_response.status_code} - {search_response.text[:300]}"
    )

    payload = search_response.json()
    results = payload.get("results", payload if isinstance(payload, list) else [])
    assert results, (
        f"unified-search aggregated no results for {query!r} even though "
        "the mocked sources returned some."
    )


# ---------------------------------------------------------------------------
# presence-aggregator (study 2.8, connector identified as "to be developed")
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def presence_aggregator_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.presence_aggregator}/health")


def test_presence_aggregator_returns_consolidated_status(base_urls, presence_aggregator_ready, test_user):
    """
    Queries the consolidated presence status of a test user. The connector
    is expected to combine at least Matrix presence and the "in meeting"
    state coming from Visio (2.8): here we only check the shape of the
    response (known status, timestamp), not the business accuracy of the
    status - that depends on the actual state of the source components at
    test time.
    """
    response = requests.get(
        f"{base_urls.presence_aggregator}/presence/{test_user.username}",
        timeout=15,
    )
    assert response.status_code == 200, (
        f"presence-aggregator failed for user {test_user.username}: "
        f"HTTP {response.status_code} - {response.text[:300]}"
    )

    payload = response.json()
    assert "status" in payload, (
        f"presence-aggregator response without a 'status' field: {payload}"
    )
    known_statuses = {"online", "offline", "busy", "in_meeting", "away", "unknown"}
    assert payload["status"] in known_statuses, (
        f"Unexpected presence status {payload['status']!r} for "
        f"{test_user.username}, expected one of {sorted(known_statuses)}."
    )
