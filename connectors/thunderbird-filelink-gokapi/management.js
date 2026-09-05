/**
 * Configuration page for the Gokapi Filelink account. Thunderbird opens this page
 * (`cloud_file.management_url`) with an `accountId` parameter in the URL for each
 * Filelink account of this provider added by the user.
 */
function getAccountId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("accountId") ?? "default";
}

async function load() {
  const accountId = getAccountId();
  const key = `account-${accountId}`;
  const stored = await browser.storage.local.get(key);
  const config = stored[key] ?? {};

  document.getElementById("baseUrl").value = config.baseUrl ?? "";
  document.getElementById("apiKey").value = config.apiKey ?? "";
  document.getElementById("expiryDays").value = config.expiryDays ?? "";
  document.getElementById("allowedDownloads").value = config.allowedDownloads ?? "";
}

async function save() {
  const accountId = getAccountId();
  const key = `account-${accountId}`;

  const config = {
    baseUrl: document.getElementById("baseUrl").value.trim(),
    apiKey: document.getElementById("apiKey").value.trim(),
    expiryDays: Number(document.getElementById("expiryDays").value) || undefined,
    allowedDownloads: Number(document.getElementById("allowedDownloads").value) || undefined,
  };

  await browser.storage.local.set({ [key]: config });
  document.getElementById("status").textContent = "Saved.";
}

document.getElementById("save").addEventListener("click", save);
load();
