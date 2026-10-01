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
    try:
        os.remove(result)
    except OSError:
        try:
            os.replace(result, result + ".trash")
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
        try:
            r = subprocess.run([py, target], stdout=f, stderr=subprocess.STDOUT,
                               cwd=here, env=env, timeout=TIMEOUT)
            return r.returncode, False
        except subprocess.TimeoutExpired:
            return None, True


rc, timed_out = attempt(1)
if timed_out:
    print("timeout after", TIMEOUT, "s -> retry once")
    time.sleep(3)                      # 给 Chromium 释放共享上下文留时间
    rc, timed_out = attempt(2)
    if timed_out:
        print("timeout again -> give up")
        sys.exit(1)
print("exit=", rc, "->", out)
