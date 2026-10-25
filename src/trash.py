# -*- coding: utf-8 -*-
"""v3.47（P0 跨平台）：跨平台回收站 / 删除。

send_to_trash(path) 把文件 / 目录移入系统回收站：
- Windows  → SHFileOperationW(FO_DELETE, FOF_ALLOWUNDO)
- macOS    → 复制到 ~/.Trash（同名冲突加时间戳），再移除原文件
- Linux    → gio trash（可用时）；否则按 XDG 规范写入 ~/.local/share/Trash
- 兜底      → 永久删除（极罕见，仅未知平台且无回收站机制时）

返回值：
- True     ：已移入回收站（或兜底永久删除成功）
- False    ：操作失败（文件不存在 / 权限不足等）
注意：兜底永久删除不会返回 False（视为已删除），但调用方可读 backend_name()
判断是否需要额外告警。
"""
import os
import platform
import shutil
import subprocess
import time

_SYS = platform.system()  # "Windows" / "Darwin" / "Linux" / "Java" / ""


def backend_name():
    """返回当前回收站实现：'windows' | 'macos-trash' | 'linux-gio' | 'linux-xdg' | 'permanent'。"""
    if _SYS == "Windows":
        return "windows"
    if _SYS == "Darwin":
        return "macos-trash"
    if _SYS == "Linux":
        from shutil import which
        if which("gio"):
            return "linux-gio"
        return "linux-xdg"
    return "permanent"


def _win_recycle(path):
    import ctypes
    from ctypes import (wintypes, Structure, c_void_p, c_uint, c_ushort,
                        c_wchar_p, c_int)

    class SHFILEOPSTRUCTW(Structure):
        _fields_ = [("hwnd", c_void_p), ("wFunc", c_uint),
                    ("pFrom", c_wchar_p), ("pTo", c_wchar_p),
                    ("fFlags", c_ushort), ("fAnyOperationsAborted", c_int),
                    ("hNameMappings", c_void_p), ("lpszProgressTitle", c_wchar_p)]

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = 3                    # FO_DELETE
    op.pFrom = path + "\0"
    op.pTo = None
    op.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400  # ALLOWUNDO|NOCONFIRMATION|SILENT|NOERRORUI
    try:
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    except (OSError, AttributeError):
        return False
    return rc == 0 and not op.fAnyOperationsAborted


def _unique_dest(dest):
    """同名冲突时在 basename 中插入毫秒时间戳，避免覆盖回收站内既有文件。"""
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(dest)
    return "%s-%d%s" % (base, int(time.time() * 1000), ext)


def _mac_trash(path):
    trash = os.path.join(os.path.expanduser("~"), ".Trash")
    try:
        os.makedirs(trash, exist_ok=True)
    except Exception:
        return False
    name = os.path.basename(path.rstrip("/"))
    dest = _unique_dest(os.path.join(trash, name))
    try:
        shutil.move(path, dest)
        return True
    except Exception:
        return False


def _linux_trash(path):
    from shutil import which
    if which("gio"):
        try:
            rc = subprocess.run(["gio", "trash", path], check=False)
            if rc.returncode == 0:
                return True
        except Exception:
            pass
    # XDG 用户级回收站：~/.local/share/Trash/{files,info}
    home = os.path.expanduser("~")
    files_dir = os.path.join(home, ".local", "share", "Trash", "files")
    info_dir = os.path.join(home, ".local", "share", "Trash", "info")
    try:
        os.makedirs(files_dir, exist_ok=True)
        os.makedirs(info_dir, exist_ok=True)
    except Exception:
        return False
    name = os.path.basename(path.rstrip("/"))
    dest = _unique_dest(os.path.join(files_dir, name))
    try:
        shutil.move(path, dest)
        info_path = os.path.join(info_dir, os.path.basename(dest) + ".trashinfo")
        try:
            with open(info_path, "w", encoding="utf-8") as f:
                f.write("[Trash Info]\n")
                f.write("Path=%s\n" % path)
                f.write("DeletionDate=%s\n" %
                        time.strftime("%Y-%m-%dT%H:%M:%S"))
        except Exception:
            pass
        return True
    except Exception:
        return False


def _permanent_delete(path):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True
    except Exception:
        return False


def send_to_trash(path):
    """移入系统回收站；成功返回 True，失败返回 False。"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return False
    if _SYS == "Windows":
        return _win_recycle(path)
    if _SYS == "Darwin":
        return _mac_trash(path)
    if _SYS == "Linux":
        return _linux_trash(path)
    return _permanent_delete(path)
