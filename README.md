# ezNTFS

ezNTFS is an easy-to-use wrapper for NTFS-3G on macOS.


## Installation

To use ezNTFS, you will need
[Python 3](https://www.python.org),
[FUSE for macOS (osxfuse)](https://osxfuse.github.io),
and [NTFS-3G](https://www.tuxera.com/community/open-source-ntfs-3g/)
installed in your system.

These can easily be installed using [Homebrew](https://brew.sh),
example: `brew install ntfs-3g`.

To install ezNTFS, run:
```
$ pip3 install ezntfs
```
It should be accessible from the terminal afterwards.


## Usage

Mount all NTFS volumes using `ntfs-3g` (root privileges are needed for mounting):
```
$ sudo ezntfs all
```

Mount a specific NTFS volume (run `ezntfs list` to find the disk id):
```
$ sudo ezntfs <disk id>
```
