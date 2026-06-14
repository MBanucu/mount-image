"""Cross-platform disk image mounting — platform dispatch."""

import platform


_SYSTEM = platform.system()

if _SYSTEM == 'Darwin':
    from mount_image._mount_darwin import mount_image, umount_image, attach_image, detach_image
else:
    from mount_image._mount_linux import mount_image, umount_image, attach_image, detach_image
