# WireGuard Incremental Peer Updates

## Overview

This feature enables **partial deployments** of worker nodes without losing WireGuard peer configurations on the control plane. Previously, deploying to a single worker would regenerate the control plane's WireGuard config with only that worker as a peer, removing all other peers.

## Problem Statement

**Before this feature:**

```bash
# Full deployment works fine
just deploy
# Control plane wg0.conf contains: cm4, s2204, k8s-proxy

# Partial deployment breaks other peers
ansible-playbook -i inventory.yml site.yml --limit=cm4
# Control plane wg0.conf now only contains: cm4
# ❌ s2204 and k8s-proxy lose connectivity!
```

**After this feature:**

```bash
# Partial deployment preserves existing peers
ansible-playbook -i inventory.yml site.yml --limit=cm4
# Control plane wg0.conf contains: cm4, s2204, k8s-proxy (all preserved)
# ✅ All peers remain configured!
```

## How It Works

### Architecture

The incremental update system follows these steps:

1. **Fetch Existing State** - Parse current WireGuard configuration on control plane
2. **Merge Peers** - Combine existing peers with workers from current Ansible play
3. **Generate Config** - Use merged peer data in template
4. **Validate** - Verify all expected peers are configured

### Components

#### 1. Filter Plugin: `filter_plugins/wireguard_filters.py`

Custom Ansible filters for WireGuard configuration manipulation:

- **`parse_wireguard_peers`** - Parses WireGuard INI-format config into dictionary
- **`merge_wireguard_peers`** - Merges existing and new peer dictionaries
- **`filter_peers_by_inventory`** - Filters peers to only those in inventory

```python
# Example usage in Ansible
existing_peers: "{{ config_content | parse_wireguard_peers }}"
merged_peers: "{{ existing_peers | merge_wireguard_peers(new_peers) }}"
```

#### 2. Task Files

**`roles/wireguard/tasks/fetch_existing_peers.yml`**
- Checks if WireGuard config exists
- Reads existing configuration
- Parses peers into `existing_wg_peers` fact
- Initializes empty dict if no config exists

**`roles/wireguard/tasks/merge_peer_config.yml`**
- Builds dictionary of peers from current play
- Merges with existing peers
- Sets `merged_wg_peers` fact for template

**`roles/wireguard/tasks/validate_peers.yml`**
- Validates all inventory workers are configured
- Reports extra peers (preserved from previous runs)
- Provides validation summary

#### 3. Updated Template: `roles/wireguard/templates/wg0.conf.j2`

The template now uses `merged_wg_peers` when available, falling back to the traditional method:

```jinja2
{% if merged_wg_peers is defined and merged_wg_peers | length > 0 %}
{% for peer_name, peer_data in (merged_wg_peers | dict2items | sort(attribute='key')) %}
[Peer]
# {{ peer_name }}
PublicKey = {{ peer_data.public_key }}
AllowedIPs = {{ peer_data.allowed_ips }}
{% endfor %}
{% else %}
# Fallback to traditional method
{% for host in groups['workers'] %}
...
{% endfor %}
{% endif %}
```

#### 4. Integration in `site.yml`

The "Configure WireGuard" play now includes incremental update tasks:

```yaml
- name: Configure WireGuard
  hosts: all
  tasks:
    # NEW: Fetch and merge peers on control plane
    - include_tasks: roles/wireguard/tasks/fetch_existing_peers.yml
      when: inventory_hostname in groups['control_plane']

    - include_tasks: roles/wireguard/tasks/merge_peer_config.yml
      when: inventory_hostname in groups['control_plane']

    # Existing: Generate config (now uses merged_wg_peers)
    - template:
        src: roles/wireguard/templates/wg0.conf.j2
        dest: /etc/wireguard/wg0.conf

    # NEW: Validate configuration
    - include_tasks: roles/wireguard/tasks/validate_peers.yml
      when: inventory_hostname in groups['control_plane']
```

