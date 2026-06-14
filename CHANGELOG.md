# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[unreleased]: https://github.com/MBanucu/mount-image/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/MBanucu/mount-image/releases/tag/v0.1.1
[0.1.0]: https://github.com/MBanucu/mount-image/releases/tag/v0.1.0
