import { LiveKitPresence } from "../types";

// Utilisation differee (require) pour ne pas imposer `livekit-server-sdk` comme
// dependance de build obligatoire si ce module n'est pas encore installe en
// developpement local -- charge au premier appel seulement.
let cachedRoomServiceClient: unknown | null = null;

const LIVEKIT_URL = process.env.LIVEKIT_URL ?? "https://visio.example.org";
const LIVEKIT_API_KEY = process.env.LIVEKIT_API_KEY ?? "";
const LIVEKIT_API_SECRET = process.env.LIVEKIT_API_SECRET ?? "";

/**
 * Determine si l'utilisateur est actuellement participant d'une room LiveKit active
 * (etude 2.8 ligne 499 : "Visio (LiveKit) n'a de notion de presence que pendant un
 * appel actif -- liste des participants connectes a une room").
 *
 * Utilise `livekit-server-sdk` (RoomServiceClient.listRooms / listParticipants), qui
 * necessite l'API key/secret du serveur LiveKit (pas le token de l'utilisateur final).
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
