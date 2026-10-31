#!/usr/bin/env python3
"""Persist s2605's already-active wg0 MTU without rendering its peer config."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import time


CONFIG = Path("/etc/wireguard/wg0.conf")
HOST = "shion-ubuntu-2605"
MTU = 1380
SECTION = re.compile(rb"^\s*\[([^]]+)\]\s*$")
DIRECTIVE = re.compile(rb"^\s*([A-Za-z]+)\s*=\s*([^#\r\n]*)")


class SafetyError(Exception):
    """A precondition failed; leave the live configuration untouched."""


def config_parts(data: bytes) -> tuple[list[bytes], list[int], list[int], list[bytes]]:
    """Return original lines, Interface Address/MTU locations, and peer keys."""
    lines = data.splitlines(keepends=True)
    section = b""
    interface_count = 0
    addresses: list[int] = []
    mtu_lines: list[int] = []
    peer_keys: list[bytes] = []
    peer_count = 0
    for index, line in enumerate(lines):
        content = line.split(b"#", 1)[0].strip()
        match = SECTION.fullmatch(content)
        if match:
            section = match.group(1).lower()
            interface_count += section == b"interface"
            peer_count += section == b"peer"
            continue
        match = DIRECTIVE.match(content)
        if not match:
            continue
        key, value = match.group(1).lower(), match.group(2).strip()
        if section == b"interface":
            if key == b"address":
                addresses.append(index)
            elif key == b"mtu":
                if not re.fullmatch(rb"\s*MTU\s*=\s*[0-9]+\s*", line, re.I):
                    raise SafetyError("MTU directive has unexpected formatting")
                mtu_lines.append(index)
            elif key == b"saveconfig" and value.lower() not in (b"false", b"no", b"0"):
                raise SafetyError("SaveConfig may overwrite the MTU on shutdown")
        elif section == b"peer" and key == b"publickey":
            peer_keys.append(value)
    if interface_count != 1 or len(addresses) != 1 or len(mtu_lines) > 1:
        raise SafetyError("expected one Interface, one Address, and at most one MTU")
    if not peer_keys or len(peer_keys) != peer_count or len(set(peer_keys)) != len(peer_keys):
        raise SafetyError("peer sections do not have unique PublicKey directives")
    return lines, addresses, mtu_lines, peer_keys


def without_interface_mtu(data: bytes) -> bytes:
    lines, _, mtu_lines, _ = config_parts(data)
    return b"".join(line for index, line in enumerate(lines) if index not in mtu_lines)


def plan_mtu_edit(data: bytes) -> bytes:
    lines, addresses, mtu_lines, peer_keys = config_parts(data)
    if mtu_lines:
        old = lines[mtu_lines[0]]
        newline = b"\r\n" if old.endswith(b"\r\n") else b"\n"
        lines[mtu_lines[0]] = b"MTU = 1380" + newline
    else:
        old = lines[addresses[0]]
        if not old.endswith(b"\n"):
            raise SafetyError("Address line must end with a newline")
        newline = b"\r\n" if old.endswith(b"\r\n") else b"\n"
        lines.insert(addresses[0] + 1, b"MTU = 1380" + newline)
    proposed = b"".join(lines)
    if without_interface_mtu(data) != without_interface_mtu(proposed):
        raise SafetyError("non-MTU configuration changed")
    if config_parts(proposed)[3] != peer_keys:
        raise SafetyError("peer configuration changed")
    return proposed


def read_config() -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(CONFIG, flags)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise SafetyError("configuration must be a regular, unlinked file")
        if metadata.st_uid != 0 or metadata.st_gid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise SafetyError("configuration must be owned by root:root with mode 0600")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read()
    finally:
        os.close(fd)
    return data, metadata


def runtime_state() -> tuple[int, set[bytes]]:
    link = json.loads(subprocess.check_output(["ip", "-j", "link", "show", "dev", "wg0"]))
    peers = set(subprocess.check_output(["wg", "show", "wg0", "peers"]).splitlines())
    return link[0]["mtu"], peers


def write_all(fd: int, data: bytes) -> None:
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def sync_config_directory() -> None:
    directory_fd = os.open(CONFIG.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def persist(data: bytes, proposed: bytes, metadata: os.stat_result) -> str:
    current, current_metadata = read_config()
    if current != data or (current_metadata.st_dev, current_metadata.st_ino) != (metadata.st_dev, metadata.st_ino):
        raise SafetyError("configuration changed since preflight")

    backup = CONFIG.with_name(f"{CONFIG.name}.pre-mtu-{int(time.time())}-{os.getpid()}")
    backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.fchmod(backup_fd, 0o600)
    os.fchown(backup_fd, 0, 0)
    write_all(backup_fd, data)
    sync_config_directory()

    temporary_fd, temporary_name = tempfile.mkstemp(prefix=f".{CONFIG.name}.mtu-", dir=CONFIG.parent)
    try:
        os.fchmod(temporary_fd, 0o600)
        os.fchown(temporary_fd, 0, 0)
        write_all(temporary_fd, proposed)
        os.replace(temporary_name, CONFIG)
        sync_config_directory()
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)

    saved, _ = read_config()
    if saved != proposed or without_interface_mtu(saved) != without_interface_mtu(data):
        raise SafetyError("post-write verification failed; restore the root-only backup")
    return str(backup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-sha256")
    arguments = parser.parse_args()
    if socket.gethostname().split(".")[0] != HOST:
        raise SafetyError("this command is restricted to shion-ubuntu-2605")
    if os.geteuid() != 0:
        raise SafetyError("root privileges are required")
    data, metadata = read_config()
    proposed = plan_mtu_edit(data)
    configured_peers = set(config_parts(data)[3])
    runtime_mtu, runtime_peers = runtime_state()
    if runtime_mtu != MTU:
        raise SafetyError("runtime wg0 MTU must already be 1380")
    if runtime_peers != configured_peers:
        raise SafetyError("runtime and configured peer sets differ")
    before_sha = hashlib.sha256(data).hexdigest()
    if arguments.apply:
        if not arguments.expected_sha256 or not re.fullmatch(r"[0-9a-f]{64}", arguments.expected_sha256):
            raise SafetyError("--apply requires --expected-sha256 from a fresh preview")
        if arguments.expected_sha256 != before_sha:
            raise SafetyError("configuration hash changed since preview")
    elif arguments.expected_sha256:
        raise SafetyError("--expected-sha256 is valid only with --apply")
    changed = proposed != data
    backup = persist(data, proposed, metadata) if arguments.apply and changed else None
    print(json.dumps({"changed": changed if arguments.apply else False,
                      "would_change": changed, "before_sha256": before_sha,
                      "after_sha256": hashlib.sha256(proposed).hexdigest(),
                      "peer_count": len(configured_peers), "runtime_mtu": runtime_mtu,
                      "backup": backup}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, SafetyError) as error:
        raise SystemExit(f"Safety check failed: {error}") from None
