#!/usr/bin/env python3
"""
Galaxy Package Manager — Self-Bootstrapping Installer

Downloads and installs the 'galaxy' command globally on your system.
No need to clone the repo — the installer fetches everything it needs.

Usage:
  python galaxy.py                     Install galaxy
  python galaxy.py --uninstall         Remove galaxy
"""

import sys
import os
import shutil
import stat
import platform
import urllib.request
import urllib.error

APP_NAME = "galaxy"
SOURCE_FILE = "_galaxy.py"
SOURCE_URL = "https://raw.githubusercontent.com/nova-programming/Nova/develop/_galaxy.py"

if platform.system() == "Windows":
    INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "galaxy", "bin")
    LAUNCHER_NAME = "galaxy.bat"
    LAUNCHER_CONTENT = '@echo off\r\nREM Galaxy Package Manager for Nova\r\npython "%~dp0_galaxy.py" %*\r\n'
else:
    INSTALL_DIR = os.path.join(os.path.expanduser("~"), ".galaxy", "bin")
    LAUNCHER_NAME = "galaxy"
    LAUNCHER_CONTENT = '#!/usr/bin/env python3\nimport sys, os\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\nfrom _galaxy import main\nmain()\n'


def warn(msg):   print(f"  [WARN] {msg}")
def success(msg): print(f"  [OK]   {msg}")
def info(msg):    print(f"  [..]  {msg}")
def error(msg):   print(f"  [FAIL] {msg}"); sys.exit(1)


def download_source():
    info(f"Downloading {SOURCE_FILE} from GitHub...")
    try:
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "galaxy-installer/1.0"})
        with urllib.request.urlopen(req, timeout=30) as rsp:
            return rsp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        error(f"Failed to download {SOURCE_FILE} (HTTP {e.code}: {e.reason})")
    except urllib.error.URLError as e:
        error(f"Network error: {e.reason}. Check your internet connection.")
    except Exception as e:
        error(f"Failed to download {SOURCE_FILE}: {e}")


