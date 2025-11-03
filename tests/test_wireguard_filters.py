"""Table-driven tests for WireGuard filter plugins."""

import sys
from pathlib import Path

import pytest

# Add filter_plugins to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent / 'filter_plugins'))

from wireguard_filters import (
    parse_wireguard_config,
    parse_wireguard_peers,
    merge_wireguard_peers,
    filter_peers_by_inventory,
)


class TestParseWireguardConfig:
    """Table-driven tests for parse_wireguard_config filter."""

    test_cases = [
        (
            "interface with public key comment",
            """[Interface]
Address = 10.0.0.20/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

[Peer]
# test-worker-1
PublicKey = cDUMMYpeerKEY1111111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.3/32
""",
            {
                'interface': {
                    'address': '10.0.0.20/24',
                    'listenport': '51820',
                    'privatekey': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                    'public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                },
                'peers': {
                    'test-worker-1': {
                        'public_key': 'cDUMMYpeerKEY1111111111abcdefGHIJKLMNOPQRST=',
                        'allowed_ips': '10.0.0.3/32',
                    }
                }
            },
        ),
        (
            "interface without public key comment",
            """[Interface]
Address = 10.0.0.20/24
PrivateKey = test_private_key_no_comment_dummy_data_123=

[Peer]
# test-worker-2
PublicKey = dDUMMYpeerKEY2222222222abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.4/32
""",
            {
                'interface': {
                    'address': '10.0.0.20/24',
                    'privatekey': 'test_private_key_no_comment_dummy_data_123=',
                },
                'peers': {
                    'test-worker-2': {
                        'public_key': 'dDUMMYpeerKEY2222222222abcdefGHIJKLMNOPQRST=',
                        'allowed_ips': '10.0.0.4/32',
                    }
                }
            },
        ),
        (
            "empty config",
            "",
            {
                'interface': {},
                'peers': {}
            },
        ),
    ]

    @pytest.mark.parametrize("description,config,expected", test_cases)
    def test_parse_wireguard_config(self, description, config, expected):
        """Test parse_wireguard_config with various config formats."""
        result = parse_wireguard_config(config)
        assert result == expected, f"Failed: {description}"


class TestParseWireguardPeers:
    """Table-driven tests for parse_wireguard_peers filter."""

    # Test cases: (description, input_config, expected_output)
    test_cases = [
        (
            "empty config",
            "",
            {},
        ),
        (
            "only whitespace",
            "   \n  \n  ",
            {},
        ),
        (
            "interface only - no peers",
            """[Interface]
Address = 10.0.0.20/24
PrivateKey = test_private_key
""",
            {},
        ),
        (
            "single peer with comment name",
            """[Interface]
Address = 10.0.0.20/24
PrivateKey = server_key

[Peer]
# test-worker-1
PublicKey = eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.3/32
""",
            {
                'test-worker-1': {
                    'public_key': 'eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=',
                    'allowed_ips': '10.0.0.3/32',
                }
            },
        ),
        (
            "single peer without comment - uses key prefix",
            """[Interface]
Address = 10.0.0.20/24
PrivateKey = server_key

[Peer]
PublicKey = eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.3/32
""",
            {
                'eDUMMYworker': {
                    'public_key': 'eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=',
                    'allowed_ips': '10.0.0.3/32',
                }
            },
        ),
        (
            "multiple peers with comments",
            """[Interface]
Address = 10.0.0.20/24
ListenPort = 51820
PrivateKey = server_key

# Worker nodes
[Peer]
# test-worker-1
PublicKey = eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.3/32

[Peer]
# test-worker-2
PublicKey = fDUMMYworker2KEY22222222abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.4/32

[Peer]
# test-worker-3
PublicKey = gDUMMYworker3KEY33333333abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.21/32
""",
            {
                'test-worker-1': {
                    'public_key': 'eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=',
                    'allowed_ips': '10.0.0.3/32',
                },
                'test-worker-2': {
                    'public_key': 'fDUMMYworker2KEY22222222abcdefGHIJKLMNOPQRST=',
                    'allowed_ips': '10.0.0.4/32',
                },
                'test-worker-3': {
                    'public_key': 'gDUMMYworker3KEY33333333abcdefGHIJKLMNOPQRST=',
                    'allowed_ips': '10.0.0.21/32',
                },
            },
        ),
        (
            "peer with endpoint and keepalive",
            """[Interface]
Address = 10.0.0.3/24
PrivateKey = client_key

[Peer]
# control-plane
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = test-control-plane.example.com:51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
""",
            {
                'control-plane': {
                    'public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                    'allowed_ips': '10.0.0.0/24',
                    'endpoint': 'test-control-plane.example.com:51820',
                    'persistent_keepalive': '25',
                }
            },
        ),
        (
            "interface with public key comment",
            """[Interface]
Address = 10.0.0.20/24
ListenPort = 51820
PrivateKey = iDUMMYprivateKEYtest7777777abcdefGHIJKLMNOP=
# PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=

[Peer]
# test-worker-1
PublicKey = eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.3/32
""",
            {
                'test-worker-1': {
                    'public_key': 'eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=',
                    'allowed_ips': '10.0.0.3/32',
                }
            },
        ),
        (
            "mixed case keys - normalized to lowercase",
            """[Interface]
Address = 10.0.0.20/24
PrivateKey = test_key

[Peer]
# test-peer
PublicKey = testpublickey123=
AllowedIPs = 10.0.0.5/32
PersistentKeepalive = 25
""",
            {
                'test-peer': {
                    'public_key': 'testpublickey123=',
                    'allowed_ips': '10.0.0.5/32',
                    'persistent_keepalive': '25',
                }
            },
        ),
    ]

    @pytest.mark.parametrize("description,config,expected", test_cases)
    def test_parse_wireguard_peers(self, description, config, expected):
        """Test parse_wireguard_peers with various config formats."""
        result = parse_wireguard_peers(config)
        assert result == expected, f"Failed: {description}"

    def test_none_input(self):
        """Test that None input returns empty dict."""
        assert parse_wireguard_peers(None) == {}


class TestMergeWireguardPeers:
    """Table-driven tests for merge_wireguard_peers filter."""

    test_cases = [
        (
            "empty dicts",
            {},
            {},
            {},
        ),
        (
            "empty existing, new peers added",
            {},
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
            },
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
            },
        ),
        (
            "existing peers, empty new",
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
            },
            {},
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
            },
        ),
        (
            "non-overlapping peers - all preserved",
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
                'test-worker-2': {'public_key': 'key2', 'allowed_ips': '10.0.0.4/32'},
            },
            {
                'test-worker-3': {'public_key': 'key3', 'allowed_ips': '10.0.0.21/32'},
            },
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
                'test-worker-2': {'public_key': 'key2', 'allowed_ips': '10.0.0.4/32'},
                'test-worker-3': {'public_key': 'key3', 'allowed_ips': '10.0.0.21/32'},
            },
        ),
        (
            "overlapping peers - new overrides existing",
            {
                'test-worker-1': {'public_key': 'old_key', 'allowed_ips': '10.0.0.3/32'},
                'test-worker-2': {'public_key': 'key2', 'allowed_ips': '10.0.0.4/32'},
            },
            {
                'test-worker-1': {'public_key': 'new_key', 'allowed_ips': '10.0.0.3/32'},
            },
            {
                'test-worker-1': {'public_key': 'new_key', 'allowed_ips': '10.0.0.3/32'},
                'test-worker-2': {'public_key': 'key2', 'allowed_ips': '10.0.0.4/32'},
            },
        ),
        (
            "None inputs treated as empty",
            None,
            None,
            {},
        ),
    ]

    @pytest.mark.parametrize("description,existing,new,expected", test_cases)
    def test_merge_wireguard_peers(self, description, existing, new, expected):
        """Test merge_wireguard_peers with various scenarios."""
        result = merge_wireguard_peers(existing, new)
        assert result == expected, f"Failed: {description}"


