# -*- coding: utf-8 -*-
"""v3.27 诊断：合并后整表缩放，colgroup 为何多 1 列。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m27c.txt")
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


wait(2500)

TBL = "| 甲 | 乙 | 丙 | 丁 |\n| --- | --- | --- | --- |\n| 1 | 2 | 3 | 4 |\n| 5 | 6 | 7 | 8 |"
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)

DUMP = ("(function(){var b=document.querySelector('#editor .blk');"
        "var tbl=b?b.querySelector('table'):null;if(!tbl)return JSON.stringify({tbl:false});"
        "var rows=[];var all=tbl.querySelectorAll('tr');"
        "for(var i=0;i<all.length;i++){var cs=[];for(var j=0;j<all[i].cells.length;j++)"
        "cs.push(all[i].cells[j].tagName+'x'+all[i].cells[j].colSpan+'r'+all[i].cells[j].rowSpan+':'+all[i].cells[j].textContent.slice(0,4));"
        "rows.push(cs.join('|'))}"
        "var cgs=tbl.querySelectorAll('colgroup');var cgw=[];"
        "if(cgs.length){for(var k=0;k<cgs[0].children.length;k++)cgw.push(cgs[0].children[k].getAttribute('style')||'');}"
        "return JSON.stringify({tbl:true, nColgroup:cgs.length, colgroup:cgw, rows:rows})})()")

out.append("=== after setMarkdown ===")
out.append(str(js(DUMP)))

js("window.__tblSelSet(0, 1, 1, 1, 2)")
wait(200)
js("window.__tblOp('merge')")
wait(400)

out.append("=== after merge (1x2 rect) ===")
out.append(str(js(DUMP)))

# 模拟 RZ 东手柄拖拽
code = ("(function(){var rz=document.getElementById('rzframe');"
        "if(!rz)return 'no rz';var h=rz.querySelector('.rz.e');"
        "if(!h)return 'no handle';var r=h.getBoundingClientRect();"
        "function fire(el,t,x,y){el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,clientX:x,clientY:y}));}"
        "fire(h,'mousedown',r.left,r.top);"
        "fire(document,'mousemove',r.left+60,r.top);"
        "fire(document,'mouseup',r.left+60,r.top);"
        "return 'dragged'})()")
out.append("drag: " + str(js(code)))
wait(500)

out.append("=== after drag ===")
out.append(str(js(DUMP)))
raw0 = js("window.__raw()")
out.append("raw[0]: " + str(raw0)[:600])

out.append("DONE")
flush()
print("done")
