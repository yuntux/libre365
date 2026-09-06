"""Batch script, run via cron (study 2.12 line 589: "this upload can be done as a
periodic task -- daily batch -- simpler to operate, with no risk even if the
connector has a temporary outage"). Lists objects uploaded since the last run and
uploads them to PeerTube.

Usage: `python -m app.batch [--since=2026-09-04T00:00:00Z]`
Without `--since`, falls back to "the last 25 hours" (1h margin to cover a
scheduling drift of the daily cron without a coverage gap).
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Sequence

import httpx

from .ingest import IngestDeps, filter_video_objects, ingest_all
from .s3_client import get_object_stream, get_object_tags, list_recent_objects
from .peertube_client import upload_to_peertube


def resolve_since(argv: Sequence[str]) -> str:
    for arg in argv:
        if arg.startswith("--since="):
            return arg[len("--since=") :]
    return (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()


async def main(argv: Sequence[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    since = resolve_since(argv)
    print(f"[peertube-ingest batch] scanning objects modified since {since}")

    objects = await list_recent_objects(since)
    candidates = filter_video_objects(objects)
    print(f"[peertube-ingest batch] {len(candidates)} candidate(s) to ingest")

    async with httpx.AsyncClient() as http_client:

        async def _upload(**kwargs: Any) -> Dict[str, str]:
            return await upload_to_peertube(http_client=http_client, **kwargs)

        deps = IngestDeps(
            get_object_tags=get_object_tags,
            get_object_stream=get_object_stream,
            upload_to_peertube=_upload,
        )
        results = await ingest_all(candidates, deps)

    failed = [r for r in results if not r.uploaded]
    print(
        f"[peertube-ingest batch] done: {len(results) - len(failed)} uploaded, "
        f"{len(failed)} failed"
    )
    if failed:
        print(json.dumps([asdict(r) for r in failed], indent=2), file=sys.stderr)
        return 1
    return 0


def run() -> None:
    try:
        exit_code = asyncio.run(main())
    except Exception as err:  # noqa: BLE001 - mirrors the TS top-level catch
        print(f"[peertube-ingest batch] fatal error: {err}", file=sys.stderr)
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    run()
