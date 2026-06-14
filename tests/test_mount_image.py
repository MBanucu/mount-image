"""Unit tests for mount_image — platform dispatch and orchestration."""

import unittest
from unittest.mock import patch, MagicMock


class TestImports(unittest.TestCase):
    def test_import_mount_image(self):
        from mount_image import mount_image, umount_image, attach_image, detach_image
        self.assertTrue(callable(mount_image))
        self.assertTrue(callable(umount_image))
        self.assertTrue(callable(attach_image))
        self.assertTrue(callable(detach_image))


class TestLinuxOrchestrator(unittest.TestCase):
    """Test the orchestrator's strategy chain (Linux)."""

    @classmethod
    def setUpClass(cls):
        import platform
        if platform.system() != 'Linux':
            raise unittest.SkipTest('Linux-only tests')

    @patch('mount_image._mount_linux._sudo_mount')
    def test_mount_image_success(self, mock_sudo_mount):
        mock_sudo_mount.return_value = ('/dev/loop0', '/tmp/mount_image_abc')
        from mount_image._mount_linux import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/loop0')
        self.assertEqual(mount_point, '/tmp/mount_image_abc')

    @patch('mount_image._mount_linux._sudo_mount')
    @patch('mount_image._mount_linux._udisks_mount')
    @patch('mount_image._mount_linux._guestmount_mount')
    def test_mount_image_all_strategies_fail(self, mock_guest, mock_udisks, mock_sudo):
        mock_sudo.side_effect = RuntimeError('losetup failed: Permission denied')
        mock_udisks.side_effect = RuntimeError('udisksctl loop-setup failed')
        mock_guest.side_effect = RuntimeError('guestmount failed')
        from mount_image._mount_linux import mount_image
        with self.assertRaises(RuntimeError) as ctx:
            mount_image('/tmp/test.img')
        self.assertIn('All mount strategies failed', str(ctx.exception))

    @patch('mount_image._mount_linux._sudo_mount')
    @patch('mount_image._mount_linux._udisks_mount')
    def test_mount_image_fallback_to_udisks(self, mock_udisks, mock_sudo):
        mock_sudo.side_effect = RuntimeError('losetup failed')
        mock_udisks.return_value = ('/dev/loop0', '/media/user/NO NAME')
        from mount_image._mount_linux import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/loop0')
        self.assertEqual(mount_point, '/media/user/NO NAME')

    @patch('mount_image._mount_linux._teardown', {})
    def test_umount_image_no_teardown_info(self):
        from mount_image._mount_linux import umount_image
        umount_image('/dev/loop0', '/tmp/mount_point')

    @patch('mount_image._mount_linux._sudo_attach')
    def test_attach_image_success(self, mock_attach):
        mock_attach.return_value = '/dev/loop0'
        from mount_image._mount_linux import attach_image
        device = attach_image('/tmp/test.img')
        self.assertEqual(device, '/dev/loop0')

    @patch('mount_image._mount_linux._sudo_attach')
    @patch('mount_image._mount_linux._udisks_attach')
    def test_attach_image_all_fail(self, mock_udisks, mock_sudo):
        mock_sudo.side_effect = RuntimeError('Permission denied')
        mock_udisks.side_effect = RuntimeError('udisksctl failed')
        from mount_image._mount_linux import attach_image
        with self.assertRaises(RuntimeError):
            attach_image('/tmp/test.img')

    @patch('mount_image._mount_linux._teardown', {})
    def test_detach_image_no_teardown_info(self):
        from mount_image._mount_linux import detach_image
        detach_image('/dev/loop0')

    @patch('mount_image._mount_linux._sudo_mount')
    def test_mount_image_custom_fstype_and_options(self, mock_sudo_mount):
        mock_sudo_mount.return_value = ('/dev/loop0', '/tmp/mount_image_abc')
        from mount_image._mount_linux import mount_image
        device, mount_point = mount_image(
            '/tmp/test.img', fstype='ext4', options=['ro', 'noexec'])
        mock_sudo_mount.assert_called_once_with(
            '/tmp/test.img', 'ext4', ['ro', 'noexec'])
        self.assertEqual(device, '/dev/loop0')
        self.assertEqual(mount_point, '/tmp/mount_image_abc')

    @patch('mount_image._mount_linux._teardown',
           {'/dev/loop0': (MagicMock(), MagicMock(), '/tmp/mp')})
    def test_umount_image_with_teardown(self):
        from mount_image._mount_linux import umount_image
        umount_image('/dev/loop0')

    @patch('mount_image._mount_linux._teardown',
           {'/dev/loop0': (MagicMock(), MagicMock(), None)})
    def test_detach_image_with_teardown(self):
        from mount_image._mount_linux import detach_image
        detach_image('/dev/loop0')


