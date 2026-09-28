# -*- coding: utf-8 -*-
"""v3.29 诊断 5：smoke17 图片 __wantPick 失效定位。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29h.txt")
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


wait(2500)
js("window.setMarkdown('')")
wait(300)
js("window.openBlockMenu()")
wait(300)

# 菜单现场：所有 .si 的 data-k 与文字
d = js("(function(){var m=document.getElementById('slashmenu');"
       "return JSON.stringify([].map.call(m.querySelectorAll('.si'),function(x){"
       "return [x.getAttribute('data-k'), x.textContent.slice(0,10), x.className]}))})()")
note("menu items", str(d))

# 复刻 click_si
r = js("(function(){var m=document.getElementById('slashmenu');"
       "var it=[].filter.call(m.querySelectorAll('.si'),function(x){"
       "return x.textContent.indexOf('图片')!==-1})[0];"
       "if(!it)return 'NOITEM';"
       "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'clicked:'+it.getAttribute('data-k')})()")
note("click_si", str(r))

for i in range(6):
    wait(150)
    r = js("window.__wantPick === true ? 'pick' : 'no'")
    note(f"wantPick t={(i+1)*150}ms", str(r))

out.append("DONE")
flush()
print("done")
