# grommunio_cert_renewal

Ensures automatic Let's Encrypt renewal stays enabled on the Grommunio VM
(study 1.9/4.3) — closes a gap noted during review: Grommunio (`mail.<domain>`
and `autodiscover.<domain>`, see `docs/clients.md`) is deliberately **not**
Caddy-fronted, so it doesn't benefit from Caddy's own Automatic HTTPS the
way every other public hostname in this repository does. It needs its own
certificate lifecycle.

## What this role does — and deliberately does not do

Verified against grommunio's own documentation
(`grommunio/grommunio-documentation`, `admin/installation.rst` and
`admin/quickstart.rst`) rather than assumed:

- The appliance's own setup wizard (`grommunio-setup`) offers "Automatic
  generation of certificates with Let's Encrypt" as one of four certificate
  options, backed by **certbot** (not `acme.sh` — confirmed by the exact
  command the docs show for adding extra domains to an existing
  certificate, see below). Certificates are stored under `/etc/grommunio/ssl`.
- **Initial issuance is NOT automated by this role.** It requires port 80
  briefly reachable from the Internet and is presented by grommunio's own
  docs as a wizard step — consistent with this repository's existing
  convention that Grommunio's initial installation is semi-interactive (see
  `infra/terraform/grommunio.tf`'s own comment on the appliance ISO
  installer). Run it once, by hand, covering BOTH hostnames Grommunio
  answers for (`mail.<domain>` and `autodiscover.<domain>` — see
  `docs/clients.md`) as a single multi-domain certificate, using the exact
  command grommunio's own docs give for this case:

  ```
  certbot certonly -n --standalone --agree-tos --preferred-challenges http \
    --cert-name="mail.<domain>" \
    -d "mail.<domain>" -d "autodiscover.<domain>" \
    --deploy-hook /usr/share/grommunio-setup/grommunio-certbot-renew-hook
  ```

  (`--deploy-hook` points at the script grommunio-setup itself installs, so
  every service on the appliance picks up the renewed certificate the same
  way it would after a wizard-driven renewal — not something this role
  needs to reimplement.)

- **What this role DOES automate**: ensuring `certbot.timer` (the standard
  systemd timer shipped by Debian/Ubuntu's `certbot` package, running
  `certbot renew` twice daily and only actually renewing a certificate in
  its last ~30 days of validity) is enabled and running — the actual
  ongoing renewal, once a certificate already exists from the manual step
  above. This is exactly the "no manual renewal treadmill" outcome the
  review comment asked for, without re-implementing or second-guessing
  grommunio's own certbot integration.

## Not automated (and why)

Grommunio's `grommunio-certbot-renew-hook` deploy-hook itself is not
inspected or modified here — it is installed and owned by the
`grommunio-setup` package, this role only makes sure the timer that would
invoke `certbot renew` (which then calls that hook) actually runs.
