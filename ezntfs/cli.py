import os
import sys

from . import ezntfs
from . import __version__

USAGE = f"""Usage: ezntfs <command>

Commands:
  list         List all NTFS volumes available for mounting
  all          Mount all NTFS volumes via ntfs-3g
  <disk id>    Mount a specific NTFS volume via ntfs-3g

Version: {__version__}
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE, end="")
        sys.exit(1)

    env = ezntfs.get_environment_info()
    if env.fuse is None:
        sys.exit("ERROR: Failed to detect macFUSE.")
    if env.ntfs_3g is None:
        sys.exit("ERROR: Failed to detect ntfs-3g.")

    command = sys.argv[1]
    volumes = ezntfs.get_all_ntfs_volumes()

    if command == "list":
        list_volumes(volumes)
        sys.exit(0)

    if command == "all":
        if not env.can_mount:
            sys.exit("ERROR: Need root privileges to mount via ntfs-3g.")

        mount_all_volumes(volumes, version=env.ntfs_3g)
        sys.exit(0)

    if command in volumes:
        if not env.can_mount:
            sys.exit("ERROR: Need root privileges to mount via ntfs-3g.")

        ok = mount_volume(volumes[command], version=env.ntfs_3g)
        sys.exit(0 if ok else 1)

    print("ezntfs: Invalid command or disk id.")
    print()
    print(USAGE, end="")
    sys.exit(1)


def list_volumes(volumes):
    if len(volumes) == 0:
        print("No NTFS volumes found.")

    for id, volume in volumes.items():
        name = f"{id}: {volume.name} [{volume.size}]"
        is_read_only = volume.access is ezntfs.Access.READ_ONLY
        details = (
            "mounted: " + ("yes" if volume.mounted else "no")
            + (" (read-only)" if is_read_only else "")
        )

        print(f"{name} -- {details}")


def mount_all_volumes(volumes, version):
    print(f"Found {len(volumes)} NTFS volume(s).")

    for id, volume in volumes.items():
        print()
        mount_volume(volume, version)


def mount_volume(volume, version):
    print(f"Volume: {volume.name} [{volume.size}]")

    if volume.access is ezntfs.Access.WRITABLE:
        print(f"{volume.name} is already writable.")
        return True

    if volume.mounted:
        print("Unmounting...")
        ok = ezntfs.macos_unmount(volume)
        if not ok:
            return False

    print("Mounting via ntfs-3g...")
    ok = ezntfs.mount(volume, version=version, path=volume.mount_path)
    if ok:
        print(f"Successfully mounted {volume.name}.")
        return True
    else:
        print(f"Failed to mount {volume.name}.")

        if volume.mounted:
            print("Remounting via macOS...")
            ezntfs.macos_mount(volume)

        return False
