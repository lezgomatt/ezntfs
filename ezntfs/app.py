from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

from collections import deque
import contextlib
from enum import Enum
import os
from pathlib import Path
import shutil
import subprocess
import sys

from . import ezntfs
from . import __version__


DEFAULT_ICON = NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill", "ezNTFS")
BUSY_ICON = NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill.badge.minus", "ezNTFS (busy)")
ERROR_ICON = NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill.badge.xmark", "ezNTFS (error)")

AppState = Enum("AppState", ["READY", "FAILED", "RELOADING", "MOUNTING"])

ALWAYS_SHOW_FLAG = os.getenv('EZNTFS_ALWAYS_SHOW') == "yes"

status_icons = {
    AppState.READY: DEFAULT_ICON,
    AppState.FAILED: ERROR_ICON,
    AppState.RELOADING: BUSY_ICON,
    AppState.MOUNTING: BUSY_ICON,
}

class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        self.initializeAppState()
        self.initializeAppUi()

        self.env = self.detectEnvironment()

        if not self.state is AppState.FAILED:
            self.observeMountChanges()
            self.goNext()

    def runOnMainThread_with_(self, method, payload):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            method, payload, False
        )

    def initializeAppState(self):
        self.state = AppState.READY
        self.failure = None
        self.needs_reload = True
        self.volumes = []
        self.mount_queue = deque()
        self.mounting = None
        self.last_mount_failed = None

    def initializeAppUi(self):
        status_bar = NSStatusBar.systemStatusBar()
        status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
        status_item.setVisible_(False)

        button = status_item.button()
        button.setTitle_("ezNTFS")
        button.setImage_(DEFAULT_ICON)
        button.setToolTip_(f"ezNTFS {__version__}")

        menu = NSMenu.new()
        menu.setAutoenablesItems_(False)
        status_item.setMenu_(menu)

        self.status_item = status_item

    def detectEnvironment(self):
        try:
            env = ezntfs.get_environment_info()

            if env.fuse is None:
                self.handleFail_("Failed to detect macFUSE")
            elif env.ntfs_3g is None:
                self.handleFail_("Failed to detect ntfs-3g")
            elif not env.can_mount:
                self.handleFail_("Missing privileges to mount via ntfs-3g")

            return env
        except:
            self.handleFail_("Failed to detect the environment")

    def observeMountChanges(self):
        workspace = NSWorkspace.sharedWorkspace()
        notification_center = workspace.notificationCenter()

        notification_center.addObserver_selector_name_object_(self, "handleVolumeDidMount:", NSWorkspaceDidMountNotification, None)
        notification_center.addObserver_selector_name_object_(self, "handleVolumeDidUnmount:", NSWorkspaceDidUnmountNotification, None)
        notification_center.addObserver_selector_name_object_(self, "handleVolumeDidRename:", NSWorkspaceDidRenameVolumeNotification, None)

    def handleVolumeDidMount_(self, notification):
        if self.state is AppState.FAILED:
            return

        if self.state is AppState.READY:
            path = notification.userInfo()[NSWorkspaceVolumeURLKey].path()
            self.needs_reload = path
        else:
            self.needs_reload = True

        self.goNext()

    def handleVolumeDidUnmount_(self, notification):
        if self.state is AppState.FAILED:
            return

        url = notification.userInfo()[NSWorkspaceVolumeURLKey]
        volume = self.findVolumeWithUrl_(url)

        if self.state is AppState.READY:
            if volume is not None:
                self.removeVolume_(volume)
        elif volume is not None and self.isMountingVolume_(volume):
            pass
        else:
            self.needs_reload = True

        self.goNext()

    def handleVolumeDidRename_(self, notification):
        if self.state is AppState.FAILED:
            return

        old_url = notification.userInfo()[NSWorkspaceVolumeOldURLKey]
        old_volume = self.findVolumeWithUrl_(old_url)

        if self.state is AppState.READY:
            if old_volume is not None:
                new_name = notificaiton.userInfo()[NSWorkspaceVolumeLocalizedNameKey]
                new_path = notificaiton.userInfo()[NSWorkspaceVolumeURLKey].path()
                new_volume = old_volume._replace(name=new_name, mount_path=new_path)
                self.addVolume_(new_volume)
        else:
            self.needs_reload = True

        self.goNext()

    def goNext(self):
        if self.state is not AppState.READY:
            pass
        elif self.needs_reload:
            if isinstance(self.needs_reload, str):
                self.goAddVolume_(self.needs_reload)
            else:
                self.goReloadVolumeList()

            self.needs_reload = False
        elif len(self.mount_queue) > 0:
            volume = self.mount_queue.popleft()
            self.goMountVolume_(volume)

        self.refreshUi()

    def findVolumeWithUrl_(self, url):
        path = url.path()

        return next((v for v in self.volumes if v.mount_path == path), None)

    def fail_(self, message):
        self.runOnMainThread_with_(self.handleFail_, message)

    def handleFail_(self, message):
        self.state = AppState.FAILED
        self.failure = message
        self.goNext()

    def goReloadVolumeList(self):
        self.state = AppState.RELOADING
        self.performSelectorInBackground_withObject_(self.doReloadVolumeList_, None)

    def doReloadVolumeList_(self, nothing):
        try:
            volumes = ezntfs.get_all_ntfs_volumes().values()
            self.runOnMainThread_with_(self.handleReloadVolumeList_, volumes)
        except:
            self.fail_("Failed to retrieve NTFS volumes")

    def handleReloadVolumeList_(self, volumes):
        if self.state == AppState.FAILED:
            return

        self.state = AppState.READY
        self.volumes = [v for v in volumes if v.mounted or v.internal or self.isMountingVolume_(v)]
        self.volumes.sort(key=lambda v: v.id)
        self.goNext()

    def goAddVolume_(self, volumeIdOrPath):
        self.state = AppState.RELOADING
        self.performSelectorInBackground_withObject_(self.doAddVolume_, volumeIdOrPath)

    def doAddVolume_(self, volumeIdOrPath):
        try:
            volume = ezntfs.get_ntfs_volume(volumeIdOrPath)
            self.runOnMainThread_with_(self.handleAddVolume_, volume)
        except:
            self.fail_("Failed to retrieve NTFS volumes")

    def handleAddVolume_(self, volume):
        if self.state is AppState.FAILED:
            return

        self.state = AppState.READY

        if volume is not None:
            self.addVolume_(volume)

        self.goNext()

    def addVolume_(self, volume):
        self.removeVolume_(volume)
        self.volumes.append(volume)
        self.volumes.sort(key=lambda v: v.id)

    def removeVolume_(self, volume):
        self.volumes = [v for v in self.volumes if v.id != volume.id]

    def refreshUi(self):
        self.status_item.button().setImage_(status_icons[self.state])

        menu = self.status_item.menu()
        menu.removeAllItems()

        if self.state is AppState.FAILED:
            self.addTextItem_withLabel_(menu, self.failure)
        else:
            if self.last_mount_failed is not None:
                self.addTextItem_withLabel_(menu, f"Failed to mount: {self.last_mount_failed.name}")
                menu.addItem_(NSMenuItem.separatorItem())

            self.addVolumeItems_(menu)

        menu.addItem_(NSMenuItem.separatorItem())
        menu.addItemWithTitle_action_keyEquivalent_("Quit", "terminate:", "")

        self.status_item.setVisible_(self.state is AppState.FAILED or ALWAYS_SHOW_FLAG or len(self.volumes) > 0)

    def addTextItem_withLabel_(self, menu, label):
        item = menu.addItemWithTitle_action_keyEquivalent_(label, "", "")
        item.setEnabled_(False)

    def addVolumeItems_(self, menu):
        if len(self.volumes) == 0:
            self.addTextItem_withLabel_(menu, "No NTFS volumes found")

        for volume in self.volumes:
            label = f"{volume.name} [{volume.size}]"
            item = menu.addItemWithTitle_action_keyEquivalent_(label, "handleVolumeClicked:", "")
            item.setRepresentedObject_(volume)
            if self.isMountingVolume_(volume) or self.willMountVolume_(volume):
                item.setEnabled_(False)
                item.setToolTip_("Mounting...")
            elif volume.access is ezntfs.Access.WRITABLE:
                item.setState_(NSControlStateValueOn)
                item.setEnabled_(False)
                item.setToolTip_("Volume is writable")
            else:
                item.setToolTip_("Click to mount with ntfs-3g")

    def isMountingVolume_(self, volume):
        return self.mounting is not None and self.mounting.id == volume.id

    def willMountVolume_(self, volume):
        return volume.id in (v.id for v in self.mount_queue)

    def handleVolumeClicked_(self, menu_item):
        volume = menu_item.representedObject()
        self.mount_queue.append(volume)
        self.goNext()

    def goMountVolume_(self, volume):
        self.state = AppState.MOUNTING
        self.mounting = volume
        self.performSelectorInBackground_withObject_(self.doMountVolume_, volume)

    def doMountVolume_(self, volume):
        try:
            if volume.access is ezntfs.Access.WRITABLE:
                return self.runOnMainThread_with_(self.handleMountVolumeOk_, volume)

            if volume.mounted:
                ok = ezntfs.macos_unmount(volume)
                if not ok:
                    return self.runOnMainThread_with_(self.handleMountVolumeFail_, volume)

            ok = ezntfs.mount(volume, version=self.env.ntfs_3g, path=volume.mount_path)
            if not ok:
                if volume.mounted:
                    ezntfs.macos_mount(volume)
                return self.runOnMainThread_with_(self.handleMountVolumeFail_, volume)

            self.runOnMainThread_with_(self.handleMountVolumeOk_, volume)
        except:
            self.runOnMainThread_with_(self.handleMountVolumeFail_, volume)

    def handleMountVolumeOk_(self, volume):
        if self.state is AppState.FAILED:
            return

        self.state = AppState.READY
        self.addVolume_(volume._replace(access=ezntfs.Access.WRITABLE))
        self.mounting = None
        self.last_mount_failed = None
        self.goNext()

    def handleMountVolumeFail_(self, volume):
        if self.state is AppState.FAILED:
            return

        self.state = AppState.READY
        self.needs_reload = True
        self.mounting = None
        self.last_mount_failed = volume
        self.goNext()


