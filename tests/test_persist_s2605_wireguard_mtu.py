"""The scoped MTU writer must leave every non-MTU byte intact."""

from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from persist_s2605_wireguard_mtu import SafetyError, config_parts, plan_mtu_edit, without_interface_mtu  # noqa: E402


CONFIG = (b"[Interface]\nAddress = 10.130.5.67/24\nPrivateKey = fixture-only\n"
          b"# PublicKey = comment-only\n\n"
          b"[Peer]\nPublicKey = hub-fixture\nAllowedIPs = 10.130.5.0/24\n\n"
          b"[Peer]\nPublicKey = direct-fixture\nAllowedIPs = 10.130.5.66/32\n")


def test_add_mtu_preserves_exact_non_mtu_bytes_and_peer_order():
    proposed = plan_mtu_edit(CONFIG)
    assert proposed == CONFIG.replace(b"Address = 10.130.5.67/24\n",
                                      b"Address = 10.130.5.67/24\nMTU = 1380\n")
    assert without_interface_mtu(proposed) == CONFIG
    assert config_parts(proposed)[3] == [b"hub-fixture", b"direct-fixture"]
    assert plan_mtu_edit(proposed) == proposed


def test_replace_existing_mtu_changes_only_that_line():
    original = CONFIG.replace(b"Address = 10.130.5.67/24\n",
                              b"Address = 10.130.5.67/24\nMTU = 1420\n")
    proposed = plan_mtu_edit(original)
    assert proposed == original.replace(b"MTU = 1420\n", b"MTU = 1380\n")
    assert without_interface_mtu(original) == without_interface_mtu(proposed)


def test_crlf_is_preserved():
    original = CONFIG.replace(b"\n", b"\r\n")
    proposed = plan_mtu_edit(original)
    assert b"Address = 10.130.5.67/24\r\nMTU = 1380\r\n" in proposed
    assert without_interface_mtu(proposed) == original


@pytest.mark.parametrize("unsafe", [
    CONFIG.replace(b"PrivateKey = fixture-only", b"SaveConfig = true\nPrivateKey = fixture-only"),
    CONFIG.replace(b"PrivateKey = fixture-only", b"MTU = 1400\nMTU = 1420\nPrivateKey = fixture-only"),
    CONFIG.replace(b"PrivateKey = fixture-only", b"MTU = 1420 # unexpected comment\nPrivateKey = fixture-only"),
    CONFIG.replace(b"PublicKey = direct-fixture", b"PublicKey = hub-fixture"),
    CONFIG.replace(b"Address = 10.130.5.67/24\n", b""),
])
def test_reject_ambiguous_or_peer_unsafe_config(unsafe):
    with pytest.raises(SafetyError):
        plan_mtu_edit(unsafe)
