"""Pure consolidation logic (study 2.8 line 504): priority
"in meeting > online on Matrix > away", with no network dependency, so it
stays unit-testable. Used both for `GET /presence/{user_id}` and the SSE stream.

Priority rule:
1. LiveKit "inCall" or Grommunio/EWS "inMeetingNow" -> "in-meeting"
   (study 2.8 line 492: avoid showing "available" while the person is in a meeting)
2. Matrix "online" -> "online"
3. Matrix "unavailable" -> "unavailable"
4. Otherwise (no active source, or Matrix "offline"/unknown) -> "offline"

Port of `src/consolidate.ts` -- keep the logic exactly in sync with that file.
"""

from __future__ import annotations

from app.types import ConsolidatedStatus, PresenceSources


def consolidate_presence(sources: PresenceSources) -> ConsolidatedStatus:
    if (sources.livekit is not None and sources.livekit.in_call) or (
        sources.grommunio is not None and sources.grommunio.in_meeting_now
    ):
        return "in-meeting"
    if sources.matrix == "online":
        return "online"
    if sources.matrix == "unavailable":
        return "unavailable"
    return "offline"
