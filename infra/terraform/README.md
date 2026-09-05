# Terraform/OpenTofu — infrastructure Proxmox

Matérialise l'infrastructure décrite au chapitre 4 de l'étude
(`sortie-office365-etude.md`) : hyperviseur **Proxmox VE**, provider
**`bpg/proxmox`** (4.2), VM appliance **Grommunio** hors cluster Kubernetes
(4.3, "Exception assumée"), nœuds du cluster **Kubernetes** cible de
production (4.4).

Ce code n'est **pas appliqué** dans ce dépôt : aucune infrastructure Proxmox
réelle n'y est associée, et **aucune credential n'y est committée**.

## Fichiers

| Fichier | Rôle |
|---|---|
| `versions.tf` | Provider `bpg/proxmox`, backend (local par défaut, exemple S3/MinIO en commentaire) |
| `variables.tf` | Toutes les variables d'entrée, dont `deployment_scale` (`"100"` / `"2000"`) |
| `locals.tf` | Table de dimensionnement par échelle (`sizing_by_scale`), reprenant les chiffres de l'étude (1.1, 1.2, 1.7) |
| `grommunio.tf` | VM appliance Grommunio (ISO), dimensionnée par `local.sizing.grommunio` |
| `kubernetes_nodes.tf` | Nœuds control-plane + workers du cluster Kubernetes, nombre de workers dérivé de `deployment_scale` |
| `network.tf` | Modèle d'interface réseau (bridge/VLAN) partagé par les VM |
| `outputs.tf` | IPs et noms de VM à consommer par l'inventaire Ansible |
| `terraform.tfvars.example` | Valeurs d'exemple à copier en `terraform.tfvars` (jamais committé) |

## Prérequis avant un `terraform apply` réel

1. Un cluster Proxmox VE joignable (`proxmox_endpoint`), avec un jeton d'API
   dédié (`user@realm!tokenid=uuid`, permissions `VM.Allocate`,
   `Datastore.AllocateSpace`, `Sys.Modify` a minima).
2. Une image ISO d'appliance Grommunio déjà téléversée sur le storage ISO du
   nœud Proxmox, référencée par `grommunio_iso_file_id`.
3. Une cloud image (Debian/Ubuntu) téléversée ou importable, référencée par
   `kubernetes_cloud_image_file_id`.
4. Un VLAN/bridge réseau existant côté hyperviseur (`network_bridge`,
   `network_vlan_id`) — ce dépôt ne configure pas la couche réseau physique
   du nœud Proxmox lui-même, seulement les interfaces des VM.

## Utilisation

```bash
cp terraform.tfvars.example terraform.tfvars
# éditer terraform.tfvars avec les vraies valeurs de l'environnement cible —
# ne jamais committer ce fichier (déjà exclu via .gitignore à la racine du dépôt)

tofu init
tofu plan -var-file=terraform.tfvars
tofu apply -var-file=terraform.tfvars   # non exécuté dans le cadre de ce dépôt
```

Le provider retenu (`bpg/proxmox`) fonctionne indifféremment avec Terraform
ou OpenTofu ; les exemples ci-dessus utilisent `tofu`, substituer `terraform`
si préféré.

## Secrets

`proxmox_api_token` est marquée `sensitive` mais **reste en clair dans l'état
Terraform** comme toute variable sensible native — cohérent avec l'étude
4.5 ("gestion des secrets externalisée dans un coffre-fort dédié, jamais en
clair dans le dépôt de code") : en production, ce jeton doit être injecté via
une variable d'environnement (`TF_VAR_proxmox_api_token`) alimentée par le
coffre-fort (Vault ou équivalent), jamais écrit dans `terraform.tfvars` sur un
poste ou un runner CI.

## Trajectoire de croissance (100 → 2000 → au-delà)

- `deployment_scale = "100"` ou `"2000"` pilote entièrement le dimensionnement
  des VM (`locals.tf`) et le nombre de workers Kubernetes — aucune autre
  variable à modifier pour ce palier.
- **Au-delà de 2000 utilisateurs**, l'étude documente des changements de
  *topologie*, pas une simple extrapolation de ces chiffres :
  - Grommunio : bascule vers l'architecture multi-serveurs "share-nothing"
    documentée par l'éditeur (cluster Corosync/Pacemaker) plutôt qu'une VM
    appliance unique surdimensionnée (1.1) — nécessiterait un nouveau fichier
    `grommunio-cluster.tf` distinct de `grommunio.tf`.
  - Matrix/Synapse : bascule en mode "workers" (déjà retenu comme cible dès la
    conception, 1.2) — le pod Synapse unique devient plusieurs déploiements
    Kubernetes spécialisés, sans changement côté Terraform (le cluster
    Kubernetes absorbe la charge par ajout de workers).

## Backend d'état distant

Le backend local (par défaut, `versions.tf`) convient à un usage
mono-exploitant. Pour une équipe ou un pipeline CI/CD (chapitre 5), activer le
backend S3 commenté dans `versions.tf`, pointé vers une instance **MinIO**
auto-hébergée — cohérent avec le choix déjà fait pour la plateforme vidéo
d'entreprise (étude 2.12) plutôt que d'introduire un service cloud tiers
supplémentaire pour le seul état Terraform.
