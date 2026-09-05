"""Shared types for the presence-aggregator (study 2.8).

Port of `src/types.ts`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

ConsolidatedStatus = Literal["in-meeting", "online", "unavailable", "offline"]

MatrixPresence = Optional[Literal["online", "unavailable", "offline"]]


@dataclass
class GrommunioAvailability:
    """Derived from GetUserAvailability (EWS): true if a calendar event is currently
    in progress."""

    in_meeting_now: bool

    def to_dict(self) -> dict:
        return {"inMeetingNow": self.in_meeting_now}


@dataclass
class LiveKitPresence:
    """true if the user is currently a participant in at least one active LiveKit
    room."""

    in_call: bool

    def to_dict(self) -> dict:
        return {"inCall": self.in_call}


@dataclass
class PresenceSources:
    matrix: MatrixPresence
    grommunio: Optional[GrommunioAvailability]
    livekit: Optional[LiveKitPresence]

    def to_dict(self) -> dict:
        return {
            "matrix": self.matrix,
            "grommunio": self.grommunio.to_dict() if self.grommunio else None,
            "livekit": self.livekit.to_dict() if self.livekit else None,
        }


@dataclass
class ConsolidatedPresence:
    user_id: str
    status: ConsolidatedStatus
    sources: PresenceSources
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "userId": self.user_id,
            "status": self.status,
            "sources": self.sources.to_dict(),
            "updatedAt": self.updated_at,
        }
