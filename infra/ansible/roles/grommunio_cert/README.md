# grommunio_cert

Fully automates Let's Encrypt for the Grommunio VM (study 1.9/4.3) —
**both initial issuance and ongoing renewal**, no manual/wizard step.
Closes a gap noted during review: Grommunio (`mail.<domain>` and
`autodiscover.<domain>`, see `docs/clients.md`) is deliberately **not**
Caddy-fronted, so it doesn't benefit from Caddy's own Automatic HTTPS the
way every other public hostname in this repository does — it needs its
own certificate lifecycle, and this repo already has the Ansible tooling
to not leave that as a manual step.

## Verified against grommunio's own documentation, not assumed

`grommunio/grommunio-documentation`'s `admin/installation.rst` and
`admin/quickstart.rst`:

- The appliance's own setup wizard (`grommunio-setup`) offers "Automatic
  generation of certificates with Let's Encrypt" as one of four options,
  backed by **certbot** (not `acme.sh`). Certificates are referenced by
  every service on the appliance once issued and are stored under
  `/etc/grommunio/ssl`.
- The docs' own example for adding several domains to one certificate:

  ```
  certbot certonly -n --standalone --agree-tos --preferred-challenges http \
    --cert-name="<domain1>" -d "<domain1>" -d "<domain2>" \
    --deploy-hook /usr/share/grommunio-setup/grommunio-certbot-renew-hook
  ```

  `-n` (non-interactive) confirms this command was always scriptable —
  nothing about certbot itself requires going through the wizard. This
  role runs exactly this shape of command (see `tasks/main.yml`), covering
  `mail.<domain>` and `autodiscover.<domain>` as one multi-domain
  certificate, with `--register-unsafely-without-email` added so the
  account-registration step (which does prompt interactively without an
  email) doesn't block either.

## What this role does

1. Installs `certbot`.
2. Issues the initial certificate — `ansible.builtin.command` with
   `creates: /etc/letsencrypt/live/<cert-name>/fullchain.pem`, so a
   re-run is a no-op once the certificate exists (idempotent, safe to
   include in every playbook run).
3. Ensures `certbot.timer` (the standard systemd timer shipped by
   Debian/Ubuntu's `certbot` package, running `certbot renew` twice
   daily and only actually renewing a certificate in its last ~30 days
   of validity) is enabled and running.

`--pre-hook`/`--post-hook` briefly stop/start `gromox-http.service`
around the HTTP-01 challenge (certbot needs port 80 to itself for a few
seconds) — the same unit name already used elsewhere in this repo
(`infra/ansible/playbooks/grommunio.yml`), reasoned by analogy rather than
independently re-verified against a live appliance. These hooks are
certbot's own standard mechanism and get saved into its renewal
configuration automatically, so every future `certbot renew` (via
`certbot.timer`) reuses them with no separate renewal-specific wiring.

## Known residual risk (not a manual step, but worth knowing)

If `gromox-http.service` briefly failing to stop/restart around a renewal
ever caused an issue, that would only surface at actual renewal time
(months out) rather than at first deploy — worth a one-time check in
staging that the pre/post hooks work as expected on the real appliance,
since this repo has no live Grommunio instance to test against.
