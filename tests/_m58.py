# -*- coding: utf-8 -*-
"""m58 诊断：cmd('math') 之后 js 通道为何全部返回 None。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m58.txt")
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
    loop = QEventLoop(); box = {"r": None, "done": False}
    def cb(res): box["r"] = res; box["done"] = True; loop.quit()
    QTimer.singleShot(8000, loop.quit)
    win._js_active(code, cb); loop.exec()
    return box["r"], box["done"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


wait(3000)
r, ok = js("!!window.setMarkdown && !!window.cmd")
log(f"A ready={r} done={ok}")
r, ok = js("document.querySelectorAll('#editor .blk').length")
log(f"B blkcount={r} done={ok}")
r, ok = js("window.cmd('math')")
log(f"C cmd-math={r!r} done={ok}")
r, ok = js("document.querySelectorAll('#editor .blk').length")
log(f"D blkcount-after={r!r} done={ok}")
r, ok = js("(function(){return 'alive';})()")
log(f"E alive={r!r} done={ok}")
r, ok = js("var mb=document.querySelector('#editor .mathblock');"
           "mb?mb.outerHTML.slice(0,200):'nomb'")
log(f"F mb={r!r} done={ok}")
r, ok = js("!!document.querySelector('.math-src')")
log(f"G srcbox={r!r} done={ok}")
log("DONE")
