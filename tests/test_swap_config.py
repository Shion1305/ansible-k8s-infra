"""Validate the per-node swap opt-in declared in inventory.yml.

Kubernetes >= 1.35 supports swap, so a host can keep swap on by setting
`swap_enabled: true` (and, to have Ansible provision a swapfile, `swap_size`).
Defaults live in group_vars/all.yml; per-host overrides in inventory.yml.

This guards against the easy misconfigurations:
  * `swap_size` set without `swap_enabled` (silently ignored -> no swapfile),
  * a malformed `swap_size` (fallocate would fail mid-deploy),
  * an invalid `kubelet_swap_behavior`,
  * accidentally flipping swap on for a host that should not have it.

CI runs this via `just test` (pytest). It parses the YAML directly — no Ansible
or live hosts involved.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
INVENTORY = ROOT / "inventory.yml"
GROUP_VARS = ROOT / "group_vars" / "all.yml"

# Hosts expected to run with swap on. Update this set (deliberately) whenever you
# opt another node in — the test then re-checks its size/behavior too.
EXPECTED_SWAP_HOSTS = {"s2605"}

# fallocate size, e.g. "64G", "8192M", "2G" (suffix = powers of 1024).
SIZE_RE = re.compile(r"^\d+(\.\d+)?[KMGTP]?B?$")
VALID_BEHAVIORS = {"LimitedSwap", "NoSwap"}


def _defaults():
    return yaml.safe_load(GROUP_VARS.read_text())


def _hosts():
    """Yield (name, hostvars) for every inventory host."""
    inv = yaml.safe_load(INVENTORY.read_text())
    out = []
    for group in inv["all"]["children"].values():
        for host, hv in (group.get("hosts") or {}).items():
            out.append((host, hv or {}))
    return out


DEFAULTS = _defaults()
HOSTS = _hosts()
HOST_IDS = [h[0] for h in HOSTS]


def _effective(hostvars, key):
    """Host override if present, else the group_vars/all.yml default."""
    return hostvars.get(key, DEFAULTS.get(key))


def test_swap_defaults_are_conservative():
    """The cluster-wide default must keep swap disabled."""
    assert DEFAULTS.get("swap_enabled") is False, (
        "group_vars/all.yml must default swap_enabled to false"
    )
    assert DEFAULTS.get("swap_size", "") == "", (
        "group_vars/all.yml must default swap_size to empty"
    )
    assert DEFAULTS.get("kubelet_swap_behavior") in VALID_BEHAVIORS


@pytest.mark.parametrize("name,hv", HOSTS, ids=HOST_IDS)
def test_swap_size_implies_enabled(name, hv):
    """A swap_size with swap_enabled off would be silently ignored."""
    size = _effective(hv, "swap_size") or ""
    enabled = bool(_effective(hv, "swap_enabled"))
    if size:
        assert enabled, (
            f"{name}: swap_size='{size}' set but swap_enabled is false "
            f"(swapfile would never be created)"
        )


@pytest.mark.parametrize("name,hv", HOSTS, ids=HOST_IDS)
def test_swap_size_is_well_formed(name, hv):
    size = _effective(hv, "swap_size") or ""
    if size:
        assert SIZE_RE.match(size), (
            f"{name}: swap_size='{size}' is not a valid fallocate size"
        )


@pytest.mark.parametrize("name,hv", HOSTS, ids=HOST_IDS)
def test_swap_behavior_is_valid(name, hv):
    behavior = _effective(hv, "kubelet_swap_behavior")
    assert behavior in VALID_BEHAVIORS, (
        f"{name}: kubelet_swap_behavior='{behavior}' must be one of {VALID_BEHAVIORS}"
    )


def test_only_expected_hosts_enable_swap():
    enabled = {name for name, hv in HOSTS if bool(_effective(hv, "swap_enabled"))}
    assert enabled == EXPECTED_SWAP_HOSTS, (
        f"swap-enabled hosts {enabled} != expected {EXPECTED_SWAP_HOSTS}; "
        f"update EXPECTED_SWAP_HOSTS if this change is intentional"
    )


def test_s2605_has_64g_swap():
    hv = dict(HOSTS)["s2605"]
    assert bool(_effective(hv, "swap_enabled")) is True
    assert _effective(hv, "swap_size") == "64G"
