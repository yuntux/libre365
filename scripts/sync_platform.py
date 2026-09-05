#!/usr/bin/env python3
"""
Synchronise tous les fichiers consommateurs à partir de `platform.yaml`
(source unique des versions d'image et des ports, cf. l'en-tête de ce
fichier pour le pourquoi).

Usage:
    python3 scripts/sync_platform.py            # applique les changements
    python3 scripts/sync_platform.py --check    # échoue (exit 1) si un
                                                  # fichier généré/patché
                                                  # divergerait de platform.yaml

Fichiers touchés :
    - docker-compose/docker-compose.yml   (tags d'image, patch en place)
    - docker-compose/.env.example         (bloc de ports généré)
    - infra/k8s/helm-values/*.yaml        (image.repository / image.tag)
    - infra/k8s/manifests/gokapi.yaml     (ligne `image:` brute)
    - connectors/*/Dockerfile             (tag de base Node, patch en place)
    - tests/integration/_platform_defaults.py  (fichier généré, ne pas éditer)

N'écrit jamais dans platform.yaml lui-même.
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
    "# Ce bloc est généré depuis platform.yaml par scripts/sync_platform.py.\n"
    "# Ne pas éditer à la main : modifier platform.yaml puis relancer le script.\n"
)
PORTS_BEGIN = "# BEGIN GENERATED PORTS (platform.yaml)"
PORTS_END = "# END GENERATED PORTS"

ruamel_yaml = YAML()
ruamel_yaml.preserve_quotes = True
ruamel_yaml.width = 4096  # évite les retours à la ligne intempestifs sur les commentaires longs
# Convention utilisée dans tout infra/k8s/helm-values/*.yaml : les items de
# séquence sont indentés de 2 espaces sous leur clé parente (`env:\n  - name:
# ...`). Sans ce réglage, ruamel retombe sur son style par défaut (item aligné
# avec la clé) et regénère un diff massif et non fonctionnel sur tout fichier
# contenant la moindre liste.
ruamel_yaml.indent(mapping=2, sequence=4, offset=2)


class Change:
    """Une modification en attente sur un fichier : (chemin, contenu désiré)."""

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
    """Remplace `image: <repository>:<ancien-tag>` par `<repository>:<new_tag>`,
    en préservant tout ce qui suit sur la ligne (commentaire éventuel)."""
    pattern = re.compile(
        r"(image:\s*)" + re.escape(repository) + r":[^\s\"']+"
    )
    return pattern.sub(lambda m: f"{m.group(1)}{repository}:{new_tag}", text)


def sub_from_tag(text: str, repository: str, new_tag: str) -> str:
    """Remplace `FROM <repository>:<ancien-tag>` (Dockerfile), en préservant
    un éventuel `AS <stage>` qui suit."""
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

    return [Change(compose_path, text, "docker-compose.yml (tags d'image)")]


def compute_dockerfile_changes(platform: dict) -> list[Change]:
    node_tag = platform["shared"]["node"]
    changes = []
    for dockerfile in sorted((REPO_ROOT / "connectors").glob("*/Dockerfile")):
        text = dockerfile.read_text()
        new_text = sub_from_tag(text, "node", node_tag)
        changes.append(Change(dockerfile, new_text, f"{dockerfile.relative_to(REPO_ROOT)} (base Node)"))
    return changes


def set_nested(data, dot_path: str, value: str) -> None:
    """`.image.tag` -> data['image']['tag'] = value, en créant les niveaux
    manquants (ex: minio.yaml n'a aujourd'hui aucun bloc `image:` explicite —
    on le crée plutôt que de laisser le chart sur son tag par défaut,
    silencieux et donc source de dérive)."""
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
    """Normalise `helm` (un seul patch) et/ou `helm_images` (plusieurs images
    dans le même fichier, ex: visio-meet backend+frontend) en une liste plate
    de specs {file, image_repository, tag_path, version, raw_image_line?}."""
    specs = []
    helm = svc.get("helm")
    if helm:
        specs.append({**helm, "version": svc.get("version")})
    for extra in svc.get("helm_images") or []:
        specs.append({**extra, "version": extra.get("version", svc.get("version"))})
    return specs


def compute_helm_changes(platform: dict) -> list[Change]:
    from io import StringIO

    # Regroupées par fichier : plusieurs images (backend/frontend) peuvent
    # cibler le même fichier de values, il faut les appliquer en une seule
    # passe de chargement/écriture pour ne pas s'écraser l'une l'autre.
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
            changes.append(Change(target, text, f"{spec['file']} (image brute)"))
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
    """Fusionne toutes les variables de port déclarées dans platform.yaml en un
    seul dict {NOM_VARIABLE: valeur}, dans l'ordre de lecture (services, puis
    connecteurs, puis divers) pour un diff stable et lisible."""
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
            f"'{path}' ne contient pas les marqueurs {PORTS_BEGIN} / {PORTS_END} — "
            "ajoutez-les une fois manuellement autour du bloc de ports existant."
        )

    return [Change(path, new_text, ".env.example (bloc de ports)")]


def compute_test_defaults_changes(platform: dict) -> list[Change]:
    path = REPO_ROOT / "tests" / "integration" / "_platform_defaults.py"
    port_map = all_ports(platform)

    body = [
        '"""',
        "Fichier généré par scripts/sync_platform.py à partir de platform.yaml.",
        "Ne PAS éditer à la main : les valeurs par défaut de tests/integration/conftest.py",
        "doivent rester alignées avec les ports par défaut de docker-compose (étude 4.6) —",
        "c'est précisément ce que ce fichier garantit en étant généré depuis la même",
        "source que docker-compose/.env.example.",
        '"""',
        "",
        "DEFAULT_PORTS = {",
    ]
    for key in sorted(port_map):
        body.append(f'    "{key}": {port_map[key]!r},')
    body.append("}")
    body.append("")

    content = "\n".join(body)
    return [Change(path, content, "tests/integration/_platform_defaults.py (généré)")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="n'écrit rien, échoue si des fichiers divergeraient de platform.yaml",
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
            print("Dérive détectée entre platform.yaml et les fichiers suivants :", file=sys.stderr)
            for c in dirty:
                print(f"  - {c.description}", file=sys.stderr)
            print(
                "\nLancez `python3 scripts/sync_platform.py` puis committez le résultat.",
                file=sys.stderr,
            )
            return 1
        print("OK : aucun fichier ne diverge de platform.yaml.")
        return 0

    for c in dirty:
        c.apply()
        print(f"mis à jour : {c.description}")
    if not dirty:
        print("Rien à faire : tous les fichiers sont déjà alignés sur platform.yaml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
