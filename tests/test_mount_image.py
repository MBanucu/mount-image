"""Unit tests for mount_image — platform dispatch and mocked subprocess calls."""

import unittest
from unittest.mock import patch, MagicMock


class TestImports(unittest.TestCase):
    def test_import_mount_image(self):
        from mount_image import mount_image, umount_image, attach_image, detach_image
        self.assertTrue(callable(mount_image))
        self.assertTrue(callable(umount_image))
        self.assertTrue(callable(attach_image))
        self.assertTrue(callable(detach_image))


class TestLinuxMount(unittest.TestCase):
    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_mount_image_success(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='/dev/loop0\n'),
            MagicMock(returncode=0, stdout=''),
        ]
        from mount_image._mount_linux import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/loop0')
        self.assertEqual(mount_point, '/tmp/mount_image_abc')

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_mount_image_losetup_fails(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.return_value = MagicMock(returncode=1, stderr='Permission denied')
        from mount_image._mount_linux import mount_image
        with self.assertRaises(RuntimeError) as ctx:
            mount_image('/tmp/test.img')
        self.assertIn('losetup failed', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_mount_image_mount_fails(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='/dev/loop0\n'),
            MagicMock(returncode=1, stderr='mount failed'),
            MagicMock(returncode=0, stdout=''),
        ]
        from mount_image._mount_linux import mount_image
        with self.assertRaises(RuntimeError) as ctx:
            mount_image('/tmp/test.img')
        self.assertIn('mount failed', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    def test_umount_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image._mount_linux import umount_image
        umount_image('/dev/loop0', '/tmp/mount_point')

    @patch('mount_image._mount_linux.subprocess.run')
    def test_attach_image_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='/dev/loop0\n')
        from mount_image._mount_linux import attach_image
        device = attach_image('/tmp/test.img')
        self.assertEqual(device, '/dev/loop0')

    @patch('mount_image._mount_linux.subprocess.run')
    def test_attach_image_fails(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr='Permission denied')
        from mount_image._mount_linux import attach_image
        with self.assertRaises(RuntimeError):
            attach_image('/tmp/test.img')

    @patch('mount_image._mount_linux.subprocess.run')
    def test_detach_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image._mount_linux import detach_image
        detach_image('/dev/loop0')

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_mount_image_custom_fstype_and_options(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='/dev/loop0\n'),
            MagicMock(returncode=0, stdout=''),
        ]
        from mount_image._mount_linux import mount_image
        device, mount_point = mount_image(
            '/tmp/test.img', fstype='ext4', options=['ro', 'noexec'])
        self.assertEqual(device, '/dev/loop0')
        self.assertEqual(mount_point, '/tmp/mount_image_abc')


def _make_plist(entities: list[dict]) -> str:
    import plistlib
    return plistlib.dumps(
        {'system-entities': entities},
        fmt=plistlib.FMT_XML,
    ).decode()


