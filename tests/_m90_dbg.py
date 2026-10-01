# -*- coding: utf-8 -*-
"""m90：G1 第 3 步 toggle 无效的诊断探针（段落 B→I→B 逐步 dump）"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m90.txt")
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

def jj(code):
    try:
        return json.loads(js(code) or "{}")
    except Exception:
        return {"_raw": js(code)}

wait(2500)
MD = "段落内容文字示例"
js("window.setMarkdown(" + json.dumps(MD, ensure_ascii=False) + ")")
wait(700)

SEL = ("(function(){var el=document.querySelector('#editor .blk p');"
       "if(!el)return 'no-el';"
       "var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")

def dump(tag):
    d = jj("(function(){var r=window.__raw();"
           "return JSON.stringify({raw:JSON.parse(r).raw,"
           "edit:!!document.querySelector('#editor .raw-edit'),"
           "sel:getSelection().toString()})})()")
    log("%s -> %s" % (tag, json.dumps(d, ensure_ascii=False)))

for act in ("bold", "italic", "bold"):
    r_sel = js(SEL)
    wait(250)
    r_fmt = js("(function(){try{return 'R:' + window.__applyFloat('%s')}catch(e){return 'ERR:' + e.message}})()" % act)
    wait(450)
    log("=== act=%s sel=%s fmt=%s" % (act, r_sel, r_fmt))
    dump("after " + act)

log("DONE")
print("DONE")
