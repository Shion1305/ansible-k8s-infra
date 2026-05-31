"""Offline render check for roles/wireguard/templates/wg0.conf.j2.

Mocks the Ansible template context (inventory_hostname / groups / hostvars +
the host's own vars) and asserts the direct same-site peering logic produces
the expected config for each node, WITHOUT touching any live host.

Run: uv run python tests/render_wg_template.py
"""

import sys
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, FileSystemLoader

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = "roles/wireguard/templates/wg0.conf.j2"

GROUPS = {
    "all": ["cm4", "k8s", "k8s-proxy", "s2204"],
    "control_plane": ["k8s"],
    "workers": ["cm4", "s2204", "k8s-proxy"],
}

HOSTVARS = {
    "k8s": {
        "inventory_hostname": "k8s",
        "wireguard_ip": "10.130.5.1",
        "wireguard_port": 51820,
        "wireguard_interface": "wg0",
        "ansible_host": "k8s.shion1305.com",
        "wireguard_public_key": "KEY_k8s",
        "wireguard_private_key": "PRIV_k8s",
        "wireguard_direct_peer_group": "",
        "ansible_default_ipv4": {"address": "10.0.0.1"},
    },
    "cm4": {
        "inventory_hostname": "cm4",
        "wireguard_ip": "10.130.5.3",
        "wireguard_port": 51820,
        "wireguard_interface": "wg0",
        "ansible_host": "cm4",
        "wireguard_public_key": "KEY_cm4",
        "wireguard_private_key": "PRIV_cm4",
        "wireguard_direct_peer_group": "home",
        "ansible_default_ipv4": {"address": "192.168.1.3"},
    },
    "s2204": {
        "inventory_hostname": "s2204",
        "wireguard_ip": "10.130.5.4",
        "wireguard_port": 51820,
        "wireguard_interface": "wg0",
        "ansible_host": "s2204",
        "wireguard_public_key": "KEY_s2204",
        "wireguard_private_key": "PRIV_s2204",
        "wireguard_direct_peer_group": "home",
        "ansible_default_ipv4": {"address": "192.168.1.4"},
    },
    "k8s-proxy": {
        "inventory_hostname": "k8s-proxy",
        "wireguard_ip": "10.130.5.21",
        "wireguard_port": 51820,
        "wireguard_interface": "wg0",
        "ansible_host": "prox",
        "wireguard_public_key": "KEY_proxy",
        "wireguard_private_key": "PRIV_proxy",
        "wireguard_direct_peer_group": "",
        "ansible_default_ipv4": {"address": "10.0.0.21"},
    },
}

GLOBALS = {
    "wireguard_network": "10.130.5.0/24",
    "wireguard_port": 51820,
    "wireguard_direct_peer_group": "",
    "groups": GROUPS,
    "hostvars": HOSTVARS,
}

# Control-plane-only var produced by merge_peer_config.yml at runtime.
MERGED_PEERS = {
    "cm4": {"public_key": "KEY_cm4", "allowed_ips": "10.130.5.3/32"},
    "s2204": {"public_key": "KEY_s2204", "allowed_ips": "10.130.5.4/32"},
    "k8s-proxy": {"public_key": "KEY_proxy", "allowed_ips": "10.130.5.21/32"},
}

env = Environment(
    loader=FileSystemLoader(str(REPO)),
    undefined=ChainableUndefined,
    trim_blocks=False,
    lstrip_blocks=False,
)
# Minimal stand-ins for Ansible-specific filters so the template renders offline
# (built-in `sort`, `select*`, `reject`, `map(attribute=...)`, `equalto` work).
env.filters["dict2items"] = lambda d: [{"key": k, "value": v} for k, v in d.items()]
env.filters["extract"] = lambda key, container: container[key]
tmpl = env.get_template(TEMPLATE)


def render(host):
    ctx = dict(GLOBALS)
    ctx.update(HOSTVARS[host])  # host's own vars are top-level in Ansible
    if host in GROUPS["control_plane"]:
        ctx["wireguard_merged_peers"] = MERGED_PEERS
    return tmpl.render(**ctx)


def peer_blocks(text):
    """Return list of [Peer] block bodies (text after each [Peer] header)."""
    parts = text.split("[Peer]")
    return [p for p in parts[1:]]


failures = []


def check(cond, msg, ctx=""):
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        failures.append(f"{msg}\n{ctx}")


for host in ["cm4", "s2204", "k8s-proxy", "k8s"]:
    print(f"\n=== {host} ===")
    out = render(host)
    print(out)
    blocks = peer_blocks(out)

    if host == "cm4":
        check("ListenPort = 51820" in out, "cm4 has ListenPort (direct-peer member)", out)
        check(any("AllowedIPs = 10.130.5.0/24" in b for b in blocks),
              "cm4 keeps control-plane hub /24 peer", out)
        direct = [b for b in blocks if "s2204 (direct LAN peer)" in b]
        check(len(direct) == 1, "cm4 has exactly one direct peer (s2204)", out)
        if direct:
            b = direct[0]
            check("AllowedIPs = 10.130.5.4/32" in b, "cm4->s2204 uses /32 (longest prefix)", b)
            check("Endpoint = 192.168.1.4:51820" in b, "cm4->s2204 endpoint = s2204 LAN IP", b)
            check("PersistentKeepalive = 25" in b, "cm4->s2204 has keepalive", b)
        check("k8s-proxy (direct LAN peer)" not in out, "cm4 does NOT peer k8s-proxy (diff group)", out)
        check(len(blocks) == 2, "cm4 has exactly 2 peers (hub + s2204)", out)

    if host == "s2204":
        check("ListenPort = 51820" in out, "s2204 has ListenPort", out)
        direct = [b for b in blocks if "cm4 (direct LAN peer)" in b]
        check(len(direct) == 1, "s2204 has exactly one direct peer (cm4)", out)
        if direct:
            b = direct[0]
            check("AllowedIPs = 10.130.5.3/32" in b, "s2204->cm4 uses /32", b)
            check("Endpoint = 192.168.1.3:51820" in b, "s2204->cm4 endpoint = cm4 LAN IP", b)
        check(len(blocks) == 2, "s2204 has exactly 2 peers (hub + cm4)", out)

    if host == "k8s-proxy":
        check("ListenPort" not in out, "k8s-proxy has NO ListenPort (hub-only)", out)
        check("direct LAN peer" not in out, "k8s-proxy has NO direct peers", out)
        check(len(blocks) == 1, "k8s-proxy has exactly 1 peer (hub only)", out)
        check("AllowedIPs = 10.130.5.0/24" in out, "k8s-proxy still uses hub /24", out)

    if host == "k8s":
        check("ListenPort = 51820" in out, "control plane keeps ListenPort", out)
        check("direct LAN peer" not in out, "control plane unaffected by direct logic", out)
        check(len(blocks) == 3, "control plane has all 3 worker peers (merged)", out)
        for w, ip in [("cm4", "10.130.5.3"), ("s2204", "10.130.5.4"), ("k8s-proxy", "10.130.5.21")]:
            check(any(f"# {w}" in b and f"{ip}/32" in b for b in blocks),
                  f"control plane peers {w} as {ip}/32", out)


print("\n" + "=" * 50)
if failures:
    print(f"{len(failures)} CHECK(S) FAILED")
    sys.exit(1)
print("ALL CHECKS PASSED")
