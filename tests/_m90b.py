# -*- coding: utf-8 -*-
"""m90b：G2 拆分结果完整 dump"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m90b.txt")
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

wait(2500)
MD = "| a | b | c |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |"
js("window.setMarkdown(" + json.dumps(MD, ensure_ascii=False) + ")")
wait(700)
log("sel=" + str(js("window.__tblSelSet(0, 1, 0, 2, 2)")))
wait(200)
js("window.__tblOp('merge')")
wait(300)
log("after merge raw=" + json.dumps(json.loads(js("window.__raw()"))["raw"], ensure_ascii=False))
js("window.__tblOp('splitInto', [3, 4])")
wait(400)
log("after split raw=\n" + json.loads(js("window.__raw()"))["raw"][0])
log("DONE")
print("DONE")