## Usage Examples

### Dry-Run Mode (Preview Changes)

Preview configuration changes without applying them:

```bash
# Dry-run for all nodes
ansible-playbook -i inventory.yml site.yml --tags=wireguard -e "wireguard_dry_run=true"

# Dry-run for specific worker
ansible-playbook -i inventory.yml site.yml --tags=wireguard --limit=cm4 -e "wireguard_dry_run=true"

# Dry-run for control plane only
ansible-playbook -i inventory.yml site.yml --tags=wireguard --limit=control_plane -e "wireguard_dry_run=true"
```

**Dry-run mode will:**
- Generate config to `/tmp/wg0.conf.preview` on each node
- Display a diff showing what would change
- Show peer count changes
- NOT modify actual configuration
- NOT restart WireGuard service
- Provide commands to review the preview file

### Partial Worker Deployment

Deploy only a single worker node:

```bash
# Deploy only cm4 worker
ansible-playbook -i inventory.yml site.yml --limit=cm4

# Deploy specific workers
ansible-playbook -i inventory.yml site.yml --limit=cm4,s2204

# Using just with limit (if you extend justfile)
just deploy-worker cm4
```

### Full Cluster Deployment

Works exactly as before:

```bash
just deploy
# or
ansible-playbook -i inventory.yml site.yml
```

### WireGuard-Only Updates

Update only WireGuard configuration:

```bash
ansible-playbook -i inventory.yml site.yml --tags=wireguard

# For specific host
ansible-playbook -i inventory.yml site.yml --tags=wireguard --limit=cm4
```

### Adding New Worker

When adding a new worker to inventory:

1. Add host to `inventory.yml` under `workers` group
2. Run deployment:
   ```bash
   ansible-playbook -i inventory.yml site.yml --limit=new-worker
   ```
3. The new peer is **added** to control plane config (existing peers preserved)

## Dry-Run Mode Details

### What is Dry-Run Mode?

Dry-run mode allows you to preview WireGuard configuration changes before applying them. This is especially useful when:
- Testing incremental updates for the first time
- Verifying peer merge logic
- Previewing changes before production deployment
- Debugging configuration issues

### How Dry-Run Works

1. **Generates Preview**: Creates configuration to `/tmp/wg0.conf.preview` on target host
2. **Shows Diff**: Displays unified diff comparing current vs. preview config
3. **Provides Summary**: Shows peer counts and changes
4. **No Side Effects**: Does not modify actual config or restart services

### Dry-Run Output Example

```
==========================================
DRY-RUN MODE: WireGuard Configuration Preview
==========================================
Comparing with existing configuration

--- Current Config
+++ Preview Config
@@ -10,6 +10,10 @@
 PublicKey = xyz123...
 AllowedIPs = 10.0.0.3/32

+[Peer]
+# k8s-proxy
+PublicKey = abc789...
+AllowedIPs = 10.0.0.21/32
+

==========================================
DRY-RUN SUMMARY
==========================================
Node: k8s
Preview file: /tmp/wg0.conf.preview
Target file: /etc/wireguard/wg0.conf
Status: UPDATE EXISTING
Current peers: 2
Preview peers: 3
Change: +1 peer(s)

To apply this configuration, run without -e wireguard_dry_run=true
==========================================
```

### Reviewing Preview Files

After dry-run, you can manually inspect the preview files:

```bash
# View preview on control plane
ssh k8s.shion1305.com 'sudo cat /tmp/wg0.conf.preview'

# Compare with diff tool
ssh k8s.shion1305.com 'sudo diff -u /etc/wireguard/wg0.conf /tmp/wg0.conf.preview'

# Side-by-side comparison
ssh k8s.shion1305.com 'sudo diff -y /etc/wireguard/wg0.conf /tmp/wg0.conf.preview | less'
```

### Workflow: Dry-Run → Review → Apply

