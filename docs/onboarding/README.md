# Native application onboarding (study 2.5)

`docs/mapping.md` has pointed here since the very first version of this
repository's correspondence table, but this directory was never actually
populated — a dangling reference, found during review (the same kind of gap
`docs/clients.md` used to be, study 1.9).

## What study 2.5 asks for

"Facilitating the installation of native applications (Mac, iOS, Android)",
concluding on a lightweight approach with **no MDM server**:

1. A static onboarding page (HTML, behind Caddy) listing each application
   with an App Store/Play Store link and a preconfigured deep-link QR code.
2. An optional `.mobileconfig` file to preconfigure the Grommunio mail
   account (ActiveSync) on Mac/iPhone.
3. No MDM infrastructure until a real fleet-management need is identified.

## Where the actual content lives

Not in this directory: the onboarding page and the `.mobileconfig` are
**generated** by `scripts/sync_platform.py` (`compute_onboarding_changes()`)
into `infra/k8s/manifests/onboarding.yaml`, mounted into the Caddy
Deployment and served at `onboarding.<domain>` (see that Caddyfile site
block in `infra/k8s/manifests/caddy.yaml`).

They have to be generated rather than hand-written and patched like every
other domain occurrence in this repo: each application's QR code is an SVG
rendering (via the `qrcode` package) of a URL containing the domain — a
plain text substitution (`sub_domain()`, used everywhere else) cannot
"re-render" that image if `platform.yaml`'s `domains.base` changes, only a
full regeneration can. Run `python3 scripts/sync_platform.py` after any
domain change, same as for every other generated/patched file.

## Deliberately generic `.mobileconfig` — no authentication needed

The generated `grommunio-eas.mobileconfig` carries **only** the EAS server
hostname (`EASHost`) — no username, email, or password. iOS/macOS prompts
the user for those interactively while installing the profile. This is what
makes it safe to publish on the onboarding page **without authentication**:
there is nothing personal or secret in the file, and every consultant
downloads the exact same one.

A per-user, personalized profile (credentials pre-filled) would need its own
small backend generating it on demand (gated behind Keycloak SSO, most
likely) and would then need to sit behind authentication — a materially
larger scope than what study 2.5 asks for, and it would contradict that
section's own conclusion ("no MDM infrastructure", "static ... page"). Not
built here for that reason; flagged in case a future requirement changes
this trade-off.

## App/Play Store links: search results, not a direct listing

Each app card links to `apps.apple.com/search?...` / `play.google.com/store/search?...`
rather than a specific app's listing page (a numeric bundle ID / package
name). Neither could be verified against the live stores from the
environment this was built in — a wrong guessed direct link is worse than a
search page the user picks the right result from once. Replace them with
direct listing links once verified, if a smoother experience is wanted.

## Related: cross-cutting banner Tasmane branding

The same graphic-charter tokens (Tasmane's Brand Guidelines: Madison
`#2B3B58`, Ripe Malinka `#F55364`, Off White `#EEEEEE`, Midnight Edition
`#0C141A`, Aileron typeface) used on this onboarding page are also applied
to `infra/k8s/manifests/caddy-injection.yaml`'s cross-cutting application
banner and `infra/k8s/manifests/gokapi.yaml`'s Gokapi `custom.css` — kept in
sync by hand across these three places today.
