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

## Une seule source pour les versions et les ports : `platform.yaml`

L'environnement de développement (`docker-compose/`) et la cible de
production (`infra/k8s/`) décrivent les mêmes briques par deux mécanismes
différents (image Docker Hub vs. chart Helm) : sans précaution, leurs tags de
version et leurs ports dérivent l'un de l'autre silencieusement — c'est
d'ailleurs déjà arrivé une fois dans ce dépôt (les ports par défaut de
`tests/integration/` avaient divergé de ceux de `docker-compose/`).

[`platform.yaml`](./platform.yaml) est désormais la seule source autorisée
pour ces valeurs. Il alimente :
- les tags d'image dans `docker-compose/docker-compose.yml` et les
  `FROM node:...` des `connectors/*/Dockerfile` ;
- `image.repository`/`image.tag` dans `infra/k8s/helm-values/*.yaml` (et la
  ligne `image:` brute de `infra/k8s/manifests/gokapi.yaml`) ;
- le bloc de ports généré dans `docker-compose/.env.example` ;
- les ports par défaut de `tests/integration/conftest.py`, via le fichier
  généré `tests/integration/_platform_defaults.py`.

Workflow : éditer `platform.yaml`, puis :

```bash
pip install -r scripts/requirements.txt
python3 scripts/sync_platform.py          # applique les changements
python3 scripts/sync_platform.py --check  # utilisé par la CI : échoue en cas de dérive
```

Ne jamais modifier un tag ou un port directement dans un fichier généré/patché
— il sera écrasé (ou, en CI, la dérive sera détectée et bloquera la pull
request) à la prochaine synchronisation.

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
