# -*- coding: utf-8 -*-
"""m86：粗体/斜体 LIFO 取消（标题1 / 列表 / 引用 / 段落 四容器）

复现（用户实测）：标题1 内容 → 加粗 → 斜体 → 再斜体，第二次斜体不取消
而是再套一层（`***C***` → `****C****`，界面显示字面 `*`）。

新语义（v3.31.2）：按 CommonMark 强调「游程」判定当前是否已含该格式 ——
  mlen=1（斜体 / 行内码）：两侧游程为奇数（1 或 3）→ 已含 → 取消（删 1）
  mlen=2（粗体 / 删除线 / 高亮）：两侧游程 ≥ 2 → 已含 → 取消（删 2）
序列：
  S1 B→I→I  期望 **C**（取消斜体，留粗体）
  S2 I→B→B  期望 *C*（取消粗体，留斜体）
  S3 B→I→B  期望 *C*
  S4 I→B→I  期望 **C**
  S5 B→B    期望 C      S6 I→I 期望 C
  S7 S→S    期望 C      S8 MK→MK 期望 C     S9 CODE→CODE 期望 C
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m86_bi.txt")
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


def note(s):
    log("NOTE %s" % s)


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
        return json.loads(js(code) or "{}")
    except Exception:
        return {"_raw": js(code)}


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    return (jj("window.__raw()").get("raw") or [""])[0]


def sel_in(sel, ms=280):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def fmt(act, ms=400):
    js("window.__applyFloat(" + json.dumps(act) + ")")
    wait(ms)


def text_of(idx=0):
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return JSON.stringify({text:''});"
           "return JSON.stringify({text:(b.textContent||'').replace(/\\n/g,' ')})})()")
    return r.get("text") or ""


wait(2500)

CASES = [
    ("标题1", "# 演示标题内容文字", "#editor .blk h1", "演示标题内容文字"),
    ("列表", "- 第一项内容文本", "#editor .blk li", "第一项内容文本"),
    ("引用", "> 引用块内的文字内容", "#editor .blk blockquote", "引用块内的文字内容"),
    ("段落", "段落内容文字示例", "#editor .blk p", "段落内容文字示例"),
]

SEQS = [
    ("S1 B→I→I", [("bold", "**{C}**"), ("italic", "***{C}***"), ("italic", "**{C}**")]),
    ("S2 I→B→B", [("italic", "*{C}*"), ("bold", "***{C}***"), ("bold", "*{C}*")]),
    ("S3 B→I→B", [("bold", "**{C}**"), ("italic", "***{C}***"), ("bold", "*{C}*")]),
    ("S4 I→B→I", [("italic", "*{C}*"), ("bold", "***{C}***"), ("italic", "**{C}**")]),
    ("S5 B→B", [("bold", "**{C}**"), ("bold", "{C}")]),
    ("S6 I→I", [("italic", "*{C}*"), ("italic", "{C}")]),
    ("S7 S→S", [("strike", "~~{C}~~"), ("strike", "{C}")]),
    ("S8 MK→MK", [("mark", "=={C}=="), ("mark", "{C}")]),
    ("S9 CODE→CODE", [("code", "`{C}`"), ("code", "{C}")]),
]

for cname, md, sel, plain in CASES:
    pre = md[:md.index(" ")] + " " if " " in md else ""
    note("========== %s ==========" % cname)
    for sname, steps in SEQS:
        setmd(md)
        got = []
        bad = []
        for act, want_tpl in steps:
            sel_in(sel)
            fmt(act)
            r = getraw()
            got.append(r)
            t = text_of(0)
            want = pre + want_tpl.replace("{C}", plain)
            check("%s/%s %s" % (cname, sname, act), r == want,
                  "实际=%s 预期=%s" % (r, want))
            leak = [m for m in ("*", "~~", "==", "`") if m in t]
            if leak:
                bad.append("%s(leak=%s)" % (t, ",".join(leak)))
        check("%s/%s 渲染无字面标记" % (cname, sname), not bad, " ".join(bad))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