def main():
    if len(sys.argv) <= 1:
        return launch_app()

    command = sys.argv[1]

    if command == "install":
        return install()
    elif command == "uninstall":
        return uninstall()

    print(f"Unknown command: {command}")
    sys.exit(1)

def launch_app():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.new()
    app.setDelegate_(delegate)
    app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    AppHelper.runEventLoop()

APP_NAME = "com.lezgomatt.ezntfs"
LAUNCHD_CONFIG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
    <dict>
        <key>Label</key>
        <string>{app_name}</string>
        <key>EnvironmentVariables</key>
        <dict>
            <key>NTFS_3G_PATH</key>
            <string>{ntfs_3g_path}</string>
        </dict>
        <key>Program</key>
        <string>{app_path}</string>
        <key>RunAtLoad</key>
        <true/>
    </dict>
</plist>"""

def install():
    user = os.getenv("SUDO_USER")
    user_id = os.getenv("SUDO_UID")
    group_id = os.getenv("SUDO_GID")

    if os.geteuid() != 0 or user is None or user_id is None or group_id is None:
        print("Need root to configure sudoers, try again with sudo")
        return

    env = ezntfs.get_environment_info()

    if env.fuse is None:
        print("Failed to detect macFUSE")
        return

    if env.ntfs_3g is None:
        print("Failed to detect ntfs-3g")
        return

    app_path = shutil.which("ezntfs-app")
    if app_path is None:
        print("Could not find ezntfs-app in the path")
        return

    sudoers_config_path = f"/private/etc/sudoers.d/{APP_NAME.replace('.', '-')}"
    with open(sudoers_config_path, "w") as sudoers_config_file:
        sudoers_config_file.write(f"%staff\t\tALL = NOPASSWD: {ezntfs.NTFS_3G_PATH}")

    launchd_config_path = f"{Path.home()}/Library/LaunchAgents/{APP_NAME}.plist"
    with open(launchd_config_path, "w") as launchd_config_file:
        launchd_config_file.write(LAUNCHD_CONFIG_TEMPLATE.format(
            app_name=APP_NAME,
            ntfs_3g_path=ezntfs.NTFS_3G_PATH,
            app_path=app_path,
        ))

    os.chown(sudoers_config_path, 0, 0)
    os.chmod(sudoers_config_path, 0o640)
    os.chown(launchd_config_path, int(user_id), int(group_id))

    subprocess.run(["su", "-", user, "-c", f"launchctl unload -F {launchd_config_path}"], capture_output=True)
    subprocess.run(["su", "-", user, "-c", f"launchctl load -F {launchd_config_path}"], capture_output=True)

    print("Installation complete! Try plugging an NTFS drive in.")
    print("NOTE: You may need to grant python access to removable volumes.")

def uninstall():
    if os.geteuid() != 0:
        print("Need root to remove sudoers config, try again with sudo")
        return

    with contextlib.suppress(FileNotFoundError):
        os.remove(f"/private/etc/sudoers.d/{APP_NAME.replace('.', '-')}")

    with contextlib.suppress(FileNotFoundError):
        os.remove(f"{Path.home()}/Library/LaunchAgents/{APP_NAME}.plist")

    print("Uninstallation complete!")
