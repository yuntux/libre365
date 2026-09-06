# Mail clients — Thunderbird and Apple Mail (study 1.9)

Reference configuration for the desktop mail clients selected in study 1.9:
**Thunderbird** (Windows/Mac/Linux) and **Apple Mail/Calendar/Contacts**
(native macOS integration). No server-side code is needed for the clients
themselves — this document only covers how each one finds and authenticates
against Grommunio, and what this repository already automates for that.

## Connection protocol

Per study 1.9 (L.323, L.350): both clients connect **directly to Grommunio
over EWS**, with no third-party cloud intermediary — this is the whole point
of the sovereignty argument that ruled out the new Outlook for Mac (see the
study's own analysis, same section). IMAP/CalDAV/CardDAV remains a documented
fallback if EWS is unavailable for a given client version.

`infra/ansible/playbooks/grommunio.yml` already ensures the EWS
(`gromox-http.service`), EAS/ActiveSync and MAPI/RPC-HTTP services are active
on the Grommunio VM (study 1.1/1.9) — this document is about how a client
*finds* those services, not about enabling them.

## Account autodiscovery

Two independent mechanisms cover the two families of client this repository
targets, both pointing at the same Grommunio VM (`mail.libre365.example.org`,
see `platform.yaml`'s `domains.subdomains.mail`):

### Thunderbird — Mozilla autoconfig (`autoconfig.<domain>`)

Thunderbird's account wizard checks, among a few methods, an XML file at a
fixed path on an `autoconfig` subdomain of the address's domain:

```
https://autoconfig.libre365.example.org/mail/config-v1.1.xml
```

This repository serves that file: `infra/k8s/manifests/caddy.yaml` has a
`autoconfig.libre365.example.org` Caddyfile site block (static file server,
no HTML injection — this isn't a browsed application) backed by the
`caddy-autoconfig` ConfigMap in the same file. The DNS record is populated
automatically like every other Caddy-fronted subdomain, via `external-dns`
watching the Caddy Service's `external-dns.alpha.kubernetes.io/hostname`
annotation (see `infra/k8s/helm-values/external-dns.yaml`) — no manual step.

The XML declares two ways to auto-configure the account, in order of
preference:

1. **`<incomingServer type="exchange">`** with an `<ewsURL>` pointing at
   Grommunio's EWS endpoint — Thunderbird has supported native Exchange/EWS
   accounts configured this way since version 91, so this alone lets the
   wizard set up the study's primary connection path (EWS) without any
   further round-trip.
2. **`<incomingServer type="imap">` / `<outgoingServer type="smtp">`** — the
   fallback path (IMAP over TLS on 993, SMTP with STARTTLS on 587),
   for a build or a client that doesn't use the exchange block above.

Caveat: Mozilla's algorithm also checks
`https://<domain>/.well-known/autoconfig/mail/config-v1.1.xml` on the bare
address domain (`libre365.example.org`) before falling back to the
`autoconfig.` subdomain — that path is **not** covered here, since no Caddy
site currently serves the bare base domain at all (see
`infra/k8s/manifests/caddy.yaml`'s header comment: Caddy only fronts the
subdomains listed in `platform.yaml`). The `autoconfig.` subdomain method
above is Thunderbird's next attempt in the same lookup sequence and is
sufficient on its own.

### Outlook-style / mobile EAS clients — Microsoft Autodiscover (`autodiscover.<domain>`)

Clients that speak Microsoft's own Autodiscover protocol (Outlook, and most
mobile EAS clients even when reached via a non-Microsoft app) resolve
account settings against:

```
https://autodiscover.libre365.example.org/autodiscover/autodiscover.xml
```

`platform.yaml` declares `domains.subdomains.autodiscover` for this — but,
like `mail` itself, **this hostname is not Caddy-fronted**: Grommunio
terminates its own HTTPS certificate and answers Autodiscover requests
directly (it emulates Exchange), so routing it through Caddy would add
nothing. Populate it the same way `mail.libre365.example.org`'s own DNS
record is populated today: **manually**, as a `CNAME` to
`mail.libre365.example.org` (or an `A`/`AAAA` record matching the Grommunio
VM's address from `infra/terraform/grommunio.tf`'s `grommunio_static_ip`
variable) — this repository does not yet automate DNS for VM-direct
hostnames (no OVH Terraform DNS resource exists for `mail` either, see that
file's comment on line 58; `autodiscover` simply inherits the same
pre-existing gap rather than introducing a new one).

### Apple Mail / Calendar / Contacts

Per the study, Apple Mail/Calendar/Contacts connects the same way (EWS for
mail, CalDAV/EWS for calendar, CardDAV for contacts — GAL exposure over
CardDAV is 2.13, see `infra/ansible/playbooks/grommunio.yml`'s
`GAL_ENABLED`). macOS's own account-setup flow for an Exchange-type account
uses the same Autodiscover mechanism as Outlook above
(`autodiscover.libre365.example.org`) rather than Mozilla's autoconfig, so no
separate configuration is needed beyond the DNS entry already described.

## Thunderbird-specific configuration point — disabling the built-in Matrix chat

See the study's own note (same section, just after the client selection):
Thunderbird bundles an optional Matrix chat client that must be disabled to
avoid a second, redundant chat surface next to Element (1.2) — a per-profile
Thunderbird setting (`chat.enabled` = `false` via policies.json or manual
configuration), not something this repository's server-side IaC can enforce
centrally.

## Large-attachment Filelink (study 1.8/2.11)

Separate from account setup: `connectors/thunderbird-filelink-gokapi/` is a
Thunderbird WebExtension implementing the `cloudFile` API so large
attachments are uploaded to Gokapi instead of sent inline — see that
connector's own README. It has no bearing on account autoconfiguration.
