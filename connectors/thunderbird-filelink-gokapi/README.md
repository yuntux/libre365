# thunderbird-filelink-gokapi

WebExtension Thunderbird (pas un service serveur) implementant un provider Filelink pour
Gokapi (etude 2.11 ligne 559-563).

## Contexte (etude 2.11)

Au-dela d'un seuil de taille configurable (5 Mo par defaut), Thunderbird propose
automatiquement d'envoyer une piece jointe via un fournisseur **Filelink** plutot qu'en
piece jointe classique -- mecanisme deja utilise par des fournisseurs tiers existants
(Dropbox, Box, WebDAV, instances de Send). Ce module suit ce patron deja eprouve par la
communaute Thunderbird pour l'appliquer a **Gokapi** (etude 1.8), via l'API REST de
Gokapi (memes points d'entree que ceux utilises par `gokapi-cli`).

## Ce que ce n'est pas

Ce n'est **pas** un service Node/Express comme les 5 autres connecteurs de ce depot :
c'est une extension installee dans Thunderbird cote client. Aucun serveur a deployer ni
Dockerfile associe.

## Fichiers

- `manifest.json` — manifest WebExtension minimal, `permissions: ["cloudFile", "storage"]`,
  declaration `cloud_file` (nom du provider, page de gestion de compte).
- `background.js` — implemente les callbacks requis par l'API `cloudFile` :
  - `onFileUpload` : upload la piece jointe vers `POST /api/files/upload` (Gokapi),
    retourne le lien de telechargement genere a inserer dans le corps du mail.
  - `onFileDeleted` : purge le fichier cote Gokapi (`DELETE /api/files/delete/:id`) si
    l'utilisateur retire la piece jointe avant l'envoi.
  - `onAccountDeleted` : nettoyage de la configuration locale du compte.
- `management.html` / `management.js` — page de configuration par compte (URL de
  l'instance Gokapi, cle API, duree de conservation, nombre max de telechargements),
  stockee via `browser.storage.local`.

## Installation / test manuel

1. Dans Thunderbird : `Outils -> Modules complementaires et themes -> engrenage ->
   Installer un module depuis un fichier`, en pointant vers un zip de ce dossier
   (ou charger temporairement via `about:debugging` en mode developpeur).
2. Dans les parametres du compte mail, section Pieces jointes / Filelink, ajouter un
   compte "Gokapi" : la page `management.html` s'ouvre pour saisir l'URL de l'instance
   et la cle API (associee au compte OIDC de l'expediteur, cf. etude 2.11).
3. Joindre un fichier au-dela du seuil Filelink configure : Thunderbird propose de
   l'envoyer via Gokapi plutot qu'en piece jointe classique.

## Limitations assumees (stub volontaire)

- Le format exact de la reponse `POST /api/files/upload` de Gokapi est simplifie
  (`result?.FilesInfo?.UrlDownload ?? result?.Url ?? result?.url`) -- a ajuster a la
  version precise de l'API Gokapi deployee en production.
- Pas de gestion de la progression d'upload (`onFileUploadProgress`) dans cette version
  minimale -- a ajouter si l'UX de progression devient un besoin exprime.
