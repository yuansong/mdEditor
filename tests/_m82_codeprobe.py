# -*- coding: utf-8 -*-
"""m82 最小验证：行内代码承载叠加标记后，渲染明文是否把标记当字面文本

假设：`` `~~内容~~` `` 按 Markdown 规范，整段渲染为一个 <code>，
      其中的 ~~ 不解析为删除线，而是作为字面字符出现在「渲染明文」里。
      若成立 → 后续基于渲染明文偏移的选区映射整体错位（链接只包部分文字）。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m82.txt")
out = []


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


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
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


wait(2500)
Q = "> 引用块内的文字内容"


def setmd(md, ms=780):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    r = jj("window.__raw()")
    return r.get("raw", [""]) if isinstance(r, dict) else [""]


def plain():
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
           "if(!b)return JSON.stringify({err:1});"
           "return JSON.stringify({t:b.textContent||'',len:(b.textContent||'').length,"
           "code:!!b.querySelector('code'),del:!!b.querySelector('del,s'),"
           "html:(b.innerHTML||'').substring(0,300)})})()")
    return r


def sel(a, b, ms=240):
    js("(function(){var blk=document.querySelectorAll('#editor .blk')[0];"
       "var w=document.createTreeWalker(blk,NodeFilter.SHOW_TEXT);"
       "var pos=0,sn=null,so=0,en=null,eo=0,n;"
       "while(n=w.nextNode()){var L=n.nodeValue.length;"
       "if(sn===null&&pos+L>=" + str(a) + "){sn=n;so=" + str(a) + "-pos;}"
       "if(pos+L>=" + str(b) + "){en=n;eo=" + str(b) + "-pos;break;}"
       "pos+=L;}"
       "var rg=document.createRange();rg.setStart(sn,so);rg.setEnd(en,eo);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def act(a, ms=330):
    js("window.__applyFloat(" + json.dumps(a) + ")")
    wait(ms)


def link(url="https://ex.com/doc", ms=330):
    js("window.__applyFloat('link')")
    wait(ms)
    js("(function(){var i=document.getElementById('link-url');if(!i)return 'no-input';"
       "i.value=" + json.dumps(url) + ";var b=document.getElementById('link-ok');"
       "if(!b)return 'no-btn';b.click();return 'ok'})()")
    wait(ms + 100)


log("原始内容 = " + Q)
setmd(Q)
p = plain()
log("① 初始       渲染明文=%s  长度=%s  code=%s del=%s" % (
    json.dumps(p.get("t"), ensure_ascii=False), p.get("len"), p.get("code"), p.get("del")))
log("   html=%s" % json.dumps(p.get("html"), ensure_ascii=False))

sel(0, 9)
act("code")
p = plain()
log("② 加行内码后 渲染明文=%s  长度=%s  code=%s del=%s" % (
    json.dumps(p.get("t"), ensure_ascii=False), p.get("len"), p.get("code"), p.get("del")))
log("   raw=%s" % json.dumps(getraw(), ensure_ascii=False))

sel(0, 9)
act("strike")
p = plain()
log("③ 加删除线后 渲染明文=%s  长度=%s  code=%s del=%s" % (
    json.dumps(p.get("t"), ensure_ascii=False), p.get("len"), p.get("code"), p.get("del")))
log("   html=%s" % json.dumps(p.get("html"), ensure_ascii=False))
log("   raw=%s" % json.dumps(getraw(), ensure_ascii=False))
log("   >>> 关键：若 len != 9，说明渲染明文已包含字面标记字符")

sel(0, 9)
link()
log("④ 加链接后   raw=%s" % json.dumps(getraw(), ensure_ascii=False))

# 对照：干净状态直接加链接
setmd(Q)
sel(0, 9)
link()
log("⑤ 对照（干净直接加链接） raw=%s" % json.dumps(getraw(), ensure_ascii=False))

# 对照：先加删除线（不含行内码）再加链接
setmd(Q)
sel(0, 9)
act("strike")
p = plain()
log("⑥ 先删除线（无行内码） 渲染明文=%s 长度=%s code=%s del=%s" % (
    json.dumps(p.get("t"), ensure_ascii=False), p.get("len"), p.get("code"), p.get("del")))
sel(0, 9)
link()
log("⑦ 删除线后加链接 raw=%s" % json.dumps(getraw(), ensure_ascii=False))

print("done")
