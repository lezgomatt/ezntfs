#!/usr/bin/env python3

from collections import namedtuple
import os
import re
import shutil
import subprocess
import sys


usage = f"""Usage: ezntfs <command>

Commands:
  list         List all NTFS volumes available for mounting
  all          Mount all NTFS volumes via ntfs-3g
  <disk id>    Mount a specific NTFS volume via ntfs-3g
"""

Volume = namedtuple("Volume", ["id", "node", "name", "mounted", "size", "read_only"])

def cli(command):
    volumes = get_ntfs_volumes()

    if command == "list":
        if len(volumes) == 0:
            print("No NTFS volumes found.")

        for id, volume in volumes.items():
            name = f"{id}: {volume.name} [{volume.size}]"
            details = (
                "mounted: " + ("yes" if volume.mounted else "no")
                + (" (read-only)" if volume.read_only else "")
            )

            print(f"{name} -- {details}")

        sys.exit(0)

    if command == "all":
        run_checks()
        print(f"Found {len(volumes)} NTFS volume(s).")

        for id, volume in volumes.items():
            print()
            mount(volume)

        sys.exit(0)

    if command in volumes:
        run_checks()
        ok = mount(volumes[command])
        sys.exit(0 if ok else 1)

    print(f"ezntfs: Invalid command or disk id.")
    print()
    print(usage)

    sys.exit(1)


def run_checks():
    if shutil.which("ntfs-3g") is None:
        sys.exit("ERROR: Could not find ntfs-3g.")

    if not os.geteuid() == 0:
        sys.exit("ERROR: Need root privileges to mount via ntfs-3g.")


def get_ntfs_volumes():
    # NOTE: A "Windows_NTFS" partition type might actually be using the exFAT file system.
    # The types listed by `diskutil list` refer to the partition type not the file system.
    # "Windows_NTFS" is used for MBR partition tables and "Microsoft Basic Data" for GPT.
    # To determine the actual file system used, we use `diskutil info` later on.

    list_out = subprocess.run(["diskutil", "list"], capture_output=True, check=True).stdout.decode()

    disk_ids = [
        re.search(r"\S+$", line)[0]
        for line in list_out.split("\n")
        if re.match(r"^\s*\d+:\s*(Windows_NTFS|Microsoft Basic Data) ", line)
    ]

    volumes = {}

    for id in disk_ids:
        info_out = subprocess.run(["diskutil", "info", id], capture_output=True, check=True).stdout.decode()

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
            )

    return volumes


def mount(volume):
    print(f"Volume: {volume.name} [{volume.size}]")

    if volume.mounted:
        if not volume.read_only:
            print(f"{volume.name} is already writable.")
            return False

        print("Unmounting...")
        try:
            subprocess.run(["diskutil", "unmount", volume.id], check=True)
        except:
            return False

    path = f"/Volumes/{volume.name}"

    if os.path.exists(path):
        counter = 1
        while os.path.exists(path + " " + str(counter)):
            counter += 1

        path = path + " " + str(counter)

    user_id = os.getenv("SUDO_UID", os.getuid())
    group_id = os.getenv("SUDO_GID", os.getgid())

    mount_cmd = [
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

    print(f"Mounting on `{path}` via ntfs-3g...")
    try:
        subprocess.run(mount_cmd, check=True)
        print(f"Successfully mounted {volume.name}.")
        return True
    except:
        print(f"Failed to mount {volume.name}.")

        if volume.mounted:
            print("Remounting via macOS...")
            subprocess.run(["diskutil", "mount", volume.id], check=True)

        return False


def main():
    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    cli(sys.argv[1])


if __name__ == "__main__":
    main()
