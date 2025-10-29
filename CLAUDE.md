# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ansible-k8s-wireguard** is an Ansible automation framework that deploys production-ready Kubernetes clusters with WireGuard overlay networking across heterogeneous infrastructure (cloud + on-premises). It automates a 3+ hour manual configuration process into 20-30 minutes.

**Target Infrastructure:**

- **Control Plane (k8s):** Oracle Cloud instance in Tokyo (ARM64)
- **Worker Nodes:** Raspberry Pi CM4 (ARM64) and Ubuntu x86_64 VM

**Core Technologies:** Ansible 2.19.0, Kubernetes 1.33.1, containerd 1.7.27, WireGuard, Flannel CNI

## Development Setup

### Initial Setup

```bash
just lint                       # Validate playbooks before first deployment
```

### Main Commands

```bash
just deploy                     # Deploy complete cluster (site.yml → verify.yml)
just reset                      # Reset entire cluster (destructive, prompts for confirmation)
just clean                      # Clean CNI bridges and restart services
just lint                       # Validate all playbooks with ansible-lint
```

### Workflow

The `just deploy` command runs the complete workflow:

1. **Deployment Phase** - Runs `site.yml` to configure cluster
2. **Verification Phase** - Runs `verify.yml` to validate everything is working

If deployment succeeds but verification fails, re-run `just deploy` to retry both phases.

### Advanced / Debugging

```bash
# Deploy with verbose output
uv run ansible-playbook -i inventory.yml site.yml -vv

# Deploy specific tags
uv run ansible-playbook -i inventory.yml site.yml --tags=wireguard

# Deploy specific hosts
uv run ansible-playbook -i inventory.yml site.yml --limit=k8s-proxy

# Verbose cluster verification
uv run ansible-playbook -i inventory.yml verify.yml -vv

# Run diagnostics
uv run ansible-playbook -i inventory.yml troubleshoot.yml
```

## Architecture

### Playbooks

- **site.yml** (307 lines): Main deployment orchestration - runs sequentially through all setup phases
- **verify.yml** (209 lines): Comprehensive cluster health verification
- **maintenance.yml** (151 lines): Operational tasks (tagged: health-check, clean-cni, wireguard-check)
- **troubleshoot.yml** (146 lines): Diagnostic operations with multiple tags
- **reset.yml** (169 lines): Cluster reset (destroys all data)
- **test-standardized.yml**: Connectivity and health test suite
- **test-workers.yml**: Worker-specific tests

### Roles (6 modular components)

1. **common** (173 lines): Prerequisites - packages, kernel modules, sysctl networking, CNI plugins
2. **kubernetes** (80+ lines): containerd + Kubernetes components (kubelet, kubeadm, kubectl)
3. **control_plane**: kubeadm init and kubeconfig setup for control plane
4. **worker**: kubeadm join for worker nodes
5. **wireguard**: WireGuard installation, key generation, and configuration via `wg0.conf.j2` template
6. **cni**: Flannel CNI deployment and verification

### Deployment Flow (site.yml)

1. Setup common prerequisites across all hosts
2. Generate WireGuard keys locally on each node
3. Configure WireGuard networking with UFW firewall rules
4. Initialize Kubernetes control plane (kubeadm init)
5. Join worker nodes (kubeadm join)
6. Prepare CNI environment (clean conflicting bridges)
7. Deploy Flannel CNI plugin
8. Verify final cluster status

### Inventory Structure (inventory.yml)

```yaml
control_plane:  # k8s node
  hosts:
    k8s:
      ansible_host: k8s.shion1305.com
      wireguard_ip: 10.0.0.20
      # ... other vars

workers:  # cm4, s2204, and secret hosts
  hosts:
    cm4:
      ansible_host: cm4
      wireguard_ip: 10.0.0.3
    s2204:
      ansible_host: s2204
      wireguard_ip: 10.0.0.4
    k8s-proxy:
      ansible_host: prox
      wireguard_ip: 10.0.0.21
```

### Secret Hosts

To keep sensitive host information (like public IPs) private and out of version control:

1. **Add to inventory.yml** with internal/local IPs and hostnames (not public IPs)
2. **Use .gitignore** to exclude sensitive inventory files:
   - `inventory.secret.yml` - for per-host sensitive data
   - `inventory.local.yml` - for local-only configurations
3. **Reference by hostname** in ansible commands/playbooks, not by public IP

**Example: k8s-proxy host**

- Stored in inventory.yml with `ansible_host: prox` (hostname, not IP)
- Uses internal WireGuard IP: 10.0.0.21
- Public IP is kept private and not committed to git
- Deploys like any other worker node: `just deploy =k8s-proxy`

## Key Configuration Details

### WireGuard

