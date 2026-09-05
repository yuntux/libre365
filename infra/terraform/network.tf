# Network — study 4.2/4.5: critical VMs (Grommunio, Kubernetes control plane)
# receive a static IP address rather than a DHCP lease, to stay reliably
# reachable by the Ansible inventory (4.5) and by the CardDAV GAL (2.13,
# which depends on grommunio-dav's continuous availability at a known
# address).
#
# The bridge/VLAN themselves (vmbr, 802.1Q tagging) are assumed to already be
# configured on the Proxmox hypervisor side (out of scope for the
# bpg/proxmox provider, which manages VMs but not the network configuration
# of the physical nodes) — this file only references the target bridge/VLAN
# in the VM interface definitions.

locals {
  # Network interface template reused by each VM resource (grommunio.tf,
  # kubernetes_nodes.tf): a single source of truth for bridge + VLAN.
  network_interface_template = {
    bridge   = var.network_bridge
    vlan_id  = var.network_vlan_id != 0 ? var.network_vlan_id : null
    firewall = true
  }
}

# Nothing to provision here strictly speaking from the bpg/proxmox provider's
# point of view (no dedicated "network" resource on the PVE API side outside
# the VMs themselves): this file documents and centralizes the static IP
# addressing model consumed by grommunio.tf and kubernetes_nodes.tf via the
# grommunio_static_ip / kubernetes_control_plane_static_ips variables.
