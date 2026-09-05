# Terraform/OpenTofu — Proxmox infrastructure

Materializes the infrastructure described in chapter 4 of the study
(`office365-exit-study.md`): **Proxmox VE** hypervisor, **`bpg/proxmox`**
provider (4.2), **Grommunio** appliance VM outside the Kubernetes cluster
(4.3, "Assumed exception"), production-target **Kubernetes** cluster nodes
(4.4).

This code is **not applied** in this repository: no real Proxmox
infrastructure is associated with it, and **no credentials are committed**.

## Files

| File | Role |
|---|---|
| `versions.tf` | `bpg/proxmox` provider, backend (local by default, S3/MinIO example in a comment) |
| `variables.tf` | All input variables, including `deployment_scale` (`"100"` / `"2000"`) |
| `locals.tf` | Sizing table by scale (`sizing_by_scale`), reusing the study's figures (1.1, 1.2, 1.7) |
| `grommunio.tf` | Grommunio appliance VM (ISO), sized via `local.sizing.grommunio` |
| `kubernetes_nodes.tf` | Kubernetes cluster control-plane + worker nodes, worker count derived from `deployment_scale` |
| `network.tf` | Network interface model (bridge/VLAN) shared by the VMs |
| `outputs.tf` | VM IPs and names to be consumed by the Ansible inventory |
| `terraform.tfvars.example` | Example values to copy to `terraform.tfvars` (never committed) |

## Prerequisites before a real `terraform apply`

1. A reachable Proxmox VE cluster (`proxmox_endpoint`), with a dedicated API
   token (`user@realm!tokenid=uuid`, `VM.Allocate`, `Datastore.AllocateSpace`,
   `Sys.Modify` permissions at a minimum).
2. A Grommunio appliance ISO image already uploaded to the ISO storage of the
   Proxmox node, referenced by `grommunio_iso_file_id`.
3. A cloud image (Debian/Ubuntu) uploaded or importable, referenced by
   `kubernetes_cloud_image_file_id`.
4. An existing network VLAN/bridge on the hypervisor side (`network_bridge`,
   `network_vlan_id`) — this repository does not configure the physical
   network layer of the Proxmox node itself, only the VM interfaces.

## Usage

```bash
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with the real values of the target environment —
# never commit this file (already excluded via .gitignore at the repo root)

tofu init
tofu plan -var-file=terraform.tfvars
tofu apply -var-file=terraform.tfvars   # not run as part of this repository
```

The chosen provider (`bpg/proxmox`) works equally well with Terraform or
OpenTofu; the examples above use `tofu`, substitute `terraform` if preferred.

## Secrets

`proxmox_api_token` is marked `sensitive` but **remains in plaintext in the
Terraform state** like any native sensitive variable — consistent with study
section 4.5 ("secrets management externalized to a dedicated vault, never in
plaintext in the code repository"): in production, this token must be
injected via an environment variable (`TF_VAR_proxmox_api_token`) fed by the
vault (Vault or equivalent), never written to `terraform.tfvars` on a
workstation or a CI runner.

## Growth trajectory (100 → 2000 → beyond)

- `deployment_scale = "100"` or `"2000"` fully drives the VM sizing
  (`locals.tf`) and the number of Kubernetes workers — no other variable
  needs to be changed for this tier.
- **Beyond 2000 users**, the study documents *topology* changes, not a
  simple extrapolation of these figures:
  - Grommunio: switches to the multi-server "share-nothing" architecture
    documented by the vendor (Corosync/Pacemaker cluster) rather than a
    single oversized appliance VM (1.1) — would require a new
    `grommunio-cluster.tf` file distinct from `grommunio.tf`.
  - Matrix/Synapse: switches to "workers" mode (already chosen as the target
    from the design stage, 1.2) — the single Synapse pod becomes several
    specialized Kubernetes deployments, with no change on the Terraform side
    (the Kubernetes cluster absorbs the load by adding workers).

## Remote state backend

The local backend (default, `versions.tf`) is suitable for a single-operator
use case. For a team or a CI/CD pipeline (chapter 5), enable the S3 backend
commented out in `versions.tf`, pointing to a self-hosted **MinIO**
instance — consistent with the choice already made for the enterprise video
platform (study 2.12) rather than introducing an additional third-party
cloud service for Terraform state alone.
