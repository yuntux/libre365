# Sizing table by deployment scale (100 / 2000 users).
# Each block explicitly reuses the figures sized by the study; beyond 2000,
# the study documents a topology change ("share-nothing" Grommunio cluster,
# Synapse workers mode) rather than a simple linear extrapolation of these
# figures — see the comments per component.
locals {
  sizing_by_scale = {
    "100" = {
      # Grommunio (study 1.1, line ~56): "100 users: ~4-8 GB RAM / 4 cores".
      # High-end value kept as a precaution (large mailboxes from the start).
      grommunio = {
        cpu_cores = 4
        memory_mb = 8192
        disk_gb   = 200 # sized by mailbox size, not by connection count (1.1)
      }

      # Keycloak (study 1.7, line ~271): "2-4 cores / 4-8 GB RAM with a
      # dedicated Postgres database, for both scales (100 and 2000 users)".
      # Sizing therefore deliberately does not vary with scale for this
      # component: the sizing factor is authentication throughput, not the
      # total headcount.
      keycloak = {
        cpu_cores = 2
        memory_mb = 4096
        disk_gb   = 40
      }

      # Kubernetes cluster hosting the rest of the containerized components
      # (4.3/4.4). 3 workers minimum from 100 users onward to natively have
      # the high availability targeted for Synapse/Keycloak/OnlyOffice (see
      # 1.2, 1.5, 1.7).
      k8s_control_plane_count = 3
      k8s_control_plane = {
        cpu_cores = 2
        memory_mb = 4096
        disk_gb   = 60
      }
      k8s_worker_count = 3
      k8s_worker = {
        cpu_cores = 4
        memory_mb = 8192
        disk_gb   = 100
      }

      # Matrix/Synapse + Postgres (study 1.2, line ~87): "100 users:
      # ~2 CPU / 2 GB (Synapse) + 2 CPU / 6 GB (Postgres)" — official Element
      # sizing, reused as-is as the reference load for sizing the Kubernetes
      # workers that will host these pods (not dedicated VMs: Matrix is
      # containerized, see 4.3).
      matrix_synapse = {
        cpu_cores = 2
        memory_mb = 2048
      }
      matrix_postgres = {
        cpu_cores = 2
        memory_mb = 6144
      }
    }

    "2000" = {
      # Grommunio (study 1.1, line ~57): "2000 users: ~16-32 GB RAM / 8+
      # cores, generous disk storage". High-end value kept, storage increased
      # accordingly (mailbox size is the real sizing factor).
      grommunio = {
        cpu_cores = 8
        memory_mb = 32768
        disk_gb   = 2000
      }

      keycloak = {
        cpu_cores = 4
        memory_mb = 8192
        disk_gb   = 60
      }

      # Expanded Kubernetes cluster: control plane still at 3 nodes (standard
      # etcd quorum, no need to exceed that at this tier), workers expanded to
      # absorb Synapse in workers mode (1.2), the OnlyOffice cluster (1.5) and
      # the Keycloak cluster (1.7) at this scale.
      k8s_control_plane_count = 3
      k8s_control_plane = {
        cpu_cores = 4
        memory_mb = 8192
        disk_gb   = 80
      }
      k8s_worker_count = 6
      k8s_worker = {
        cpu_cores = 8
        memory_mb = 16384
        disk_gb   = 200
      }

      # Matrix/Synapse + Postgres (study 1.2, line ~88): "2000 users:
      # ~6 CPU / 5.6 GB (Synapse) + 4 CPU / 18 GB (Postgres)" — official
      # Element recommendations reused as-is. Synapse workers mode
      # (recommended from the design stage, 1.2) spreads this total across
      # several pods.
      matrix_synapse = {
        cpu_cores = 6
        memory_mb = 5734 # ~5.6 GB
      }
      matrix_postgres = {
        cpu_cores = 4
        memory_mb = 18432
      }
    }
  }

  sizing = local.sizing_by_scale[var.deployment_scale]

  # Round-robin distribution of VMs across the physical nodes of the Proxmox
  # cluster (study 4.2: multi-node Proxmox cluster for HA at the hypervisor
  # level).
  proxmox_node_count = length(var.proxmox_node_names)

  name_prefix = "${var.environment}-libre365"
}
