#!/usr/bin/env bash
# libre365 - verify external-dns correctly reads the Caddy Service's
# external-dns.alpha.kubernetes.io/hostname annotation and computes a DNS
# record for every expected hostname, WITHOUT touching a real DNS provider.
#
# Run after ./deploy.sh (which installs external-dns with the `inmemory`
# provider via infra/k8s/helm-values/dev/external-dns.yaml, and applies the
# real infra/k8s/manifests/caddy.yaml so its Service carries the exact
# production annotation - see deploy.sh's own comment on that step).
#
# This validates the annotation-parsing/record-computation logic end to
# end - it does NOT validate that a real DNS provider (OVH) would actually
# apply the change; see dev-cluster/README.md, "Testing DNS record
# computation", for why that half can only be checked against a real OVH
# account in an actual deployment.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

NAMESPACE="libre365"

# Every domain expected to be covered, straight from platform.yaml - stays
# correct automatically if a domain is ever added/removed there, no
# hand-maintained duplicate list to drift (mirrors
# scripts/sync_platform.py's own DOMAINS_WITHOUT_CADDY_SITE exclusion).
EXPECTED_DOMAINS="$(python3 - <<'PYEOF'
import sys
sys.path.insert(0, "scripts")
import yaml
from sync_platform import DOMAINS_WITHOUT_CADDY_SITE

with open("platform.yaml") as f:
    platform = yaml.safe_load(f)

domains = platform["domains"]
base = domains["base"]
for key, subdomain in domains["subdomains"].items():
    if key not in DOMAINS_WITHOUT_CADDY_SITE:
        print(f"{subdomain}.{base}")
PYEOF
)"

echo "==> Waiting for external-dns to be ready"
kubectl rollout status deployment/external-dns -n "$NAMESPACE" --timeout=120s

echo "==> Waiting for at least one reconcile pass to be logged"
sleep 10 # external-dns's default --interval is 1m; --once isn't set here,
         # so give the first pass a moment rather than polling logs empty.

logs="$(kubectl logs deployment/external-dns -n "$NAMESPACE" --tail=500)"

failures=0
for domain in $EXPECTED_DOMAINS; do
  if echo "$logs" | grep -qi "$domain"; then
    echo "    OK   $domain"
  else
    echo "    MISSING   $domain (not found in external-dns logs)"
    failures=$((failures + 1))
  fi
done

if [ "$failures" -gt 0 ]; then
  echo
  echo "==> $failures domain(s) missing from external-dns's logs - showing recent log output for context:"
  echo "$logs" | tail -50
  exit 1
fi

echo
echo "All expected domains were seen by external-dns (inmemory provider - no real DNS changed)."
