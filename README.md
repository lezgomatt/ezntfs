# ezNTFS

ezNTFS is an easy-to-use wrapper for NTFS-3G on macOS.

ezNTFS can be used as a menu bar app, or via the CLI in the terminal.


## Installation

To use ezNTFS, you will need [Python 3](https://www.python.org),
[FUSE for macOS (osxfuse)](https://osxfuse.github.io),
and [NTFS-3G](https://www.tuxera.com/community/open-source-ntfs-3g/)
installed in your system.

To install NTFS-3G, you may compile and install it yourself
(recommended, see instructions at the end),
or you may also [install it via brew](https://github.com/osxfuse/osxfuse/wiki/NTFS-3G#installation).

To install ezNTFS, run:
```
$ pip3 install ezntfs
```
It should be accessible from the terminal afterwards.

To configure the menu bar app, run the command after installing ezNTFS:
```
$ ezntfs-app install
```
This command adds `ntfs-3g` to a sudoers file,
and automatically launches the app on start-up.
The app will also be launched right after install.

**NOTE:** The app icon will only show up if there are NTFS volumes plugged in.
You may also need to grant Python access to removable volumes for this to work.


## Usage (CLI)

Mount all read-only NTFS volumes using `ntfs-3g` (root privileges are needed for mounting):
```
$ sudo ezntfs all
```

Mount a specific NTFS volume (run `ezntfs list` to find the disk id):
```
$ sudo ezntfs <disk id>
```


## Alternatives

### [Format as exFAT](https://support.apple.com/guide/disk-utility/format-a-disk-for-windows-computers-dskutl1010/mac)
- Natively supported by macOS
- exFAT is less reliable (no journaling), only use for flash drives

### [Auto-mount script](https://github.com/osxfuse/osxfuse/wiki/NTFS-3G#auto-mount-ntfs-volumes-in-read-write-mode)
- Setup requires disabling System Integrity Protection (SIP) or Sealed System Volume (SSV)
- Mounts with NTFS-3G even when not needed, which may slow down reads

### [Mounty](https://mounty.app)
- Volumes won't show up on Finder
- Writing via Apple's native NTFS driver is not officially supported

### [Tuxera NTFS driver](https://ntfsformac.tuxera.com)
- Not free
- Mature (same developers as NTFS-3G)
- Kernel driver, should be faster than FUSE

### [Paragon NTFS driver](https://www.paragon-software.com/home/ntfs-mac/)
- Not free, [except for Seagate external drives](https://www.seagate.com/as/en/support/software/paragon/)
- Mature
- Kernel driver, should be faster than FUSE


## Compiling and installing NTFS-3G

We recommend compiling and installing NTFS-3G yourself for the following reasons:
- You can use the newest version (`2017.3.23AR.6`), which includes important bug fixes for macOS
- It can be installed as root, which is important for security (since we're adding it to sudoers)

### Instructions
```
# Clone the git repo (you may want to clone a newer version if available)
git clone --depth 1 --branch 2017.3.23AR.6 https://github.com/tuxera/ntfs-3g.git
cd ntfs-3g

# Install the dependencies needed for compilation
brew install autoconf automake libgcrypt libtool pkg-config gettext

# Compile and install ntfs-3g
export LDFLAGS=-lintl
./autogen.sh
./configure \
    --disable-debug \
    --disable-dependency-tracking \
    --with-fuse=external \
    --prefix=/usr/local \
    --exec-prefix=/usr/local \
    --mandir=/usr/local/share/man \
    --sbindir=/usr/local/sbin
make
sudo make install

# Delete the cloned git repo
rm -r .
```
