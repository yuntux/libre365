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


def _onboarding_platform(base: str) -> dict:
    return _platform(base, {"matrix": "matrix", "files": "files", "taches": "taches", "mail": "mail"})


def test_qr_svg_markup_has_no_xml_declaration_and_is_embeddable():
    markup = sync_platform._qr_svg_markup("https://example.org")

    assert markup.startswith("<svg")
    assert markup.endswith("</svg>")
    assert "<?xml" not in markup


def test_onboarding_mobileconfig_carries_no_personal_data():
    """Study 2.5's design (and the reason this page can be unauthenticated,
    per review) depends on the .mobileconfig never containing a username,
    email or password - only the server hostname."""
    import plistlib

    change = sync_platform.compute_onboarding_changes(_onboarding_platform("libre365.example.org"))[0]
    manifest = yaml_load_configmap(change.desired)
    mobileconfig = plistlib.loads(manifest["data"]["grommunio-eas.mobileconfig"].encode())

    payload = mobileconfig["PayloadContent"][0]
    assert payload["EASHost"] == "mail.libre365.example.org"
    assert "EASUsername" not in payload
    assert "EASPassword" not in payload
    assert "EASEmailAddress" not in payload


def test_onboarding_html_reflects_the_current_domain():
    change = sync_platform.compute_onboarding_changes(_onboarding_platform("libre365.example.org"))[0]
    manifest = yaml_load_configmap(change.desired)
    index_html = manifest["data"]["index.html"]

    assert "element://https://matrix.libre365.example.org" in index_html
    assert "https://files.libre365.example.org" in index_html
    assert "https://taches.libre365.example.org" in index_html
    assert "https://mail.libre365.example.org" in index_html
    assert index_html.count("<svg") == 4


def test_onboarding_regenerates_for_a_different_base_domain():
    change = sync_platform.compute_onboarding_changes(_onboarding_platform("new-base.example.net"))[0]
    manifest = yaml_load_configmap(change.desired)

    assert "matrix.new-base.example.net" in manifest["data"]["index.html"]
    assert "libre365.example.org" not in manifest["data"]["index.html"]


def yaml_load_configmap(text: str) -> dict:
    import yaml

    return yaml.safe_load(text)


# --- check_oidc_coverage() -------------------------------------------------
#
# Regression tests for the audit findings fixed on request ("est-ce que la
# connexion OIDC via Keycloak est bien configurée pour toutes les
# applications ?"): Gokapi/Seafile/PeerTube had a client_id with no client
# secret ever wired (dangling secretKeyRef, no ExternalSecret), and Visio
# (LaSuite Meet) had full app-side config referencing a Keycloak client that
# was never created at all. check_oidc_coverage() must catch both shapes of
# gap, and never false-positive on a fully-wired client.


def _write_oidc_fixture(
    tmp_path,
    monkeypatch,
    *,
    defaults_client_ids: list[str],
    app_file_text: str,
    external_secrets_text: str,
) -> None:
    defaults_dir = tmp_path / "infra" / "ansible" / "roles" / "keycloak_realm" / "defaults"
    defaults_dir.mkdir(parents=True)
    clients_yaml = "\n".join(f'  - client_id: "{cid}"\n    name: "{cid}"' for cid in defaults_client_ids)
    (defaults_dir / "main.yml").write_text(f"keycloak_oidc_clients:\n{clients_yaml}\n")

    app_dir = tmp_path / "infra" / "k8s" / "helm-values"
    app_dir.mkdir(parents=True)
    (app_dir / "seafile.yaml").write_text(app_file_text)

    manifests_dir = tmp_path / "infra" / "k8s" / "manifests"
    manifests_dir.mkdir(parents=True)
    (manifests_dir / "external-secrets.yaml").write_text(external_secrets_text)

    monkeypatch.setattr(sync_platform, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sync_platform, "OIDC_CLIENT_APP_FILES", {"seafile": "infra/k8s/helm-values/seafile.yaml"})


def test_oidc_coverage_passes_when_client_id_and_secret_are_both_wired(tmp_path, monkeypatch):
    _write_oidc_fixture(
        tmp_path, monkeypatch,
        defaults_client_ids=["seafile"],
        app_file_text=(
            'OAUTH_CLIENT_ID: "seafile"\n'
            "OAUTH_CLIENT_SECRET:\n"
            "  valueFrom:\n"
            "    secretKeyRef:\n"
            "      name: seafile-oidc-secret\n"
        ),
        external_secrets_text="metadata:\n  name: seafile-oidc-secret\n",
    )

    assert sync_platform.check_oidc_coverage({}) == []


