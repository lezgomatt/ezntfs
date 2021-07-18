from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

from tempfile import NamedTemporaryFile
import subprocess

from . import ezntfs


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        self.statusItem = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)

        self.statusItem.button().setTitle_("ezNTFS")
        self.statusItem.button().setImage_(NSImage.imageWithSystemSymbolName_accessibilityDescription_("externaldrive.fill", "ezNTFS"))

        self.build_menu()

    def volumeDidChange_(self, notification):
        NSLog("Volume changed.")
        self.build_menu()

    def build_menu(self):
        menu = NSMenu.new()
        menu.setAutoenablesItems_(False)

        volumes = [v for v in ezntfs.get_all_ntfs_volumes().values() if v.mounted or v.internal]
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
            if volume.access is ezntfs.Access.WRITABLE:
                menuItem.setState_(NSControlStateValueOn)
                menuItem.setEnabled_(False)

        menu.addItem_(NSMenuItem.separatorItem())
        menu.addItemWithTitle_action_keyEquivalent_("Quit", "terminate:", "")

        self.statusItem.setMenu_(menu)
        self.statusItem.setVisible_(len(volumes) > 0)

    def mountVolume_(self, menuItem):
        volume = menuItem.representedObject()

        self.performSelectorInBackground_withObject_(self.runMountCommands_, volume)

    def runMountCommands_(self, volume):
        if volume.access is ezntfs.Access.WRITABLE:
            return

        if volume.mounted:
            ok = ezntfs.macos_unmount(volume)
            if not ok:
                return

        ok = ezntfs.mount(volume, sudo=True)
        if not ok:
            if volume.mounted:
                ezntfs.macos_mount(volume)


def main():
    workspace = NSWorkspace.sharedWorkspace()
    notification_center = workspace.notificationCenter()

    app = NSApplication.sharedApplication()
    delegate = AppDelegate.new()
    app.setDelegate_(delegate)

    app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    notification_center.addObserver_selector_name_object_(delegate, "volumeDidChange:", NSWorkspaceDidMountNotification, None)
    notification_center.addObserver_selector_name_object_(delegate, "volumeDidChange:", NSWorkspaceDidUnmountNotification, None)
    notification_center.addObserver_selector_name_object_(delegate, "volumeDidChange:", NSWorkspaceDidRenameVolumeNotification, None)

    AppHelper.runEventLoop()
