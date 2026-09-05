from app.metadata import extract_meeting_metadata_from_key, merge_with_s3_tags


class TestExtractMeetingMetadataFromKey:
    def test_extracts_title_date_participants_from_conventional_name(self):
        result = extract_meeting_metadata_from_key(
            "recordings/2026-09-05_kickoff-projet-libre365_alice-bob-carol.mp4"
        )
        assert result.date == "2026-09-05"
        assert result.title == "Kickoff Projet Libre365"
        assert result.participants == ["Alice", "Bob", "Carol"]

    def test_degrades_gracefully_for_non_conventional_name(self):
        result = extract_meeting_metadata_from_key("recording-42.mp4")
        assert result.date is None
        assert result.participants == []
        assert "recording" in result.title


class TestMergeWithS3Tags:
    def test_s3_tags_take_priority_over_the_file_name(self):
        base = extract_meeting_metadata_from_key("recording-42.mp4")
        merged = merge_with_s3_tags(
            base,
            {
                "meeting-title": "Steering committee",
                "meeting-date": "2026-09-01",
                "meeting-participants": "Alice, Bob",
            },
        )
        assert merged.title == "Steering committee"
        assert merged.date == "2026-09-01"
        assert merged.participants == ["Alice", "Bob"]

    def test_falls_back_to_the_file_name_if_no_tag_is_present(self):
        base = extract_meeting_metadata_from_key("2026-09-05_retro-sprint_alice-bob.mp4")
        merged = merge_with_s3_tags(base, {})
        assert merged == base
