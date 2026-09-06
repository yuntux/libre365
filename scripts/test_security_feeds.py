"""
Offline unit tests for scripts/security_feeds.py's parsing/dedup logic
(study 5.2). Deliberately never touches the network: feed fetching itself
is a thin `urllib` call, not worth mocking; what needs to be correct
without a live GitHub is the Atom/RSS parsing, the recency filter, and the
stability of the dedup marker used to avoid re-creating the same issue on
every run.

Run with: pytest scripts/test_security_feeds.py
"""

from datetime import datetime, timedelta, timezone

from security_feeds import FeedEntry, collect_entries, parse_feed

ATOM_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:github.com,2008:Repository/1/v2.0.0</id>
    <title>v2.0.0</title>
    <link href="https://github.com/example/project/releases/tag/v2.0.0"/>
    <published>2024-06-01T10:00:00Z</published>
  </entry>
  <entry>
    <id>tag:github.com,2008:Repository/1/v1.9.0</id>
    <title>v1.9.0</title>
    <link href="https://github.com/example/project/releases/tag/v1.9.0"/>
    <published>2023-01-01T10:00:00Z</published>
  </entry>
</feed>
"""

RSS_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example security feed</title>
    <item>
      <title>CVE-2024-0001 fixed in 3.1.4</title>
      <link>https://example.org/security/CVE-2024-0001</link>
      <guid>https://example.org/security/CVE-2024-0001</guid>
      <pubDate>Mon, 01 Jul 2024 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_parse_atom_feed_extracts_all_entries():
    entries = parse_feed("Example", ATOM_SAMPLE)

    assert len(entries) == 2
    assert entries[0].title == "v2.0.0"
    assert entries[0].link == "https://github.com/example/project/releases/tag/v2.0.0"
    assert entries[0].published == datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)


def test_parse_rss_feed_extracts_entries():
    entries = parse_feed("Example", RSS_SAMPLE)

    assert len(entries) == 1
    assert entries[0].title == "CVE-2024-0001 fixed in 3.1.4"
    assert entries[0].published == datetime(2024, 7, 1, 8, 0, tzinfo=timezone.utc)


def test_marker_is_stable_and_scoped_per_component():
    entry_a = FeedEntry("Synapse", "same-id", "title", "link", None)
    entry_b = FeedEntry("Keycloak", "same-id", "title", "link", None)

    # Same marker on repeated calls (idempotent across runs)...
    assert entry_a.marker == entry_a.marker
    # ...but distinct between components sharing the same upstream entry id
    # (defensive: nothing guarantees id-namespaces don't collide).
    assert entry_a.marker != entry_b.marker
    assert entry_a.marker.startswith("security-feed-id:Synapse:")


def test_marker_differs_for_different_entry_ids():
    entry_a = FeedEntry("Synapse", "id-1", "title", "link", None)
    entry_b = FeedEntry("Synapse", "id-2", "title", "link", None)

    assert entry_a.marker != entry_b.marker


def test_collect_entries_skips_an_unreachable_feed_without_raising(monkeypatch):
    def fake_fetch(url: str) -> bytes:
        if "keycloak" in url:
            raise OSError("simulated network failure")
        return ATOM_SAMPLE

    monkeypatch.setattr("security_feeds.fetch_feed", fake_fetch)

    entries = collect_entries(since_days=3650, max_per_feed=10)

    # Every other feed still contributed its entries; the one broken feed
    # (Keycloak) is silently absent rather than aborting the whole run.
    assert entries
    assert all(entry.component != "Keycloak" for entry in entries)


def test_collect_entries_filters_out_of_window_entries(monkeypatch):
    monkeypatch.setattr("security_feeds.fetch_feed", lambda url: ATOM_SAMPLE)

    # since_days=30 from "now" excludes the 2023 entry in ATOM_SAMPLE, keeps
    # the 2024 one only if it's still within the window relative to "now" -
    # so instead assert on the always-true invariant: no returned entry is
    # older than the cutoff.
    entries = collect_entries(since_days=30, max_per_feed=10)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    assert all(e.published is None or e.published >= cutoff for e in entries)


def test_collect_entries_respects_max_per_feed(monkeypatch):
    monkeypatch.setattr("security_feeds.fetch_feed", lambda url: ATOM_SAMPLE)

    entries = collect_entries(since_days=3650, max_per_feed=1)

    from security_feeds import FEEDS

    assert len(entries) == len(FEEDS)  # exactly 1 kept per feed
