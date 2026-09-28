# -*- coding: utf-8 -*-
"""一次性诊断：scroll 派发与对象选中态。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m36.txt")
out = []


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


wait(2500)
js("window.setMarkdown('![图](x.png)')"); wait(800)
out.append("step1: " + str(js("(function(){var img=document.querySelector('#editor img');"
                              "img.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
                              "return 'ok'})()"))); flush()
wait(300)
out.append("sel: " + str(js("window.__objSel()"))); flush()
r = js("(function(){var ed=document.getElementById('editor');var n=0;"
       "function h(){n++;}"
       "var errs=[];window.onerror=function(m){errs.push(String(m));return false;};"
       "ed.addEventListener('scroll',h,false);"
       "try{ed.dispatchEvent(new Event('scroll'));}catch(e){return 'ERR:'+e.message;}"
       "return JSON.stringify({fired:n, sel:window.__objSel(), errs:errs,"
       " imgSel:(function(){var i=document.querySelector('#editor img');return i?i.classList.contains('sel'):null})()})})()")
out.append("scroll diag: " + str(r)); flush()
wait(200)
out.append("sel after: " + str(js("window.__objSel()"))); flush()
# 对照：Escape 走同一条 hideObjSel 链路
r = js("(function(){var errs=[];window.onerror=function(m){errs.push(String(m));return false;};"
       "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
       "return JSON.stringify({sel:window.__objSel(),errs:errs})})()")
out.append("after Escape: " + str(r)); flush()
out.append("DONE"); flush()
print("done")
