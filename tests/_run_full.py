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


SUB_TIMEOUT = 300   # GUI 探针正常 30~120s；300s 未退出视为挂死，杀掉继续队列


def run(cmd, timeout=SUB_TIMEOUT):
    try:
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as _te:
        out = (getattr(_te, "stdout", None) or "")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        return -9, out + "\n[runner] TIMEOUT after %ss: %s" % (timeout, cmd[-1])
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
                # v3.48.30：只认「FAIL 」带空格前缀 —— 修「FAIL_COUNT=0」汇总行
                # 被误计为失败的假红（probe_diffmerge/merge/aifrag 三探针均带此行）
                if ln.startswith("PASS"):
                    pass_n += 1
                elif ln.startswith("FAIL "):
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
                "m163": "_m163_slashctx.py", "m164": "_m164_cropassets.py",
                # v3.45.3 起纳入：书籍/双链导航 + 导出链接书签（5 项体验整改收口）
                "m170": "_m170_book.py", "m174": "_m174_wikilink.py",
                "m181": "_m181_verify.py",
                # v3.45.5 起纳入：PDF 相对 .html 单元 + 链接悬停/右键编辑/源码模式
                "m183": "_m183_pdflink_unit.py", "m184": "_m184_v455.py",
                # v3.45.6 起纳入：书籍 PDF 链接不跳转根因修复验收
                "m185": "_m185_pdflink_diag.py",
                # v3.48.12 起纳入：本地语义搜索（SEM-1）核心单测 + UI 探针
                "semcore": "_sem_core_test.py", "semui": "_probe_semsearch.py",
                # v3.48.13 起纳入：反向链接面板（BACKLINK-4）
                "backlink": "_probe_backlinks.py",
                # v3.48.13：m186 幽灵条目修正——库中无 _m186.py，真实探针为 _m186_v3458.py
                "m186": "_m186_v3458.py",
                # v3.48.20 起纳入：编辑器内核「无感化」L1/L2 验证
                "impercept_l1l2": "_probe_impercept_l1l2.py",
                # v3.48.21 起纳入：编辑器内核「无感化」L3/L4/L5 验证
                "impercept_l3l4l5": "_probe_impercept_l3l4l5.py",
                # v3.48.32 起纳入：差异引擎回归（文件名不循 _probe_<tag>.py 约定）
                "expand_diff": "_expand_diff_check.py",
                "probe_fragfail": "_probe_fragfail.py"}
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
               "m163": "_m163.txt", "m164": "_m164.txt",
               "m170": "_m170_book.txt", "m174": "_m174_wikilink.txt",
               "m181": "_m181_verify_run.txt",
               "m183": "_m183_pdflink_unit_run.txt", "m184": "_m184_v455.txt",
               "m185": "_m185_pdflink_diag.txt",
               "semcore": "_sem_core_test.txt",
               "semui": "_probe_semsearch.txt",
               "backlink": "_probe_backlinks.txt",
               "impercept_l1l2": "_probe_impercept_l1l2.txt",
               "impercept_l3l4l5": "_probe_impercept_l3l4l5.txt",
               "ainative": "_probe_ainative_run.txt",
               "aibatch": "_probe_aibatch.txt",
               "mc": "_probe_mc.txt",
               "pandoc": "_probe_pandoc.txt",
               "m186": "_m186_v3458_run.txt",
               # v3.48.32 起纳入：结果文件名不循 _<tag>.txt 约定的差异引擎探针
               "expand_diff": "_expand_diff_check.out.txt",
               "probe_fragfail": "_probe_fragfail_run.txt"}
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
          "m161", "m162", "m163", "m164",
          # v3.45.3：链接导航 + 导出链路（m170/m174/m181）
          # v3.45.5：PDF 相对 .html 单元（m183）+ 链接悬停/右键编辑/源码模式（m184）
          # v3.45.6：书籍 PDF 链接不跳转根因修复（m185）
          "m170", "m174", "m181", "m183", "m184", "m185", "m186",
          # v3.48.12：本地语义搜索（SEM-1）
          "semcore", "semui",
          # v3.48.13：反向链接面板（BACKLINK-4）
          "backlink",
          # v3.48.14~16：AI 原生通道 / 多光标 / Pandoc 验收
          # （aibatch 已随 v3.48.24 移除批量处理功能下架，探针过时不再登记）
          "ainative", "mc", "pandoc",
          # v3.48.20~21：编辑器内核「无感化」L1/L2 + L3/L4/L5 验证
          "impercept_l1l2", "impercept_l3l4l5",
          # v3.48.25（MERGE-CORE）：统一差异引擎 + 三对话框行级合并
          # （脚本名 _probe_<tag>.py / 结果文件 _probe_<tag>.txt 均走默认映射）
          "probe_diffmerge", "probe_merge", "probe_aifrag",
          # v3.48.30（DRIFT-FIX）：长行合并漂移（positionInBlock 根因修复）
          "probe_drift",
          # v3.48.31~32（EXPAND-DIFF / MAP-EDGE）：分层差异 + 用户回归语料
          # （expand_diff = 引擎单测、probe_expand_merge = M1~M9 合并 23 项、
          #  probe_edge_insert = T1~T5 贴边插入合并、probe_fragfail = 失败路径）
          "probe_fragfail", "expand_diff", "probe_expand_merge",
          "probe_edge_insert",
          # v3.48.33（AI-ANCHOR / HINT-ONCE）：位置锚点替换 24 项 + 引导提示一次性 15 项
          "probe_frag_anchor", "probe_hint_once"):
    try:
        subprocess.run([VENV, "_runner.py", PROBE_SCRIPT.get(m, "_%s.py" % m)],
                       cwd=HERE, capture_output=True, text=True, timeout=SUB_TIMEOUT)
    except subprocess.TimeoutExpired:
        fail.append("%s-timeout" % m)
        logln("%s done PASS=0 FAIL=0 (TIMEOUT %ss)" % (m, SUB_TIMEOUT))
        continue
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
    try:
        subprocess.run([VENV, "_runner.py", "_smoke%d.py" % n],
                       cwd=HERE, capture_output=True, text=True, timeout=SUB_TIMEOUT)
    except subprocess.TimeoutExpired:
        fail.append("smoke%d-timeout" % n)
        logln("smoke%d done PASS=0 FAIL=0 (TIMEOUT %ss)" % (n, SUB_TIMEOUT))
        continue
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
