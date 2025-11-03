"""Custom Ansible filters for WireGuard configuration parsing and manipulation."""

from configparser import ConfigParser
from io import StringIO


def parse_wireguard_peers(config_text):
    """
    Parse WireGuard configuration and extract peer information using configparser.

    WireGuard configs are INI-like format with [Interface] and [Peer] sections.

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
    if not config_text or not config_text.strip():
        return {}

    peers = {}
    current_section = None
    current_comment = None

    # Parse line by line to handle multiple [Peer] sections and comments
    # configparser doesn't handle duplicate section names well
    lines = config_text.split('\n')
    peer_data = None

    for line in lines:
        stripped = line.strip()

        # Check for comment (peer name)
        if stripped.startswith('#'):
            current_comment = stripped[1:].strip()
            continue

        # Check for section headers
        if stripped.startswith('['):
            # Save previous peer if exists
            if peer_data and peer_data.get('publickey'):
                peer_name = current_comment or peer_data['publickey'][:12]
                peers[peer_name] = {
                    'public_key': peer_data['publickey'],
                    'allowed_ips': peer_data.get('allowedips', ''),
                }
                if 'endpoint' in peer_data:
                    peers[peer_name]['endpoint'] = peer_data['endpoint']
                if 'persistentkeepalive' in peer_data:
                    peers[peer_name]['persistent_keepalive'] = peer_data['persistentkeepalive']

            # Start new section
            if '[Peer]' in stripped:
                current_section = 'peer'
                peer_data = {}
                current_comment = None
            elif '[Interface]' in stripped:
                current_section = 'interface'
                peer_data = None
            continue

        # Parse key-value pairs
        if '=' in stripped and peer_data is not None:
            key, value = stripped.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            peer_data[key] = value

    # Don't forget the last peer
    if peer_data and peer_data.get('publickey'):
        peer_name = current_comment or peer_data['publickey'][:12]
        peers[peer_name] = {
            'public_key': peer_data['publickey'],
            'allowed_ips': peer_data.get('allowedips', ''),
        }
        if 'endpoint' in peer_data:
            peers[peer_name]['endpoint'] = peer_data['endpoint']
        if 'persistentkeepalive' in peer_data:
            peers[peer_name]['persistent_keepalive'] = peer_data['persistentkeepalive']

    return peers


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
            'parse_wireguard_peers': parse_wireguard_peers,
            'merge_wireguard_peers': merge_wireguard_peers,
            'filter_peers_by_inventory': filter_peers_by_inventory,
        }
