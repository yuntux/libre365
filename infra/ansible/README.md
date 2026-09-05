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

The `keycloak-realm.yml`, `matrix.yml`, `seafile.yml` and `onlyoffice.yml`
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
ansible-playbook -i inventory/hosts.ini playbooks/keycloak-realm.yml
ansible-playbook -i inventory/hosts.ini playbooks/grommunio.yml
ansible-playbook -i inventory/hosts.ini playbooks/matrix.yml
ansible-playbook -i inventory/hosts.ini playbooks/seafile.yml
ansible-playbook -i inventory/hosts.ini playbooks/onlyoffice.yml
```

## Playbooks

| Playbook | Content | Study reference |
|---|---|---|
| `playbooks/keycloak-realm.yml` | Main realm, TOTP + WebAuthn/FIDO2, per-component OIDC clients (via the `keycloak_realm` role) | 1.7 |
| `playbooks/grommunio.yml` | `GAL_ENABLED`/`GAL_CACHE_TTL`, disabling the web admin, EWS/EAS/MAPI enabled | 1.1, 2.13 |
| `playbooks/matrix.yml` | `server_name`, Synapse OIDC provider pointing to Keycloak | 1.2, 1.7 |
| `playbooks/seafile.yml` | `SHARE_LINK_LOGIN_REQUIRED`, per-role share link generation permission, OnlyOffice connector | 2.11, 1.5 |
| `playbooks/onlyoffice.yml` | `document.permissions.chat: false` by default | 2.6 |

## Roles

`roles/keycloak_realm/` is the reference role: the
`tasks/`/`defaults/`/`templates/`/`handlers/` structure to reuse for any
future role extracted from these playbooks (see its own `README.md`).

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
