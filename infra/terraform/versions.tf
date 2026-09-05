# Provider Proxmox retenu explicitement par l'étude (chapitre 4.2) : bpg/proxmox,
# provider Terraform/OpenTofu mature permettant de décrire les VM Proxmox de façon
# déclarative (nœuds Kubernetes + VM appliance Grommunio, cf. 4.3).
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.66"
    }
  }

  # Backend local par défaut (adapté au dépôt seul, sans dépendance externe).
  # Pour un usage en équipe/CI, préférer un backend distant partagé afin d'éviter
  # les conflits d'état entre exploitants (cohérent avec l'exigence de
  # reconstruction depuis le dépôt seul, chapitre 4.1) :
  #
  # backend "s3" {
  #   endpoints                  = { s3 = "https://minio.example.internal:9000" }
  #   bucket                     = "open365-terraform-state"
  #   key                        = "proxmox/terraform.tfstate"
  #   region                     = "us-east-1" # valeur imposée par le provider S3, sans effet chez MinIO
  #   skip_credentials_validation = true
  #   skip_region_validation      = true
  #   skip_metadata_api_check     = true
  #   use_path_style              = true
  # }
}

provider "proxmox" {
  endpoint  = var.proxmox_endpoint
  api_token = var.proxmox_api_token
  insecure  = var.proxmox_tls_insecure

  ssh {
    agent    = true
    username = var.proxmox_ssh_username
  }
}
