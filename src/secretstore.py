# -*- coding: utf-8 -*-
"""v3.47（P0 跨平台）：跨平台密钥存储抽象层。

为 AI API Key 等敏感字符串提供统一接口 save_cred / read_cred / delete_cred，
按平台分派后端，调用方（ai_pane）无需感知底层平台实现：

- Windows  → wincred（Win32 Credential Manager，本地机器级持久化）
- macOS    → security(1) CLI（Keychain login keychain）
- Linux    → secret-tool(1)（Secret Service / libsecret）；不可用则回退到文件
- 兜底      → 本地加密文件 ~/.config/mdeditor/credentials.json（仅属主可读写）

保持与旧版 Windows 凭据管理器一致的 TargetName（CRED_TARGET），已存密钥可继续读取。
"""
import base64
import json
import os
import platform
import stat
import subprocess

try:
    import wincred
except Exception:  # pragma: no cover - 非 Windows 或接口不可用时
    wincred = None

# 与历史 Windows Credential Manager TargetName 保持一致，避免旧密钥丢失
CRED_TARGET = "mdEditor/AI/APIKey"

_SYS = platform.system()  # "Windows" / "Darwin" / "Linux" / "Java" / ""


def _has_cli(name):
    from shutil import which
    return which(name) is not None


def _backend_name():
    if _SYS == "Windows" and wincred is not None and wincred.available():
        return "wincred"
    if _SYS == "Darwin" and _has_cli("security"):
        return "macos-keychain"
    if _SYS == "Linux" and _has_cli("secret-tool"):
        return "linux-secret-tool"
    # Linux（无 Secret Service）/ macOS（无 security）/ 未知平台 → 文件兜底
    return "file"


BACKEND = _backend_name()


def backend_name():
    """返回当前生效的后端名（用于 UI 提示 / 诊断）。"""
    return BACKEND


def available():
    """密钥后端是否可用——文件兜底始终可用，故恒为 True。"""
    return True


# ───────────────────────── Windows（wincred） ─────────────────────────
def _win_save(target, secret):
    wincred.save_cred(target, secret)


def _win_read(target):
    return wincred.read_cred(target)


def _win_delete(target):
    wincred.delete_cred(target)


# ───────────────────────── macOS Keychain（security CLI） ─────────────────────────
_MAC_SERVICE = "mdEditor"


def _mac_save(target, secret):
    # 先删后写，避免重复条目堆积
    subprocess.run(["security", "delete-generic-password", "-s", _MAC_SERVICE,
                    "-a", target], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)
    rc = subprocess.run(["security", "add-generic-password", "-s", _MAC_SERVICE,
                         "-a", target, "-w", secret], check=False)
    return rc.returncode == 0


def _mac_read(target):
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", _MAC_SERVICE,
                              "-a", target, "-w"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, check=False, timeout=5)
        if out.returncode != 0:
            return None
        return out.stdout.decode("utf-8", "replace").rstrip("\n")
    except Exception:
        return None


def _mac_delete(target):
    subprocess.run(["security", "delete-generic-password", "-s", _MAC_SERVICE,
                    "-a", target], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)


# ───────────────────────── Linux Secret Service（secret-tool） ─────────────────────────
def _linux_save(target, secret):
    p = subprocess.run(["secret-tool", "store", "--label", "mdEditor " + target,
                        "service", "mdEditor", "account", target],
                       input=secret.encode("utf-8"), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
    return p.returncode == 0


def _linux_read(target):
    try:
        out = subprocess.run(["secret-tool", "lookup", "service", "mdEditor",
                              "account", target], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, check=False, timeout=5)
        if out.returncode != 0:
            return None
        return out.stdout.decode("utf-8", "replace")
    except Exception:
        return None


def _linux_delete(target):
    subprocess.run(["secret-tool", "delete", "service", "mdEditor",
                    "account", target], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)


# ───────────────────────── 文件兜底（仅属主可读写） ─────────────────────────
def _store_path():
    if _SYS == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "mdEditor")
    else:
        d = os.path.join(os.path.expanduser("~"), ".config", "mdeditor")
    return os.path.join(d, "credentials.json")


def _file_load():
    p = _store_path()
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _file_save_all(data):
    p = _store_path()
    d = os.path.dirname(p)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        return
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except Exception:
            pass
    except Exception:
        pass


def _file_save(target, secret):
    data = _file_load()
    data[target] = base64.b64encode(secret.encode("utf-8")).decode("ascii")
    _file_save_all(data)
    return True


def _file_read(target):
    data = _file_load()
    raw = data.get(target)
    if not raw:
        return None
    try:
        return base64.b64decode(raw).decode("utf-8", "replace")
    except Exception:
        return None


def _file_delete(target):
    data = _file_load()
    if target in data:
        del data[target]
        _file_save_all(data)


# ───────────────────────── 公共 API ─────────────────────────
def save_cred(target, secret):
    """写入凭据（明文 secret）。按后端分派；失败抛异常由调用方捕获。"""
    if BACKEND == "wincred":
        _win_save(target, secret)
    elif BACKEND == "macos-keychain":
        if not _mac_save(target, secret):
            raise RuntimeError("security 写入 Keychain 失败")
    elif BACKEND == "linux-secret-tool":
        if not _linux_save(target, secret):
            raise RuntimeError("secret-tool 写入失败")
    else:
        _file_save(target, secret)


def read_cred(target):
    """读取凭据明文；不存在返回 None。"""
    if BACKEND == "wincred":
        return _win_read(target)
    elif BACKEND == "macos-keychain":
        return _mac_read(target)
    elif BACKEND == "linux-secret-tool":
        return _linux_read(target)
    else:
        return _file_read(target)


def delete_cred(target):
    """删除凭据（不存在时静默）。"""
    if BACKEND == "wincred":
        _win_delete(target)
    elif BACKEND == "macos-keychain":
        _mac_delete(target)
    elif BACKEND == "linux-secret-tool":
        _linux_delete(target)
    else:
        _file_delete(target)
