#!/usr/bin/env python3
"""
Synchronizes every consumer file from `platform.yaml` (single source of
image versions, ports, and public domain names, see that file's header for
the rationale).

Usage:
    python3 scripts/sync_platform.py            # applies the changes
    python3 scripts/sync_platform.py --check    # fails (exit 1) if a
                                                  # generated/patched file
                                                  # would diverge from platform.yaml

Files touched:
    - dev-cluster/grommunio-dev/docker-compose.yml (image tag, patched in place)
    - dev-cluster/grommunio-dev/.env.example       (generated ports block)
    - infra/k8s/helm-values/*.yaml        (image.repository / image.tag, domain names)
    - infra/k8s/manifests/gokapi.yaml     (raw `image:` line, domain names)
    - infra/k8s/manifests/caddy.yaml      (domain names)
    - connectors/*/Dockerfile             (Python base tag, patched in place)
    - connectors/thunderbird-filelink-gokapi/manifest.json  (domain name)
    - connectors/thunderbird-filelink-gokapi/policies.json  (domain name)
    - infra/k8s/manifests/onboarding.yaml  (generated: onboarding page + QR codes, study 2.5)
    - infra/k8s/manifests/dev/caddy.yaml    (Caddyfile only, generated from the
                                              production Caddyfile - see
                                              compute_dev_caddy_change())
    - tests/integration/_platform_defaults.py  (generated file, do not edit)

Also enforces (never generates/patches, only fails loudly on drift, both in
apply and --check mode):
    - domain coverage: every platform.yaml subdomain has a Caddyfile site
      block and external-dns hostname entry (check_domain_coverage())
    - OIDC coverage: every Keycloak client declared in
      infra/ansible/roles/keycloak_realm/defaults/main.yml has a matching
      application-side client_id and a real ExternalSecret backing its
      client secret (check_oidc_coverage(), see docs/oidc.md)

Never writes to platform.yaml itself.
"""

import argparse
import html
import io
import re
import sys
import textwrap
import urllib.parse
from pathlib import Path

import qrcode
import qrcode.image.svg
import yaml
from ruamel.yaml.scalarstring import LiteralScalarString
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
PLATFORM_FILE = REPO_ROOT / "platform.yaml"

GENERATED_HEADER = (
    "# This block is generated from platform.yaml by scripts/sync_platform.py.\n"
    "# Do not edit by hand: change platform.yaml then re-run the script.\n"
)
PORTS_BEGIN = "# BEGIN GENERATED PORTS (platform.yaml)"
PORTS_END = "# END GENERATED PORTS"

ruamel_yaml = YAML()
ruamel_yaml.preserve_quotes = True
ruamel_yaml.width = 4096  # avoids unwanted line wraps on long comments
# Convention used throughout infra/k8s/helm-values/*.yaml: sequence items are
# indented 2 spaces under their parent key (`env:\n  - name: ...`). Without
# this setting, ruamel falls back to its default style (item aligned with the
# key) and regenerates a massive, non-functional diff on any file containing
# so much as a single list.
ruamel_yaml.indent(mapping=2, sequence=4, offset=2)


class Change:
    """A pending change to a file: (path, desired content)."""

    def __init__(self, path: Path, desired: str, description: str) -> None:
        self.path = path
        self.desired = desired
        self.description = description

    def current(self) -> str:
        return self.path.read_text() if self.path.exists() else ""

    def is_dirty(self) -> bool:
        return self.current() != self.desired

    def apply(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.desired)


def load_platform() -> dict:
    with PLATFORM_FILE.open() as f:
        return yaml.safe_load(f)


def sub_image_tag(text: str, repository: str, new_tag: str) -> str:
    """Replaces `image: <repository>:<old-tag>` with `<repository>:<new_tag>`,
    preserving everything else on the line (e.g. a trailing comment)."""
    pattern = re.compile(
        r"(image:\s*)" + re.escape(repository) + r":[^\s\"']+"
    )
    return pattern.sub(lambda m: f"{m.group(1)}{repository}:{new_tag}", text)


def sub_from_tag(text: str, repository: str, new_tag: str) -> str:
    """Replaces `FROM <repository>:<old-tag>` (Dockerfile), preserving a
    trailing `AS <stage>` if present."""
    pattern = re.compile(
        r"(FROM\s+)" + re.escape(repository) + r":[^\s]+"
    )
    return pattern.sub(lambda m: f"{m.group(1)}{repository}:{new_tag}", text)