class TestDarwinMount(unittest.TestCase):
    # ── mount_image ──────────────────────────────────────────────────

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_mount_image_auto_mount_succeeds(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_plist([
            {'dev-entry': '/dev/disk5', 'mount-point': '/Volumes/Test'},
        ]), stderr='')
        from mount_image._mount_darwin import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5')
        self.assertEqual(mount_point, '/Volumes/Test')

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_mount_image_attach_fails(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout='', stderr='hdiutil: attach failed')
        from mount_image._mount_darwin import mount_image
        with self.assertRaises(RuntimeError) as ctx:
            mount_image('/tmp/test.img')
        self.assertIn('hdiutil attach failed', str(ctx.exception))

    @patch('mount_image._mount_darwin.subprocess.run')
    @patch('mount_image._mount_darwin.tempfile.mkdtemp')
    def test_mount_image_mount_via_partition(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
            ]), stderr=''),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
                {'dev-entry': '/dev/disk5s1'},
            ]), stderr=''),
            MagicMock(returncode=0, stdout='', stderr=''),
        ]
        from mount_image._mount_darwin import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5s1')
        self.assertEqual(mount_point, '/tmp/mount_image_abc')

    @patch('mount_image._mount_darwin.subprocess.run')
    @patch('mount_image._mount_darwin.tempfile.mkdtemp')
    def test_mount_image_mount_via_whole_disk(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
            ]), stderr=''),               # auto-mount: no mount-point → detach
            MagicMock(returncode=0),       # detach
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
            ]), stderr=''),               # nomount: whole-disk, no partition loop
            MagicMock(returncode=0, stdout='', stderr=''),  # whole-disk mount succeeds
        ]
        from mount_image._mount_darwin import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5')
        self.assertEqual(mount_point, '/tmp/mount_image_abc')

    @patch('mount_image._mount_darwin.subprocess.run')
    @patch('mount_image._mount_darwin.tempfile.mkdtemp')
    def test_mount_image_all_mounts_fail(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
            ]), stderr=''),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
                {'dev-entry': '/dev/disk5s1'},
            ]), stderr=''),
            MagicMock(returncode=1),
            MagicMock(returncode=1),
            MagicMock(returncode=0),
        ]
        from mount_image._mount_darwin import mount_image
        with self.assertRaises(RuntimeError) as ctx:
            mount_image('/tmp/test.img')
        self.assertIn('mount failed', str(ctx.exception))

    @patch('mount_image._mount_darwin.subprocess.run')
    @patch('mount_image._mount_darwin.tempfile.mkdtemp')
    def test_mount_image_nomount_attach_fails(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
            ]), stderr=''),
            MagicMock(returncode=0),
            MagicMock(returncode=1, stdout='', stderr='nomount failed'),
        ]
        from mount_image._mount_darwin import mount_image
        with self.assertRaises(RuntimeError) as ctx:
            mount_image('/tmp/test.img')
        self.assertIn('nomount', str(ctx.exception))

    # ── umount_image ─────────────────────────────────────────────────

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_umount_image_with_mount_point(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image._mount_darwin import umount_image
        umount_image('/dev/disk5', '/tmp/mount_point')

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_umount_image_no_mount_point(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image._mount_darwin import umount_image
        umount_image('/dev/disk5')

    # ── attach_image ─────────────────────────────────────────────────

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_attach_image_whole_disk(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_plist([
            {'dev-entry': '/dev/disk5'},
            {'dev-entry': '/dev/disk5s1'},
        ]), stderr='')
        from mount_image._mount_darwin import attach_image
        device = attach_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5')

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_attach_image_only_slices_fallback(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_plist([
            {'dev-entry': '/dev/disk5s1'},
        ]), stderr='')
        from mount_image._mount_darwin import attach_image
        device = attach_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5s1')

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_attach_image_no_entities(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_plist([]),
                                           stderr='')
        from mount_image._mount_darwin import attach_image
        with self.assertRaises(RuntimeError) as ctx:
            attach_image('/tmp/test.img')
        self.assertIn('no devices', str(ctx.exception))

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_attach_image_attach_fails(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout='', stderr='hdiutil: attach failed')
        from mount_image._mount_darwin import attach_image
        with self.assertRaises(RuntimeError) as ctx:
            attach_image('/tmp/test.img')
        self.assertIn('hdiutil attach', str(ctx.exception))

    # ── detach_image ─────────────────────────────────────────────────

    @patch('mount_image._mount_darwin.subprocess.run')
    def test_detach_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image._mount_darwin import detach_image
        detach_image('/dev/disk5')


class TestPlatformDispatch(unittest.TestCase):
    def test_linux_import(self):
        import platform
        with patch.object(platform, 'system', return_value='Linux'):
            import importlib
            import mount_image._mount
            importlib.reload(mount_image._mount)
            from mount_image._mount import mount_image
            # The linux function should have the string 'losetup' in source
            self.assertTrue(callable(mount_image))

    def test_darwin_import(self):
        import platform
        with patch.object(platform, 'system', return_value='Darwin'):
            import importlib
            import mount_image._mount
            importlib.reload(mount_image._mount)
            from mount_image._mount import mount_image
            self.assertTrue(callable(mount_image))


if __name__ == '__main__':
    unittest.main()
