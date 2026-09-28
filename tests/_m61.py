# -*- coding: utf-8 -*-
"""m61 探针：缺陷2 真实场景复现 —— 3x4 表格合并第 4 列（最后一列）第 2-3 行。
用户报告：合并目标 = 逻辑 (1,3)+(2,3)（两个正文行的最后一列），
但产出的 HTML rowspan 落在 thead 第 2 列（跨表头+首行）——锚点错位。
E1/E2: API 路径（空表 / 有内容表）
E3/E4: UI 拖选→右键→点合并（空表 / 有内容表）
E5: 用户贴的 HTML 直接载入 → 渲染几何审计
E6: 合并正确产物 reload 往返
"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m61.txt")
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

# 空表（insertTableBlock 的产物形态）与有内容表
MD_EMPTY = ("|  |  |  |  |\n| --- | --- | --- | --- |\n"
            "|  |  |  |  |\n|  |  |  |  |")
MD_P = ("| A1 | B1 | C1 | D1 |\n| --- | --- | --- | --- |\n"
        "| A2 | B2 | C2 | D2 |\n| A3 | B3 | C3 | D3 |")

USER_HTML = ('<table class="md-tbl">\n<thead>\n<tr><th></th><th rowspan="2"></th>'
             '<th></th><th></th></tr>\n</thead>\n<tbody>\n'
             '<tr><td></td><td></td><td></td></tr>\n'
             '<tr><td></td><td></td><td></td><td></td></tr>\n</tbody>\n</table>')


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(700)


# 审计：合并格锚点/跨度/内容 + 各行逻辑覆盖 + 合并格渲染位置 + raw 中 rowspan 所在行
AUDIT = ("(function(){"
         "var t=document.querySelector('.b-table table');"
         "if(!t)return JSON.stringify({none:1});"
         "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
         "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
         "var grid=[],cols=0,merged=[];"
         "for(var r=0;r<trs.length;r++)grid.push([]);"
         "for(var r2=0;r2<trs.length;r2++){"
         "var cs2=trs[r2].cells,c=0;"
         "for(var q=0;q<cs2.length;q++){"
         "while(grid[r2][c]!==undefined)c++;"
         "var CS=+cs2[q].getAttribute('colspan')||1,RS=+cs2[q].getAttribute('rowspan')||1;"
         "if(CS>1||RS>1)merged.push({r:r2,c:c,cs:CS,rs:RS,txt:cs2[q].textContent.trim(),"
         "tag:cs2[q].tagName,sect:(cs2[q].closest('thead')?'thead':'tbody')});"
         "for(var dr=0;dr<RS;dr++)for(var dc=0;dc<CS;dc++){var rr=r2+dr,cc=c+dc;"
         "if(!grid[rr])continue;grid[rr][cc]=cs2[q].textContent.trim();}"
         "c+=CS;}"
         "if(grid[r2].length>cols)cols=grid[r2].length;}"
         "var tblR=t.getBoundingClientRect();"
         "var mc=t.querySelector('td[colspan],td[rowspan],th[colspan],th[rowspan]');"
         "var mLeft=mc?Math.round(mc.getBoundingClientRect().left-tblR.left):-1;"
         "var mW=mc?Math.round(mc.getBoundingClientRect().width):-1;"
         "return JSON.stringify({cols:cols,merged:merged,cov:grid,mLeft:mLeft,mW:mW,"
         "tblW:Math.round(tblR.width),rows:trs.length})})()")

# 逐格几何审计：每格 (逻辑r, 逻辑c, x, w, h, rowspan)
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

MENU = ("(function(){var tb=document.getElementById('tblbar');"
        "if(!tb)return JSON.stringify({titles:[]});"
        "var a=[],es=tb.querySelectorAll('.tmi,.alrow button');"
        "for(var i=0;i<es.length;i++){if(es[i].title)a.push(es[i].title);}"
        "return JSON.stringify({titles:a})})()")

CLICK_MERGE = ("(function(){var b=document.querySelector('#tblbar .tmi[title=\"合并单元格\"]');"
               "if(!b)return 'nomergeitem';"
               "b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
               "return 'clicked'})()")

DRAGSEL_CTX = ("(function(r0,c0,r1,c1){"
               "try{"
               "var t=document.querySelector('.b-table table');if(!t)return 'notable';"
               "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
               "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
               "var a=trs[r0].cells[c0],b2=trs[r1].cells[c1];if(!a||!b2)return 'nocell';"
               "var ra=a.getBoundingClientRect(),rb=b2.getBoundingClientRect();"
               "var x0=ra.left+ra.width/2,y0=ra.top+ra.height/2;"
               "var x1=rb.left+rb.width/2,y1=rb.top+rb.height/2;"
               "a.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
               "clientX:x0,clientY:y0}));"
               "document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,buttons:1,"
               "clientX:x1,clientY:y1}));"
               "document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
               "clientX:x1,clientY:y1}));"
               "b2.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:x1,clientY:y1}));"
               "return 'ok';"
               "}catch(e){return 'ERR:'+e.message}})")


def audit_name(tag, au, raw):
    """通用断言：合并应锚定在 (1,3) 1x2，tag=tbody，不在 thead"""
    mg = au.get("merged") or []
    log(f"{tag} audit={json.dumps(au, ensure_ascii=False)[:400]}")
    log(f"{tag} raw={raw[:300]}")
    ok_anchor = len(mg) == 1 and mg[0].get("r") == 1 and mg[0].get("c") == 3 \
        and mg[0].get("rs") == 2 and mg[0].get("cs") == 1
    ck(f"{tag} 合并锚点在 (1,3) 跨度 1x2", ok_anchor, str(mg))
    ck(f"{tag} 合并格在 tbody（非 thead）", len(mg) == 1 and mg[0].get("sect") == "tbody", str(mg))
    ck(f"{tag} 存储无 thead rowspan（rowspan 不在表头行）",
       raw.find("rowspan") > raw.find("<tbody>"), raw[:120])


# ==================== E1: 空表 API 路径 ====================
setmd(MD_EMPTY)
js("window.__tblSelSet(0, 1,3, 2,3)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
audit_name("E1", au, raw)

# ==================== E2: 有内容表 API 路径 ====================
setmd(MD_P)
js("window.__tblSelSet(0, 1,3, 2,3)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
audit_name("E2", au, raw)
ck("E2 合并内容 D2+D3", (au.get("merged") or [{}])[0].get("txt") == "D2 D3",
   str((au.get("merged") or [{}])[0].get("txt")))

# ==================== E3: 空表 UI 拖选路径 ====================
setmd(MD_EMPTY)
r = js(DRAGSEL_CTX + "(1,3,2,3)"); wait(400)
mu = jj(MENU)
sel = js("window.__tblSel()")
log(f"E3 drag={r} sel={sel} menu={mu.get('titles')}")
ck("E3 拖选后选区 = (1,3)-(2,3)", sel and '"r0":1' in sel and '"c0":3' in sel
   and '"r1":2' in sel and '"c1":3' in sel, str(sel))
ck("E3 右键菜单含「合并单元格」", "合并单元格" in mu.get("titles", []), str(mu.get("titles")))
r2 = js(CLICK_MERGE); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
audit_name("E3", au, raw)

# ==================== E4: 有内容表 UI 拖选路径 ====================
setmd(MD_P)
r = js(DRAGSEL_CTX + "(1,3,2,3)"); wait(400)
mu = jj(MENU)
sel = js("window.__tblSel()")
log(f"E4 drag={r} sel={sel} menu={mu.get('titles')}")
ck("E4 拖选后选区 = (1,3)-(2,3)", sel and '"r0":1' in sel and '"c0":3' in sel
   and '"r1":2' in sel and '"c1":3' in sel, str(sel))
r2 = js(CLICK_MERGE); wait(700)
au = jj(AUDIT); raw = js("window.getMarkdown()")
audit_name("E4", au, raw)

# ==================== E5: 用户贴的 HTML 直接载入 → 渲染审计（v3.30.13 归一） ====================
setmd(USER_HTML)
au = jj(AUDIT)
geo = jj(CELLGEO)
nth = jj("(function(){var t=document.querySelector('.b-table table');"
         "return JSON.stringify({th:!!(t&&t.tHead)})})()")
log(f"E5 audit={json.dumps(au, ensure_ascii=False)}")
log(f"E5 geo={json.dumps(geo, ensure_ascii=False)}")
mg = au.get("merged") or []
ck("E5 载入后合并锚点 (0,1) 1x2", len(mg) == 1 and mg[0].get("r") == 0 and mg[0].get("c") == 1
   and mg[0].get("rs") == 2 and mg[0].get("cs") == 1, str(mg))
ck("E5 归一后 DOM 无 thead（跨表头合并渲染修复）", nth.get("th") is False, str(nth))
cells = geo.get("cells") or []
th_x = {c["c"]: c["x"] for c in cells if c["tag"] == "TH"}
tb1 = sorted([c for c in cells if c["r"] == 1], key=lambda c: c["x"])
ck("E5 tbody 行1 只有 3 格", len(tb1) == 3, str(tb1))
if len(tb1) == 3 and len(th_x) == 4:
    ck("E5 tbody 行1 三格对齐 col0/col2/col3（跳过合并列，不再左移）",
       abs(tb1[0]["x"] - th_x[0]) <= 2 and abs(tb1[1]["x"] - th_x[2]) <= 2
       and abs(tb1[2]["x"] - th_x[3]) <= 2,
       f"td_x={[c['x'] for c in tb1]} th_x={th_x}")
mH = [c for c in cells if c.get("rs") == 2]
ck("E5 合并格高度跨两行（>60px）", mH and mH[0]["h"] > 60, str(mH))
ck("E5 合并格渲染位置在 col1（x < 表宽45%）",
   0 <= au.get("mLeft", -1) < au.get("tblW", 0) * 0.45, f"mLeft={au.get('mLeft')} tblW={au.get('tblW')}")
raw5 = js("window.getMarkdown()")
ck("E5 载入往返存储保持（rowspan 仍在）", 'rowspan="2"' in (raw5 or ""), (raw5 or "")[:120])

# ==================== E6: 合并正确产物 reload 往返 ====================
setmd(MD_P)
js("window.__tblSelSet(0, 1,3, 2,3)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
raw6 = js("window.getMarkdown()")
setmd(raw6)
au6 = jj(AUDIT)
mg6 = au6.get("merged") or []
ck("E6 合并产物 reload 后锚点保持 (1,3) 1x2",
   len(mg6) == 1 and mg6[0].get("r") == 1 and mg6[0].get("c") == 3
   and mg6[0].get("rs") == 2, str(mg6))

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
flush()
os._exit(0)
