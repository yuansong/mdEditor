# -*- coding: utf-8 -*-
"""m71b：钉死 S2 缺陷的最小触发条件——前面的列表项完全无格式时，
对第 2 项渲染态加格式是否仍然错位。"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m71b.txt")
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


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def rawdump(tag):
    r = js("window.__raw()")
    log("NOTE %s raw=%s" % (tag, r))
    return r


def sel_li(idx, li):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
       "if(!b)return 'no-blk';"
       "var li=b.querySelectorAll('li')[" + str(li) + "];if(!li)return 'no-li';"
       "var rg=document.createRange();rg.selectNodeContents(li);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(300)


def eqs(idx=0):
    r = js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return '[]';var t=b.textContent||'';var m=t.match(/={2,}/g);"
           "return JSON.stringify(m||[])})()")
    wait(250)
    return r


wait(2500)

# T1: 前项无格式（最常见场景）
setmd("- 第一项\n- 第二项")
sel_li(0, 1)
js("window.__applyFloat('mark')")
wait(400)
rawdump("T1 前项无格式 第2项高亮")
log("T1 eqs=" + eqs())

# T2: 三项列表，对第 3 项
setmd("- 一\n- 二\n- 三")
sel_li(0, 2)
js("window.__applyFloat('bold')")
wait(400)
rawdump("T2 三项列表 第3项加粗")

# T3: 引用块多行（同 lineWalker 路径）？引用行模型不同，验证一下
setmd("> 引用一行\n> 引用二行")
selq = js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
          "if(!b)return 'no-blk';var q=b.querySelector('blockquote');if(!q)return 'no-q';"
          "var rg=document.createRange();rg.selectNodeContents(q);rg.collapse(false);"
          "return 'ok'})()")
wait(300)
log("T3 selq=" + str(selq))
js("window.__applyFloat('mark')")
wait(400)
rawdump("T3 引用（对照）")

log("DONE")
