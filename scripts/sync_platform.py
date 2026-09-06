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
    - tests/integration/_platform_defaults.py  (generated file, do not edit)

Never writes to platform.yaml itself.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
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
    "infra/k8s/manifests/caddy.yaml",
    "infra/k8s/manifests/gokapi.yaml",
    "infra/k8s/helm-values/external-dns.yaml",
    "connectors/thunderbird-filelink-gokapi/manifest.json",
]


def compute_domain_changes(platform: dict) -> list[Change]:
    domains = platform.get("domains")
    if not domains:
        return []
    base = domains["base"]
    subdomains = domains["subdomains"].values()

    changes = []
    for rel_path in DOMAIN_TARGET_FILES:
        path = REPO_ROOT / rel_path
        text = path.read_text()
        for subdomain in subdomains:
            text = sub_domain(text, subdomain, base)
        for bare_pattern in _BARE_DOMAIN_PATTERNS.get(path, []):
            text = re.sub(bare_pattern, rf"\g<1>{base}\g<2>", text)
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


def compute_test_defaults_changes(platform: dict) -> list[Change]:
    path = REPO_ROOT / "tests" / "integration" / "_platform_defaults.py"
    port_map = all_ports(platform)

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

    changes: list[Change] = []
    changes += compute_compose_changes(platform)
    changes += compute_dockerfile_changes(platform)
    changes += compute_helm_changes(platform)
    changes += compute_k3d_config_change(platform)
    changes += compute_env_example_changes(platform)
    changes += compute_test_defaults_changes(platform)
    changes += compute_domain_changes(platform)

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
