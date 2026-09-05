# Proxmox provider explicitly chosen by the study (chapter 4.2): bpg/proxmox,
# a mature Terraform/OpenTofu provider allowing Proxmox VMs to be described
# declaratively (Kubernetes nodes + Grommunio appliance VM, see 4.3).
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.66"
    }
  }

  # Local backend by default (suitable for a single repository, no external
  # dependency). For team/CI use, prefer a shared remote backend to avoid
  # state conflicts between operators (consistent with the requirement to be
  # rebuildable from the repository alone, chapter 4.1):
  #
  # backend "s3" {
  #   endpoints                  = { s3 = "https://minio.example.internal:9000" }
  #   bucket                     = "libre365-terraform-state"
  #   key                        = "proxmox/terraform.tfstate"
  #   region                     = "us-east-1" # value imposed by the S3 provider, has no effect with MinIO
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
