# -*- coding: utf-8 -*-
"""m59 诊断：复现 m57 S1 序列，逐步记录 js 返回值。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m59.txt")
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
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


wait(3000)
r = js("!!window.setMarkdown && !!window.cmd && !!window.__raw")
log(f"A ready={r!r}")
r = js("window.cmd('math')")
log(f"B cmd={r!r}")
wait(500)
r = js("(function(){var ta=document.querySelector('.math-src');"
       "if(!ta)return 'nota';"
       "ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
       "return 'esc';})()")
log(f"C esc-dispatch={r!r}")
wait(500)
r = js("(function(){var mb=document.querySelector('#editor .mathblock');"
       "if(!mb)return {};"
       "return {empty:mb.classList.contains('math-empty'),"
       "txt:mb.textContent,h:mb.offsetHeight};})()")
log(f"D mb-query={r!r}")
# 复现 m57 的 setmd("前文 $x^{2}+1$ 后文") + inlinemath mousedown
r = js("window.setMarkdown(" + json.dumps("前文 $x^{2}+1$ 后文") + ")")
log(f"E setmd={r!r}")
wait(700)
r = js("document.querySelectorAll('#editor .inlinemath').length")
log(f"F im-count={r!r}")
r = js("(function(){var im=document.querySelector('#editor .inlinemath');"
       "if(!im)return {hit:'noim'};"
       "var rc=im.getBoundingClientRect();"
       "im.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
       "clientX:rc.left+2,clientY:rc.top+rc.height/2}));"
       "return {hit:'ok'};})()")
log(f"G im-mousedown={r!r}")
wait(500)
r = js("(function(){var el=document.querySelector('#editor .raw-edit');"
       "if(!el)return {edit:false};"
       "var s=getSelection();var off=-1;"
       "if(s.rangeCount>0&&s.anchorNode&&s.anchorNode.nodeType===3)"
       "off=s.anchorOffset;"
       "var txt=el.textContent;var dl=txt.indexOf('$');"
       "return {edit:true,txt:txt,off:off,dollar:dl};})()")
log(f"H rawedit={r!r}")
log("DONE")
