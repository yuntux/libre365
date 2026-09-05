# Variables de dimensionnement — étude chapitre 4.1 : "monter en charge de 100 à
# plusieurs milliers de consultants doit se traduire par une simple variation de
# ces paramètres [...], jamais par une réécriture de la définition d'infrastructure".
# Aucune valeur par utilisateur/client n'est codée en dur ici : voir locals.tf pour
# la table de dimensionnement dérivée de deployment_scale.

variable "deployment_scale" {
  description = <<-EOT
    Échelle de référence du déploiement, alignée sur les deux paliers objectivés
    par l'étude (introduction et chapitre 1) : "100" (effectif actuel) ou "2000"
    (première marche de la trajectoire de croissance). Pilote le dimensionnement
    de chaque VM via la map locale sizing_by_scale (locals.tf) — au-delà de 2000,
    voir les notes de topologie (cluster Grommunio multi-serveurs, mode workers
    Synapse) plutôt qu'une simple variation de cette variable.
  EOT
  type        = string

  validation {
    condition     = contains(["100", "2000"], var.deployment_scale)
    error_message = "deployment_scale doit valoir \"100\" ou \"2000\" (paliers de référence de l'étude)."
  }
}

variable "environment" {
  description = "Nom de l'environnement (dev, recette, production — chapitre 4.6). Utilisé comme préfixe de nommage des ressources Proxmox."
  type        = string
  default     = "production"
}

variable "proxmox_endpoint" {
  description = "URL de l'API Proxmox VE (ex: https://pve1.example.internal:8006/)."
  type        = string
}

variable "proxmox_api_token" {
  description = "Jeton d'API Proxmox, au format \"user@realm!tokenid=uuid\". Ne jamais committer de valeur réelle — cf. terraform.tfvars.example et la gestion des secrets externalisée (étude 4.5)."
  type        = string
  sensitive   = true
}

variable "proxmox_ssh_username" {
  description = "Utilisateur SSH utilisé par le provider bpg/proxmox pour les opérations nécessitant un accès direct au nœud (upload d'ISO/cloud-init)."
  type        = string
  default     = "root"
}

variable "proxmox_tls_insecure" {
  description = "Désactive la vérification TLS vers l'API Proxmox (à réserver à un lab de recette avec certificat auto-signé, jamais en production)."
  type        = bool
  default     = false
}

variable "proxmox_node_names" {
  description = <<-EOT
    Liste des nœuds physiques du cluster Proxmox sur lesquels répartir les VM
    (étude 4.2 : cluster Proxmox à plusieurs nœuds physiques pour la haute
    disponibilité au niveau hyperviseur). Les VM sont réparties par round-robin
    sur cette liste.
  EOT
  type        = list(string)
}

variable "network_bridge" {
  description = "Bridge réseau Proxmox (vmbr) auquel rattacher les interfaces des VM."
  type        = string
  default     = "vmbr0"
}

variable "network_vlan_id" {
  description = "VLAN tag appliqué aux interfaces réseau des VM de la stack (0 = pas de VLAN dédié). Voir network.tf."
  type        = number
  default     = 0
}

variable "storage_pool" {
  description = "Nom du storage Proxmox (ex: local-lvm, ceph-pool) utilisé pour les disques des VM."
  type        = string
  default     = "local-lvm"
}

variable "storage_pool_iso" {
  description = "Nom du storage Proxmox utilisé pour héberger les images ISO/cloud-init."
  type        = string
  default     = "local"
}

variable "ssh_public_keys" {
  description = "Clés publiques SSH injectées via cloud-init dans chaque VM (accès Ansible, étude 4.5)."
  type        = list(string)
}

variable "grommunio_iso_file_id" {
  description = <<-EOT
    Identifiant Proxmox (datastore:iso/fichier.iso) de l'image d'appliance
    Grommunio téléversée au préalable sur le storage ISO. Grommunio est déployé
    en VM appliance et non en conteneur Kubernetes — choix explicite de l'étude,
    section 4.3 ("Exception assumée : Grommunio en VM appliance").
  EOT
  type        = string
  default     = "local:iso/grommunio-appliance.iso"
}

variable "kubernetes_cloud_image_file_id" {
  description = "Identifiant Proxmox (datastore:iso/fichier.img) de l'image cloud (ex: Debian/Ubuntu cloud image) utilisée comme disque de base pour les VM du cluster Kubernetes, importée via cloud-init."
  type        = string
  default     = "local:iso/debian-12-generic-amd64.qcow2"
}

variable "grommunio_static_ip" {
  description = "Adresse IP statique (CIDR, ex: 10.10.0.10/24) réservée à la VM Grommunio — service critique nécessitant une adresse stable (étude 2.13, GAL CardDAV ; 1.1, mailbox)."
  type        = string
}

variable "kubernetes_control_plane_static_ips" {
  description = "Liste d'adresses IP statiques (CIDR) réservées aux nœuds control-plane Kubernetes, une par nœud du plan de contrôle (locals.sizing.k8s_control_plane_count)."
  type        = list(string)
}

variable "network_gateway" {
  description = "Passerelle réseau (IP) utilisée par les VM en IP statique."
  type        = string
}

variable "network_dns_servers" {
  description = "Serveurs DNS injectés via cloud-init."
  type        = list(string)
  default     = ["1.1.1.1", "9.9.9.9"]
}
