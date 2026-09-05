export type ConsolidatedStatus = "in-meeting" | "online" | "unavailable" | "offline";

export type MatrixPresence = "online" | "unavailable" | "offline" | null;

export interface GrommunioAvailability {
  /** Derive de GetUserAvailability (EWS) : true si un evenement de calendrier est en cours. */
  inMeetingNow: boolean;
}

export interface LiveKitPresence {
  /** true si l'utilisateur est actuellement participant d'au moins une room LiveKit active. */
  inCall: boolean;
}

export interface PresenceSources {
  matrix: MatrixPresence;
  grommunio: GrommunioAvailability | null;
  livekit: LiveKitPresence | null;
}

export interface ConsolidatedPresence {
  userId: string;
  status: ConsolidatedStatus;
  sources: PresenceSources;
  updatedAt: string;
}
