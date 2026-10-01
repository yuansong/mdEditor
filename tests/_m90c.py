# -*- coding: utf-8 -*-
"""m90c：imgalign 直调链路诊断"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m90c.txt")
out = []
def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))

app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()

def js(code, ms=15000):
    loop = QEventLoop()
    box = {"r": None}
    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(ms, loop.quit)
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

wait(2500)
js("window.setMarkdown('![图](x.png)')")
wait(700)
log("raw0=" + json.dumps(jj("window.__raw()")["raw"], ensure_ascii=False))
# 直接调 applyBlockAct（走 handleIdx：先模拟选中）
r = js("(function(){try{var img=document.querySelector('#editor img');"
       "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:200}));"
       "var st=window.__blkMenuState();"
       "var mi=document.querySelector('#blkmenu .mi[data-act=imgalign\\\\:l]');"
       "return JSON.stringify({acts:st?st.acts:null, hasItem:!!mi})}catch(e){return 'ERR:'+e.message}})()")
log("menu=" + str(r))
wait(300)
r = js("(function(){try{var mi=document.querySelector('#blkmenu .mi[data-act=\"imgalign:l\"]');"
       "if(!mi)return 'NOITEM';"
       "mi.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "return 'clicked'}catch(e){return 'ERR:'+e.message}})()")
log("click=" + str(r))
wait(500)
log("raw1=" + json.dumps(jj("window.__raw()")["raw"], ensure_ascii=False))
# 直调 applyBlockAct（绕过菜单）
r = js("(function(){try{window.__applyBlockAct('imgalign:l', 0);return 'ok'}catch(e){return 'ERR:'+e.message}})()")
log("direct=" + str(r))
wait(500)
log("raw2=" + json.dumps(jj("window.__raw()")["raw"], ensure_ascii=False))
log("DONE")
print("DONE")
