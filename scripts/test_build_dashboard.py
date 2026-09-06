"""
Offline unit tests for scripts/build_dashboard.py (study 5.6). Never
touches the network or GitHub API: what's tested here is the pure
rendering logic (render_html on a fixture DashboardData) and the version
comparison helper, since the GitHub-API-backed collectors are thin
`urllib` calls not worth mocking in detail (their per-call try/except is
exercised the same way as scripts/security_feeds.py's, see
test_security_feeds.py).

Run with: pytest scripts/test_build_dashboard.py
"""

from __future__ import annotations

from build_dashboard import ComponentVersion, DashboardData, _normalize_version, render_html


def test_normalize_version_strips_v_prefix_and_case():
    assert _normalize_version("v1.2.3") == "1.2.3"
    assert _normalize_version("1.2.3") == "1.2.3"
    assert _normalize_version("V1.2.3") == "1.2.3"


def test_render_html_reports_unavailable_sections_honestly():
    data = DashboardData(
        generated_at="2024-01-01T00:00:00+00:00",
        versions=[ComponentVersion("keycloak", "26.0.7", None, "unknown")],
        code_scanning_alerts=None,
        security_feed_issues=None,
        latest_acceptance_run=None,
        errors=["could not fetch the latest release for keycloak: simulated"],
    )

    output = render_html(data)

    assert "keycloak" in output
    assert "26.0.7" in output
    # Sections with no data must say so, never render as if empty/clean.
    assert output.count("Data unavailable this run") == 3
    assert "Production health status" in output
    assert "not an operating production tenant" in output
    assert "simulated" in output


def test_render_html_shows_up_to_date_badge_on_matching_versions():
    data = DashboardData(
        generated_at="2024-01-01T00:00:00+00:00",
        versions=[ComponentVersion("caddy", "v2.8.4", "v2.8.4", "up to date")],
        code_scanning_alerts=[],
        security_feed_issues=[],
        latest_acceptance_run={"run_number": 42, "conclusion": "success", "html_url": "https://example.org/run/42", "created_at": "2024-01-01"},
    )

    output = render_html(data)

    assert "up to date" in output
    assert "No open Code Scanning" in output
    assert "No open security-feed issue" in output
    assert "#42" in output
    assert "success" in output


def test_render_html_groups_code_scanning_alerts_by_severity():
    data = DashboardData(
        generated_at="2024-01-01T00:00:00+00:00",
        code_scanning_alerts=[
            {"rule": {"security_severity_level": "critical"}},
            {"rule": {"security_severity_level": "critical"}},
            {"rule": {"security_severity_level": "medium"}},
        ],
        security_feed_issues=[],
        latest_acceptance_run=None,
    )

    output = render_html(data)

    assert "3 open alert" in output
    assert "critical" in output and "2" in output
    assert "medium" in output


def test_render_html_escapes_untrusted_text():
    data = DashboardData(
        generated_at="2024-01-01T00:00:00+00:00",
        security_feed_issues=[{"title": "<script>alert(1)</script>", "html_url": "https://example.org/1"}],
    )

    output = render_html(data)

    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;" in output
