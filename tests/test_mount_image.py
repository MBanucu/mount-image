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


class TestLinuxStrategyFunctions(unittest.TestCase):
    """Test internal strategy functions by mocking subprocess.run."""

    @classmethod
    def setUpClass(cls):
        import platform
        if platform.system() != 'Linux':
            raise unittest.SkipTest('Linux-only tests')

    # ── _sudo_mount ──────────────────────────────────────────────

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_sudo_mount_success(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mp'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='/dev/loop0\n'),
            MagicMock(returncode=0, stdout=''),
        ]
        from mount_image._mount_linux import _sudo_mount
        dev, mp = _sudo_mount('/tmp/test.img', 'vfat', None)
        self.assertEqual(dev, '/dev/loop0')
        self.assertEqual(mp, '/tmp/mp')

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_sudo_mount_losetup_fails(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mp'
        mock_run.return_value = MagicMock(returncode=1, stderr='Permission denied')
        from mount_image._mount_linux import _sudo_mount
        with self.assertRaises(RuntimeError) as ctx:
            _sudo_mount('/tmp/test.img', 'vfat', None)
        self.assertIn('losetup failed', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_sudo_mount_mount_fails_cleans_up(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mp'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='/dev/loop0\n'),
            MagicMock(returncode=1, stderr='mount failed'),
            MagicMock(returncode=0, stdout=''),
        ]
        from mount_image._mount_linux import _sudo_mount
        with self.assertRaises(RuntimeError) as ctx:
            _sudo_mount('/tmp/test.img', 'vfat', None)
        self.assertIn('mount failed', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_sudo_mount_custom_options(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mp'
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='/dev/loop0\n'),
            MagicMock(returncode=0, stdout=''),
        ]
        from mount_image._mount_linux import _sudo_mount
        _sudo_mount('/tmp/test.img', 'ext4', ['ro', 'noexec'])
        args = mock_run.call_args_list[1][0][0]
        self.assertIn('-o', args)
        self.assertIn('ro,noexec', args)

    # ── _sudo_attach / _sudo_detach ──────────────────────────────

    @patch('mount_image._mount_linux.subprocess.run')
    def test_sudo_attach_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='/dev/loop0\n')
        from mount_image._mount_linux import _sudo_attach
        dev = _sudo_attach('/tmp/test.img')
        self.assertEqual(dev, '/dev/loop0')

    @patch('mount_image._mount_linux.subprocess.run')
    def test_sudo_attach_fails(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr='error')
        from mount_image._mount_linux import _sudo_attach
        with self.assertRaises(RuntimeError):
            _sudo_attach('/tmp/test.img')

    @patch('mount_image._mount_linux.subprocess.run')
    def test_sudo_detach(self, mock_run):
        from mount_image._mount_linux import _sudo_detach
        _sudo_detach('/dev/loop0')
        mock_run.assert_called_once_with(
            ['sudo', 'losetup', '-d', '/dev/loop0'], capture_output=True)

    # ── _udisks_mount ────────────────────────────────────────────

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_mount_success(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0,
                      stdout='Mapped file /tmp/test.img as /dev/loop0.\n'),
            MagicMock(returncode=0,
                      stdout='Mounted /dev/loop0 at /media/user/NO NAME.\n'),
        ]
        from mount_image._mount_linux import _udisks_mount
        dev, mp = _udisks_mount('/tmp/test.img', 'vfat', None)
        self.assertEqual(dev, '/dev/loop0')
        self.assertEqual(mp, '/media/user/NO NAME')

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_mount_loop_setup_fails(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout='', stderr='error')
        from mount_image._mount_linux import _udisks_mount
        with self.assertRaises(RuntimeError) as ctx:
            _udisks_mount('/tmp/test.img', 'vfat', None)
        self.assertIn('loop-setup failed', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_mount_mount_fails_cleans_up(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0,
                      stdout='Mapped file /tmp/test.img as /dev/loop0.\n'),
            MagicMock(returncode=1, stdout='', stderr='mount error'),
            MagicMock(returncode=0),
        ]
        from mount_image._mount_linux import _udisks_mount
        with self.assertRaises(RuntimeError) as ctx:
            _udisks_mount('/tmp/test.img', 'vfat', None)
        self.assertIn('mount failed', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_mount_unparsable_device(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout='garbage\n', stderr='')
        from mount_image._mount_linux import _udisks_mount
        with self.assertRaises(RuntimeError) as ctx:
            _udisks_mount('/tmp/test.img', 'vfat', None)
        self.assertIn('could not parse device', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_mount_unparsable_mount_point(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0,
                      stdout='Mapped file /tmp/test.img as /dev/loop0.\n'),
            MagicMock(returncode=0, stdout='no mount here\n', stderr=''),
        ]
        from mount_image._mount_linux import _udisks_mount
        with self.assertRaises(RuntimeError) as ctx:
            _udisks_mount('/tmp/test.img', 'vfat', None)
        self.assertIn('could not parse mount point', str(ctx.exception))

    # ── _udisks_attach / _udisks_detach ──────────────────────────

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_attach_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Mapped file /tmp/test.img as /dev/loop0.\n')
        from mount_image._mount_linux import _udisks_attach
        dev = _udisks_attach('/tmp/test.img')
        self.assertEqual(dev, '/dev/loop0')

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_attach_fails(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr='error')
        from mount_image._mount_linux import _udisks_attach
        with self.assertRaises(RuntimeError):
            _udisks_attach('/tmp/test.img')

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_attach_unparsable(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='garbage\n')
        from mount_image._mount_linux import _udisks_attach
        with self.assertRaises(RuntimeError) as ctx:
            _udisks_attach('/tmp/test.img')
        self.assertIn('could not parse device', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_detach(self, mock_run):
        from mount_image._mount_linux import _udisks_detach
        _udisks_detach('/dev/loop0')
        mock_run.assert_called_once_with(
            ['udisksctl', 'loop-delete', '-b', '/dev/loop0',
             '--no-user-interaction'], capture_output=True)

    @patch('mount_image._mount_linux.subprocess.run')
    def test_udisks_umount_inner(self, mock_run):
        from mount_image._mount_linux import _udisks_umount_inner
        _udisks_umount_inner('/dev/loop0')
        mock_run.assert_called_once_with(
            ['udisksctl', 'unmount', '-b', '/dev/loop0',
             '--no-user-interaction'], capture_output=True)

    # ── parsing helpers ──────────────────────────────────────────

    def test_parse_udisks_dev(self):
        from mount_image._mount_linux import _parse_udisks_dev
        self.assertEqual(
            _parse_udisks_dev('Mapped file img.img as /dev/loop0.\n'),
            '/dev/loop0')

    def test_parse_udisks_dev_no_dev(self):
        from mount_image._mount_linux import _parse_udisks_dev
        self.assertIsNone(_parse_udisks_dev('garbage\n'))
        self.assertIsNone(_parse_udisks_dev(''))

    def test_parse_udisks_mount(self):
        from mount_image._mount_linux import _parse_udisks_mount
        self.assertEqual(
            _parse_udisks_mount(
                'Mounted /dev/loop0 at /media/user/NO NAME.\n'),
            '/media/user/NO NAME')

    def test_parse_udisks_mount_no_mount(self):
        from mount_image._mount_linux import _parse_udisks_mount
        self.assertIsNone(_parse_udisks_mount('garbage\n'))
        self.assertIsNone(_parse_udisks_mount(''))

    # ── _guestmount_mount ────────────────────────────────────────

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_guestmount_mount_success(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mp'
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        from mount_image._mount_linux import _guestmount_mount
        dev, mp = _guestmount_mount('/tmp/test.img', 'vfat', None)
        self.assertEqual(dev, '/tmp/mp')
        self.assertEqual(mp, '/tmp/mp')

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_guestmount_mount_fails(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mp'
        mock_run.return_value = MagicMock(returncode=1, stderr='fail')
        from mount_image._mount_linux import _guestmount_mount
        with self.assertRaises(RuntimeError) as ctx:
            _guestmount_mount('/tmp/test.img', 'vfat', None)
        self.assertIn('guestmount failed', str(ctx.exception))

    @patch('mount_image._mount_linux.subprocess.run')
    @patch('mount_image._mount_linux.tempfile.mkdtemp')
    def test_guestmount_mount_custom_options(self, mock_mkdtemp, mock_run):
        mock_mkdtemp.return_value = '/tmp/mp'
        mock_run.return_value = MagicMock(returncode=0)
        from mount_image._mount_linux import _guestmount_mount
        _guestmount_mount('/tmp/test.img', 'vfat', ['ro', 'noexec'])
        args = mock_run.call_args[0][0]
        self.assertIn('-o', args)
        self.assertIn('ro', args)

    # ── teardown with populated _teardown dict ───────────────────

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
