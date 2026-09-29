# -*- coding: utf-8 -*-
"""m84：含链接内容上的行内格式 toggle（取消）判定

_m71 S3 观察到：已高亮且已链接的内容上再点高亮 → 变成嵌套 ==[==x==](url)==
                 而非取消高亮。本探针在标题 / 列表 / 引用 三容器验证两种顺序：
  A) 链接 → 高亮 → 再高亮（第二次应取消，回到 [x](url)）
  B) 高亮 → 链接 → 再高亮（第二次应取消，回到 [x](url)，即 S3 场景）
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m84.txt")
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


def link_ok(url, ms=400):
    js("(function(){var i=document.getElementById('link-url');"
       "if(!i)return 'no-input';i.value=" + json.dumps(url) + ";"
       "var b=document.getElementById('link-ok');"
       "if(!b)return 'no-btn';b.click();return 'ok'})()")
    wait(ms)


def text_of(idx=0):
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return JSON.stringify({text:''});"
           "return JSON.stringify({text:(b.textContent||'').replace(/\\n/g,' ')})})()")
    return r.get("text") or ""


wait(2500)

CASES = [
    ("引用", "> 引用块内的文字内容", "#editor .blk blockquote", "引用块内的文字内容"),
    ("标题", "# 演示标题内容文字", "#editor .blk h1", "演示标题内容文字"),
    ("列表", "- 第一项内容文本", "#editor .blk li", "第一项内容文本"),
]

note("========== A) 链接 → 高亮 → 再高亮（应取消） ==========")
for cname, md, sel, plain in CASES:
    setmd(md)
    sel_in(sel); fmt("link"); link_ok(URL)
    a1 = getraw()
    sel_in(sel); fmt("mark")
    a2 = getraw()
    sel_in(sel); fmt("mark")
    a3 = getraw()
    t3 = text_of(0)
    want = "%s[%s](%s)" % (md[:md.index(" ")] + " ", plain, URL)
    check("A/%s 二次高亮应取消（回到纯链接）" % cname, a3 == want,
          "1st=%s 2nd=%s 3rd=%s 预期=%s" % (a1, a2, a3, want))
    check("A/%s 渲染无字面标记" % cname, "==" not in t3 and "[" not in t3,
          "text=%s" % json.dumps(t3, ensure_ascii=False))

note("========== B) 高亮 → 链接 → 再高亮（应取消，S3 场景） ==========")
for cname, md, sel, plain in CASES:
    setmd(md)
    sel_in(sel); fmt("mark")
    b1 = getraw()
    sel_in(sel); fmt("link"); link_ok(URL)
    b2 = getraw()
    sel_in(sel); fmt("mark")
    b3 = getraw()
    t3 = text_of(0)
    want = "%s[%s](%s)" % (md[:md.index(" ")] + " ", plain, URL)
    check("B/%s 二次高亮应取消（回到纯链接）" % cname, b3 == want,
          "1st=%s 2nd=%s 3rd=%s 预期=%s" % (b1, b2, b3, want))
    check("B/%s 渲染无字面标记" % cname, "==" not in t3 and "[" not in t3,
          "text=%s" % json.dumps(t3, ensure_ascii=False))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
