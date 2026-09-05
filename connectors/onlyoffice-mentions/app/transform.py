"""
Transforms the directory (Keycloak Admin API) into the format expected by OnlyOffice
for `onRequestUsers` (study 2.7 line 484: "list of users suggested when typing
the +/@ character"). Pure functions, testable without a network call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from app.types import (
    DirectoryUser,
    NotificationHubPayload,
    OnlyOfficeUserEntry,
    OnRequestSendNotifyPayload,
)


def to_onlyoffice_user_list(users: Iterable[DirectoryUser]) -> list[OnlyOfficeUserEntry]:
    result: list[OnlyOfficeUserEntry] = []
    for u in users:
        email = u.get("email")
        if not email:
            continue
        first_name = u.get("firstName")
        last_name = u.get("lastName")
        name = " ".join(part for part in (first_name, last_name) if part) or u.get("username", "")
        result.append({"id": u.get("id", ""), "name": name, "email": email})
    return result


def to_notification_hub_payload(
    payload: Optional[OnRequestSendNotifyPayload],
) -> Optional[NotificationHubPayload]:
    """
    Builds the payload expected by `notification-hub` (`POST /webhooks/onlyoffice-mention`,
    see connectors/notification-hub `OnlyOfficeMentionPayload`) from
    the native OnlyOffice `onRequestSendNotify` event (study 2.7 line 487).
    """
    if not payload or not payload.get("emails"):
        return None

    return {
        "actionLink": payload.get("actionLink"),
        "comment": payload.get("message"),
        "document": payload.get("document"),
        "emails": payload["emails"],
        "fileId": payload.get("fileId"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
