# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-14

### Added

- Mount strategy chain: `mount_image()` now automatically tries sudo
  losetup, udisksctl, and guestmount in order, selecting the first
  available tool. `umount_image()` and `detach_image()` use the
  matching strategy automatically.

### Changed

- Add CI, Codecov, and PyPI download badges to README.

### Fixed

- udisksctl failures now raise `RuntimeError` instead of being
  silently ignored.
- Fallback teardown commands are now wrapped in try/except to prevent
  cascading errors during cleanup.

## [0.2.1] - 2026-06-14

### Changed

- Depend on `mount-resolve>=0.2.0` and use `device_backing_file()` in
  integration tests instead of custom helper.

## [0.2.0] - 2026-06-14

### Added

- Integration tests with real FAT image mount/unmount/attach/detach.
- Pre-built sparse `tests/fat.img.gz` fixture (1.3 KB) as fallback when
  `mkfs.fat` is unavailable on the test runner.

## [0.1.2] - 2026-06-14

### Changed

- Expanded test coverage for `_mount_darwin.py` (all fallback paths now tested).

## [0.1.1] - 2026-06-14

### Changed

- Use SPDX license string format in `pyproject.toml` (fixes setuptools deprecation warnings).
- Remove deprecated license classifier.

## [0.1.0] - 2026-06-14

### Added

- `mount_image(path)` — attach a disk image as a loop device and mount it.
- `umount_image(device, mount_point)` — unmount and detach a disk image.
- `attach_image(path)` — attach a disk image as a raw block device (no mount).
- `detach_image(device)` — detach a raw block device.
- Linux support via `losetup` + `mount`.
- macOS support via `hdiutil attach` + `mount`.
- Nix flake with dev shell and package overlay.

[unreleased]: https://github.com/MBanucu/mount-image/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/MBanucu/mount-image/releases/tag/v0.3.0
[0.2.1]: https://github.com/MBanucu/mount-image/releases/tag/v0.2.1
[0.2.0]: https://github.com/MBanucu/mount-image/releases/tag/v0.2.0
[0.1.2]: https://github.com/MBanucu/mount-image/releases/tag/v0.1.2
[0.1.1]: https://github.com/MBanucu/mount-image/releases/tag/v0.1.1
[0.1.0]: https://github.com/MBanucu/mount-image/releases/tag/v0.1.0
