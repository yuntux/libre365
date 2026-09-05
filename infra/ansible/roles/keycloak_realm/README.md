# Rôle `keycloak_realm`

Crée le realm Keycloak principal du cabinet, active TOTP et WebAuthn/FIDO2
nativement (étude 1.7), et crée un client OIDC confidentiel par brique de la
stack qui supporte nativement OIDC.

Sert de **convention de référence** pour la structure des rôles suivants de ce
dépôt (`tasks/`, `defaults/`, `templates/`, `handlers/`) — les rôles à ajouter
pour les autres briques (Seafile, Vikunja, OnlyOffice, Matrix, etc., quand ils
seront extraits des playbooks en rôles dédiés) doivent reprendre cette même
structure plutôt qu'un patron ad hoc par brique.

## Variables principales (`defaults/main.yml`)

- `keycloak_realm_name`, `keycloak_realm_display_name`
- `keycloak_realm_webauthn_enabled` — active WebAuthn/passwordless dans le
  browser flow (1.7 : "à la fois comme second facteur et comme facteur
  principal sans mot de passe")
- `keycloak_oidc_clients` — liste des clients OIDC à créer (un par brique
  compatible OIDC ; Grommunio en est volontairement absent, cf. commentaire
  dans le fichier)

## Non couvert par ce rôle

- **OTP par SMS et par mail** : l'étude (1.7, lignes ~266-268) est explicite —
  ces deux canaux "ne sont pas couverts nativement par Keycloak" et
  nécessitent un SPI Keycloak custom, traité comme un chantier de
  développement à part entière, pas une option de ce rôle.
- **Haute disponibilité du cluster Keycloak** (nœuds, cache distribué) : objet
  des manifestes Helm (`infra/k8s/helm-values/keycloak.yaml`, hors périmètre
  de cette tâche), pas de ce rôle de configuration applicative.

## Secrets

Les secrets clients générés sont écrits sur le contrôleur Ansible dans
`infra/ansible/secrets/keycloak-clients/<client_id>.env` (répertoire à exclure
du contrôle de version) — à transférer vers le coffre-fort de secrets retenu
par le cabinet (étude 4.5), jamais laissés en clair dans le dépôt.
