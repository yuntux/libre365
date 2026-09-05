"""Pure normalization functions, one per source (study 2.1 line 379:
"a connector per service is needed to translate each event").
Deliberately free of side effects / network calls to stay unit-testable.
"""

from __future__ import annotations

import datetime as _dt
from typing import List, Optional
from urllib.parse import quote

from .types import (
    GrommunioWebhookPayload,
    MatrixWebhookPayload,
    NormalizedEvent,
    OnlyOfficeMentionPayload,
    SeafileWebhookPayload,
    VikunjaWebhookPayload,
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_ms_to_iso(ms: float) -> str:
    return (
        _dt.datetime.fromtimestamp(ms / 1000, tz=_dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_matrix_event(payload: Optional[MatrixWebhookPayload]) -> Optional[NormalizedEvent]:
    """Normalizes a Matrix Application Service event (text message or mention)."""
    if not payload or payload.get("type") != "m.room.message":
        return None

    content = payload.get("content") or {}
    mentioned = (content.get("m.mentions") or {}).get("user_ids") or []
    target_user = payload.get("target_user_id") or (mentioned[0] if mentioned else None)
    if not target_user:
        return None

    body = content.get("body") or "(empty message)"
    sender = payload.get("sender") or "a user"
    room_id = payload.get("room_id")
    event_id = payload.get("event_id")

    if room_id:
        action_url = f"https://element.example.org/#/room/{room_id}" + (
            f"/{event_id}" if event_id else ""
        )
    else:
        action_url = "https://element.example.org"

    origin_server_ts = payload.get("origin_server_ts")
    timestamp = _epoch_ms_to_iso(origin_server_ts) if origin_server_ts else _now_iso()

    return NormalizedEvent(
        source="matrix",
        eventType="mention" if len(mentioned) > 0 else "message",
        userId=target_user,
        title=f"New message from {sender}",
        body=body if len(body) <= 280 else f"{body[:277]}...",
        actionUrl=action_url,
        timestamp=timestamp,
    )


def normalize_grommunio_event(
    payload: Optional[GrommunioWebhookPayload],
) -> Optional[NormalizedEvent]:
    """Normalizes a Grommunio event (new mail received)."""
    if not payload or not payload.get("mailboxUser"):
        return None

    subject = payload.get("subject")
    message_id = payload.get("messageId")
    web_url = payload.get("webUrl")

    if web_url:
        action_url = web_url
    elif message_id:
        action_url = f"https://mail.example.org/webapp/index.html#eml={quote(message_id, safe='')}"
    else:
        action_url = "https://mail.example.org"

    return NormalizedEvent(
        source="grommunio",
        eventType=payload.get("event") or "new_mail",
        userId=payload["mailboxUser"],
        title=f"New mail: {subject}" if subject else "New mail",
        body=payload.get("preview") or payload.get("from") or "",
        actionUrl=action_url,
        timestamp=payload.get("receivedAt") or _now_iso(),
    )


def normalize_seafile_event(payload: Optional[SeafileWebhookPayload]) -> Optional[NormalizedEvent]:
    """Normalizes a Seafile event (file/folder share)."""
    if not payload or not payload.get("to_user"):
        return None

    path = payload.get("path")
    file_name = path.rsplit("/", 1)[-1] if path else payload.get("repo_name")

    action_url = payload.get("url") or (
        f"https://seafile.example.org/library/{payload.get('repo_id') or ''}{payload.get('path') or ''}"
    )

    return NormalizedEvent(
        source="seafile",
        eventType=payload.get("event_type") or "file-shared",
        userId=payload["to_user"],
        title=f"File shared: {file_name or 'document'}",
        body=f"Shared by {payload['from_user']}" if payload.get("from_user") else "",
        actionUrl=action_url,
        timestamp=payload.get("timestamp") or _now_iso(),
    )


def normalize_vikunja_event(payload: Optional[VikunjaWebhookPayload]) -> Optional[NormalizedEvent]:
    """Normalizes a Vikunja event (task assigned)."""
    if not payload:
        return None

    assignee = (payload.get("assignee") or {}).get("username")
    if not assignee:
        return None

    data = payload.get("data") or {}
    task = data.get("task") or {}
    doer = data.get("doer") or {}
    task_id = task.get("id")

    return NormalizedEvent(
        source="vikunja",
        eventType=payload.get("event_name") or "task.assigned",
        userId=assignee,
        title=f"Task assigned: {task['title']}" if task.get("title") else "New task assigned",
        body=f"Assigned by {doer['username']}" if doer.get("username") else "",
        actionUrl=f"https://vikunja.example.org/tasks/{task_id}"
        if task_id is not None
        else "https://vikunja.example.org",
        timestamp=payload.get("time") or _now_iso(),
    )


def normalize_onlyoffice_mention_event(
    payload: Optional[OnlyOfficeMentionPayload],
) -> List[NormalizedEvent]:
    """Normalizes an OnlyOffice mention (`onRequestSendNotify`, study 2.7 line 484).

    One normalized event is emitted per mentioned email address (0..n), so this
    function returns a list rather than a single event.
    """
    if not payload or not payload.get("emails"):
        return []

    document_title = (payload.get("document") or {}).get("title") or "a document"
    timestamp = payload.get("timestamp") or _now_iso()
    action_url = payload.get("actionLink") or "https://office.example.org"
    comment = payload.get("comment") or ""

    return [
        NormalizedEvent(
            source="onlyoffice",
            eventType="mention",
            userId=email,
            title=f"You were mentioned in {document_title}",
            body=comment,
            actionUrl=action_url,
            timestamp=timestamp,
        )
        for email in payload["emails"]
    ]
