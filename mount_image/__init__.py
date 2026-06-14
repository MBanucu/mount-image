"""Cross-platform disk image mounting.

Creates loop devices (Linux losetup) or attaches disk images (macOS hdiutil)
and mounts them on the filesystem.
"""

from mount_image._mount import mount_image, umount_image, attach_image, detach_image

__all__ = [
    'mount_image',
    'umount_image',
    'attach_image',
    'detach_image',
]
