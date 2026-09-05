"""
Scénario critique (étude 4.5): "envoi/réception mail (Grommunio)".

Utilise imaplib/smtplib de la bibliothèque standard plutôt qu'un client
Grommunio spécifique: Grommunio expose IMAP/SMTP standards, et s'en tenir à
la stdlib limite les dépendances de cette suite pérenne.

Marqué `smoke` car c'est l'un des usages les plus critiques identifiés dans
l'étude (messagerie = premier point de la migration Office 365 -> stack
libre, section 1).
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
    Grommunio est ici authentifié par identifiants IMAP/SMTP natifs (pas via
    Keycloak): le scénario SSO bout-en-bout dédié à Grommunio est couvert
    séparément dans test_sso_e2e.py contre l'endpoint web/API de Grommunio.
    """
    return {
        "address": os.environ.get("TEST_MAIL_ADDRESS", test_user.email),
        "password": os.environ.get("TEST_MAIL_PASSWORD", test_user.password),
    }


def test_send_and_receive_mail(base_urls, mail_credentials):
    """
    Envoie un mail de l'utilisateur de test vers lui-même via SMTP, puis
    vérifie sa réception via IMAP dans un délai raisonnable (livraison locale
    généralement quasi instantanée sur la stack Grommunio).
    """
    address = mail_credentials["address"]
    password = mail_credentials["password"]
    subject = _unique_subject()
    body = "Message envoyé par la suite de tests d'intégration (test_mail_grommunio.py)."

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = address
    message["To"] = address

    # --- Envoi SMTP ---
    try:
        with smtplib.SMTP(
            base_urls.grommunio_smtp_host, base_urls.grommunio_smtp_port, timeout=15
        ) as smtp:
            smtp.starttls()
            smtp.login(address, password)
            smtp.sendmail(address, [address], message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        pytest.fail(
            f"Échec de l'envoi SMTP vers {base_urls.grommunio_smtp_host}:"
            f"{base_urls.grommunio_smtp_port} - {type(exc).__name__}: {exc}. "
            "Vérifier que Grommunio est démarré et accessible."
        )

    # --- Réception IMAP (polling, la livraison n'est pas garantie synchrone) ---
    found = _poll_for_subject_in_inbox(
        host=base_urls.grommunio_imap_host,
        port=base_urls.grommunio_imap_port,
        address=address,
        password=password,
        subject=subject,
        timeout=60,
    )

    assert found, (
        f"Le mail de sujet {subject!r} envoyé à {address} n'a pas été retrouvé "
        "dans la boîte de réception IMAP dans le délai imparti."
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
            f"Connexion IMAP à {host}:{port} en échec pendant le sondage: "
            f"{type(last_error).__name__}: {last_error}"
        )
    return False
