.PHONY: help install deploy verify clean reset maintenance test ping troubleshoot fix-nodes lint format

# Default target
help:
	@echo "Kubernetes WireGuard Cluster - Ansible Automation"
	@echo ""
	@echo "Usage:"
	@echo "  make install       - Install Ansible dependencies"
	@echo "  make ping          - Test connectivity to all nodes"
	@echo "  make deploy        - Deploy the complete cluster"
	@echo "  make verify        - Run cluster verification checks"
	@echo "  make maintenance   - Run maintenance operations"
	@echo "  make troubleshoot  - Diagnose cluster issues"
	@echo "  make fix-nodes     - Fix NotReady nodes"
	@echo "  make reset         - Reset the entire cluster (WARNING: destructive)"
	@echo "  make test          - Run connectivity and health tests"
	@echo "  make clean         - Clean up CNI bridges and restart services"
	@echo "  make lint          - Run ansible-lint on playbooks"
	@echo "  make format        - Auto-fix ansible formatting issues"
	@echo ""
	@echo "Examples:"
	@echo "  make deploy        # Full cluster deployment"
	@echo "  make verify        # Quick health check"
	@echo "  make troubleshoot  # Diagnose issues"
	@echo "  make fix-nodes     # Fix NotReady nodes"

install:
	@echo "Installing Ansible dependencies..."
	pip3 install ansible
	ansible-galaxy collection install -r requirements.yml
	@echo "✅ Dependencies installed"

ping:
	@echo "Testing connectivity to all nodes..."
	ansible all -i inventory.yml -m ping
	@echo "✅ Connectivity test complete"

deploy:
	@echo "Deploying Kubernetes cluster with WireGuard..."
	ansible-playbook -i inventory.yml site.yml
	@echo "✅ Cluster deployment complete"

verify:
	@echo "Running cluster verification..."
	ansible-playbook -i inventory.yml verify.yml
	@echo "✅ Verification complete"

maintenance:
	@echo "Running maintenance operations..."
	ansible-playbook -i inventory.yml maintenance.yml
	@echo "✅ Maintenance complete"

reset:
	@echo "⚠️  WARNING: This will completely destroy the cluster!"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	ansible-playbook -i inventory.yml reset.yml
	@echo "✅ Cluster reset complete"

test:
	@echo "Running comprehensive tests..."
	make ping
	make verify
	@echo "✅ All tests complete"

clean:
	@echo "Cleaning CNI interfaces and restarting services..."
	ansible-playbook -i inventory.yml maintenance.yml --tags=clean-cni
	@echo "✅ Cleanup complete"

lint:
	@echo "Running ansible-lint on playbooks..."
	uv run ansible-lint
	@echo "✅ Lint check complete"

format:
	@echo "Auto-fixing ansible formatting issues..."
	uv run ansible-lint --fix
	@echo "✅ Format complete"

# Quick operations
status:
	@echo "Checking cluster status..."
	ansible control_plane -i inventory.yml -m shell -a "kubectl get nodes -o wide" --become-user=ubuntu
	ansible control_plane -i inventory.yml -m shell -a "kubectl get pods --all-namespaces | grep -v Running" --become-user=ubuntu || true

wireguard:
	@echo "Checking WireGuard status..."
	ansible all -i inventory.yml -m shell -a "wg show" --become

logs:
	@echo "Checking recent kubelet logs..."
	ansible all -i inventory.yml -m shell -a "journalctl -u kubelet --no-pager -n 20" --become

troubleshoot:
	@echo "Running cluster troubleshooting..."
	ansible-playbook -i inventory.yml troubleshoot.yml
	@echo "✅ Troubleshooting complete"

fix-nodes:
	@echo "Fixing NotReady nodes..."
	ansible-playbook -i inventory.yml troubleshoot.yml --tags=force_restart
	@echo "✅ Node fix complete"

# Development targets
dev-deploy:
	@echo "Development deployment (with verbose output)..."
	ansible-playbook -i inventory.yml site.yml -vv

dev-reset:
	@echo "Development reset (no confirmation)..."
	ansible-playbook -i inventory.yml reset.yml

dev-test:
	@echo "Development testing..."
	make ping
	ansible-playbook -i inventory.yml verify.yml -v

