# -*- coding: utf-8 -*-
"""m62 探针：缺陷2 残留组合场景。
E7:  空表 + 合并 (0,1)+(1,1)（表头第2格+正文第1行第2格，即用户贴的 HTML 形态）
     → 实时渲染逐格几何审计（每格 x 坐标应落在其逻辑列位置）
E8:  空表 + 合并 (0,1)+(1,1) 后拖列边线 → 落盘重放后 rowspan 应仍在 thead col1
E9:  空表 + 合并 (1,1)+(2,1)（正文第2列两格）后拖列边线 → rowspan 应仍在 tbody
E10: 空表 + 合并 (1,3)+(2,3)（正文第4列两格）后拖列边线 → rowspan 应仍在 tbody
E11: 空表 + 合并 (1,1)+(2,1) 后拖行边线 → rowspan 保持
E12: 有内容表 + 合并 (0,1)+(1,1) 后整表缩放 → 重放后 rowspan 应仍在 thead col1
"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m62.txt")
out = []
PASS = 0
FAIL = 0


def log(s):
    out.append(str(s)); flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def ck(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; log(f"[PASS] {name} {detail}")
    else: FAIL += 1; log(f"[FAIL] {name} {detail}")


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
    try: return json.loads(r)
    except Exception: return {"_raw": str(r or "")}


wait(3000)

MD_EMPTY = ("|  |  |  |  |\n| --- | --- | --- | --- |\n"
            "|  |  |  |  |\n|  |  |  |  |")
MD_P = ("| A1 | B1 | C1 | D1 |\n| --- | --- | --- | --- |\n"
        "| A2 | B2 | C2 | D2 |\n| A3 | B3 | C3 | D3 |")


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(700)


# 逐格几何审计：每格 (逻辑r, 逻辑c, x, w, rowspan)；列边界组（每行首格 x 应≈同列首格 x）
CELLGEO = ("(function(){"
           "var t=document.querySelector('.b-table table');"
           "if(!t)return JSON.stringify({none:1});"
           "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
           "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
           "var grid=[];for(var r=0;r<trs.length;r++)grid.push([]);"
           "var cells=[];"
           "for(var r2=0;r2<trs.length;r2++){"
           "var cs2=trs[r2].cells,c=0;"
           "for(var q=0;q<cs2.length;q++){"
           "while(grid[r2][c]!==undefined)c++;"
           "var CS=+cs2[q].getAttribute('colspan')||1,RS=+cs2[q].getAttribute('rowspan')||1;"
           "var rc=cs2[q].getBoundingClientRect();"
           "cells.push({r:r2,c:c,rs:RS,cs:CS,x:Math.round(rc.left),w:Math.round(rc.width),"
           "h:Math.round(rc.height),tag:cs2[q].tagName});"
           "for(var dr=0;dr<RS;dr++)for(var dc=0;dc<CS;dc++){var rr=r2+dr,cc=c+dc;"
           "if(!grid[rr])continue;grid[rr][cc]=1;}"
           "c+=CS;}}"
           "var tb=t.getBoundingClientRect();"
           "return JSON.stringify({cells:cells,tblX:Math.round(tb.left),tblW:Math.round(tb.width)})})()")

# 简版审计：合并格锚点/所在节 + 列宽
AUDIT = ("(function(){"
         "var t=document.querySelector('.b-table table');"
         "if(!t)return JSON.stringify({none:1});"
         "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
         "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
         "var merged=[],grid=[];"
         "for(var r=0;r<trs.length;r++)grid.push([]);"
         "for(var r2=0;r2<trs.length;r2++){"
         "var cs2=trs[r2].cells,c=0;"
         "for(var q=0;q<cs2.length;q++){"
         "while(grid[r2][c]!==undefined)c++;"
         "var CS=+cs2[q].getAttribute('colspan')||1,RS=+cs2[q].getAttribute('rowspan')||1;"
         "if(CS>1||RS>1)merged.push({r:r2,c:c,cs:CS,rs:RS,tag:cs2[q].tagName,"
         "sect:(cs2[q].closest('thead')?'thead':'tbody')});"
         "for(var dr=0;dr<RS;dr++)for(var dc=0;dc<CS;dc++){var rr=r2+dr,cc=c+dc;"
         "if(!grid[rr])continue;grid[rr][cc]=1;}"
         "c+=CS;}}"
         "var cg=t.querySelectorAll('colgroup > col');var cw=[];"
         "for(var q2=0;q2<cg.length;q2++){var m=(cg[q2].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
         "cw.push(m?parseFloat(m[1]):null);}"
         "return JSON.stringify({merged:merged,cov:grid,colW:cw})})()")

# 拖指定格的边线（by 逻辑坐标定位格子）
DRAG_CELL_EDGE = ("(function(rIdx,cIdx,side,dx,dy,n){"
                  "try{"
                  "var t=document.querySelector('.b-table table');"
                  "if(!t)return 'notable';"
                  "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
                  "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
                  "var grid=[];for(var r=0;r<trs.length;r++)grid.push([]);"
                  "var cell=null;"
                  "for(var r2=0;r2<trs.length&&!cell;r2++){"
                  "var cs2=trs[r2].cells,c=0;"
                  "for(var q=0;q<cs2.length;q++){"
                  "while(grid[r2][c]!==undefined)c++;"
                  "var CS=+cs2[q].getAttribute('colspan')||1,RS=+cs2[q].getAttribute('rowspan')||1;"
                  "if(r2===rIdx&&c===cIdx){cell=cs2[q];break;}"
                  "for(var dr=0;dr<RS;dr++)for(var dc=0;dc<CS;dc++){var rr=r2+dr,cc=c+dc;"
                  "if(!grid[rr])continue;grid[rr][cc]=1;}"
                  "c+=CS;}}"
                  "if(!cell)return 'nocell';"
                  "var rc=cell.getBoundingClientRect();"
                  "var x0,y0;"
                  "if(side=='left'){x0=rc.left+1;y0=rc.top+rc.height/2;}"
                  "else if(side=='right'){x0=rc.right-1;y0=rc.top+rc.height/2;}"
                  "else{x0=rc.left+rc.width/2;y0=rc.bottom-1;}"
                  "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
                  "clientX:x0,clientY:y0}));"
                  "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
                  "buttons:1,clientX:x0+(dx||0)*i/n,clientY:y0+(dy||0)*i/n}));}"
                  "return 'held';"
                  "}catch(e){return 'ERR:'+e.message}})")

UP = ("document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
      "clientX:0,clientY:0}));'up'")

# 整表缩放手柄
OUTER = ("(function(dx,n){"
         "try{"
         "var h=document.querySelector('#rzframe .rz.e');"
         "if(!h)return 'nohandle';"
         "var rc=h.getBoundingClientRect();"
         "var x0=rc.left+rc.width/2,y0=rc.top+rc.height/2;"
         "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
         "clientX:x0,clientY:y0}));"
         "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
         "buttons:1,clientX:x0+dx*i/n,clientY:y0}));}"
         "return 'held';"
         "}catch(e){return 'ERR:'+e.message}})")


def merged_of(au):
    return (au.get("merged") or [{}])[0]


# ==================== E7: 空表 + 合并 (0,1)+(1,1) → 逐格几何 ====================
setmd(MD_EMPTY)
js("window.__tblSelSet(0, 0,1, 1,1)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
geo = jj(CELLGEO)
au = jj(AUDIT); raw = js("window.getMarkdown()")
log(f"E7 geo={json.dumps(geo, ensure_ascii=False)}")
log(f"E7 merged={au.get('merged')} raw={raw[:200]}")
mg = merged_of(au)
ck("E7 合并锚点 (0,1) 1x2", mg.get("r") == 0 and mg.get("c") == 1 and mg.get("rs") == 2,
   str(au.get("merged")))
ck("E7 序列化归一：跨表头合并的 raw 无 thead", "<thead>" not in (raw or ""), (raw or "")[:80])
nth7 = jj("(function(){var t=document.querySelector('.b-table table');"
          "return JSON.stringify({th:!!(t&&t.tHead)})})()")
ck("E7 渲染归一：DOM 无 thead", nth7.get("th") is False, str(nth7))
cells = geo.get("cells") or []
# 列锚点：thead 行 th(col0..3) 的 x；tbody 行1 的 3 个 td 应对齐 col0/2/3
th_x = {c["c"]: c["x"] for c in cells if c["tag"] == "TH"}
tb1 = [c for c in cells if c["r"] == 1]
ck("E7 tbody 行1 只有 3 格", len(tb1) == 3, str(tb1))
if len(tb1) == 3 and len(th_x) == 4:
    tb1.sort(key=lambda c: c["x"])
    ck("E7 tbody 行1 三格对齐 col0/col2/col3（跳过合并列）",
       abs(tb1[0]["x"] - th_x[0]) <= 2 and abs(tb1[1]["x"] - th_x[2]) <= 2
       and abs(tb1[2]["x"] - th_x[3]) <= 2,
       f"td_x={[c['x'] for c in tb1]} th_x={th_x}")
    ck("E7 合并格宽度 = col1 宽（未横跨）",
       abs([c for c in cells if c["rs"] == 2][0]["w"] - (th_x.get(2, 0) - th_x.get(1, 0))) <= 3,
       "")
tb2 = [c for c in cells if c["r"] == 2]
ck("E7 tbody 行2 仍有 4 格", len(tb2) == 4, str(len(tb2)))

# ==================== E8: 空表 + 合并 (0,1)+(1,1) → 拖合并格右边线 +60 ====================
setmd(MD_EMPTY)
js("window.__tblSelSet(0, 0,1, 1,1)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
r = js(DRAG_CELL_EDGE + "(0,1,'right',60,0,10)"); js(UP); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
log(f"E8 drag={r} merged={au.get('merged')} colW={au.get('colW')} raw={raw[:250]}")
mg = merged_of(au)
ck("E8 拖边线后合并仍在 (0,1) 1x2 thead",
   mg.get("r") == 0 and mg.get("c") == 1 and mg.get("rs") == 2, str(au.get("merged")))
ck("E8 拖边线后 raw 仍无 thead（归一稳定）", "<thead>" not in (raw or ""), (raw or "")[:80])
cw = au.get("colW") or []
ck("E8 列宽只 col1 +60（4 列其余不变）", len(cw) == 4, str(cw))

# ==================== E9: 空表 + 合并 (1,1)+(2,1) → 拖列边线 ====================
setmd(MD_EMPTY)
js("window.__tblSelSet(0, 1,1, 2,1)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
au0 = jj(AUDIT)
mg0 = merged_of(au0)
ck("E9 前置：合并锚点 (1,1) 1x2 tbody", mg0.get("r") == 1 and mg0.get("c") == 1 and mg0.get("rs") == 2,
   str(au0.get("merged")))
r = js(DRAG_CELL_EDGE + "(1,1,'right',60,0,10)"); js(UP); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
log(f"E9 drag={r} merged={au.get('merged')} colW={au.get('colW')} raw={raw[:250]}")
mg = merged_of(au)
ck("E9 拖边线后合并仍在 (1,1) 1x2 tbody",
   mg.get("r") == 1 and mg.get("c") == 1 and mg.get("rs") == 2 and mg.get("sect") == "tbody",
   str(au.get("merged")))

# ==================== E10: 空表 + 合并 (1,3)+(2,3) → 拖列边线 ====================
setmd(MD_EMPTY)
js("window.__tblSelSet(0, 1,3, 2,3)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
au0 = jj(AUDIT)
ck("E10 前置：合并锚点 (1,3) 1x2 tbody", merged_of(au0).get("r") == 1 and merged_of(au0).get("c") == 3,
   str(au0.get("merged")))
r = js(DRAG_CELL_EDGE + "(1,3,'right',60,0,10)"); js(UP); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
log(f"E10 drag={r} merged={au.get('merged')} colW={au.get('colW')} raw={raw[:250]}")
mg = merged_of(au)
ck("E10 拖边线后合并仍在 (1,3) 1x2 tbody",
   mg.get("r") == 1 and mg.get("c") == 3 and mg.get("rs") == 2, str(au.get("merged")))

# ==================== E11: 空表 + 合并 (1,1)+(2,1) → 拖行边线 ====================
setmd(MD_EMPTY)
js("window.__tblSelSet(0, 1,1, 2,1)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
r = js(DRAG_CELL_EDGE + "(1,0,'bottom',0,50,10)"); js(UP); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
log(f"E11 drag={r} merged={au.get('merged')} raw={raw[:250]}")
mg = merged_of(au)
ck("E11 拖行边线后合并仍在 (1,1) 1x2 tbody",
   mg.get("r") == 1 and mg.get("c") == 1 and mg.get("rs") == 2, str(au.get("merged")))

# ==================== E12: 有内容表 + 合并 (0,1)+(1,1) → 整表缩放 ====================
setmd(MD_P)
js("window.__tblSelSet(0, 0,1, 1,1)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
r = js(OUTER + "(-80,10)"); js(UP); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
log(f"E12 drag={r} merged={au.get('merged')} colW={au.get('colW')} raw={raw[:250]}")
mg = merged_of(au)
ck("E12 整表缩放后合并仍在 (0,1) 1x2 thead",
   mg.get("r") == 0 and mg.get("c") == 1 and mg.get("rs") == 2, str(au.get("merged")))
ck("E12 整表缩放后 raw 仍无 thead（归一稳定）", "<thead>" not in (raw or ""), (raw or "")[:80])
cw = au.get("colW") or []
ck("E12 缩放后 colW 全部存在且 < 原宽（等比缩小）",
   len(cw) == 4 and all(c and c < 200 for c in cw), str(cw))

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
flush()
os._exit(0)
