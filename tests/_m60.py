# -*- coding: utf-8 -*-
"""m60 探针：v3.30.12 表格三缺陷复现 + 修复验证。
V1 竖向合并 (0,1)+(1,1)：存储/DOM 逻辑网格/渲染位置审计（缺陷2：合并格跑到最右侧）
V2 横向三格表头合并 (0,1)-(0,3)：同上
V3 用户路径：mousedown 拖选两格 → contextmenu → 菜单含「合并单元格」→ 点击 → 合并生效
S1 缺陷3：合并 2x2 后选「合并格+右邻格」（矩形只盖部分合并格）→ 菜单应显示合并 → 点击成功
S2 缺陷3 完整路径：拆分(1,1)为2x2 → 合并回 → 选该格+右邻格 → 菜单合并可用
Z1 缺陷1：非等宽列（先拖 col0 +40）→ 合并 2x2 → 拖合并格右边线 +60 → 仅 col2 +60，col0 不动
Z2 等宽新表：合并 2x2 → 拖右边线 +60 → 仅 col2 +60
Z3 竖向合并 → 拖合并格下边线 +50 → 仅 row1 行高变化，合并保留
Z4 整表缩放 +80 后 → 拖合并格右边线 +50 → 仅一列变化
"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m60.txt")
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

MD_P = ("| A1 | B1 | C1 | D1 |\n| --- | --- | --- | --- |\n"
        "| A2 | B2 | C2 | D2 |\n| A3 | B3 | C3 | D3 |")


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(700)


SNAP = ("(function(){"
        "var t=document.querySelector('.b-table table');"
        "if(!t)return JSON.stringify({none:1});"
        "var cw=[],cg=t.querySelectorAll('colgroup > col');"
        "for(var q=0;q<cg.length;q++){var m=(cg[q].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
        "cw.push(m?parseFloat(m[1]):null);}"
        "var rc=t.getBoundingClientRect();"
        "var spans=[];"
        "var all=t.querySelectorAll('td,th');"
        "for(var q2=0;q2<all.length;q2++){var cs=+all[q2].getAttribute('colspan')||1,rs=+all[q2].getAttribute('rowspan')||1;"
        "if(cs>1||rs>1)spans.push(cs+'x'+rs);}"
        "return JSON.stringify({tblW:Math.round(rc.width),style:t.getAttribute('style'),colW:cw,spans:spans})})()")

ROWH = ("(function(){var t=document.querySelector('.b-table table');var trs=t.querySelectorAll('tr');"
        "var hs=[];for(var q=0;q<trs.length;q++)hs.push(Math.round(trs[q].getBoundingClientRect().height));"
        "return JSON.stringify({hs:hs})})()")

# 逻辑网格审计：逐行铺 colspan/rowspan → 每行覆盖、合并格锚点、合并格渲染左偏移
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
         "if(CS>1||RS>1)merged.push({r:r2,c:c,cs:CS,rs:RS,txt:cs2[q].textContent.trim()});"
         "for(var dr=0;dr<RS;dr++)for(var dc=0;dc<CS;dc++){var rr=r2+dr,cc=c+dc;"
         "if(!grid[rr])continue;grid[rr][cc]=cs2[q].textContent.trim();}"
         "c+=CS;}"
         "if(grid[r2].length>cols)cols=grid[r2].length;}"
         "var cov=[];for(var r3=0;r3<grid.length;r3++)cov.push(grid[r3]);"
         "var tblR=t.getBoundingClientRect();"
         "var mc=t.querySelector('td[colspan],td[rowspan],th[colspan],th[rowspan]');"
         "var mLeft=mc?Math.round(mc.getBoundingClientRect().left-tblR.left):-1;"
         "return JSON.stringify({cols:cols,merged:merged,cov:cov,mLeft:mLeft,"
         "tblW:Math.round(tblR.width)})})()")

MENU = ("(function(){var tb=document.getElementById('tblbar');"
        "if(!tb)return JSON.stringify({titles:[]});"
        "var a=[],es=tb.querySelectorAll('.tmi,.alrow button');"
        "for(var i=0;i<es.length;i++){if(es[i].title)a.push(es[i].title);}"
        "return JSON.stringify({titles:a})})()")

CLICK_MERGE = ("(function(){var b=document.querySelector('#tblbar .tmi[title=\"合并单元格\"]');"
               "if(!b)return 'nomergeitem';"
               "b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
               "return 'clicked'})()")

# 用户路径：中心点拖选 (r0,c0)→(r1,c1) → 右键 (r1,c1)
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

DRAG_EDGE = ("(function(side,dx,dy,n){"
             "try{"
             "var t=document.querySelector('.b-table table');"
             "if(!t)return 'notable';"
             "var all=t.querySelectorAll('td,th');"
             "var cell=null;"
             "for(var q=0;q<all.length;q++){var cs=+all[q].getAttribute('colspan')||1,rs=+all[q].getAttribute('rowspan')||1;"
             "if(cs>1||rs>1){cell=all[q];break;}}"
             "if(!cell)return 'nomerge';"
             "var rc=cell.getBoundingClientRect();"
             "var x0,y0;"
             "if(side=='right'){x0=rc.right-1;y0=rc.top+rc.height/2;}"
             "else if(side=='left'){x0=rc.left+1;y0=rc.top+rc.height/2;}"
             "else{x0=rc.left+rc.width/2;y0=rc.bottom-1;}"
             "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
             "clientX:x0,clientY:y0}));"
             "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
             "buttons:1,clientX:x0+(dx||0)*i/n,clientY:y0+(dy||0)*i/n}));}"
             "return 'held';"
             "}catch(e){return 'ERR:'+e.message}})")

DRAG_CELL_EDGE = ("(function(rIdx,cIdx,side,dx,dy,n){"
                  "try{"
                  "var t=document.querySelector('.b-table table');"
                  "if(!t)return 'notable';"
                  "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
                  "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
                  "var cell=trs[rIdx].cells[cIdx];"
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


def wclose(a, b, tol=3):
    return a is not None and b is not None and abs(a - b) <= tol


# ==================== V1: 竖向合并 (0,1)+(1,1) ====================
setmd(MD_P)
js("window.__tblSelSet(0, 0,1, 1,1)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
au = jj(AUDIT)
raw = js("window.getMarkdown()")
log(f"V1 audit={json.dumps(au, ensure_ascii=False)}")
ck("V1 合并锚点在 (0,1) 跨度 1x2", au.get("merged") == [{"r": 0, "c": 1, "cs": 1, "rs": 2, "txt": "B1 B2"}],
   str(au.get("merged")))
ck("V1 行覆盖：row1 在逻辑列 1 处是合并格内容", au.get("cov", [[], []])[1][1] == "B1 B2",
   str(au.get("cov", [[]])[1] if au.get("cov") else None))
ck("V1 行覆盖：row2 不受影响", au.get("cov", [[], [], []])[2] == ["A3", "B3", "C3", "D3"],
   str(au.get("cov", [[], [], []])[2] if len(au.get("cov", [])) > 2 else None))
ck("V1 存储含 rowspan=2 且无 colspan", 'rowspan="2"' in raw and 'colspan' not in raw, raw[:90])
ck("V1 合并格渲染位置在 col1（不在最右）",
   au.get("mLeft", -1) >= 0 and au.get("mLeft", 0) < au.get("tblW", 0) * 0.45,
   f"mLeft={au.get('mLeft')} tblW={au.get('tblW')}")
# 重开文档往返
setmd(raw)
au2 = jj(AUDIT)
ck("V1 存储往返后合并锚点保持 (0,1) 1x2",
   au2.get("merged") == [{"r": 0, "c": 1, "cs": 1, "rs": 2, "txt": "B1 B2"}], str(au2.get("merged")))

# ==================== V2: 横向三格表头合并 (0,1)-(0,3) ====================
setmd(MD_P)
js("window.__tblSelSet(0, 0,1, 0,3)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
au = jj(AUDIT)
log(f"V2 audit={json.dumps(au, ensure_ascii=False)}")
ck("V2 合并锚点在 (0,1) 跨度 3x1", au.get("merged") == [{"r": 0, "c": 1, "cs": 3, "rs": 1, "txt": "B1 C1 D1"}],
   str(au.get("merged")))
ck("V2 合并格渲染位置在 col1（不在最右）",
   au.get("mLeft", -1) >= 0 and au.get("mLeft", 0) < au.get("tblW", 0) * 0.45,
   f"mLeft={au.get('mLeft')} tblW={au.get('tblW')}")

# ==================== V3: 用户路径（拖选 → 右键 → 点合并） ====================
setmd(MD_P)
r = js(DRAGSEL_CTX + "(0,1,1,1)"); wait(400)
mu = jj(MENU)
ck("V3 右键菜单含「合并单元格」", "合并单元格" in mu.get("titles", []), str(mu.get("titles")))
r2 = js(CLICK_MERGE); wait(700)
au = jj(AUDIT)
log(f"V3 menu={mu.get('titles')} click={r2} merged={au.get('merged')}")
ck("V3 点击合并后生效 (0,1) 1x2", r2 == "clicked" and
   au.get("merged") == [{"r": 0, "c": 1, "cs": 1, "rs": 2, "txt": "B1 B2"}], str(au.get("merged")))

# ==================== S1: 缺陷3 —— 合并格 + 右邻格 → 菜单应显示合并 ====================
setmd(MD_P)
js("window.__tblSelSet(0, 1,1, 2,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
js("window.__tblSelSet(0, 1,1, 1,3)"); wait(200)   # 合并格(1,1)-(2,2) + 右邻 (1,3)
mu = jj(MENU)
ck("S1 选「合并格+右邻格」菜单含「合并单元格」", "合并单元格" in mu.get("titles", []), str(mu.get("titles")))
r2 = js(CLICK_MERGE); wait(700)
au = jj(AUDIT)
log(f"S1 click={r2} merged={au.get('merged')}")
ck("S1 点击合并后扩展为 (1,1) 3x2", r2 == "clicked" and
   au.get("merged") and au["merged"][0].get("cs") == 3 and au["merged"][0].get("rs") == 2,
   str(au.get("merged")))

# ==================== S2: 缺陷3 完整路径 —— 拆分→合并回→选该格+邻格 ====================
setmd(MD_P)
js("window.__tblSelSet(0, 1,1, 1,1)"); wait(200)
r0 = js("window.__tblSplitInto(0,2,2)"); wait(700)
au = jj(AUDIT)
log(f"S2 split={r0} cols={au.get('cols')} cov={json.dumps(au.get('cov'), ensure_ascii=False)}")
js("window.__tblSelSet(0, 1,1, 2,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
js("window.__tblSelSet(0, 1,1, 1,3)"); wait(200)
mu = jj(MENU)
ck("S2 拆分→合并回→选该格+邻格 菜单含「合并单元格」", "合并单元格" in mu.get("titles", []),
   str(mu.get("titles")))
r2 = js(CLICK_MERGE); wait(700)
au = jj(AUDIT)
log(f"S2 click={r2} merged={au.get('merged')}")
# 拆分语义：B1/B3/A2/D2 也带跨度 → merged 列表有多项；断言目标格 (1,1) cs=3 rs=2 存在
tgt = [g for g in (au.get("merged") or []) if g.get("r") == 1 and g.get("c") == 1]
ck("S2 点击合并成功（(1,1) 跨度 3x2）", r2 == "clicked" and
   tgt and tgt[0].get("cs") == 3 and tgt[0].get("rs") == 2, str(au.get("merged")))

# ==================== Z1: 缺陷1 —— 非等宽列 + 合并 + 拖右边线 ====================
setmd(MD_P)
r = js(DRAG_CELL_EDGE + "(0,0,'right',40,0,10)")
js(UP); wait(700)                                  # col0 +40 → 非等宽
js("window.__tblSelSet(0, 0,1, 1,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)           # 合并 (0,1)-(1,2) 2x2
s0 = jj(SNAP)
r = js(DRAG_EDGE + "('right',60,0,10)")
js(UP); wait(700)
s1 = jj(SNAP)
log(f"Z1 {s0['colW']}->{s1['colW']} drag={r}")
cw0, cw1 = s0["colW"], s1["colW"]
# v3.30.14：内部边线 = 被拖列 ↔ 右邻列 转移宽度（总宽不变，Typora/Word 语义）
ok = (r == "held" and len(cw1) == 4 and len(cw0) == 4 and
      wclose(cw1[2], (cw0[2] or 0) + 60, 4) and
      wclose(cw1[3], (cw0[3] or 0) - 60, 4) and
      wclose(cw1[0], cw0[0], 3) and wclose(cw1[1], cw0[1], 3))
ck("Z1 非等宽列拖合并格右边线 col2 +60 / col3 -60", ok, f"{cw0}->{cw1}")
ck("Z1 合并保留 2x2", s1["spans"] == ["2x2"], str(s1["spans"]))
# 存储往返：列宽冻结一致
raw = js("window.getMarkdown()")
setmd(raw)
s2 = jj(SNAP)
ck("Z1 存储往返后列宽与合并保留", s2["colW"] == cw1 and s2["spans"] == ["2x2"],
   f"{s2['colW']} {s2['spans']}")

# ==================== Z2: 等宽新表合并 → 拖右边线 ====================
setmd(MD_P)
js("window.__tblSelSet(0, 0,1, 1,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
r = js(DRAG_EDGE + "('right',60,0,10)")
js(UP); wait(700)
s1 = jj(SNAP)
cw = s1["colW"]
d = [(i, (cw[i] or 0) - (cw[i - 1] or 0)) for i in range(1, len(cw))] if len(cw) == 4 else []
log(f"Z2 colW={cw} drag={r}")
ck("Z2 等宽表拖合并格右边线 col2 +60 / col3 -60",
   r == "held" and len(cw) == 4 and cw[0] and wclose(cw[2], cw[0] + 60, 4) and
   wclose(cw[1], cw[0], 3) and wclose(cw[3], cw[0] - 60, 4), str(cw))
ck("Z2 合并保留 2x2", s1["spans"] == ["2x2"], str(s1["spans"]))

# ==================== Z3: 竖向合并 → 拖合并格下边线（行高） ====================
setmd(MD_P)
js("window.__tblSelSet(0, 0,1, 1,1)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
h0 = jj(ROWH)
r = js(DRAG_EDGE + "('bottom',0,50,10)")
js(UP); wait(700)
h1 = jj(ROWH)
au = jj(AUDIT)
log(f"Z3 {h0['hs']}->{h1['hs']} drag={r} merged={au.get('merged')}")
ok = (r == "held" and len(h1["hs"]) == 3 and len(h0["hs"]) == 3 and
      wclose(h1["hs"][1], h0["hs"][1] + 50, 4) and
      wclose(h1["hs"][0], h0["hs"][0], 3) and wclose(h1["hs"][2], h0["hs"][2], 3))
ck("Z3 竖向合并拖下边线 仅 row1 行高 +50", ok, f"{h0['hs']}->{h1['hs']}")
ck("Z3 合并保留 1x2", au.get("merged") and au["merged"][0].get("rs") == 2 and
   au["merged"][0].get("cs") == 1, str(au.get("merged")))

# ==================== Z4: 整表缩放后 → 拖内部边线 ====================
setmd(MD_P)
js("window.__tblSelSet(0, 0,1, 1,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
js(OUTER + "(80,10)")
js(UP); wait(700)
s0 = jj(SNAP)
r = js(DRAG_EDGE + "('right',50,0,10)")
js(UP); wait(700)
s1 = jj(SNAP)
d = [(i, (s1["colW"][i] or 0) - (s0["colW"][i] or 0)) for i in range(min(len(s0["colW"]), len(s1["colW"])))] \
    if s0["colW"] and s1["colW"] else []
log(f"Z4 {s0['colW']}->{s1['colW']} drag={r}")
ck("Z4 整表缩放后拖合并格右边线 col2 +50 / col3 -50", r == "held" and
   d == [(0, 0), (1, 0), (2, 50), (3, -50)], str(d))

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
flush()
print(f"M60 DONE PASS={PASS} FAIL={FAIL}")
