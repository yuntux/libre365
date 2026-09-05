# Grommunio — study 4.3, "Assumed exception: Grommunio as an appliance VM".
#
# Grommunio offers an official container package (grommunio/gromox-container),
# but its own documentation presents it as reserved for special needs, not
# production-ready by default, and bundling many services under a single
# supervisord process — without the microservices decomposition that
# naturally orchestrates in Kubernetes. The appliance (full VM, ISO) remains
# the most mature deployment mode documented by the vendor. Grommunio is
# therefore deployed here as a dedicated Proxmox VM, separate from the
# Kubernetes cluster (kubernetes_nodes.tf), and in turn benefits from HA at
# the hypervisor level (Proxmox cluster, live migration — 4.2) rather than
# application-level HA.
#
# Post-deployment configuration (GAL_ENABLED/GAL_CACHE_TTL, disabling the web
# admin, EWS/EAS/MAPI) is carried by Ansible, not Terraform — see
# infra/ansible/playbooks/grommunio.yml (study 4.5: Terraform provisioning,
# Ansible application configuration).

resource "proxmox_virtual_environment_vm" "grommunio" {
  name        = "${local.name_prefix}-grommunio"
  description = "Grommunio appliance (dedicated VM, outside the Kubernetes cluster — study 4.3)"
  tags        = ["libre365", "grommunio", "mail", var.environment]

  node_name = var.proxmox_node_names[0] # placement priority on the 1st physical node: a stateful service, no automatic live vMotion wanted here

  # Grommunio publishes a full appliance ISO (pre-configured Debian +
  # Grommunio installer): we boot from this ISO rather than a generic cloud
  # image + application provisioning, in line with the most mature
  # deployment mode documented by the vendor (4.3).
  cdrom {
    file_id = var.grommunio_iso_file_id
  }

  cpu {
    cores = local.sizing.grommunio.cpu_cores
    type  = "host"
  }

  memory {
    dedicated = local.sizing.grommunio.memory_mb
  }

  disk {
    datastore_id = var.storage_pool
    interface    = "scsi0"
    size         = local.sizing.grommunio.disk_gb
    ssd          = true
    discard      = "on"
  }

  network_device {
    bridge   = local.network_interface_template.bridge
    vlan_id  = local.network_interface_template.vlan_id
    firewall = local.network_interface_template.firewall
  }

  # Static IP: Grommunio is a critical, stateful service (mailbox, CardDAV
  # GAL — 2.13), its address must stay stable for the Ansible inventory and
  # the DNS/MX records pointing to it.
  initialization {
    ip_config {
      ipv4 {
        address = var.grommunio_static_ip
        gateway = var.network_gateway
      }
    }

    dns {
      servers = var.network_dns_servers
    }

    user_account {
      keys = var.ssh_public_keys
    }
  }

  agent {
    enabled = true
  }

  # The Grommunio appliance embeds its own post-boot installer (Ansible can
  # only drive the VM once the appliance is installed and its SSH exposed):
  # the initial installation remains semi-interactive on the ISO side,
  # documented in infra/terraform/README.md.
  lifecycle {
    ignore_changes = [
      cdrom, # do not remount the installation ISO after the initial provisioning
    ]
  }
}

output "grommunio_vm_id" {
  description = "Proxmox ID of the Grommunio VM"
  value       = proxmox_virtual_environment_vm.grommunio.vm_id
}
