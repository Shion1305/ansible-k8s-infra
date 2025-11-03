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
        # Register dict2items filter (Ansible built-in)
        env.filters['dict2items'] = lambda d: [{'key': k, 'value': v} for k, v in sorted(d.items())]
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
                'wireguard_ip': '10.0.0.20',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'wireguard_merged_peers': {
                    'test-worker-1': {
                        'public_key': 'cDUMMYpeerKEY1111111111abcdefGHIJKLMNOPQRST=',
                        'allowed_ips': '10.0.0.3/32',
                    },
                },
            },
            """[Interface]
Address = 10.0.0.20/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
[Peer]
# test-worker-1
PublicKey = cDUMMYpeerKEY1111111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.3/32


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
                'wireguard_ip': '10.0.0.20',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'wireguard_merged_peers': {
                    'worker-c': {
                        'public_key': 'cDUMMYworkerCKEY3333333333abcdefGHIJKLMNOP=',
                        'allowed_ips': '10.0.0.5/32',
                    },
                    'worker-a': {
                        'public_key': 'cDUMMYworkerAKEY1111111111abcdefGHIJKLMNOP=',
                        'allowed_ips': '10.0.0.3/32',
                    },
                    'worker-b': {
                        'public_key': 'cDUMMYworkerBKEY2222222222abcdefGHIJKLMNOP=',
                        'allowed_ips': '10.0.0.4/32',
                    },
                },
            },
            """[Interface]
Address = 10.0.0.20/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
[Peer]
# worker-a
PublicKey = cDUMMYworkerAKEY1111111111abcdefGHIJKLMNOP=
AllowedIPs = 10.0.0.3/32

[Peer]
# worker-b
PublicKey = cDUMMYworkerBKEY2222222222abcdefGHIJKLMNOP=
AllowedIPs = 10.0.0.4/32

[Peer]
# worker-c
PublicKey = cDUMMYworkerCKEY3333333333abcdefGHIJKLMNOP=
AllowedIPs = 10.0.0.5/32


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
                'wireguard_ip': '10.0.0.20',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'wireguard_merged_peers': {},
                'hostvars': {
                    'test-worker-1': {
                        'wireguard_public_key': 'eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=',
                        'wireguard_ip': '10.0.0.3',
                    },
                    'test-worker-2': {
                        'wireguard_public_key': 'fDUMMYworker2KEY22222222abcdefGHIJKLMNOPQRST=',
                        'wireguard_ip': '10.0.0.4',
                    },
                },
            },
            """[Interface]
Address = 10.0.0.20/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
# Fallback to traditional method if wireguard_merged_peers not available
[Peer]
# test-worker-1
PublicKey = eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.3/32

[Peer]
# test-worker-2
PublicKey = fDUMMYworker2KEY22222222abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.4/32


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
                'wireguard_ip': '10.0.0.20',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'hostvars': {
                    'test-worker-1': {
                        'wireguard_public_key': 'eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=',
                        'wireguard_ip': '10.0.0.3',
                    },
                },
            },
            """[Interface]
Address = 10.0.0.20/24
ListenPort = 51820
PrivateKey = aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=
# PublicKey = bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=

# Worker nodes
# Fallback to traditional method if wireguard_merged_peers not available
[Peer]
# test-worker-1
PublicKey = eDUMMYworker1KEY11111111abcdefGHIJKLMNOPQRST=
AllowedIPs = 10.0.0.3/32


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
                'wireguard_ip': '10.0.0.3',
                'wireguard_private_key': 'wDUMMYworker1privateKEY123456abcdefGHIJKLM=',
                'wireguard_public_key': 'wDUMMYworker1publicKEY123456abcdefGHIJKLMN=',
                'wireguard_network': '10.0.0.0/24',
                'hostvars': {
                    'test-control': {
                        'wireguard_public_key': 'hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=',
                        'ansible_host': 'test-control-plane.example.com',
                        'wireguard_port': 51820,
                    },
                },
            },
            """[Interface]
Address = 10.0.0.3/24
PrivateKey = wDUMMYworker1privateKEY123456abcdefGHIJKLM=
# PublicKey = wDUMMYworker1publicKEY123456abcdefGHIJKLMN=

# Control plane
[Peer]
PublicKey = hDUMMYctrlplaneKEY4444444abcdefGHIJKLMNOPQ=
Endpoint = root.test-control-plane.example.com:51820
AllowedIPs = 10.0.0.0/24
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
                'wireguard_ip': '10.0.0.20',
                'wireguard_port': 51820,
                'wireguard_private_key': 'aDUMMYprivateKEY1234567890abcdefGHIJKLMNOP=',
                'wireguard_public_key': 'bDUMMYpublicKEY1234567890abcdefGHIJKLMNOPQ=',
                'wireguard_merged_peers': {},
                'hostvars': {},
            },
            """[Interface]
Address = 10.0.0.20/24
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
