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
  @echo "  just install              - Install Ansible dependencies"
  @echo "  just ping                 - Test connectivity to all nodes"
  @echo "  just deploy               - Deploy the complete cluster"
  @echo "  just verify               - Run cluster verification checks"
  @echo "  just maintenance          - Run maintenance operations"
  @echo "  just troubleshoot         - Diagnose cluster issues"
  @echo "  just fix-nodes            - Fix NotReady nodes"
  @echo "  just reset                - Reset the entire cluster (WARNING: destructive)"
  @echo "  just test                 - Run connectivity and health tests"
  @echo "  just clean                - Clean up CNI bridges and restart services"
  @echo "  just lint                 - Run ansible-lint on playbooks"
  @echo "  just format               - Auto-fix ansible formatting issues"
  @echo "  just status               - Check cluster node and pod status"
  @echo "  just wireguard            - Check WireGuard connectivity"
  @echo "  just logs                 - View recent kubelet logs"
  @echo "  just reconfigure-wireguard- Reconfigure WireGuard across all nodes"
  @echo ""
  @echo "Examples:"
  @echo "  just deploy        # Full cluster deployment"
  @echo "  just verify        # Quick health check"
  @echo "  just troubleshoot  # Diagnose issues"
  @echo "  just fix-nodes     # Fix NotReady nodes"

# Install Ansible dependencies
install:
  @echo "Installing Ansible dependencies..."
  uv sync
  uv run ansible-galaxy collection install -r requirements.yml
  @echo "✅ Dependencies installed"

# Test connectivity to all nodes
ping:
  @echo "Testing connectivity to all nodes..."
  uv run ansible all -i inventory.yml -m ping
  @echo "✅ Connectivity test complete"

# Deploy the complete cluster
deploy:
  @echo "Deploying Kubernetes cluster with WireGuard..."
  uv run ansible-playbook -i inventory.yml site.yml
  @echo "✅ Cluster deployment complete"

# Reconfigure WireGuard across all nodes
reconfigure-wireguard:
  @echo "Reconfiguring WireGuard across all nodes..."
  uv run ansible-playbook -i inventory.yml site.yml --tags wireguard
  @echo "✅ WireGuard reconfiguration complete"

# Run cluster verification
verify:
  @echo "Running cluster verification..."
  uv run ansible-playbook -i inventory.yml verify.yml
  @echo "✅ Verification complete"

# Run maintenance operations
maintenance:
  @echo "Running maintenance operations..."
  uv run ansible-playbook -i inventory.yml maintenance.yml
  @echo "✅ Maintenance complete"

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

# Run comprehensive tests
test: ping verify
  @echo "✅ All tests complete"

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

# Auto-fix ansible formatting issues
format:
  @echo "Auto-fixing ansible formatting issues..."
  uv run ansible-lint --fix
  @echo "✅ Format complete"

# Check cluster status
status:
  @echo "Checking cluster status..."
  uv run ansible control_plane -i inventory.yml -m shell -a "kubectl get nodes -o wide" --become-user=ubuntu
  uv run ansible control_plane -i inventory.yml -m shell -a "kubectl get pods --all-namespaces | grep -v Running" --become-user=ubuntu || true

# Check WireGuard status
wireguard:
  @echo "Checking WireGuard status..."
  uv run ansible all -i inventory.yml -m shell -a "wg show" --become

# View recent kubelet logs
logs:
  @echo "Checking recent kubelet logs..."
  uv run ansible all -i inventory.yml -m shell -a "journalctl -u kubelet --no-pager -n 20" --become

# Run cluster troubleshooting
troubleshoot:
  @echo "Running cluster troubleshooting..."
  uv run ansible-playbook -i inventory.yml troubleshoot.yml
  @echo "✅ Troubleshooting complete"

# Fix NotReady nodes
fix-nodes:
  @echo "Fixing NotReady nodes..."
  uv run ansible-playbook -i inventory.yml troubleshoot.yml --tags=force_restart
  @echo "✅ Node fix complete"

# Development deployment (with verbose output)
dev-deploy:
  @echo "Development deployment (with verbose output)..."
  uv run ansible-playbook -i inventory.yml site.yml -vv

# Development reset (no confirmation)
dev-reset:
  @echo "Development reset (no confirmation)..."
  uv run ansible-playbook -i inventory.yml reset.yml

# Development testing
dev-test: ping
  @echo "Development testing..."
  uv run ansible-playbook -i inventory.yml verify.yml -v
