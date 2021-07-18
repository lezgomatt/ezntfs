from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

from tempfile import NamedTemporaryFile
import subprocess

from . import ezntfs


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        self.failure = None

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
            if volume.access is ezntfs.Access.WRITABLE:
                menuItem.setState_(NSControlStateValueOn)
                menuItem.setEnabled_(False)

        if self.failure is not None:
            menu.addItem_(NSMenuItem.separatorItem())
            menuItem = menu.addItemWithTitle_action_keyEquivalent_(f"Failed to mount: {self.failure[0]}", "", "")
            menuItem.setEnabled_(False)
            menu.addItemWithTitle_action_keyEquivalent_("View logs", "viewFailureLogs:", "")

        menu.addItem_(NSMenuItem.separatorItem())
        menu.addItemWithTitle_action_keyEquivalent_("Quit", "terminate:", "")

        self.statusItem.setMenu_(menu)
        self.statusItem.setVisible_(len(volumes) > 0)

    def mountVolume_(self, menuItem):
        volume_id = menuItem.representedObject()

        self.performSelectorInBackground_withObject_(self.runMountCommand_, volume_id)

    def runMountCommand_(self, volume_id):
        # assumes ezntfs has NOPASSWD set in sudoers
        result = subprocess.run(["sudo", "--non-interactive", "ezntfs", volume_id], capture_output=True)
        try:
            result.check_returncode()
            self.failure = None
        except:
            logs = result.stdout.decode() + result.stderr.decode()
            self.failure = (volume_id, logs)
        finally:
            self.build_menu()

    def viewFailureLogs_(self, menuItem):
        with NamedTemporaryFile(mode="w", prefix="ezntfs-", suffix=".log.txt", delete=False) as temp_log_file:
            temp_log_file.write(self.failure[1])
            temp_log_file.flush()
            subprocess.call(["open", temp_log_file.name])

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
