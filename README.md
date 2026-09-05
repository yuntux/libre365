# open365

Sortie d'Office 365 vers une stack libre — implémentation de l'étude
[`sortie-office365-etude.md`](./sortie-office365-etude.md).

Ce dépôt matérialise l'architecture décrite dans l'étude : infrastructure as
code, briques applicatives, connecteurs d'intégration développés en propre,
et suite de tests d'intégration pérenne. Il est organisé pour que chaque
répertoire de code renvoie explicitement au chapitre/section de l'étude qui
motive son existence — voir [`docs/mapping.md`](./docs/mapping.md) pour la
table de correspondance complète.

## Arborescence

```
infra/
  terraform/        IaC de l'infrastructure Proxmox (VM, réseau) — chapitre 4.2/4.5
  ansible/           Configuration applicative (realms Keycloak, domaine Matrix, GAL...) — chapitre 4.5
  k8s/
    helm-values/     Values Helm par brique conteneurisée — chapitre 4.3/4.4
    manifests/       Manifests bruts pour les briques sans chart officiel adapté
docker-compose/      Environnement dev/test à échelle réduite — chapitre 4.6
connectors/          Modules d'intégration développés en propre — chapitre 2
tests/integration/   Suite de tests d'intégration pérenne — chapitre 5.5
.github/workflows/   CI/CD : scan CVE, veille de versions, recette éphémère — chapitre 5
docs/                Documentation technique complémentaire
```

## Principe directeur

Toute l'infrastructure doit pouvoir être reconstruite depuis ce dépôt seul
(chapitre 4.1) : les paramètres de dimensionnement (répliques, ressources)
sont pilotés par variable pour couvrir la trajectoire 100 → 2000+
utilisateurs sans réécriture, jamais codés en dur.

## Démarrage rapide (environnement de développement)

```bash
cd docker-compose
cp .env.example .env
docker compose up -d
```

Voir [`docker-compose/README.md`](./docker-compose/README.md) pour le détail
des services démarrés et leurs identifiants par défaut.

## Tests d'intégration

```bash
cd tests/integration
pip install -r requirements.txt
pytest -m smoke              # scénarios critiques, contre l'environnement docker-compose
```

Voir [`tests/integration/README.md`](./tests/integration/README.md).

## Statut

Ce dépôt est un chantier actif : chaque brique/connecteur porte l'état
d'avancement réel (scaffold, fonctionnel, validé en recette) dans son propre
README plutôt que dans un statut global qui deviendrait vite obsolète. Les
points encore ouverts identifiés par l'étude (fin du document
`sortie-office365-etude.md`) restent la référence pour prioriser les
prochains chantiers.