def sub_domain(text: str, subdomain: str, new_base: str) -> str:
    """Replaces `<subdomain>.<anything-that-looks-like-a-domain>` with
    `<subdomain>.<new_base>`, anchored on the subdomain label (stable
    identifier tied to a specific service) rather than on the base domain
    currently in the file — same principle as sub_image_tag anchoring on the
    repository name rather than the previous tag, so re-running this after
    changing `domains.base` in platform.yaml always converges, regardless of
    what base domain the file currently has.

    The lookbehind (rather than a plain `\\b`) is required: `\\b` alone lets
    a short subdomain label like "call" match mid-identifier inside an
    unrelated in-cluster Service DNS name such as
    "element-call.libre365.svc.cluster.local" (the hyphen before "call" is
    still a word boundary) — corrupting it into
    "element-call.libre365.example.org". The lookbehind additionally
    excludes a preceding word character, dot, or hyphen, so the subdomain
    must start a fresh hostname label."""
    pattern = re.compile(r"(?<![\w.-])" + re.escape(subdomain) + r"\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
    return pattern.sub(f"{subdomain}.{new_base}", text)


# Files with a "bare" occurrence of the base domain (no subdomain prefix):
# a Matrix server_name, or the Thunderbird extension's WebExtension ID
# (`<name>@<domain>` format). Each entry anchors on a stable, unrelated-to-
# the-domain marker (a YAML key name, or the extension ID's fixed prefix),
# capturing only the domain portion to replace — sub_domain's subdomain-label
# anchor doesn't apply here since there is no subdomain.
_BARE_DOMAIN_PATTERNS = {
    REPO_ROOT / "infra/k8s/helm-values/element-web.yaml": [
        r'(server_name:\s*")[^"]*(")',
    ],
    REPO_ROOT / "infra/k8s/helm-values/element-call.yaml": [
        r'(name:\s*DEFAULT_HOMESERVER\s*\n\s*value:\s*")[^"]*(")',
    ],
    REPO_ROOT / "connectors/thunderbird-filelink-gokapi/manifest.json": [
        r'("id":\s*"gokapi-filelink@)[^"]*(")',
    ],
    REPO_ROOT / "infra/k8s/helm-values/external-dns.yaml": [
        r'(domainFilters:\s*\n\s*-\s*)\S+()',
    ],
    REPO_ROOT / "infra/k8s/manifests/gokapi.yaml": [
        # GOKAPI_ADMIN_EMAIL's value ("admin@<base>") - a bare-base-domain
        # pattern, not a subdomain one (sub_domain() already handles every
        # "<subdomain>.<base>" occurrence in this same file, e.g. the
        # Ingress host).
        r'(value:\s*"admin@)[^"]*(")',
    ],
}

# Every file containing a subdomain-prefixed public domain name (see
# platform.yaml's `domains` section for the rationale). Files using only
# `*.libre365.svc.cluster.local` (in-cluster Service DNS, e.g. the k3d dev
# manifests) are a different, unrelated namespace and are not listed here.
DOMAIN_TARGET_FILES = [
    "infra/k8s/helm-values/keycloak.yaml",
    "infra/k8s/helm-values/synapse.yaml",
    "infra/k8s/helm-values/element-web.yaml",
    "infra/k8s/helm-values/element-call.yaml",
    "infra/k8s/helm-values/visio-meet.yaml",
    "infra/k8s/helm-values/seafile.yaml",
    "infra/k8s/helm-values/onlyoffice.yaml",
    "infra/k8s/helm-values/vikunja.yaml",
    "infra/k8s/helm-values/minio.yaml",
    "infra/k8s/helm-values/peertube.yaml",
    "infra/k8s/helm-values/novu.yaml",
    "infra/k8s/helm-values/oauth2-proxy-onlyoffice.yaml",
    "infra/k8s/helm-values/oauth2-proxy-novu.yaml",
    "infra/k8s/manifests/caddy.yaml",
    "infra/k8s/manifests/gokapi.yaml",
    "infra/k8s/helm-values/external-dns.yaml",
    "connectors/thunderbird-filelink-gokapi/manifest.json",
    "connectors/thunderbird-filelink-gokapi/policies.json",
]


def compute_domain_changes(platform: dict) -> list[Change]:
    domains = platform.get("domains")
    if not domains:
        return []
    base = domains["base"]
    subdomains = domains["subdomains"].values()
    realm_name = platform["services"]["keycloak"]["realm_name"]

    changes = []
    for rel_path in DOMAIN_TARGET_FILES:
        path = REPO_ROOT / rel_path
        text = path.read_text()
        for subdomain in subdomains:
            text = sub_domain(text, subdomain, base)
        for bare_pattern in _BARE_DOMAIN_PATTERNS.get(path, []):
            text = re.sub(bare_pattern, rf"\g<1>{base}\g<2>", text)
        # Every OIDC app config builds its issuer/authorization URL as
        # ".../realms/<realm_name>" - this used to be a literal "libre365"
        # independently hand-copied into 7 different files (see
        # platform.yaml's services.keycloak.realm_name comment for the
        # full story), with nothing keeping them in sync with the Ansible
        # role that actually creates the realm. Matched structurally
        # (any "realms/<segment>"), not against a specific name, so this
        # keeps working regardless of what the realm is currently called.
        text = re.sub(r"realms/[a-zA-Z0-9_-]+", f"realms/{realm_name}", text)
        changes.append(Change(path, text, f"{rel_path} (domain names)"))
    return changes


# Subdomain keys that legitimately have NO Caddyfile site block: `registry`
# is a container-registry hostname (pulled by kubelet, never browsed/proxied),
# `livekit` has no Kubernetes deployment anywhere in this repository —
# visio-meet.yaml and element-call.yaml both USE a LiveKit URL
# (LIVEKIT_URL/LIVEKIT_API_URL) but neither DEPLOYS LiveKit itself; that gap
# is explained in infra/k8s/helm-values/README.md's "Out of scope for this
# directory" section, not in either of those two files — `mail` (Grommunio)
# is a Proxmox VM appliance, not a Kubernetes Service at all (see
# infra/ansible/, consumed directly by group_vars/all.yml instead) — and
# `autodiscover` is the Microsoft Autodiscover hostname for the same
# Grommunio VM (study 1.9), populated the same way as `mail` (see
# docs/clients.md), not through Caddy either. Every other domain in
# platform.yaml is expected to be reachable through Caddy
# (../k8s/manifests/caddy.yaml) — see infra/k8s/helm-values/README.md,
# "Public entry point: Caddy".
DOMAINS_WITHOUT_CADDY_SITE = {"registry", "livekit", "mail", "autodiscover"}


def check_domain_coverage(platform: dict) -> list[str]:
    """Guards against exactly the kind of gap found by manual review once
    already (5 domains declared in platform.yaml with no matching Caddyfile
    site block, and Ingress objects nobody could reach): every subdomain not
    in DOMAINS_WITHOUT_CADDY_SITE must appear as a Caddyfile site address in
    infra/k8s/manifests/caddy.yaml, and in the Caddy Service's external-dns
    hostname annotation. Returns a list of human-readable problems (empty if
    none) — checked unconditionally (both `sync_platform.py` and
    `--check`), since this is a structural consistency guarantee, not
    something to silently "fix" by generating content none of this script's
    other functions know how to write (a Caddyfile site block is
    hand-authored, not generated)."""
    domains = platform.get("domains")
    if not domains:
        return []

    expected = {
        key: subdomain
        for key, subdomain in domains["subdomains"].items()
        if key not in DOMAINS_WITHOUT_CADDY_SITE
    }

    caddy_text = (REPO_ROOT / "infra/k8s/manifests/caddy.yaml").read_text()
    # Site addresses are lines like `sso.libre365.example.org {` or
    # `matrix.libre365.example.org:8448 {` inside the Caddyfile ConfigMap
    # block — the `:port` suffix (if any) is irrelevant to domain coverage.
    site_addresses = set(re.findall(r"^\s*([a-zA-Z0-9.-]+(?::\d+)?)\s*\{", caddy_text, re.MULTILINE))
    site_domains = {addr.split(":")[0] for addr in site_addresses}

    annotation_match = re.search(
        r'external-dns\.alpha\.kubernetes\.io/hostname:\s*"([^"]*)"', caddy_text
    )
    annotated_domains = set(annotation_match.group(1).split(",")) if annotation_match else set()

    # Matched on the SUBDOMAIN LABEL (e.g. "sso"), not the full FQDN with
    # the current `domains.base` baked in: this check runs unconditionally,
    # including as the very first thing `sync_platform.py` does on a run
    # that is ABOUT to change `domains.base` itself — comparing full FQDNs
    # would then compare the NEW base (from the platform.yaml already on
    # disk) against caddy.yaml's site blocks, which still carry the OLD
    # base until compute_domain_changes() below patches them later in this
    # same run. That ordering bug made changing `domains.base` at all
    # immediately fail with a false "no matching Caddyfile site block" for
    # every single domain, before ever reaching the code that would have
    # fixed it. Label-based matching sidesteps the ordering entirely: which
    # base is currently on disk doesn't matter, only whether a site block
    # for that subdomain label exists at all.
    site_labels = {domain.split(".", 1)[0] for domain in site_domains}
    annotated_labels = {domain.split(".", 1)[0] for domain in annotated_domains}

    problems = []
    for key, subdomain in expected.items():
        fqdn = f"{subdomain}.{domains['base']}"
        if subdomain not in site_labels:
            problems.append(
                f"platform.yaml declares domains.subdomains.{key} ({fqdn}) but no "
                "matching Caddyfile site block was found in infra/k8s/manifests/caddy.yaml "
                "(add one, or add its key to DOMAINS_WITHOUT_CADDY_SITE in "
                "scripts/sync_platform.py if it's genuinely not meant to be reachable through Caddy)"
            )
        elif subdomain not in annotated_labels:
            problems.append(
                f"{fqdn} has a Caddyfile site block but is missing from the Caddy Service's "
                "external-dns.alpha.kubernetes.io/hostname annotation in infra/k8s/manifests/caddy.yaml "
                "(external-dns would never create its DNS record)"
            )
    return problems


# One entry per `keycloak_oidc_clients` client_id declared in
# infra/ansible/roles/keycloak_realm/defaults/main.yml — maps it to the
# infra/k8s/helm-values (or manifests) file where the application side of
# that same OIDC client is expected to be configured. Not every client_id
# matches its app file's name 1:1 (matrix-synapse -> synapse.yaml,
# gokapi -> manifests/gokapi.yaml, not helm-values/), hence an explicit
# mapping rather than a naming guess.
OIDC_CLIENT_APP_FILES = {
    "seafile": "infra/k8s/helm-values/seafile.yaml",
    "vikunja": "infra/k8s/helm-values/vikunja.yaml",
    "matrix-synapse": "infra/k8s/helm-values/synapse.yaml",
    "gokapi": "infra/k8s/manifests/gokapi.yaml",
    "peertube": "infra/k8s/helm-values/peertube.yaml",
    "visio-meet": "infra/k8s/helm-values/visio-meet.yaml",
    # These two have no OIDC support of their own: the client authenticates
    # an oauth2-proxy forward_auth gate in front of the app, not the app
    # itself (see docs/oidc.md and each oauth2-proxy-*.yaml's own header).
    "onlyoffice": "infra/k8s/helm-values/oauth2-proxy-onlyoffice.yaml",
    "novu": "infra/k8s/helm-values/oauth2-proxy-novu.yaml",
}


def check_oidc_coverage(platform: dict) -> list[str]:
    """Guards against exactly the kind of gap a manual review once found by
    hand (docs/oidc.md's changelog): a `keycloak_oidc_clients` entry in
    infra/ansible/roles/keycloak_realm/defaults/main.yml with no matching
    application-side `client_id` configuration, or with a `client_id` but no
    secret ever wired (a dangling `secretKeyRef`/`existingSecret` with no
    matching ExternalSecret, so the Kubernetes Secret it points at would
    never materialize). Every client_id/secret name involved is read from
    the repository's own files, never hardcoded here, so a future client
    added the right way (app file + `*-oidc-secret` ExternalSecret) needs no
    change to this function - only OIDC_CLIENT_APP_FILES, for the small
    subset of clients whose app file name doesn't match their client_id.
    Checked unconditionally (both `sync_platform.py` and `--check`), for the
    same reason as check_domain_coverage(): this is a structural consistency
    guarantee, not something to silently "fix" by generating hand-authored
    application config."""
    defaults_path = REPO_ROOT / "infra/ansible/roles/keycloak_realm/defaults/main.yml"
    defaults_text = defaults_path.read_text()
    client_ids = re.findall(r'client_id:\s*"([^"]+)"', defaults_text)

    secrets_text = (REPO_ROOT / "infra/k8s/manifests/external-secrets.yaml").read_text()
    declared_secret_names = set(re.findall(r"^\s*name:\s*(\S+-oidc-secret)\s*$", secrets_text, re.MULTILINE))

    problems = []
    for client_id in client_ids:
        rel_path = OIDC_CLIENT_APP_FILES.get(client_id)
        if rel_path is None:
            problems.append(
                f"infra/ansible/roles/keycloak_realm/defaults/main.yml declares an OIDC client "
                f'"{client_id}" but scripts/sync_platform.py\'s OIDC_CLIENT_APP_FILES does not know '
                "which application file configures it (add it there once the app side exists)"
            )
            continue

        app_path = REPO_ROOT / rel_path
        app_text = app_path.read_text()
        if f'"{client_id}"' not in app_text:
            problems.append(
                f'Keycloak client "{client_id}" has no matching client_id configured in {rel_path} '
                "(the realm declares the client, but nothing on the application side would ever use it)"
            )

        app_secret_names = set(re.findall(r"([a-z0-9][a-z0-9-]*-oidc-secret)", app_text))
        if not app_secret_names:
            problems.append(
                f'{rel_path} configures OIDC client "{client_id}" but references no '
                '"*-oidc-secret" secretKeyRef/existingSecret at all (the client secret would '
                "never be supplied to the running application)"
            )
            continue

        missing = app_secret_names - declared_secret_names
        for secret_name in sorted(missing):
            problems.append(
                f'{rel_path} references secret "{secret_name}" for OIDC client "{client_id}" but no '
                "matching ExternalSecret exists in infra/k8s/manifests/external-secrets.yaml "
                "(the Kubernetes Secret would never materialize)"
            )
    return problems


def compute_compose_changes(platform: dict) -> list[Change]:
    compose_path = REPO_ROOT / "dev-cluster" / "grommunio-dev" / "docker-compose.yml"
    text = compose_path.read_text()

    for _name, svc in platform["services"].items():
        compose = svc.get("compose")
        version = svc.get("version")
        if not compose or not version:
            continue
        text = sub_image_tag(text, compose["image"], version)

    shared = platform["shared"]
    text = sub_image_tag(text, "postgres", shared["postgres"])
    text = sub_image_tag(text, "redis", shared["redis"])
    text = sub_image_tag(text, "mariadb", shared["mariadb"])

    return [Change(compose_path, text, "docker-compose.yml (image tags)")]


def compute_dockerfile_changes(platform: dict) -> list[Change]:
    # Connector Dockerfiles are Python/FastAPI (`FROM python:<tag>`).
    python_tag = platform["shared"]["python"]
    changes = []
    for dockerfile in sorted((REPO_ROOT / "connectors").glob("*/Dockerfile")):
        text = dockerfile.read_text()
        new_text = sub_from_tag(text, "python", python_tag)
        changes.append(Change(dockerfile, new_text, f"{dockerfile.relative_to(REPO_ROOT)} (Python base image)"))
    return changes


def set_nested(data, dot_path: str, value: str) -> None:
    """`.image.tag` -> data['image']['tag'] = value, creating any missing
    levels (e.g. minio.yaml currently has no explicit `image:` block — this
    creates one rather than leaving the chart on its default, silent, and
    therefore drift-prone tag)."""
    from ruamel.yaml.comments import CommentedMap

    keys = [k for k in dot_path.split(".") if k]
    node = data
    for key in keys[:-1]:
        if key not in node:
            node[key] = CommentedMap()
        node = node[key]
    node[keys[-1]] = value


def sibling_path(dot_path: str, new_leaf: str) -> str:
    """`.image.tag` -> `.image.<new_leaf>`."""
    keys = dot_path.split(".")
    keys[-1] = new_leaf
    return ".".join(keys)


def _helm_specs(svc: dict) -> list[dict]:
    """Normalizes `helm` (a single patch) and/or `helm_images` (several
    images in the same file, e.g. visio-meet backend+frontend) into a flat
    list of specs {file, image_repository, tag_path, version, raw_image_line?}."""
    specs = []
    helm = svc.get("helm")
    if helm:
        specs.append({**helm, "version": svc.get("version")})
    for extra in svc.get("helm_images") or []:
        specs.append({**extra, "version": extra.get("version", svc.get("version"))})
    return specs


def compute_helm_changes(platform: dict) -> list[Change]:
    from io import StringIO

    # Grouped by file: several images (backend/frontend) can target the same
    # values file, so they must be applied in a single load/write pass to
    # avoid overwriting one another.
    specs_by_file: dict[Path, list[dict]] = {}
    for svc in platform["services"].values():
        for spec in _helm_specs(svc):
            target = REPO_ROOT / spec["file"]
            specs_by_file.setdefault(target, []).append(spec)

    changes = []
    for target, specs in specs_by_file.items():
        raw_specs = [s for s in specs if s.get("raw_image_line")]
        structured_specs = [s for s in specs if not s.get("raw_image_line")]

        if raw_specs:
            text = target.read_text()
            for spec in raw_specs:
                text = sub_image_tag(text, spec["image_repository"], spec["version"])
            changes.append(Change(target, text, f"{spec['file']} (raw image line)"))
            continue

        with target.open() as f:
            doc = ruamel_yaml.load(f)

        for spec in structured_specs:
            tag_path = spec.get("tag_path")
            if not tag_path:
                continue
            set_nested(doc, tag_path, spec["version"])
            set_nested(doc, sibling_path(tag_path, "repository"), spec["image_repository"])

        buf = StringIO()
        ruamel_yaml.dump(doc, buf)
        changes.append(Change(target, buf.getvalue(), f"{specs[0]['file']} (image.tag / image.repository)"))

    return changes


def all_ports(platform: dict) -> dict:
    """Merges every port variable declared in platform.yaml into a single
    dict {VARIABLE_NAME: value}, in reading order (services, then
    connectors, then miscellaneous) for a stable, readable diff."""
    merged: dict[str, int] = {}
    for svc in platform["services"].values():
        merged.update(svc.get("ports") or {})
    merged.update(platform.get("connector_ports") or {})
    merged.update(platform.get("other_ports") or {})
    return merged


def k3d_ports(platform: dict) -> dict:
    """Ports that must be reachable from the host through the k3d cluster's
    load balancer: every service port except `grommunio_dev` (stays on
    docker-compose, see its entry in platform.yaml), plus every connector
    port."""
    merged: dict[str, int] = {}
    for name, svc in platform["services"].items():
        if name == "grommunio_dev":
            continue
        merged.update(svc.get("ports") or {})
    merged.update(platform.get("connector_ports") or {})
    return merged


def compute_k3d_config_change(platform: dict) -> list[Change]:
    path = REPO_ROOT / "dev-cluster" / "k3d-config.yaml"
    cluster = platform["dev_cluster"]

    lines = [
        "# " + "=" * 77,
        "# Generated by scripts/sync_platform.py from platform.yaml. Do not edit by",
        "# hand: change platform.yaml's `dev_cluster` section (topology) or its port",
        "# tables (which ports get mapped) then re-run the script.",
        "# " + "=" * 77,
        "apiVersion: k3d.io/v1alpha5",
        "kind: Simple",
        "metadata:",
        f"  name: {cluster['name']}",
        f"servers: {cluster['servers']}",
        f"agents: {cluster['agents']}",
        "options:",
        "  k3s:",
        "    extraArgs:",
        "      # Widens the NodePort range so the ports below (largely <30000,",
        "      # matching docker-compose's historical port numbers) are valid",
        "      # NodePorts, instead of forcing yet another port remapping.",
        f"      - arg: --kube-apiserver-arg=service-node-port-range={cluster['node_port_range']}",
        "        nodeFilters: [\"server:*\"]",
        "  kubeconfig:",
        "    updateDefaultKubeconfig: true",
        "    switchCurrentContext: true",
        "ports:",
    ]
    for var_name, port in k3d_ports(platform).items():
        lines.append(f"  # {var_name}")
        lines.append(f"  - port: {port}:{port}")
        lines.append("    nodeFilters: [\"loadbalancer\"]")
    lines.append("")

    return [Change(path, "\n".join(lines), "dev-cluster/k3d-config.yaml (generated)")]


def compute_env_example_changes(platform: dict) -> list[Change]:
    path = REPO_ROOT / "dev-cluster" / "grommunio-dev" / ".env.example"
    text = path.read_text()

    lines = [PORTS_BEGIN, GENERATED_HEADER.rstrip("\n")]
    for var_name, port in all_ports(platform).items():
        lines.append(f"{var_name}={port}")
    lines.append(PORTS_END)
    generated_block = "\n".join(lines)

    pattern = re.compile(
        re.escape(PORTS_BEGIN) + r".*?" + re.escape(PORTS_END), re.DOTALL
    )
    if pattern.search(text):
        new_text = pattern.sub(generated_block, text)
    else:
        raise SystemExit(
            f"'{path}' does not contain the {PORTS_BEGIN} / {PORTS_END} markers — "
            "add them once by hand around the existing ports block."
        )

    return [Change(path, new_text, ".env.example (ports block)")]


def _qr_svg_markup(data: str) -> str:
    """Renders `data` as an inline <svg> fragment (no XML declaration, ready
    to embed directly in HTML), using the `qrcode` package's own SvgPathImage
    factory - a well-established, independently maintained implementation,
    not a hand-rolled QR encoder (getting the error-correction/matrix-
    placement algorithm subtly wrong would silently produce an
    unscannable code, not an obvious bug)."""
    buffer = io.BytesIO()
    qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=8).save(buffer)
    return buffer.getvalue().decode("utf-8").split("?>", 1)[1].strip()


