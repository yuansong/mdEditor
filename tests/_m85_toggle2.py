# -*- coding: utf-8 -*-
"""m85：m84-B 场景扩展到 bold / italic / strike / code —— 是否同源
顺序：格式 → 链接 → 再点同一格式（预期取消该格式，保留链接）
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m85.txt")
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
FMTS = [("bold", "**"), ("italic", "*"), ("strike", "~~"), ("code", "`")]

note("========== 格式 → 链接 → 再点同格式（应取消） ==========")
for act, M in FMTS:
    for cname, md, sel, plain in CASES:
        setmd(md)
        sel_in(sel); fmt(act)
        s1 = getraw()
        sel_in(sel); fmt("link"); link_ok(URL)
        s2 = getraw()
        sel_in(sel); fmt(act)
        s3 = getraw()
        t3 = text_of(0)
        pre = md[:md.index(" ")] + " "
        if act == "code":
            # v3.31.2（FMT-1 守卫）：行内代码内不支持叠加链接 → 第 2 步 raw 保持不变；
            # 第 3 步再点行内码 = toggle 取消码壳 → 回到裸文字（无链接）
            want2, want3 = s1, pre + plain
        else:
            want2 = "%s%s[%s](%s)%s" % (pre, M, plain, URL, M)
            want3 = "%s[%s](%s)" % (pre, plain, URL)
        check("%s/%s 第2步加链接" % (act, cname), s2 == want2,
              "1st=%s 2nd=%s 预期2nd=%s" % (s1, s2, want2))
        check("%s/%s 二次点击应取消格式" % (act, cname), s3 == want3,
              "1st=%s 2nd=%s 3rd=%s 预期=%s" % (s1, s2, s3, want3))
        check("%s/%s 渲染无字面标记" % (act, cname),
              (M * 2 not in t3) and ("[" not in t3),
              "text=%s" % json.dumps(t3, ensure_ascii=False))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
