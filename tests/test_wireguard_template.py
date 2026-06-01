"""Table-driven tests for WireGuard configuration template (wg0.conf.j2) rendering."""

import sys
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

# Add filter_plugins to path for custom filters
sys.path.insert(0, str(Path(__file__).parent.parent / 'filter_plugins'))


class TestWireguardTemplate:
    """Table-driven tests for wg0.conf.j2 template rendering."""

    @pytest.fixture
    def jinja_env(self):
        """Set up Jinja2 environment with template directory and custom filters."""
        template_dir = Path(__file__).parent.parent / 'roles' / 'wireguard' / 'templates'
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        # Register Ansible built-in filters used by the template
        env.filters['dict2items'] = lambda d: [{'key': k, 'value': v} for k, v in sorted(d.items())]
        env.filters['extract'] = lambda key, container: container[key]
        return env

    # Test cases: (description, context, expected_output)
    test_cases = [
        (
            "control plane with single worker using merged peers",
            {
                'inventory_hostname': 'test-control',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1'],
                },
                'wireguard_ip': '10.130.5.1',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'wireguard_merged_peers': {
                    'test-worker-1': {
                        'public_key': 'cDUMMYpeerKEY1111111111abcdefGHIJKLMNOPQRST=',
                        'allowed_ips': '10.130.5.3/32',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.1/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
[Peer]
# test-worker-1
PublicKey = cDUMMYpeerKEY1111111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.130.5.3/32


""",
        ),
        (
            "control plane with multiple workers sorted alphabetically",
            {
                'inventory_hostname': 'test-control',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['worker-c', 'worker-a', 'worker-b'],
                },
                'wireguard_ip': '10.130.5.1',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'wireguard_merged_peers': {
                    'worker-c': {
                        'public_key': 'cDUMMYworkerCKEY3333333333abcdefGHIJKLMNOP=',
                        'allowed_ips': '10.130.5.5/32',
                    },
                    'worker-a': {
                        'public_key': 'cDUMMYworkerAKEY1111111111abcdefGHIJKLMNOP=',
                        'allowed_ips': '10.130.5.3/32',
                    },
                    'worker-b': {
                        'public_key': 'cDUMMYworkerBKEY2222222222abcdefGHIJKLMNOP=',
                        'allowed_ips': '10.130.5.4/32',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.1/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
[Peer]
# worker-a
PublicKey = cDUMMYworkerAKEY1111111111abcdefGHIJKLMNOP=
AllowedIPs = 10.130.5.3/32

[Peer]
# worker-b
PublicKey = cDUMMYworkerBKEY2222222222abcdefGHIJKLMNOP=
AllowedIPs = 10.130.5.4/32

[Peer]
# worker-c
PublicKey = cDUMMYworkerCKEY3333333333abcdefGHIJKLMNOP=
AllowedIPs = 10.130.5.5/32


""",
        ),
        (
            "control plane with empty merged peers uses fallback",
            {
                'inventory_hostname': 'test-control',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2'],
                },
                'wireguard_ip': '10.130.5.1',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'wireguard_merged_peers': {},
                'hostvars': {
                    'test-worker-1': {
                        'wireguard_public_key': 'eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=',
                        'wireguard_ip': '10.130.5.3',
                    },
                    'test-worker-2': {
                        'wireguard_public_key': 'fDUMMYworker2KEY22222222abcdefGHIJKLMNOPQRST=',
                        'wireguard_ip': '10.130.5.4',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.1/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
# Fallback to traditional method if wireguard_merged_peers not available
[Peer]
# test-worker-1
PublicKey = eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.130.5.3/32

[Peer]
# test-worker-2
PublicKey = fDUMMYworker2KEY22222222abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.130.5.4/32


""",
        ),
        (
            "control plane without merged peers variable uses fallback",
            {
                'inventory_hostname': 'test-control',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1'],
                },
                'wireguard_ip': '10.130.5.1',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'hostvars': {
                    'test-worker-1': {
                        'wireguard_public_key': 'eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=',
                        'wireguard_ip': '10.130.5.3',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.1/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
# Fallback to traditional method if wireguard_merged_peers not available
[Peer]
# test-worker-1
PublicKey = eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.130.5.3/32


""",
        ),
        (
            "worker node config with control plane peer",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'hostvars': {
                    'test-control': {
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

""",
        ),
        (
            "worker in a direct-peer group adds a /32 LAN peer and a ListenPort",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2'],
                    'all': ['test-control', 'test-worker-1', 'test-worker-2'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_port': 51820,
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'wireguard_direct_peer_group': 'home',
                'hostvars': {
                    'test-control': {
                        'inventory_hostname': 'test-control',
                        'wireguard_direct_peer_group': '',
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                    'test-worker-1': {
                        'inventory_hostname': 'test-worker-1',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.3',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.3',
                    },
                    'test-worker-2': {
                        'inventory_hostname': 'test-worker-2',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker2publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.4',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.4',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
ListenPort = 51820
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

# Direct same-site peers. Each advertises a /32 AllowedIPs that is more specific
# than the hub's /24, so WireGuard's longest-prefix crypto-routing sends traffic
# for these nodes straight over the LAN instead of relaying via the control plane.
# NOTE: because /32 wins over /24, the direct path does NOT fail over to the hub
# if it breaks -- acceptable here since the peers share a LAN.
[Peer]
# test-worker-2 (direct LAN peer)
PublicKey = wDUMMYworker2publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.4/32
Endpoint = 192.168.1.4:51820
PersistentKeepalive = 25


""",
        ),
        (
            "direct-peer group only meshes same-group nodes (different group excluded)",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2', 'test-worker-3'],
                    'all': ['test-control', 'test-worker-1', 'test-worker-2', 'test-worker-3'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_port': 51820,
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'wireguard_direct_peer_group': 'home',
                'hostvars': {
                    'test-control': {
                        'inventory_hostname': 'test-control',
                        'wireguard_direct_peer_group': '',
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                    'test-worker-1': {
                        'inventory_hostname': 'test-worker-1',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.3',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.3',
                    },
                    'test-worker-2': {
                        'inventory_hostname': 'test-worker-2',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker2publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.4',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.4',
                    },
                    'test-worker-3': {
                        'inventory_hostname': 'test-worker-3',
                        'wireguard_direct_peer_group': 'office',
                        'wireguard_public_key': 'wDUMMYworker3publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.5',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '10.20.30.5',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
ListenPort = 51820
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

# Direct same-site peers. Each advertises a /32 AllowedIPs that is more specific
# than the hub's /24, so WireGuard's longest-prefix crypto-routing sends traffic
# for these nodes straight over the LAN instead of relaying via the control plane.
# NOTE: because /32 wins over /24, the direct path does NOT fail over to the hub
# if it breaks -- acceptable here since the peers share a LAN.
[Peer]
# test-worker-2 (direct LAN peer)
PublicKey = wDUMMYworker2publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.4/32
Endpoint = 192.168.1.4:51820
PersistentKeepalive = 25


""",
        ),
        (
            "direct-peer wireguard_lan_endpoint overrides ansible_default_ipv4",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2'],
                    'all': ['test-control', 'test-worker-1', 'test-worker-2'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_port': 51820,
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'wireguard_direct_peer_group': 'home',
                'hostvars': {
                    'test-control': {
                        'inventory_hostname': 'test-control',
                        'wireguard_direct_peer_group': '',
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                    'test-worker-1': {
                        'inventory_hostname': 'test-worker-1',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.3',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.3',
                    },
                    'test-worker-2': {
                        'inventory_hostname': 'test-worker-2',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker2publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.4',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '10.99.99.4',
                        'ansible_default_ipv4': {'address': '192.168.1.4'},
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
ListenPort = 51820
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

# Direct same-site peers. Each advertises a /32 AllowedIPs that is more specific
# than the hub's /24, so WireGuard's longest-prefix crypto-routing sends traffic
# for these nodes straight over the LAN instead of relaying via the control plane.
# NOTE: because /32 wins over /24, the direct path does NOT fail over to the hub
# if it breaks -- acceptable here since the peers share a LAN.
[Peer]
# test-worker-2 (direct LAN peer)
PublicKey = wDUMMYworker2publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.4/32
Endpoint = 10.99.99.4:51820
PersistentKeepalive = 25


""",
        ),
        (
            "direct-peer wireguard_lan_endpoint works without ansible_default_ipv4 fact",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2'],
                    'all': ['test-control', 'test-worker-1', 'test-worker-2'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_port': 51820,
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'wireguard_direct_peer_group': 'home',
                'hostvars': {
                    'test-control': {
                        'inventory_hostname': 'test-control',
                        'wireguard_direct_peer_group': '',
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                    'test-worker-1': {
                        'inventory_hostname': 'test-worker-1',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.3',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.3',
                    },
                    # No ansible_default_ipv4: the override must still resolve (it
                    # previously hard-failed because default() eagerly evaluates).
                    'test-worker-2': {
                        'inventory_hostname': 'test-worker-2',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker2publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.4',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '10.99.99.4',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
ListenPort = 51820
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

# Direct same-site peers. Each advertises a /32 AllowedIPs that is more specific
# than the hub's /24, so WireGuard's longest-prefix crypto-routing sends traffic
# for these nodes straight over the LAN instead of relaying via the control plane.
# NOTE: because /32 wins over /24, the direct path does NOT fail over to the hub
# if it breaks -- acceptable here since the peers share a LAN.
[Peer]
# test-worker-2 (direct LAN peer)
PublicKey = wDUMMYworker2publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.4/32
Endpoint = 10.99.99.4:51820
PersistentKeepalive = 25


""",
        ),
        (
            "direct-peer endpoint auto-detects from ansible_default_ipv4 when no wireguard_lan_endpoint is set",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2'],
                    'all': ['test-control', 'test-worker-1', 'test-worker-2'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_port': 51820,
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'wireguard_direct_peer_group': 'home',
                'hostvars': {
                    'test-control': {
                        'inventory_hostname': 'test-control',
                        'wireguard_direct_peer_group': '',
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                    'test-worker-1': {
                        'inventory_hostname': 'test-worker-1',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.3',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.3',
                    },
                    # No explicit wireguard_lan_endpoint: the endpoint is auto-detected
                    # from the gathered ansible_default_ipv4 fact (the default-route IP).
                    'test-worker-2': {
                        'inventory_hostname': 'test-worker-2',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker2publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.4',
                        'wireguard_port': 51820,
                        'ansible_default_ipv4': {'address': '192.168.1.4'},
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
ListenPort = 51820
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

# Direct same-site peers. Each advertises a /32 AllowedIPs that is more specific
# than the hub's /24, so WireGuard's longest-prefix crypto-routing sends traffic
# for these nodes straight over the LAN instead of relaying via the control plane.
# NOTE: because /32 wins over /24, the direct path does NOT fail over to the hub
# if it breaks -- acceptable here since the peers share a LAN.
[Peer]
# test-worker-2 (direct LAN peer)
PublicKey = wDUMMYworker2publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.4/32
Endpoint = 192.168.1.4:51820
PersistentKeepalive = 25


""",
        ),
        (
            "direct-peer group sorts 3+ members and skips a peer with no resolvable endpoint",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2', 'test-worker-3', 'test-worker-4'],
                    'all': ['test-control', 'test-worker-1', 'test-worker-2', 'test-worker-3', 'test-worker-4'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_port': 51820,
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'wireguard_direct_peer_group': 'home',
                'hostvars': {
                    'test-control': {
                        'inventory_hostname': 'test-control',
                        'wireguard_direct_peer_group': '',
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                    'test-worker-1': {
                        'inventory_hostname': 'test-worker-1',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.3',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.3',
                    },
                    # Deliberately out of alphabetical order to exercise `| sort`.
                    'test-worker-4': {
                        'inventory_hostname': 'test-worker-4',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker4publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.6',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.6',
                    },
                    # No endpoint (no override, no fact) -> omitted, stays on hub.
                    'test-worker-3': {
                        'inventory_hostname': 'test-worker-3',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker3publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.5',
                        'wireguard_port': 51820,
                    },
                    'test-worker-2': {
                        'inventory_hostname': 'test-worker-2',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker2publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.4',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.4',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
ListenPort = 51820
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

# Direct same-site peers. Each advertises a /32 AllowedIPs that is more specific
# than the hub's /24, so WireGuard's longest-prefix crypto-routing sends traffic
# for these nodes straight over the LAN instead of relaying via the control plane.
# NOTE: because /32 wins over /24, the direct path does NOT fail over to the hub
# if it breaks -- acceptable here since the peers share a LAN.
[Peer]
# test-worker-2 (direct LAN peer)
PublicKey = wDUMMYworker2publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.4/32
Endpoint = 192.168.1.4:51820
PersistentKeepalive = 25

[Peer]
# test-worker-4 (direct LAN peer)
PublicKey = wDUMMYworker4publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.6/32
Endpoint = 192.168.1.6:51820
PersistentKeepalive = 25


""",
        ),
        (
            "direct-peer Endpoint uses each peer's own wireguard_port, falling back to the node's",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2', 'test-worker-3'],
                    'all': ['test-control', 'test-worker-1', 'test-worker-2', 'test-worker-3'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_port': 51820,
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'wireguard_direct_peer_group': 'home',
                'hostvars': {
                    'test-control': {
                        'inventory_hostname': 'test-control',
                        'wireguard_direct_peer_group': '',
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                    'test-worker-1': {
                        'inventory_hostname': 'test-worker-1',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.3',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.3',
                    },
                    # Explicit non-default port.
                    'test-worker-2': {
                        'inventory_hostname': 'test-worker-2',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker2publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.4',
                        'wireguard_port': 52000,
                        'wireguard_lan_endpoint': '192.168.1.4',
                    },
                    # No wireguard_port -> falls back to the rendering node's 51820.
                    'test-worker-3': {
                        'inventory_hostname': 'test-worker-3',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker3publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.5',
                        'wireguard_lan_endpoint': '192.168.1.5',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
ListenPort = 51820
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

# Direct same-site peers. Each advertises a /32 AllowedIPs that is more specific
# than the hub's /24, so WireGuard's longest-prefix crypto-routing sends traffic
# for these nodes straight over the LAN instead of relaying via the control plane.
# NOTE: because /32 wins over /24, the direct path does NOT fail over to the hub
# if it breaks -- acceptable here since the peers share a LAN.
[Peer]
# test-worker-2 (direct LAN peer)
PublicKey = wDUMMYworker2publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.4/32
Endpoint = 192.168.1.4:52000
PersistentKeepalive = 25

[Peer]
# test-worker-3 (direct LAN peer)
PublicKey = wDUMMYworker3publicKEY123456abcdefGHIJKLMN=
AllowedIPs = 10.130.5.5/32
Endpoint = 192.168.1.5:51820
PersistentKeepalive = 25


""",
        ),
        (
            "direct-peer group with a single member renders no direct section (only ListenPort)",
            {
                'inventory_hostname': 'test-worker-1',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': ['test-worker-1', 'test-worker-2'],
                    'all': ['test-control', 'test-worker-1', 'test-worker-2'],
                },
                'wireguard_ip': '10.130.5.3',
                'wireguard_port': 51820,
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.130.5.0/24',
                'wireguard_direct_peer_group': 'home',
                'hostvars': {
                    'test-control': {
                        'inventory_hostname': 'test-control',
                        'wireguard_direct_peer_group': '',
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                    'test-worker-1': {
                        'inventory_hostname': 'test-worker-1',
                        'wireguard_direct_peer_group': 'home',
                        'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.3',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.3',
                    },
                    # Different group -> test-worker-1 is the only "home" member.
                    'test-worker-2': {
                        'inventory_hostname': 'test-worker-2',
                        'wireguard_direct_peer_group': 'office',
                        'wireguard_public_key': 'wDUMMYworker2publicKEY123456abcdefGHIJKLMN=',
                        'wireguard_ip': '10.130.5.4',
                        'wireguard_port': 51820,
                        'wireguard_lan_endpoint': '192.168.1.4',
                    },
                },
            },
            """[Interface]
Address = 10.130.5.3/24
ListenPort = 51820
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane (hub): catch-all /24 route. Anything without a more specific
# direct-peer route below is relayed through the control plane.
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.130.5.0/24
PersistentKeepalive = 25

""",
        ),
        (
            "control plane with no workers - empty config",
            {
                'inventory_hostname': 'test-control',
                'groups': {
                    'control_plane': ['test-control'],
                    'workers': [],
                },
                'wireguard_ip': '10.130.5.1',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'wireguard_merged_peers': {},
                'hostvars': {},
            },
            """[Interface]
Address = 10.130.5.1/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
# Fallback to traditional method if wireguard_merged_peers not available

""",
        ),
    ]

    @pytest.mark.parametrize("description,context,expected", test_cases)
    def test_template_rendering(self, jinja_env, description, context, expected):
        """Test template rendering with diff-based assertion."""
        template = jinja_env.get_template('wg0.conf.j2')
        actual = template.render(context)

        # Use unified diff for clear comparison
        if actual != expected:
            import difflib
            diff = '\n'.join(difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile='expected',
                tofile='actual',
                lineterm='',
            ))
            pytest.fail(f"Template output mismatch for: {description}\n\n{diff}")

        # Also do strict equality check
        assert actual == expected, f"Failed: {description}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
