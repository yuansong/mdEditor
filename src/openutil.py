# -*- coding: utf-8 -*-
"""跨平台「用系统默认程序打开文件 / 打开所在文件夹」。

- Windows : os.startfile（仅 Windows 存在）
- macOS   : open
- Linux   : xdg-open

早期实现直接调用 os.startfile，在非 Windows 平台会因该符号不存在而崩溃；
本模块统一封装，使导出完成后的「打开文件 / 打开文件夹」、外部程序打开、
查看更新日志等操作在三平台上行为一致。
"""
import os
import subprocess
import sys


def open_path(path):
    """用系统默认关联程序打开文件或目录。

    任何失败都收敛为 OSError，便于上层已有的 ``except OSError`` 处理复用。
    """
    target = os.path.abspath(path)
    try:
        if sys.platform == "win32":
            os.startfile(target)                 # noqa: S606 — Windows 关联程序
        elif sys.platform == "darwin":
            subprocess.run(["open", target], check=True)
        else:  # linux / 其它 POSIX
            subprocess.run(["xdg-open", target], check=True)
    except Exception as exc:  # noqa: BLE001 — 统一上抛为 OSError
        raise OSError(str(exc)) from exc


def open_in_folder(path):
    """在文件管理器中定位到 path 所在目录（path 可为文件或目录本身）。"""
    p = os.path.abspath(path)
    if os.path.isfile(p):
        p = os.path.dirname(p) or "."
    try:
        if sys.platform == "win32":
            os.startfile(p)                       # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", p], check=True)
        else:
            subprocess.run(["xdg-open", p], check=True)
    except Exception as exc:  # noqa: BLE001
        raise OSError(str(exc)) from exc
