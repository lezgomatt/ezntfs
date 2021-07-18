import os
import shutil
import sys

from . import ezntfs


usage = f"""Usage: ezntfs <command>

Commands:
  list         List all NTFS volumes available for mounting
  all          Mount all NTFS volumes via ntfs-3g
  <disk id>    Mount a specific NTFS volume via ntfs-3g
"""


def main():
    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    command = sys.argv[1]
    volumes = ezntfs.get_all_ntfs_volumes()

    if command == "list":
        list_volumes(volumes)
    elif command == "all":
        run_checks()
        mount_all_volumes(volumes)
    elif command in volumes:
        run_checks()
        ok = mount_volume(volumes[command])
        sys.exit(0 if ok else 1)
    else:
        print(f"ezntfs: Invalid command or disk id.")
        print()
        print(usage)
        sys.exit(1)


def run_checks():
    if shutil.which("ntfs-3g") is None:
        sys.exit("ERROR: Could not find ntfs-3g.")

    if not os.geteuid() == 0:
        sys.exit("ERROR: Need root privileges to mount via ntfs-3g.")


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


def mount_all_volumes(volumes):
    print(f"Found {len(volumes)} NTFS volume(s).")

    for id, volume in volumes.items():
        print()
        mount_volume(volume)


def mount_volume(volume):
    print(f"Volume: {volume.name} [{volume.size}]")

    if volume.access is ezntfs.Access.WRITABLE:
        print(f"{volume.name} is already writable.")
        return True

    if volume.mounted:
        print("Unmounting...")
        ok = ezntfs.macos_unmount(volume)
        if not ok:
            return False

    print(f"Mounting via ntfs-3g...")
    ok = ezntfs.mount(volume)
    if ok:
        print(f"Successfully mounted {volume.name}.")
        return True
    else:
        print(f"Failed to mount {volume.name}.")

        if volume.mounted:
            print("Remounting via macOS...")
            ezntfs.macos_mount(volume)

        return False
