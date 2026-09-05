# CI/CD — chapitre 5 de l'étude ("Exploitation et pilotage transverse")

Ce document explique comment les workflows sous `.github/workflows/` et la
configuration `renovate.json` matérialisent le chapitre 5 de
[`sortie-office365-etude.md`](../sortie-office365-etude.md) (lignes
769-802), et ce qui resterait à construire pour une automatisation complète
de bout en bout ciblant Kubernetes.

## Table de correspondance

| Besoin de l'étude (chapitre 5) | Section | Réalisation dans ce dépôt |
|---|---|---|
| Suivi transverse de la stack dans la durée (5.1) | 5.1 (L.771-773) | Ensemble des workflows ci-dessous + `docs/mapping.md` |
| Scan automatisé et régulier des images conteneurisées (Trivy/Grype) | 5.2 (L.777) | `.github/workflows/cve-scan.yml` — Trivy, quotidien + sur push |
| Abonnement aux flux de sécurité officiels de chaque brique | 5.2 (L.778) | **Non couvert par GitHub Actions** — reste à outiller, voir "Ce qui manque" ci-dessous |
| Centralisation des alertes (scan + veille éditeurs) | 5.2 (L.779) | Partiellement : `cve-scan.yml` publie en SARIF vers l'onglet **Security** de GitHub (Code Scanning), qui sert de tableau de bord pour le volet scan uniquement — pas de fusion avec la veille éditeurs (non automatisée, cf. ci-dessus) |
| Suivi automatisé des nouvelles releases (images + dépendances IaC), type Renovate/Dependabot | 5.3 (L.783) | `renovate.json` — images Docker (`docker-compose/`, `infra/k8s/helm-values/`), providers Terraform (`infra/terraform/`), dépendances npm des connecteurs (`connectors/*/`) |
| Nouvelle version détectée → déclenche le cycle plutôt qu'appliquée directement | 5.3 (L.784) | `renovate.json` : aucune règle `automerge` sur les mises à jour de versions applicatives — chaque détection produit une PR à valider, pas un déploiement direct |
| Environnement de recette éphémère créé automatiquement depuis l'IaC | 5.4.1 (L.789) | `.github/workflows/ephemeral-staging.yml` — **simplifié** : démarre `docker-compose` plutôt qu'un environnement Kubernetes provisionné par `infra/terraform` + `infra/k8s` (voir justification dans le commentaire en tête du fichier et section "Ce qui manque") |
| Jeu de données de test représentatif (pas de données de prod) | 5.4.2 (L.790) | Configuration par défaut de `docker-compose/` (`.env.example`), pas de branchement sur des données de production |
| Pipeline CI/CD orchestrant le cycle sans intervention manuelle jusqu'à la validation | 5.4.3 (L.791) | `ephemeral-staging.yml` enchaîne démarrage → attente de santé → rejeu des tests → publication du rapport sans intervention manuelle ; seul le **déclenchement** du workflow est manuel pour l'instant (`workflow_dispatch`), voir "Ce qui manque" |
| Bibliothèque de scénarios de test automatisés (mail, fichiers, co-édition, visio/tchat, tâches, SSO) | 5.5 (L.795) | `tests/integration/` (suite `pytest`, marqueur `smoke`) — maintenue par ailleurs, référencée sans être dupliquée par `ephemeral-staging.yml` |
| Rejeu automatique sur la recette éphémère à chaque nouvelle version détectée | 5.5 (L.796) | `ephemeral-staging.yml` exécute `pytest -m smoke` contre l'environnement démarré ; le déclenchement automatique depuis une PR Renovate n'est pas câblé (cf. "Ce qui manque") |
| Rapport de résultats conditionnant la décision de promotion | 5.5 (L.797) | `ephemeral-staging.yml` publie `tests/integration/report.html` (pytest-html) en artefact GitHub Actions et fait échouer le workflow si un scénario `smoke` échoue |
| Tableau de bord unique (CVE, versions, résultats recette, supervision prod) | 5.6 (L.801-802) | **Non couvert** — l'onglet Security de GitHub ne couvre que le volet CVE scan ; pas de tableau consolidé versions/recette/supervision, cf. "Ce qui manque" |

## Fichiers créés

- `.github/workflows/lint-and-test.yml` — socle de qualité continue (Terraform, Ansible, Helm values, connecteurs Node, docker-compose), déclenché sur chaque PR/push. Ce n'est pas directement une exigence numérotée du chapitre 5, mais la fondation qui rend le reste du cycle fiable (une image ou un manifest cassé ne doit pas atteindre la recette éphémère).
- `.github/workflows/cve-scan.yml` — étude 5.2.
- `renovate.json` — étude 5.3.
- `.github/workflows/ephemeral-staging.yml` — étude 5.4 et 5.5.
- `docs/ci-cd.md` — ce document.

