#!/usr/bin/env python3
"""
Synchronizes every consumer file from `platform.yaml` (single source of
image versions and ports, see that file's header for the rationale).

Usage:
    python3 scripts/sync_platform.py            # applies the changes
    python3 scripts/sync_platform.py --check    # fails (exit 1) if a
                                                  # generated/patched file
                                                  # would diverge from platform.yaml

Files touched:
    - docker-compose/docker-compose.yml   (image tags, patched in place)
    - docker-compose/.env.example         (generated ports block)
    - infra/k8s/helm-values/*.yaml        (image.repository / image.tag)
    - infra/k8s/manifests/gokapi.yaml     (raw `image:` line)
    - connectors/*/Dockerfile             (Node base tag, patched in place)
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


def compute_compose_changes(platform: dict) -> list[Change]:
    compose_path = REPO_ROOT / "docker-compose" / "docker-compose.yml"
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
    text = sub_image_tag(text, "node", shared["node"])

    return [Change(compose_path, text, "docker-compose.yml (image tags)")]


def compute_dockerfile_changes(platform: dict) -> list[Change]:
    node_tag = platform["shared"]["node"]
    changes = []
    for dockerfile in sorted((REPO_ROOT / "connectors").glob("*/Dockerfile")):
        text = dockerfile.read_text()
        new_text = sub_from_tag(text, "node", node_tag)
        changes.append(Change(dockerfile, new_text, f"{dockerfile.relative_to(REPO_ROOT)} (Node base image)"))
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


def compute_env_example_changes(platform: dict) -> list[Change]:
    path = REPO_ROOT / "docker-compose" / ".env.example"
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
        "same source as docker-compose/.env.example.",
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

    changes: list[Change] = []
    changes += compute_compose_changes(platform)
    changes += compute_dockerfile_changes(platform)
    changes += compute_helm_changes(platform)
    changes += compute_env_example_changes(platform)
    changes += compute_test_defaults_changes(platform)

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
