export interface MeetingMetadata {
  title: string;
  date: string | null;
  participants: string[];
}

/** Sous-ensemble du format d'evenement S3 `ObjectCreated` publie par MinIO (webhook). */
export interface MinioObjectCreatedEvent {
  EventName?: string;
  Records?: Array<{
    eventName?: string;
    s3?: {
      bucket?: { name?: string };
      object?: { key?: string; size?: number; eTag?: string };
    };
  }>;
}

export interface IngestCandidate {
  bucket: string;
  key: string;
  size: number;
  lastModified: string;
}

export interface IngestResult {
  key: string;
  uploaded: boolean;
  peertubeVideoId?: string;
  error?: string;
}
