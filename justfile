# Kubernetes WireGuard Cluster - Ansible Automation
# Run 'just' or 'just help' to see available commands

# Default recipe - show help
default:
  @just help

# Show help menu
help:
  @echo "Kubernetes WireGuard Cluster - Ansible Automation"
  @echo ""
  @echo "Usage:"
  @echo "  just deploy [host]  - Deploy cluster to all hosts or only the specified host"
  @echo "  just reset      - Reset the entire cluster (WARNING: destructive)"
  @echo "  just clean      - Clean up CNI bridges and restart services"
  @echo "  just lint       - Validate all playbooks with ansible-lint"
  @echo ""
  @echo "Examples:"
  @echo "  just deploy           # Full cluster deployment with verification (all hosts)"
  @echo "  just deploy worker-1  # Deploy & verify only on host 'worker-1'"
  @echo "  just reset      # Destroy everything and reset to clean state"
  @echo "  just clean      # Clean CNI interfaces"
  @echo "  just lint       # Check playbook syntax"

# Deploy the complete cluster (runs deployment + verification)
deploy host='':
  @bash -uc '\
    set -euo pipefail; \
    if [ -n "{{host}}" ]; then \
      echo "Deploying Kubernetes cluster with WireGuard... (limit: {{host}})"; \
      LIMIT=( -l "{{host}}" ); \
    else \
      echo "Deploying Kubernetes cluster with WireGuard... (all hosts)"; \
      LIMIT=(); \
    fi; \
    uv run ansible-playbook -i inventory.yml "${LIMIT[@]}" site.yml; \
    echo "✅ Deployment phase complete, running verification..."; \
    uv run ansible-playbook -i inventory.yml "${LIMIT[@]}" verify.yml; \
    echo "✅ Cluster fully deployed and verified"; \
  '

# Reset the entire cluster (destructive!)
reset:
  #!/usr/bin/env bash
  echo "⚠️  WARNING: This will completely destroy the cluster!"
  read -p "Are you sure? Type 'yes' to continue: " confirm
  if [ "$confirm" = "yes" ]; then
    uv run ansible-playbook -i inventory.yml reset.yml
    echo "✅ Cluster reset complete"
  else
    echo "Cancelled"
    exit 1
  fi

# Clean up CNI interfaces and restart services
clean:
  @echo "Cleaning CNI interfaces and restarting services..."
  uv run ansible-playbook -i inventory.yml maintenance.yml --tags=clean-cni
  @echo "✅ Cleanup complete"

# Run ansible-lint on playbooks
lint:
  @echo "Running ansible-lint on playbooks..."
  uv run ansible-lint
  @echo "✅ Lint check complete"
