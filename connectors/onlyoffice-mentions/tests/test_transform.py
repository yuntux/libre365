from app.transform import to_notification_hub_payload, to_onlyoffice_user_list


class TestToOnlyOfficeUserList:
    def test_maps_the_keycloak_directory_to_the_onlyoffice_format(self):
        result = to_onlyoffice_user_list(
            [
                {
                    "id": "u1",
                    "username": "alice",
                    "email": "alice@example.org",
                    "firstName": "Alice",
                    "lastName": "Martin",
                },
                {"id": "u2", "username": "bob", "email": "bob@example.org"},
            ]
        )
        assert result == [
            {"id": "u1", "name": "Alice Martin", "email": "alice@example.org"},
            {"id": "u2", "name": "bob", "email": "bob@example.org"},
        ]

    def test_excludes_users_without_an_email(self):
        result = to_onlyoffice_user_list([{"id": "u3", "username": "svc", "email": ""}])
        assert result == []


class TestToNotificationHubPayload:
    def test_builds_the_relay_payload_with_the_mentioned_emails(self):
        result = to_notification_hub_payload(
            {
                "actionLink": "https://office.example.org/doc/42#comment-3",
                "message": "@alice can you approve this?",
                "emails": ["alice@example.org"],
                "document": {"title": "Budget 2027.xlsx"},
                "fileId": "42",
            }
        )
        assert result is not None
        assert result["emails"] == ["alice@example.org"]
        assert "comment-3" in result["actionLink"]
        assert result["document"]["title"] == "Budget 2027.xlsx"

    def test_returns_none_without_a_mentioned_email(self):
        assert to_notification_hub_payload({"message": "hello"}) is None
