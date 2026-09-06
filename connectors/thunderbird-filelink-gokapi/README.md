# thunderbird-filelink-gokapi

Thunderbird WebExtension (not a backend service) implementing a Filelink provider for
Gokapi (study 2.11, lines 559-563).

## Context (study 2.11)

Beyond a configurable size threshold (5 MB by default), Thunderbird automatically
offers to send an attachment via a **Filelink** provider rather than as a classic
attachment -- a mechanism already used by existing third-party providers
(Dropbox, Box, WebDAV, Send instances). This module follows that pattern, already
proven by the Thunderbird community, to apply it to **Gokapi** (study 1.8), via
Gokapi's REST API (the same endpoints used by `gokapi-cli`).

## What this is not

This is **not** a Node/Express service like the other 5 connectors in this repo:
it is an extension installed client-side in Thunderbird. No server to deploy and
no associated Dockerfile.

## Files

- `manifest.json` — minimal WebExtension manifest, `permissions: ["cloudFile", "storage"]`,
  `cloud_file` declaration (provider name, account management page).
- `background.js` — implements the callbacks required by the `cloudFile` API:
  - `onFileUpload`: uploads the attachment to `POST /api/files/upload` (Gokapi),
    returns the generated download link to insert into the mail body.
  - `onFileDeleted`: purges the file on the Gokapi side (`DELETE /api/files/delete/:id`)
    if the user removes the attachment before sending.
  - `onAccountDeleted`: cleans up the local account configuration.
- `management.html` / `management.js` — per-account configuration page (Gokapi
  instance URL, API key, retention duration, max number of downloads),
  stored via `browser.storage.local`.

## Installation / manual testing

1. In Thunderbird: `Tools -> Add-ons and Themes -> gear icon ->
   Install Add-on From File`, pointing to a zip of this folder
   (or load it temporarily via `about:debugging` in developer mode).
2. In the mail account settings, Attachments / Filelink section, add a
   "Gokapi" account: the `management.html` page opens to enter the instance URL
   and the API key (associated with the sender's OIDC account, see study 2.11).
3. Attach a file above the configured Filelink threshold: Thunderbird offers to
   send it via Gokapi rather than as a classic attachment.

## Fleet-wide deployment (`policies.json`)

The manual steps above don't scale to every consultant's workstation. This is
a **different mechanism from the mail account autoconfig** (`autoconfig.xml`,
see `docs/clients.md`) — that one only ever describes mail server settings,
it has no notion of an extension to install. Thunderbird's own **enterprise
policy engine** covers that instead: `policies.json`'s `ExtensionSettings`
key, with `"installation_mode": "force_installed"`, silently installs (and
keeps installed) an extension from a URL — bypassing the AMO signing
requirement that would otherwise block a custom, non-Mozilla-reviewed
extension like this one.

`policies.json` (this directory) is a ready-to-deploy template:

```json
{
  "policies": {
    "ExtensionSettings": {
      "gokapi-filelink@libre365.example.org": {
        "installation_mode": "force_installed",
        "install_url": "https://onboarding.libre365.example.org/extensions/gokapi-filelink.xpi"
      }
    }
  }
}
```

Two things a maintainer still has to do — both are workstation/endpoint
concerns, out of scope for this repository's server-side IaC:

1. **Package this extension as a `.xpi`** (a plain zip of this directory's
   contents — `manifest.json`, `background.js`, `management.html`,
   `management.js`, `icons/`, excluding `README.md`/`policies.json`
   themselves) and publish it at the `install_url` above. No build step
   currently packages or publishes this automatically; the URL assumes it's
   hosted on the onboarding static site
   (`infra/k8s/manifests/caddy.yaml`'s `onboarding.<domain>` site block),
   whose actual content isn't populated by anything in this repository
   either (see that file's Caddyfile comment) — publishing the `.xpi` there
   requires that gap to be closed too, or an alternative hosting location.
2. **Deploy `policies.json` to every workstation** — Thunderbird looks for it
   in a `distribution/` folder next to its own installation directory, or it
   can be centrally pushed via a Windows GPO (`Software\Policies\Mozilla\Thunderbird`
   registry keys, one per policy) or a macOS configuration profile. Which
   channel to use depends on the firm's existing endpoint-management tooling
   (Active Directory, MDM, or a plain login-script copy) — not something an
   infrastructure-as-code repository targeting the server side can prescribe.

The `install_url`'s domain is patched automatically by `scripts/sync_platform.py`
like every other domain occurrence in this repository (see
`platform.yaml`'s `domains.subdomains.onboarding`) — never edit it by hand.

## Accepted limitations (deliberate stub)

- The exact format of Gokapi's `POST /api/files/upload` response is simplified
  (`result?.FilesInfo?.UrlDownload ?? result?.Url ?? result?.url`) -- to be adjusted
  to the exact Gokapi API version deployed in production.
- No upload progress handling (`onFileUploadProgress`) in this minimal version --
  to be added if progress UX becomes a stated requirement.
