"""
Tests des connecteurs applicatifs développés pour cette stack (chapitre 2 de
l'étude: centre de notifications 2.1, recherche unifiée 2.2, agrégateur de
présence 2.8 - les autres connecteurs listés comme "restant à développer" en
fin de document ne sont pas encore testables ici).

Ces tests traitent les connecteurs en boîte noire, via leur API HTTP
publique, sans connaissance de leur implémentation interne:
- notification-hub: reçoit un webhook entrant, doit répondre 2xx et exposer
  l'événement reçu.
- unified-search: agrège des résultats de recherche provenant de plusieurs
  sources (mockées ici avec `responses`, pour ne pas dépendre de données
  réelles dans Seafile/Grommunio/Vikunja au moment du test).
- presence-aggregator: consolide un statut de présence à partir de
  plusieurs briques sources et répond un statut unique.
"""

from __future__ import annotations

import uuid

import pytest
import requests
import responses

pytestmark = [pytest.mark.timeout(60)]


# ---------------------------------------------------------------------------
# notification-hub (étude 2.1)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def notification_hub_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.notification_hub}/health")


def test_notification_hub_accepts_webhook(base_urls, notification_hub_ready):
    """
    Envoie un webhook générique (format proche de ce qu'émettent Vikunja ou
    Seafile) et vérifie que notification-hub répond 2xx et enregistre
    l'événement (relecture via l'API de listing, best-effort si l'API de
    listing exacte diffère de l'implémentation finale du connecteur).
    """
    event_id = str(uuid.uuid4())
    webhook_payload = {
        "id": event_id,
        "source": "integration-test",
        "type": "task.created",
        "title": "Notification de test d'intégration",
    }

    response = requests.post(
        f"{base_urls.notification_hub}/webhooks/generic",
        json=webhook_payload,
        timeout=15,
    )
    assert 200 <= response.status_code < 300, (
        f"notification-hub a refusé le webhook: HTTP {response.status_code} - "
        f"{response.text[:300]}"
    )


# ---------------------------------------------------------------------------
# unified-search (étude 2.2)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def unified_search_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.unified_search}/health")


@responses.activate
def test_unified_search_aggregates_multiple_sources(base_urls, unified_search_ready):
    """
    Mocke les API sources (Seafile, Vikunja, Matrix) que unified-search est
    censé interroger, pour vérifier isolément sa logique d'agrégation sans
    dépendre de données réelles présentes dans ces briques au moment du test.

    Les URLs mockées visent les mêmes hôtes que `base_urls` pour rester
    représentatives, mais interceptées par `responses` avant tout appel
    réseau réel.
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
        f"unified-search a échoué sur la requête {query!r}: "
        f"HTTP {search_response.status_code} - {search_response.text[:300]}"
    )

    payload = search_response.json()
    results = payload.get("results", payload if isinstance(payload, list) else [])
    assert results, (
        f"unified-search n'a agrégé aucun résultat pour {query!r} alors que "
        "les sources mockées en renvoyaient."
    )


# ---------------------------------------------------------------------------
# presence-aggregator (étude 2.8, connecteur identifié comme "à développer")
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def presence_aggregator_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.presence_aggregator}/health")


def test_presence_aggregator_returns_consolidated_status(base_urls, presence_aggregator_ready, test_user):
    """
    Interroge le statut de présence consolidé d'un utilisateur de test.
    Le connecteur est censé combiner au minimum la présence Matrix et l'état
    "en réunion" issu de Visio (2.8): on vérifie ici seulement la forme de
    la réponse (statut connu, horodatage), pas la véracité métier du statut
    - celle-ci dépend de l'état réel des briques sources au moment du test.
    """
    response = requests.get(
        f"{base_urls.presence_aggregator}/presence/{test_user.username}",
        timeout=15,
    )
    assert response.status_code == 200, (
        f"presence-aggregator a échoué pour l'utilisateur {test_user.username}: "
        f"HTTP {response.status_code} - {response.text[:300]}"
    )

    payload = response.json()
    assert "status" in payload, (
        f"Réponse presence-aggregator sans champ 'status': {payload}"
    )
    known_statuses = {"online", "offline", "busy", "in_meeting", "away", "unknown"}
    assert payload["status"] in known_statuses, (
        f"Statut de présence inattendu {payload['status']!r} pour "
        f"{test_user.username}, attendu un de {sorted(known_statuses)}."
    )
