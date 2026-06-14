"""Integration tests — actually mount and unmount a real disk image.

Requires sudo and mkfs.fat. Skips if unavailable.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def _sudo_available() -> bool:
    r = subprocess.run(['sudo', '-n', 'true'], capture_output=True)
    return r.returncode == 0


def _mkfs_available() -> bool:
    r = subprocess.run(['which', 'mkfs.fat'], capture_output=True)
    return r.returncode == 0


def _create_fat_image(path: str, size_mb: int = 1):
    subprocess.run(['truncate', '-s', f'{size_mb}M', path], check=True)
    subprocess.run(['mkfs.fat', path], check=True, capture_output=True)


class TestMountImageIntegration(unittest.TestCase):
    """Integration tests using a real FAT filesystem image."""

    _img: str

    @classmethod
    def setUpClass(cls):
        if not _sudo_available():
            raise unittest.SkipTest('sudo passwordless access required')
        if not _mkfs_available():
            raise unittest.SkipTest('mkfs.fat not available')

        fd, cls._img = tempfile.mkstemp(suffix='.img', prefix='mount_image_test_')
        os.close(fd)
        _create_fat_image(cls._img)

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._img)
        except OSError:
            pass

    def test_mount_and_umount(self):
        from mount_image import mount_image, umount_image

        device, mount_point = mount_image(self._img, fstype='vfat')
        try:
            self.assertTrue(os.path.ismount(mount_point))
            entries = os.listdir(mount_point)
            self.assertIsInstance(entries, list)
        finally:
            umount_image(device, mount_point)

        self.assertFalse(os.path.ismount(mount_point))

    def test_attach_and_detach_raw(self):
        from mount_image import attach_image, detach_image

        device = attach_image(self._img)
        try:
            self.assertTrue(os.path.exists(device))
            self.assertTrue(device.startswith('/dev/'))
            r = subprocess.run(['sudo', 'losetup', device],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertIn(self._img, r.stdout)
        finally:
            detach_image(device)

        r = subprocess.run(['sudo', 'losetup', device],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0,
                            f'loop device {device} should be detached')

    def test_mount_image_twice_different_mount_points(self):
        from mount_image import mount_image, umount_image

        dev1, mp1 = mount_image(self._img, fstype='vfat')
        try:
            self.assertTrue(os.path.ismount(mp1))
            dev2, mp2 = mount_image(self._img, fstype='vfat')
            try:
                self.assertTrue(os.path.ismount(mp2))
                self.assertNotEqual(mp1, mp2)
            finally:
                umount_image(dev2, mp2)
        finally:
            umount_image(dev1, mp1)


if __name__ == '__main__':
    unittest.main()
