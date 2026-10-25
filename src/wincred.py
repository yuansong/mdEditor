# -*- coding: utf-8 -*-
"""v3.46（SoloMD P1）：Windows 凭据管理器封装（ctypes，免 keyring 依赖）。

用于存储 AI API Key 等敏感字符串。非 Windows 平台或接口不可用时，调用方
（ai_pane）应回退到 QSettings 本地存储；本模块只负责凭据管理器的读 / 写 / 删。
"""
import ctypes
from ctypes import (wintypes, Structure, POINTER, cast, byref,
                    create_string_buffer, c_void_p, c_char)

CRED_TYPE_GENERIC = 0x1
CRED_PERSIST_LOCAL_MACHINE = 0x2

_AVAILABLE = False
_adv = None
try:
    _adv = ctypes.windll.advapi32

    class _CREDENTIALA(Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPSTR),
            ("Comment", wintypes.LPSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", wintypes.LPBYTE),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", c_void_p),
            ("TargetAlias", wintypes.LPSTR),
            ("UserName", wintypes.LPSTR),
        ]

    _adv.CredWriteA.argtypes = [POINTER(_CREDENTIALA), wintypes.DWORD]
    _adv.CredWriteA.restype = wintypes.BOOL
    _adv.CredReadA.argtypes = [wintypes.LPCSTR, wintypes.DWORD, wintypes.DWORD, POINTER(c_void_p)]
    _adv.CredReadA.restype = wintypes.BOOL
    _adv.CredDeleteA.argtypes = [wintypes.LPCSTR, wintypes.DWORD, wintypes.DWORD]
    _adv.CredDeleteA.restype = wintypes.BOOL
    _adv.CredFree.argtypes = [c_void_p]
    _adv.CredFree.restype = None
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


def available():
    """凭据管理器是否可用（仅 Windows + 接口加载成功为 True）。"""
    return _AVAILABLE


def save_cred(target, secret):
    """写入一条 GENERIC 凭据（本地机器级持久化）。secret 为明文字符串。"""
    blob = secret.encode("utf-8")
    cred = _CREDENTIALA()
    cred.Flags = 0
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = target.encode("utf-8")
    cred.Comment = b"mdEditor AI API Key"
    cred.CredentialBlobSize = len(blob)
    cred.CredentialBlob = cast(create_string_buffer(blob, len(blob)), wintypes.LPBYTE)
    cred.Persist = CRED_PERSIST_LOCAL_MACHINE
    if not _adv.CredWriteA(byref(cred), 0):
        raise ctypes.WinError()


def read_cred(target):
    """读取凭据明文；不存在返回 None。"""
    p = c_void_p()
    if not _adv.CredReadA(target.encode("utf-8"), CRED_TYPE_GENERIC, 0, byref(p)):
        return None
    try:
        cred = cast(p, POINTER(_CREDENTIALA)).contents
        size = cred.CredentialBlobSize
        buf = cast(cred.CredentialBlob, POINTER(c_char))
        # v3.47 修复：buf[:size] 已是 bytes，原 .tobytes() 在非 py2 下抛 AttributeError；
        # 改用 ctypes.string_at 取定长字节再解码（避免密钥读取失败被上层吞掉）
        return ctypes.string_at(buf, size).decode("utf-8", "replace")
    finally:
        _adv.CredFree(p)


def delete_cred(target):
    """删除凭据（不存在时静默）。"""
    try:
        _adv.CredDeleteA(target.encode("utf-8"), CRED_TYPE_GENERIC, 0)
    except Exception:
        pass
