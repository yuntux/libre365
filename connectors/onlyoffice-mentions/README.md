# onlyoffice-mentions

Handler for OnlyOffice Document Server mention events (study 2.7). Implements the
two extension points exposed by OnlyOffice for comments:

- **`onRequestUsers`** (`GET /onlyoffice/request-users`): list of users suggested
  when typing `@`/`+`, querying the directory via the Keycloak Admin API (simple stub).
- **`onRequestSendNotify`** (`POST /onlyoffice/request-send-notify`): triggered when
  a comment mentioning someone is submitted; this connector relays each mention to
  `notification-hub` (`POST /webhooks/onlyoffice-mention`, see `connectors/notification-hub`)
  with the action link natively provided by OnlyOffice.

This connector is the bridge between OnlyOffice and the rest of the notification
infrastructure (study 2.1 line 487: "this connector joins the list of those to be
developed in 2.1").

## OnlyOffice-side configuration

In the editor configuration (Document Server), point to:
- `editorConfig.customization.chat: false` (study 2.6, disabling the internal chat)
- `editorConfig.plugins` / mention webhooks to this service: `onRequestUsers` ->
  `GET /onlyoffice/request-users`, `onRequestSendNotify` -> `POST /onlyoffice/request-send-notify`.

## Endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/onlyoffice/request-users` | List of users for `@` autocompletion |
| POST | `/onlyoffice/request-send-notify` | Relays a mention to notification-hub |
| GET | `/healthz` | Health probe |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `4004` | HTTP listen port |
| `KEYCLOAK_BASE_URL` | `https://auth.example.org` | Keycloak server URL |
| `KEYCLOAK_REALM` | `libre365` | Keycloak realm |
| `KEYCLOAK_ADMIN_TOKEN` | (empty) | Service token (Admin API, `view-users` role) |
| `NOTIFICATION_HUB_URL` | `http://notification-hub:4001` | Notification center URL |

## Development

```bash
npm install
npm test
npm run build
npm start
```
