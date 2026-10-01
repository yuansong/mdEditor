# -*- coding: utf-8 -*-
"""m101b 启动诊断：页面钩子存活状态检查"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()

loop = QEventLoop()
QTimer.singleShot(2500, loop.quit)
loop.exec()


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


r = js("JSON.stringify({sm:typeof window.setMarkdown,raw:typeof window.__raw,"
       "gm:typeof window.getMarkdown,ed:!!document.getElementById('editor'),"
       "blkN:document.querySelectorAll('#editor .blk').length,"
       "ver:(window.APP_VERSION||window.__APP_VERSION||'')})")
print("HOOKS:", r)

# 捕获启动错误：注入 error 收集后再手动触发一次关键初始化检查
r2 = js("(function(){try{return JSON.stringify({snap:typeof window.snapshotNow,"
        "state:typeof state,ed:typeof ED,rebuild:typeof rebuild})}catch(e){"
        "return JSON.stringify({err:String(e)})}})()")
print("CTX:", r2)
print("DONE")
