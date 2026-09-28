# -*- coding: utf-8 -*-
"""m56 调试探针：多行合并为何未生效（对照单行合并）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m56.txt")
out = []


def log(s):
    out.append(str(s)); flush()


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

MD_P = ("| A1 | B1 | C1 | D1 |\n| --- | --- | --- | --- |\n"
        "| A2 | B2 | C2 | D2 |\n| A3 | B3 | C3 | D3 |")


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(700)


def spans():
    return js("(function(){var t=document.querySelector('.b-table table');"
              "if(!t)return 'notable';var a=[];var all=t.querySelectorAll('td,th');"
              "for(var q=0;q<all.length;q++){var cs=all[q].colspan||1,rs=all[q].rowspan||1;"
              "if(cs>1||rs>1)a.push(cs+'x'+rs);}return JSON.stringify(a)})()")


# 对照组：单行两格合并（m53 同款，应成功）
setmd(MD_P)
js("window.__tblSelSet(0,1,1,1,2)"); wait(200)
log("ctrl sel=" + str(js("window.__tblSel()")))
js("window.__tblOp('merge')"); wait(700)
log("ctrl merge spans=" + str(spans()))
log("ctrl raw0=" + str(js("(function(){var d=JSON.parse(window.__raw());return JSON.stringify(d.raw[0])})()"))[:150])

# 实验组 1：2x2
setmd(MD_P)
js("window.__tblSelSet(0,1,1,2,2)"); wait(200)
log("e1 sel=" + str(js("window.__tblSel()")))
js("window.__tblOp('merge')"); wait(700)
log("e1 merge spans=" + str(spans()))
log("e1 raw0=" + str(js("(function(){var d=JSON.parse(window.__raw());return JSON.stringify(d.raw[0])})()"))[:150])

# 实验组 2：2x1（两行一列）
setmd(MD_P)
js("window.__tblSelSet(0,1,1,2,1)"); wait(200)
log("e2 sel=" + str(js("window.__tblSel()")))
js("window.__tblOp('merge')"); wait(700)
log("e2 merge spans=" + str(spans()))
log("e2 raw0=" + str(js("(function(){var d=JSON.parse(window.__raw());return JSON.stringify(d.raw[0])})()"))[:150])

# 实验组 3：单行三格 (1,1)-(1,3)（用户报告场景的最小复现，正文行）
setmd(MD_P)
js("window.__tblSelSet(0,1,1,1,3)"); wait(200)
log("e3 sel=" + str(js("window.__tblSel()")))
js("window.__tblOp('merge')"); wait(700)
log("e3 merge spans=" + str(spans()))
log("e3 raw0=" + str(js("(function(){var d=JSON.parse(window.__raw());return JSON.stringify(d.raw[0])})()"))[:200])

flush()