```bash
# Step 1: Preview changes with dry-run
ansible-playbook -i inventory.yml site.yml --tags=wireguard --limit=cm4 -e "wireguard_dry_run=true"

# Step 2: Review output and preview files
# (check diff output, peer counts, etc.)

# Step 3: Apply changes if satisfied
ansible-playbook -i inventory.yml site.yml --tags=wireguard --limit=cm4
```

## Validation and Verification

### Automatic Validation

The `validate_peers.yml` task automatically runs after WireGuard configuration:

- ✅ Verifies all inventory workers are configured as peers
- ✅ Reports extra peers preserved from previous runs
- ✅ Shows validation summary with counts

### Manual Verification

Check control plane WireGuard status:

```bash
# SSH to control plane
ssh k8s.shion1305.com

# Show all peers
sudo wg show wg0 peers

# Show full status
sudo wg show wg0

# Check configuration file
sudo cat /etc/wireguard/wg0.conf
```

Expected output shows all workers as peers:

```
[Peer]
# cm4
PublicKey = ...
AllowedIPs = 10.0.0.3/32

[Peer]
# s2204
PublicKey = ...
AllowedIPs = 10.0.0.4/32

[Peer]
# k8s-proxy
PublicKey = ...
AllowedIPs = 10.0.0.21/32
```

## Troubleshooting

### Issue: Validation reports missing peers

**Symptom:** Validation task fails saying a peer is missing

**Cause:** WireGuard service may not have loaded the new configuration

**Solution:**
```bash
# Restart WireGuard on control plane
ansible control_plane -i inventory.yml -b -m systemd -a "name=wg-quick@wg0 state=restarted"

# Verify peers loaded
ansible control_plane -i inventory.yml -b -a "wg show wg0 peers"
```

### Issue: Extra peers reported but not expected

**Symptom:** Validation shows extra peers not in current inventory

**Explanation:** This is **normal behavior** for incremental updates. Extra peers are workers that:
- Were in a previous deployment
- Are not in the current Ansible play (due to `--limit`)
- Are intentionally preserved to maintain connectivity

**To remove peers no longer needed:**

1. Run full deployment (no `--limit`):
   ```bash
   just deploy
   ```

2. Or manually edit `/etc/wireguard/wg0.conf` and remove unwanted `[Peer]` sections

### Issue: Worker loses connectivity after partial deployment

**Symptom:** Worker node can't reach control plane after deploying different worker

**Diagnosis:**
```bash
# On affected worker
ping 10.0.0.20  # Control plane WireGuard IP

# Check WireGuard status
sudo wg show wg0
```

**Solution:** This should not happen with incremental updates enabled. If it does:

1. Check control plane config includes the worker:
   ```bash
   ansible control_plane -i inventory.yml -b -a "grep -A3 'worker-name' /etc/wireguard/wg0.conf"
   ```

2. Re-run deployment with that worker:
   ```bash
   ansible-playbook -i inventory.yml site.yml --limit=affected-worker
   ```

### Issue: Parser fails to read config

**Symptom:** Error in `parse_wireguard_peers` filter

**Cause:** Configuration file format is malformed or has unexpected structure

**Solution:**
```bash
# Check config file syntax
ansible control_plane -i inventory.yml -b -a "cat /etc/wireguard/wg0.conf"

# Validate WireGuard can parse it
ansible control_plane -i inventory.yml -b -a "wg-quick strip wg0"
```

If config is corrupted, restore from backup:
```bash
ansible control_plane -i inventory.yml -b -a "ls -lt /etc/wireguard/wg0.conf*"
ansible control_plane -i inventory.yml -b -a "cp /etc/wireguard/wg0.conf.backup /etc/wireguard/wg0.conf"
```

## Configuration Backups

The template task automatically creates backups:

```yaml
- template:
    backup: true  # Creates timestamped backup before changes
```

Backups are stored in `/etc/wireguard/` with format: `wg0.conf.TIMESTAMP.backup`

