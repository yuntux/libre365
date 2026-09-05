"""Extracts meeting metadata (title, date, participants) from the MinIO object name
(study 2.12 line 589: "meeting metadata association -- title, date,
participants -- extracted from the object name or S3 tags"). Pure functions,
testable without network access or an S3 SDK.

Expected naming convention, on the LiveKit Egress export side (to be documented/
configured at the Egress rule level):
  <ISO-date>_<title-slug>_<participant1>-<participant2>-....<ext>
e.g.: "2026-09-05_kickoff-projet-libre365_alice-bob-carol.mp4"

If the name does not follow this format, falls back to a title derived from the
raw file name, with no date or participants -- degrades gracefully rather than failing.
"""

from __future__ import annotations

import re
from typing import Dict

from .types import MeetingMetadata

_NAME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_([a-z0-9-]+)_([a-z0-9-]+(?:-[a-z0-9-]+)*)$",
    re.IGNORECASE,
)


def extract_meeting_metadata_from_key(object_key: str) -> MeetingMetadata:
    file_name = object_key.split("/")[-1] if object_key else object_key
    without_ext = re.sub(r"\.[a-zA-Z0-9]+$", "", file_name)

    match = _NAME_RE.match(without_ext)
    if not match:
        title = re.sub(r"[-_]", " ", without_ext).strip() or "Meeting recording"
        return MeetingMetadata(title=title, date=None, participants=[])

    iso_date, title_slug, participants_slug = match.groups()
    return MeetingMetadata(
        title=_slug_to_title(title_slug),
        date=iso_date,
        participants=[_slug_to_title(p) for p in participants_slug.split("-")],
    )


def merge_with_s3_tags(base: MeetingMetadata, tags: Dict[str, str]) -> MeetingMetadata:
    """Additionally applies S3 tags (`meeting-title`, `meeting-participants`) when
    present, taking priority over what is inferred from the file name."""
    participants = (
        [p.strip() for p in tags["meeting-participants"].split(",")]
        if "meeting-participants" in tags
        else base.participants
    )
    return MeetingMetadata(
        title=tags.get("meeting-title", base.title),
        date=tags.get("meeting-date", base.date),
        participants=participants,
    )


def _slug_to_title(slug: str) -> str:
    return " ".join(word[:1].upper() + word[1:] for word in slug.split("-") if word)
