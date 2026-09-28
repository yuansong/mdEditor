# -*- coding: utf-8 -*-
"""v3.29 诊断 3：引用 Enter#1 现场精查。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29f.txt")
out = []


def note(tag, extra):
    out.append(f"NOTE | {tag} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def jj(code):
    r = js(code)
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


wait(2500)

Q1 = "> 第一行内容\n> 第二行内容"
js(f"window.setMarkdown({json.dumps(Q1)})")
wait(700)

d = jj("(function(){var bq=document.querySelector('#editor blockquote');"
       "return JSON.stringify({tc:JSON.stringify(bq.textContent),"
       "html:bq.innerHTML,nodes:[].map.call(bq.childNodes,function(n){"
       "return n.nodeType===3?('t:'+JSON.stringify(n.nodeValue)):('e:'+n.tagName)})})})()")
note("A 初始 DOM", str(d))
note("A raw", str(raw()))

# 复刻 caretRawOffset 口径
d = jj("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
       "var sel=getSelection();var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
       "sel.removeAllRanges();sel.addRange(rg);"
       "var r2=sel.getRangeAt(0);var rr=r2.cloneRange();rr.selectNodeContents(bq);"
       "rr.setEnd(r2.endContainer,r2.endOffset);"
       "return JSON.stringify({off:rr.toString().length,tcLen:bq.textContent.length})})()")
note("B off 复刻", str(d))

d = jj("(function(){try{document.querySelector('#editor blockquote')"
       ".dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
       "return 'ok'}catch(e){return String(e)}})()")
note("C Enter#1 dispatch", str(d))
wait(600)
note("C raw after", str(raw()))
d = jj("(function(){var bq=document.querySelector('#editor blockquote');"
       "return JSON.stringify({tc:JSON.stringify(bq.textContent),inEdit:!!document.querySelector('#editor .raw-edit')})})()")
note("C DOM after", str(d))

out.append("DONE")
flush()
print("done")