def test_oidc_coverage_flags_a_client_id_with_no_matching_secret(tmp_path, monkeypatch):
    """Reproduces the Seafile/Gokapi/PeerTube shape: client_id is set
    app-side, but the ExternalSecret backing its secret was never declared
    (a dangling secretKeyRef the Kubernetes Secret would never materialize for)."""
    _write_oidc_fixture(
        tmp_path, monkeypatch,
        defaults_client_ids=["seafile"],
        app_file_text=(
            'OAUTH_CLIENT_ID: "seafile"\n'
            "OAUTH_CLIENT_SECRET:\n"
            "  valueFrom:\n"
            "    secretKeyRef:\n"
            "      name: seafile-oidc-secret\n"
        ),
        external_secrets_text="metadata:\n  name: some-other-secret\n",
    )

    problems = sync_platform.check_oidc_coverage({})

    assert len(problems) == 1
    assert "seafile-oidc-secret" in problems[0]
    assert "no matching ExternalSecret" in problems[0]


def test_oidc_coverage_flags_a_client_never_configured_app_side(tmp_path, monkeypatch):
    """Reproduces the Visio/LaSuite Meet shape: the realm declares a
    Keycloak client, but nothing on the application side ever references it."""
    _write_oidc_fixture(
        tmp_path, monkeypatch,
        defaults_client_ids=["seafile"],
        app_file_text="# no OIDC config here at all\n",
        external_secrets_text="metadata:\n  name: seafile-oidc-secret\n",
    )

    problems = sync_platform.check_oidc_coverage({})

    assert any("no matching client_id configured" in p for p in problems)


def test_oidc_coverage_flags_a_client_id_wired_with_no_secret_reference_at_all(tmp_path, monkeypatch):
    _write_oidc_fixture(
        tmp_path, monkeypatch,
        defaults_client_ids=["seafile"],
        app_file_text='OAUTH_CLIENT_ID: "seafile"\n# secret never referenced\n',
        external_secrets_text="metadata:\n  name: seafile-oidc-secret\n",
    )

    problems = sync_platform.check_oidc_coverage({})

    assert len(problems) == 1
    assert "references no" in problems[0]


def test_oidc_coverage_passes_for_an_oauth2_proxy_gated_client(tmp_path, monkeypatch):
    """OnlyOffice/Novu don't support OIDC natively - their Keycloak client
    authenticates an oauth2-proxy forward_auth gate instead (see
    docs/oidc.md), so the "app file" is the oauth2-proxy gate's own
    helm-values file, and the client_id appears there only in a comment
    documenting which key of its existingSecret carries it - both
    legitimate for this check, which only asks "is this client referenced
    somewhere in the file that actually uses it"."""
    _write_oidc_fixture(
        tmp_path, monkeypatch,
        defaults_client_ids=["onlyoffice"],
        app_file_text=(
            "config:\n"
            '  # client_id: "onlyoffice" - supplied via existingSecret below\n'
            "  existingSecret: onlyoffice-oidc-secret\n"
        ),
        external_secrets_text="metadata:\n  name: onlyoffice-oidc-secret\n",
    )
    monkeypatch.setattr(
        sync_platform, "OIDC_CLIENT_APP_FILES", {"onlyoffice": "infra/k8s/helm-values/seafile.yaml"}
    )

    assert sync_platform.check_oidc_coverage({}) == []


def test_oidc_coverage_flags_a_client_missing_from_the_app_files_mapping(tmp_path, monkeypatch):
    """A client_id declared in Keycloak's defaults with no entry at all in
    OIDC_CLIENT_APP_FILES - the mapping itself falling out of sync, distinct
    from a wired-but-broken client."""
    _write_oidc_fixture(
        tmp_path, monkeypatch,
        defaults_client_ids=["seafile", "unmapped-client"],
        app_file_text=(
            'OAUTH_CLIENT_ID: "seafile"\n'
            "OAUTH_CLIENT_SECRET:\n"
            "  valueFrom:\n"
            "    secretKeyRef:\n"
            "      name: seafile-oidc-secret\n"
        ),
        external_secrets_text="metadata:\n  name: seafile-oidc-secret\n",
    )

    problems = sync_platform.check_oidc_coverage({})

    assert len(problems) == 1
    assert "unmapped-client" in problems[0]
    assert "does not know which application file" in problems[0]
