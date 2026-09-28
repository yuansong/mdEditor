# -*- coding: utf-8 -*-
"""m48 诊断探针：合并表拖边线「自动缩小」第二轮——更多合并拓扑。
T1 合并到最右列拖表右缘；T2 整行合并拖右缘；T3 先缩窄再合并再拖；
T4 表头+体同时合并；T5 高 rowspan 内部行线。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m48.txt")
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
        "var rows=trs.slice(0,4).map(function(tr){var cs=[];"
        "for(var j=0;j<tr.cells.length;j++){var c=tr.cells[j].getBoundingClientRect();"
        "cs.push([Math.round(c.left),Math.round(c.right)]);}"
        "return cs;});"
        "var cw=[],cg=t.querySelectorAll('colgroup > col');"
        "for(var q=0;q<cg.length;q++){var m=(cg[q].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
        "cw.push(m?parseFloat(m[1]):null);}"
        "var rc=t.getBoundingClientRect();"
        "return JSON.stringify({tblW:Math.round(rc.width),tblH:Math.round(rc.height),"
        "tblStyle:t.getAttribute('style')||'',rows:rows,colW:cw})})()")

# 任意格边线拖拽：ri 行 ci 格，edge='r'|'b'，d 像素
DRAG = ("(function(ri,ci,edge,d,n){"
        "var t=document.querySelector('.b-table table');"
        "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
        "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
        "var cell=trs[ri].cells[ci];var rc=cell.getBoundingClientRect();"
        "var x0,y0;if(edge==='r'){x0=rc.right-1;y0=rc.top+rc.height/2;}else{x0=rc.left+rc.width/2;y0=rc.bottom-1;}"
        "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
        "clientX:x0,clientY:y0}));"
        "var dx=edge==='r'?d:0,dy=edge==='b'?d:0;"
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


# ---------- T1: 合并体行 rows1-2 cols2-3（到最右列），拖合并格右缘 +50 ----------
scene("T1 合并到最右列", ["window.__tblSelSet(0,1,2,2,3)", "window.__tblOp('merge')"])
r = js(DRAG + "(1,1,'r',50,10)")   # 体行1 现有 cells=[c0,合并(c1-c3)]，拖其右缘
log("T1 hold=" + str(r))
log("=== T1 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== T1 松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("T1 raw=" + str(jj(RAW0)))

# ---------- T2: 整行合并（row1 全宽），拖该行右缘 +50 / 行线 +30 ----------
scene("T2 整行合并", ["window.__tblSelSet(0,1,0,1,3)", "window.__tblOp('merge')"])
r = js(DRAG + "(1,0,'r',50,10)")
log("T2 hold=" + str(r))
log("=== T2 拖右缘中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== T2 右缘松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
r = js(DRAG + "(1,0,'b',30,8)")
log("T2b hold=" + str(r))
js(UP)
wait(500)
log("=== T2b 行线松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("T2 raw=" + str(jj(RAW0)))

# ---------- T3: 先缩窄 col1（-100），再合并 rows1-2 cols1-2，再拖 +30 ----------
scene("T3 先缩窄再合并", None)
r = js(DRAG + "(0,1,'r',-100,10)")
js(UP)
wait(500)
log("=== T3 缩窄后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js("window.__tblSelSet(0,1,1,2,2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
log("=== T3 合并后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
r = js(DRAG + "(0,1,'r',30,10)")
log("T3 hold=" + str(r))
log("=== T3 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== T3 松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("T3 raw=" + str(jj(RAW0)))

# ---------- T4: 表头+体同时合并（cols1-2），拖表头合并格右缘 ----------
scene("T4 表头体同合并", ["window.__tblSelSet(0,0,1,0,2)", "window.__tblOp('merge')",
                          "window.__tblSelSet(0,1,1,2,2)", "window.__tblOp('merge')"])
r = js(DRAG + "(0,1,'r',40,10)")   # 表头现 cells=[th0, 合并th(c1-c2), th3]
log("T4 hold=" + str(r))
log("=== T4 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== T4 松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("T4 raw=" + str(jj(RAW0)))

# ---------- T5: 高 rowspan（rows1-3 col1），拖合并区内行线（row2 底缘）----------
scene("T5 高rowspan内部行线", ["window.__tblSelSet(0,1,1,3,1)", "window.__tblOp('merge')"])
r = js(DRAG + "(2,0,'b',40,8)")   # row2 的 col0 格底缘 = 合并区内视觉行线
log("T5 hold=" + str(r))
log("=== T5 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== T5 松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("T5 raw=" + str(jj(RAW0)))

out.append("DONE")
flush()
print("done")
