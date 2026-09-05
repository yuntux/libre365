# Sorties consommées par l'inventaire Ansible (étude 4.5 : provisionnement
# Terraform, configuration applicative Ansible) — voir infra/ansible/README.md
# pour la génération de l'inventaire à partir de ces valeurs
# (ex: `terraform output -json > ../ansible/inventory/terraform-outputs.json`,
# consommé par un plugin d'inventaire dynamique ou un script de rendu Jinja).

output "grommunio_ip" {
  description = "Adresse IP statique de la VM Grommunio"
  value       = split("/", var.grommunio_static_ip)[0]
}

output "k8s_control_plane_ips" {
  description = "Adresses IP statiques des nœuds control-plane Kubernetes, dans l'ordre"
  value       = [for ip in var.kubernetes_control_plane_static_ips : split("/", ip)[0]]
}

output "k8s_control_plane_names" {
  description = "Noms Proxmox des nœuds control-plane Kubernetes"
  value       = [for vm in proxmox_virtual_environment_vm.k8s_control_plane : vm.name]
}

output "k8s_worker_names" {
  description = "Noms Proxmox des nœuds worker Kubernetes"
  value       = [for vm in proxmox_virtual_environment_vm.k8s_worker : vm.name]
}

output "k8s_worker_count" {
  description = "Nombre de workers Kubernetes provisionnés pour l'échelle courante"
  value       = local.sizing.k8s_worker_count
}

output "deployment_scale_applied" {
  description = "Échelle de dimensionnement effectivement appliquée (100 ou 2000)"
  value       = var.deployment_scale
}

output "ansible_inventory_hint" {
  description = "Rappel : générer l'inventaire Ansible depuis ces sorties plutôt que le maintenir à la main"
  value       = "cd ../ansible && ./scripts/render-inventory-from-terraform.sh"
}
