# -*- coding: utf-8 -*-
"""m49 诊断探针：引用块(qblk)内嵌表格的边线拖拽破坏路径验证。
Q1 素管道表格在引用内拖列线；Q2 合并 HTML 表格在引用内拖列线。
观察 raw[0] 是否被破坏（整块被替换 / 表格变小）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m49.txt")
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


def jj(code):
    r = js(code)
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


wait(2500)

SNAP = ("(function(){var t=document.querySelector('.b-table table');"
        "if(!t)return JSON.stringify({none:1});"
        "var rc=t.getBoundingClientRect();"
        "return JSON.stringify({tblW:Math.round(rc.width),tblH:Math.round(rc.height),"
        "inQuote:!!t.closest('blockquote')})})()")

DRAG = ("(function(ri,ci,d,n){"
        "var t=document.querySelector('.b-table table');"
        "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
        "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
        "var cell=trs[ri].cells[ci];var rc=cell.getBoundingClientRect();"
        "var x0=rc.right-1,y0=rc.top+rc.height/2;"
        "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
        "clientX:x0,clientY:y0}));"
        "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
        "buttons:1,clientX:x0+d*i/n,clientY:y0}));}"
        "document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
        "clientX:x0+d,clientY:y0}));"
        "return 'done'})")

RAW_ALL = "(function(){var r=window.__raw();return r&&r.raw?JSON.stringify(r.raw.slice(0,3)):\"noRaw\"})()"

# ---------- Q1: 引用内管道表格 ----------
MD1 = "> | A | B |\n> | --- | --- |\n> | 1 | 2 |"
js(f"window.setMarkdown({json.dumps(MD1)})")
wait(700)
log("=== Q1 初始 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("Q1 raw=" + str(jj(RAW_ALL)))
r = js(DRAG + "(0,0,40,8)")
log("Q1 drag=" + str(r))
wait(600)
log("=== Q1 拖列线后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("Q1 raw=" + str(jj(RAW_ALL)))

# ---------- Q2: 引用内合并 HTML 表格 ----------
MD2 = ("> <table class=\"md-tbl\"><thead><tr><th>A</th><th>B</th></tr></thead>"
       "<tbody><tr><td rowspan=\"2\">1</td><td>2</td></tr><tr><td>4</td></tr></tbody></table>")
js(f"window.setMarkdown({json.dumps(MD2)})")
wait(700)
log("=== Q2 初始 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("Q2 raw=" + str(jj(RAW_ALL)))
r = js(DRAG + "(0,0,40,8)")
log("Q2 drag=" + str(r))
wait(600)
log("=== Q2 拖列线后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("Q2 raw=" + str(jj(RAW_ALL)))

out.append("DONE")
flush()
print("done")
