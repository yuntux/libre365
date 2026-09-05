import { LiveKitPresence } from "../types";

// Deferred use (require) so `livekit-server-sdk` is not an unconditional build
// dependency if this module is not yet installed in local development -- it is
// loaded only on first call.
let cachedRoomServiceClient: unknown | null = null;

const LIVEKIT_URL = process.env.LIVEKIT_URL ?? "https://visio.example.org";
const LIVEKIT_API_KEY = process.env.LIVEKIT_API_KEY ?? "";
const LIVEKIT_API_SECRET = process.env.LIVEKIT_API_SECRET ?? "";

/**
 * Determines whether the user is currently a participant in an active LiveKit room
 * (study 2.8 line 499: "Video (LiveKit) only has a notion of presence during an
 * active call -- list of participants connected to a room").
 *
 * Uses `livekit-server-sdk` (RoomServiceClient.listRooms / listParticipants), which
 * requires the LiveKit server's API key/secret (not the end user's token).
 */
export async function getLiveKitPresence(
  userIdentity: string,
  listRoomsAndParticipants: () => Promise<{ roomName: string; participants: string[] }[]> = defaultLister
): Promise<LiveKitPresence | null> {
  try {
    const roomsWithParticipants = await listRoomsAndParticipants();
    const inCall = roomsWithParticipants.some((r) => r.participants.includes(userIdentity));
    return { inCall };
  } catch {
    return null;
  }
}

async function defaultLister(): Promise<{ roomName: string; participants: string[] }[]> {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { RoomServiceClient } = require("livekit-server-sdk") as typeof import("livekit-server-sdk");

  if (!cachedRoomServiceClient) {
    cachedRoomServiceClient = new RoomServiceClient(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET);
  }
  const client = cachedRoomServiceClient as InstanceType<typeof RoomServiceClient>;

  const rooms = await client.listRooms();
  const results: { roomName: string; participants: string[] }[] = [];
  for (const room of rooms) {
    const participants = await client.listParticipants(room.name);
    results.push({ roomName: room.name, participants: participants.map((p) => p.identity) });
  }
  return results;
}
