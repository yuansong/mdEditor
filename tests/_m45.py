# -*- coding: utf-8 -*-
"""诊断探针：表格边线拖动两问题实测。
A) 无合并表格：拖一条竖边线 → 记录拖动中各列宽度（验证其他边线是否跟动）；
B) 含合并格表格：拖边线 → 记录表格总宽 / colgroup 变化（定位整表变小路径）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m45.txt")
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

# 列几何快照：表头每格 left/right + 表总宽 + colgroup 各列声明宽
SNAP = ("(function(){var t=document.querySelector('.b-table table');"
        "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
        "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
        "var hdr=trs[0],ws=[];"
        "for(var j=0;j<hdr.cells.length;j++){var rc=hdr.cells[j].getBoundingClientRect();"
        "ws.push([Math.round(rc.left),Math.round(rc.right),Math.round(rc.width)]);}"
        "var cw=[];var cg=t.querySelectorAll('colgroup > col');"
        "for(var q=0;q<cg.length;q++){var m=(cg[q].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
        "cw.push(m?parseFloat(m[1]):null);}"
        "var trc=t.getBoundingClientRect();"
        "return JSON.stringify({tblW:Math.round(trc.width),tblStyle:t.getAttribute('style')||'',"
        "layout:t.style.tableLayout||'css',cells:ws,colW:cw})})()")

# 边线拖拽：mousedown 于表头格 idx 右缘 → n 步 mousemove → （hold 不 mouseup）
BORDER_DRAG_HOLD = ("(function(ci,dx,n){"
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

UP = ("document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
      "clientX:0,clientY:0}));'up'")

# ---------- A: 无合并表格，拖第 1 列右缘 +50px ----------
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
log("=== A0 初始状态 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
r = js(BORDER_DRAG_HOLD + "(1,50,10)")
log("A1 hold=" + str(r))
log("=== A1 拖动中（未松手）===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(400)
log("=== A2 松手提交后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("A2 raw[0]=" + (jj("window.__raw()").get("raw") or [""])[0][:200])

# ---------- A3: 缩窄列（-60px，sum < 容器 100% → 疑似等比放大）----------
r = js(BORDER_DRAG_HOLD + "(1,-60,10)")
log("A3 hold=" + str(r))
log("=== A3 缩窄拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(400)
log("=== A4 缩窄松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))

# ---------- B: 合并格表格，拖表头第 0 列右缘 +50px ----------
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
js("window.__tblSelSet(0, 1, 1, 1, 2)")   # 数据行 1，列 1~2（值 2、3）合并
wait(300)
js("window.__tblOp('merge')")
wait(600)
log("=== B0 合并后初始状态 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("B0 raw[0]=" + (jj("window.__raw()").get("raw") or [""])[0][:260])
r = js(BORDER_DRAG_HOLD + "(0,50,10)")
log("B1 hold=" + str(r))
log("=== B1 拖动中（未松手）===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== B2 松手提交后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("B2 raw[0]=" + (jj("window.__raw()").get("raw") or [""])[0][:260])

# ---------- C: 表头行合并格（B+C 合并），拖合并格右缘 / 左缘 ----------
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
js("window.__tblSelSet(0, 0, 1, 0, 2)")   # 表头行，列 1~2 合并
wait(300)
js("window.__tblOp('merge')")
wait(600)
log("=== C0 表头合并后初始 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
# 合并 th 的右缘 = 原始 3 格表头里 cells[1] 的右缘（th 跨 B~C）
r = js(BORDER_DRAG_HOLD + "(1,50,10)")
log("C1 hold=" + str(r))
log("=== C1 拖合并格右缘 +50 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== C2 松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("C2 raw[0]=" + (jj("window.__raw()").get("raw") or [""])[0][:300])

# ---------- D: 同表，缩窄合并格左邻列（-60）+ 行边线拖动 ----------
r = js(BORDER_DRAG_HOLD + "(0,-60,10)")
log("D1 hold=" + str(r))
log("=== D1 缩窄列 A 拖动中 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
js(UP)
wait(500)
log("=== D2 松手后 ===")
log(json.dumps(jj(SNAP), ensure_ascii=False))
log("D2 raw[0]=" + (jj("window.__raw()").get("raw") or [""])[0][:300])

out.append("DONE")
flush()
print("done")
