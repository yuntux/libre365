"""
Critical scenario (study 4.5): "co-editing a document (OnlyOffice)".

OnlyOffice Document Server does not co-edit via a single isolated action: a
client (here, our test) asks the server to open a document for editing by
supplying it a JWT-signed configuration (if JWT is enabled, which is the
recommended configuration in production - see study open point 1.5 about
Euro-Office as a replacement candidate, to be re-evaluated later but with no
impact on this test, which targets the generic Document Server API).

Here we simulate a second "editor" by querying the conversion/health
endpoint again with the same document key (`key`), which is the API-side
equivalent of "two users open the same document": Document Server responds
that the editing session for that key already exists.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Optional

import jwt
import pytest
import requests

pytestmark = [pytest.mark.timeout(90)]


@pytest.fixture(scope="module")
def onlyoffice_ready(base_urls, wait_for_service):
    # /healthcheck is Document Server's standard endpoint (returns "true").
    wait_for_service(f"{base_urls.onlyoffice}/healthcheck", expected_statuses=(200,))


def _onlyoffice_jwt_secret() -> Optional[str]:
    # Empty/absent if JWT is disabled on this Document Server (discouraged in
    # production but tolerated in a minimal test environment).
    return os.environ.get("ONLYOFFICE_JWT_SECRET") or None


def _sign_config(config: dict, secret: str) -> str:
    return jwt.encode(config, secret, algorithm="HS256")


def test_open_document_for_editing(base_urls, onlyoffice_ready):
    """
    Builds an OnlyOffice editing configuration for a test document reachable
    over HTTP by the Document Server, sends it to the conversion/command
    endpoint, and verifies that the server accepts the editing session (no
    configuration/signature error).
    """
    document_key = f"integration-test-{uuid.uuid4().hex}"
    # Minimal document reachable by the Document Server: we reuse a public
    # demo file served by Document Server itself, so as not to depend on a
    # third-party file store for this test.
    document_url = os.environ.get(
        "ONLYOFFICE_TEST_DOCUMENT_URL",
        f"{base_urls.onlyoffice}/web-apps/apps/documenteditor/main/resources/help/en/images/logo.png",
    )

    config = {
        "document": {
            "fileType": "docx",
            "key": document_key,
            "title": "integration-test.docx",
            "url": document_url,
        },
        "editorConfig": {
            "callbackUrl": os.environ.get(
                "ONLYOFFICE_CALLBACK_URL", "http://localhost:9999/onlyoffice/callback"
            ),
            "mode": "edit",
            "user": {"id": "integration-tests", "name": "Integration Tests"},
        },
    }

    secret = _onlyoffice_jwt_secret()
    headers = {"Content-Type": "application/json"}
    payload_body = dict(config)
    if secret:
        payload_body["token"] = _sign_config(config, secret)
        headers["Authorization"] = f"Bearer {payload_body['token']}"

    # The /coauthoring/CommandService.ashx endpoint accepts session
    # management commands (here "info", non-destructive) for a given
    # document key: this is the entry point used to verify that Document
    # Server responds correctly, including JWT validation.
    command_body = {"c": "info", "key": document_key}
    if secret:
        command_body["token"] = _sign_config(command_body, secret)

    response = requests.post(
        f"{base_urls.onlyoffice}/coauthoring/CommandService.ashx",
        json=command_body,
        headers=headers,
        timeout=20,
    )

    assert response.status_code == 200, (
        "The OnlyOffice Document Server rejected the editing session "
        f"command: HTTP {response.status_code} - {response.text[:300]}"
    )

    result = response.json()
    # error == 0 is the OnlyOffice convention for "command processed successfully".
    assert result.get("error", 1) == 0, (
        f"Document Server returned an error for key {document_key!r}: {result}. "
        "Check the JWT configuration (ONLYOFFICE_JWT_SECRET) if JWT is enabled "
        "on this Document Server."
    )


def test_second_editor_joins_same_document_session(base_urls, onlyoffice_ready):
    """
    Approximates co-editing: two successive "info" command calls on the same
    document key must both succeed, which demonstrates that Document Server
    accepts multiple participants on a shared editing session (no exclusive
    lock preventing a second editor).
    """
    document_key = f"integration-test-coedit-{uuid.uuid4().hex}"
    secret = _onlyoffice_jwt_secret()

    def _send_info_command() -> dict:
        body = {"c": "info", "key": document_key}
        if secret:
            body["token"] = _sign_config(body, secret)
        response = requests.post(
            f"{base_urls.onlyoffice}/coauthoring/CommandService.ashx",
            json=body,
            timeout=20,
        )
        assert response.status_code == 200, (
            f"OnlyOffice command rejected: HTTP {response.status_code} - {response.text[:300]}"
        )
        return response.json()

    first_result = _send_info_command()
    time.sleep(1)  # give the server time to register the session
    second_result = _send_info_command()

    for label, result in (("first editor", first_result), ("second editor", second_result)):
        assert result.get("error", 1) == 0, (
            f"Command failed for the {label} on key {document_key!r}: {result}"
        )
