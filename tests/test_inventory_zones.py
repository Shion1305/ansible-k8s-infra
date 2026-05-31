"""Enforce the WireGuard overlay addressing plan declared in inventory.yml.

Every host and static peer must declare a `wireguard_zone` / `zone`, and the IP
it is assigned must fall inside that zone's CIDR (`wireguard_zones`). The zone is
also auto-derived from the IP, so a typo in either field is caught as a mismatch.

CI runs this via `just test` (pytest). It parses the YAML directly — no Ansible
or live hosts involved.
"""

import ipaddress
from pathlib import Path

import pytest
import yaml

INVENTORY = Path(__file__).parent.parent / "inventory.yml"


def _load():
    return yaml.safe_load(INVENTORY.read_text())


def _vars():
    return _load()["all"]["vars"]


def _zone_networks():
    return {z: ipaddress.ip_network(c) for z, c in _vars()["wireguard_zones"].items()}


def _entries():
    """Yield (name, ip, declared_zone) for every host and static peer."""
    inv = _load()
    out = []
    for group in inv["all"]["children"].values():
        for host, hv in (group.get("hosts") or {}).items():
            out.append((host, hv.get("wireguard_ip"), hv.get("wireguard_zone")))
    for peer, pv in (_vars().get("wireguard_static_peers") or {}).items():
        ip = (pv.get("allowed_ips") or "").split("/")[0] or None
        out.append((peer, ip, pv.get("zone")))
    return out


ENTRIES = _entries()
ENTRY_IDS = [e[0] for e in ENTRIES]


def _auto_zone(ip):
    """The single zone whose CIDR contains ip, or None."""
    addr = ipaddress.ip_address(ip)
    hits = [z for z, net in _zone_networks().items() if addr in net]
    return hits[0] if len(hits) == 1 else None


def test_at_least_one_entry():
    assert ENTRIES, "no hosts or static peers found in inventory.yml"


@pytest.mark.parametrize("name,ip,zone", ENTRIES, ids=ENTRY_IDS)
def test_entry_has_ip_and_zone(name, ip, zone):
    assert ip, f"{name}: missing WireGuard IP"
    assert zone, f"{name}: missing required `wireguard_zone`/`zone` attribute"


@pytest.mark.parametrize("name,ip,zone", ENTRIES, ids=ENTRY_IDS)
def test_zone_name_is_defined(name, ip, zone):
    zones = _zone_networks()
    assert zone in zones, (
        f"{name}: zone '{zone}' is not defined in wireguard_zones "
        f"(known: {sorted(zones)})"
    )


@pytest.mark.parametrize("name,ip,zone", ENTRIES, ids=ENTRY_IDS)
def test_ip_within_overlay(name, ip, zone):
    overlay = ipaddress.ip_network(_vars()["wireguard_network"])
    assert ipaddress.ip_address(ip) in overlay, f"{name}: {ip} is outside {overlay}"


@pytest.mark.parametrize("name,ip,zone", ENTRIES, ids=ENTRY_IDS)
def test_declared_zone_matches_ip(name, ip, zone):
    """The declared zone must equal the zone auto-derived from the IP."""
    derived = _auto_zone(ip)
    assert derived == zone, (
        f"{name}: IP {ip} is in zone '{derived}' but is declared as '{zone}'. "
        f"Fix the IP or the wireguard_zone so they agree."
    )


def test_no_duplicate_ips():
    seen = {}
    for name, ip, _ in ENTRIES:
        assert ip not in seen, f"duplicate IP {ip}: {seen.get(ip)} and {name}"
        seen[ip] = name


def test_zones_do_not_overlap_and_fit_overlay():
    overlay = ipaddress.ip_network(_vars()["wireguard_network"])
    nets = list(_zone_networks().items())
    for z, net in nets:
        assert net.subnet_of(overlay), f"zone {z} ({net}) is not within {overlay}"
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            (za, na), (zb, nb) = nets[i], nets[j]
            assert not na.overlaps(nb), f"zones overlap: {za} ({na}) and {zb} ({nb})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
