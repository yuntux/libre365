# CI/CD — study chapter 5 ("Cross-cutting operations and steering")

This document explains how the workflows under `.github/workflows/` and the
`renovate.json` configuration materialize chapter 5 of
[`office365-exit-study.md`](../office365-exit-study.md) (lines
769-802), and what would remain to be built for a fully automated end-to-end
pipeline targeting Kubernetes.

## Correspondence table

| Study need (chapter 5) | Section | Implementation in this repository |
|---|---|---|
| Cross-cutting long-term monitoring of the stack (5.1) | 5.1 (L.771-773) | All the workflows below + `docs/mapping.md` |
| Automated, regular scanning of container images (Trivy/Grype) | 5.2 (L.777) | `.github/workflows/cve-scan.yml` — Trivy, daily + on push |
| Subscription to each building block's official security feeds | 5.2 (L.778) | **Not covered by GitHub Actions** — still needs tooling, see "What's missing" below |
| Centralized alerting (scan + vendor monitoring) | 5.2 (L.779) | Partial: `cve-scan.yml` publishes SARIF to GitHub's **Security** tab (Code Scanning), which serves as a dashboard for the scan side only — no merging with vendor monitoring (not automated, see above) |
| Automated tracking of new releases (images + IaC dependencies), Renovate/Dependabot-style | 5.3 (L.783) | `renovate.json` — Docker images (`docker-compose/`, `infra/k8s/helm-values/`), Terraform providers (`infra/terraform/`), connector npm dependencies (`connectors/*/`) |
| New version detected → triggers the cycle rather than being applied directly | 5.3 (L.784) | `renovate.json`: no `automerge` rule on application version updates — every detection produces a PR to review, not a direct deployment |
| Ephemeral staging environment automatically created from IaC | 5.4.1 (L.789) | `.github/workflows/ephemeral-staging.yml` — **simplified**: starts `docker-compose` rather than a Kubernetes environment provisioned by `infra/terraform` + `infra/k8s` (see the justification in the comment at the top of the file and the "What's missing" section) |
| Representative test dataset (no production data) | 5.4.2 (L.790) | Default `docker-compose/` configuration (`.env.example`), no connection to production data |
| CI/CD pipeline orchestrating the cycle without manual intervention up to validation | 5.4.3 (L.791) | `ephemeral-staging.yml` chains startup → health wait → test replay → report publication without manual intervention; only the workflow's **trigger** is manual for now (`workflow_dispatch`), see "What's missing" |
| Library of automated test scenarios (mail, files, co-editing, video/chat, tasks, SSO) | 5.5 (L.795) | `tests/integration/` (`pytest` suite, `smoke` marker) — maintained separately, referenced without being duplicated by `ephemeral-staging.yml` |
| Automatic replay against ephemeral staging on every new version detected | 5.5 (L.796) | `ephemeral-staging.yml` runs `pytest -m smoke` against the started environment; automatic triggering from a Renovate PR is not wired up (see "What's missing") |
| Results report driving the promotion decision | 5.5 (L.797) | `ephemeral-staging.yml` publishes `tests/integration/report.html` (pytest-html) as a GitHub Actions artifact and fails the workflow if a `smoke` scenario fails |
| Single dashboard (CVE, versions, staging results, production monitoring) | 5.6 (L.801-802) | **Not covered** — GitHub's Security tab only covers the CVE scan side; no consolidated dashboard for versions/staging/monitoring, see "What's missing" |

## Files created

- `.github/workflows/lint-and-test.yml` — continuous quality baseline (Terraform, Ansible, Helm values, Node connectors, docker-compose), triggered on every PR/push. This isn't directly a numbered requirement of chapter 5, but it's the foundation that makes the rest of the cycle reliable (a broken image or manifest must not reach ephemeral staging).
- `.github/workflows/cve-scan.yml` — study 5.2.
- `renovate.json` — study 5.3.
- `.github/workflows/ephemeral-staging.yml` — study 5.4 and 5.5.
- `docs/ci-cd.md` — this document.

