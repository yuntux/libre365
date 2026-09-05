from unittest.mock import AsyncMock

import pytest

from app.ingest import IngestDeps, filter_video_objects, ingest_all, ingest_object
from app.types import IngestCandidate

candidate = IngestCandidate(
    bucket="visio-recordings",
    key="2026-09-05_kickoff_alice-bob.mp4",
    size=1234,
    last_modified="2026-09-05T10:00:00Z",
)


class TestIngestObject:
    async def test_uploads_successfully_and_returns_the_peertube_id(self):
        deps = IngestDeps(
            get_object_tags=AsyncMock(return_value={}),
            get_object_stream=AsyncMock(return_value=b"fake-video-bytes"),
            upload_to_peertube=AsyncMock(return_value={"peertube_video_id": "abc-123"}),
        )

        result = await ingest_object(candidate, deps)

        assert result.uploaded is True
        assert result.peertube_video_id == "abc-123"
        _, kwargs = deps.upload_to_peertube.call_args
        assert kwargs["object_key"] == candidate.key
        assert kwargs["metadata"].title == "Kickoff"
        assert kwargs["metadata"].date == "2026-09-05"

    async def test_returns_an_error_without_failing_the_caller(self):
        async def _raise(*_args, **_kwargs):
            raise RuntimeError("network down")

        deps = IngestDeps(
            get_object_tags=AsyncMock(return_value={}),
            get_object_stream=_raise,
            upload_to_peertube=AsyncMock(),
        )

        result = await ingest_object(candidate, deps)

        assert result.uploaded is False
        assert result.error == "network down"
        deps.upload_to_peertube.assert_not_called()


class TestIngestAll:
    async def test_ingests_several_candidates_sequentially(self):
        order = []

        async def _get_object_stream(bucket, key):
            order.append(key)
            return b"x"

        deps = IngestDeps(
            get_object_tags=AsyncMock(return_value={}),
            get_object_stream=_get_object_stream,
            upload_to_peertube=AsyncMock(return_value={"peertube_video_id": "id"}),
        )

        other = IngestCandidate(**{**candidate.__dict__, "key": "2026-09-06_retro_carol.mp4"})
        results = await ingest_all([candidate, other], deps)

        assert len(results) == 2
        assert order == [candidate.key, "2026-09-06_retro_carol.mp4"]


class TestFilterVideoObjects:
    def test_keeps_only_known_video_extensions(self):
        objects = [
            IngestCandidate(**{**candidate.__dict__, "key": "a.mp4"}),
            IngestCandidate(**{**candidate.__dict__, "key": "b.txt"}),
            IngestCandidate(**{**candidate.__dict__, "key": "c.webm"}),
            IngestCandidate(**{**candidate.__dict__, "key": "d.json"}),
        ]
        assert [o.key for o in filter_video_objects(objects)] == ["a.mp4", "c.webm"]
