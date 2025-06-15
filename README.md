# Kubernetes Cluster with WireGuard - Ansible Automation

This Ansible playbook automates the deployment of a Kubernetes cluster with WireGuard overlay networking across multiple network environments. It implements the same architecture documented in the main README.md but with full automation.

## Architecture Overview

- **Control Plane**: k8s (Oracle Cloud, Tokyo)
- **Worker Nodes**: cm4 (Raspberry Pi CM4), s2204 (Ubuntu x86_64) 
- **Networking**: WireGuard tunnels + local network optimization
- **CNI**: Flannel with custom configuration for WireGuard compatibility
- **Firewall**: UFW standardized across all worker nodes

## Prerequisites

### 1. Install Ansible and Dependencies

```bash
# Install Ansible
pip3 install ansible

# Install required collections
ansible-galaxy collection install -r requirements.yml
```

### 2. SSH Access

Ensure SSH key-based authentication to all nodes:

```bash
# Test connectivity
ansible all -i inventory.yml -m ping
```

### 3. DNS Configuration

Ensure `k8s.shion1305.com` resolves to `150.230.214.233` (Oracle Cloud public IP).

### 4. Cloud Firewall Rules

Oracle Cloud security group must allow:
- Port 6443/tcp (Kubernetes API)
- Port 51820/udp (WireGuard)
- Port 22/tcp (SSH)

## Configuration

### Inventory Configuration

Update `inventory.yml` with your specific details:

```yaml
# Key settings to verify/modify:
k8s:
  ansible_host: 150.230.214.233  # Your Oracle Cloud IP
  ansible_user: ubuntu           # Your SSH user
  public_ip: 150.230.214.233
  fqdn: k8s.shion1305.com        # Your domain
  
cm4:
  ansible_host: 192.168.11.7     # Your Raspberry Pi IP
  ansible_user: pi               # Your SSH user
  
s2204:
  ansible_host: 192.168.11.2     # Your Ubuntu worker IP
  ansible_user: shion            # Your SSH user
```

### SSH Key Configuration

Update the SSH key paths in inventory.yml:

```yaml
ansible_ssh_private_key_file: ~/.ssh/id_rsa  # Your SSH private key
```

## Deployment

### Full Cluster Deployment

```bash
# Deploy the complete cluster
ansible-playbook -i inventory.yml site.yml
```

The playbook will:
1. Install and configure prerequisites on all nodes
2. Set up WireGuard tunnels
3. Install Kubernetes components
4. Initialize the control plane
5. Join worker nodes
6. Deploy and configure Flannel CNI
7. Verify cluster health

### Deployment Time

Expected deployment time: **20-30 minutes** (vs ~3 hours manual)

## Playbook Structure

```
ansible-k8s-wireguard/
├── ansible.cfg              # Ansible configuration
├── inventory.yml            # Hosts and variables
├── site.yml                 # Main deployment playbook
├── reset.yml                # Cluster reset playbook
├── requirements.yml         # Required Ansible collections
└── roles/
    ├── common/              # Common prerequisites
    │   └── tasks/main.yml
    ├── wireguard/           # WireGuard setup
    │   ├── tasks/main.yml
    │   ├── templates/
    │   │   └── wg0.conf.j2
    │   └── handlers/main.yml
    ├── kubernetes/          # Kubernetes installation
    │   ├── tasks/main.yml
    │   └── handlers/main.yml
    ├── control-plane/       # Control plane initialization
    │   └── tasks/main.yml
    ├── worker/              # Worker node configuration
    │   ├── tasks/main.yml
    │   └── handlers/main.yml
    └── cni/                 # CNI deployment and configuration
        └── tasks/main.yml
```

## Key Features

### 🔒 **Security-First Design**
- WireGuard private keys generated on each node
- No plaintext secrets in playbooks
- Proper file permissions and ownership
- Minimal firewall rules

### 🚀 **Performance Optimized**
- Local network traffic between cm4 ↔ s2204 (~0.5ms)
- WireGuard tunnels for secure cross-site communication (~8ms)
- Proper CNI plugin installation prevents CoreDNS issues

### 🛠 **Production Ready**
- Idempotent operations (safe to re-run)
- Comprehensive error handling
- Health checks and verification
- Backup configurations before changes

### 🔧 **Troubleshooting Built-in**
- Addresses all known issues from manual deployment
- Automatic CNI plugin installation
- WireGuard connectivity verification
- Flannel DaemonSet patching for API access

## Operations

### Verify Cluster Status

