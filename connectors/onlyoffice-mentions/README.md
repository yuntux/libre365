# onlyoffice-mentions

Handler des evenements de mention OnlyOffice Document Server (etude 2.7). Implemente les
deux points d'extension exposes par OnlyOffice pour les commentaires :

- **`onRequestUsers`** (`GET /onlyoffice/request-users`) : liste des utilisateurs proposes
  a la frappe de `@`/`+`, interrogeant l'annuaire via l'API Admin Keycloak (stub simple).
- **`onRequestSendNotify`** (`POST /onlyoffice/request-send-notify`) : declenche quand un
  commentaire mentionnant quelqu'un est soumis ; ce connecteur relaie chaque mention vers
  `notification-hub` (`POST /webhooks/onlyoffice-mention`, cf. `connectors/notification-hub`)
  avec le lien d'action fourni nativement par OnlyOffice.

Ce connecteur est le pont entre OnlyOffice et le reste de l'infrastructure de notification
(etude 2.1 ligne 487 : "ce connecteur rejoint la liste de ceux a developper en 2.1").

## Configuration cote OnlyOffice

Dans la configuration de l'editeur (Document Server), pointer :
- `editorConfig.customization.chat: false` (etude 2.6, desactivation du tchat interne)
- `editorConfig.plugins` / webhook mentions vers ce service : `onRequestUsers` ->
  `GET /onlyoffice/request-users`, `onRequestSendNotify` -> `POST /onlyoffice/request-send-notify`.

## Endpoints

| Methode | Route | Description |
|---|---|---|
| GET | `/onlyoffice/request-users` | Liste des utilisateurs pour l'autocompletion `@` |
| POST | `/onlyoffice/request-send-notify` | Relais d'une mention vers notification-hub |
| GET | `/healthz` | Sonde de sante |

## Variables d'environnement

| Variable | Defaut | Description |
|---|---|---|
| `PORT` | `4004` | Port d'ecoute HTTP |
| `KEYCLOAK_BASE_URL` | `https://auth.example.org` | URL du serveur Keycloak |
| `KEYCLOAK_REALM` | `libre365` | Realm Keycloak |
| `KEYCLOAK_ADMIN_TOKEN` | (vide) | Token de service (Admin API, role `view-users`) |
| `NOTIFICATION_HUB_URL` | `http://notification-hub:4001` | URL du centre de notifications |

## Developpement

```bash
npm install
npm test
npm run build
npm start
```
