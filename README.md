# mount-image

[![PyPI version](https://img.shields.io/pypi/v/mount-image)](https://pypi.org/project/mount-image/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/)
[![License](https://img.shields.io/github/license/MBanucu/mount-image)](LICENSE)
[![OS](https://img.shields.io/badge/OS-Linux%20%7C%20macOS-blue)](https://github.com/MBanucu/mount-image)

[![CI](https://img.shields.io/github/actions/workflow/status/MBanucu/mount-image/test.yml?branch=main)](https://github.com/MBanucu/mount-image/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/MBanucu/mount-image/branch/main/graph/badge.svg)](https://codecov.io/gh/MBanucu/mount-image)

[![Downloads total](https://pepy.tech/badge/mount-image)](https://pepy.tech/project/mount-image)
[![Downloads/month](https://pepy.tech/badge/mount-image/month)](https://pepy.tech/project/mount-image)
[![Downloads/week](https://pepy.tech/badge/mount-image/week)](https://pepy.tech/project/mount-image)

Cross-platform disk image mounting — strategy selector that chains multiple
backends, preferring methods that **do not require sudo**.

## Strategy chain

`mount_image()` tries each strategy in order and uses the first one that
succeeds.  The default chain (Linux) is ordered from no-sudo to sudo:

| # | Strategy | Package | Sudo? | Description |
|---|----------|---------|-------|-------------|
| 1 | **udisksctl** | `mount-image-udisks` | **No** | Loop devices via UDisks2 (polkit). Works on most desktop distros. |
| 2 | **guestmount** | `mount-image-guestmount` | No | FUSE mount via libguestfs. |
| 3 | **sshfs** | `mount-image-sshfs` | No | FUSE mount of remote paths via SSH. |
| 4 | **rclone** | `mount-image-rclone` | No | FUSE mount of cloud/remote storage. |
| 5 | **sudo** | `mount-image-sudo` | Yes | `losetup` + `mount`. Last resort. |

On macOS, `hdiutil` (`mount-image-hdiutil`) is used.

## Quick start

```python
from mount_image import mount_image, umount_image

# Mount a disk image (tries udisksctl first — no sudo on most systems)
device, mount_point = mount_image('/path/to/disk.img')
print(f'Mounted {device} at {mount_point}')

# ... do work with the mounted filesystem ...

# Unmount and detach
umount_image(device, mount_point)
```

### Raw device access (no mount)

```python
from mount_image import attach_image, detach_image

dev = attach_image('/path/to/disk.img')
# Read/write raw blocks via /dev/loopN
detach_image(dev)
```

### Custom filesystem type and mount options

```python
device, mount_point = mount_image(
    '/path/to/disk.img',
    fstype='ext4',
    options=['ro', 'noexec'],
)
```

## Installation

Each strategy is a separate pip package. Install what you need:

```bash
pip install mount-image                  # orchestrator + all strategies
pip install mount-image-udisks           # only udisksctl strategy (no-sudo)
```

Or pick individual strategies:

```bash
pip install mount-image mount-image-udisks mount-image-guestmount
```

## License

GPL-3.0-only
