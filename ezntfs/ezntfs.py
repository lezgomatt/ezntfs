from collections import namedtuple
import os
import re
import subprocess


Volume = namedtuple("Volume", ["id", "node", "name", "mounted", "size", "read_only", "internal"])


def get_ntfs_volumes():
    # NOTE: A "Windows_NTFS" partition type might actually be using the exFAT file system.
    # The types listed by `diskutil list` refer to the partition type not the file system.
    # "Windows_NTFS" is used for MBR partition tables and "Microsoft Basic Data" for GPT.
    # To determine the actual file system used, we use `diskutil info` later on.

    list_out = run(["diskutil", "list"], capture_output=True)

    disk_ids = [
        re.search(r"\S+$", line)[0]
        for line in list_out.split("\n")
        if re.match(r"^\s*\d+:\s*(Windows_NTFS|Microsoft Basic Data) ", line)
    ]

    volumes = {}

    for id in disk_ids:
        info_out = run(["diskutil", "info", id], capture_output=True)

        info = {
            line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
            for line in info_out.split("\n") if line != ""
        }

        if (
            info["Type (Bundle)"] == "ntfs"
            and info["File System Personality"] == "NTFS"
            # Older versions of diskutil used the label "Read-Only Media"
            and (info.get("Media Read-Only") or info.get("Read-Only Media")) == "No"
        ):
            volumes[id] = Volume(
                id=id,
                node=info["Device Node"],
                name=info["Volume Name"] if info["Volume Name"] != "" else "Untitled",
                mounted=info["Mounted"] == "Yes",
                size=re.match(r"\d+(\.\d+)? \S+", info["Disk Size"])[0],
                # Older versions of diskutil used the label "Read-Only Volume"
                read_only=(info.get("Volume Read-Only") or info.get("Read-Only Volume")).startswith("Yes"),
                internal=info.get("Device Location") == "Internal"
            )

    return volumes


def mount(volume, *, sudo=False):
    cmd = build_mount_command(
        volume,
        user_id=os.getenv("SUDO_UID", os.getuid()),
        group_id=os.getenv("SUDO_GID", os.getgid()),
        path=genrate_path(volume),
    )

    if sudo:
        # assumes ntfs-3g has NOPASSWD set in sudoers
        return run(["sudo", "--non-interactive"] + cmd)
    else:
        return run(cmd)


def build_mount_command(volume, *, user_id, group_id, path):
    return [
        "ntfs-3g",
        "-o", f"volname={volume.name}",
        "-o", "local",
        "-o", "allow_other",
        "-o", "auto_xattr",
        "-o", f"uid={user_id}",
        "-o", f"gid={group_id}",
        "-o", "windows_names",
        volume.node, path,
    ]


def genrate_path(volume):
    path = f"/Volumes/{volume.name}"
    if not os.path.exists(path):
        return path

    counter = 1
    while os.path.exists(f"{path} {counter}"):
        counter += 1

    return f"{path} {counter}"


def macos_mount(volume):
    return run(["diskutil", "mount", volume.id])


def macos_unmount(volume):
    return run(["diskutil", "unmount", volume.id])


def run(command, capture_output=False):
    if capture_output:
        result = subprocess.run(command, capture_output=True, check=True)
        return result.stdout.decode()
    else:
        result = subprocess.run(command)
        return result.returncode == 0
