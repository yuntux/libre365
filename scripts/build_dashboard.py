#!/usr/bin/env python3
"""
Study 5.6 (lines 800-802): "A single dashboard consolidating: open
vulnerabilities per component, current versions vs. available versions per
component, results of the latest acceptance runs, health status (technical
monitoring) of each component in production."

Generates a static HTML page (published to GitHub Pages by
.github/workflows/dashboard.yml) from four data sources, gathered
independently so a single source being unreachable degrades that one
section instead of failing the whole page:

  1. Open vulnerabilities  -> GitHub Code Scanning alerts (Trivy findings
     uploaded by cve-scan.yml) + open issues labeled "security" (feed
     entries from security_feeds.py, study 5.2).
  2. Current vs. available versions -> platform.yaml (single source of
     truth, see its header) vs. each component's latest GitHub release.
  3. Latest acceptance ("recette") run -> the most recent run of
     ephemeral-staging.yml (study 5.4/5.5).
  4. Health status of each component in production -> **not available**:
     this repository is an infrastructure-as-code case study, not an
     operating production tenant (no live cluster is reachable from CI or
     from this dashboard) - reported as such rather than fabricated. A
     real deployment would feed this section from its own
     Prometheus/Grafana (see docs/ci-cd.md).

Usage:
    python3 scripts/build_dashboard.py --output-dir dashboard-site
        # requires GITHUB_TOKEN + GITHUB_REPOSITORY for the GitHub-API-backed
        # sections; falls back to "data unavailable" per section otherwise.
"""

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "libre365-dashboard/1.0 (+https://github.com/yuntux/libre365)"
REQUEST_TIMEOUT_SECONDS = 15
ATOM_NS = "{http://www.w3.org/2005/Atom}"

# Component key (platform.yaml `services.*`) -> official GitHub releases
# Atom feed, reused for the "latest available version" column. Kept
# separate from scripts/security_feeds.py's own FEEDS list (that one is
# scoped to the study's named 7 security-feed components, this one covers
# every versioned component in platform.yaml) even though several URLs
# overlap.
RELEASE_FEEDS = {
    "keycloak": "https://github.com/keycloak/keycloak/releases.atom",
    "synapse": "https://github.com/element-hq/synapse/releases.atom",
    "element_web": "https://github.com/element-hq/element-web/releases.atom",
    "element_call": "https://github.com/element-hq/element-call/releases.atom",
    "seafile": "https://github.com/haiwen/seafile/releases.atom",
    "onlyoffice": "https://github.com/ONLYOFFICE/DocumentServer/releases.atom",
    "vikunja": "https://github.com/go-vikunja/vikunja/releases.atom",
    "gokapi": "https://github.com/Forceu/Gokapi/releases.atom",
    "seaweedfs": "https://github.com/seaweedfs/seaweedfs/releases.atom",
    "peertube": "https://github.com/Chocobozzz/PeerTube/releases.atom",
    "caddy": "https://github.com/caddyserver/caddy/releases.atom",
}

ACCEPTANCE_WORKFLOW_FILE = "ephemeral-staging.yml"


@dataclass
class ComponentVersion:
    component: str
    current: str | None
    latest: str | None
    status: str  # "up to date" | "check needed" | "unknown"


@dataclass
class DashboardData:
    generated_at: str
    versions: list[ComponentVersion] = field(default_factory=list)
    code_scanning_alerts: list[dict] | None = None  # None = unavailable
    security_feed_issues: list[dict] | None = None
    latest_acceptance_run: dict | None = None
    errors: list[str] = field(default_factory=list)


def _normalize_version(raw: str) -> str:
    return raw.lower().lstrip("v")


def fetch_latest_release_title(url: str) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml, application/xml"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        root = ElementTree.fromstring(response.read())
    entry = root.find(f"{ATOM_NS}entry")
    if entry is None:
        return None
    title = entry.find(f"{ATOM_NS}title")
    return (title.text or "").strip() if title is not None else None


