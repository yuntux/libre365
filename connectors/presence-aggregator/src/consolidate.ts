import { ConsolidatedStatus, PresenceSources } from "./types";

/**
 * Logique de consolidation pure (etude 2.8 ligne 504) : priorite
 * "en reunion > en ligne Matrix > absent", sans aucune dependance reseau, pour rester
 * testable unitairement. Sert a la fois pour `GET /presence/:userId` et le flux SSE.
 *
 * Regle de priorite :
 * 1. LiveKit "inCall" ou Grommunio/EWS "inMeetingNow" -> "in-meeting"
 *    (etude 2.8 ligne 492 : eviter d'afficher "disponible" alors que la personne est en reunion)
 * 2. Matrix "online" -> "online"
 * 3. Matrix "unavailable" -> "unavailable"
 * 4. Sinon (aucune source active, ou Matrix "offline"/inconnu) -> "offline"
 */
export function consolidatePresence(sources: PresenceSources): ConsolidatedStatus {
  if (sources.livekit?.inCall || sources.grommunio?.inMeetingNow) {
    return "in-meeting";
  }
  if (sources.matrix === "online") {
    return "online";
  }
  if (sources.matrix === "unavailable") {
    return "unavailable";
  }
  return "offline";
}
