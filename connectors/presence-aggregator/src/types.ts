export type ConsolidatedStatus = "in-meeting" | "online" | "unavailable" | "offline";

export type MatrixPresence = "online" | "unavailable" | "offline" | null;

export interface GrommunioAvailability {
  /** Derived from GetUserAvailability (EWS): true if a calendar event is currently in progress. */
  inMeetingNow: boolean;
}

export interface LiveKitPresence {
  /** true if the user is currently a participant in at least one active LiveKit room. */
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
