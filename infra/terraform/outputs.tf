# Outputs consumed by the Ansible inventory (study 4.5: Terraform
# provisioning, Ansible application configuration) — see
# infra/ansible/README.md for generating the inventory from these values
# (e.g. `terraform output -json > ../ansible/inventory/terraform-outputs.json`,
# consumed by a dynamic inventory plugin or a Jinja rendering script).

output "grommunio_ip" {
  description = "Static IP address of the Grommunio VM"
  value       = split("/", var.grommunio_static_ip)[0]
}

output "k8s_control_plane_ips" {
  description = "Static IP addresses of the Kubernetes control-plane nodes, in order"
  value       = [for ip in var.kubernetes_control_plane_static_ips : split("/", ip)[0]]
}

output "k8s_control_plane_names" {
  description = "Proxmox names of the Kubernetes control-plane nodes"
  value       = [for vm in proxmox_virtual_environment_vm.k8s_control_plane : vm.name]
}

output "k8s_worker_names" {
  description = "Proxmox names of the Kubernetes worker nodes"
  value       = [for vm in proxmox_virtual_environment_vm.k8s_worker : vm.name]
}

output "k8s_worker_count" {
  description = "Number of Kubernetes workers provisioned for the current scale"
  value       = local.sizing.k8s_worker_count
}

output "deployment_scale_applied" {
  description = "Sizing scale actually applied (100 or 2000)"
  value       = var.deployment_scale
}

output "ansible_inventory_hint" {
  description = "Reminder: generate the Ansible inventory from these outputs rather than maintaining it by hand"
  value       = "cd ../ansible && ./scripts/render-inventory-from-terraform.sh"
}