def _store_search_links(app_name: str) -> str:
    """Deliberately links to each store's SEARCH results rather than a
    specific listing (exact bundle ID / package name), since neither could
    be verified against the live App Store/Play Store from this
    environment - a wrong guessed direct link is worse than a search page
    the user picks the right result from once."""
    apple = f"https://apps.apple.com/search?term={urllib.parse.quote(app_name)}"
    google = f"https://play.google.com/store/search?q={urllib.parse.quote(app_name)}&c=apps"
    return f'<a href="{apple}">App Store</a> / <a href="{google}">Play Store</a> (search results, not a direct link - see this script\'s header comment)'


def compute_onboarding_changes(platform: dict) -> list[Change]:
    """Study 2.5 (L.454-457): "A static onboarding page (HTML, behind
    Caddy) listing each application with an App Store/Play Store link and
    a preconfigured deep-link QR code" + "An optional .mobileconfig file to
    preconfigure the Grommunio mail account (ActiveSync) on Mac/iPhone" -
    explicitly "No MDM infrastructure" (2.5's own conclusion).

    GENERATED, not hand-edited (same convention as
    tests/integration/_platform_defaults.py): each QR code is a rendered
    SVG encoding of a URL containing the domain, which sub_domain()'s plain
    text substitution (used everywhere else in this file) cannot
    "re-render" if the domain changes - only regenerating from
    platform.yaml can.

    The .mobileconfig is deliberately GENERIC: only the EAS server
    hostname, no username/password/email baked in - iOS/macOS prompts for
    those interactively during profile installation instead. This is what
    makes it safe to publish on this UNAUTHENTICATED static page: nothing
    personal or secret is in it. A per-user personalized profile would need
    its own small backend (SSO-gated generation) sitting behind
    authentication - out of scope here, and it would contradict 2.5's own
    "no MDM server" conclusion."""
    domains = platform.get("domains")
    if not domains:
        return []
    base = domains["base"]
    sub = domains["subdomains"]

    apps = [
        {
            "name": "Element (Matrix chat, study 1.2)",
            "store_name": "Element Messenger",
            "qr_target": f"element://https://{sub['matrix']}.{base}",
            "instructions": (
                "Install Element, then scan this code to auto-configure the firm's "
                "homeserver (deep-link format per study 2.5, L.446)."
            ),
        },
        {
            "name": "Seafile (files, study 1.4)",
            "store_name": "Seafile",
            "qr_target": f"https://{sub['files']}.{base}",
            "instructions": (
                'Install Seafile, choose "Add an account", then scan this code '
                "(or type the address shown) as the server URL."
            ),
        },
        {
            "name": "Vikunja (tasks, study 1.6)",
            "store_name": "Vikunja",
            "qr_target": f"https://{sub['taches']}.{base}",
            "instructions": "Install Vikunja, then scan this code (or type the address shown) as the server URL.",
        },
        {
            "name": "Grommunio webmail (study 1.1)",
            "store_name": None,  # no dedicated app - native Mail app via the .mobileconfig below instead
            "qr_target": f"https://{sub['mail']}.{base}",
            "instructions": (
                "Scan to open webmail directly in a mobile browser, or use the native "
                "Mail app via the .mobileconfig profile below (Mac/iPhone, EAS/ActiveSync, no MDM)."
            ),
        },
    ]

    cards = []
    for app in apps:
        store_line = (
            f"<p class=\"store\">{_store_search_links(app['store_name'])}</p>"
            if app["store_name"]
            else ""
        )
        card = f"""    <div class="app-card">
      <h2>{html.escape(app['name'])}</h2>
      <div class="qr">{_qr_svg_markup(app['qr_target'])}</div>
      <p>{html.escape(app['instructions'])}</p>
      <p class="target"><code>{html.escape(app['qr_target'])}</code></p>"""
        if store_line:
            card += f"\n      {store_line}"
        card += "\n    </div>"
        cards.append(card)
    app_cards = "\n".join(cards)

    mail_domain = f"{sub['mail']}.{base}"
    onboarding_html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>libre365 - Get started</title>