class TestFilterPeersByInventory:
    """Table-driven tests for filter_peers_by_inventory filter."""

    test_cases = [
        (
            "empty peers and inventory",
            {},
            [],
            {},
        ),
        (
            "empty inventory - all peers preserved",
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
                'test-worker-2': {'public_key': 'key2', 'allowed_ips': '10.0.0.4/32'},
            },
            [],
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
                'test-worker-2': {'public_key': 'key2', 'allowed_ips': '10.0.0.4/32'},
            },
        ),
        (
            "filter to inventory subset",
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
                'test-worker-2': {'public_key': 'key2', 'allowed_ips': '10.0.0.4/32'},
                'test-worker-3': {'public_key': 'key3', 'allowed_ips': '10.0.0.21/32'},
            },
            ['test-worker-1', 'test-worker-2'],
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
                'test-worker-2': {'public_key': 'key2', 'allowed_ips': '10.0.0.4/32'},
            },
        ),
        (
            "no matching peers",
            {
                'test-worker-1': {'public_key': 'key1', 'allowed_ips': '10.0.0.3/32'},
            },
            ['other-host'],
            {},
        ),
        (
            "None peers input",
            None,
            ['test-worker-1'],
            {},
        ),
    ]

    @pytest.mark.parametrize("description,peers,inventory,expected", test_cases)
    def test_filter_peers_by_inventory(self, description, peers, inventory, expected):
        """Test filter_peers_by_inventory with various scenarios."""
        result = filter_peers_by_inventory(peers, inventory)
        assert result == expected, f"Failed: {description}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
