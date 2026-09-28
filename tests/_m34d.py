# -*- coding: utf-8 -*-
"""诊断：捕获 editor.html 初始化错误（当前并发修改后的 src 状态）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m34d.txt")
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


wait(3000)
d1 = js("(function(){return JSON.stringify({"
        "hasSetMd: typeof window.setMarkdown,"
        "hasCmd: typeof window.cmd,"
        "jsErr: window.__jsErrors || null,"
        "edChildren: document.querySelectorAll('#editor .blk').length"
        "})})()")
out.append("STATE: " + str(d1))
flush()
# 尝试重新加载页面并捕获错误事件
d2 = js("(function(){window.__errs=[];window.addEventListener('error',function(e){"
        "window.__errs.push((e.message||'')+' @ '+(e.filename||'')+':'+(e.lineno||0)+':'+(e.colno||0));});"
        "location.reload();return 'reloading'})()")
wait(4000)
d3 = js("(function(){return JSON.stringify({errs:window.__errs||null,"
        "hasSetMd: typeof window.setMarkdown})})()")
out.append("RELOAD: " + str(d3))
out.append("DONE")
flush()
print("done")
