"""Destructive SATA initialization must accept only the exact reviewed layouts."""

from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_s2605_garm_workspaces as disk  # noqa: E402


def old_layout():
    return {
        "name": "/dev/sda", "type": "disk", "size": disk.DISK_BYTES,
        "fstype": None, "uuid": None, "label": None,
        "mountpoints": [None],
        "children": [
            {"name": name, "type": "part", "size": size,
             "fstype": fstype, "uuid": uuid, "partlabel": partlabel,
             "partuuid": partuuid, "mountpoints": [None]}
            for name, size, fstype, uuid, partlabel, partuuid in disk.OLD_PARTITIONS
        ],
    }


def ready_layout():
    result = old_layout()
    result["children"] = [{
        "name": "/dev/sda1", "type": "part", "size": disk.DISK_BYTES - 2 * 1024 * 1024,
        "fstype": "ext4", "uuid": "new-filesystem-uuid", "label": disk.FS_LABEL,
        "partlabel": disk.FS_LABEL, "partuuid": "new-partition-uuid",
        "mountpoints": [None],
    }]
    return result


def test_exact_old_layout_is_the_only_destructive_starting_state():
    assert disk.classify_layout(old_layout()) == ("old", "")
    for change in (
        lambda state: state["children"][1].update(uuid="different"),
        lambda state: state["children"][0].update(partuuid="different"),
        lambda state: state.update(size=disk.DISK_BYTES - 1),
        lambda state: state["children"].append({"name": "/dev/sda3"}),
    ):
        altered = old_layout()
        change(altered)
        with pytest.raises(disk.SafetyError):
            disk.classify_layout(altered)


def test_prepared_layout_requires_new_ext4_identity_and_one_full_disk_partition():
    assert disk.classify_layout(ready_layout()) == ("ready", "new-filesystem-uuid")
    for change in (
        lambda state: state["children"][0].update(uuid="D059-D020"),
        lambda state: state["children"][0].update(label="unexpected"),
        lambda state: state["children"][0].update(size=400 * 1024**3),
        lambda state: state["children"].append({"name": "/dev/sda2"}),
    ):
        altered = ready_layout()
        change(altered)
        with pytest.raises(disk.SafetyError):
            disk.classify_layout(altered)


def test_active_uefi_entry_must_match_mounted_non_sata_efi_partition():
    entries = (
        "BootCurrent: 0004\n"
        "Boot0004* ubuntu HD(1,GPT,b265b44c-3411-4c9b-8307-c499b8035754,0x800,0x200000)\n"
        "Boot0005* ubuntu HD(1,GPT,17d3cdfd-31bb-48bf-861e-b4f462635f6e,0x800,0x200000)\n"
    )
    assert disk.active_boot_partuuid(entries) == "b265b44c-3411-4c9b-8307-c499b8035754"
    with pytest.raises(disk.SafetyError, match="active boot entry"):
        disk.active_boot_partuuid(entries.replace("BootCurrent: 0004", "BootCurrent: 0006"))


def test_unmounted_workspace_directory_must_be_empty(tmp_path, monkeypatch):
    mount = tmp_path / "garm-workspaces"
    mount.mkdir()
    monkeypatch.setattr(disk, "MOUNT", mount)
    monkeypatch.setattr(disk, "command", lambda *args, **kwargs: "")
    assert disk.check_mounts(ready_layout(), "ready") is False
    (mount / "existing-data").write_text("unexpected")
    with pytest.raises(disk.SafetyError, match="contains data"):
        disk.check_mounts(ready_layout(), "ready")


def test_mount_from_other_device_is_rejected(tmp_path, monkeypatch):
    mount = tmp_path / "garm-workspaces"
    mount.mkdir()
    monkeypatch.setattr(disk, "MOUNT", mount)
    monkeypatch.setattr(disk, "command", lambda *args, **kwargs: "/dev/nvme0n1p2")
    with pytest.raises(disk.SafetyError, match="unexpected source"):
        disk.check_mounts(ready_layout(), "ready")


def test_default_cli_mode_cannot_initialize(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prepare_s2605_garm_workspaces.py"])
    monkeypatch.setattr(disk, "inspect", lambda: {"layout": "old"})
    monkeypatch.setattr(disk, "initialize", lambda: pytest.fail("format path was called"))
    disk.main()
    assert '"layout": "old"' in capsys.readouterr().out


def test_initialize_does_not_format_an_already_prepared_disk(tmp_path, monkeypatch):
    lock = tmp_path / "init.lock"
    original = disk.Path
    monkeypatch.setattr(disk, "Path", lambda path: lock if path == "/run/lock/garm-workspaces-init.lock" else original(path))
    monkeypatch.setattr(disk.os, "geteuid", lambda: 0)
    monkeypatch.setattr(disk, "inspect", lambda: {"layout": "ready", "uuid": "new-filesystem-uuid"})
    monkeypatch.setattr(disk, "command", lambda *args, **kwargs: pytest.fail("destructive command was called"))
    assert disk.initialize() == {"layout": "ready", "uuid": "new-filesystem-uuid", "changed": False}


def test_failed_preflight_cannot_run_destructive_commands(tmp_path, monkeypatch):
    lock = tmp_path / "init.lock"
    original = disk.Path
    monkeypatch.setattr(disk, "Path", lambda path: lock if path == "/run/lock/garm-workspaces-init.lock" else original(path))
    monkeypatch.setattr(disk.os, "geteuid", lambda: 0)

    def refuse():
        raise disk.SafetyError("unexpected disk layout")

    monkeypatch.setattr(disk, "inspect", refuse)
    monkeypatch.setattr(disk, "command", lambda *args, **kwargs: pytest.fail("destructive command was called"))
    with pytest.raises(disk.SafetyError, match="unexpected disk layout"):
        disk.initialize()


def test_conflicting_fstab_mount_is_rejected(tmp_path, monkeypatch):
    mount = tmp_path / "garm-workspaces"
    fstab = tmp_path / "fstab"
    fstab.write_text(f"UUID=other {mount} ext4 defaults,nodev,nosuid,noatime 0 2\n")
    monkeypatch.setattr(disk, "MOUNT", mount)
    original = disk.Path
    monkeypatch.setattr(disk, "Path", lambda path: fstab if path == "/etc/fstab" else original(path))
    with pytest.raises(disk.SafetyError, match="fstab entry"):
        disk.check_fstab("ready", "new-filesystem-uuid")
