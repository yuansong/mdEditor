# -*- coding: utf-8 -*-
"""v3.29 探针：方向合并彻底移除 —— __tblOp('merge*') 为空操作、工具条无方向合并按钮。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m27b.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
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


def jj(code):
    r = js(code)
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


wait(2500)
TBL = "| 甲 | 乙 | 丙 | 丁 |\n| --- | --- | --- | --- |\n| 1 | 2 | 3 | 4 |\n| 5 | 6 | 7 | 8 |"
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)
js("window.__tblSelSet(0, 1, 1, 1, 1)")
wait(300)
before = jj("window.__raw()").get("raw", [""])[0]

for op in ["mergeLeft", "mergeRight", "mergeUp", "mergeDown"]:
    r = js("(function(){try{window.__tblOp('" + op + "');return 'called'}catch(e){return 'ERR:'+e.message}})()")
    check(f"__tblOp('{op}') 可调用（不再报错）", r == "called", str(r))
wait(300)
after = jj("window.__raw()").get("raw", [""])[0]
check("四个方向合并均为空操作（raw 不变）", before == after, after[:160])

bt2 = js("(function(){var b=document.querySelectorAll('#tblbar button');var t=[];for(var i=0;i<b.length;i++)t.push(b[i].title);return JSON.stringify(t)})()")
check("单选格操作条无任何方向合并按钮",
      all("合并" not in t for t in json.loads(bt2 or "[]")), bt2)

out.append("DONE")
flush()
print("done")
