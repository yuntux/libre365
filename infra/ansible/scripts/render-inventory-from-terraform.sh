#!/usr/bin/env bash
# Génère inventory/hosts.ini à partir des sorties Terraform (grommunio.tf,
# kubernetes_nodes.tf), plutôt que de le maintenir à la main — étude 4.5 :
# "provisionnement Terraform, configuration applicative Ansible, sur le même
# dépôt". Nécessite `terraform`/`tofu` initialisé et un state à jour dans
# infra/terraform/, ainsi que `jq`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../../terraform"
INVENTORY_DIR="${SCRIPT_DIR}/../inventory"
INVENTORY_FILE="${INVENTORY_DIR}/hosts.ini"

TF_BIN="$(command -v tofu || command -v terraform || true)"
if [[ -z "${TF_BIN}" ]]; then
  echo "Ni tofu ni terraform trouvés dans le PATH." >&2
  exit 1
fi

OUTPUTS_JSON="$("${TF_BIN}" -chdir="${TERRAFORM_DIR}" output -json)"

GROMMUNIO_IP="$(echo "${OUTPUTS_JSON}" | jq -r '.grommunio_ip.value')"
CP_IPS="$(echo "${OUTPUTS_JSON}" | jq -r '.k8s_control_plane_ips.value[]')"
CP_NAMES="$(echo "${OUTPUTS_JSON}" | jq -r '.k8s_control_plane_names.value[]')"

{
  echo "# Généré automatiquement par render-inventory-from-terraform.sh — ne pas éditer à la main."
  echo
  echo "[grommunio]"
  echo "grommunio-vm ansible_host=${GROMMUNIO_IP} ansible_user=root"
  echo
  echo "[k8s_control_plane]"
  paste -d' ' <(echo "${CP_NAMES}") <(echo "${CP_IPS}") | while read -r name ip; do
    echo "${name} ansible_host=${ip} ansible_user=debian"
  done
  echo
  echo "[control_apis]"
  echo "localhost ansible_connection=local"
  echo
  echo "[keycloak:children]"
  echo "control_apis"
  echo
  echo "[matrix:children]"
  echo "control_apis"
  echo
  echo "[seafile:children]"
  echo "control_apis"
  echo
  echo "[onlyoffice:children]"
  echo "control_apis"
} > "${INVENTORY_FILE}"

echo "Inventaire généré : ${INVENTORY_FILE}"
