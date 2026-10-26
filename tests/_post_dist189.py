# -*- coding: utf-8 -*-
"""v3.48.33 打包后处理：dist → dist189、SHA256、启动自检、清理旧版。"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
import uuid

ROOT = r"E:\WorkBuddy\md-editor"
SRC = os.path.join(ROOT, "dist")
DST = os.path.join(ROOT, "dist189")
EXE = os.path.join(DST, "mdEditor", "mdEditor.exe")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    # 并发/重入锁：沙箱重试可能让本脚本被执行两次，第二次直接退出
    lock = os.path.join(ROOT, "tests", "_post189.lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(time.time()).encode())
        os.close(fd)
    except FileExistsError:
        age = time.time() - os.path.getmtime(lock)
        if age < 600:
            print("[skip] another post run in progress (lock age %.0fs)" % age)
            return
        os.remove(lock)

    # 幂等：只有新构建（SRC）存在时才动 DST，避免重复执行把成品删掉
    if os.path.isdir(SRC):
        if os.path.isdir(DST):
            shutil.rmtree(DST)
        os.rename(SRC, DST)
        print("[rename] dist -> dist189")
    elif os.path.isfile(EXE):
        print("[reuse] dist189 已存在，跳过重命名")
    assert os.path.isfile(EXE), "exe missing: %s" % EXE

    digest = sha256(EXE)
    with open(os.path.join(ROOT, "dist189.sha256"), "w", encoding="utf-8") as f:
        f.write("%s  mdEditor.exe\n" % digest)
    print("[sha256]", digest)
    print("[size] %.2f MB" % (os.path.getsize(EXE) / 1048576))

    env = dict(os.environ)
    env.update({
        "MDEDITOR_SKIP_DRAFT": "1",
        "QT_QPA_PLATFORM": "offscreen",
        "MDEDITOR_SINGLETON_KEY": "verify-34833-" + uuid.uuid4().hex[:10],
    })
    proc = subprocess.Popen([EXE], env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    alive = None
    for _ in range(26):           # ~13s
        time.sleep(0.5)
        if proc.poll() is not None:
            alive = False
            break
    if alive is None:
        alive = proc.poll() is None
    print("[selfcheck] alive=%s (pid=%s, rc=%s)" % (alive, proc.pid, proc.poll()))
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            proc.kill()
        except OSError:
            pass

    # 只留最近两版
    for old in ("dist187",):
        p = os.path.join(ROOT, old)
        if os.path.isdir(p):
            shutil.rmtree(p)
            print("[clean]", old)
        s = os.path.join(ROOT, old + ".sha256")
        if os.path.isfile(s):
            os.remove(s)
            print("[clean]", old + ".sha256")

    try:
        os.remove(lock)
    except OSError:
        pass
    print("POST DONE")
    if not alive:
        sys.exit(2)


if __name__ == "__main__":
    main()
