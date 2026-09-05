from app.normalize import (
    normalize_grommunio_event,
    normalize_matrix_event,
    normalize_onlyoffice_mention_event,
    normalize_seafile_event,
    normalize_vikunja_event,
)


class TestNormalizeMatrixEvent:
    def test_normalizes_a_message_with_a_mention(self):
        result = normalize_matrix_event(
            {
                "type": "m.room.message",
                "room_id": "!abc:matrix.example.org",
                "event_id": "$xyz",
                "sender": "@alice:matrix.example.org",
                "content": {
                    "body": "@bob hi!",
                    "m.mentions": {"user_ids": ["@bob:matrix.example.org"]},
                },
            }
        )
        assert result is not None
        assert result["userId"] == "@bob:matrix.example.org"
        assert result["eventType"] == "mention"
        assert "!abc:matrix.example.org" in result["actionUrl"]

    def test_ignores_non_message_events(self):
        assert normalize_matrix_event({"type": "m.room.member"}) is None

    def test_ignores_a_message_with_no_target_user(self):
        assert (
            normalize_matrix_event({"type": "m.room.message", "content": {"body": "hello"}})
            is None
        )


class TestNormalizeGrommunioEvent:
    def test_normalizes_a_new_mail(self):
        result = normalize_grommunio_event(
            {
                "mailboxUser": "alice@example.org",
                "subject": "Meeting tomorrow",
                "from": "bob@example.org",
                "preview": "Hello, ...",
            }
        )
        assert result["userId"] == "alice@example.org"
        assert "Meeting tomorrow" in result["title"]

    def test_returns_none_without_mailbox_user(self):
        assert normalize_grommunio_event({"subject": "x"}) is None


class TestNormalizeSeafileEvent:
    def test_normalizes_a_file_share(self):
        result = normalize_seafile_event(
            {
                "event_type": "repo-share",
                "repo_id": "abc123",
                "path": "/folder/report.docx",
                "to_user": "alice@example.org",
                "from_user": "bob@example.org",
            }
        )
        assert result["userId"] == "alice@example.org"
        assert "report.docx" in result["title"]


class TestNormalizeVikunjaEvent:
    def test_normalizes_a_task_assignment(self):
        result = normalize_vikunja_event(
            {
                "event_name": "task.assignee.created",
                "data": {
                    "task": {"id": 42, "title": "Prepare the kickoff"},
                    "doer": {"username": "bob"},
                },
                "assignee": {"username": "alice"},
            }
        )
        assert result["userId"] == "alice"
        assert "42" in result["actionUrl"]

    def test_returns_none_without_an_assignee(self):
        assert normalize_vikunja_event({"event_name": "task.created"}) is None


class TestNormalizeOnlyOfficeMentionEvent:
    def test_generates_one_event_per_mentioned_user(self):
        results = normalize_onlyoffice_mention_event(
            {
                "actionLink": "https://office.example.org/doc/1#comment-5",
                "comment": "@alice can you review this?",
                "document": {"title": "Annual report.docx"},
                "emails": ["alice@example.org", "carol@example.org"],
            }
        )
        assert len(results) == 2
        assert results[0]["userId"] == "alice@example.org"
        assert results[0]["actionUrl"] == "https://office.example.org/doc/1#comment-5"

    def test_returns_empty_list_without_a_mentioned_email(self):
        assert normalize_onlyoffice_mention_event({"comment": "hello"}) == []