<style>
  :root {{
    --libre365-brand-primary: #2B3B58;
    --libre365-brand-secondary: #F55364;
    --libre365-brand-surface: #EEEEEE;
    --libre365-brand-text: #0C141A;
    --libre365-brand-on-primary: #FFFFFF;
  }}
  body {{
    font-family: "Aileron", system-ui, -apple-system, sans-serif;
    background: var(--libre365-brand-surface);
    color: var(--libre365-brand-text);
    margin: 0;
    padding: 2rem;
  }}
  h1 {{ color: var(--libre365-brand-primary); }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1.5rem;
    max-width: 1100px;
    margin: 2rem auto;
  }}
  .app-card {{
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,.1);
  }}
  .app-card h2 {{ font-size: 1.1rem; color: var(--libre365-brand-primary); margin-top: 0; }}
  .qr {{ width: 160px; margin: 1rem auto; }}
  .qr svg {{ width: 100%; height: auto; }}
  .target code {{ font-size: .8rem; word-break: break-all; }}
  a {{ color: var(--libre365-brand-primary); }}
  a:hover {{ color: var(--libre365-brand-secondary); }}
  .mobileconfig {{ text-align: center; margin: 2rem auto; max-width: 500px; }}
</style>
</head>
<body>
<h1>Get started</h1>
<p>Install and configure the firm's applications on your Mac, iPhone, or Android device.
Scan the code for each application with your phone's camera.</p>

