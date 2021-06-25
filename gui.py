#!/usr/bin/env python3

from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        NSLog("Launched.")

        self.statusItem = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self.statusItem.button().setTitle_("ezNTFS")

        menu = NSMenu.new()
        menu.setAutoenablesItems_(False)

        menuItem = (
            NSMenuItem
                .alloc()
                .initWithTitle_action_keyEquivalent_("Writable Drive", "mount:", "")
        )
        menuItem.setState_(NSControlStateValueOn)
        menuItem.setEnabled_(False)
        menu.addItem_(menuItem)

        menuItem = (
            NSMenuItem
                .alloc()
                .initWithTitle_action_keyEquivalent_("Read-only Drive", "mount:", "")
        )
        menuItem.setState_(NSControlStateValueOff)
        menuItem.setEnabled_(True)
        menu.addItem_(menuItem)

        menu.addItem_(NSMenuItem.separatorItem())

        menuItem = (
            NSMenuItem
                .alloc()
                .initWithTitle_action_keyEquivalent_("Quit", "terminate:", "")
        )
        menu.addItem_(menuItem)

        self.statusItem.setMenu_(menu)

    def mount_(self, menuItem):
        NSLog("Mount.")
        print(menuItem)

    def onMount_(self, notif):
        NSLog("OnMount.")
        print(notif.userInfo())

    def onUnmount_(self, notif):
        NSLog("OnUnmount.")
        print(notif.userInfo())

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
