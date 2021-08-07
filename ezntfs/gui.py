from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

from tempfile import NamedTemporaryFile
import subprocess

from . import ezntfs


default_icon = NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill", "ezNTFS")
busy_icon = NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill.badge.minus", "ezNTFS (busy)")

class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        self.mounting = None

        self.env = ezntfs.get_environment_info()

        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self.status_item.setMenu_(NSMenu.new())

        self.status_item.button().setTitle_("ezNTFS")
        self.status_item.button().setImage_(default_icon)
        self.status_item.button().setToolTip_("ezNTFS")

        self.build_menu()

        self.observe_mount_changes()

    def observe_mount_changes(self):
        workspace = NSWorkspace.sharedWorkspace()
        notification_center = workspace.notificationCenter()

        notification_center.addObserver_selector_name_object_(self, "volumeDidChange:", NSWorkspaceDidMountNotification, None)
        notification_center.addObserver_selector_name_object_(self, "volumeDidChange:", NSWorkspaceDidUnmountNotification, None)
        notification_center.addObserver_selector_name_object_(self, "volumeDidChange:", NSWorkspaceDidRenameVolumeNotification, None)

    def volumeDidChange_(self, notification):
        if notification.name() == NSWorkspaceDidMountNotification:
            NSLog("Volume mounted.")
            path = notification.userInfo().valueForKey_("NSDevicePath")
            if self.mounting is not None and self.mounting.mount_path == path:
                self.mounting = None
                self.status_item.button().setImage_(default_icon)
        elif notification.name() == NSWorkspaceDidUnmountNotification:
            NSLog("Volume unmounted.")
        elif notification.name() == NSWorkspaceDidRenameVolumeNotification:
            NSLog("Volume renamed.")
        else:
            NSLog("Volume changed?")

        self.build_menu()

    def build_menu(self):
        menu = self.status_item.menu()
        menu.removeAllItems()
        menu.setAutoenablesItems_(False)

        if self.env.fuse is None:
            label = "Failed to detect macFUSE."
            menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "", "")
            menuItem.setEnabled_(False)
        elif self.env.ntfs_3g is None:
            label = "Failed to detect ntfs-3g."
            menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "", "")
            menuItem.setEnabled_(False)
        elif not self.env.can_mount:
            label = "Missing privileges to mount via ntfs-3g."
            menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "", "")
            menuItem.setEnabled_(False)
        else:
            volumes = [
                v for v in ezntfs.get_all_ntfs_volumes().values()
                if v.mounted or v.internal
                or self.mounting is not None and v.id == self.mounting.id
            ]
            print("Volumes:")
            print(volumes)

            if len(volumes) == 0:
                label = "No NTFS volumes found."
                menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "", "")
                menuItem.setEnabled_(False)

            for volume in volumes:
                label = f"{volume.name} [{volume.size}]"
                menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "mountVolume:", "")
                menuItem.setRepresentedObject_(volume)
                if self.mounting is not None and volume.id == self.mounting.id:
                    menuItem.setEnabled_(False)
                    menuItem.setToolTip_("Mounting...")
                elif volume.access is ezntfs.Access.WRITABLE:
                    menuItem.setState_(NSControlStateValueOn)
                    menuItem.setEnabled_(False)
                    menuItem.setToolTip_("Volume is writable")
                else:
                    menuItem.setToolTip_("Click to mount with ntfs-3g")

        menu.addItem_(NSMenuItem.separatorItem())
        menu.addItemWithTitle_action_keyEquivalent_("Quit", "terminate:", "")

        self.status_item.setVisible_(True)
        # self.status_item.setVisible_(len(volumes) > 0)

    def mountVolume_(self, menuItem):
        volume = menuItem.representedObject()
        self.mounting = volume

        self.status_item.button().setImage_(busy_icon)

        self.performSelectorInBackground_withObject_(self.runMountCommands_, volume)

    def runMountCommands_(self, volume):
        if volume.access is ezntfs.Access.WRITABLE:
            return

        if volume.mounted:
            ok = ezntfs.macos_unmount(volume)
            if not ok:
                return

        ok = ezntfs.mount(volume, version=self.env.ntfs_3g, path=volume.mount_path)
        if not ok:
            if volume.mounted:
                ezntfs.macos_mount(volume)


def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.new()
    app.setDelegate_(delegate)
    app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    AppHelper.runEventLoop()
