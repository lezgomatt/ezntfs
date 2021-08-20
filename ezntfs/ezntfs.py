from collections import namedtuple
from enum import Enum
import os
import re
import shutil
import subprocess


EnvironmentInfo = namedtuple("EnvironmentInfo", ["fuse", "ntfs_3g", "can_mount"])
Volume = namedtuple("Volume", ["id", "node", "name", "mounted", "mount_path", "size", "access", "internal"])
Access = Enum("Access", ["READ_ONLY", "WRITABLE", "NOT_APPLICABLE", "UNKNOWN"])

NTFS_3G_PATH = os.getenv("NTFS_3G_PATH", shutil.which("ntfs-3g"))

def get_environment_info():
    fuse = (
        "macfuse" if os.path.exists("/Library/Filesystems/macfuse.fs")
        else "osxfuse" if os.path.exists("/Library/Filesystems/osxfuse.fs")
        else None
    )

    ntfs_3g = get_ntfs_3g_version()

    test_cmd = ["sudo", "--non-interactive", NTFS_3G_PATH, "--version"]
    can_mount = (
        fuse is not None
        and ntfs_3g is not None
        and subprocess.run(test_cmd, capture_output=True).returncode == 0
    )

    return EnvironmentInfo(fuse=fuse, ntfs_3g=ntfs_3g, can_mount=can_mount)


def get_ntfs_3g_version():
    if NTFS_3G_PATH is None:
        return None

    result = subprocess.run([NTFS_3G_PATH, "--version"], capture_output=True)
    if result.returncode != 0:
        return None

    version = result.stderr.decode().strip()
    m = re.match(r"ntfs-3g (\d+)\.(\d+)\.(\d+)(?:AR\.(\d+))? external FUSE (\d+)", version)
    if m is None:
        return None

    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))
    ar = int(m.group(4)) if m.group(4) is not None else 0

    return (year, month, day, ar)


def get_all_ntfs_volumes():
    # NOTE: A "Windows_NTFS" partition type might actually be using the exFAT file system.
    # The types listed by `diskutil list` refer to the partition type not the file system.
    # "Windows_NTFS" is used for MBR partition tables and "Microsoft Basic Data" for GPT.
    # To determine the actual file system used, we use `diskutil info` later on.
    # Simpler volumes might not have a partition type set, so we always check those too.

    list_out = run(["diskutil", "list"], capture_output=True)
    lines = list_out.split("\n")

    type_last_char_index = next(line for line in lines if re.match("\s*#:\s*TYPE", line)).index("E")

    disk_ids = [
        re.search(r"\S+$", line)[0]
        for line in lines
        if re.match(r"\s*\d+:\s*(Windows_NTFS|Microsoft Basic Data) ", line)
        or re.match(r"\s*0:\s*", line) and line[type_last_char_index] == " "
    ]

    return { vol.id: vol for vol in map(get_ntfs_volume, disk_ids) if vol is not None }


def get_ntfs_volume(idOrPath):
    info_out = run(["diskutil", "info", idOrPath], capture_output=True)

    info = {
        line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
        for line in info_out.split("\n") if line != ""
    }

    if (
        info["Type (Bundle)"] != "ntfs"
        or info["File System Personality"] != "NTFS"
        # Older versions of diskutil used the label "Read-Only Media"
        or (info.get("Media Read-Only") or info.get("Read-Only Media")) == "Yes"
    ):
        return None

    # Older versions of diskutil used the label "Read-Only Volume"
    ro_value = info.get("Volume Read-Only") or info.get("Read-Only Volume")
    # Remove trailing notes enclosed in parentheses, examples:
    # - "Yes (read-only mount flag set)" => "Yes"
    # - "Not applicable (not mounted)" => "Not applicable"
    ro_value = re.sub(r"\s*\(.*\)$", "", ro_value)
    access = (
            Access.READ_ONLY if ro_value == "Yes"
            else Access.WRITABLE if ro_value == "No"
            else Access.NOT_APPLICABLE if ro_value == "Not applicable"
            else Access.UNKNOWN
    )

    return Volume(
        id=info["Device Identifier"],
        node=info["Device Node"],
        name=info["Volume Name"] if info["Volume Name"] != "" else "Untitled",
        mounted=info["Mounted"] == "Yes",
        mount_path=info.get("Mount Point"),
        size=re.match(r"\d+(\.\d+)? \S+", info["Disk Size"])[0],
        access=access,
        internal=info["Device Location"] == "Internal"
    )


def mount(volume, version=None, path=None):
    if path is None:
        path = genrate_path(volume)

    cmd = build_mount_command(
        volume,
        version=version,
        user_id=os.getenv("SUDO_UID", os.getuid()),
        group_id=os.getenv("SUDO_GID", os.getgid()),
        path=path,
    )

    # User must run this command as root (via sudo)
    # or ntfs-3g must have NOPASSWD set in sudoers
    return run(["sudo", "--non-interactive"] + cmd)


def build_mount_command(volume, *, version, user_id, group_id, path):
    xattr_option = "user_xattr" if version is not None and version >= (2017, 3, 23, 6) else "auto_xattr"

    return [
        NTFS_3G_PATH,
        "-o", f"volname={volume.name}",
        "-o", "local",
        "-o", "allow_other",
        "-o", xattr_option,
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
