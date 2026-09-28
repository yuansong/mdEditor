# -*- coding: utf-8 -*-
"""v3.29 诊断 K：Office 右键菜单 —— 拆分网格面板为何不生效。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29k.txt")
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
TBL = "| 甲 | 乙 | 丙 |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |\n| 7 | 8 | 9 |"
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)

js("window.__tblSelSet(0, 0, 0, 0, 1)")
wait(200)
r = js("(function(){var b=[].filter.call(document.getElementById('tblbar')"
       ".querySelectorAll('button'),function(x){return x.title.indexOf('合并单元格')===0})[0];"
       "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
       "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'})()")
wait(500)
note("merge click", str(r))
note("raw after merge", js("window.getMarkdown()").split("\n")[0])

js("window.__tblSelSet(0, 0, 0, 0, 0)")
wait(200)
d = json.loads(js("""
(function(){var tb=document.getElementById('tblbar');
var sp=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title.indexOf('拆分单元格')===0})[0];
if(!sp)return JSON.stringify({err:'nosplitbtn'});
return JSON.stringify({dis:sp.classList.contains('dis')})})()""") or "{}")
note("split btn state", str(d))

r = js("(function(){var b=[].filter.call(document.getElementById('tblbar')"
       ".querySelectorAll('button'),function(x){return x.title.indexOf('拆分单元格')===0})[0];"
       "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
       "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'})()")
wait(400)
d = json.loads(js("""
(function(){var tsz=document.getElementById('tblsize');
return JSON.stringify({tszShow:tsz?tsz.classList.contains('show'):'notsz',
cells:document.querySelectorAll('#tblgrid .gc').length,
gc01:!!document.querySelector('#tblgrid .gc[data-r=\\"0\\"][data-c=\\"1\\"]')})})()""") or "{}")
note("after split click", str(d))

r = js("(function(){var g=document.querySelector('#tblgrid .gc[data-r=\"0\"][data-c=\"1\"]');"
       "if(!g) return 'NOGC';"
       "g.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'x'})()")
wait(500)
note("gc click", str(r))
note("raw after split", js("window.getMarkdown()").split("\n")[0])

out.append("DONE")
flush()
print("done")
