"""macOS disk image mounting via hdiutil."""

import plistlib
import re
import shutil
import subprocess
import tempfile
import time


_PART_RE = re.compile(r'disk\d+s\d+')


def mount_image(image_path: str, fstype: str = 'exfat',
                options: list[str] | None = None) -> tuple[str, str]:
    """Attach *image_path* via hdiutil and mount it.

    Returns ``(device, mount_point)``.
    Raises ``RuntimeError`` on failure.
    """
    r = subprocess.run([
        'hdiutil', 'attach', '-plist', '-imagekey',
        'diskimage-class=CRawDiskImage', str(image_path),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"hdiutil attach failed: {r.stderr}")

    plist = plistlib.loads(r.stdout.encode())
    entities = plist.get('system-entities', [])

    for ent in entities:
        if ent.get('mount-point'):
            ent_dev = ent.get('dev-entry')
            if ent_dev:
                return ent_dev, ent['mount-point']

    for ent in entities:
        dev = ent.get('dev-entry')
        if dev:
            subprocess.run(['hdiutil', 'detach', dev],
                           capture_output=True, timeout=10)

    r = subprocess.run([
        'hdiutil', 'attach', '-nomount', '-plist', '-imagekey',
        'diskimage-class=CRawDiskImage', str(image_path),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"hdiutil attach (-nomount) failed: {r.stderr}")

    plist = plistlib.loads(r.stdout.encode())
    entities = plist.get('system-entities', [])

    mount_point = tempfile.mkdtemp(prefix='mount_image_')
    for ent in entities:
        dev = ent.get('dev-entry', '')
        if _PART_RE.search(dev):
            r = subprocess.run(
                ['sudo', 'mount', '-t', fstype, dev, mount_point],
                capture_output=True, text=True)
            if r.returncode == 0:
                return dev, mount_point

    for ent in entities:
        dev = ent.get('dev-entry', '')
        if dev and not _PART_RE.search(dev):
            r = subprocess.run(
                ['sudo', 'mount', '-t', fstype, dev, mount_point],
                capture_output=True, text=True)
            if r.returncode == 0:
                return dev, mount_point

    disk_dev = next(
        (ent.get('dev-entry', '') for ent in entities if ent.get('dev-entry')),
        None)
    if disk_dev:
        subprocess.run(['hdiutil', 'detach', disk_dev], capture_output=True)
    shutil.rmtree(mount_point, ignore_errors=True)
    raise RuntimeError(f"mount failed for {entities}")


def umount_image(device: str, mount_point: str | None = None):
    """Unmount and detach a disk image."""
    if mount_point:
        subprocess.run(['sudo', 'umount', mount_point], capture_output=True)
        time.sleep(0.3)
        try:
            shutil.rmtree(mount_point, ignore_errors=True)
        except Exception:
            pass
    subprocess.run(
        ['hdiutil', 'detach', device],
        capture_output=True, timeout=10)


def attach_image(image_path: str) -> str:
    """Attach *image_path* via hdiutil without mounting.

    Returns the device path (e.g. ``/dev/disk5``).
    Raises ``RuntimeError`` on failure.
    """
    r = subprocess.run([
        'hdiutil', 'attach', '-nomount', '-plist', '-imagekey',
        'diskimage-class=CRawDiskImage', str(image_path),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"hdiutil attach (-nomount) failed: {r.stderr}")
    plist = plistlib.loads(r.stdout.encode())
    entities = plist.get('system-entities', [])
    for ent in entities:
        dev = ent.get('dev-entry', '')
        if dev and not _PART_RE.search(dev):
            return dev
    if entities:
        return entities[0].get('dev-entry', '')
    raise RuntimeError("hdiutil attach returned no devices")


def detach_image(device: str):
    """Detach a disk image."""
    subprocess.run(['hdiutil', 'detach', device], capture_output=True, timeout=10)