- **Template**: `roles/wireguard/templates/wg0.conf.j2`
- Overlay network: 10.0.0.0/24
- Private keys generated locally on each node (never transmitted)
- Worker nodes configured with 25-second persistent keepalive
- Control plane acts as WireGuard endpoint

### Kubernetes Networking

- **Pod CIDR**: 10.244.0.0/16 (Flannel)
- **Service CIDR**: 10.96.0.0/12
- **kubeadm init** uses WireGuard IP as advertise address
- Kubelet configured with node-ip pointing to WireGuard interface

### Ansible Configuration (ansible.cfg)

- Host key checking disabled
- SSH connection pooling and pipelining enabled
- Timeout: 30 seconds
- Log output to `./ansible.log`

## Important Implementation Notes

### Security

- WireGuard private keys never transmitted (generated locally)
- SSH key-based authentication required
- UFW firewall configured with minimal required rules
- File permissions set to 0600 for sensitive configs
- `no_log` flags used for sensitive operations

### Idempotency

- All tasks are safe to re-run
- Conditional checks prevent duplicate installations
- Handlers manage service restarts cleanly

### Performance

- Local network latency: ~0.5ms
- WireGuard tunnel latency: ~8ms with gigabit throughput
- SSH connection pooling reduces overhead
- Pre-installed CNI plugins prevent CoreDNS startup issues

### Error Handling

- Configuration backups before changes
- Health checks verify each phase
- Troubleshooting playbook for diagnostics
- Multiple verification mechanisms

## Python & Tool Management

**Python**: Version 3.13 (via `.python-version`)
**Package Manager**: uv (UV handles environment isolation automatically - no separate virtual env needed)
**CLI Tools**: aqua (declarative version management)
**Linter**: ansible-lint >= 25.7.0

All commands should be prefixed with `uv run` for consistency:

```bash
uv run ansible-playbook ...
uv run ansible-lint
```

## CI/CD

GitHub Actions (`.github/workflows/ansible-lint.yml`):

- Runs ansible-lint on push to main and all PRs
- Uses aqua to install tools
- Executes `just lint`

## Common Development Tasks

### Adding a New Role

1. Create `roles/new-role/tasks/main.yml`
2. Add handler file if needed: `roles/new-role/handlers/main.yml`
3. Include role in appropriate playbook with `- include_role: name=new-role`
4. Run `just lint` to validate

### Modifying WireGuard Configuration

- Edit `roles/wireguard/templates/wg0.conf.j2`
- Key generation is automatic from inventory variables
- Test with `just deploy <host>` on a single node first

### Troubleshooting Cluster Issues

```bash
uv run ansible-playbook -i inventory.yml troubleshoot.yml -vvv        # Run all diagnostics (debug mode)
ansible all -i inventory.yml -a "journalctl -u kubelet --no-pager"    # View kubelet logs on all nodes
```

### Fixing NotReady Nodes

```bash
just fix-nodes                              # Restart kubelet and verify
# Or manually: just clean && just deploy workers
```

## File Structure Summary

```text
├── justfile                              # Task automation (use instead of make!)
├── Makefile                              # Legacy - superseded by justfile
├── ansible.cfg                           # Ansible configuration
├── pyproject.toml                        # Python project config (ansible-lint)
├── aqua.yaml                             # CLI tool version management
├── requirements.yml                      # Ansible collection dependencies
├── inventory.yml                         # Host inventory
├── site.yml                              # Main deployment playbook
├── verify.yml                            # Health verification
├── maintenance.yml                       # Maintenance operations
├── troubleshoot.yml                      # Diagnostics
├── reset.yml                             # Cluster reset
├── test-*.yml                            # Test suites
├── roles/
│   ├── common/                           # Prerequisites
│   ├── kubernetes/                       # K8s components
│   ├── control_plane/                    # Control plane setup
│   ├── worker/                           # Worker setup
│   ├── wireguard/                        # WireGuard overlay
│   └── cni/                              # Flannel CNI
└── .github/workflows/ansible-lint.yml    # CI/CD pipeline
```

## Related Documentation

See **README.md** for:

- Detailed deployment instructions
- Network topology diagrams
- Troubleshooting guide
- Performance benchmarks
- Feature overview

## Notes for Future Development

- Always validate changes with `just lint` before committing
- The main workflow is `just deploy` - it automatically runs site.yml then verify.yml
- To test partial deployments, use direct ansible-playbook commands with `--tags` or `--limit`
- WireGuard configuration changes require service restart (automatic via handlers)
- The project is designed for heterogeneous hardware - test on both ARM64 and x86_64
- Keep `uv.lock` in sync when updating Python dependencies
- Maintain idempotency when adding new tasks
- Use `just` command runner - minimalist design with only essential commands
