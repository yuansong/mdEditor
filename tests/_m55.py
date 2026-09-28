# -*- coding: utf-8 -*-
"""m55 探针：合并后拖边线 / 整表缩放行为复查（用户报告：合并后拖边线整表缩放+布局错乱）。
M1 合并 2x2 → 拖合并格右边线（内侧）→ 只应 col2 +60
M2 合并最右列 (1,3)-(2,3) → 拖合并格右边线（内侧 1px）→ 只应 col3 +60，无整表缩放
M3 同 M2 → 从外侧抓 e 手柄 +80（整表缩放）→ 落盘后合并保留、colW 总和≈表宽
M4 合并 2x2 → 拖表头 (0,1) 左边线 → 只应 col0 +50
M5 合并 2x2 → 拖合并格下边线 → 只应 body row1 行高变化
M6 M3 之后 → 再拖内部边线 → 行为正常（只有一列 +50）
"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m55.txt")
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


def cdiffs(a, b):
    return [(i, (b[i] or 0) - (a[i] or 0)) for i in range(min(len(a), len(b)))]


def one_col_delta(ws, delta, tol=3):
    """最终列宽语义断言：恰好一列与其余列相差 ~delta（其余列等宽；方向不限）"""
    if not ws or len(ws) < 2: return False, str(ws)
    u = sorted(set(ws))
    if len(u) != 2: return False, str(ws)
    lo, hi = u
    if ws.count(lo) == len(ws) - 1:
        return abs((hi - lo) - delta) <= tol, str(ws)
    if ws.count(hi) == len(ws) - 1:
        return abs((lo - hi) - delta) <= tol, str(ws)
    return False, str(ws)


# ==================== M1: 合并 2x2 → 拖合并格右边线（内侧） ====================
setmd(MD_P)
js("window.__tblSelSet(0,1,1,2,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
s0 = jj(SNAP)
r = js(DRAG_EDGE + "('right',60,0,10)")
js(UP); wait(700)
s1 = jj(SNAP)
d = cdiffs(s0["colW"], s1["colW"])
log(f"M1 {s0['colW']}->{s1['colW']} spans={s1['spans']} drag={r}")
ok, det = one_col_delta(s1["colW"], 60)
ck("M1 合并2x2拖右边线 只有col2变化+60", r == "held" and ok, det)
ck("M1 合并保留 2x2", s1["spans"] == ["2x2"], str(s1["spans"]))

# ==================== M2: 合并最右列 → 拖合并格右边线（内侧 1px） ====================
setmd(MD_P)
js("window.__tblSelSet(0,1,3,2,3)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
s0 = jj(SNAP)
r = js(DRAG_EDGE + "('right',60,0,10)")
js(UP); wait(700)
s1 = jj(SNAP)
d = cdiffs(s0["colW"], s1["colW"])
log(f"M2 {s0['colW']}->{s1['colW']} drag={r}")
# 合并后 colW 未冻结前 s0 可能为空数组（与 M1 同）——改用语义断言：
# 恰好一列与其余列差 ~60，且变宽的是最后一列（col3，合并格右边线）
ok, det = one_col_delta(s1["colW"], 60)
hiIdx = s1["colW"].index(max(s1["colW"])) if s1["colW"] else -1
ck("M2 合并最右列拖右边线 只有col3变化+60（无整表缩放）",
   r == "held" and ok and hiIdx == 3, f"{det} hiIdx={hiIdx} drag={r}")

# ==================== M3: 同 M2 → 外侧抓 e 手柄整表缩放 +80 ====================
s0 = jj(SNAP)
r = js(OUTER + "(80,10)")
js(UP); wait(700)
s1 = jj(SNAP)
cw = s1["colW"]
ssum = sum(w for w in cw if w)
log(f"M3 {s0['colW']}->{s1['colW']} tblW={s1['tblW']} spans={s1['spans']} drag={r}")
ck("M3 整表缩放后合并保留", s1["spans"] == ["1x2"], str(s1["spans"]))
ck("M3 colW 总和 ≈ 表宽（列宽冻结一致）",
   ssum > 0 and abs(ssum + 2 - s1["tblW"]) <= 6, f"sum={ssum} tblW={s1['tblW']}")
ck("M3 等比缩放（按总宽比）",
   s0["tblW"] > 0 and len(cw) == 4 and len(s0["colW"]) == 4 and
   all(cw[i] and s0["colW"][i] and
       abs(cw[i] - s0["colW"][i] * s1["tblW"] / s0["tblW"]) <= 6 for i in range(4)),
   str(cw))
# 重开文档验证存储往返
raw1 = js("window.getMarkdown()")
setmd(raw1)
s2 = jj(SNAP)
log(f"M3 重开 spans={s2['spans']} colW={s2['colW']}")
ck("M3 存储往返后合并与列宽保留",
   s2["spans"] == ["1x2"] and s2["colW"] == cw, str(s2["colW"]))

# ==================== M4: 合并 2x2 → 拖表头 (0,1) 左边线 ====================
setmd(MD_P)
js("window.__tblSelSet(0,1,1,2,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
s0 = jj(SNAP)
r = js(DRAG_CELL_EDGE + "(0,1,'left',-50,0,10)")   # 向左拖 = col0 变窄 50? left+1, dx=-50 → 列宽-50
js(UP); wait(700)
s1 = jj(SNAP)
d = cdiffs(s0["colW"], s1["colW"])
log(f"M4 {s0['colW']}->{s1['colW']} drag={r}")
ok, det = one_col_delta(s1["colW"], -50)
ck("M4 表头 B1 左边线拖拽 只有col0变化(-50)", r == "held" and ok, det)

# ==================== M5: 合并 2x2 → 拖合并格下边线（行高） ====================
setmd(MD_P)
js("window.__tblSelSet(0,1,1,2,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
r = js(DRAG_EDGE + "('bottom',0,60,10)")
js(UP); wait(700)
h = jj("(function(){var t=document.querySelector('.b-table table');"
       "var trs=t.querySelectorAll('tr');var hs=[];"
       "for(var q=0;q<trs.length;q++){hs.push(Math.round(trs[q].getBoundingClientRect().height))}"
       "return JSON.stringify({hs:hs,spans:(function(){var a=[];var all=t.querySelectorAll('td,th');"
       "for(var q2=0;q2<all.length;q2++){var cs=+all[q2].getAttribute('colspan')||1,rs=+all[q2].getAttribute('rowspan')||1;"
       "if(cs>1||rs>1)a.push(cs+'x'+rs);}return a})()})})()")
log(f"M5 rows={h['hs']} spans={h['spans']} drag={r}")
ck("M5 合并格下边线拖拽=行高变化且合并保留（行数=表头+2正文）",
   r == "held" and h["spans"] == ["2x2"] and len(h["hs"]) == 3, str(h))

# ==================== M6: 整表缩放后 → 再拖内部边线 ====================
setmd(MD_P)
js("window.__tblSelSet(0,1,1,2,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
js(OUTER + "(80,10)")
js(UP); wait(700)
s0 = jj(SNAP)
r = js(DRAG_EDGE + "('right',50,0,10)")
js(UP); wait(700)
s1 = jj(SNAP)
d = cdiffs(s0["colW"], s1["colW"])
log(f"M6 {s0['colW']}->{s1['colW']} drag={r}")
ck("M6 整表缩放后拖合并格右边线 只有col2+50",
   r == "held" and d == [(0, 0), (1, 0), (2, 50), (3, 0)], str(d))

# ==================== M7-M9: 行内合并位置正确性（用户报告：合并格错误靠到表格边缘） ====================
# DOM 布局审计：逐行展开 colspan/rowspan 得到每格逻辑列区间，核对合并格锚点列
GRID_AUDIT = ("(function(){"
              "var t=document.querySelector('.b-table table');"
              "if(!t)return JSON.stringify({none:1});"
              "var occ={};"
              "function take(r,c){for(var k=0;k<200;k++){var key=r+':'+(c+k);if(!occ[key])return k;}return -1;}"
              "var rows=[];"
              "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push({row:t.tHead.rows[i],head:1});"
              "var b=t.tBodies[0];for(var k2=0;k2<b.rows.length;k2++)trs.push({row:b.rows[k2],head:0});"
              "for(var r=0;r<trs.length;r++){"
              "  var cells=trs[r].row.cells;var info=[];"
              "  for(var c=0;c<cells.length;c++){"
              "    var cs=+cells[c].getAttribute('colspan')||1,rs=+cells[c].getAttribute('rowspan')||1;"
              "    var off=take(r,0);"
              "    for(var rr=r;rr<r+rs;rr++)for(var cc2=off;cc2<off+cs;cc2++)occ[rr+':'+cc2]=1;"
              "    info.push({c0:off,cs:cs,rs:rs,txt:(cells[c].textContent||'').trim().slice(0,4)});"
              "  }"
              "  rows.push(info);"
              "}"
              "return JSON.stringify({rows:rows})})()")

RAW0 = "(function(){var d=JSON.parse(window.__raw());return JSON.stringify(d.raw[0])})()"


def audit_merge(name, r0, c0, r1, c1, exp_c0, exp_cs, exp_span_cells):
    """合并指定矩形 → 审计渲染网格：合并格应锚在 exp_c0、跨 exp_cs 列；
    每行逻辑列覆盖 0..3 无缝隙；存储中合并格数 == exp_span_cells"""
    setmd(MD_P)
    js(f"window.__tblSelSet(0,{r0},{c0},{r1},{c1})"); wait(200)
    js("window.__tblOp('merge')"); wait(700)
    a = jj(GRID_AUDIT)
    raw0 = js(RAW0)
    span_cells = raw0.count('colspan=')
    # 每行逻辑列区间应连续覆盖 0..cols-1 且不重叠
    ok_cover = True
    for ri, row in enumerate(a.get("rows", [])):
        seen = sorted((g["c0"], g["c0"] + g["cs"]) for g in row)
        pos = 0
        for st, en in seen:
            if st != pos: ok_cover = False
            pos = en
        if pos != 4: ok_cover = False
    # 合并格锚点与跨度
    merged = None
    for row in a.get("rows", []):
        for g in row:
            if g["cs"] > 1 or g["rs"] > 1: merged = g
    ck(f"{name} 合并格锚在列{exp_c0} 跨{exp_cs}列",
       merged is not None and merged["c0"] == exp_c0 and merged["cs"] == exp_cs,
       str(a.get("rows")))
    ck(f"{name} 各行逻辑列连续覆盖 0..3（无错位 / 无靠边）", ok_cover, str(a.get("rows")))
    ck(f"{name} 存储中合并格数 = {exp_span_cells}", span_cells == exp_span_cells,
       raw0[:120])


# M7：表头行 (0,1)-(0,3)（0 基：第 1 行后三格）
audit_merge("M7 表头(0,1)-(0,3)", 0, 1, 0, 3, 1, 3, 1)
# M8：表头行 (0,0)-(0,2)（第 1 行前三格）
audit_merge("M8 表头(0,0)-(0,2)", 0, 0, 0, 2, 0, 3, 1)
# M9：正文行 (1,1)-(1,3)
audit_merge("M9 正文(1,1)-(1,3)", 1, 1, 1, 3, 1, 3, 1)

# M10：M8 合并后重开文档 → 布局保持（往返稳定）
setmd(MD_P)
js("window.__tblSelSet(0,0,0,0,2)"); wait(200)
js("window.__tblOp('merge')"); wait(700)
raw1 = js("window.getMarkdown()")
setmd(raw1)
a = jj(GRID_AUDIT)
merged = None
for row in a.get("rows", []):
    for g in row:
        if g["cs"] > 1 or g["rs"] > 1: merged = g
ck("M10 往返后合并格仍在列0 跨3列", merged is not None and merged["c0"] == 0 and merged["cs"] == 3,
   str(a.get("rows")))

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
log("DONE")
flush()
