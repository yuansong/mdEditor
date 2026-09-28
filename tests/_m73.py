# -*- coding: utf-8 -*-
"""m73 回归：合并 → 还原（unmerge）应把合并格按 rs × cs 完整铺回网格。

用户报告：3×4 表格合并成一个单元格后点「还原」，源码错乱成
  第 0 行 4 格、第 1/2 行各 1 格（且全部是 th）。
本用例覆盖：整表合并 / 子区域合并 / 单行合并 / 存储往返 / 连续合并还原。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m73.txt")
out = []
FAIL = [0]
TOTAL = [0]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def jj(code):
    try:
        return json.loads(js(code))
    except Exception as e:
        return {"err": "%s / %s" % (e, str(js(code))[:160])}


wait(3000)

T34 = ('<table class="md-tbl">\n<thead>\n'
       '<tr><th>h0</th><th>h1</th><th>h2</th><th>h3</th></tr>\n</thead>\n<tbody>\n'
       '<tr><td>b0c0</td><td>b0c1</td><td>b0c2</td><td>b0c3</td></tr>\n'
       '<tr><td>b1c0</td><td>b1c1</td><td>b1c2</td><td>b1c3</td></tr>\n'
       '</tbody>\n</table>')

AUDIT = "window.__tblAudit()"


def setmd(md):
    js("window.setMarkdown(%s)" % json.dumps(md))
    wait(900)


def sel(r0, c0, r1, c1):
    js("window.__tblSelSet(0,%d,%d,%d,%d)" % (r0, c0, r1, c1))
    wait(250)


def do(op):
    js("window.__tblOp('%s')" % op)
    wait(900)


def perrow(au):
    """每行格数"""
    d = {}
    for c in au.get("cells", []):
        d[c["r"]] = d.get(c["r"], 0) + 1
    return [d.get(i, 0) for i in range(au.get("rows", 0))]


def merges(au):
    return [(c["r"], c["c"], c["rs"], c["cs"]) for c in au.get("cells", [])
            if c["rs"] > 1 or c["cs"] > 1]


def tags(au):
    """每行的标签（th / td）—— 用 raw 里的标签统计更直观"""
    raw = au.get("raw") or ""
    return raw


# ============ U1: 整表（3×4）合并 → 还原 ============
log("CASE U1 begin")
setmd(T34)
sel(0, 0, 2, 3)
do("merge")
a1 = jj(AUDIT)
log("  U1 合并后 audit ok=%s merges=%s perrow=%s" % (a1.get("ok"), merges(a1), perrow(a1)))
check("U1 合并成一个单元格（rs=3,cs=4）", merges(a1) == [(0, 0, 3, 4)], str(merges(a1)))
sel(0, 0, 0, 0)
do("unmerge")
a2 = jj(AUDIT)
log("  U1 还原后 audit ok=%s reason=%s perrow=%s" % (a2.get("ok"), a2.get("reason"), perrow(a2)))
check("U1 还原后结构审计通过", a2.get("ok") is True, str(a2.get("reason")))
check("U1 还原后每行都是 4 格（3 行 × 4 列）", perrow(a2) == [4, 4, 4], str(perrow(a2)))
check("U1 还原后无残留合并格", merges(a2) == [], str(merges(a2)))
raw2 = a2.get("raw") or ""
check("U1 还原后总格数 = 12", raw2.count("<td") + raw2.count("<th") >= 12,
      "td=%d th=%d" % (raw2.count("<td"), raw2.count("<th")))
check("U1 还原后正文行为 td（不是整表 th）", raw2.count("<td") >= 8,
      "td=%d th=%d" % (raw2.count("<td"), raw2.count("<th")))
log("  U1 raw=%s" % raw2.replace("\n", " ")[:300])
# 存储往返
setmd(raw2)
sel(0, 0, 0, 3)
a2b = jj(AUDIT)
check("U1 往返后结构仍正确", a2b.get("ok") is True and perrow(a2b) == [4, 4, 4],
      "%s %s" % (a2b.get("reason"), perrow(a2b)))
log("CASE U1 end")

# ============ U2: 子区域 2×2 合并 → 还原 ============
log("CASE U2 begin")
setmd(T34)
sel(1, 1, 2, 2)                    # 正文 2 行 × 2 列
do("merge")
a3 = jj(AUDIT)
check("U2 合并为 2×2", merges(a3) == [(1, 1, 2, 2)], str(merges(a3)))
sel(1, 1, 1, 1)
do("unmerge")
a4 = jj(AUDIT)
check("U2 还原后结构审计通过", a4.get("ok") is True, str(a4.get("reason")))
check("U2 还原后每行 4 格", perrow(a4) == [4, 4, 4], str(perrow(a4)))
check("U2 还原后无残留合并", merges(a4) == [], str(merges(a4)))
log("CASE U2 end")

# ============ U3: 单行 2 列合并（cs=2, rs=1）→ 还原 ============
log("CASE U3 begin")
setmd(T34)
sel(0, 1, 0, 2)
do("merge")
a5 = jj(AUDIT)
check("U3 合并为 1×2", merges(a5) == [(0, 1, 1, 2)], str(merges(a5)))
sel(0, 1, 0, 1)
do("unmerge")
a6 = jj(AUDIT)
check("U3 还原后结构审计通过", a6.get("ok") is True, str(a6.get("reason")))
check("U3 还原后每行 4 格", perrow(a6) == [4, 4, 4], str(perrow(a6)))
log("CASE U3 end")

# ============ U4: 连续「合并 → 还原」三轮不留痕迹 ============
log("CASE U4 begin")
setmd(T34)
bad = []
for i in range(3):
    sel(0, 0, 2, 3)
    do("merge")
    au1 = jj(AUDIT)
    sel(0, 0, 0, 0)
    do("unmerge")
    au2 = jj(AUDIT)
    if au2.get("ok") is not True or perrow(au2) != [4, 4, 4] or merges(au2):
        bad.append("round%d ok=%s perrow=%s merges=%s" %
                   (i, au2.get("ok"), perrow(au2), merges(au2)))
    log("  U4 round%d perrow=%s merges=%s" % (i, perrow(au2), merges(au2)))
check("U4 三轮合并/还原均恢复 3×4", not bad, ";".join(bad) if bad else "ok")
log("CASE U4 end")

log("SUMMARY TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
os._exit(0)
