# -*- coding: utf-8 -*-
"""v3.29: pure-Python port of _run_full.ps1 (same steps, same verdict rules).
Runs under the Bash background runner, which has no 2-minute kill."""
import subprocess, sys, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VENV = r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
NODE = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"
LOG = os.path.join(HERE, "_full_out.txt")

fail = []


def run(cmd):
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def logln(s):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def run_logged(cmd, tag):
    rc, out = run(cmd)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(out.rstrip() + "\n")
    return rc, out


def count_result(path):
    pass_n = fail_n = 0
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                if ln.startswith("PASS"):
                    pass_n += 1
                elif ln.startswith("FAIL"):
                    fail_n += 1
    return pass_n, fail_n


# === syntax ===
with open(LOG, "w", encoding="utf-8") as f:
    f.write("=== syntax (editor.html inline script) ===\n")
rc, out = run_logged([VENV, "_syntax_check.py"], "syntax")
if rc != 0 or "returncode=0" not in out:
    fail.append("syntax")

# === core ===
logln("=== core ===")
rc, out = run_logged([NODE, "test_core.js"], "core")
if rc != 0 or "ALL TESTS PASSED" not in out:
    fail.append("core")

# === probes ===
logln("=== probes ===")
rc, out = run_logged([VENV, "_probe25_export.py"], "probe25")
if "PROBE25 DONE" not in out:
    fail.append("probe25-incomplete")
if '"FAIL"' in out:
    fail.append("probe25-fail")

# 探针脚本名约定为 _<tag>.py；少数探针带后缀，在此显式登记
PROBE_SCRIPT = {"m84": "_m84_toggle.py", "m85": "_m85_toggle2.py",
                "m86": "_m86_bi.py", "m87": "_m87_hdr.py", "m88": "_m88_hdr.py",
                # v3.39 起纳入（v3.39.10 登记批次）：带后缀文件名集中映射
                "m104b": "_m104b_img.py", "m137": "_m137_codew.py",
                "m141": "_m141_slashp.py", "m144": "_m144_mmd14.py",
                "m146": "_m146_mmdsz.py", "m147": "_m147_mmdfix.py",
                "m150": "_m150_mmd19.py", "m151": "_m151_v392.py",
                "m154": "_m154_crop.py", "m155": "_m155_hist.py",
                "m156": "_m156_fmtlog.py", "m157": "_m157_slash.py",
                "m158": "_m158_mmdmenu.py", "m159": "_m159_mmdrz.py",
                "m161": "_m161_qa_invariants.py", "m162": "_m162_qa_stress.py",
                "m163": "_m163_slashctx.py", "m164": "_m164_cropassets.py"}
# 结果文件名 ≠ _<tag>.txt 的探针（v3.39.10 全量核对，_mNNN 前缀别名/后缀名/
# 仅 stdout 输出（映射到 runner 捕获的 *_run.txt）三类均有）
RESULT_FILE = {"m86": "_m86_bi.txt",
               "m104b": "_m104b_img.txt", "m137": "_m137.txt",
               "m141": "_m141_slashp_run.txt",
               "m144": "_m144_mmd14_run.txt", "m146": "_m146_mmdsz_run.txt",
               "m147": "_m147_mmdfix_run.txt",
               "m150": "_m150.txt", "m151": "_m151.txt",
               "m154": "_m154_crop.txt", "m155": "_m155_hist.txt",
               "m156": "_m156_fmtlog.txt", "m157": "_m157_slash.txt",
               "m158": "_m158.txt", "m159": "_m159.txt",
               "m161": "_m161.txt", "m162": "_m162.txt",
               "m163": "_m163.txt", "m164": "_m164.txt"}
for m in ("m29a", "m29b", "m30a", "m30b", "m31", "m33", "m34", "m35", "m39",
          "m83", "m84", "m85", "m86", "m87", "m88",
          # v3.37 起纳入：m104 = 图标块交互收口（代码块顶栏 / 图表留白 / 图表自然尺寸 / 七模板）
          #              m106 = FMT-11/12/13 行内格式叠加回归（字面外露 / LIFO / T× / 单元格下划线）
          #              m107 = DOCGEN-1 换文档时旧渲染态失焦回写脏写（含正常回写不误伤）
          "m104", "m106", "m107",
          # v3.39.10 起纳入：MMD 系 / 裁剪 / 斜杠 / 格式化矩阵 / QA 三不变量 / 压力
          # （m138 结果文件为 OK 前缀格式，count_result 不适用 → 仍单独跑）
          "m104b", "m137", "m141", "m144", "m146", "m147", "m150", "m151",
          "m154", "m155", "m156", "m157", "m158", "m159",
          "m161", "m162", "m163", "m164"):
    subprocess.run([VENV, "_runner.py", PROBE_SCRIPT.get(m, "_%s.py" % m)], cwd=HERE,
                   capture_output=True, text=True)
    time.sleep(5)
    rc_txt = os.path.join(HERE, RESULT_FILE.get(m, "_%s.txt" % m))
    pass_n, fail_n = count_result(rc_txt)
    if fail_n > 0:
        fail.append("%s-fail(%d)" % (m, fail_n))
    elif pass_n == 0:
        fail.append("%s-crash" % m)
    logln("%s done PASS=%d FAIL=%d" % (m, pass_n, fail_n))


# === smoke ===
logln("=== smoke ===")
for n in range(11, 34):
    subprocess.run([VENV, "_runner.py", "_smoke%d.py" % n], cwd=HERE,
                   capture_output=True, text=True)
    time.sleep(5)
    res = os.path.join(HERE, "_smoke%d.txt" % n)
    pass_n, fail_n = count_result(res)
    # Judged by the result file, not the exit code (teardown crashes are noise).
    if fail_n > 0:
        fail.append("smoke%d-fail(%d)" % (n, fail_n))
    elif pass_n == 0:
        fail.append("smoke%d-crash" % n)
    logln("smoke%d done PASS=%d FAIL=%d" % (n, pass_n, fail_n))

# === final integrity check (same as ps1) ===
for n in range(11, 34):
    res = os.path.join(HERE, "_smoke%d.txt" % n)
    pass_n, fail_n = count_result(res)
    if pass_n == 0:
        fail.append("smoke%d-noresult" % n)
    if fail_n > 0:
        fail.append("smoke%d-hasfail" % n)

logln("=== verdict ===")
if fail:
    logln("VERDICT: FAILED -> " + ", ".join(fail))
    sys.exit(1)
logln("VERDICT: ALL GREEN")
sys.exit(0)
