# -*- coding: utf-8 -*-
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m49b.txt")
out = []
def log(s): out.append(str(s)); flush()
def flush():
    with open(LOG, "w", encoding="utf-8") as f: f.write("\n".join(out))
app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow(); win.show()
def js(code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]
def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()
wait(2500)
MD1 = "> | A | B |\n> | --- | --- |\n> | 1 | 2 |"
MD2 = ("> <table class=\"md-tbl\"><thead><tr><th>A</th><th>B</th></tr></thead>"
       "<tbody><tr><td rowspan=\"2\">1</td><td>2</td></tr><tr><td>4</td></tr></tbody></table>")
js("window.setMarkdown(%s)" % json.dumps(MD1)); wait(700)
log("Q1 html=" + str(js("document.querySelector('#editor').innerHTML.slice(0,600)")))
log("Q1 raw=" + str(js("JSON.stringify(window.__raw&&window.__raw())")[:400]))
js("window.setMarkdown(%s)" % json.dumps(MD2)); wait(700)
log("Q2 html=" + str(js("document.querySelector('#editor').innerHTML.slice(0,600)")))
log("Q2 raw=" + str(js("JSON.stringify(window.__raw&&window.__raw())")[:400]))
log("DONE")
flush()
