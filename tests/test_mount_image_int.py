"""Integration tests — actually mount and unmount a real disk image.

Requires sudo. Uses mkfs.fat on-the-fly when available; falls back to
a pre-built sparse FAT image (tests/fat.img.gz) otherwise.
"""

import gzip
import os
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path


_FAT_IMG_SIZE_MB = 1
_SYSTEM = platform.system()


def _sudo_available() -> bool:
    r = subprocess.run(['sudo', '-n', 'true'], capture_output=True)
    return r.returncode == 0


def _mkfs_available() -> bool:
    r = subprocess.run(['which', 'mkfs.fat'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def _create_fat_image(path: str):
    subprocess.run(['truncate', '-s', f'{_FAT_IMG_SIZE_MB}M', path], check=True)
    subprocess.run(['mkfs.fat', path], check=True, capture_output=True)


def _decompress_image(gz_path: Path, dest_path: str):
    CHUNK = 1024 * 1024
    zero = b'\x00' * CHUNK
    full_size = _FAT_IMG_SIZE_MB * 1024 * 1024

    fd = os.open(dest_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
    os.ftruncate(fd, full_size)
    os.close(fd)

    offset = 0
    with gzip.open(gz_path, 'rb') as src, open(dest_path, 'rb+') as dst:
        while True:
            chunk = src.read(CHUNK)
            if not chunk:
                break
            if chunk != zero[:len(chunk)]:
                os.lseek(dst.fileno(), offset, os.SEEK_SET)
                dst.write(chunk)
            offset += len(chunk)


def _prepare_image() -> str:
    """Return path to a writable FAT image, creating it if needed."""
    if _mkfs_available():
        fd, path = tempfile.mkstemp(suffix='.img', prefix='mount_image_test_')
        os.close(fd)
        _create_fat_image(path)
        return path

    gz_path = Path(__file__).parent / 'fat.img.gz'
    if not gz_path.exists():
        raise unittest.SkipTest(
            'mkfs.fat not available and fat.img.gz fixture not found')

    fd, path = tempfile.mkstemp(suffix='.img', prefix='mount_image_test_')
    os.close(fd)
    _decompress_image(gz_path, path)
    return path


class TestMountImageIntegration(unittest.TestCase):
    """Integration tests using a real FAT filesystem image."""

    _img: str

    @classmethod
    def setUpClass(cls):
        if not _sudo_available():
            raise unittest.SkipTest('sudo passwordless access required')
        cls._img = _prepare_image()

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
        from mount_resolve import device_backing_file

        device = attach_image(self._img)
        try:
            self.assertTrue(os.path.exists(device))
            self.assertTrue(device.startswith('/dev/'))
            self.assertEqual(device_backing_file(device), self._img)
        finally:
            detach_image(device)

    def test_mount_image_twice_different_mount_points(self):
        if _SYSTEM == 'Darwin':
            raise unittest.SkipTest(
                'macOS cannot mount the same image twice')
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
