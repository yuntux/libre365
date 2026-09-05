/**
 * Provider Filelink Thunderbird pour Gokapi (etude 2.11 ligne 562).
 *
 * Suit le patron des providers Filelink existants (Dropbox/Box/WebDAV) : implemente
 * les evenements de l'API `cloudFile` (https://webextension-api.thunderbird.net/en/latest/cloudFile.html),
 * en s'appuyant sur l'API REST de Gokapi pour l'upload et la generation de lien.
 *
 * Configuration (URL de l'instance Gokapi + cle API) stockee via `browser.storage.local`,
 * saisie dans `management.html` (page de compte Filelink, une entree par compte
 * Thunderbird configure pour ce provider -- cf. `accountId` transmis a chaque callback).
 */

const GOKAPI_API_TIMEOUT_MS = 60000;

async function getAccountConfig(accountId) {
  const key = `account-${accountId}`;
  const stored = await browser.storage.local.get(key);
  const config = stored[key];
  if (!config || !config.baseUrl || !config.apiKey) {
    throw new Error(
      "Compte Gokapi non configure : renseignez l'URL de l'instance et la cle API dans les parametres du compte Filelink."
    );
  }
  return config;
}

/**
 * Declenche a chaque piece jointe deposee au-dessus du seuil Filelink (etude 2.11
 * ligne 562 : "au-dela d'un seuil de taille configurable, Thunderbird propose
 * automatiquement d'envoyer la piece jointe via un fournisseur Filelink").
 */
browser.cloudFile.onFileUpload.addListener(async (account, { id, name, data }) => {
  try {
    const config = await getAccountConfig(account.id);

    // API Gokapi : POST /api/files/upload (multipart/form-data), cf. documentation
    // Gokapi (`gokapi-cli` s'appuie sur le meme endpoint REST).
    const form = new FormData();
    form.append("file", data, name);
    if (config.allowedDownloads) {
      form.append("allowedDownloads", String(config.allowedDownloads));
    }
    if (config.expiryDays) {
      form.append("expiryDays", String(config.expiryDays));
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), GOKAPI_API_TIMEOUT_MS);
    let response;
    try {
      response = await fetch(`${config.baseUrl.replace(/\/$/, "")}/api/files/upload`, {
        method: "POST",
        headers: { apikey: config.apiKey },
        body: form,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) {
      throw new Error(`Gokapi a repondu avec le statut ${response.status}`);
    }

    const result = await response.json();
    // Reponse Gokapi attendue : { FilesInfo: { Id, UrlDownload, ... } } (structure
    // simplifiee ici -- a ajuster a la version exacte de l'API Gokapi deployee).
    const downloadUrl = result?.FilesInfo?.UrlDownload ?? result?.Url ?? result?.url;
    const fileId = result?.FilesInfo?.Id ?? result?.Id ?? id;

    if (!downloadUrl) {
      throw new Error("Reponse Gokapi inattendue : lien de telechargement absent.");
    }

    // Conserve la correspondance id-piece-jointe <-> id-fichier-Gokapi, necessaire a
    // `onFileDeleted` pour purger le fichier cote serveur si l'utilisateur retire la
    // piece jointe avant l'envoi du mail.
    await browser.storage.local.set({ [`upload-${account.id}-${id}`]: fileId });

    return { url: downloadUrl };
  } catch (error) {
    return { aborted: false, error: { message: error.message } };
  }
});

/**
 * Declenche quand l'utilisateur retire une piece jointe Filelink avant l'envoi du mail,
 * ou apres l'envoi selon la politique de retention choisie par l'utilisateur. Purge le
 * fichier cote Gokapi pour ne pas laisser de fichiers orphelins.
 */
browser.cloudFile.onFileDeleted.addListener(async (account, id) => {
  try {
    const config = await getAccountConfig(account.id);
    const key = `upload-${account.id}-${id}`;
    const stored = await browser.storage.local.get(key);
    const fileId = stored[key];
    if (!fileId) {
      return;
    }

    await fetch(`${config.baseUrl.replace(/\/$/, "")}/api/files/delete/${encodeURIComponent(fileId)}`, {
      method: "DELETE",
      headers: { apikey: config.apiKey },
    });

    await browser.storage.local.remove(key);
  } catch (error) {
    // La suppression est best-effort : un fichier expire de toute facon selon la
    // politique de retention Gokapi (`expiryDays`) configuree a l'upload.
    console.warn("gokapi-filelink: echec de suppression distante", error);
  }
});

// Optionnel mais attendu par certains providers Filelink : nettoyage local quand
// Thunderbird supprime completement le compte Filelink cote client.
browser.cloudFile.onAccountDeleted.addListener(async (accountId) => {
  await browser.storage.local.remove(`account-${accountId}`);
});
