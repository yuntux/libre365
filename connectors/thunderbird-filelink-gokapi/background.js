/**
 * Thunderbird Filelink provider for Gokapi (study 2.11 line 562).
 *
 * Follows the pattern of existing Filelink providers (Dropbox/Box/WebDAV): implements
 * the events of the `cloudFile` API (https://webextension-api.thunderbird.net/en/latest/cloudFile.html),
 * relying on Gokapi's REST API for upload and link generation.
 *
 * Configuration (Gokapi instance URL + API key) stored via `browser.storage.local`,
 * entered in `management.html` (Filelink account page, one entry per Thunderbird
 * account configured for this provider -- see `accountId` passed to each callback).
 */

const GOKAPI_API_TIMEOUT_MS = 60000;

async function getAccountConfig(accountId) {
  const key = `account-${accountId}`;
  const stored = await browser.storage.local.get(key);
  const config = stored[key];
  if (!config || !config.baseUrl || !config.apiKey) {
    throw new Error(
      "Gokapi account not configured: enter the instance URL and API key in the Filelink account settings."
    );
  }
  return config;
}

/**
 * Fires for each attachment uploaded above the Filelink threshold (study 2.11
 * line 562: "beyond a configurable size threshold, Thunderbird automatically
 * offers to send the attachment via a Filelink provider").
 */
browser.cloudFile.onFileUpload.addListener(async (account, { id, name, data }) => {
  try {
    const config = await getAccountConfig(account.id);

    // Gokapi API: POST /api/files/upload (multipart/form-data), see Gokapi
    // documentation (`gokapi-cli` relies on the same REST endpoint).
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
      throw new Error(`Gokapi responded with status ${response.status}`);
    }

    const result = await response.json();
    // Expected Gokapi response: { FilesInfo: { Id, UrlDownload, ... } } (simplified
    // structure here -- to be adjusted to the exact deployed Gokapi API version).
    const downloadUrl = result?.FilesInfo?.UrlDownload ?? result?.Url ?? result?.url;
    const fileId = result?.FilesInfo?.Id ?? result?.Id ?? id;

    if (!downloadUrl) {
      throw new Error("Unexpected Gokapi response: download link missing.");
    }

    // Keeps the attachment-id <-> Gokapi-file-id mapping, needed by
    // `onFileDeleted` to purge the file server-side if the user removes the
    // attachment before sending the mail.
    await browser.storage.local.set({ [`upload-${account.id}-${id}`]: fileId });

    return { url: downloadUrl };
  } catch (error) {
    return { aborted: false, error: { message: error.message } };
  }
});

/**
 * Fires when the user removes a Filelink attachment before sending the mail,
 * or after sending depending on the retention policy chosen by the user. Purges the
 * file on the Gokapi side to avoid leaving orphaned files.
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
    // Deletion is best-effort: the file expires anyway according to the
    // Gokapi retention policy (`expiryDays`) configured at upload time.
    console.warn("gokapi-filelink: remote deletion failed", error);
  }
});

// Optional but expected by some Filelink providers: local cleanup when
// Thunderbird fully removes the Filelink account on the client side.
browser.cloudFile.onAccountDeleted.addListener(async (accountId) => {
  await browser.storage.local.remove(`account-${accountId}`);
});