def load_platform_versions(platform_yaml: Path) -> dict[str, str]:
    platform = yaml.safe_load(platform_yaml.read_text(encoding="utf-8"))
    return {
        key: value["version"]
        for key, value in platform.get("services", {}).items()
        if isinstance(value, dict) and value.get("version")
    }


def collect_versions(platform_yaml: Path, errors: list[str]) -> list[ComponentVersion]:
    current_versions = load_platform_versions(platform_yaml)
    results = []

    for component, current in sorted(current_versions.items()):
        feed_url = RELEASE_FEEDS.get(component)
        latest = None
        if feed_url:
            try:
                latest = fetch_latest_release_title(feed_url)
            except (OSError, ElementTree.ParseError) as exc:
                errors.append(f"could not fetch the latest release for {component}: {exc}")

        if latest is None:
            status = "unknown"
        elif _normalize_version(current) == _normalize_version(latest):
            status = "up to date"
        else:
            status = "check needed"

        results.append(ComponentVersion(component=component, current=current, latest=latest, status=status))

    return results


def github_api_get(path: str, token: str, repo: str, params: str = "") -> object:
    url = f"https://api.github.com/repos/{repo}{path}{params}"
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


def collect_code_scanning_alerts(token: str, repo: str, errors: list[str]) -> list[dict] | None:
    try:
        return github_api_get("/code-scanning/alerts", token, repo, "?state=open&per_page=100")
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        errors.append(f"could not fetch Code Scanning alerts: {exc}")
        return None


def collect_security_feed_issues(token: str, repo: str, errors: list[str]) -> list[dict] | None:
    try:
        return github_api_get("/issues", token, repo, "?state=open&labels=security&per_page=100")
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        errors.append(f"could not fetch open security issues: {exc}")
        return None


def collect_latest_acceptance_run(token: str, repo: str, errors: list[str]) -> dict | None:
    try:
        result = github_api_get(f"/actions/workflows/{ACCEPTANCE_WORKFLOW_FILE}/runs", token, repo, "?per_page=1")
        runs = result.get("workflow_runs", [])
        return runs[0] if runs else None
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        errors.append(f"could not fetch the latest acceptance ({ACCEPTANCE_WORKFLOW_FILE}) run: {exc}")
        return None


def gather_dashboard_data(platform_yaml: Path, token: str | None, repo: str | None) -> DashboardData:
    errors: list[str] = []
    data = DashboardData(generated_at=datetime.now(timezone.utc).isoformat(), errors=errors)
    data.versions = collect_versions(platform_yaml, errors)

    if token and repo:
        data.code_scanning_alerts = collect_code_scanning_alerts(token, repo, errors)
        data.security_feed_issues = collect_security_feed_issues(token, repo, errors)
        data.latest_acceptance_run = collect_latest_acceptance_run(token, repo, errors)
    else:
        errors.append("GITHUB_TOKEN/GITHUB_REPOSITORY not set: Code Scanning alerts, security-feed issues and the "
                       "latest acceptance run could not be fetched (version comparison above still ran).")

    return data


def _status_badge(status: str) -> str:
    colors = {"up to date": "#1a7f37", "check needed": "#9a6700", "unknown": "#57606a"}
    color = colors.get(status, "#57606a")
    return f'<span class="badge" style="background:{color}">{html.escape(status)}</span>'


