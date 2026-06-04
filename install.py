#!/usr/bin/env python3
"""
Nova + Galaxy — Unified Installer

Downloads the Nova compiler and Galaxy package manager, installing them
globally as 'nova' and 'galaxy' commands. No repo clone, no pip required.

Usage:
  python install.py                     Install Nova + Galaxy
  python install.py --uninstall         Remove everything
"""

import sys
import os
import shutil
import stat
import platform
import urllib.request
import urllib.error
import zipfile
import io
import time


APP_NAME = "Nova + Galaxy"
# Try release zip first (leaner), fall back to full repo zip
NOVA_RELEASE_BASE = "https://github.com/nova-programming/Nova/releases/download"
NOVA_ZIP_URL = "https://github.com/nova-programming/Nova/archive/refs/heads/develop.zip"
ZIP_PREFIX = "Nova-develop"

ALLOWED_ROOT_FILES = {"main.py", "_galaxy.py", "nova_main.nv"}
ALLOWED_SUBDIRS = {
    "compiler", "parser", "lexer", "stdlib",
    "nova_ast", "tools", "galaxy", "vm", "modules",
}

if platform.system() == "Windows":
    INSTALL_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "nova"
    )
    LAUNCHER_TEMPLATES = {
        "nova.bat": (
            '@echo off\r\n'
            'python "%~dp0main.py" %*\r\n'
        ),
        "galaxy.bat": (
            '@echo off\r\n'
            'python "%~dp0_galaxy.py" %*\r\n'
        ),
    }
