# -*- coding: utf-8 -*-
"""m92：strike → bold → strike（取消）在 4 种块型上的对照
判定 m90/D1 step24 是引用块专属还是通用缺陷。
正确预期：第二次 strike 应移除 ~~ 得到 **文字**
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m92.txt")
out = []
TOTAL = [0]
FAIL = [0]


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


def setdoc(lines, ms=800):
    js("window.setMarkdown(" + json.dumps("\n\n".join(lines)) + ")")
    wait(ms)


def getraw():
    return jj("window.__raw()").get("raw") or []


def sel_in(blk, sel, ms=250):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(blk) + "];"
       "if(!b)return 'no-blk';var el=b.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def fmt(act, ms=330):
    js("window.__applyFloat(" + json.dumps(act) + ")")
    wait(ms)


def blk_dump(idx):
    return jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
              "if(!b)return JSON.stringify({err:'noblk'});"
              "return JSON.stringify({text:(b.textContent||''),"
              "html:b.innerHTML.substring(0,300)})})()")


wait(2500)

T = "中文测试文本内容"
CASES = [
    ("正文段落", T, 0, "p"),
    ("标题", "# " + T, 0, "h1"),
    ("列表项", "- " + T, 0, "li"),
    ("引用", "> " + T, 0, "blockquote"),
]

note("========== strike → bold → strike(取消) ==========")
for name, md, idx, sel in CASES:
    setdoc(["前置段落", md])
    bi = 1
    sel_in(bi, sel); fmt("strike")
    r1 = getraw()[bi]
    sel_in(bi, sel); fmt("bold")
    r2 = getraw()[bi]
    sel_in(bi, sel); fmt("strike")
    r3 = getraw()[bi]
    d = blk_dump(bi)
    t = d.get("text") or ""
    # 期望：前缀 + **文字**（~~ 已取消）
    body3 = r3
    for pre in ["# ", "- ", "> "]:
        if body3.startswith(pre):
            body3 = body3[len(pre):]
            break
    want = "**" + T + "**"
    check("%s：二次 strike 取消后仅剩加粗" % name, body3 == want,
          "1st=%s 2nd=%s 3rd=%s 预期=%s" % (r1, r2, r3, want))
    check("%s：渲染无裸标记" % name, "**" not in t and "~~" not in t,
          "text=%s html=%s" % (json.dumps(t, ensure_ascii=False),
                               json.dumps(d.get("html", ""), ensure_ascii=False)))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