## What's missing for full end-to-end Kubernetes automation

The study describes a fully automated cycle:

```
Renovate detects a new version
        ↓
Ephemeral staging provisioned via IaC (Terraform + Ansible + Helm on Kubernetes)
        ↓
Critical test scenarios replayed
        ↓
Results report → promotion decision (manual or automated depending on criticality)
        ↓
Staging environment destroyed
```

What is delivered here stops at a simplified version, testable in GitHub
Actions CI, on `docker-compose` rather than Kubernetes. Still to be built, in
dependency order:

1. **Automatic triggering from Renovate** — today
   `ephemeral-staging.yml` only launches via manual `workflow_dispatch`. To
   close the loop from 5.3 to 5.4 automatically, we'd need either a
   `pull_request` workflow filtered on PRs opened by Renovate
   (`github.actor == 'renovate[bot]'`), or an action in the Renovate
   configuration itself (`postUpgradeTasks` or an external hook) that calls
   this workflow with the affected building block and version as
   parameters.

2. **Real Kubernetes provisioning of ephemeral staging** — replacing the
   `docker compose up -d` startup with:
   - a `terraform apply` (or OpenTofu) targeting a dedicated
     staging namespace/cluster, from `infra/terraform/`;
   - running the Ansible playbooks from `infra/ansible/` for application
     configuration (Keycloak realms, Matrix domain, etc.) on this
     environment;
   - a Helm deployment of the `infra/k8s/helm-values/` values with the
     targeted building block's image overridden to the new version, the
     other building blocks staying at their current versions (an explicit
     requirement of 5.4.1);
   - a destruction step (`terraform destroy` / namespace deletion) that
     guarantees the environment is genuinely ephemeral, even if prior steps
     fail.

   This assumes network access from GitHub Actions runners to the target
   infrastructure (self-hosted runners, or a VPN/peering link to the
   Proxmox/Kubernetes environment described in chapter 4), which is beyond
   the reach of a standard hosted GitHub runner.

3. **Representative test dataset at the Kubernetes level** — the
   docker-compose version relies on the default dev configuration; a real
   Kubernetes staging setup would need a dedicated, replayable test dataset
   (anonymized dump or application fixtures), to be loaded after the Helm
   deployment and before replaying the scenarios.

4. **Promotion decision** — the study calls for a promotion that is "manual
   or automated depending on the criticality of the building block
   concerned" (5.5, L.797). Today, a failed `smoke` scenario simply fails
   the workflow (blocking, with no notion of criticality). A real promotion
   mechanism would require: (a) a per-building-block criticality
   classification, (b) for non-critical building blocks, an automatic
   trigger of the production deployment (or the automerge of the
   corresponding Renovate PR) if the report is green, (c) for critical
   building blocks, an explicit human approval step (e.g. a protected
   GitHub environment with required reviewers) before any production
   deployment.

5. **Single cross-cutting dashboard (5.6)** — consolidating in one place:
   CVE alerts (today only in GitHub's Security tab), current vs. available
   versions per building block (scattered between the Renovate dashboard and
   the values files), the results of the latest staging runs (the
   `rapport-recette-*` artifacts from `ephemeral-staging.yml`, not
   aggregated), and production technical monitoring (out of scope for this
   CI repository). This requires a dedicated steering tool (e.g. an internal
   dashboard fed by the GitHub API + a monitoring tool such as
   Prometheus/Grafana), distinct from the chapter 2 user notification center
   (5.6, L.802).

6. **Monitoring vendor security feeds (5.2, L.778)** — subscribing to the
   security mailing lists / RSS feeds / GitHub Security Advisories of each
   building block (Grommunio, Synapse/Element, Seafile, OnlyOffice, Vikunja,
   Keycloak, Caddy), independent of the Trivy scan. Not implemented: a
   simple first step would be to enable GitHub Security Advisories on the
   tracked upstream repositories (when they are GitHub repositories) and
   aggregate them into the same dashboard as point 5 above.
