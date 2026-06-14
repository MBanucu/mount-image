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

Cross-platform disk image mounting via loop devices (Linux) or hdiutil (macOS).

## Features

- **`mount_image`** — attach a disk image as a loop device and mount it:
  Linux uses `losetup` + `mount`, macOS uses `hdiutil attach` + `mount`
- **`umount_image`** — unmount and detach a disk image
- **`attach_image`** — attach a disk image as a block device without mounting
  (for raw block I/O)
- **`detach_image`** — detach a raw block device

## Quick start

```python
from mount_image import mount_image, umount_image

# Mount a disk image
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
# Read/write raw blocks via /dev/loop0 or /dev/disk5
detach_image(dev)
```

> **Note:** All functions require `sudo` for losetup/mount (Linux) or
> hdiutil/mount (macOS).

## License

GPL-3.0-only
