#!/usr/bin/env python3

from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

import subprocess

import ezntfs

class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        NSLog("Launched.")

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

        volumes = [v for v in ezntfs.get_ntfs_volumes().values() if v.mounted or v.internal]
        print(volumes)

        if len(volumes) == 0:
            label = "No NTFS volumes found."
            menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "", "")
            menuItem.setEnabled_(False)

        for volume in volumes:
            label = f"{volume.id}: {volume.name} [{volume.size}]"
            menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "mountVolume:", "")
            menuItem.setRepresentedObject_(volume.id)
            if not volume.read_only:
                menuItem.setState_(NSControlStateValueOn)
                menuItem.setEnabled_(False)

        menu.addItem_(NSMenuItem.separatorItem())
        menuItem = menu.addItemWithTitle_action_keyEquivalent_("Quit", "terminate:", "")

        self.statusItem.setMenu_(menu)
        self.statusItem.setVisible_(len(volumes) > 0)

    def mountVolume_(self, menuItem):
        volume_id = menuItem.representedObject()

        self.performSelectorInBackground_withObject_(self.runMountCommand_, volume_id)

    def runMountCommand_(self, volume_id):
        try:
            # assumes ezntfs has NOPASSWD set in sudoers
            subprocess.run(["sudo", "--non-interactive", "ezntfs", volume_id], check=True)
            print("ok")
        except:
            print("fail")

def main():
    workspace = NSWorkspace.sharedWorkspace()
    notification_center = workspace.notificationCenter()

    app = NSApplication.sharedApplication()
    delegate = AppDelegate.new()
    app.setDelegate_(delegate)

    app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    notification_center.addObserver_selector_name_object_(delegate, 'volumeDidChange:', NSWorkspaceDidMountNotification, None)
    notification_center.addObserver_selector_name_object_(delegate, 'volumeDidChange:', NSWorkspaceDidUnmountNotification, None)
    notification_center.addObserver_selector_name_object_(delegate, 'volumeDidChange:', NSWorkspaceDidRenameVolumeNotification, None)

    AppHelper.runEventLoop()

if __name__ == "__main__":
    main()
