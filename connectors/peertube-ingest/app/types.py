"""Shared data types for the peertube-ingest connector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MeetingMetadata:
    title: str
    date: Optional[str]
    participants: List[str] = field(default_factory=list)


@dataclass
class IngestCandidate:
    bucket: str
    key: str
    size: int
    last_modified: str


@dataclass
class IngestResult:
    key: str
    uploaded: bool
    peertube_video_id: Optional[str] = None
    error: Optional[str] = None
