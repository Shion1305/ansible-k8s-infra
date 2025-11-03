"""Custom Ansible filters for WireGuard configuration parsing and manipulation."""

from configparser import ConfigParser
from io import StringIO


def parse_wireguard_config(config_text):
    """
    Parse WireGuard configuration and extract both interface and peer information.

    WireGuard configs are INI-like format with [Interface] and [Peer] sections.

    Args:
        config_text: String content of WireGuard configuration file

    Returns:
        Dictionary with 'interface' and 'peers' keys:
        {
            'interface': {
                'private_key': 'base64_key',
                'public_key': 'base64_key',  # from comment if present
                'address': '10.0.0.20/24',
                'listen_port': '51820' (optional)
            },
            'peers': {
                'peer_name': {
                    'public_key': 'base64_key',
                    'allowed_ips': '10.0.0.3/32',
                    'endpoint': 'host:port' (optional),
                    'persistent_keepalive': '25' (optional)
                }
            }
        }
    """
    if not config_text or not config_text.strip():
        return {'interface': {}, 'peers': {}}

    interface = {}
    peers = {}
    current_section = None
    current_comment = None
    current_data = None

    lines = config_text.split('\n')

    for line in lines:
        stripped = line.strip()

        # Check for comments
        if stripped.startswith('#'):
            comment_text = stripped[1:].strip()
            # Check if this is a PublicKey comment in interface section
            if current_section == 'interface' and 'publickey' in comment_text.lower():
                # Extract public key from comment like "# PublicKey = base64key..."
                if '=' in comment_text:
                    key_part = comment_text.split('=', 1)[0].strip().lower()
                    value_part = comment_text.split('=', 1)[1].strip()
                    if key_part == 'publickey':
                        interface['public_key'] = value_part
            else:
                # Regular comment (peer name, etc.)
                current_comment = comment_text
            continue

        # Check for section headers
        if stripped.startswith('['):
            # Save previous peer if exists
            if current_section == 'peer' and current_data and current_data.get('publickey'):
                peer_name = current_comment or current_data['publickey'][:12]
                peers[peer_name] = {
                    'public_key': current_data['publickey'],
                    'allowed_ips': current_data.get('allowedips', ''),
                }
                if 'endpoint' in current_data:
                    peers[peer_name]['endpoint'] = current_data['endpoint']
                if 'persistentkeepalive' in current_data:
                    peers[peer_name]['persistent_keepalive'] = current_data['persistentkeepalive']

            # Start new section
            if '[Peer]' in stripped:
                current_section = 'peer'
                current_data = {}
                current_comment = None
            elif '[Interface]' in stripped:
                current_section = 'interface'
                current_data = interface
                current_comment = None
            continue

        # Parse key-value pairs
        if '=' in stripped and current_data is not None:
            key, value = stripped.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            current_data[key] = value

    # Don't forget the last peer
    if current_section == 'peer' and current_data and current_data.get('publickey'):
        peer_name = current_comment or current_data['publickey'][:12]
        peers[peer_name] = {
            'public_key': current_data['publickey'],
            'allowed_ips': current_data.get('allowedips', ''),
        }
        if 'endpoint' in current_data:
            peers[peer_name]['endpoint'] = current_data['endpoint']
        if 'persistentkeepalive' in current_data:
            peers[peer_name]['persistent_keepalive'] = current_data['persistentkeepalive']

    return {'interface': interface, 'peers': peers}


def parse_wireguard_peers(config_text):
    """
    Parse WireGuard configuration and extract peer information.

    This is a convenience wrapper around parse_wireguard_config that returns
    only the peers dictionary for backward compatibility.

    Args:
        config_text: String content of WireGuard configuration file

    Returns:
        Dictionary mapping peer names to their configuration:
        {
            'peer_name': {
                'public_key': 'base64_key',
                'allowed_ips': '10.0.0.3/32',
                'endpoint': 'host:port' (optional),
                'persistent_keepalive': '25' (optional)
            }
        }
    """
    result = parse_wireguard_config(config_text)
    return result.get('peers', {})


def merge_wireguard_peers(existing_peers, new_peers):
    """
    Merge existing WireGuard peers with new peer data.

    New peers override existing ones with the same name.
    This allows updating peer configurations while preserving others.

    Args:
        existing_peers: Dictionary of existing peer configurations
        new_peers: Dictionary of new/updated peer configurations

    Returns:
        Merged dictionary of peer configurations
    """
    if not existing_peers:
        existing_peers = {}
    if not new_peers:
        new_peers = {}

    # Create a copy to avoid modifying input
    merged = dict(existing_peers)

    # Update with new peers (overrides existing)
    for peer_name, peer_data in new_peers.items():
        merged[peer_name] = peer_data

    return merged


def filter_peers_by_inventory(peers, inventory_hosts):
    """
    Filter peers to only include those present in current inventory.

    This is useful for pruning peers that are no longer in the inventory.

    Args:
        peers: Dictionary of peer configurations
        inventory_hosts: List of hostnames from inventory

    Returns:
        Filtered dictionary containing only peers in inventory
    """
    if not peers:
        return {}
    if not inventory_hosts:
        return peers

    return {
        name: data
        for name, data in peers.items()
        if name in inventory_hosts
    }


class FilterModule:
    """Ansible filter plugin for WireGuard operations."""

    def filters(self):
        """Return filter mappings."""
        return {
            'parse_wireguard_config': parse_wireguard_config,
            'parse_wireguard_peers': parse_wireguard_peers,
            'merge_wireguard_peers': merge_wireguard_peers,
            'filter_peers_by_inventory': filter_peers_by_inventory,
        }
