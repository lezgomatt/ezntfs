from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

from collections import deque
from enum import Enum
import os
import subprocess

from . import ezntfs
from . import __version__


DEFAULT_ICON = NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill", "ezNTFS")
BUSY_ICON = NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill.badge.minus", "ezNTFS (busy)")
ERROR_ICON = NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill.badge.xmark", "ezNTFS (error)")

AppState = Enum("AppState", ["READY", "FAILED", "RELOADING", "MOUNTING"])

always_show_flag = os.environ.get('EZNTFS_ALWAYS_SHOW') == "yes"

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
                self.fail_("Failed to detect macFUSE")
            elif env.ntfs_3g is None:
                self.fail_("Failed to detect ntfs-3g")
            elif not env.can_mount:
                self.fail_("Missing privileges to mount via ntfs-3g")

            return env
        except:
            self.fail_("Failed to detect the environment")

    def observeMountChanges(self):
        workspace = NSWorkspace.sharedWorkspace()
        notification_center = workspace.notificationCenter()

        notification_center.addObserver_selector_name_object_(self, "handleVolumeDidMount:", NSWorkspaceDidMountNotification, None)
        notification_center.addObserver_selector_name_object_(self, "handleVolumeDidUnmount:", NSWorkspaceDidUnmountNotification, None)
        notification_center.addObserver_selector_name_object_(self, "handleVolumeDidRename:", NSWorkspaceDidRenameVolumeNotification, None)

    def handleVolumeDidMount_(self, notification):
        if self.state is AppState.READY:
            path = notification.userInfo()[NSWorkspaceVolumeURLKey].path()
            self.needs_reload = path
        else:
            self.needs_reload = True

        self.goNext()

    def handleVolumeDidUnmount_(self, notification):
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

        self.status_item.setVisible_(always_show_flag or len(self.volumes) > 0)

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
        self.state = AppState.READY
        self.addVolume_(volume._replace(access=ezntfs.Access.WRITABLE))
        self.mounting = None
        self.last_mount_failed = None
        self.goNext()

    def handleMountVolumeFail_(self, volume):
        self.state = AppState.READY
        self.needs_reload = True
        self.mounting = None
        self.last_mount_failed = volume
        self.goNext()


def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.new()
    app.setDelegate_(delegate)
    app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    AppHelper.runEventLoop()