<div class="grid">
{app_cards}
</div>

<div class="mobileconfig">
  <h2>Mac / iPhone mail account (Grommunio, EAS)</h2>
  <p>Preconfigures the mail server address only - you'll be asked for your username
  and password when installing the profile, never stored in this file.</p>
  <p><a href="grommunio-eas.mobileconfig">Download the configuration profile</a></p>
</div>
</body>
</html>
"""

    mobileconfig = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>PayloadType</key>
            <string>com.apple.eas.account</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>PayloadIdentifier</key>
            <string>org.libre365.eas.account</string>
            <key>PayloadUUID</key>
            <string>FC23DD3A-771F-407D-A1C3-61C917955644</string>
            <key>PayloadDisplayName</key>
            <string>libre365 mail (Grommunio)</string>
            <key>EASHost</key>
            <string>{mail_domain}</string>
            <key>EASUseSSL</key>
            <true/>
        </dict>
    </array>
    <key>PayloadDisplayName</key>
    <string>libre365 - Grommunio mail account</string>
    <key>PayloadIdentifier</key>
    <string>org.libre365.eas.profile</string>
    <key>PayloadRemovalDisallowed</key>
    <false/>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>E0C4750C-D0C1-4A8D-8743-AA9CF43B0C4C</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
"""

    manifest_yaml = f"""# GENERATED by scripts/sync_platform.py from platform.yaml - do not edit by
# hand (same convention as tests/integration/_platform_defaults.py): each
# QR code below is a rendered SVG encoding of a URL containing the domain,
# which sub_domain()'s plain text substitution (used everywhere else in
# this file) cannot "re-render" if the domain changes - only regenerating
# from platform.yaml can. Study 2.5 (L.454-457), see
# compute_onboarding_changes()'s docstring in scripts/sync_platform.py for
# the full rationale, including why the .mobileconfig below carries no
# personal data (safe to serve from this UNAUTHENTICATED page) and why the
# App/Play Store links point at search results rather than a specific
# listing.
apiVersion: v1
kind: ConfigMap
metadata:
  name: onboarding-page
  namespace: libre365
  labels:
    app.kubernetes.io/name: caddy
    app.kubernetes.io/component: onboarding
data:
  index.html: |
{textwrap.indent(onboarding_html, '    ')}
  grommunio-eas.mobileconfig: |
{textwrap.indent(mobileconfig, '    ')}"""

    path = REPO_ROOT / "infra/k8s/manifests/onboarding.yaml"
    return [Change(path, manifest_yaml, "infra/k8s/manifests/onboarding.yaml (generated: onboarding page + QR codes)")]


