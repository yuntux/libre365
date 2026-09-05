# Réseau — étude 4.2/4.5 : les VM critiques (Grommunio, control-plane Kubernetes)
# reçoivent une adresse IP statique plutôt qu'un bail DHCP, pour rester joignables
# de façon stable par l'inventaire Ansible (4.5) et par le GAL CardDAV (2.13, qui
# dépend de la disponibilité continue de grommunio-dav sur une adresse connue).
#
# Le bridge/VLAN eux-mêmes (vmbr, tagging 802.1Q) sont supposés déjà configurés
# côté hyperviseur Proxmox (hors périmètre du provider bpg/proxmox, qui gère les
# VM mais pas la configuration réseau des nœuds physiques) — ce fichier ne fait
# que référencer le bridge/VLAN cible dans les définitions d'interface des VM.

locals {
  # Gabarit d'interface réseau réutilisé par chaque ressource VM (grommunio.tf,
  # kubernetes_nodes.tf) : un seul point de vérité pour bridge + VLAN.
  network_interface_template = {
    bridge   = var.network_bridge
    vlan_id  = var.network_vlan_id != 0 ? var.network_vlan_id : null
    firewall = true
  }
}

# Rien à provisionner ici au sens strict du provider bpg/proxmox (pas de
# ressource "réseau" dédiée côté API PVE en dehors des VM elles-mêmes) : ce
# fichier documente et centralise le modèle d'adressage IP statique consommé
# par grommunio.tf et kubernetes_nodes.tf via les variables
# grommunio_static_ip / kubernetes_control_plane_static_ips.
