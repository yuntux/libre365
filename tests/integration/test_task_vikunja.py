"""
Critical scenario (study 4.5): "creating and notifying a task (Vikunja)".

First verifies creation via the Vikunja REST API, then the associated
notification. The notification-hub connector (2.1 in the study) is the
target user notification center: when it is present and reachable, we
verify that it did relay the task-creation event. Otherwise (e.g. in a
minimal docker-compose environment without the connectors started), we fall
back to checking the state of the created task on the Vikunja side itself,
so this test remains independently replayable.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

pytestmark = [pytest.mark.timeout(90)]


@pytest.fixture(scope="module")
def vikunja_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.vikunja}/api/v1/info")


@pytest.fixture(scope="module")
def vikunja_token(base_urls, test_user, vikunja_ready) -> str:
    """
    Native Vikunja authentication. The Vikunja SSO scenario via Keycloak
    (OpenID Connect) is covered separately in test_sso_e2e.py.
    """
    response = requests.post(
        f"{base_urls.vikunja}/api/v1/login",
        json={
            "username": os.environ.get("TEST_VIKUNJA_USERNAME", test_user.username),
            "password": os.environ.get("TEST_VIKUNJA_PASSWORD", test_user.password),
        },
        timeout=15,
    )
    if response.status_code != 200:
        pytest.fail(
            f"Vikunja login failed on {base_urls.vikunja}: "
            f"HTTP {response.status_code} - {response.text[:300]}"
        )
    token = response.json().get("token")
    if not token:
        pytest.fail(f"Vikunja login response without a token: {response.text[:300]}")
    return token


@pytest.fixture()
def vikunja_headers(vikunja_token: str) -> dict:
    return {"Authorization": f"Bearer {vikunja_token}"}


@pytest.fixture()
def test_project(base_urls, vikunja_headers):
    """Creates a test Vikunja project and cleans it up (deletion) at the end of the test."""
    project_title = f"integration-test-{uuid.uuid4().hex[:8]}"
    create_response = requests.put(
        f"{base_urls.vikunja}/api/v1/projects",
        headers=vikunja_headers,
        json={"title": project_title},
        timeout=15,
    )
    if create_response.status_code not in (200, 201):
        pytest.fail(
            "Failed to create the test Vikunja project: "
            f"HTTP {create_response.status_code} - {create_response.text[:300]}"
        )
    project_id = create_response.json()["id"]

    yield project_id

    requests.delete(
        f"{base_urls.vikunja}/api/v1/projects/{project_id}",
        headers=vikunja_headers,
        timeout=15,
    )


def test_create_task_and_notification(base_urls, vikunja_headers, test_project):
    """
    Creates a task in the test project, then verifies:
    1. that the task does exist on the Vikunja side with the expected
       attributes;
    2. if notification-hub is reachable, that it did relay the event
       (best-effort check, does not block the scenario if the connector is
       not started in this environment).
    """
    task_title = f"Test task {uuid.uuid4()}"

    create_response = requests.put(
        f"{base_urls.vikunja}/api/v1/projects/{test_project}/tasks",
        headers=vikunja_headers,
        json={"title": task_title},
        timeout=15,
    )
    assert create_response.status_code in (200, 201), (
        f"Failed to create the Vikunja task: HTTP {create_response.status_code} - "
        f"{create_response.text[:300]}"
    )
    task_id = create_response.json()["id"]

    get_response = requests.get(
        f"{base_urls.vikunja}/api/v1/tasks/{task_id}",
        headers=vikunja_headers,
        timeout=15,
    )
    assert get_response.status_code == 200, (
        f"Created task (id={task_id}) not found when reading it back: "
        f"HTTP {get_response.status_code}"
    )
    assert get_response.json()["title"] == task_title

    _assert_notification_relayed_if_hub_available(base_urls, task_id, task_title)


def _assert_notification_relayed_if_hub_available(base_urls, task_id: int, task_title: str) -> None:
    hub_health_url = f"{base_urls.notification_hub}/health"
    try:
        health_response = requests.get(hub_health_url, timeout=5)
    except requests.exceptions.RequestException:
        pytest.skip(
            "notification-hub not reachable in this environment: "
            "notification check limited to the Vikunja task state."
        )
        return

    if health_response.status_code != 200:
        pytest.skip(
            f"notification-hub responds but with a failure ({health_response.status_code}): "
            "notification check skipped."
        )
        return

    # Polling the history of notifications relayed for this task
    # (endpoint expected of the notification-hub connector, study 2.1).
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        notifications_response = requests.get(
            f"{base_urls.notification_hub}/notifications",
            params={"source": "vikunja", "reference_id": str(task_id)},
            timeout=10,
        )
        if notifications_response.status_code == 200:
            notifications = notifications_response.json()
            if isinstance(notifications, list) and any(
                task_title in str(item) for item in notifications
            ):
                return
        time.sleep(2)

    pytest.fail(
        f"No notification relayed by notification-hub found for Vikunja "
        f"task {task_id} ({task_title!r}) after 30s."
    )
