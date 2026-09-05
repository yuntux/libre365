# presence-aggregator

Agregateur de presence unifiee (etude 2.8). Consulte trois sources disjointes et republie
un statut consolide par utilisateur pour le bandeau du portail applicatif (etude 2.3) :

- **Matrix** : `m.presence` (online/unavailable/offline) via l'API cliente/serveur.
- **Grommunio/EWS** : etat "en reunion" derive de `GetUserAvailability` (SOAP), stub
  d'appel structure et commente dans `src/sources/grommunio-ews.ts`.
- **Visio/LiveKit** : liste des participants connectes a une room, via
  `livekit-server-sdk` (`RoomServiceClient.listRooms`/`listParticipants`).

## Regle de consolidation

`src/consolidate.ts` est une fonction pure, sans dependance reseau, donc testable
unitairement sans mock HTTP : priorite **en reunion > en ligne Matrix > absent**
(etude 2.8 ligne 504).

## Endpoints

| Methode | Route | Description |
|---|---|---|
| GET | `/presence/:userId` | Statut consolide instantane pour un utilisateur |
| GET | `/presence/stream?userIds=a,b,c` | Flux SSE, rafraichi toutes les `PRESENCE_STREAM_INTERVAL_MS` |
| GET | `/healthz` | Sonde de sante |

## Variables d'environnement

| Variable | Defaut | Description |
|---|---|---|
| `PORT` | `4003` | Port d'ecoute HTTP |
| `PRESENCE_STREAM_INTERVAL_MS` | `5000` | Intervalle de rafraichissement SSE |
| `MATRIX_BASE_URL` | `https://matrix.example.org` | URL du homeserver Matrix |
| `MATRIX_SERVICE_TOKEN` | (vide) | Token de service Matrix pour lire la presence de tout utilisateur |
| `GROMMUNIO_EWS_URL` | `https://mail.example.org/EWS/Exchange.asmx` | Endpoint SOAP EWS |
| `LIVEKIT_URL` | `https://visio.example.org` | URL du serveur LiveKit |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | (vide) | Identifiants API serveur LiveKit |

## Developpement

```bash
npm install
npm test        # vitest sur src/consolidate.ts, sans reseau
npm run build
npm start
```
