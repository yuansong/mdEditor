# -*- coding: utf-8 -*-
"""mdEditor 启动自检（offscreen）：确认打包产物能正常启动并存活，不崩溃。

用法：
    python selfcheck.py <mdEditor.exe 路径> [等待秒数]
退出码 0 = 存活（PASS）；非 0 = 启动失败 / 过早退出。
"""
import os
import sys
import time
import subprocess

DEFAULT_WAIT = 13


def main():
    if len(sys.argv) < 2:
        print("用法：python selfcheck.py <mdEditor.exe> [wait_seconds]")
        return 2
    exe = os.path.abspath(sys.argv[1])
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_WAIT
    if not os.path.isfile(exe):
        print("[selfcheck] 找不到可执行文件：%s" % exe)
        return 2

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MDEDITOR_SKIP_DRAFT"] = "1"
    # 唯一单实例键，避免与任何可能存在的运行实例冲突
    env["MDEDITOR_SINGLETON_KEY"] = "selfcheck_%d" % int(time.time() * 1000)

    print("[selfcheck] 启动：%s" % exe)
    print("[selfcheck] 平台：offscreen，等待 %ds ..." % wait)
    try:
        p = subprocess.Popen([exe], env=env)
    except Exception as e:
        print("[selfcheck] 启动异常：%s" % e)
        return 2

    # 先小等，确认不是秒退
    time.sleep(3)
    if p.poll() is not None:
        print("[selfcheck] 进程在 3s 内退出，退出码 %s（FAIL）" % p.returncode)
        return 1

    time.sleep(max(0, wait - 3))
    rc = p.poll()
    if rc is None:
        print("[selfcheck] 进程存活 %ds（PASS），pid=%s" % (wait, p.pid))
        # 清理：温和终止自检进程
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
        return 0
    else:
        print("[selfcheck] 进程在 %ds 内退出，退出码 %s（FAIL）" % (wait, rc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