To restore:
```bash
sudo cp /etc/wireguard/wg0.conf.TIMESTAMP.backup /etc/wireguard/wg0.conf
sudo systemctl restart wg-quick@wg0
```

## Future Enhancements

### Optional: Peer Pruning

Add a task to remove peers not in inventory:

```yaml
- name: Build filtered peers (only inventory hosts)
  set_fact:
    merged_wg_peers: "{{ merged_wg_peers | filter_peers_by_inventory(groups['workers']) }}"
  when: wireguard_prune_extra_peers | default(false)
```

Enable with variable:
```yaml
# inventory.yml or group_vars
wireguard_prune_extra_peers: true
```

### Optional: Peer Health Checks

Validate connectivity to configured peers:

```yaml
- name: Test connectivity to all peers
  command: "ping -c 1 -W 2 {{ item }}"
  loop: "{{ merged_wg_peers.values() | map(attribute='allowed_ips') | map('regex_replace', '/32$', '') | list }}"
  register: peer_ping_results
  failed_when: false
```

### Optional: Configuration Drift Detection

Compare running config vs. file config:

```yaml
- name: Detect configuration drift
  shell: |
    wg-quick strip wg0 | diff -u - /etc/wireguard/wg0.conf
  register: config_drift
  changed_when: config_drift.rc != 0
  failed_when: false
```

## Technical Details

### Peer Dictionary Format

```python
{
    'cm4': {
        'public_key': 'base64_encoded_public_key_here',
        'allowed_ips': '10.0.0.3/32',
        # Optional fields:
        'endpoint': 'host:port',
        'persistent_keepalive': '25'
    },
    's2204': {
        'public_key': 'another_base64_key',
        'allowed_ips': '10.0.0.4/32'
    }
}
```

### Merge Behavior

- **New peers:** Added to configuration
- **Existing peers with same name:** Updated with new data (public key, IPs)
- **Existing peers not in play:** Preserved unchanged
- **Sorting:** Peers are sorted alphabetically by name in config file

### Performance Impact

- **Minimal:** Adds ~2 seconds to deployment (file read + parsing)
- **Network:** No additional network calls
- **Idempotent:** Re-running with same hosts produces identical config

## Testing

Run ansible-lint to validate:
```bash
just lint
```

Test incremental deployment:
```bash
# 1. Full deployment
just deploy

# 2. Verify all peers present
ansible control_plane -i inventory.yml -b -a "wg show wg0 peers" | wc -l
# Should show: 3 (or number of workers)

# 3. Partial deployment
ansible-playbook -i inventory.yml site.yml --tags=wireguard --limit=cm4

# 4. Verify all peers still present
ansible control_plane -i inventory.yml -b -a "wg show wg0 peers" | wc -l
# Should still show: 3 (unchanged!)
```

## Related Files

- **Filter Plugin:** [filter_plugins/wireguard_filters.py](../filter_plugins/wireguard_filters.py)
- **Fetch Task:** [roles/wireguard/tasks/fetch_existing_peers.yml](../roles/wireguard/tasks/fetch_existing_peers.yml)
- **Merge Task:** [roles/wireguard/tasks/merge_peer_config.yml](../roles/wireguard/tasks/merge_peer_config.yml)
- **Dry-Run Task:** [roles/wireguard/tasks/dry_run_config.yml](../roles/wireguard/tasks/dry_run_config.yml)
- **Validation Task:** [roles/wireguard/tasks/validate_peers.yml](../roles/wireguard/tasks/validate_peers.yml)
- **Template:** [roles/wireguard/templates/wg0.conf.j2](../roles/wireguard/templates/wg0.conf.j2)
- **Main Playbook:** [site.yml](../site.yml)

## References

- [WireGuard Documentation](https://www.wireguard.com/quickstart/)
- [Ansible Template Module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html)
- [Ansible Custom Filters](https://docs.ansible.com/ansible/latest/dev_guide/developing_plugins.html#filter-plugins)
