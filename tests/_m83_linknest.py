# -*- coding: utf-8 -*-
"""m83：已有链接上再叠加行内格式（标题 / 列表项 / 引用 三容器）

背景：_m71 S3 观察到「先链接再高亮」产生 ==[==x==](url)== ，
      渲染回字面源码。本探针系统验证 5 种格式 × 3 容器。
正确预期：标记应落在链接文字内部 —— [==文字==](url) / [**文字**](url)
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m83.txt")
out = []
FAIL = [0]
TOTAL = [0]
URL = "https://x.com/demo"


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


def rawdump(tag):
    r = jj("window.__raw()")
    note("%s raw=%s" % (tag, json.dumps(r.get("raw"), ensure_ascii=False)))
    return r


def htmldump(idx, tag):
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return JSON.stringify({err:'noblk'});"
           "return JSON.stringify({html:b.innerHTML.substring(0,500),"
           "text:(b.textContent||'').replace(/\\n/g,' ')})})()")
    note("%s text=%s" % (tag, json.dumps(r.get("text"), ensure_ascii=False)))
    return r


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


def link_ok(url, ms=400):
    js("(function(){var i=document.getElementById('link-url');"
       "if(!i)return 'no-input';i.value=" + json.dumps(url) + ";"
       "var b=document.getElementById('link-ok');"
       "if(!b)return 'no-btn';b.click();return 'ok'})()")
    wait(ms)


wait(2500)

# 容器：(名称, 初始 md, 块内选区选择器, 裸文本)
CASES = [
    ("引用", "> 引用块内的文字内容", "#editor .blk blockquote", "引用块内的文字内容"),
    ("标题", "# 演示标题内容文字", "#editor .blk h1", "演示标题内容文字"),
    ("列表", "- 第一项内容文本", "#editor .blk li", "第一项内容文本"),
]
# 格式：(动作, 左标记, 右标记)
FMTS = [
    ("mark", "==", "=="),
    ("bold", "**", "**"),
    ("italic", "*", "*"),
    ("strike", "~~", "~~"),
    ("code", "`", "`"),
]

note("========== 先加链接 → 再叠加行内格式 ==========")
for cname, md, sel, plain in CASES:
    note("--- 容器：%s ---" % cname)
    for act, L, R in FMTS:
        setmd(md)
        # 1) 先加链接
        sel_in(sel)
        fmt("link")
        link_ok(URL)
        r1 = jj("window.__raw()")
        linked = (r1.get("raw") or [""])[0]
        ok_link = linked == "%s[%s](%s)" % (
            md.split(" ")[0] + " " if not md.startswith("#") else "# ", plain, URL)
        # 2) 再叠加格式（渲染态选区仍选整块内容）
        sel_in(sel)
        fmt(act)
        r2 = jj("window.__raw()")
        after = (r2.get("raw") or [""])[0]
        h = htmldump(0, "  %s/%s 渲染" % (cname, act))
        text = h.get("text") or ""
        # 判定：标记应在链接文字内部，且渲染文本不得含字面标记
        want = "%s[%s%s%s](%s)" % (md[:md.index(" ")] + " ", L, plain, R, URL)
        literal = (L * 2 in text) or ("[" in text) or ("](http" in text)
        check("%s/%s 叠加后标记在链接内" % (cname, act), after == want,
              "实际=%s  预期=%s" % (json.dumps(after, ensure_ascii=False),
                                 json.dumps(want, ensure_ascii=False)))
        check("%s/%s 渲染无字面标记" % (cname, act), not literal,
              "text=%s" % json.dumps(text, ensure_ascii=False))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
