# Table de dimensionnement par échelle de déploiement (100 / 2000 utilisateurs).
# Chaque bloc reprend explicitement les dimensionnements chiffrés par l'étude ;
# au-delà de 2000, l'étude documente un changement de topologie (cluster
# Grommunio "share-nothing", mode workers Synapse) plutôt qu'une simple
# extrapolation linéaire de ces chiffres — voir les commentaires par brique.
locals {
  sizing_by_scale = {
    "100" = {
      # Grommunio (étude 1.1, ligne ~56) : "100 utilisateurs : ~4-8 Go RAM / 4 cœurs".
      # Valeur haute retenue par prudence (mailbox volumineuses dès le départ).
      grommunio = {
        cpu_cores  = 4
        memory_mb  = 8192
        disk_gb    = 200 # dimensionné par la taille des mailbox, pas par le nb de connexions (1.1)
      }

      # Keycloak (étude 1.7, ligne ~271) : "2-4 cœurs / 4-8 Go RAM avec base Postgres
      # dédiée, pour les deux échelles (100 et 2000 utilisateurs)". Le dimensionnement
      # ne varie donc volontairement pas avec l'échelle pour cette brique : le
      # facteur dimensionnant est le débit d'authentification, pas l'effectif total.
      keycloak = {
        cpu_cores = 2
        memory_mb = 4096
        disk_gb   = 40
      }

      # Cluster Kubernetes portant le reste des briques conteneurisées (4.3/4.4).
      # 3 workers minimum dès 100 utilisateurs pour disposer nativement de la
      # haute disponibilité visée pour Synapse/Keycloak/OnlyOffice (cf. 1.2, 1.5, 1.7).
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

      # Matrix/Synapse + Postgres (étude 1.2, ligne ~87) : "100 utilisateurs :
      # ~2 CPU / 2 Go (Synapse) + 2 CPU / 6 Go (Postgres)" — dimensionnement
      # officiel Element, repris tel quel comme charge de référence pour le
      # sizing des workers Kubernetes qui hébergeront ces pods (pas des VM
      # dédiées : Matrix est conteneurisé, cf. 4.3).
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
      # Grommunio (étude 1.1, ligne ~57) : "2000 utilisateurs : ~16-32 Go RAM /
      # 8+ cœurs, stockage disque généreux". Valeur haute retenue, stockage
      # augmenté en conséquence (taille des mailbox = facteur dimensionnant réel).
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

      # Cluster Kubernetes élargi : plan de contrôle toujours à 3 nœuds (quorum
      # etcd standard, inutile de dépasser pour ce palier), workers étendus pour
      # absorber Synapse en mode workers (1.2), le cluster OnlyOffice (1.5) et
      # le cluster Keycloak (1.7) à cette échelle.
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

      # Matrix/Synapse + Postgres (étude 1.2, ligne ~88) : "2000 utilisateurs :
      # ~6 CPU / 5,6 Go (Synapse) + 4 CPU / 18 Go (Postgres)" — recommandations
      # officielles Element reprises telles quelles. Le mode workers Synapse
      # (recommandé dès la conception, 1.2) répartit ce total sur plusieurs pods.
      matrix_synapse = {
        cpu_cores = 6
        memory_mb = 5734 # ~5,6 Go
      }
      matrix_postgres = {
        cpu_cores = 4
        memory_mb = 18432
      }
    }
  }

  sizing = local.sizing_by_scale[var.deployment_scale]

  # Répartition round-robin des VM sur les nœuds physiques du cluster Proxmox
  # (étude 4.2 : cluster Proxmox multi-nœuds pour la HA au niveau hyperviseur).
  proxmox_node_count = length(var.proxmox_node_names)

  name_prefix = "${var.environment}-open365"
}