def _dev_caddyfile_from_production(caddyfile_text: str) -> str:
    """
    Derives the k3d dev cluster's Caddyfile (infra/k8s/manifests/dev/
    caddy.yaml) from the real, already domain-patched production one
    (infra/k8s/manifests/caddy.yaml) - GENERATED so the two can never
    silently drift apart the way a hand-maintained dev copy eventually
    would (found happening for real: dev's Caddyfile was a hand-written,
    path-based portal with none of production's domain-based site blocks
    or SSO gates, discovered while trying to add a live test for the
    OnlyOffice/Novu oauth2-proxy gates and finding nothing in dev could
    exercise them).

    Only strips what the dev environment genuinely cannot run - domain
    site addresses, `forward_auth`/`route` SSO gates, and every backend
    hostname stay byte-for-byte the same values used in production
    (nothing new is hard-coded for "dev" here):

    - `html_inject` directives and the `order html_inject before respond`
      global option: both need the custom xcaddy-built HTML-injection
      plugin baked into production's Caddy image, which cannot be built
      or pulled from this sandboxed/local dev environment (see this
      file's own header comment). Dev loses the injected top bar, not the
      routing underneath it.
    - Automatic HTTPS on every domain site address, forced to plain
      `http://` instead: there is no real public DNS for
      `*.<domains.base>` to obtain a certificate for from a local
      cluster - left on, Caddy would hang retrying ACME issuance forever.

    `forward_auth`/`route` (the OnlyOffice/Novu SSO gates, study 1.7) are
    both Caddy built-ins since 2.7 - not part of the unavailable custom
    plugin - so they survive unchanged and ARE exercisable in dev, once
    something resolves `*.<domains.base>` to this Caddy instance inside
    the cluster (see dev-cluster/deploy.sh's CoreDNS step) and outside it
    (see tests/integration/conftest.py's `DomainRoutingAdapter`).
    """
    text = re.sub(
        r"\{\s*#[^\n]*\n\s*order html_inject before respond\s*\n\}\s*\n*",
        "",
        caddyfile_text,
        count=1,
    )
    text = re.sub(r"\n[ \t]*html_inject\s*\{[^}]*\}", "", text)
    # A line that is ONLY "<hostname[:port]> {" - matched structurally (not
    # against any specific domain name, so this keeps working regardless of
    # platform.yaml's domains.base) - excludes snippet definitions like
    # "(banner_assets) {", which start with "(".
    text = re.sub(
        r"(?m)^([a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?(?::\d+)?)[ \t]*\{[ \t]*$",
        r"http://\1 {",
        text,
    )
    return text


