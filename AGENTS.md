# mount-image — AGENTS.md

## Project

Cross-platform disk image mounting via loop devices (Linux) or hdiutil (macOS).

- **Package**: `mount-image` (PyPI), `mount_image` (import)
- **Repo**: `https://github.com/MBanucu/mount-image`
- **Python**: `>=3.10`
- **License**: GPL-3.0-only

## Commands

```bash
# Install (editable)
pip install -e .

# Run tests
python -m unittest discover -s tests -v

# Run tests with coverage
pip install coverage
python -m coverage run -m unittest discover -s tests -v
python -m coverage report --fail-under=70 --skip-covered

# Coverage per-file JSON dump
python -m coverage json -o cov.json
```

CI workflow: `.github/workflows/test.yml` — matrix on `ubuntu-latest` and `macos-latest` × Python 3.10–3.14.

## Module structure

```
mount_image/
  __init__.py         — public API re-exports
  _mount.py           — platform dispatch
  _mount_linux.py     — Linux losetup + mount
  _mount_darwin.py    — macOS hdiutil + mount
tests/
  test_mount_image.py — unit + mocked tests
```
