# Kubernetes cluster — study 4.4: orchestrator chosen from the initial design
# stage (100 users) so that scaling up to 2000+ translates into adding
# nodes/replicas rather than an orchestrator migration mid-growth. The nodes
# are Proxmox VMs (4.2), not a bare-metal deployment.
#
# The worker count is derived from deployment_scale (locals.sizing): 3 for
# 100 users, 6 for 2000 — see locals.tf for the full table. The control plane
# stays at 3 nodes across both tiers (standard etcd quorum).
#
# Bootstrap: cloud-init installs the prerequisites (containerd, kubeadm); the
# actual cluster bootstrap (kubeadm init/join, CNI) is then driven by Ansible
# (infra/ansible/playbooks/kubernetes.yml, out of scope for this repository
# at this stage — see README) to stay consistent with the study's Terraform
# (infrastructure) / Ansible (configuration) split (4.5).

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
  description = "Kubernetes control-plane node ${count.index + 1}/${local.sizing.k8s_control_plane_count}"
  tags        = ["libre365", "kubernetes", "control-plane", var.environment]

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

  # Importing the cloud image as the base disk, rather than a full ISO
  # installation — consistent with stateless nodes that are easy to
  # recreate (unlike Grommunio, see grommunio.tf).
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
  description = "Kubernetes worker node ${count.index + 1}/${local.sizing.k8s_worker_count}"
  tags        = ["libre365", "kubernetes", "worker", var.environment]

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

  # Workers stay on DHCP by default (no critical external dependency on
  # their address — unlike the control plane, which exposes the API server
  # at an address known to kubeadm join); adapt if DHCP is not available on
  # the target VLAN.
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
