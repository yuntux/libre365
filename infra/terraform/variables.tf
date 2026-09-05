# Sizing variables — study chapter 4.1: "scaling from 100 to several thousand
# consultants must translate into a simple variation of these parameters [...],
# never into a rewrite of the infrastructure definition".
# No per-user/client value is hardcoded here: see locals.tf for the sizing
# table derived from deployment_scale.

variable "deployment_scale" {
  description = <<-EOT
    Reference scale of the deployment, aligned with the two tiers targeted by
    the study (introduction and chapter 1): "100" (current headcount) or
    "2000" (first step of the growth trajectory). Drives the sizing of each
    VM via the local sizing_by_scale map (locals.tf) — beyond 2000, see the
    topology notes (multi-server Grommunio cluster, Synapse workers mode)
    rather than a simple variation of this variable.
  EOT
  type        = string

  validation {
    condition     = contains(["100", "2000"], var.deployment_scale)
    error_message = "deployment_scale must be \"100\" or \"2000\" (the study's reference tiers)."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, production — chapter 4.6). Used as a naming prefix for Proxmox resources."
  type        = string
  default     = "production"
}

variable "proxmox_endpoint" {
  description = "Proxmox VE API URL (e.g. https://pve1.example.internal:8006/)."
  type        = string
}

variable "proxmox_api_token" {
  description = "Proxmox API token, in the format \"user@realm!tokenid=uuid\". Never commit a real value — see terraform.tfvars.example and the externalized secrets management (study 4.5)."
  type        = string
  sensitive   = true
}

variable "proxmox_ssh_username" {
  description = "SSH user used by the bpg/proxmox provider for operations requiring direct node access (ISO/cloud-init upload)."
  type        = string
  default     = "root"
}

variable "proxmox_tls_insecure" {
  description = "Disables TLS verification toward the Proxmox API (reserve for a staging lab with a self-signed certificate, never in production)."
  type        = bool
  default     = false
}

variable "proxmox_node_names" {
  description = <<-EOT
    List of physical nodes in the Proxmox cluster across which to spread the
    VMs (study 4.2: multi-node Proxmox cluster for high availability at the
    hypervisor level). VMs are distributed round-robin across this list.
  EOT
  type        = list(string)
}

variable "network_bridge" {
  description = "Proxmox network bridge (vmbr) to attach VM interfaces to."
  type        = string
  default     = "vmbr0"
}

variable "network_vlan_id" {
  description = "VLAN tag applied to the network interfaces of the stack's VMs (0 = no dedicated VLAN). See network.tf."
  type        = number
  default     = 0
}

variable "storage_pool" {
  description = "Name of the Proxmox storage (e.g. local-lvm, ceph-pool) used for VM disks."
  type        = string
  default     = "local-lvm"
}

variable "storage_pool_iso" {
  description = "Name of the Proxmox storage used to host ISO/cloud-init images."
  type        = string
  default     = "local"
}

variable "ssh_public_keys" {
  description = "SSH public keys injected via cloud-init into each VM (Ansible access, study 4.5)."
  type        = list(string)
}

variable "grommunio_iso_file_id" {
  description = <<-EOT
    Proxmox identifier (datastore:iso/file.iso) of the Grommunio appliance
    image previously uploaded to the ISO storage. Grommunio is deployed as
    an appliance VM rather than a Kubernetes container — an explicit choice
    of the study, section 4.3 ("Assumed exception: Grommunio as an appliance
    VM").
  EOT
  type        = string
  default     = "local:iso/grommunio-appliance.iso"
}

variable "kubernetes_cloud_image_file_id" {
  description = "Proxmox identifier (datastore:iso/file.img) of the cloud image (e.g. Debian/Ubuntu cloud image) used as the base disk for the Kubernetes cluster VMs, imported via cloud-init."
  type        = string
  default     = "local:iso/debian-12-generic-amd64.qcow2"
}

variable "grommunio_static_ip" {
  description = "Static IP address (CIDR, e.g. 10.10.0.10/24) reserved for the Grommunio VM — a critical service needing a stable address (study 2.13, CardDAV GAL; 1.1, mailbox)."
  type        = string
}

variable "kubernetes_control_plane_static_ips" {
  description = "List of static IP addresses (CIDR) reserved for the Kubernetes control-plane nodes, one per control-plane node (locals.sizing.k8s_control_plane_count)."
  type        = list(string)
}

variable "network_gateway" {
  description = "Network gateway (IP) used by VMs with a static IP."
  type        = string
}

variable "network_dns_servers" {
  description = "DNS servers injected via cloud-init."
  type        = list(string)
  default     = ["1.1.1.1", "9.9.9.9"]
}
