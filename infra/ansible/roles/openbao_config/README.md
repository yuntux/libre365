# `openbao_config` role

Bootstraps OpenBao's Kubernetes auth method so External Secrets Operator
(ESO) can authenticate to it without a long-lived static credential (study
4.5) — see `../../k8s/manifests/external-secrets-store.yaml` (the
`ClusterSecretStore` this role's configuration is for) and
`../../k8s/manifests/external-secrets.yaml` (the `ExternalSecret` resources
that actually pull values once this is wired up).

## Prerequisites

- OpenBao (`../../k8s/helm-values/openbao.yaml`) already deployed,
  **initialized and unsealed** — a manual, security-sensitive operation
  (key-shares handling) deliberately NOT automated by this role or
  anything else in this repository. See OpenBao's own documentation for
  `bao operator init` / `bao operator unseal`.
- External Secrets Operator (`../../k8s/helm-values/external-secrets.yaml`)
  and its `external-secrets` ServiceAccount
  (`../../k8s/manifests/external-secrets-store.yaml`) already applied.
- `kubectl`'s current context pointing at the target cluster.
- A root or sufficiently-privileged OpenBao token supplied as
  `openbao_root_token` via `--extra-vars` or a vault file — **never in
  plaintext** (same convention as every other sensitive variable in this
  directory, see `../../group_vars/all.yml`).

## What it does

1. Creates a long-lived `kubernetes.io/service-account-token` Secret for
   the `external-secrets` ServiceAccount (Kubernetes 1.24+ no longer
   auto-generates one — see the task's own comment).
2. Enables OpenBao's `kubernetes` auth method (skipped if already enabled).
3. Configures it against this cluster's API server, using that
   ServiceAccount token as the "token reviewer" credential OpenBao uses to
   validate future login attempts.
4. Writes a read-only policy scoped to `secret/data/libre365/*` (nothing
   outside this stack's own paths).
5. Creates a `kubernetes` auth role binding the `external-secrets`
   ServiceAccount (in the `libre365` namespace) to that policy.

## ⚠️ Verify before running

This role calls OpenBao's HTTP API directly (`ansible.builtin.uri`) rather
than a Vault-specific Ansible collection module, precisely because that API
shape is very stable and well-documented — but it was still authored in a
sandboxed environment with no live OpenBao/Kubernetes cluster to actually
run it against. Test it against a real (or throwaway) OpenBao instance
before relying on it — the equivalent, fully manual sequence is
[OpenBao's own Kubernetes auth method
documentation](https://openbao.org/docs/auth/kubernetes/) (`bao auth
enable kubernetes`, `bao write auth/kubernetes/config ...`, `bao policy
write ...`, `bao write auth/kubernetes/role/...`), which this role
automates via direct API calls with equivalent parameters.

## Not covered by this role

- **OpenBao's own initialization/unseal** — see "Prerequisites" above.
- **Writing the actual secret values** into OpenBao's KV store (the
  `libre365/<component>` paths referenced by
  `../../k8s/manifests/external-secrets.yaml`) — a separate, per-secret
  operational task, not something to template/automate generically here
  (each is a distinct, sensitive value with its own provenance: a
  generated password, an API key from a third-party provider, etc.).
