# -*- coding: utf-8 -*-
"""m101c 引用退出落点精查：双回车后块状态 / 末行退格拍平 / 中部标题字面 / 多行首行退格 / Shift+Tab"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m101c.txt")
out = []


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def note(s):
    log("NOTE %s" % s)


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code, timeout=15000):
    lp = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        lp.quit()
    QTimer.singleShot(timeout, lp.quit)
    win._js_active(code, cb)
    lp.exec()
    return box["r"]


def wait(ms):
    lp = QEventLoop()
    QTimer.singleShot(ms, lp.quit)
    lp.exec()


def setmd(md, ms=750):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def allblks():
    return js("(function(){var rw={};try{rw=JSON.parse(window.__raw()||'{}')}catch(e){}"
              "var bs=document.querySelectorAll('#editor .blk');var arr=[];"
              "for(var k=0;k<bs.length&&k<6;k++)arr.push({cls:bs[k].className,"
              "txt:(bs[k].textContent||'').slice(0,50)});"
              "return JSON.stringify({raw:rw.raw||[],editIdx:rw.editIdx,blks:arr,"
              "ae:document.activeElement?document.activeElement.tagName:''})})()")


def q_caret_end():
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(200)


def q_caret_start():
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var w=document.createTreeWalker(bq,NodeFilter.SHOW_TEXT,null);var n;"
       "while(n=w.nextNode()){if(n.closest&&n.closest('.qblk'))continue;"
       "if(n.nodeValue.length===0)continue;"
       "var rg=document.createRange();rg.setStart(n,0);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'}"
       "return 'no-text'})()")
    wait(200)


def key_on_quote(key, ms=430, shift=False):
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var ev=new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,shiftKey:" + ("true" if shift else "false") + "});"
       "bq.dispatchEvent(ev);return 'ok'})()")
    wait(ms)


wait(2800)
note("=== A2 精查：双回车后的块状态 ===")
setmd("> 引文甲行\n\n段落乙")
q_caret_end()
key_on_quote("Enter")
q_caret_end()
key_on_quote("Enter")
wait(300)
note("双回车后 allblks=%s" % allblks())

note("=== B2 精查：末尾空行退格后的 raw ===")
setmd("> 引文丙行\n>")
q_caret_end()
key_on_quote("Backspace")
wait(300)
note("末行空行退格后 allblks=%s" % allblks())

note("=== D2 精查：引用中部标题行的渲染形态 ===")
setmd("> 正文行\n> # 粘贴来的标题\n> 尾行")
wait(400)
note("中部标题 allblks=%s" % allblks())

note("=== F1 精查：多行引用首行行首退格 ===")
setmd("> 行一\n> 行二\n\n段落乙")
q_caret_start()
key_on_quote("Backspace")
wait(300)
note("多行首行退格后 allblks=%s" % allblks())

note("=== F2 精查：单行引用 Shift+Tab ===")
setmd("> 引文庚行\n\n段落乙")
q_caret_end()
key_on_quote("Tab", shift=True)
wait(300)
note("单行 Shift+Tab 后 allblks=%s" % allblks())

note("=== F3 精查：引用行中 Shift+Tab（嵌套降低） ===")
setmd(">> 深层甲\n\n段落乙")
q_caret_end()
key_on_quote("Tab", shift=True)
wait(300)
note("嵌套 Shift+Tab 后 allblks=%s" % allblks())

log("DONE")
print("DONE")
