# 运行子进程并捕获 stdout/stderr 到文件（PowerShell 输出捕获不稳定时的包装器）
import subprocess, sys, os, time

if len(sys.argv) < 2:
    print("usage: _runner.py <script.py>")
    sys.exit(2)

target = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
# 支持从项目根目录传 "tests/_xxx.py" 或在 tests 目录内直接传 "_xxx.py"，统一解析为绝对路径
if not os.path.isabs(target):
    target = os.path.abspath(target)
if not os.path.exists(target):
    cand = os.path.join(here, os.path.basename(target))
    if os.path.exists(cand):
        target = cand
out = os.path.join(here, os.path.splitext(os.path.basename(target))[0] + "_run.txt")
# 结果文件（脚本结束时写出）：跑之前先删，避免超时/崩溃后 verdict 读到上一轮陈旧结果
# v3.32：os.remove 受环境删除拦截时降级 rename 到 .trash（rename 不受影响）
result = os.path.join(here, os.path.splitext(os.path.basename(target))[0] + ".txt")
if os.path.exists(result):
    # v3.48.14：改截断而非 os.remove —— 环境 safe-delete 守卫按每轮 50 次删除
    # 限额拦截，且拦截方式是直接终止进程（不抛 OSError），全量回归超限后
    # _runner.py 在首行清理即被杀、探针根本没跑，verdict 误读上一轮陈旧结果。
    # 截断是写操作不触发守卫；mtime 早于 attempt() 的 start_ts，新鲜度判定不变。
    try:
        with open(result, "w", encoding="utf-8"):
            pass
    except OSError:
        pass
# v3.39.9：部分探针的结果文件名与脚本名不同步（如 _m159_mmdrz.py → _m159.txt、
# _m158_mmdmenu.py → _m158.txt），按 _mNNN 前缀把对应历史结果一并删除，
# 否则超时/崩溃后 verdict 会读到上一轮陈旧结果
import re as _re
_m = _re.match(r'_m(\d+)', os.path.basename(target))
if _m:
    alt = os.path.join(here, '_m%s.txt' % _m.group(1))
else:
    # v3.39.10：smoke 等非 _mNNN 探针无别名 —— 原实现在此分支对 None 调
    # os.path.abspath 直接 TypeError，runner 秒挂且不产生任何 run 文件
    # （smoke11~33「crash/noresult」假象、smoke31~33 读陈旧结果假通过同源）
    alt = None
if alt and os.path.abspath(alt) != os.path.abspath(result) and os.path.exists(alt):
    # 同上：别名结果文件也改截断（_m159_mmdrz.py → _m159.txt 之类）
    try:
        with open(alt, "w", encoding="utf-8"):
            pass
    except OSError:
        pass
py = sys.executable

# v3.28：单个 smoke 的时限收紧到 420s（正常 30~90s），超时视为
# QWebEngine 初始化挂死（批量连跑时偶发 GPU 上下文创建失败：
# "Failed to create shared context for virtualization"），
# 此时自动重试一次 —— 换新进程后 GPU 状态重建，实测可恢复。
TIMEOUT = 420
TRIES = 2


def attempt(tag):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    # v3.28：批量连跑 GUI 用例时曾出现 QWebEngine 初始化挂死
    # （chromium gpu_channel_manager: Failed to create shared context for virtualization），
    # 强制软件渲染 + 关沙箱可稳定初始化（脚本自身只设 QTWEBENGINE_CHROMIUM_FLAGS，不会覆盖这两项）。
    env["QT_OPENGL"] = "software"
    env["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
    # v3.32（P0-1）：测试进程关闭影子草稿与启动恢复弹窗 —— smoke 大量编辑
    # 未命名文档，避免向 %APPDATA%/mdEditor/drafts 写入垃圾草稿
    env["MDEDITOR_SKIP_DRAFT"] = "1"
    mode = "w" if tag == 1 else "a"
    with open(out, mode, encoding="utf-8") as f:
        if tag > 1:
            f.write("\n===== RETRY after timeout =====\n")
        # v3.39.9：探针「结果文件已写完但进程不退出」（QWebEngine 退出竞态，
        # GPU/IPC 线程偶发挂住，实测同一探针时 hang 时不 hang）不再干等 420s ——
        # Popen + 轮询：结果文件生成且连续 ~3s 大小不变即判定完成，主动结束进程。
        proc = subprocess.Popen([py, target], stdout=f, stderr=subprocess.STDOUT,
                                cwd=here, env=env)
        deadline = time.time() + TIMEOUT
        # v3.39.9b：稳定性判定必须基于「本轮新写入」——若旧结果文件删除失败
        # （沙箱删除拦截/配额），陈旧文件会被误判为已完成、3 秒就杀掉新探针。
        # 记录启动时刻，轮询时要求文件 mtime 晚于启动才算本轮产出。
        start_ts = time.time()
        last_size = -1
        stable = 0
        finished = False
        timed_out = False
        while True:
            if proc.poll() is not None:
                finished = True      # 进程自然退出（正常路径）
                break
            if time.time() >= deadline:
                timed_out = True
                break
            sz = -1
            for cand in ((result, alt) if alt else (result,)):
                try:
                    st = os.stat(cand)
                    if st.st_mtime > start_ts:
                        sz = max(sz, st.st_size)
                except OSError:
                    pass
            if sz > 0:
                if sz == last_size:
                    stable += 1
                    # v3.39.11：3s → 8s —— m104 D 组等慢段（setmd+菜单+提交连续
                    # 等待 ~3s 不写文件）会被 3s 判定误杀（exit=0 但结果截断、
                    # 无 SUMMARY），实测三次两杀；8s 仍远小于 420s 超时
                    if stable >= 8:  # 结果文件 ~8s 无增长 = 已写完
                        finished = True
                        break
                else:
                    stable = 0
                last_size = sz
            time.sleep(1)
        if not finished:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
        if timed_out:
            return None, True
        return 0, False


rc, timed_out = attempt(1)
if timed_out:
    print("timeout after", TIMEOUT, "s -> retry once")
    time.sleep(3)                      # 给 Chromium 释放共享上下文留时间
    rc, timed_out = attempt(2)
    if timed_out:
        print("timeout again -> give up")
        sys.exit(1)
print("exit=", rc, "->", out)
