"""
Offline unit tests for scripts/sync_platform.py's check_domain_coverage()
regression: changing `domains.base` used to make `sync_platform.py` fail
immediately with a false "no matching Caddyfile site block" for every
single domain, because the check compared the FULL FQDN (subdomain + the
NEW base already on disk in platform.yaml) against infra/k8s/manifests/
caddy.yaml's site blocks, which still carried the OLD base until later in
the same run. Fixed by matching on the subdomain LABEL only, independent
of whichever base happens to be baked into the file at check time.

Run with: pytest scripts/test_sync_platform.py
"""

from __future__ import annotations

import sync_platform


def _platform(base: str, subdomains: dict[str, str]) -> dict:
    return {"domains": {"base": base, "subdomains": subdomains}}


def _write_caddy_fixture(tmp_path, monkeypatch, caddyfile_body: str, hostname_annotation: str) -> None:
    manifests_dir = tmp_path / "infra" / "k8s" / "manifests"
    manifests_dir.mkdir(parents=True)
    (manifests_dir / "caddy.yaml").write_text(
        f"data:\n  Caddyfile: |\n{caddyfile_body}\n"
        f'    external-dns.alpha.kubernetes.io/hostname: "{hostname_annotation}"\n'
    )
    monkeypatch.setattr(sync_platform, "REPO_ROOT", tmp_path)


def test_coverage_passes_when_every_subdomain_has_a_site_block_and_annotation(tmp_path, monkeypatch):
    _write_caddy_fixture(
        tmp_path, monkeypatch,
        caddyfile_body="    sso.libre365.example.org {\n    }\n",
        hostname_annotation="sso.libre365.example.org",
    )
    platform = _platform("libre365.example.org", {"sso": "sso"})

    assert sync_platform.check_domain_coverage(platform) == []


def test_coverage_flags_a_genuinely_missing_site_block(tmp_path, monkeypatch):
    _write_caddy_fixture(
        tmp_path, monkeypatch,
        caddyfile_body="    sso.libre365.example.org {\n    }\n",
        hostname_annotation="sso.libre365.example.org",
    )
    platform = _platform("libre365.example.org", {"sso": "sso", "chat": "chat"})

    problems = sync_platform.check_domain_coverage(platform)

    assert len(problems) == 1
    assert "chat" in problems[0]
    assert "no matching Caddyfile site block" in problems[0]


def test_coverage_flags_a_site_block_missing_from_the_dns_annotation(tmp_path, monkeypatch):
    _write_caddy_fixture(
        tmp_path, monkeypatch,
        caddyfile_body="    sso.libre365.example.org {\n    }\n    chat.libre365.example.org {\n    }\n",
        hostname_annotation="sso.libre365.example.org",
    )
    platform = _platform("libre365.example.org", {"sso": "sso", "chat": "chat"})

    problems = sync_platform.check_domain_coverage(platform)

    assert len(problems) == 1
    assert "chat" in problems[0]
    assert "external-dns" in problems[0]


def test_coverage_survives_a_base_domain_change_before_the_file_is_repatched(tmp_path, monkeypatch):
    """Regression test for the ordering bug: platform.yaml already has the
    NEW base, but infra/k8s/manifests/caddy.yaml (checked here via a
    fixture standing in for it) still has the OLD one, exactly like the
    real file looks the instant `domains.base` is edited and before
    compute_domain_changes() has run in the same invocation."""
    _write_caddy_fixture(
        tmp_path, monkeypatch,
        caddyfile_body="    sso.libre365.example.org {\n    }\n",  # still the OLD base
        hostname_annotation="sso.libre365.example.org",
    )
    platform = _platform("new-base.example.net", {"sso": "sso"})  # platform.yaml already has the NEW base

    assert sync_platform.check_domain_coverage(platform) == []


def test_coverage_ignores_domains_without_a_caddy_site(tmp_path, monkeypatch):
    _write_caddy_fixture(
        tmp_path, monkeypatch,
        caddyfile_body="    sso.libre365.example.org {\n    }\n",
        hostname_annotation="sso.libre365.example.org",
    )
    platform = _platform("libre365.example.org", {"sso": "sso", "mail": "mail"})

    assert sync_platform.check_domain_coverage(platform) == []
