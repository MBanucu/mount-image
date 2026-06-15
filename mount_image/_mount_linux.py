"""Linux disk image mounting — strategy chain (udisksctl → guestmount → sshfs → rclone → sudo).

Strategies are tried in order: no-sudo methods first, falling back to sudo
as a last resort.  Popular desktop distributions grant active local sessions
permission to create loop devices via udisksctl without a password.
"""

import os
import shutil
import subprocess
import time
from typing import Callable

from mount_image_sudo import (
    mount_image as _sudo_mount,
    attach_image as _sudo_attach,
    umount_inner as _sudo_umount_inner,
    detach_inner as _sudo_detach,
)
from mount_image_udisks import (
    mount_image as _udisks_mount,
    attach_image as _udisks_attach,
    umount_inner as _udisks_umount_inner,
    detach_inner as _udisks_detach,
)
from mount_image_guestmount import (
    mount_image as _guestmount_mount,
    umount_inner as _guestmount_umount_inner,
    detach_inner as _guestmount_detach,
)
from mount_image_sudo import attach_image as _guestmount_attach
from mount_image_sshfs import (
    mount_image as _sshfs_mount,
    umount_inner as _sshfs_umount_inner,
    detach_inner as _sshfs_detach,
)
from mount_image_rclone import (
    mount_image as _rclone_mount,
    umount_inner as _rclone_umount_inner,
    detach_inner as _rclone_detach,
)

# Strategy order: no-sudo methods first, sudo last
_STRATEGY_NAMES = ['udisksctl', 'guestmount', 'sshfs', 'rclone', 'sudo']
_FUSE_STRATEGIES = {'guestmount', 'sshfs', 'rclone'}
_NO_RMTREE_STRATEGIES = {'udisksctl'}
_teardown: dict[str, tuple[Callable, Callable, str | None]] = {}
# Track which mount points were created by us (temp dirs) and need cleanup
_managed_mount_points: set[str] = set()


def _get_strategy_fns():
    return [
        (_STRATEGY_NAMES[0], _udisks_mount, _udisks_attach,
         _udisks_umount_inner, _udisks_detach),
        (_STRATEGY_NAMES[1], _guestmount_mount, _guestmount_attach,
         _guestmount_umount_inner, _guestmount_detach),
        (_STRATEGY_NAMES[2], _sshfs_mount, None,
         _sshfs_umount_inner, _sshfs_detach),
        (_STRATEGY_NAMES[3], _rclone_mount, None,
         _rclone_umount_inner, _rclone_detach),
        (_STRATEGY_NAMES[4], _sudo_mount, _sudo_attach,
         _sudo_umount_inner, _sudo_detach),
    ]


def mount_image(image_path: str, fstype: str = 'exfat',
                options: list[str] | None = None) -> tuple[str, str]:
    """Attach *image_path* as a loop device and mount it.

    Tries strategies in order: udisksctl → guestmount → sshfs → rclone → sudo.
    Returns ``(device, mount_point)``.
    Raises ``RuntimeError`` if all strategies fail.
    """
    errors = []
    for label, mount_fn, _attach_fn, umount_fn, detach_fn in _get_strategy_fns():
        try:
            device, mp = mount_fn(image_path, fstype, options)
            _teardown[device] = (umount_fn, detach_fn, mp)
            if label not in _NO_RMTREE_STRATEGIES:
                _managed_mount_points.add(mp)
            return device, mp
        except (RuntimeError, FileNotFoundError) as e:
            errors.append(f'{label}: {e}')
    raise RuntimeError(
        f'All mount strategies failed for {image_path}:\n' +
        '\n'.join(f'  {e}' for e in errors))


def umount_image(device: str, mount_point: str | None = None):
    """Unmount and detach a disk image using the strategy that mounted it."""
    umount_fn, detach_fn, stored_mp = _teardown.pop(device, (None, None, None))
    mp = mount_point or stored_mp

    if umount_fn is not None:
        try:
            umount_fn(device)
        except Exception:
            pass
    elif mp:
        try:
            subprocess.run(['udisksctl', 'unmount', '-b', device,
                           '--no-user-interaction'], capture_output=True)
        except Exception:
            pass
        try:
            subprocess.run(['sudo', 'umount', mp], capture_output=True)
        except Exception:
            pass
        try:
            subprocess.run(['fusermount', '-u', mp],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    if mp and mp in _managed_mount_points:
        _managed_mount_points.discard(mp)
        time.sleep(0.3)
        try:
            shutil.rmtree(mp, ignore_errors=True)
        except Exception:
            pass

    if detach_fn is not None:
        try:
            detach_fn(device)
        except Exception:
            pass
    elif device:
        for cmd in (
            ['udisksctl', 'loop-delete', '-b', device, '--no-user-interaction'],
            ['sudo', 'losetup', '-d', device],
        ):
            subprocess.run(cmd, stderr=subprocess.DEVNULL)


def attach_image(image_path: str) -> str:
    """Attach *image_path* as a block device without mounting.

    Tries strategies in order: udisksctl → sudo.
    Returns the device path (e.g. ``/dev/loop0``).
    Raises ``RuntimeError`` if all strategies fail.
    """
    errors = []
    for label, _mount_fn, attach_fn, _umount_fn, detach_fn in _get_strategy_fns():
        if label in _FUSE_STRATEGIES or attach_fn is None:
            continue
        try:
            device = attach_fn(image_path)
            _teardown[device] = (None, detach_fn, None)
            return device
        except (RuntimeError, FileNotFoundError) as e:
            errors.append(f'{label}: {e}')
    raise RuntimeError(
        f'All attach strategies failed for {image_path}:\n' +
        '\n'.join(f'  {e}' for e in errors))


def detach_image(device: str):
    """Detach a block device using the matching strategy."""
    _dummy, detach_fn, _mp = _teardown.pop(device, (None, None, None))
    if detach_fn is not None:
        try:
            detach_fn(device)
        except Exception:
            pass
    else:
        for cmd in (
            ['udisksctl', 'loop-delete', '-b', device, '--no-user-interaction'],
            ['sudo', 'losetup', '-d', device],
        ):
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            except Exception:
                pass
