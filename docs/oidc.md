# Keycloak OIDC coverage (study 1.7)

Study 1.7 says SSO via Keycloak has to be "checked service by service"
rather than assumed. This file is that check, kept current: which
components have a real, working OIDC chain today, which deliberately don't,
and how a future gap of the same shape gets caught automatically instead of
by another manual audit.

## What "a complete chain" means here

Every entry in `infra/ansible/roles/keycloak_realm/defaults/main.yml`'s
`keycloak_oidc_clients` is expected to be backed by three things, all
present, all consistent:

1. A Keycloak client definition (the realm entry itself).
2. The matching `client_id` configured on the side that actually uses it —
   normally the application's own `infra/k8s/helm-values/*.yaml` (or
   `infra/k8s/manifests/gokapi.yaml`); for the two components with no
   native OIDC support of their own (OnlyOffice, Novu — see below), that's
   instead the `oauth2-proxy-*.yaml` gate placed in front of them.
3. A real `ExternalSecret` in `infra/k8s/manifests/external-secrets.yaml`
   backing the client secret that side references — never a hardcoded or
   dangling `secretKeyRef`.

**Every component the study expects to be SSO-gated has a client** —
including the two that don't speak OIDC themselves. Rather than leave them
unprotected (as an earlier pass on this branch mistakenly did — see the
changelog note at the end of this file) or invent OIDC support neither
product has, they're gated at the reverse-proxy layer: Caddy's
`forward_auth` sends every request to an `oauth2-proxy` instance first,
which redirects an unauthenticated browser to Keycloak and only lets the
request through once Keycloak has authenticated it. The application never
sees Keycloak directly; the gate is what holds the client.

`scripts/sync_platform.py`'s `check_oidc_coverage()` enforces (2) and (3)
for every client declared in (1), unconditionally, on every run (`apply`
and `--check` alike) — see that function's docstring. It is covered by
offline unit tests in `scripts/test_sync_platform.py` that reproduce each
gap found below, so a regression of the same shape fails CI immediately
instead of waiting for another manual review.

## Audit findings and fixes

A full pass across every component in the stack found the following gaps,
all fixed on this branch:

