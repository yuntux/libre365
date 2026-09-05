"""
Critical scenario (study 4.5): "sending/receiving mail (Grommunio)".

Uses the standard library's imaplib/smtplib rather than a Grommunio-specific
client: Grommunio exposes standard IMAP/SMTP, and sticking to the stdlib
limits the dependencies of this long-lived suite.

Marked `smoke` because it is one of the most critical usages identified in
the study (mail = the first point of the Office 365 -> free stack migration,
section 1).
"""

from __future__ import annotations

import imaplib
import os
import smtplib
import time
import uuid
from email.mime.text import MIMEText

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.timeout(120)]


def _unique_subject() -> str:
    return f"[integration-test] {uuid.uuid4()}"


@pytest.fixture()
def mail_credentials(test_user):
    """
    Grommunio is authenticated here with native IMAP/SMTP credentials (not
    via Keycloak): the end-to-end SSO scenario dedicated to Grommunio is
    covered separately in test_sso_e2e.py against Grommunio's web/API
    endpoint.
    """
    return {
        "address": os.environ.get("TEST_MAIL_ADDRESS", test_user.email),
        "password": os.environ.get("TEST_MAIL_PASSWORD", test_user.password),
    }


def test_send_and_receive_mail(base_urls, mail_credentials):
    """
    Sends a mail from the test user to themselves via SMTP, then verifies
    its receipt via IMAP within a reasonable delay (local delivery is
    generally near-instant on the Grommunio stack).
    """
    address = mail_credentials["address"]
    password = mail_credentials["password"]
    subject = _unique_subject()
    body = "Message sent by the integration test suite (test_mail_grommunio.py)."

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = address
    message["To"] = address

    # --- SMTP send ---
    try:
        with smtplib.SMTP(
            base_urls.grommunio_smtp_host, base_urls.grommunio_smtp_port, timeout=15
        ) as smtp:
            smtp.starttls()
            smtp.login(address, password)
            smtp.sendmail(address, [address], message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        pytest.fail(
            f"SMTP send failed to {base_urls.grommunio_smtp_host}:"
            f"{base_urls.grommunio_smtp_port} - {type(exc).__name__}: {exc}. "
            "Check that Grommunio is started and reachable."
        )

    # --- IMAP receipt (polling, delivery is not guaranteed to be synchronous) ---
    found = _poll_for_subject_in_inbox(
        host=base_urls.grommunio_imap_host,
        port=base_urls.grommunio_imap_port,
        address=address,
        password=password,
        subject=subject,
        timeout=60,
    )

    assert found, (
        f"The mail with subject {subject!r} sent to {address} was not found "
        "in the IMAP inbox within the allotted time."
    )


def _poll_for_subject_in_inbox(
    host: str, port: int, address: str, password: str, subject: str, timeout: float
) -> bool:
    deadline = time.monotonic() + timeout
    last_error = None

    while time.monotonic() < deadline:
        try:
            with imaplib.IMAP4_SSL(host, port, timeout=15) as imap:
                imap.login(address, password)
                imap.select("INBOX")
                status, data = imap.search(None, "SUBJECT", f'"{subject}"')
                if status == "OK" and data and data[0]:
                    return True
        except (imaplib.IMAP4.error, OSError) as exc:
            last_error = exc

        time.sleep(3)

    if last_error is not None:
        pytest.fail(
            f"IMAP connection to {host}:{port} failed while polling: "
            f"{type(last_error).__name__}: {last_error}"
        )
    return False