def find_local_source():
    """Look for _galaxy.py next to this script (useful when run from repo checkout)."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), SOURCE_FILE)
    if os.path.exists(local):
        return local
    return None


def install_source(content):
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dst = os.path.join(INSTALL_DIR, SOURCE_FILE)
    try:
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        success(f"Installed {SOURCE_FILE} to {dst}")
    except Exception as e:
        error(f"Failed to write {dst}: {e}")
    if platform.system() != "Windows":
        st = os.stat(dst)
        os.chmod(dst, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dst


def copy_local_source(src_path):
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dst = os.path.join(INSTALL_DIR, SOURCE_FILE)
    try:
        shutil.copy2(src_path, dst)
        success(f"Copied {SOURCE_FILE} to {dst}")
    except Exception as e:
        error(f"Failed to copy {SOURCE_FILE}: {e}")
    if platform.system() != "Windows":
        st = os.stat(dst)
        os.chmod(dst, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dst


def create_launcher():
    launcher_path = os.path.join(INSTALL_DIR, LAUNCHER_NAME)
    try:
        with open(launcher_path, "w", newline="\n") as f:
            f.write(LAUNCHER_CONTENT)
        if platform.system() != "Windows":
            st = os.stat(launcher_path)
            os.chmod(launcher_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        success(f"Created launcher: {launcher_path}")
    except Exception as e:
        error(f"Failed to create launcher: {e}")
    return launcher_path


def add_to_path_windows():
    try:
        import winreg
    except ImportError:
        warn("Could not import winreg. Add to PATH manually:"); info(f"  {INSTALL_DIR}")
        return False
    key_path = r"Environment"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current_path, reg_type = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                current_path = ""; reg_type = winreg.REG_EXPAND_SZ
            parts = [p.strip() for p in current_path.split(";") if p.strip()]
            normalized = os.path.normcase(os.path.normpath(INSTALL_DIR))
            if any(os.path.normcase(os.path.normpath(p)) == normalized for p in parts):
                info("Install directory already in PATH"); return True
            new_path = current_path.rstrip(";") + ";" + INSTALL_DIR
            winreg.SetValueEx(key, "PATH", 0, reg_type, new_path)
        try:
            HWND_BROADCAST = 0xFFFF; WM_SETTINGCHANGE = 0x001A
            import ctypes
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")
        except Exception:
            pass
        success(f"Added to PATH: {INSTALL_DIR}")
        info("Restart your terminal for the change to take effect.")
        return True
    except Exception as e:
        warn(f"Could not update PATH automatically: {e}")
        info(f"Add this to your PATH manually: {INSTALL_DIR}")
        return False


def add_to_path_unix():
    shell_config = None
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        shell_config = os.path.expanduser("~/.zshrc")
    elif "bash" in shell:
        shell_config = os.path.expanduser("~/.bashrc")
    else:
        for cfg in ["~/.profile", "~/.bashrc", "~/.zshrc", "~/.config/fish/config.fish"]:
            p = os.path.expanduser(cfg)
            if os.path.exists(p):
                shell_config = p; break
    path_line = f'\nexport PATH="$PATH:{INSTALL_DIR}"\n'
    if shell_config and os.path.exists(os.path.dirname(shell_config)):
        try:
            with open(shell_config, "r") as f:
                content = f.read()
            if INSTALL_DIR in content:
                info(f"Install directory already in {shell_config}"); return True
            with open(shell_config, "a") as f:
                f.write(f"\n# Added by galaxy installer\n{path_line}")
            success(f"Added PATH to {shell_config}")
            info("Run 'source {0}' or restart your terminal.".format(shell_config))
            return True
        except Exception as e:
            warn(f"Could not update {shell_config}: {e}")
    else:
        warn("Could not detect shell config file.")
    info(f"Add this to your shell config: export PATH=\"$PATH:{INSTALL_DIR}\"")
    return False


def add_to_path():
    if platform.system() == "Windows":
        return add_to_path_windows()
    else:
        return add_to_path_unix()


def remove_from_path_windows():
    try:
        import winreg
    except ImportError:
        return False
    key_path = r"Environment"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current_path, reg_type = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                return True
            parts = [p.strip() for p in current_path.split(";") if p.strip()]
            normalized = os.path.normcase(os.path.normpath(INSTALL_DIR))
            filtered = [p for p in parts if os.path.normcase(os.path.normpath(p)) != normalized]
            if len(filtered) == len(parts):
                return True
            new_path = ";".join(filtered)
            winreg.SetValueEx(key, "PATH", 0, reg_type, new_path)
            return True
    except Exception:
        return False


def remove_from_path_unix():
    for cfg in ["~/.zshrc", "~/.bashrc", "~/.profile"]:
        p = os.path.expanduser(cfg)
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    lines = f.readlines()
                filtered = [l for l in lines if INSTALL_DIR not in l]
                if len(filtered) != len(lines):
                    with open(p, "w") as f:
                        f.writelines(filtered)
                    success(f"Removed from {p}")
            except Exception:
                pass


def do_uninstall():
    print(f"\n  Uninstalling {APP_NAME}...\n")
    launcher = os.path.join(INSTALL_DIR, LAUNCHER_NAME)
    if os.path.exists(launcher):
        os.remove(launcher); success(f"Removed launcher: {launcher}")
    galaxy_py = os.path.join(INSTALL_DIR, SOURCE_FILE)
    if os.path.exists(galaxy_py):
        os.remove(galaxy_py); success(f"Removed: {galaxy_py}")
    if os.path.exists(INSTALL_DIR):
        try:
            os.rmdir(INSTALL_DIR); success(f"Removed directory: {INSTALL_DIR}")
        except OSError:
            info(f"Directory not empty, keeping: {INSTALL_DIR}")
    if platform.system() == "Windows":
        remove_from_path_windows()
    else:
        remove_from_path_unix()
    print(f"\n  [OK]   {APP_NAME} has been uninstalled.\n")


def do_install():
    print(f"\n  +========================================+")
    print(f"  |  Galaxy Package Manager Installer      |")
    print(f"  +========================================+\n")
    info(f"Install directory: {INSTALL_DIR}")

    local_src = find_local_source()
    if local_src:
        info(f"Found {SOURCE_FILE} locally — copying directly.")
        content = open(local_src, "r", encoding="utf-8").read()
    else:
        info(f"No local {SOURCE_FILE} — downloading from GitHub...")
        content = download_source()

    install_source(content)
    launcher = create_launcher()
    add_to_path()

    print(f"\n  [OK]   {APP_NAME} installed successfully!\n")
    info(f"Install location: {INSTALL_DIR}")
    info(f"Launcher: {launcher}")
    if platform.system() == "Windows":
        info("Open a NEW terminal window and type: galaxy")
    else:
        info("Run 'source ~/.zshrc' (or your shell config), then: galaxy")
    print()
    info("Usage examples:")
    info("  galaxy init my-lib        Create a library")
    info("  galaxy search math        Search registry")
    info("  galaxy install nova-math  Install a package")
    print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--uninstall", "uninstall", "remove"):
        do_uninstall()
    else:
        do_install()


if __name__ == "__main__":
    main()