def compute_dev_caddy_change(platform: dict) -> list[Change]:
    """Regenerates infra/k8s/manifests/dev/caddy.yaml's Caddyfile from the
    real one via `_dev_caddyfile_from_production` (see its docstring) -
    that file's Deployment/Service documents are hand-maintained and kept
    untouched (ruamel round-trip), the same convention as every other file
    under infra/k8s/manifests/dev/ (sizing overlays, never platform.yaml-
    driven)."""
    domains = platform.get("domains")
    if not domains:
        return []

    prod_path = REPO_ROOT / "infra/k8s/manifests/caddy.yaml"
    prod_text = prod_path.read_text()
    base = domains["base"]
    for subdomain in domains["subdomains"].values():
        prod_text = sub_domain(prod_text, subdomain, base)

    prod_caddyfile = next(
        doc["data"]["Caddyfile"]
        for doc in yaml.safe_load_all(prod_text)
        if doc and doc.get("kind") == "ConfigMap" and "Caddyfile" in doc.get("data", {})
    )
    dev_caddyfile = _dev_caddyfile_from_production(prod_caddyfile)

    dev_path = REPO_ROOT / "infra/k8s/manifests/dev/caddy.yaml"
    with dev_path.open() as f:
        dev_docs = list(ruamel_yaml.load_all(f))
    dev_docs[0]["data"]["Caddyfile"] = LiteralScalarString(dev_caddyfile)

    buf = io.StringIO()
    ruamel_yaml.dump_all(dev_docs, buf)
    return [Change(dev_path, buf.getvalue(), "infra/k8s/manifests/dev/caddy.yaml (Caddyfile, generated from the production one)")]


