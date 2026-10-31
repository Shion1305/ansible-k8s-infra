#!/usr/bin/env python3
"""Guard a one-time format of s2605's dedicated SATA CI workspace disk."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import subprocess


HOST = "shion-ubuntu-2605"
DISK_LINK = Path("/dev/disk/by-id/ata-WDC_WDS500G2B0A-00SM50_200391450101")
PART_LINK = Path(f"{DISK_LINK}-part1")
DISK = "/dev/sda"
PART = "/dev/sda1"
DISK_BYTES = 500107862016
MOUNT = Path("/var/lib/garm-workspaces")
FS_LABEL = "garm-workspaces"
MOUNT_OPTIONS = {"defaults", "nodev", "nosuid", "noatime", "nofail",
                 "x-systemd.device-timeout=10s"}
OLD_PARTITIONS = (
    ("/dev/sda1", 1073741824, "vfat", "D059-D020", "ESP",
     "17d3cdfd-31bb-48bf-861e-b4f462635f6e"),
    ("/dev/sda2", 499033047040, "ext4",
     "f2732fe5-fb71-4020-a056-ae20cb77312e", "primary",
     "79245331-6eba-4335-8050-fc646ecdb666"),
)
LSBLK_COLUMNS = "NAME,TYPE,SIZE,FSTYPE,UUID,LABEL,PARTLABEL,PARTUUID,MOUNTPOINTS"


class SafetyError(Exception):
    """A precondition failed; leave the disk untouched."""


def command(*argv: str, allow_missing: bool = False) -> str:
    result = subprocess.run(argv, text=True, capture_output=True, check=False)
    if result.returncode == 1 and allow_missing:
        return ""
    if result.returncode != 0:
        raise SafetyError(f"{' '.join(argv[:2])} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def disk_layout() -> dict:
    data = json.loads(command(
        "lsblk", "--json", "--bytes", "--paths", "--output", LSBLK_COLUMNS,
        str(DISK_LINK),
    ))
    devices = data.get("blockdevices", [])
    if len(devices) != 1:
        raise SafetyError("expected exactly one SATA disk")
    return devices[0]


def classify_layout(disk: dict) -> tuple[str, str]:
    """Accept only the observed old layout or our one-partition ext4 layout."""
    if (disk.get("name"), disk.get("type"), disk.get("size")) != (
        DISK, "disk", DISK_BYTES,
    ):
        raise SafetyError("SATA device identity, type, or byte size changed")
    if any(disk.get(key) for key in ("fstype", "uuid", "label")):
        raise SafetyError("unexpected filesystem on the whole SATA device")

    children = disk.get("children", [])
    old = tuple((part.get("name"), part.get("size"), part.get("fstype"),
                 part.get("uuid"), part.get("partlabel"), part.get("partuuid"))
                for part in children)
    if old == OLD_PARTITIONS:
        return "old", ""

    if len(children) != 1:
        raise SafetyError("expected the original two partitions or one prepared partition")
    part = children[0]
    if (part.get("name"), part.get("type"), part.get("fstype"),
            part.get("label"), part.get("partlabel")) != (
                PART, "part", "ext4", FS_LABEL, FS_LABEL,
            ):
        raise SafetyError("the prepared partition does not have the expected ext4 labels")
    if not (DISK_BYTES - 4 * 1024 * 1024 <= part.get("size", 0) < DISK_BYTES):
        raise SafetyError("the prepared partition does not span the SATA disk")
    uuid = part.get("uuid")
    if not uuid or uuid in {item[3] for item in OLD_PARTITIONS} or not part.get("partuuid"):
        raise SafetyError("the prepared partition lacks a new filesystem/partition UUID")
    return "ready", uuid


def active_boot_partuuid(efi_boot_entries: str) -> str:
    current = re.search(r"^BootCurrent:\s*([0-9a-fA-F]{4})\s*$",
                        efi_boot_entries, re.MULTILINE)
    if not current:
        raise SafetyError("UEFI active boot entry is unavailable")
    entry = re.search(
        rf"^Boot{current.group(1)}\*?[^\n]*?HD\(\d+,GPT,([0-9a-fA-F-]{{36}}),",
        efi_boot_entries, re.MULTILINE | re.IGNORECASE,
    )
    if not entry:
        raise SafetyError("UEFI active boot entry has no GPT partition identity")
    return entry.group(1).lower()


def check_boot_sources() -> None:
    efi_source = ""
    for path in ("/", "/boot/efi"):
        source = command("findmnt", "--noheadings", "--output", "SOURCE",
                         "--mountpoint", path)
        if path == "/boot/efi":
            efi_source = source
        ancestors = command("lsblk", "--inverse", "--list", "--noheadings",
                            "--paths", "--output", "NAME", source).splitlines()
        if DISK in ancestors:
            raise SafetyError(f"SATA disk is an ancestor of {path}")
    mounted_efi_partuuid = command("lsblk", "--noheadings", "--output", "PARTUUID",
                                   efi_source).lower()
    if (not mounted_efi_partuuid or
            active_boot_partuuid(command("efibootmgr", "-v")) != mounted_efi_partuuid):
        raise SafetyError("UEFI BootCurrent is not the mounted non-SATA EFI partition")


def check_no_holders_or_swap(disk: dict) -> None:
    devices = [disk, *disk.get("children", [])]
    names = {device["name"] for device in devices}
    for device in devices:
        holders = Path("/sys/class/block") / Path(device["name"]).name / "holders"
        if not holders.is_dir() or any(holders.iterdir()):
            raise SafetyError(f"{device['name']} has a holder or unreadable holder state")
    for line in Path("/proc/swaps").read_text().splitlines()[1:]:
        if line.split():
            swap_source = os.path.realpath(line.split()[0])
            if (swap_source in names or swap_source.startswith(f"{MOUNT}/")):
                raise SafetyError("SATA disk, partition, or workspace file is active swap")


def check_mounts(disk: dict, state: str) -> bool:
    for device in [disk, *disk.get("children", [])]:
        allowed = {str(MOUNT)} if state == "ready" and device["name"] == PART else set()
        mounted = {value for value in device.get("mountpoints", []) if value}
        if mounted - allowed:
            raise SafetyError(f"unexpected mount on {device['name']}")

    if MOUNT.is_symlink() or (MOUNT.exists() and not MOUNT.is_dir()):
        raise SafetyError("workspace mountpoint is a symlink or not a directory")
    source = command("findmnt", "--noheadings", "--output", "SOURCE",
                     "--mountpoint", str(MOUNT), allow_missing=True)
    mounted = bool(source)
    if mounted and (state != "ready" or os.path.realpath(source) != PART):
        raise SafetyError("workspace mountpoint has an unexpected source")
    if not mounted and MOUNT.exists() and any(MOUNT.iterdir()):
        raise SafetyError("unmounted workspace directory contains data")
    return mounted


def check_fstab(state: str, uuid: str) -> None:
    entries = []
    for line in Path("/etc/fstab").read_text().splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) >= 4:
            entries.append(fields)
    target = [fields for fields in entries if fields[1] == str(MOUNT)]
    if len(target) > 1:
        raise SafetyError("multiple fstab entries target the workspace mountpoint")
    if target:
        fields = target[0]
        if (state != "ready" or fields[0] != f"UUID={uuid}"
                or fields[2] != "ext4" or not MOUNT_OPTIONS.issubset(set(fields[3].split(",")))
                or "noexec" in fields[3].split(",")):
            raise SafetyError("workspace fstab entry does not match the prepared SATA filesystem")
    old_uuids = {f"UUID={item[3]}" for item in OLD_PARTITIONS}
    old_devices = {item[0] for item in OLD_PARTITIONS}
    for fields in entries:
        if (fields[0] in old_uuids or
                (fields[0].startswith("/dev/") and os.path.realpath(fields[0]) in old_devices
                 and state == "old")):
            raise SafetyError("old SATA filesystem is referenced in fstab")
        if uuid and fields[0] == f"UUID={uuid}" and fields[1] != str(MOUNT):
            raise SafetyError("prepared SATA filesystem is mounted elsewhere by fstab")
        if (state == "ready" and fields[0].startswith("/dev/")
                and os.path.realpath(fields[0]) == PART):
            raise SafetyError("prepared SATA filesystem must use its UUID in fstab")


def inspect() -> dict:
    if socket.gethostname() != HOST:
        raise SafetyError("this playbook may run only on shion-ubuntu-2605")
    if not DISK_LINK.is_symlink() or os.path.realpath(DISK_LINK) != DISK:
        raise SafetyError("exact physical SATA by-id link does not resolve to /dev/sda")
    disk = disk_layout()
    state, uuid = classify_layout(disk)
    check_boot_sources()
    check_no_holders_or_swap(disk)
    mounted = check_mounts(disk, state)
    check_fstab(state, uuid)
    if state == "ready" and os.path.realpath(PART_LINK) != PART:
        raise SafetyError("prepared partition by-id link does not resolve to /dev/sda1")
    return {"layout": state, "uuid": uuid, "mounted": mounted,
            "device": str(DISK_LINK), "device_bytes": DISK_BYTES,
            "mountpoint": str(MOUNT)}


def check_single_new_partition() -> None:
    """Verify parted replaced the old table before allowing mkfs."""
    disk = disk_layout()
    children = disk.get("children", [])
    if (disk.get("name"), disk.get("size"), len(children)) != (DISK, DISK_BYTES, 1):
        raise SafetyError("partition table did not converge to one SATA partition")
    part = children[0]
    if (part.get("name"), part.get("type"), part.get("partlabel")) != (
        PART, "part", FS_LABEL,
    ) or not (DISK_BYTES - 4 * 1024 * 1024 <= part.get("size", 0) < DISK_BYTES):
        raise SafetyError("new partition identity or size is unexpected")
    if os.path.realpath(PART_LINK) != PART:
        raise SafetyError("new partition by-id link does not resolve to /dev/sda1")
    check_no_holders_or_swap(disk)
    for device in [disk, part]:
        if any(device.get("mountpoints", [])):
            raise SafetyError("new SATA partition unexpectedly mounted before format")


def initialize() -> dict:
    if os.geteuid() != 0:
        raise SafetyError("initialization requires root")
    with Path("/run/lock/garm-workspaces-init.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = inspect()
        if before["layout"] == "ready":
            return {**before, "changed": False}
        command("parted", "--script", "--align", "optimal", str(DISK_LINK),
                "mklabel", "gpt", "mkpart", FS_LABEL, "ext4", "1MiB", "100%")
        command("udevadm", "settle", "--timeout=30")
        check_single_new_partition()
        command("mkfs.ext4", "-F", "-L", FS_LABEL, str(PART_LINK))
        command("udevadm", "settle", "--timeout=30")
        after = inspect()
        if after["layout"] != "ready":
            raise SafetyError("formatted SATA disk did not pass postcondition checks")
        return {**after, "changed": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initialize", action="store_true",
                        help="replace the exact old SATA partition table and format ext4")
    args = parser.parse_args()
    result = initialize() if args.initialize else {**inspect(), "changed": False}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SafetyError as error:
        raise SystemExit(f"refusing SATA disk change: {error}") from error
