"""
Critical scenario (study 4.5): "creating and syncing a file (Seafile)".

Uses the Seafile REST API (Web API v2.1) rather than the desktop sync
client: it is the API that the unified-search connector also consumes, and
it is enough to validate the upload -> presence -> deletion cycle without
depending on a heavy client.
"""

from __future__ import annotations

import io
import os
import uuid

import pytest
import requests

pytestmark = [pytest.mark.timeout(90)]


@pytest.fixture(scope="module")
def seafile_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.seafile}/api2/ping/", expected_statuses=(200,))


@pytest.fixture(scope="module")
def seafile_auth_token(base_urls, test_user, seafile_ready) -> str:
    """
    Native Seafile authentication (login/password) to obtain an API token.
    The Seafile SSO scenario via Keycloak is covered separately in
    test_sso_e2e.py.
    """
    response = requests.post(
        f"{base_urls.seafile}/api2/auth-token/",
        data={
            "username": os.environ.get("TEST_SEAFILE_USERNAME", test_user.email),
            "password": os.environ.get("TEST_SEAFILE_PASSWORD", test_user.password),
        },
        timeout=15,
    )
    if response.status_code != 200:
        pytest.fail(
            f"Seafile authentication failed on {base_urls.seafile}: "
            f"HTTP {response.status_code} - {response.text[:300]}"
        )
    token = response.json().get("token")
    if not token:
        pytest.fail(f"Seafile response without a token: {response.text[:300]}")
    return token


@pytest.fixture(scope="module")
def seafile_headers(seafile_auth_token: str) -> dict:
    return {"Authorization": f"Token {seafile_auth_token}"}


@pytest.fixture(scope="module")
def default_library_id(base_urls, seafile_headers) -> str:
    """
    Retrieves the id of the user's default test library, or creates one
    dedicated to the tests if none exists.
    """
    library_name = os.environ.get("TEST_SEAFILE_LIBRARY", "integration-tests")

    response = requests.get(
        f"{base_urls.seafile}/api2/repos/", headers=seafile_headers, timeout=15
    )
    response.raise_for_status()
    for repo in response.json():
        if repo.get("name") == library_name:
            return repo["id"]

    create_response = requests.post(
        f"{base_urls.seafile}/api2/repos/",
        headers=seafile_headers,
        data={"name": library_name, "desc": "Integration test suite library"},
        timeout=15,
    )
    if create_response.status_code not in (200, 201):
        pytest.fail(
            "Unable to create/retrieve the Seafile test library: "
            f"HTTP {create_response.status_code} - {create_response.text[:300]}"
        )
    return create_response.json()["repo_id"]


def test_create_upload_and_sync_file(base_urls, seafile_headers, default_library_id):
    """
    Full cycle: obtaining an upload URL, sending a file, checking its
    presence via the listing API (= "synchronization" visible server-side),
    then deletion so as not to pollute the staging environment between two
    runs.
    """
    file_name = f"integration-test-{uuid.uuid4()}.txt"
    file_content = b"Test content for the integration suite (test_file_sync_seafile.py)."

    upload_link_response = requests.get(
        f"{base_urls.seafile}/api2/repos/{default_library_id}/upload-link/",
        headers=seafile_headers,
        params={"p": "/"},
        timeout=15,
    )
    if upload_link_response.status_code != 200:
        pytest.fail(
            "Unable to obtain the Seafile upload URL: "
            f"HTTP {upload_link_response.status_code} - {upload_link_response.text[:300]}"
        )
    upload_url = upload_link_response.json().strip('"')

    upload_response = requests.post(
        upload_url,
        headers=seafile_headers,
        data={"parent_dir": "/"},
        files={"file": (file_name, io.BytesIO(file_content), "text/plain")},
        timeout=30,
    )
    assert upload_response.status_code in (200, 201), (
        f"Seafile upload failed: HTTP {upload_response.status_code} - "
        f"{upload_response.text[:300]}"
    )

    try:
        # Presence check: the file must appear in the root folder listing
        # ("synchronization" server-side).
        listing_response = requests.get(
            f"{base_urls.seafile}/api2/repos/{default_library_id}/dir/",
            headers=seafile_headers,
            params={"p": "/"},
            timeout=15,
        )
        listing_response.raise_for_status()
        names = [entry["name"] for entry in listing_response.json()]
        assert file_name in names, (
            f"The uploaded file {file_name!r} does not appear in the listing "
            f"of library {default_library_id} after upload: {names}"
        )
    finally:
        # Systematic cleanup, even if the presence assertion fails.
        requests.delete(
            f"{base_urls.seafile}/api2/repos/{default_library_id}/file/",
            headers=seafile_headers,
            params={"p": f"/{file_name}"},
            timeout=15,
        )