## Ce qui manque pour une automatisation Kubernetes de bout en bout

L'étude décrit un cycle entièrement automatisé :

```
Renovate détecte une nouvelle version
        ↓
Recette éphémère provisionnée via l'IaC (Terraform + Ansible + Helm sur Kubernetes)
        ↓
Rejeu des scénarios de test critiques
        ↓
Rapport de résultats → décision de promotion (manuelle ou automatisée selon criticité)
        ↓
Destruction de l'environnement de recette
```

Ce qui est livré ici s'arrête à une version simplifiée et testable en CI
GitHub Actions, sur `docker-compose` plutôt que Kubernetes. Restent à
construire, dans l'ordre de dépendance :

1. **Déclenchement automatique depuis Renovate** — aujourd'hui
   `ephemeral-staging.yml` se lance uniquement via `workflow_dispatch`
   manuel. Pour boucler 5.3→5.4 automatiquement, il faudrait soit un
   workflow `pull_request` filtré sur les PR ouvertes par Renovate
   (`github.actor == 'renovate[bot]'`), soit une action dans la config
   Renovate elle-même (`postUpgradeTasks` ou un hook externe) qui appelle ce
   workflow avec la brique et la version concernées en paramètres.

2. **Provisionnement Kubernetes réel de la recette éphémère** — remplacer le
   démarrage `docker compose up -d` par :
   - un `terraform apply` (ou OpenTofu) ciblant un espace de noms/cluster de
     recette dédié, à partir de `infra/terraform/` ;
   - l'exécution des playbooks Ansible de `infra/ansible/` pour la
     configuration applicative (realms Keycloak, domaine Matrix...) sur cet
     environnement ;
   - un déploiement Helm des values de `infra/k8s/helm-values/` avec l'image
     de la brique ciblée surchargée à la nouvelle version, les autres briques
     restant aux versions courantes (exigence explicite de 5.4.1) ;
   - une étape de destruction (`terraform destroy` / suppression du
     namespace) garantissant le caractère réellement éphémère de
     l'environnement, y compris en cas d'échec des étapes précédentes.

   Ceci suppose un accès réseau depuis les runners GitHub Actions vers
   l'infrastructure cible (self-hosted runners ou VPN/peering vers
   l'environnement Proxmox/Kubernetes décrit au chapitre 4), hors de portée
   d'un runner GitHub hébergé standard.

3. **Jeu de données de test représentatif au niveau Kubernetes** — la
   version docker-compose s'appuie sur la configuration de dev par défaut ;
   une vraie recette Kubernetes nécessiterait un jeu de données de test
   dédié et rejouable (dump anonymisé ou fixtures applicatives), à charger
   après le déploiement Helm et avant le rejeu des scénarios.

4. **Décision de promotion** — l'étude prévoit une promotion "manuelle ou
   automatisée selon la criticité de la brique concernée" (5.5, L.797).
   Aujourd'hui, un scénario `smoke` en échec fait simplement échouer le
   workflow (bloquant, sans notion de criticité). Un mécanisme de promotion
   réel demanderait : (a) une classification de criticité par brique, (b)
   pour les briques non critiques, un déclenchement automatique du
   déploiement en production (ou de l'automerge de la PR Renovate
   correspondante) si le rapport est au vert, (c) pour les briques
   critiques, une étape d'approbation humaine explicite (environnement
   GitHub protégé avec reviewers requis, par exemple) avant tout déploiement
   en production.

5. **Tableau de bord transverse unique (5.6)** — consolider dans un même
   endroit : les alertes CVE (aujourd'hui dans l'onglet Security de GitHub
   uniquement), les versions courantes vs. disponibles par brique (dispersées
   entre le dashboard Renovate et les fichiers de values), les résultats des
   derniers passages en recette (artefacts `rapport-recette-*` de
   `ephemeral-staging.yml`, non agrégés), et la supervision technique de
   production (hors périmètre de ce dépôt CI). Ceci nécessite un outil de
   pilotage dédié (ex. un tableau de bord interne alimenté par l'API GitHub
   + un outil de supervision comme Prometheus/Grafana), distinct du centre
   de notifications utilisateur du chapitre 2 (5.6, L.802).

6. **Veille sur les flux de sécurité éditeurs (5.2, L.778)** — abonnement aux
   listes de diffusion sécurité / flux RSS / GitHub Security Advisories de
   chaque brique (Grommunio, Synapse/Element, Seafile, OnlyOffice, Vikunja,
   Keycloak, Caddy), indépendant du scan Trivy. Non implémenté : une
   première étape simple serait d'activer les GitHub Security Advisories
   côté dépôts amont suivis (quand ce sont des dépôts GitHub) et de les
   agréger vers le même tableau de bord que le point 5 ci-dessus.
