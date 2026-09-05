"""Common notification format, see study 2.1 line 368:
"A single entry point aggregating notifications from all services".
Each source connector normalizes to this shape before relaying to Novu.

Kept intentionally as plain dicts/TypedDicts (not pydantic models) to mirror
the original TypeScript `types.ts`, which only declared shapes for the raw
webhook payloads and the normalized event - no runtime validation.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional, TypedDict

Source = Literal["matrix", "grommunio", "seafile", "vikunja", "onlyoffice"]


class NormalizedEvent(TypedDict):
    source: Source
    eventType: str
    userId: str
    title: str
    body: str
    actionUrl: str
    timestamp: str


# Raw webhook payloads are treated as loosely-typed dicts (equivalent to the
# TypeScript interfaces, which only documented optional fields with no
# runtime enforcement).
MatrixWebhookPayload = dict
GrommunioWebhookPayload = dict
SeafileWebhookPayload = dict
VikunjaWebhookPayload = dict
OnlyOfficeMentionPayload = dict
