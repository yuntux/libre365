"""Faithful port of `test/consolidate.test.ts`."""

from app.consolidate import consolidate_presence
from app.types import GrommunioAvailability, LiveKitPresence, PresenceSources


def test_prioritizes_in_meeting_even_if_matrix_shows_online():
    status = consolidate_presence(
        PresenceSources(
            matrix="online",
            grommunio=GrommunioAvailability(in_meeting_now=True),
            livekit=None,
        )
    )
    assert status == "in-meeting"


def test_prioritizes_in_meeting_if_user_in_livekit_call():
    status = consolidate_presence(
        PresenceSources(
            matrix="offline",
            grommunio=None,
            livekit=LiveKitPresence(in_call=True),
        )
    )
    assert status == "in-meeting"


def test_falls_back_to_online_when_no_meeting_in_progress():
    status = consolidate_presence(
        PresenceSources(
            matrix="online",
            grommunio=GrommunioAvailability(in_meeting_now=False),
            livekit=LiveKitPresence(in_call=False),
        )
    )
    assert status == "online"


def test_returns_unavailable_when_matrix_unavailable_and_no_meeting():
    status = consolidate_presence(
        PresenceSources(matrix="unavailable", grommunio=None, livekit=None)
    )
    assert status == "unavailable"


def test_returns_offline_by_default_when_no_source_active():
    status = consolidate_presence(
        PresenceSources(matrix=None, grommunio=None, livekit=None)
    )
    assert status == "offline"


def test_returns_offline_when_matrix_explicitly_offline():
    status = consolidate_presence(
        PresenceSources(
            matrix="offline",
            grommunio=GrommunioAvailability(in_meeting_now=False),
            livekit=None,
        )
    )
    assert status == "offline"
