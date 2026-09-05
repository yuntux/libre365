# Cluster Kubernetes — étude 4.4 : orchestrateur retenu dès la conception
# initiale (100 utilisateurs) pour que la montée en charge vers 2000+ se
# traduise par un ajout de nœuds/réplicas plutôt qu'une migration
# d'orchestrateur en cours de croissance. Les nœuds sont des VM Proxmox (4.2),
# pas de déploiement bare-metal.
#
# Le nombre de workers est dérivé de deployment_scale (locals.sizing) : 3 pour
# 100 utilisateurs, 6 pour 2000 — cf. locals.tf pour la table complète.
# Le control-plane reste à 3 nœuds sur les deux paliers (quorum etcd standard).
#
# Bootstrap : cloud-init installe les prérequis (containerd, kubeadm) ; le
# bootstrap effectif du cluster (kubeadm init/join, CNI) est ensuite piloté par
# Ansible (infra/ansible/playbooks/kubernetes.yml, hors périmètre de ce dépôt à
# ce stade — cf. README) pour rester cohérent avec le partage Terraform
# (infrastructure) / Ansible (configuration) de l'étude 4.5.

locals {
  k8s_cloud_init_common = <<-EOT
    #cloud-config
    package_update: true
    packages:
      - containerd
      - apt-transport-https
      - ca-certificates
      - curl
      - gpg
    write_files:
      - path: /etc/modules-load.d/k8s.conf
        content: |
          overlay
          br_netfilter
      - path: /etc/sysctl.d/k8s.conf
        content: |
          net.bridge.bridge-nf-call-iptables  = 1
          net.bridge.bridge-nf-call-ip6tables = 1
          net.ipv4.ip_forward                 = 1
    runcmd:
      - modprobe overlay
      - modprobe br_netfilter
      - sysctl --system
  EOT
}

resource "proxmox_virtual_environment_vm" "k8s_control_plane" {
  count = local.sizing.k8s_control_plane_count

  name        = "${local.name_prefix}-k8s-cp-${count.index + 1}"
  description = "Nœud control-plane Kubernetes ${count.index + 1}/${local.sizing.k8s_control_plane_count}"
  tags        = ["open365", "kubernetes", "control-plane", var.environment]

  node_name = var.proxmox_node_names[count.index % local.proxmox_node_count]

  cpu {
    cores = local.sizing.k8s_control_plane.cpu_cores
    type  = "host"
  }

  memory {
    dedicated = local.sizing.k8s_control_plane.memory_mb
  }

  disk {
    datastore_id = var.storage_pool
    interface    = "scsi0"
    size         = local.sizing.k8s_control_plane.disk_gb
    ssd          = true
    discard      = "on"
  }

  # Import de la cloud image comme disque de base, plutôt qu'une installation
  # ISO complète — cohérent avec des nœuds sans état à recréer facilement
  # (contrairement à Grommunio, cf. grommunio.tf).
  disk {
    datastore_id = var.storage_pool
    interface    = "scsi1"
    file_format  = "qcow2"
    import_from  = var.kubernetes_cloud_image_file_id
  }

  network_device {
    bridge   = local.network_interface_template.bridge
    vlan_id  = local.network_interface_template.vlan_id
    firewall = local.network_interface_template.firewall
  }

  initialization {
    ip_config {
      ipv4 {
        address = var.kubernetes_control_plane_static_ips[count.index]
        gateway = var.network_gateway
      }
    }

    dns {
      servers = var.network_dns_servers
    }

    user_account {
      keys = var.ssh_public_keys
    }

    user_data_file_id = proxmox_virtual_environment_file.k8s_cloud_init.id
  }

  agent {
    enabled = true
  }
}

resource "proxmox_virtual_environment_vm" "k8s_worker" {
  count = local.sizing.k8s_worker_count

  name        = "${local.name_prefix}-k8s-worker-${count.index + 1}"
  description = "Nœud worker Kubernetes ${count.index + 1}/${local.sizing.k8s_worker_count}"
  tags        = ["open365", "kubernetes", "worker", var.environment]

  node_name = var.proxmox_node_names[count.index % local.proxmox_node_count]

  cpu {
    cores = local.sizing.k8s_worker.cpu_cores
    type  = "host"
  }

  memory {
    dedicated = local.sizing.k8s_worker.memory_mb
  }

  disk {
    datastore_id = var.storage_pool
    interface    = "scsi0"
    size         = local.sizing.k8s_worker.disk_gb
    ssd          = true
    discard      = "on"
  }

  disk {
    datastore_id = var.storage_pool
    interface    = "scsi1"
    file_format  = "qcow2"
    import_from  = var.kubernetes_cloud_image_file_id
  }

  network_device {
    bridge   = local.network_interface_template.bridge
    vlan_id  = local.network_interface_template.vlan_id
    firewall = local.network_interface_template.firewall
  }

  # Les workers restent en DHCP par défaut (pas de dépendance externe critique
  # sur leur adresse — contrairement au control-plane, qui expose l'API server
  # à une IP connue de kubeadm join) ; adapter si le DHCP n'est pas disponible
  # sur le VLAN cible.
  initialization {
    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }

    dns {
      servers = var.network_dns_servers
    }

    user_account {
      keys = var.ssh_public_keys
    }

    user_data_file_id = proxmox_virtual_environment_file.k8s_cloud_init.id
  }

  agent {
    enabled = true
  }
}

resource "proxmox_virtual_environment_file" "k8s_cloud_init" {
  content_type = "snippets"
  datastore_id = var.storage_pool_iso
  node_name    = var.proxmox_node_names[0]

  source_raw {
    data      = local.k8s_cloud_init_common
    file_name = "${local.name_prefix}-k8s-cloud-init.yaml"
  }
}