```bash
# Check all nodes
ansible control_plane -i inventory.yml -m shell -a "kubectl get nodes -o wide" -b --become-user=ubuntu

# Check system pods
ansible control_plane -i inventory.yml -m shell -a "kubectl get pods --all-namespaces" -b --become-user=ubuntu
```

### Reset Cluster

⚠️ **WARNING: This will completely destroy the cluster!**

```bash
# Reset everything
ansible-playbook -i inventory.yml reset.yml
```

### Partial Operations

```bash
# Only configure WireGuard
ansible-playbook -i inventory.yml site.yml --tags=wireguard

# Only join worker nodes
ansible-playbook -i inventory.yml site.yml --limit=workers

# Only deploy CNI
ansible-playbook -i inventory.yml site.yml --tags=cni
```

## Customization

### Change Kubernetes Version

```yaml
# In inventory.yml
kubernetes_version: "1.33.1-1.1"  # Update version
```

### Modify Network CIDRs

```yaml
# In inventory.yml
pod_network_cidr: "10.244.0.0/16"    # Pod network
service_cidr: "10.96.0.0/12"         # Service network
wireguard_network: "10.0.0.0/24"     # WireGuard network
```

### Add Additional Nodes

1. Add node to `inventory.yml` under appropriate group
2. Configure SSH access
3. Run playbook: `ansible-playbook -i inventory.yml site.yml --limit=new_node`

## Monitoring and Maintenance

### Health Checks

```bash
# WireGuard status
ansible all -i inventory.yml -m shell -a "wg show" -b

# Kubernetes node status
ansible control_plane -i inventory.yml -m shell -a "kubectl get nodes" -b --become-user=ubuntu

# Pod status
ansible control_plane -i inventory.yml -m shell -a "kubectl get pods --all-namespaces | grep -v Running" -b --become-user=ubuntu
```

### Updates

```bash
# Update system packages
ansible all -i inventory.yml -m apt -a "update_cache=yes upgrade=yes" -b

# Restart services if needed
ansible all -i inventory.yml -m systemd -a "name=kubelet state=restarted" -b
```

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   ```bash
   # Test connectivity
   ansible all -i inventory.yml -m ping
   ```

2. **WireGuard Not Connecting**
   ```bash
   # Check WireGuard status
   ansible all -i inventory.yml -m shell -a "systemctl status wg-quick@wg0" -b
   ```

3. **Nodes Not Ready**
   ```bash
   # Check kubelet logs
   ansible all -i inventory.yml -m shell -a "journalctl -u kubelet --no-pager -l" -b
   ```

4. **CoreDNS Issues**
   ```bash
   # Verify CNI plugins
   ansible all -i inventory.yml -m shell -a "ls /opt/cni/bin/ | grep loopback" -b
   ```

### Debug Mode

```bash
# Run with verbose output
ansible-playbook -i inventory.yml site.yml -vvv

# Check logs
tail -f ansible.log
```

## Comparison: Manual vs Ansible

| Aspect | Manual Deployment | Ansible Automation |
|--------|-------------------|--------------------|
| **Time** | ~3 hours | 20-30 minutes |
| **Reliability** | Error-prone | Idempotent & tested |
| **Reproducibility** | Difficult | Perfect |
| **Documentation** | Manual maintenance | Self-documenting |
| **Rollback** | Manual cleanup | Automated reset |
| **Scaling** | Tedious | Simple node addition |

## Security Notes

- WireGuard private keys are generated on target nodes and never transmitted
- SSH keys should use strong passphrases
- Consider using Ansible Vault for sensitive variables
- Regularly update Kubernetes and OS packages

## Performance Characteristics

- **Local Communication** (cm4 ↔ s2204): ~0.5ms latency
- **WireGuard Tunnels**: ~8ms latency, full gigabit throughput  
- **Cluster API**: Direct access via FQDN
- **Pod Networking**: Flannel VXLAN with optimized routing

---

## Quick Start

```bash
# 1. Clone/create the playbook directory
cd ansible-k8s-wireguard

# 2. Install dependencies
ansible-galaxy collection install -r requirements.yml

# 3. Update inventory with your IPs and credentials
vim inventory.yml

# 4. Test connectivity
ansible all -i inventory.yml -m ping

# 5. Deploy cluster
ansible-playbook -i inventory.yml site.yml

# 6. Verify deployment
ansible control_plane -i inventory.yml -m shell -a "kubectl get nodes" -b --become-user=ubuntu
```

**Result**: Production-ready Kubernetes cluster in under 30 minutes! 🚀