def _make_plist(entities):
    import plistlib
    return plistlib.dumps(
        {'system-entities': entities},
        fmt=plistlib.FMT_XML,
    ).decode()


class TestDarwinMount(unittest.TestCase):
    """Test hdiutil strategy (imported from mount_image_hdiutil)."""

    @patch('mount_image_hdiutil.subprocess.run')
    def test_mount_image_auto_mount_succeeds(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_plist([
            {'dev-entry': '/dev/disk5', 'mount-point': '/Volumes/Test'},
        ]), stderr='')
        from mount_image_hdiutil import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5')
        self.assertEqual(mount_point, '/Volumes/Test')

    @patch('mount_image_hdiutil.subprocess.run')
    def test_mount_image_attach_fails(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout='', stderr='hdiutil: attach failed')
        from mount_image_hdiutil import mount_image
        with self.assertRaises(RuntimeError) as ctx:
            mount_image('/tmp/test.img')
        self.assertIn('hdiutil attach failed', str(ctx.exception))

    @patch('mount_image_hdiutil.subprocess.run')
    @patch('mount_image_hdiutil.tempfile.mkdtemp')
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
        from mount_image_hdiutil import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5s1')
        self.assertEqual(mount_point, '/tmp/mount_image_abc')

    @patch('mount_image_hdiutil.subprocess.run')
    @patch('mount_image_hdiutil.tempfile.mkdtemp')
    def test_mount_image_via_whole_disk(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mount_image_abc'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
            ]), stderr=''),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=_make_plist([
                {'dev-entry': '/dev/disk5'},
            ]), stderr=''),
            MagicMock(returncode=0, stdout='', stderr=''),
        ]
        from mount_image_hdiutil import mount_image
        device, mount_point = mount_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5')
        self.assertEqual(mount_point, '/tmp/mount_image_abc')

    @patch('mount_image_hdiutil.subprocess.run')
    @patch('mount_image_hdiutil.tempfile.mkdtemp')
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
        from mount_image_hdiutil import mount_image
        with self.assertRaises(RuntimeError) as ctx:
            mount_image('/tmp/test.img')
        self.assertIn('mount failed', str(ctx.exception))

    @patch('mount_image_hdiutil.subprocess.run')
    def test_umount_image_with_mount_point(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image_hdiutil import umount_image
        umount_image('/dev/disk5', '/tmp/mount_point')

    @patch('mount_image_hdiutil.subprocess.run')
    def test_umount_image_no_mount_point(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image_hdiutil import umount_image
        umount_image('/dev/disk5')

    @patch('mount_image_hdiutil.subprocess.run')
    def test_attach_image_whole_disk(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_make_plist([
            {'dev-entry': '/dev/disk5'},
            {'dev-entry': '/dev/disk5s1'},
        ]), stderr='')
        from mount_image_hdiutil import attach_image
        device = attach_image('/tmp/test.img')
        self.assertEqual(device, '/dev/disk5')

    @patch('mount_image_hdiutil.subprocess.run')
    def test_detach_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image_hdiutil import detach_image
        detach_image('/dev/disk5')


class TestPlatformDispatch(unittest.TestCase):
    def test_linux_import(self):
        import platform
        with patch.object(platform, 'system', return_value='Linux'):
            import importlib
            import mount_image._mount
            importlib.reload(mount_image._mount)
            from mount_image._mount import mount_image
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
