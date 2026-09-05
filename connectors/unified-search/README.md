# unified-search

Recherche unifiee par fan-out temps reel (etude 2.2). `GET /search?q=...` interroge en
parallele Matrix (`/search`), Seafile (recherche API), Vikunja (`tasks/all?s=`) et
Grommunio (IMAP SEARCH, stub structure), avec un timeout par service (2s par defaut)
qui isole un service lent sans bloquer les autres reponses.

## Point cle : relais de token, pas de re-authentification

Le token Bearer Keycloak de l'utilisateur (en-tete `Authorization` de la requete entrante)
est **relaye tel quel** a chaque service source (etude 2.2 lignes 391 et 394). Ce connecteur
ne s'authentifie jamais lui-meme a la place de l'utilisateur : chaque service source
applique ses propres permissions nativement, evitant tout risque de fuite d'ACL propre a
un index central pre-calcule (cf. discussion 2.2 dans l'etude).

## Grommunio / IMAP

Grommunio n'expose pas d'API REST de recherche generique. `src/sources/grommunio.ts`
pose la structure d'un appel IMAP SEARCH via `imapflow` (en commentaire, pret a etre
active) et documente le mecanisme d'authentification XOAUTH2 permettant de relayer le
meme token utilisateur a IMAP. L'implementation active est un stub simplifie qui simule
une latence reseau, pour exercer correctement le fan-out/timeout de bout en bout.

## Endpoints

| Methode | Route | Description |
|---|---|---|
| GET | `/search?q=...` | Fan-out vers les 4 sources, agregation + timeout par source |
| GET | `/healthz` | Sonde de sante |

## Variables d'environnement

| Variable | Defaut | Description |
|---|---|---|
| `PORT` | `4002` | Port d'ecoute HTTP |
| `SEARCH_TIMEOUT_MS` | `2000` | Timeout par service source |
| `MATRIX_BASE_URL` | `https://matrix.example.org` | URL du serveur Matrix |
| `SEAFILE_BASE_URL` | `https://seafile.example.org` | URL de Seafile |
| `VIKUNJA_BASE_URL` | `https://vikunja.example.org` | URL de Vikunja |
| `GROMMUNIO_IMAP_HOST` | `mail.example.org` | Hote IMAP Grommunio |
| `GROMMUNIO_IMAP_PORT` | `993` | Port IMAP |

## Structure

- `src/fanout.ts` — coeur pur du fan-out/timeout/agregation, injecte les sources en
  parametre pour rester testable sans reseau (`test/fanout.test.ts`).
- `src/sources/*.ts` — un connecteur HTTP/IMAP par service, relayant le token utilisateur.
- `src/server.ts` — route Express `/search`, extraction du token depuis `Authorization`.

## Developpement

```bash
npm install
npm test
npm run build
npm start
```
