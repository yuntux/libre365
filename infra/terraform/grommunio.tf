# Grommunio — étude 4.3, "Exception assumée : Grommunio en VM appliance".
#
# Grommunio propose un packaging conteneur officiel (grommunio/gromox-container),
# mais sa propre documentation le présente comme réservé à des besoins spéciaux,
# pas prêt pour la production par défaut, et bundlant de nombreux services sous
# un seul processus supervisord — sans la décomposition en microservices qui
# s'orchestre naturellement dans Kubernetes. L'appliance (VM complète, ISO) reste
# le mode de déploiement le plus mature documenté par l'éditeur. Grommunio est
# donc déployé ici comme VM Proxmox dédiée, à part du cluster Kubernetes
# (kubernetes_nodes.tf), et bénéficie au passage de la HA au niveau hyperviseur
# (cluster Proxmox, migration à chaud — 4.2) plutôt que d'une HA applicative.
#
# La configuration post-déploiement (GAL_ENABLED/GAL_CACHE_TTL, désactivation de
# l'admin web, EWS/EAS/MAPI) est portée par Ansible, pas par Terraform — voir
# infra/ansible/playbooks/grommunio.yml (étude 4.5 : provisionnement Terraform,
# configuration applicative Ansible).

resource "proxmox_virtual_environment_vm" "grommunio" {
  name        = "${local.name_prefix}-grommunio"
  description = "Appliance Grommunio (VM dédiée, hors cluster Kubernetes — étude 4.3)"
  tags        = ["libre365", "grommunio", "mail", var.environment]

  node_name = var.proxmox_node_names[0] # priorité de placement sur le 1er nœud physique : service à état, pas de vMotion à chaud automatique voulu ici

  # Grommunio publie une ISO d'appliance complète (Debian pré-configuré +
  # installeur Grommunio) : on démarre sur cette ISO plutôt que sur une cloud
  # image générique + provisioning applicatif, conformément au mode de
  # déploiement le plus mature documenté par l'éditeur (4.3).
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

  # IP statique : Grommunio est un service critique et à état (mailbox, GAL
  # CardDAV — 2.13), son adresse doit rester stable pour l'inventaire Ansible
  # et les enregistrements DNS/MX pointant vers lui.
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

  # L'appliance Grommunio embarque son propre installeur post-boot (Ansible
  # ne peut piloter la VM qu'une fois l'appliance installée et son SSH exposé) :
  # la première installation reste semi-interactive côté ISO, documentée dans
  # infra/terraform/README.md.
  lifecycle {
    ignore_changes = [
      cdrom, # ne pas remonter l'ISO d'installation après le premier provisioning
    ]
  }
}

output "grommunio_vm_id" {
  description = "ID Proxmox de la VM Grommunio"
  value       = proxmox_virtual_environment_vm.grommunio.vm_id
}
