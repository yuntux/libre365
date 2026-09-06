# Ansible — application configuration

Carries the application configuration of the components provisioned by
Terraform (`infra/terraform/`), in line with the split adopted in chapter 4.5
of the study: *"Infrastructure provisioning [...] Terraform; application
configuration [...] automated via playbooks (Ansible)"*.

## Prerequisites

```bash
pip install ansible
ansible-galaxy collection install community.general
```

The `keycloak-realm.yml`, `seafile.yml` and `onlyoffice.yml`
playbooks run locally (`connection: local`) because they drive HTTP APIs
(Keycloak Admin API, `kubectl`) rather than remote hosts over SSH —
`kubectl` must therefore be configured with a context pointing to the target
Kubernetes cluster before running them. Only `grommunio.yml` connects over
SSH to a real VM (the appliance VM provisioned by Terraform).

## Inventory

```bash
cp inventory/hosts.ini.example inventory/hosts.ini
# or, once the Terraform infrastructure has been applied:
./scripts/render-inventory-from-terraform.sh
```

## Running the full configuration

```bash
ansible-playbook -i inventory/hosts.ini site.yml
```

Or component by component:

```bash
ansible-playbook -i inventory/hosts.ini playbooks/os-hardening.yml
ansible-playbook -i inventory/hosts.ini playbooks/openbao-config.yml
ansible-playbook -i inventory/hosts.ini playbooks/keycloak-realm.yml
ansible-playbook -i inventory/hosts.ini playbooks/grommunio.yml
ansible-playbook -i inventory/hosts.ini playbooks/grommunio-cert.yml
ansible-playbook -i inventory/hosts.ini playbooks/seafile.yml
ansible-playbook -i inventory/hosts.ini playbooks/onlyoffice.yml
```

## Playbooks

| Playbook | Content | Study reference |
|---|---|---|
| `playbooks/os-hardening.yml` | fail2ban (`sshd` jail) + SSH password-auth/root-login hardening on every real VM (via the `os_hardening` role) — **read its role's README before the first run** | not a numbered requirement — closes a gap noted during review |
| `playbooks/openbao-config.yml` | OpenBao Kubernetes auth method + `external-secrets` policy/role for External Secrets Operator (via the `openbao_config` role) — **read its role's README for prerequisites (OpenBao must already be initialized/unsealed)** | 4.5 |
| `playbooks/keycloak-realm.yml` | Main realm, TOTP + WebAuthn/FIDO2, per-component OIDC clients (via the `keycloak_realm` role) | 1.7 |
| `playbooks/grommunio.yml` | `GAL_ENABLED`/`GAL_CACHE_TTL`, disabling the web admin, EWS/EAS/MAPI enabled | 1.1, 2.13 |
| `playbooks/grommunio-cert.yml` | Fully automates Grommunio's Let's Encrypt certificate — issuance (idempotent) and renewal (`certbot.timer`) via the `grommunio_cert` role, no manual step | not a numbered requirement — closes a gap noted during review |
| `playbooks/seafile.yml` | `SHARE_LINK_LOGIN_REQUIRED`, per-role share link generation permission, OnlyOffice connector | 2.11, 1.5 |
| `playbooks/onlyoffice.yml` | `document.permissions.chat: false` by default | 2.6 |

Matrix/Synapse's OIDC config has no dedicated playbook: it's entirely
chart-native (`infra/k8s/helm-values/synapse.yaml`'s `synapse.oidc` block)
— a separate Ansible-rendered ConfigMap used to duplicate this with a
mismatched `client_id`, found and removed during a review pass (see
`docs/oidc.md`).

## OIDC / SSO (study 1.7)

See `docs/oidc.md` for the full per-component breakdown of which
components have a Keycloak client, why the ones that don't are excluded
deliberately, and `scripts/sync_platform.py`'s `check_oidc_coverage()` (run
as part of `--check`) which now enforces in CI that every
`keycloak_oidc_clients` entry here has a matching `client_id` reference and
`ExternalSecret` on the application side — the exact kind of gap a manual
review previously had to catch by hand.

## Domain configuration

Every domain variable used across these playbooks and roles
(`libre365_domain`, `onlyoffice_domain`, `seafile_domain`,
`vikunja_domain`, `gokapi_domain`, `novu_domain`, `peertube_domain`,
`grommunio_domain`, `matrix_domain`, `keycloak_base_url`) is defined
exactly once, in `group_vars/all.yml`, which reads them live from
`../../platform.yaml`'s `domains` section — the same single source of
truth `scripts/sync_platform.py` patches into `infra/k8s/`. Never
hardcode a subdomain in a playbook, a role default, or a template:
add it to `platform.yaml` and reference the corresponding
`group_vars/all.yml` variable instead, or Ansible's configuration will
silently drift from the Caddy/Ingress/DNS configuration actually
serving the domain (this happened once — see git history on
`group_vars/all.yml` — and produced a broken Keycloak OIDC
`redirect_uri` for OnlyOffice, Vikunja, Gokapi and PeerTube).

**Every playbook must declare `vars_files: [../group_vars/all.yml]`
explicitly.** Ansible's implicit directory-based `group_vars/`
auto-loading does not trigger for this repository's layout, in either
invocation pattern (a single `playbooks/*.yml` run directly, or via
`site.yml`'s `import_playbook`) — verified empirically. Omitting the
explicit `vars_files:` from a new playbook will leave every domain
variable undefined at runtime rather than raising an error at
`--syntax-check` time, so this is easy to miss.

## Roles

`roles/keycloak_realm/` is the reference role: the
`tasks/`/`defaults/`/`templates/`/`handlers/` structure to reuse for any
future role extracted from these playbooks (see its own `README.md`).
`roles/os_hardening/` and `roles/openbao_config/` follow the same
structure.

## Secrets management (study 4.5): OpenBao + External Secrets Operator

`playbooks/openbao-config.yml` wires up the OpenBao vault deployed by
`../k8s/helm-values/openbao.yaml` so External Secrets Operator
(`../k8s/helm-values/external-secrets.yaml`) can populate the real
Kubernetes Secrets referenced by every `existingSecret:`/`secretKeyRef:`
across `../k8s/helm-values/*.yaml` (see
`../k8s/manifests/external-secrets.yaml`) — rather than a human creating
each one by hand. See `roles/openbao_config/README.md` for the full
prerequisites (OpenBao must already be initialized and unsealed — a
manual, security-sensitive step deliberately not automated anywhere in
this repository) and `../k8s/helm-values/README.md`'s own section on this
for the Kubernetes-side half of the picture.

## Secrets

No secret is committed to this repository. Required passwords/tokens
(`vault_keycloak_admin_password`, etc.) must be supplied via Ansible Vault or
`--extra-vars`, fed from the firm's secrets vault (study 4.5):

```bash
ansible-playbook -i inventory/hosts.ini site.yml \
  --extra-vars "@secrets/vault.yml" --ask-vault-pass
```

The `secrets/` directory (created at runtime by the `keycloak_realm` role)
and `rendered/` (configuration files generated from templates) are excluded
from version control (`.gitignore`).