def render_html(data: DashboardData) -> str:
    versions_rows = "\n".join(
        f"<tr><td>{html.escape(v.component)}</td><td>{html.escape(v.current or '?')}</td>"
        f"<td>{html.escape(v.latest or 'unknown')}</td><td>{_status_badge(v.status)}</td></tr>"
        for v in data.versions
    ) or "<tr><td colspan='4'>No component found in platform.yaml.</td></tr>"

    if data.code_scanning_alerts is None:
        alerts_html = "<p class='unavailable'>Data unavailable this run (see errors below).</p>"
    elif not data.code_scanning_alerts:
        alerts_html = "<p>No open Code Scanning (Trivy) alert.</p>"
    else:
        by_severity: dict[str, int] = {}
        for alert in data.code_scanning_alerts:
            severity = (alert.get("rule", {}) or {}).get("security_severity_level") or "unknown"
            by_severity[severity] = by_severity.get(severity, 0) + 1
        rows = "\n".join(f"<tr><td>{html.escape(sev)}</td><td>{count}</td></tr>" for sev, count in sorted(by_severity.items()))
        alerts_html = (
            f"<p>{len(data.code_scanning_alerts)} open alert(s) "
            f"(<a href='../security/code-scanning'>Security tab</a>):</p>"
            f"<table><tr><th>Severity</th><th>Count</th></tr>{rows}</table>"
        )

    if data.security_feed_issues is None:
        feed_html = "<p class='unavailable'>Data unavailable this run (see errors below).</p>"
    elif not data.security_feed_issues:
        feed_html = "<p>No open security-feed issue.</p>"
    else:
        items = "\n".join(
            f"<li><a href='{html.escape(issue['html_url'])}'>{html.escape(issue['title'])}</a></li>"
            for issue in data.security_feed_issues
        )
        feed_html = f"<ul>{items}</ul>"

    if data.latest_acceptance_run is None:
        acceptance_html = "<p class='unavailable'>Data unavailable this run (see errors below).</p>"
    else:
        run = data.latest_acceptance_run
        conclusion = run.get("conclusion") or run.get("status") or "unknown"
        acceptance_html = (
            f"<p>Latest run: <a href='{html.escape(run.get('html_url', '#'))}'>#{run.get('run_number', '?')}</a> "
            f"— conclusion: <strong>{html.escape(str(conclusion))}</strong> "
            f"({html.escape(run.get('created_at', 'unknown date'))})</p>"
        )

    errors_html = ""
    if data.errors:
        items = "\n".join(f"<li>{html.escape(err)}</li>" for err in data.errors)
        errors_html = f"<section><h2>Notes</h2><ul class='notes'>{items}</ul></section>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>libre365 — consolidated dashboard</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 900px; color: #1f2328; }}
  h1 {{ font-size: 1.5rem; }}
  h2 {{ font-size: 1.15rem; margin-top: 2rem; border-bottom: 1px solid #d0d7de; padding-bottom: .25rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: .5rem; }}
  th, td {{ border: 1px solid #d0d7de; padding: .4rem .6rem; text-align: left; font-size: .9rem; }}
  .badge {{ color: white; padding: .1rem .5rem; border-radius: .75rem; font-size: .8rem; }}
  .unavailable {{ color: #9a6700; font-style: italic; }}
  .notes {{ color: #57606a; font-size: .85rem; }}
  footer {{ margin-top: 3rem; color: #57606a; font-size: .8rem; }}
</style>
</head>
<body>
<h1>libre365 — consolidated dashboard</h1>
<p>Study 5.6: open vulnerabilities, versions, latest acceptance run, production health — in one place.
Generated {html.escape(data.generated_at)}.</p>

<h2>Versions (platform.yaml vs. latest upstream release)</h2>
<table>
<tr><th>Component</th><th>Current</th><th>Latest known</th><th>Status</th></tr>
{versions_rows}
</table>

<h2>Open vulnerabilities — Trivy (Code Scanning)</h2>
{alerts_html}

<h2>Open vulnerabilities — vendor security feeds</h2>
{feed_html}

<h2>Latest acceptance ("recette") run</h2>
{acceptance_html}

<h2>Production health status</h2>
<p class="unavailable">Not available: this repository is an infrastructure-as-code case study,
not an operating production tenant — no live cluster is reachable from this dashboard.
A real deployment would feed this section from its own monitoring stack
(see <code>docs/ci-cd.md</code>).</p>

{errors_html}

<footer>Generated by <code>scripts/build_dashboard.py</code>
(<code>.github/workflows/dashboard.yml</code>) — study 5.6.</footer>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--platform-yaml", default=str(REPO_ROOT / "platform.yaml"))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")

    data = gather_dashboard_data(Path(args.platform_yaml), token, repo)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(render_html(data), encoding="utf-8")

    for error in data.errors:
        print(f"::warning::build_dashboard: {error}", file=sys.stderr)

    print(f"Dashboard written to {output_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
