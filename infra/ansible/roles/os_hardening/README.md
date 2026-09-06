# `os_hardening` role

Baseline OS-level security hardening applied to every real VM in this
stack (Grommunio, Kubernetes control-plane/worker nodes) — not a numbered
study requirement, added to close a gap noted during review: nothing in
this repository provided SSH brute-force protection or hardened default
SSH settings.

## What it does

- Installs and configures **fail2ban** with a single `sshd` jail (the only
  service in this stack exposed to raw SSH-style brute force — everything
  else sits behind Caddy/Keycloak, see `../../k8s/manifests/caddy.yaml`).
  Progressive ban durations (`bantime.increment`) for repeat offenders
  within a day, rather than one fixed ban length.
- Disables SSH password authentication (`PasswordAuthentication no`) and
  restricts root login to key-based only (`PermitRootLogin
  prohibit-password`) — every host in `inventory/hosts.ini.example`
  already authenticates via the SSH keys injected by cloud-init
  (`infra/terraform`'s `ssh_public_keys` variable), so this closes the
  password-auth attack surface without changing how the inventory itself
  reaches these hosts.

## ⚠️ Before running this role for the first time

**Confirm key-based SSH access already works for every targeted host**
before applying this role. Ansible's own SSH connection stays open for the
rest of the current play even after `PasswordAuthentication no` is
applied, but the *next* connection attempt — Ansible's own on a
subsequent run, or a human's — will fail if that host doesn't actually
have a working authorized key yet. This is exactly why cloud-init/
Terraform provisioning (`ssh_public_keys`) is expected to already be in
place first; this role hardens an existing key-based setup, it does not
create one.

## Main variables (`defaults/main.yml`)

- `os_hardening_fail2ban_ignoreip` — addresses fail2ban never bans
  regardless of failed attempts (defaults to loopback only; add the
  Ansible control host's or an admin's fixed IP here if relevant).
- `os_hardening_fail2ban_ssh_maxretry` / `_findtime` / `_bantime` — the
  `sshd` jail's thresholds.
- `os_hardening_ssh_disable_password_auth`, `os_hardening_ssh_permit_root_login`
  — the two SSH hardening toggles, both on by default.

## Not covered by this role

- **Non-SSH exposed services**: this stack's applications sit behind Caddy
  (TLS termination, see `../../k8s/manifests/caddy.yaml`) or are only
  reachable through Keycloak SSO — a `fail2ban` jail for those would need
  to parse Caddy's own access logs, out of scope here (no numbered study
  requirement covers it either).
- **A general OS CIS-benchmark-style hardening baseline** (kernel
  parameters, auditd, AppArmor/SELinux profiles, etc.) — this role is
  narrowly scoped to the two concrete gaps identified (fail2ban, SSH
  password auth), not a full hardening framework.