| Component | Finding | Fix |
|---|---|---|
| **Gokapi** | `GOKAPI_OAUTH_CLIENT_ID` was set, but no `GOKAPI_OAUTH_CLIENT_SECRET` was ever wired to a real secret — no matching `ExternalSecret` existed at all. | Added `gokapi-oidc-secret` `ExternalSecret` (`infra/k8s/manifests/external-secrets.yaml`, sourced from `libre365/gokapi`/`oidc-client-secret` in OpenBao); `gokapi.yaml` already referenced it by name. **Superseded**: Gokapi was later bumped from `v1.9.6` to `v2.2.4` (see "Gokapi's OIDC config isn't an env var anymore" below) — the secret and ExternalSecret are unchanged, but they now feed a setup-wizard bootstrap script instead of a `GOKAPI_OAUTH_CLIENT_SECRET` env var directly. |
| **Seafile** | `ENABLE_OAUTH`/`OAUTH_CLIENT_ID` were set with no `OAUTH_CLIENT_SECRET` at all — the OAuth token exchange could never complete. | Added `OAUTH_CLIENT_SECRET` (`secretKeyRef` → `seafile-oidc-secret`) to `seafile.yaml`, and the matching `ExternalSecret`. |
| **PeerTube** | The `openid_connect` plugin block had a `client_id` but no `client_secret` at all. | Added a `client_secret` block (`existingSecret: peertube-oidc-secret`) to `peertube.yaml`, and the matching `ExternalSecret`. **[UNCERTAIN]**: the community chart's exact field shape for injecting a Secret into a plugin setting isn't independently confirmed — see that file's own comment; verify against the real chart before deploying. |
| **Visio (LaSuite Meet)** | Full app-side OIDC config (`OIDC_RP_CLIENT_ID: "visio-meet"`, etc.) in `visio-meet.yaml`, but no `visio-meet` Keycloak client existed anywhere — the realm would reject every login attempt. | Added the `visio-meet` client to `keycloak_realm/defaults/main.yml` (redirect URI inferred from mozilla-django-oidc's default callback path, `/oidc/callback/` — LaSuite Meet is a Django app, per that file's env var naming convention; not independently confirmed against LaSuite Meet's own source), plus `visio-meet-oidc-secret`. |
| **Matrix / Synapse** | Two conflicting configs: the Helm chart's native `synapse.oidc` block used `client_id: "synapse"` (wrong, unused), while a separate Ansible-rendered ConfigMap (`playbooks/matrix.yml`) used the correct `client_id: "matrix-synapse"` — but that ConfigMap was never actually consumed by anything (`grep` for its name/`extraConfig` found no reference anywhere in the chart wiring). | Fixed `synapse.yaml`'s own `client_id` to `"matrix-synapse"` (matching the realm and `synapse-oidc-secret`, which was already correct); deleted the dead `playbooks/matrix.yml` and its template rather than reconciling two configs when only one was ever live. |
| **OnlyOffice Document Server** | Had a Keycloak client with nothing to use it: Community Edition has no standalone end-user login when embedded via a host app — it's reached exclusively via JWT-signed requests from Seafile (`onlyoffice-jwt-secret`, already correctly wired on both sides) — but `office.libre365.example.org` was, and remains, a direct public route with no gate at all in front of the browser-facing surface. | An earlier pass on this branch removed the client outright, reasoning the app had "no login surface to protect" — that's true of OnlyOffice's own login, but false of the public endpoint itself: anyone could open `office.libre365.example.org` directly. Corrected: re-added the `onlyoffice` client and put a Caddy `forward_auth` → `oauth2-proxy` gate (`oauth2-proxy-onlyoffice.yaml`) in front of the site block, in addition to (not instead of) the existing JWT document-level signing. |
| **Novu** | Had a Keycloak client with nothing to use it in the same way: the notification-center *widget* authenticates subscribers via an HMAC-signed subscriber hash, not OIDC. But `novu.yaml`'s own `env` block sets `FRONT_BASE_URL`/`WS_URL` to `notifications.libre365.example.org`, and that hostname *is* Caddy-fronted — the widget-facing API is the only thing actually gated by anything (its HMAC auth), and Novu's `web` admin dashboard had no route, gated or not. | An earlier pass removed the client, reasoning (partly on this file's own comment, which is accurate for the *widget*) that Novu has no exposed login surface — true for the widget, incomplete for the admin dashboard, which simply wasn't wired up either way. Corrected: re-added the `novu` client, added a new `notifications-admin.libre365.example.org` Caddy site exposing Novu's `web` dashboard, gated by its own `oauth2-proxy` instance (`oauth2-proxy-novu.yaml`). `notifications.libre365.example.org` (the API, consumed by the widget) is deliberately left as-is — gating it with an interactive Keycloak login would break the widget, which has no browser redirect flow to complete one. |

## Components with no client — by design

- **Grommunio**: application SSO for `grommunio-web` is not treated as a
  priority by the study (the web admin UI stays disabled anyway, see
  `playbooks/grommunio.yml`) — left for future extension, not a gap.
- **Element Web / Element Call**: no client — both are Matrix clients that
  authenticate against Synapse (already OIDC-wired above), never against
  Keycloak directly.
- **MinIO**: no end-user login surface in this architecture (internal S3
  backend only) — no client needed.

## OnlyOffice and Novu: gated by proxy, not by the app itself

Two components in `keycloak_oidc_clients` — `onlyoffice` and `novu` — don't
speak OIDC natively at all. Rather than leave their public routes
unprotected, or invent OIDC support neither product actually has, each is
put behind its own `oauth2-proxy` instance (official
`oauth2-proxy/oauth2-proxy` chart):

- `infra/k8s/helm-values/oauth2-proxy-onlyoffice.yaml` gates
  `office.libre365.example.org` in front of Document Server.
- `infra/k8s/helm-values/oauth2-proxy-novu.yaml` gates the *new*
  `notifications-admin.libre365.example.org` site in front of Novu's `web`
  dashboard — deliberately **not** in front of `notifications.libre365.example.org`
  (the API), which the top-bar widget calls with its own HMAC
  subscriberHash auth and has no interactive login flow to redirect
  through.

In `infra/k8s/manifests/caddy.yaml`, each gated site routes `/oauth2/*` to
the proxy itself (login start + callback) and everything else through
`forward_auth` first — verified against a real Caddy 2.8.4 binary
(`caddy validate --adapter caddyfile`), the same way every other change to
that file on this branch has been. Each proxy's Keycloak client
(`onlyoffice`/`novu` in `keycloak_realm/defaults/main.yml`) has its
`redirect_uris` pointing at that proxy's own `/oauth2/callback`, not at the
application — the application never talks to Keycloak directly in either
case. `check_oidc_coverage()`'s `OIDC_CLIENT_APP_FILES` mapping points
these two client_ids at their gate's helm-values file rather than the
application's, which is where `check_oidc_coverage()` looks for them.

## Gokapi's OIDC config isn't an env var anymore (v1.9.6 → v2.2.4)

Raised during a branding review (Gokapi's `custom.css` theming turned out
to need a version this repo wasn't pinned to - see
`infra/k8s/manifests/gokapi.yaml`'s header): bumping to the latest stable
release (`v2.2.4`) also changes how OIDC gets configured at all. Checked
against the real source at both tags, and against a **locally built
`v2.2.4` binary** (`go generate && go build`, then real HTTP requests
against it in a sandboxed test):

- `v1.9.6` reads `GOKAPI_OAUTH_PROVIDER`/`GOKAPI_OAUTH_ISSUER_URL`/
  `GOKAPI_OAUTH_CLIENT_ID`/`GOKAPI_OAUTH_CLIENT_SECRET` as plain env vars
  at every startup - simple, but that version also has no theming
  mechanism at all (the reason for the bump in the first place).
- `v2.0.0` (changelog: "Upgrade path: Requires v1.9.6 as base") replaced
  this with a one-time setup wizard
  (`internal/configuration/setup/Setup.go`) that persists everything to
  `config.json` on first boot. None of the `GOKAPI_OAUTH_*` env vars exist
  in `v2.2.4`'s `Environment` struct at all anymore - checked directly in
  the source, not inferred from the docs.
- That setup wizard is **unauthenticated by design on first boot**
  ("No auth required on initial setup", `Setup.go`'s own comment) - it's
  meant to be completed immediately after container start, before the
  instance is reachable from the internet, not filled in later through a
  public URL.
- The encryption level **numbering changed** between the two versions
  (`internal/encryption/Encryption.go`): `v1.9.6`'s level `3` meant true
  end-to-end encryption; in `v2.x`, level `3` is `FullEncryptionStored`
  (the server holds the key - not zero-knowledge) and level `5` is the
  actual `EndToEndEncryption` equivalent. Keeping the old numeric value
  across this upgrade would have silently downgraded real E2EE to
  server-side encryption-at-rest — study 1.8's explicit requirement.

Automated (not left as a manual step, consistent with this repo's
Ansible-automated Grommunio cert issuance) via
`infra/k8s/manifests/gokapi.yaml`'s `gokapi-setup-bootstrap` initContainer:
it runs the same `f0rc3/gokapi` image, checks whether `config.json`
already exists on the shared PVC (idempotent, same pattern as
`grommunio_cert`'s `creates:`), and if not, starts Gokapi's setup
webserver, POSTs the exact JSON payload `Setup.go`'s `toConfiguration()`
expects (reconstructed by reading every `getFormValue*` call in that
file, **verified by actually running it against the built binary** and
inspecting the resulting `config.json` - not just read from source and
assumed correct), and lets Gokapi shut the setup server down on its own.
Because this runs as an initContainer, it completes before the
Service/Ingress ever exist for that pod - the "unauthenticated on first
boot" window Gokapi's own design assumes is never exposed publicly.

## Automated regression coverage

- **Structural (offline, always-on)**: `scripts/sync_platform.py`'s
  `check_oidc_coverage()`, run unconditionally by every `sync_platform.py`
  invocation (including `--check`, i.e. CI). Its tests in
  `scripts/test_sync_platform.py` reproduce each finding above (a client
  with no app-side `client_id`, a `client_id` with no secret reference at
  all, a referenced secret with no matching `ExternalSecret`, and a client
  missing from the file-mapping itself) — this is what would have caught
  every one of these gaps automatically instead of requiring a manual
  audit.
- **Live end-to-end (`tests/integration/test_sso_e2e.py`)**: an earlier
  version of this test presented a single Resource Owner Password
  Credentials token, issued to a shared `"integration-tests"` Keycloak
  client, directly as `Authorization: Bearer` to Seafile/Vikunja/Matrix/
  OnlyOffice/Grommunio's own APIs. That doesn't reflect how any of these
  apps actually implement OIDC (a caught issue — see the "was this ever
  correct?" note below) — none of them validate an externally-obtained
  bearer token as a resource server would; they all complete a browser
  authorization-code redirect and mint their OWN native credential (a
  Seahub session cookie, a Vikunja JWT, a Matrix `access_token`). Rewritten
  so each covered component (**Seafile, Vikunja, Matrix**) drives the real
  redirect flow with a plain `requests.Session` via `conftest.py`'s
  `keycloak_login` helper (Keycloak's default login page is a plain HTML
  form, no browser/JS execution needed) and then verifies the credential
  that flow actually produces is what the app's protected endpoint accepts.
  Vikunja's exact callback payload shape and OIDC provider "key" derivation
  are flagged `[UNCERTAIN]` in that test — not independently confirmed
  against a live instance from this sandboxed environment; it fails with a
  clear diagnostic rather than a false pass if either assumption doesn't
  hold.

  **Grommunio** is not in this test at all: it has no Keycloak client (by
  design, see above), and the URL an earlier version queried
  (`{caddy}/grommunio/api/whoami`) never corresponded to anything actually
  built in this repository — there was no real mechanism there to test.

  **OnlyOffice and Novu** ARE now covered too
  (`test_onlyoffice_oauth2_proxy_gate_blocks_then_allows`,
  `test_novu_admin_oauth2_proxy_gate_blocks_then_allows`) — a second gap
  found on top of the first: their SSO gate lives entirely in Caddy's
  `forward_auth` routing, but this suite's dev tier (`caddy-dev`) used to
  be a completely different, hand-maintained, path-based portal with none
  of production's domain-based site blocks or SSO gates at all, so nothing
  could reach them regardless of which port a test used. Fixed at the
  infrastructure level, not by adding yet more test-only special cases:
  - `infra/k8s/manifests/dev/caddy.yaml`'s Caddyfile is now **generated**
    from the real, production one (`scripts/sync_platform.py`'s
    `compute_dev_caddy_change()`) — domain-based routing and the
    `forward_auth` gates included, so the two can never silently drift
    apart again.
  - `dev-cluster/deploy.sh`'s CoreDNS step
    (`dev-cluster/patch-coredns-hosts.sh`) makes every `platform.yaml`
    domain resolve to that Caddy instance from INSIDE the cluster (every
    app's own OIDC issuer/authurl config uses the real public domain
    unconditionally — never a second, dev-only hard-coded value).
  - `tests/integration/conftest.py`'s `DomainRoutingAdapter` does the same
    thing for the test runner OUTSIDE the cluster — self-tested against a
    throwaway local HTTP server in `test_domain_routing_adapter.py`, not
    just plausible-looking code.

  See `dev-cluster/README.md`'s "Testing Keycloak SSO/OIDC end-to-end" for
  the full picture — this also means the Seafile/Vikunja/Matrix tests
  above now go through the real public domain (Caddy), not each app's
  directly-exposed port, matching how a real browser would actually reach
  them.

  **Gokapi, PeerTube, Visio** stay out for a different reason: each
  delegates to Keycloak via a browser redirect that ends in an
  application-issued session/token of its own, and neither their exact
  redirect/session mechanics (Gokapi, PeerTube) nor a working dev-tier
  environment to target at all (Visio has no `platform.yaml` port/service
  entry yet) are available to script confidently from this sandboxed
  environment — a documented follow-up, not guessed.

### Was the previous "generic bearer token" version of this test ever correct?

No — flagged during a later review pass. Presenting a Resource Owner
Password Credentials token, issued to a client (`"integration-tests"`)
that isn't the app's own registered OIDC client, as a bearer credential on
an app's REST API only works if that app implements OAuth2
resource-server-style JWT validation of externally-issued tokens (RFC
9068) with a matching audience — none of Seafile, Vikunja, or Synapse do
this in their standard self-hosted OIDC integration; each is a
browser-redirect login that mints its own native credential instead. The
test likely never verified what it claimed to for any of its five original
targets, and — consistent with every other "no live cluster in this
sandbox" caveat throughout this repository — was probably never run
against a real deployment to notice.