def compute_test_defaults_changes(platform: dict) -> list[Change]:
    path = REPO_ROOT / "tests" / "integration" / "_platform_defaults.py"
    port_map = all_ports(platform)
    domains = platform.get("domains") or {}

    body = [
        '"""',
        "File generated by scripts/sync_platform.py from platform.yaml.",
        "Do NOT edit by hand: the default values in tests/integration/conftest.py",
        "must stay aligned with docker-compose's default ports (study 4.6) —",
        "that is precisely what this file guarantees, by being generated from the",
        "same source as dev-cluster/grommunio-dev/.env.example.",
        '"""',
        "",
        "DEFAULT_PORTS = {",
    ]
    for key in sorted(port_map):
        body.append(f'    "{key}": {port_map[key]!r},')
    body.append("}")
    body.append("")

    # DOMAIN_BASE/DOMAIN_SUBDOMAINS: the same values every OIDC config in
    # this repo uses (Keycloak's KC_HOSTNAME, each app's issuer/authurl) -
    # conftest.py's DomainRoutingAdapter/public_url fixtures read these
    # instead of a second, hard-coded copy of the domain, so a real
    # `domains.base` change (e.g. to a bought production domain) propagates
    # to the test suite the same way it already does to every Helm-values
    # file (see compute_domain_changes()).
    body.append(f"DOMAIN_BASE = {domains.get('base', '')!r}")
    body.append("DOMAIN_SUBDOMAINS = {")
    for key, subdomain in sorted((domains.get("subdomains") or {}).items()):
        body.append(f'    "{key}": {subdomain!r},')
    body.append("}")
    body.append("")

    # TEST_USER_USERNAME/TEST_USER_EMAIL: platform.yaml's test_dataset
    # (study 4.4, point 2) - conftest.py's test_user fixture reads these
    # instead of a hard-coded literal, matching the same account
    # infra/ansible/roles/keycloak_realm optionally provisions
    # (keycloak_realm_test_user_enabled). The password is deliberately NOT
    # here: it's a secret, never platform.yaml, always an env var/vault
    # variable - see conftest.py's test_user fixture.
    test_dataset = platform.get("test_dataset") or {}
    body.append(f"TEST_USER_USERNAME = {test_dataset.get('username', '')!r}")
    body.append(f"TEST_USER_EMAIL = {test_dataset.get('email', '')!r}")
    body.append("")

    content = "\n".join(body)
    return [Change(path, content, "tests/integration/_platform_defaults.py (generated)")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing, fail if any file would diverge from platform.yaml",
    )
    args = parser.parse_args()

    platform = load_platform()

    # Structural consistency, not drift: checked unconditionally (apply and
    # --check alike), since a missing Caddyfile site block or a missing
    # external-dns hostname entry isn't something this script can generate
    # by itself (both are hand-authored) - only flag it loudly.
    domain_problems = check_domain_coverage(platform)
    if domain_problems:
        print("Domain coverage problem(s) between platform.yaml and infra/k8s/manifests/caddy.yaml:", file=sys.stderr)
        for problem in domain_problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    # Same rationale as domain coverage above: a Keycloak OIDC client with
    # no matching application-side config, or an app referencing a secret
    # nobody ever declared as an ExternalSecret, isn't drift this script can
    # fix by generating hand-authored config - only flag it loudly.
    oidc_problems = check_oidc_coverage(platform)
    if oidc_problems:
        print("OIDC coverage problem(s) (see docs/oidc.md):", file=sys.stderr)
        for problem in oidc_problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    changes: list[Change] = []
    changes += compute_compose_changes(platform)
    changes += compute_dockerfile_changes(platform)
    changes += compute_helm_changes(platform)
    changes += compute_k3d_config_change(platform)
    changes += compute_env_example_changes(platform)
    changes += compute_test_defaults_changes(platform)
    changes += compute_domain_changes(platform)
    changes += compute_onboarding_changes(platform)
    changes += compute_dev_caddy_change(platform)

    dirty = [c for c in changes if c.is_dirty()]

    if args.check:
        if dirty:
            print("Drift detected between platform.yaml and the following files:", file=sys.stderr)
            for c in dirty:
                print(f"  - {c.description}", file=sys.stderr)
            print(
                "\nRun `python3 scripts/sync_platform.py` then commit the result.",
                file=sys.stderr,
            )
            return 1
        print("OK: no file diverges from platform.yaml.")
        return 0

    for c in dirty:
        c.apply()
        print(f"updated: {c.description}")
    if not dirty:
        print("Nothing to do: all files are already aligned with platform.yaml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
