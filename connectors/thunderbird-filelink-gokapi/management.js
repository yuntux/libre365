/**
 * Page de configuration du compte Filelink Gokapi. Thunderbird ouvre cette page
 * (`cloud_file.management_url`) avec un parametre `accountId` dans l'URL pour chaque
 * compte Filelink de ce provider ajoute par l'utilisateur.
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
  document.getElementById("status").textContent = "Enregistre.";
}

document.getElementById("save").addEventListener("click", save);
load();
