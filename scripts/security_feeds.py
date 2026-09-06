#!/usr/bin/env python3
"""
Study 5.2 (lines 775-779): "Subscribing to each component's official
security feeds [...] to be alerted independently of the automated scan
cycle" (the scan cycle itself is `.github/workflows/cve-scan.yml`, see its
header comment for why the two are split).

Polls each component's official Atom/RSS feed and opens one GitHub Issue
per new entry (deduplicated across runs via a stable marker embedded in the
issue body, since GitHub Actions runners keep no state between runs).

Usage:
    python3 scripts/security_feeds.py --dry-run
        # fetch + parse every feed, print what would be created, touch
        # nothing on GitHub. Works with no token, safe to run locally.

    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \\
        python3 scripts/security_feeds.py
        # fetch + parse every feed and create an issue for each new entry
        # not already reported (used by
        # .github/workflows/security-feeds.yml).

A single feed being unreachable (renamed repo, transient network issue)
must never fail the whole run: each feed is fetched independently, a
failure is reported as a warning and the others still get processed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

# Study 5.2, line 778, names 7 components explicitly: "Grommunio,
# Synapse/Element, Seafile, OnlyOffice, Vikunja, Keycloak, Caddy" (Element
# split into its own entry below since it's a separate upstream project/
# release cadence from Synapse). Each URL is the project's official GitHub
# releases Atom feed (`.../releases.atom`) — GitHub serves this for every
# public repository with no authentication, and each project's release
# notes are where they announce security fixes in practice; this is the
# closest thing to a universally-available "official feed" per component
# without depending on a mailing-list subscription (out of scope for a
# GitHub Action) or GitHub Security Advisories (no Atom/RSS export for a
# single repo's advisory list at the time this was written). A maintainer
# with a dedicated security mailing-list subscription for a given
# component can freely replace its URL below with that list's own feed.
FEEDS = [
    {"component": "Grommunio", "url": "https://github.com/grommunio/grommunio-docs/releases.atom"},
    {"component": "Synapse", "url": "https://github.com/element-hq/synapse/releases.atom"},
    {"component": "Element", "url": "https://github.com/element-hq/element-web/releases.atom"},
    {"component": "Seafile", "url": "https://github.com/haiwen/seafile/releases.atom"},
    {"component": "OnlyOffice", "url": "https://github.com/ONLYOFFICE/DocumentServer/releases.atom"},
    {"component": "Vikunja", "url": "https://github.com/go-vikunja/vikunja/releases.atom"},
    {"component": "Keycloak", "url": "https://github.com/keycloak/keycloak/releases.atom"},
    {"component": "Caddy", "url": "https://github.com/caddyserver/caddy/releases.atom"},
]

USER_AGENT = "libre365-security-feeds/1.0 (+https://github.com/yuntux/libre365)"
REQUEST_TIMEOUT_SECONDS = 15
MARKER_PREFIX = "security-feed-id"

ATOM_NS = "{http://www.w3.org/2005/Atom}"


@dataclass
class FeedEntry:
    component: str
    entry_id: str
    title: str
    link: str
    published: datetime | None

    @property
    def marker(self) -> str:
        digest = hashlib.sha1(self.entry_id.encode("utf-8")).hexdigest()[:16]
        return f"{MARKER_PREFIX}:{self.component}:{digest}"


def fetch_feed(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml, application/rss+xml, application/xml"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def _text(element: ElementTree.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        # Atom: RFC 3339 ("2024-01-01T12:00:00Z" or with an offset).
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        # RSS 2.0: RFC 2822 ("Mon, 01 Jan 2024 12:00:00 GMT").
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


def parse_feed(component: str, xml_bytes: bytes) -> list[FeedEntry]:
    root = ElementTree.fromstring(xml_bytes)
    entries: list[FeedEntry] = []

    if root.tag == f"{ATOM_NS}feed":
        for entry in root.findall(f"{ATOM_NS}entry"):
            entry_id = _text(entry.find(f"{ATOM_NS}id"))
            title = _text(entry.find(f"{ATOM_NS}title"))
            link_el = entry.find(f"{ATOM_NS}link")
            link = link_el.get("href", "") if link_el is not None else ""
            published = _parse_date(_text(entry.find(f"{ATOM_NS}published")) or _text(entry.find(f"{ATOM_NS}updated")))
            if entry_id and title:
                entries.append(FeedEntry(component, entry_id, title, link, published))
    else:
        # RSS 2.0: <rss><channel><item>...
        for item in root.findall("./channel/item"):
            guid = _text(item.find("guid"))
            link = _text(item.find("link"))
            entry_id = guid or link
            title = _text(item.find("title"))
            published = _parse_date(_text(item.find("pubDate")))
            if entry_id and title:
                entries.append(FeedEntry(component, entry_id, title, link or entry_id, published))

    return entries


def collect_entries(since_days: int, max_per_feed: int) -> list[FeedEntry]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    collected: list[FeedEntry] = []

    for feed in FEEDS:
        component, url = feed["component"], feed["url"]
        try:
            xml_bytes = fetch_feed(url)
            entries = parse_feed(component, xml_bytes)
        except (OSError, ElementTree.ParseError) as exc:
            print(f"::warning::security_feeds: could not fetch/parse {component}'s feed ({url}): {exc}", file=sys.stderr)
            continue

        # Entries with no parseable publication date are kept (better a
        # false positive worth a human's 5 seconds than a silently missed
        # advisory); recent-first once dated.
        entries.sort(key=lambda e: e.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        recent = [e for e in entries if e.published is None or e.published >= cutoff]
        collected.extend(recent[:max_per_feed])

    return collected


def github_api_request(method: str, path: str, token: str, repo: str, body: dict | None = None) -> dict:
    url = f"https://api.github.com/repos/{repo}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read() or b"{}")


def issue_already_exists(entry: FeedEntry, token: str, repo: str) -> bool:
    query = f'repo:{repo} is:issue "{entry.marker}" in:body'
    request = urllib.request.Request(
        f"https://api.github.com/search/issues?q={urllib.parse.quote(query)}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        result = json.loads(response.read())
    return result.get("total_count", 0) > 0


def create_issue(entry: FeedEntry, token: str, repo: str) -> None:
    published = entry.published.strftime("%Y-%m-%d") if entry.published else "unknown date"
    body = (
        f"New entry published on **{entry.component}**'s official feed "
        f"(study 5.2 - security-feed monitoring, independent of the "
        f"scheduled Trivy scan in `.github/workflows/cve-scan.yml`).\n\n"
        f"**{entry.title}**\n"
        f"{entry.link}\n\n"
        f"Published: {published}\n\n"
        f"Please assess whether this affects the version pinned in "
        f"`platform.yaml` and, if so, open a version-bump PR (Renovate may "
        f"already have one) and run the ephemeral staging cycle before "
        f"promoting it.\n\n"
        f"<!-- {entry.marker} -->"
    )
    github_api_request("POST", "/issues", token, repo, body={
        "title": f"[security-feed] {entry.component}: {entry.title}",
        "body": body,
        "labels": ["security"],
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since-days", type=int, default=30, help="Only consider entries published within this many days (default: 30).")
    parser.add_argument("--max-per-feed", type=int, default=5, help="Cap the number of entries processed per feed per run (default: 5).")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print what would be created, without touching GitHub.")
    parser.add_argument("--output", help="Also write the collected entries as JSON to this file.")
    args = parser.parse_args()

    entries = collect_entries(args.since_days, args.max_per_feed)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump([
                {"component": e.component, "id": e.entry_id, "title": e.title, "link": e.link,
                 "published": e.published.isoformat() if e.published else None, "marker": e.marker}
                for e in entries
            ], handle, indent=2)

    if not entries:
        print("No feed entry found in the lookback window.")
        return 0

    if args.dry_run:
        for entry in entries:
            print(f"[dry-run] would check/create an issue for {entry.component}: {entry.title!r} ({entry.marker})")
        return 0

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("GITHUB_TOKEN and GITHUB_REPOSITORY must be set to create issues (or pass --dry-run).", file=sys.stderr)
        return 1

    created = 0
    for entry in entries:
        try:
            if issue_already_exists(entry, token, repo):
                continue
            create_issue(entry, token, repo)
            created += 1
            print(f"Created issue for {entry.component}: {entry.title!r}")
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"::warning::security_feeds: could not check/create the issue for {entry.component} ({entry.title!r}): {exc}", file=sys.stderr)

    print(f"Done: {created} new issue(s) created out of {len(entries)} entrie(s) considered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
