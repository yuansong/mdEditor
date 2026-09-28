# -*- coding: utf-8 -*-
"""v3.29 诊断 4：smoke19 网格面板 Enter 失效定位。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29g.txt")
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


def state(tag):
    d = js("(function(){var sm=document.getElementById('slashmenu');"
           "var sub=document.getElementById('submenu');"
           "var ts=document.getElementById('tblsize');"
           "var act=sm.querySelector('.si.act');"
           "return JSON.stringify({sm:sm.classList.contains('show'),"
           "sub:sub.classList.contains('show'),"
           "ts:ts.classList.contains('show'),"
           "act:act?act.textContent.slice(0,12):null,"
           "raw:(window.__raw().raw||[]).join('\\\\n').slice(0,40)})})()")
    note(tag, str(d))


wait(2500)
js("window.setMarkdown('')")
wait(400)
r = js("window.openBlockMenu()")
note("openBlockMenu", str(r))
wait(300)
state("after open")

js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));return 1})()")
wait(150)
state("after Esc")

js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));return 1})()")
wait(150)
state("after Down1")
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));return 1})()")
wait(150)
state("after Down2")

js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 1})()")
wait(300)
state("after Enter")

out.append("DONE")
flush()
print("done")
