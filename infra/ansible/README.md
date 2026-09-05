# Ansible — configuration applicative

Porte la configuration applicative des briques provisionnées par Terraform
(`infra/terraform/`), conformément au partage retenu au chapitre 4.5 de
l'étude : *"Provisionnement de l'infrastructure [...] Terraform ; configuration
applicative [...] automatisée via des playbooks (Ansible)"*.

## Prérequis

```bash
pip install ansible
ansible-galaxy collection install community.general
```

Les playbooks `keycloak-realm.yml`, `matrix.yml`, `seafile.yml` et
`onlyoffice.yml` s'exécutent en local (`connection: local`) car ils pilotent
des API HTTP (Keycloak Admin API, `kubectl`) plutôt que des hôtes distants en
SSH — `kubectl` doit donc être configuré avec un contexte pointant vers le
cluster Kubernetes cible avant de les lancer. Seul `grommunio.yml` se connecte
en SSH à une VM réelle (la VM appliance provisionnée par Terraform).

## Inventaire

```bash
cp inventory/hosts.ini.example inventory/hosts.ini
# ou, une fois l'infrastructure Terraform appliquée :
./scripts/render-inventory-from-terraform.sh
```

## Lancer la configuration complète

```bash
ansible-playbook -i inventory/hosts.ini site.yml
```

Ou brique par brique :

```bash
ansible-playbook -i inventory/hosts.ini playbooks/keycloak-realm.yml
ansible-playbook -i inventory/hosts.ini playbooks/grommunio.yml
ansible-playbook -i inventory/hosts.ini playbooks/matrix.yml
ansible-playbook -i inventory/hosts.ini playbooks/seafile.yml
ansible-playbook -i inventory/hosts.ini playbooks/onlyoffice.yml
```

## Playbooks

| Playbook | Contenu | Référence étude |
|---|---|---|
| `playbooks/keycloak-realm.yml` | Realm principal, TOTP + WebAuthn/FIDO2, clients OIDC par brique (via le rôle `keycloak_realm`) | 1.7 |
| `playbooks/grommunio.yml` | `GAL_ENABLED`/`GAL_CACHE_TTL`, désactivation admin web, EWS/EAS/MAPI actifs | 1.1, 2.13 |
| `playbooks/matrix.yml` | `server_name`, provider OIDC Synapse vers Keycloak | 1.2, 1.7 |
| `playbooks/seafile.yml` | `SHARE_LINK_LOGIN_REQUIRED`, permission de génération de lien par rôle, connecteur OnlyOffice | 2.11, 1.5 |
| `playbooks/onlyoffice.yml` | `document.permissions.chat: false` par défaut | 2.6 |

## Rôles

`roles/keycloak_realm/` est le rôle de référence : structure
`tasks/`/`defaults/`/`templates/`/`handlers/` à reprendre pour tout futur
rôle extrait de ces playbooks (voir son propre `README.md`).

## Secrets

Aucun secret n'est committé dans ce dépôt. Les mots de passe/jetons
nécessaires (`vault_keycloak_admin_password`, etc.) sont à fournir via
Ansible Vault ou `--extra-vars`, alimentés depuis le coffre-fort de secrets du
cabinet (étude 4.5) :

```bash
ansible-playbook -i inventory/hosts.ini site.yml \
  --extra-vars "@secrets/vault.yml" --ask-vault-pass
```

Le répertoire `secrets/` (créé à l'exécution par le rôle `keycloak_realm`) et
`rendered/` (fichiers de configuration générés depuis les templates) sont
exclus du contrôle de version (`.gitignore`).
