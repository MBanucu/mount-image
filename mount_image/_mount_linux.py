"""Linux disk image mounting — strategy chain (sudo → udisksctl → guestmount)."""

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

_STRATEGY_NAMES = ['sudo', 'udisksctl', 'guestmount']
_teardown: dict[str, tuple[Callable, Callable, str | None]] = {}


def _get_strategy_fns():
    return [
        (_STRATEGY_NAMES[0], _sudo_mount, _sudo_attach,
         _sudo_umount_inner, _sudo_detach),
        (_STRATEGY_NAMES[1], _udisks_mount, _udisks_attach,
         _udisks_umount_inner, _udisks_detach),
        (_STRATEGY_NAMES[2], _guestmount_mount, _guestmount_attach,
         _guestmount_umount_inner, _guestmount_detach),
    ]


def mount_image(image_path: str, fstype: str = 'exfat',
                options: list[str] | None = None) -> tuple[str, str]:
    """Attach *image_path* as a loop device and mount it.

    Tries strategies in order: sudo losetup → udisksctl → guestmount.
    Returns ``(device, mount_point)``.
    Raises ``RuntimeError`` if all strategies fail.
    """
    errors = []
    for label, mount_fn, _attach_fn, umount_fn, detach_fn in _get_strategy_fns():
        try:
            device, mp = mount_fn(image_path, fstype, options)
            _teardown[device] = (umount_fn, detach_fn, mp)
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

    if umount_fn:
        try:
            umount_fn(device)
        except Exception:
            pass
    elif mp:
        try:
            subprocess.run(['sudo', 'umount', mp], capture_output=True)
        except Exception:
            pass
        try:
            subprocess.run(['fusermount', '-u', mp],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    if mp:
        time.sleep(0.3)
        try:
            shutil.rmtree(mp, ignore_errors=True)
        except Exception:
            pass

    if detach_fn:
        try:
            detach_fn(device)
        except Exception:
            pass
    elif device:
        for cmd in (
            ['sudo', 'losetup', '-d', device],
            ['udisksctl', 'loop-delete', '-b', device, '--no-user-interaction'],
        ):
            subprocess.run(cmd, stderr=subprocess.DEVNULL)


def attach_image(image_path: str) -> str:
    """Attach *image_path* as a block device without mounting.

    Tries strategies in order: sudo losetup → udisksctl.
    Returns the device path (e.g. ``/dev/loop0``).
    Raises ``RuntimeError`` if all strategies fail.
    """
    errors = []
    for label, _mount_fn, attach_fn, _umount_fn, detach_fn in _get_strategy_fns():
        if label == 'guestmount':
            continue
        try:
            device = attach_fn(image_path)
            _teardown[device] = (detach_fn, detach_fn, None)
            return device
        except (RuntimeError, FileNotFoundError) as e:
            errors.append(f'{label}: {e}')
    raise RuntimeError(
        f'All attach strategies failed for {image_path}:\n' +
        '\n'.join(f'  {e}' for e in errors))


def detach_image(device: str):
    """Detach a block device using the matching strategy."""
    _dummy, detach_fn, _mp = _teardown.pop(device, (None, None, None))
    if detach_fn:
        try:
            detach_fn(device)
        except Exception:
            pass
    else:
        for cmd in (
            ['sudo', 'losetup', '-d', device],
            ['udisksctl', 'loop-delete', '-b', device, '--no-user-interaction'],
        ):
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            except Exception:
                pass
