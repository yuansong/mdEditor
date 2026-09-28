# -*- coding: utf-8 -*-
"""m47 诊断探针：合并表边线拖动「自动缩小」+ 行高压缩下限 实测。
S0 点边线不动(合并表)；S1 拖合并格(colspan)右缘；S2 rowspan 合并拖列线；
S3 rowspan 合并拖行线(压缩/放大)；S4 缩放框 e/s 手柄；H 素表行高压到最小。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m47.txt")
out = []


def log(s):
    out.append(str(s))
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

MD = ("| A | B | C | D |\n| --- | --- | --- | --- |\n"
      "| 1 | 2 | 3 | 4 |\n| 5 | 6 | 7 | 8 |\n| 9 | 10 | 11 | 12 |")

SNAP = ("(function(){var t=document.querySelector('.b-table table');"
        "if(!t)return JSON.stringify({none:1});"
        "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
        "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
        "var rows=trs.map(function(tr){var rc=tr.getBoundingClientRect();"
        "return [Math.round(rc.height),tr.getAttribute('style')||''];});"
        "var hdr=trs[0],cells=[];"
        "for(var j=0;j<hdr.cells.length;j++){var c=hdr.cells[j].getBoundingClientRect();"
        "cells.push([Math.round(c.left),Math.round(c.right)]);}"
        "var cw=[],cg=t.querySelectorAll('colgroup > col');"
        "for(var q=0;q<cg.length;q++){var m=(cg[q].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
        "cw.push(m?parseFloat(m[1]):null);}"
        "var rc=t.getBoundingClientRect();"
        "return JSON.stringify({tblW:Math.round(rc.width),tblH:Math.round(rc.height),"
        "tblStyle:t.getAttribute('style')||'',layout:t.style.tableLayout||'',"
        "cells:cells,rows:rows,colW:cw})})()")

# 列边线拖拽：mousedown 于表头格 ci 右缘 → n 步 mousemove dx
COL_DRAG = ("(function(ci,dx,n){"
            "var t=document.querySelector('.b-table table');"
            "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
            "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
            "var cell=trs[0].cells[ci];var rc=cell.getBoundingClientRect();"
            "var x0=rc.right-1,y0=rc.top+rc.height/2;"
            "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
            "clientX:x0,clientY:y0}));"
            "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
            "buttons:1,clientX:x0+dx*i/n,clientY:y0}));}"
            "return 'held'})")

# 行边线拖拽：mousedown 于行 ri 格 ci 底缘 → n 步 mousemove dy
ROW_DRAG = ("(function(ri,ci,dy,n){"
            "var t=document.querySelector('.b-table table');"
            "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
            "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
            "var cell=trs[ri].cells[ci];var rc=cell.getBoundingClientRect();"
            "var x0=rc.left+rc.width/2,y0=rc.bottom-1;"
            "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
            "clientX:x0,clientY:y0}));"
            "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
            "buttons:1,clientX:x0,clientY:y0+dy*i/n}));}"
            "return 'held'})")

# 缩放框手柄拖拽
FRAME_DRAG = ("(function(h,dx,dy,n){"
              "var hd=document.querySelector('#rzframe .rz.'+h);"
              "if(!hd)return 'nohandle';"
              "var rc=hd.getBoundingClientRect();"
              "var x0=rc.left+rc.width/2,y0=rc.top+rc.height/2;"
              "hd.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
              "clientX:x0,clientY:y0}));"
              "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
              "buttons:1,clientX:x0+dx*i/n,clientY:y0+dy*i/n}));}"
              "return 'held'})")

UP = ("document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
      "clientX:0,clientY:0}));'up'")

RAW0 = "(function(){var r=window.__raw();return r&&r.raw?r.raw[0].slice(0,300):'noRaw'})()"


def scene(name, setup=None):
    js(f"window.setMarkdown({json.dumps(MD)})")
    wait(700)
    if setup:
        for step in setup:
            js(step)
            wait(500)
    log(f"=== {name} 初始 ===")
    log(json.dumps(jj(SNAP), ensure_ascii=False))


# ---------- S0: 合并表(colspan)，点边线不动（d=0）----------
scene("S0 合并表点边线不动", ["window.__tblSelSet(0,1,1,1,2)", "window.__tblOp('merge')"])
r = js(COL_DRAG + "(0,0,1)")
log("S0 hold=" + str(r))
js(UP)
wait(500)
log("=== S0 松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("S0 raw=" + str(jj(RAW0)))

# ---------- S1: 合并表(colspan)，拖表头第0列右缘 +50 ----------
scene("S1 合并表拖列线+50", ["window.__tblSelSet(0,1,1,1,2)", "window.__tblOp('merge')"])
r = js(COL_DRAG + "(0,50,10)")
log("S1 hold=" + str(r))
log("=== S1 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== S1 松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("S1 raw=" + str(jj(RAW0)))

# ---------- S2: rowspan 合并，拖列线 +50 / 再拖一次 ----------
scene("S2 rowspan合并拖列线", ["window.__tblSelSet(0,1,1,2,1)", "window.__tblOp('merge')"])
r = js(COL_DRAG + "(1,50,10)")
log("S2 hold=" + str(r))
log("=== S2 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== S2 松手后(第一次) ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
r = js(COL_DRAG + "(1,-40,10)")
log("S2b hold=" + str(r))
js(UP)
wait(500)
log("=== S2b 松手后(第二次) ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("S2 raw=" + str(jj(RAW0)))

# ---------- S3: rowspan 合并，拖行线（放大+30 / 压缩-100 / 点一下不动）----------
scene("S3 rowspan合并拖行线", ["window.__tblSelSet(0,1,1,2,1)", "window.__tblOp('merge')"])
r = js(ROW_DRAG + "(1,0,30,8)")
log("S3 hold=" + str(r))
log("=== S3 放大+30 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== S3 放大松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
r = js(ROW_DRAG + "(1,0,-100,10)")
log("S3b hold=" + str(r))
log("=== S3b 压缩-100 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== S3b 压缩松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("S3 raw=" + str(jj(RAW0)))
r = js(ROW_DRAG + "(2,0,0,1)")
log("S3c hold=" + str(r))
js(UP)
wait(500)
log("=== S3c 点行线不动后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))

# ---------- S4: 缩放框手柄（先点一下行线让框出现，再拖 e / s）----------
scene("S4 缩放框手柄", ["window.__tblSelSet(0,1,1,1,2)", "window.__tblOp('merge')"])
r = js(COL_DRAG + "(0,0,1)")
js(UP)
wait(400)
r = js(FRAME_DRAG + "('e',60,0,10)")
log("S4 e hold=" + str(r))
log("=== S4 拖e手柄中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== S4 拖e松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
r = js(FRAME_DRAG + "('s',0,-120,10)")
log("S4b s hold=" + str(r))
log("=== S4b 拖s手柄(-120)中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== S4b 拖s松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("S4 raw=" + str(jj(RAW0)))

# ---------- H: 素表行高压到最小（自然高 vs 拖-100）----------
scene("H 素表行高下限")
log("H 自然行高见初始 rows")
r = js(ROW_DRAG + "(1,0,-100,10)")
log("H hold=" + str(r))
log("=== H 压缩-100 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== H 压缩松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("H raw=" + str(jj(RAW0)))

out.append("DONE")
flush()
print("done")
