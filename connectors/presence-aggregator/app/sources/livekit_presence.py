"""Determines whether the user is currently a participant in an active LiveKit room
(study 2.8 line 499: "Video (LiveKit) only has a notion of presence during an
active call -- list of participants connected to a room").

Port of `src/sources/livekit-presence.ts`.

Library choice: the original TypeScript used `livekit-server-sdk`
(`RoomServiceClient.listRooms`/`listParticipants`). Its Python equivalent,
the official `livekit-api` package (PyPI: `livekit-api`, import path
`livekit.api`), is used here rather than a hand-rolled HTTP client: it is
maintained by LiveKit, is natively async (aiohttp-based, matching this
service's async stack), and exposes the exact same
`RoomService.list_rooms`/`list_participants` calls the JS SDK does -- so the
"minimal HTTP client" fallback mentioned in the migration brief was not
needed.
"""

from __future__ import annotations

import os
from typing import Awaitable, Callable, List, Optional, TypedDict

from livekit import api as livekit_api

from app.types import LiveKitPresence

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "https://visio.example.org")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")


class RoomParticipants(TypedDict):
    room_name: str
    participants: List[str]


async def get_livekit_presence(
    user_identity: str,
    list_rooms_and_participants: Optional[
        Callable[[], Awaitable[List[RoomParticipants]]]
    ] = None,
) -> Optional[LiveKitPresence]:
    lister = list_rooms_and_participants or _default_lister
    try:
        rooms_with_participants = await lister()
        in_call = any(
            user_identity in r["participants"] for r in rooms_with_participants
        )
        return LiveKitPresence(in_call=in_call)
    except Exception:
        return None


async def _default_lister() -> List[RoomParticipants]:
    async with livekit_api.LiveKitAPI(
        LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    ) as client:
        rooms_response = await client.room.list_rooms(livekit_api.ListRoomsRequest())
        results: List[RoomParticipants] = []
        for room in rooms_response.rooms:
            participants_response = await client.room.list_participants(
                livekit_api.ListParticipantsRequest(room=room.name)
            )
            results.append(
                {
                    "room_name": room.name,
                    "participants": [
                        p.identity for p in participants_response.participants
                    ],
                }
            )
        return results