else:
    INSTALL_DIR = os.path.join(os.path.expanduser("~"), ".nova")
    LAUNCHER_TEMPLATES = {
        "nova": (
            '#!/usr/bin/env python3\n'
            '"""Nova compiler launcher"""\n'
            'import sys, os\n'
            'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n'
            'os.chdir(os.path.dirname(os.path.abspath(__file__)))\n'
            'from main import main\n'
            'main()\n'
        ),
        "galaxy": (
            '#!/usr/bin/env python3\n'
            '"""Galaxy package manager launcher"""\n'
            'import sys, os\n'
            'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n'
            'from _galaxy import main\n'
            'main()\n'
        ),
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def info(msg):
    print(f"  [..]  {msg}")

def ok(msg):
    print(f"  [OK]   {msg}")

def warn(msg):
    print(f"  [WARN] {msg}")

def fail(msg):
    print(f"  [FAIL] {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Download with progress reporting
# ---------------------------------------------------------------------------

class _ProgressReader(io.RawIOBase):
    """Wraps a response and reports download progress periodically."""

    def __init__(self, wrapped, label="Downloading"):
        self._wrapped = wrapped
        self._label = label
        self._total = 0
        self._next_report = time.monotonic() + 0.5
        self._content_length = wrapped.length if hasattr(wrapped, "length") else None

    def readable(self):
        return True

    def read(self, n=-1):
        data = self._wrapped.read(n)
        if data:
            self._total += len(data)
            now = time.monotonic()
            if now >= self._next_report:
                mb = self._total / (1024 * 1024)
                if self._content_length:
                    total_mb = self._content_length / (1024 * 1024)
                    pct = self._total / self._content_length * 100
                    print(f"  [..]  {self._label}: {mb:.1f} / {total_mb:.1f} MB ({pct:.0f}%)")
                else:
                    print(f"  [..]  {self._label}: {mb:.1f} MB")
                self._next_report = now + 0.5
        return data

    def readinto(self, b):
        data = self.read(len(b))
        if data is None:
            return None
        n = len(data)
        b[:n] = data
        return n


def _download_zip():
    is_unix = platform.system() != "Windows"
    ext = ".tar.gz" if is_unix else ".zip"
    urls_to_try = [
        f"{NOVA_RELEASE_BASE}/nova-v0.6.0/nova-v0.6.0{ext}",
        NOVA_ZIP_URL,
    ]
    last_err = None
    for url in urls_to_try:
        info(f"Connecting to GitHub...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nova-installer/1.0"})
            rsp = urllib.request.urlopen(req, timeout=120)
            reader = _ProgressReader(rsp, "Downloading Nova")
            data = reader.read()
            mb = len(data) / (1024 * 1024)
            info(f"Downloaded {mb:.1f} MB — verifying...")
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404 and url != NOVA_ZIP_URL:
                info(f"Release{ext} not yet available, trying full repo zip...")
                continue
            fail(f"Download failed (HTTP {e.code}: {e.reason})")
        except urllib.error.URLError as e:
            last_err = e.reason
        except Exception as e:
            last_err = str(e)
    fail(f"Download failed: {last_err}")


# ---------------------------------------------------------------------------
# Extraction (preserves full project structure minus dev-only files)
# ---------------------------------------------------------------------------

def _should_extract(rel_path: str) -> bool:
    """Return True if the file belongs in a production install."""
    parts = rel_path.strip("/").split("/")
    top = parts[0]

    # Only allow specific subdirectories
    if top in ALLOWED_SUBDIRS:
        # Skip __pycache__ and non-Python/assembly files
        if "__pycache__" in parts:
            return False
        return True

    # At the root, only allow specific files
    if len(parts) == 1 and top in ALLOWED_ROOT_FILES:
        return True

    # Skip everything else
    return False


def _extract_archive(data: bytes) -> int:
    """Extract either a .zip or .tar.gz archive."""
    # Try zip first
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            if names:
                return _extract_zip(data)
    except zipfile.BadZipFile:
        pass
    # Fallback to tar
    import tarfile
    return _extract_tar(data)


def _extract_tar(data: bytes) -> int:
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        names = tf.getmembers()
        first = names[0].name if names else ""
        has_prefix = first.startswith(ZIP_PREFIX + "/")
        for m in names:
            if not m.isfile():
                continue
            name = m.name
            if has_prefix:
                if not name.startswith(ZIP_PREFIX + "/"):
                    continue
                rel = name[len(ZIP_PREFIX) + 1:]
            else:
                rel = name
            if not rel or not _should_extract(rel):
                continue
            dst = os.path.join(INSTALL_DIR, rel)
            dst_dir = os.path.dirname(dst)
            os.makedirs(dst_dir, exist_ok=True)
            with tf.extractfile(m) as src, open(dst, "wb") as df:
                shutil.copyfileobj(src, df)
            count += 1
    return count


def _extract_zip(zip_data: bytes) -> int:
    count = 0
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        bad = zf.testzip()
        if bad is not None:
            fail(f"Corrupted zip archive: {bad}")

        # Check if this is a release zip (flat) or repo zip (with prefix dir)
        names = zf.namelist()
        first = names[0] if names else ""
        has_prefix = first.startswith(ZIP_PREFIX + "/")

        for name in names:
            if name.endswith("/"):
                continue
            if has_prefix:
                if not name.startswith(ZIP_PREFIX + "/"):
                    continue
                rel = name[len(ZIP_PREFIX) + 1:]
            else:
                rel = name
            if not rel:
                continue
            if not _should_extract(rel):
                continue

            dst = os.path.join(INSTALL_DIR, rel)
            dst_dir = os.path.dirname(dst)
            os.makedirs(dst_dir, exist_ok=True)
            with zf.open(name) as src, open(dst, "wb") as df:
                shutil.copyfileobj(src, df)
            count += 1

    return count


# ---------------------------------------------------------------------------
# Launchers
# ---------------------------------------------------------------------------

def _create_launchers():
    for name, content in LAUNCHER_TEMPLATES.items():
        path = os.path.join(INSTALL_DIR, name)
        with open(path, "w", newline="\n") as f:
            f.write(content)
        if platform.system() != "Windows":
            st = os.stat(path)
            os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        ok(f"Created launcher: {path}")


# ---------------------------------------------------------------------------
# PATH management (Windows user-level PATH via Registry)
# ---------------------------------------------------------------------------

def _add_to_path_windows() -> bool:
    try:
        import winreg
    except ImportError:
        warn("Could not import winreg.")
        info(f"Add to PATH manually: {INSTALL_DIR}")
        return False

    key_path = r"Environment"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        ) as key:
            try:
                current, reg_type = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                current, reg_type = "", winreg.REG_EXPAND_SZ

            parts = [p.strip() for p in current.split(";") if p.strip()]
            normed = os.path.normcase(os.path.normpath(INSTALL_DIR))
            if any(os.path.normcase(os.path.normpath(p)) == normed for p in parts):
                info("Install directory already in PATH")
                return True

            current = current.rstrip(";") + ";" + INSTALL_DIR
            winreg.SetValueEx(key, "PATH", 0, reg_type, current)

        # Notify Windows of environment change
        try:
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            import ctypes
            ctypes.windll.user32.SendMessageW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment"
            )
        except Exception:
            pass

        ok(f"Added to PATH: {INSTALL_DIR}")
        info("Restart your terminal for the change to take effect.")
        return True
    except Exception as e:
        warn(f"Could not update PATH: {e}")
        info(f"Add to PATH manually: {INSTALL_DIR}")
        return False


