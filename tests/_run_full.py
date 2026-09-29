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
PROBE_SCRIPT = {"m84": "_m84_toggle.py", "m85": "_m85_toggle2.py"}
for m in ("m29a", "m29b", "m30a", "m30b", "m31", "m33", "m34", "m35", "m39",
          "m83", "m84", "m85"):
    subprocess.run([VENV, "_runner.py", PROBE_SCRIPT.get(m, "_%s.py" % m)], cwd=HERE,
                   capture_output=True, text=True)
    time.sleep(5)
    rc_txt = os.path.join(HERE, "_%s.txt" % m)
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
