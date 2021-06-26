#!/usr/bin/env python3

from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

import ezntfs

class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        NSLog("Launched.")

        self.statusItem = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self.statusItem.button().setTitle_("ezNTFS")

        self.statusItem.setMenu_(self.build_menu())

    def build_menu(self):
        menu = NSMenu.new()
        menu.setAutoenablesItems_(False)

        volumes = ezntfs.get_ntfs_volumes().values()
        print(volumes)

        if len(volumes) == 0:
            label = "No NTFS volumes found."
            menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "", "")
            menuItem.setEnabled_(False)

        for volume in volumes:
            label = f"{volume.id}: {volume.name} [{volume.size}]"
            menuItem = menu.addItemWithTitle_action_keyEquivalent_(label, "mount:", "")
            if not volume.read_only:
                menuItem.setState_(NSControlStateValueOn)
                menuItem.setEnabled_(False)

        menu.addItem_(NSMenuItem.separatorItem())
        menuItem = menu.addItemWithTitle_action_keyEquivalent_("Quit", "terminate:", "")

        return menu

    def mount_(self, menuItem):
        NSLog("Mount.")
        print(menuItem)

    def onMount_(self, notif):
        NSLog("OnMount.")
        self.statusItem.setMenu_(self.build_menu())

    def onUnmount_(self, notif):
        NSLog("OnUnmount.")
        self.statusItem.setMenu_(self.build_menu())

def main():
    workspace = NSWorkspace.sharedWorkspace()
    notification_center = workspace.notificationCenter()

    app = NSApplication.sharedApplication()
    delegate = AppDelegate.new()
    app.setDelegate_(delegate)

    app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

    notification_center.addObserver_selector_name_object_(delegate, 'onMount:', NSWorkspaceDidMountNotification, None)
    notification_center.addObserver_selector_name_object_(delegate, 'onUnmount:', NSWorkspaceDidUnmountNotification, None)

    AppHelper.runEventLoop()

if __name__ == "__main__":
    main()
