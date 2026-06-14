"""Linux disk image mounting — strategy chain (sudo losetup → udisksctl → guestmount).

Each strategy is a module-level function pair (mount + umount, attach + detach).
The first strategy that succeeds for a given operation is recorded so teardown
calls the matching strategy.
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Callable


_LO_REGEX = re.compile(r'\(([^)]+)\)')

# Maps device → (umount_fn, detach_fn, mount_point) so teardown knows
# which strategy to call.
_teardown: dict[str, tuple[Callable, Callable, str | None]] = {}


# ── Sudo losetup + mount ────────────────────────────────────────────

def _sudo_mount(image_path: str, fstype: str, options: list[str] | None
                ) -> tuple[str, str]:
    r = subprocess.run(
        ['sudo', 'losetup', '-f', '--show', str(image_path)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"losetup failed: {r.stderr}")
    loop_dev = r.stdout.strip()

    mount_point = tempfile.mkdtemp(prefix='mount_image_')
    if options is not None:
        mount_opts = ','.join(options)
    else:
        mount_opts = f'uid={os.getuid()},gid={os.getgid()}'

    r = subprocess.run([
        'sudo', 'mount', '-t', fstype,
        '-o', mount_opts,
        loop_dev, mount_point,
    ], capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(['sudo', 'losetup', '-d', loop_dev], capture_output=True)
        shutil.rmtree(mount_point, ignore_errors=True)
        raise RuntimeError(f"mount failed: {r.stderr}")

    _teardown[loop_dev] = (_sudo_umount_inner, _sudo_detach, mount_point)
    return loop_dev, mount_point


def _sudo_umount_inner(device: str):
    r = subprocess.run(['sudo', 'losetup', device],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return
    m = _LO_REGEX.search(r.stdout)
    if m:
        subprocess.run(['sudo', 'umount', device], capture_output=True)
        time.sleep(0.3)


def _sudo_detach(device: str):
    subprocess.run(['sudo', 'losetup', '-d', device], capture_output=True)


def _sudo_attach(image_path: str) -> str:
    r = subprocess.run(
        ['sudo', 'losetup', '-f', '--show', str(image_path)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"losetup failed: {r.stderr}")
    loop_dev = r.stdout.strip()
    _teardown[loop_dev] = (_sudo_detach, _sudo_detach, None)
    return loop_dev


# ── udisksctl (polkit, no password) ─────────────────────────────────

def _udisks_mount(image_path: str, fstype: str, options: list[str] | None
                  ) -> tuple[str, str]:
    r = subprocess.run(
        ['udisksctl', 'loop-setup', '-f', str(image_path), '--no-user-interaction'],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"udisksctl loop-setup failed: {r.stderr}")

    loop_dev = _parse_udisks_dev(r.stdout)
    if not loop_dev:
        raise RuntimeError(
            f"udisksctl loop-setup: could not parse device from: {r.stdout}")

    r = subprocess.run(
        ['udisksctl', 'mount', '-b', loop_dev, '--no-user-interaction'],
        capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(
            ['udisksctl', 'loop-delete', '-b', loop_dev, '--no-user-interaction'],
            capture_output=True)
        raise RuntimeError(f"udisksctl mount failed: {r.stderr}")

    mount_point = _parse_udisks_mount(r.stdout)
    if not mount_point:
        raise RuntimeError(
            f"udisksctl mount: could not parse mount point from: {r.stdout}")

    _teardown[loop_dev] = (_udisks_umount_inner, _udisks_detach, mount_point)
    return loop_dev, mount_point


def _udisks_umount_inner(device: str):
    subprocess.run(
        ['udisksctl', 'unmount', '-b', device, '--no-user-interaction'],
        capture_output=True)


def _udisks_detach(device: str):
    subprocess.run(
        ['udisksctl', 'loop-delete', '-b', device, '--no-user-interaction'],
        capture_output=True)


def _udisks_attach(image_path: str) -> str:
    r = subprocess.run(
        ['udisksctl', 'loop-setup', '-f', str(image_path), '--no-user-interaction'],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"udisksctl loop-setup failed: {r.stderr}")
    loop_dev = _parse_udisks_dev(r.stdout)
    if not loop_dev:
        raise RuntimeError(
            f"udisksctl loop-setup: could not parse device from: {r.stdout}")
    _teardown[loop_dev] = (_udisks_detach, _udisks_detach, None)
    return loop_dev


def _parse_udisks_dev(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if ' as ' in line:
            parts = line.strip().split()
            if parts and parts[-1].rstrip('.').startswith('/dev/'):
                return parts[-1].rstrip('.')
    return None


def _parse_udisks_mount(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if 'Mounted' in line and 'at' in line:
            idx = line.find(' at ')
            if idx != -1:
                return line[idx + 4:].rstrip('.')
    return None


# ── guestmount (libguestfs) ─────────────────────────────────────────

def _guestmount_mount(image_path: str, fstype: str, options: list[str] | None
                      ) -> tuple[str, str]:
    mount_point = tempfile.mkdtemp(prefix='mount_image_')
    cmd = ['guestmount', '-a', str(image_path), '-m', '/dev/sda']
    if options:
        for opt in options:
            cmd.extend(['-o', opt])
    else:
        cmd.extend(['-o', f'uid={os.getuid()}', '-o', f'gid={os.getgid()}'])
    cmd.append(mount_point)

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(mount_point, ignore_errors=True)
        raise RuntimeError(f"guestmount failed: {r.stderr}")

    _teardown[mount_point] = (_guestmount_umount_inner, _guestmount_detach, None)
    return mount_point, mount_point


def _guestmount_umount_inner(device: str):
    subprocess.run(['fusermount', '-u', device], capture_output=True)


def _guestmount_detach(device: str):
    pass


# ── Strategy chain dispatch ─────────────────────────────────────────

_STRATEGY_NAMES = ['sudo', 'udisksctl', 'guestmount']


def _get_strategy_fns():
    """Return [(label, mount_fn, attach_fn), ...] using current globals
    so mocks can replace the functions at test time."""
    return [
        (_STRATEGY_NAMES[0], _sudo_mount, _sudo_attach),
        (_STRATEGY_NAMES[1], _udisks_mount, _udisks_attach),
        (_STRATEGY_NAMES[2], _guestmount_mount, _sudo_attach),
    ]


def mount_image(image_path: str, fstype: str = 'exfat',
                options: list[str] | None = None) -> tuple[str, str]:
    """Attach *image_path* as a loop device and mount it.

    Tries strategies in order: sudo losetup → udisksctl → guestmount.
    Returns ``(device, mount_point)``.
    Raises ``RuntimeError`` if all strategies fail.
    """
    errors = []
    for label, mount_fn, _attach_fn in _get_strategy_fns():
        try:
            return mount_fn(image_path, fstype, options)
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
    for label, _mount_fn, attach_fn in _get_strategy_fns():
        if label == 'guestmount':
            continue
        try:
            return attach_fn(image_path)
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