def _add_to_path_unix() -> bool:
    candidates = [
        os.environ.get("SHELL", ""),
    ]
    shell = os.environ.get("SHELL", "")
    config_map = {
        "zsh": "~/.zshrc",
        "bash": "~/.bashrc",
        "fish": "~/.config/fish/config.fish",
    }
    target = None
    for shell_name, cfg_path in config_map.items():
        if shell_name in shell:
            target = os.path.expanduser(cfg_path)
            break
    if target is None:
        # Fallback: pick the first existing config
        for cfg_path in ["~/.profile", "~/.bashrc", "~/.zshrc"]:
            p = os.path.expanduser(cfg_path)
            if os.path.exists(p):
                target = p
                break
    if target and os.path.exists(os.path.dirname(target)):
        try:
            with open(target) as f:
                content = f.read()
            marker = f"# Added by Nova installer"
            if marker in content:
                info(f"PATH entry already in {target}")
                return True
            with open(target, "a") as f:
                f.write(f"\n{marker}\nexport PATH=\"$PATH:{INSTALL_DIR}\"\n")
            ok(f"Added PATH to {target}")
            info(f"Run 'source {target}' or restart your terminal.")
            return True
        except Exception as e:
            warn(f"Could not update {target}: {e}")
    info(f"Add this to your shell config: export PATH=\"$PATH:{INSTALL_DIR}\"")
    return False


def _add_to_path():
    if platform.system() == "Windows":
        return _add_to_path_windows()
    return _add_to_path_unix()


def _remove_from_path_windows():
    try:
        import winreg
    except ImportError:
        return
    key_path = r"Environment"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        ) as key:
            try:
                current, reg_type = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                return
            parts = [p.strip() for p in current.split(";") if p.strip()]
            normed = os.path.normcase(os.path.normpath(INSTALL_DIR))
            filtered = [
                p for p in parts
                if os.path.normcase(os.path.normpath(p)) != normed
            ]
            if len(filtered) != len(parts):
                new_path = ";".join(filtered)
                winreg.SetValueEx(key, "PATH", 0, reg_type, new_path)
    except Exception:
        pass


def _remove_from_path_unix():
    for cfg_path in ["~/.zshrc", "~/.bashrc", "~/.profile"]:
        p = os.path.expanduser(cfg_path)
        if os.path.exists(p):
            try:
                with open(p) as f:
                    lines = f.readlines()
                kept = [l for l in lines if INSTALL_DIR not in l]
                if len(kept) != len(lines):
                    with open(p, "w") as f:
                        f.writelines(kept)
                    ok(f"Removed from {p}")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install():
    print()
    print(f"  +========================================+")
    print(f"  |  Nova + Galaxy Unified Installer       |")
    print(f"  +========================================+")
    print()
    info(f"Install directory: {INSTALL_DIR}")

    if os.path.exists(INSTALL_DIR):
        info(f"Directory already exists — will overwrite.")
        ok_msg = "Reinstalled"
    else:
        ok_msg = "Installed"

    data = _download_zip()
    info("Extracting files (this may take a moment)...")
    count = _extract_archive(data)
    ok(f"Extracted {count} files")

    _create_launchers()
    _add_to_path()

    print()
    print(f"  +------------------------------------------------+")
    print(f"  |  {ok_msg} successfully!                         |")
    print(f"  +------------------------------------------------+")
    print()
    info(f"Location: {INSTALL_DIR}")
    if platform.system() == "Windows":
        info("Open a NEW terminal, then:")
    else:
        info("Restart your terminal or source your shell config, then:")
    print()
    info("  nova build hello.nv     Compile a Nova program")
    info("  galaxy install pkg      Install a package")
    info("  galaxy init my-lib      Create a library")
    print()


def uninstall():
    print()
    print(f"  Uninstalling {APP_NAME}...")
    print()
    if os.path.exists(INSTALL_DIR):
        shutil.rmtree(INSTALL_DIR)
        ok(f"Removed: {INSTALL_DIR}")
    else:
        info(f"Nothing to remove at {INSTALL_DIR}")

    if platform.system() == "Windows":
        _remove_from_path_windows()
    else:
        _remove_from_path_unix()
    print()
    ok(f"{APP_NAME} uninstalled.")
    print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--uninstall", "uninstall", "remove"):
        uninstall()
    else:
        install()


if __name__ == "__main__":
    main()
