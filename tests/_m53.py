# -*- coding: utf-8 -*-
"""m53 验证探针（v3.30.10 四项修复）：
S1  合并表冷启动拖合并格边线 → 被拖列 +50 / 右邻列 -50（总宽恒定，无整表缩放）
S1b 冷启动拖普通格边线 → 同样是被拖列 +50 / 右邻列 -50
S2  先整表缩放再拖内部边线 → 行为一致（列间转移）
S2r 行高拖拽 → 行高落盘
S3a 边缘内侧按合并格右边线（=表右边缘）→ 列宽拖拽（手柄不再抢占）
S3b 手柄上按下 → 整表缩放照常
S4  右键菜单动态显示：单格=拆分无合并、两格=合并无拆分、合并格=拆分+还原
S5  单元格内链接：管道 [t](url)、HTML <a>、加粗+链接组合
S6  单元格 "/" 菜单：仅显示 5 个支持项；插入列表/代码/图片/图表/公式
S7  悬浮栏：单元格内有「链接」+「＋插入」按钮
S8  快捷键路由：fence/math 插入，hr 无副作用
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m53.txt")
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
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


wait(3000)


def ready(timeout=20000):
    """页面就绪守卫：等 #editor 挂载且 window.setMarkdown 可用（冷启动偶发未就绪 → SNAP 取不到表）"""
    t0 = time.time()
    while (time.time() - t0) * 1000 < timeout:
        # 注意：JS String(true) === "true"（小写），比较必须统一大小写
        r = js("(function(){return String(!!(document.getElementById('editor') && window.setMarkdown))})()")
        if str(r).strip().lower() == "true":
            return True
        wait(300)
    return False


if not ready():
    log("FATAL 页面未就绪（#editor / setMarkdown 缺失）")
    print("\n".join(out))
    sys.exit(1)

MD_P = ("| A1 | B1 | C1 | D1 |\n| --- | --- | --- | --- |\n"
        "| A2 | B2 | C2 | D2 |\n| A3 | B3 | C3 | D3 |")
MD_L = "- 项目符号与内容文字"


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(700)


def raw0():
    r = js("window.__raw()")
    try:
        d = json.loads(r)
        return d.get("raw", [""])[0] if isinstance(d, dict) else str(r)
    except Exception:
        return str(r or "")


SNAP = ("(function(){"
        "var t=document.querySelector('.b-table table');"
        "if(!t)return JSON.stringify({none:1});"
        "var cw=[],cg=t.querySelectorAll('colgroup > col');"
        "for(var q=0;q<cg.length;q++){var m=(cg[q].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
        "cw.push(m?parseFloat(m[1]):null);}"
        "var rc=t.getBoundingClientRect();"
        "return JSON.stringify({tblW:Math.round(rc.width),style:t.getAttribute('style'),colW:cw})})()")

# 拖第 rIdx 行第 cIdx 个 DOM 格的右边线（dx 像素，分 n 步）
DRAG = ("(function(rIdx,cIdx,dx,n){"
        "try{"
        "var t=document.querySelector('.b-table table');"
        "if(!t)return 'notable';"
        "var trs=t.tBodies[0].rows;"
        "var cell=trs[rIdx].cells[cIdx];"
        "if(!cell)return 'nocell';"
        "var rc=cell.getBoundingClientRect();"
        "var x0=rc.right-1,y0=rc.top+rc.height/2;"
        "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
        "clientX:x0,clientY:y0}));"
        "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
        "buttons:1,clientX:x0+dx*i/n,clientY:y0}));}"
        "return 'held';"
        "}catch(e){return 'ERR:'+e.message}})")

DRAGROW = ("(function(rIdx,cIdx,dy,n){"
           "try{"
           "var t=document.querySelector('.b-table table');"
           "if(!t)return 'notable';"
           "var trs=t.tBodies[0].rows;"
           "var cell=trs[rIdx].cells[cIdx];"
           "if(!cell)return 'nocell';"
           "var rc=cell.getBoundingClientRect();"
           "var x0=rc.left+rc.width/2,y0=rc.bottom-1;"
           "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
           "clientX:x0,clientY:y0}));"
           "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
           "buttons:1,clientX:x0,clientY:y0+dy*i/n}));}"
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

CTXMENU_TMPL = ("(function(ri,ci){{"
                "var t=document.querySelector('.b-table table');"
                "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
                "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
                "var cell=trs[ri].cells[ci];var rc=cell.getBoundingClientRect();"
                "cell.dispatchEvent(new MouseEvent('contextmenu',{{bubbles:true,cancelable:true,"
                "clientX:rc.left+10,clientY:rc.top+10}}));"
                "var btns=document.querySelectorAll('#tblbar .tmi');var arr=[];"
                "for(var q=0;q<btns.length;q++)arr.push({{t:btns[q].title,d:btns[q].className.indexOf('dis')>=0}});"
                "return JSON.stringify(arr)}})({ri},{ci})")


def ctxmenu(ri, ci):
    return json.loads(js(CTXMENU_TMPL.format(ri=ri, ci=ci)))


def build_merged():
    setmd(MD_P)
    js("window.__tblSelSet(0,1,1,1,2)"); wait(200)
    js("window.__tblOp('merge')"); wait(700)


def cdiffs(a, b):
    return [(i, (b[i] or 0) - (a[i] or 0)) for i in range(min(len(a), len(b)))]


def one_col_plus50(ws, delta=50, tol=2):
    """冷启动断言：拖拽后恰好一列比其余列大 ~delta（其余列等宽）"""
    if not ws or len(ws) < 2: return False, str(ws)
    u = sorted(set(ws))
    if len(u) != 2: return False, str(ws)
    lo, hi = u
    if ws.count(lo) != len(ws) - 1: return False, str(ws)
    return abs((hi - lo) - delta) <= tol, str(ws)


def last_col_plus50(ws, delta=50, tol=3):
    """末列拖拽断言：末列比其余列的中位数大 ~delta（基线不一定严格等宽 / 基线缺失时用）"""
    if not ws or len(ws) < 2: return False, str(ws)
    rest = sorted(ws[:-1])
    base = rest[len(rest) // 2]
    return abs((ws[-1] - base) - delta) <= tol, str(ws)


def pair_transfer(ws, i, delta=50, tol=3):
    """列间转移断言：第 i 列 +delta / 第 i+1 列 -delta。
    冷启动时基线表可能还没有 colgroup（s0['colW'] 为空），故用「其余列的中位数」当基准。"""
    if not ws or len(ws) <= i + 1: return False, str(ws)
    rest = [w for k, w in enumerate(ws) if k not in (i, i + 1) and isinstance(w, (int, float))]
    if not rest: return False, str(ws)
    base = sorted(rest)[len(rest) // 2]
    return (abs((ws[i] - base) - delta) <= tol and abs((ws[i + 1] - base) + delta) <= tol), str(ws)


SELTEXT = ("(function(needle){"
           "var root=document.querySelector('#editor .blk');"
           "var w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);"
           "var tn=null;"
           "while(w.nextNode()){if(w.currentNode.nodeValue.indexOf(needle)>=0){tn=w.currentNode;break;}}"
           "if(!tn)return 'notext';"
           "var i0=tn.nodeValue.indexOf(needle);"
           "var rg=document.createRange();rg.setStart(tn,i0);rg.setEnd(tn,i0+needle.length);"
           "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
           "return 'sel'})")

# ==================== S1: 冷启动拖合并格边线 ====================
# 语义（v3.30.14 起，与 _m60 Z1/Z2 一致）：拖内部竖边线 = 宽度在「被拖列 ↔ 右邻列」之间
# 转移，表格总宽恒定（仅当右邻列压到 COL_MIN 后才允许总宽变化）。
build_merged()
s0 = jj(SNAP)
r = js(DRAG + "(1,1,50,10)")
js(UP); wait(700)
s1 = jj(SNAP)
log(f"S1 {s0['colW']}->{s1['colW']} drag={r}")
ck("S1 拖合并格边线总宽不变（列间转移）", abs(s1["tblW"] - s0["tblW"]) <= 2, f"{s0['tblW']}->{s1['tblW']}")
ok, det = pair_transfer(s1["colW"], 1)
ck("S1 被拖列 +50 / 右邻列 -50", ok, det)

# ==================== S1b: 冷启动拖普通格边线 ====================
build_merged()
s0 = jj(SNAP)
r = js(DRAG + "(1,0,50,10)")
js(UP); wait(700)
s1 = jj(SNAP)
ok, det = pair_transfer(s1["colW"], 0)
ck("S1b 普通格边线 被拖列 +50 / 右邻列 -50", ok, det)

# ==================== S2: 先整表缩放再拖内部边线 ====================
build_merged()
js(OUTER + "(80,10)")
js(UP); wait(700)
sA = jj(SNAP)
r = js(DRAG + "(1,1,50,10)")
js(UP); wait(700)
sB = jj(SNAP)
d = cdiffs(sA["colW"], sB["colW"])
mv = [x for x in d if abs(x[1]) > 2]
ck("S2 整表缩放后拖内部边线仍是 被拖列 +50 / 右邻列 -50",
   len(mv) == 2 and abs(mv[0][1] - 50) <= 2 and abs(mv[0][1] + mv[1][1]) <= 2, str(d))

# ==================== S2r: 行高拖拽 ====================
build_merged()
r = js(DRAGROW + "(0,0,40,8)")
js(UP); wait(700)
ck("S2r 行高拖拽落盘(height 样式)", r == "held" and "height:" in raw0(), str(r))

# ==================== S3: 边缘手柄不抢占 / 手柄整表缩放照常 ====================
setmd(MD_P)
js("window.__tblSelSet(0,1,2,1,3)"); wait(200)
js("window.__tblOp('merge')"); wait(700)     # 合并行末两格：合并格右边线=表右边缘
e0 = jj(SNAP)
EDGE_IN = ("(function(){"
           "try{"
           "var t=document.querySelector('.b-table table');"
           "var rc=t.getBoundingClientRect();"
           "var cell=t.tBodies[0].rows[0].cells[2];"
           "var cr=cell.getBoundingClientRect();"
           "var x0=cr.right-2,y0=rc.top+rc.height/2;"
           "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
           "clientX:x0,clientY:y0}));"
           "for(var i=1;i<=10;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
           "buttons:1,clientX:x0+50*i/10,clientY:y0}));}"
           "return 'held';"
           "}catch(e){return 'ERR:'+e.message}})()")
r = js(EDGE_IN)
js(UP); wait(700)
e1 = jj(SNAP)
# 注意：此处基线是管道表（无 colgroup，e0["colW"] 为空），无法做差值比较，
# 故用「末列比其余列中位数大 50」判定，不用 one_col_plus50（它要求恰好两种宽度值）。
ok, det = last_col_plus50(e1["colW"])
ck("S3a 边缘内侧按边线=列宽拖拽(仅末列+50)", ok, f"drag={r} {det}")

EDGE_OUT = ("(function(){"
            "try{"
            "var t=document.querySelector('.b-table table');"
            "var rc=t.getBoundingClientRect();"
            "var x0=rc.right+2,y0=rc.top+rc.height/2;"
            "var h=document.querySelector('#rzframe .rz.e');"
            "if(!h)return 'nohandle';"
            "var hr=h.getBoundingClientRect();"
            "if(!(x0>=hr.left&&x0<=hr.right&&y0>=hr.top&&y0<=hr.bottom))return 'handle-not-at';"
            "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
            "clientX:x0,clientY:y0}));"
            "for(var i=1;i<=10;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
            "buttons:1,clientX:x0+50*i/10,clientY:y0}));}"
            "return 'held';"
            "}catch(e){return 'ERR:'+e.message}})()")
r = js(EDGE_OUT)
js(UP); wait(700)
e2 = jj(SNAP)
ck("S3b 手柄上按下=整表缩放照常", r == "held" and e2["tblW"] > e1["tblW"] + 20,
   f"{e1['tblW']}->{e2['tblW']} drag={r}")

# ==================== S4: 右键菜单动态显示 ====================
setmd(MD_P)
js("window.__tblSelSet(0,0,0,0,0)"); wait(200)
m = ctxmenu(0, 0)
md = {x["t"]: x["d"] for x in m}
ck("S4A 单格：合并单元格不显示", "合并单元格" not in md, str(list(md)))
ck("S4A 单格：拆分显示且可用", "拆分单元格（选择行 × 列）" in md and md["拆分单元格（选择行 × 列）"] is False)
ck("S4A 单格：还原不显示", "还原单元格（拆回原格）" not in md)
js("window.__tblSelSet(0,0,0,0,1)"); wait(200)
m = ctxmenu(0, 0)
md = {x["t"]: x["d"] for x in m}
ck("S4B 两格：合并显示且可用", "合并单元格" in md and md["合并单元格"] is False)
ck("S4B 两格：拆分不显示", "拆分单元格（选择行 × 列）" not in md)
js("window.__tblOp('merge')"); wait(600)
m = ctxmenu(0, 0)
md = {x["t"]: x["d"] for x in m}
ck("S4C 合并格：合并不显示", "合并单元格" not in md)
ck("S4C 合并格：拆分显示且可用", "拆分单元格（选择行 × 列）" in md and md["拆分单元格（选择行 × 列）"] is False)
ck("S4C 合并格：还原显示", "还原单元格（拆回原格）" in md)

# ==================== S5: 单元格内链接 ====================
setmd(MD_P)
r = js(SELTEXT + '("B2")')
ck("S5 选中B2", r == "sel", str(r))
js("window.__applyFloat('link')"); wait(400)
ck("S5 链接弹层打开", jj("window.__linkPop ? window.__linkPop() : '{}'").get("show") is True)
js("document.getElementById('link-url').value='https://example.com';"
   "document.getElementById('link-ok').click()"); wait(700)
ck("S5 管道表写入 [B2](url)", "[B2](https://example.com)" in raw0(), raw0()[:120])
ck("S5 渲染为 <a>", js("!!document.querySelector('#editor .b-table td a[href]')") is True)
# 组合：先加粗后链接（对另一格）
r = js(SELTEXT + '("A2")')
js("window.__applyFloat('bold')"); wait(600)
r = js(SELTEXT + '("A2")')
js("window.__applyFloat('link')"); wait(400)
js("document.getElementById('link-url').value='https://b.cn';"
   "document.getElementById('link-ok').click()"); wait(700)
ck("S5 加粗后链接 **[A2](url)**", "**[A2](https://b.cn)**" in raw0(), raw0()[:150])
# HTML 表：<a> 标签
setmd(MD_P)
js("window.__tblSelSet(0,1,1,1,2)"); wait(200)
js("window.__tblOp('merge')"); wait(600)
r = js(SELTEXT + '("B2")')
js("window.__applyFloat('link')"); wait(400)
js("document.getElementById('link-url').value='https://c.cn';"
   "document.getElementById('link-ok').click()"); wait(700)
ck("S5 HTML表写入 <a href>", '<a href="https://c.cn">B2</a>' in raw0(), raw0()[:200])
ck("S5 HTML表渲染 <a>", js("!!document.querySelector('#editor .b-table td a[href]')") is True)

# ==================== S7: 悬浮栏按钮（链接 + ＋插入） ====================
setmd(MD_P)
r = js(SELTEXT + '("B2")'); wait(400)
fb = jj("(function(){var b=document.querySelectorAll('#floatbar button');var t=[];"
        "for(var i=0;i<b.length;i++)t.push(b[i].title);return JSON.stringify(t)})()")
ck("S7 单元格内悬浮栏有「链接」", "链接" in fb, str(fb))
ck("S7 单元格内悬浮栏有「＋插入」", any("插入" in x for x in fb), str(fb))

# ==================== S6: 单元格 "/" 菜单与块级插入 ====================
# 空单元格触发表：B3 为空（"/" 仅空格触发）
MD_E = ("| A1 | B1 | C1 | D1 |\n| --- | --- | --- | --- |\n"
        "| A2 | B2 | C2 | D2 |\n| A3 |  | C3 | D3 |")
setmd(MD_E)
SLASH_OPEN = ("(function(){"
              "try{"
              "var td=document.querySelectorAll('.b-table td')[5];"   # B3（空）
              "if(td.textContent.trim()!=='')return 'notempty';"
              "td.focus();"
              "td.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
              "var its=document.querySelectorAll('#slashmenu .si');var arr=[];"
              "for(var i=0;i<its.length;i++)arr.push(its[i].querySelector('.lb').textContent.trim());"
              "return JSON.stringify(arr);"
              "}catch(e){return 'ERR:'+e.message}})()")
items = json.loads(js(SLASH_OPEN))
log(f"S6 菜单项={items}")
ck("S6 菜单仅5个支持项", items == ["列表", "代码块", "图片", "图表", "公式"], str(items))


def slash_pick(label):
    """点击斜杠菜单指定标签项"""
    code = ("(function(lb){"
            "var its=document.querySelectorAll('#slashmenu .si');"
            "for(var i=0;i<its.length;i++){if(its[i].querySelector('.lb').textContent.trim()===lb){"
            "its[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok';}}"
            "return 'nomatch'})(" + json.dumps(label, ensure_ascii=False) + ")")
    return js(code)


def sub_pick(label):
    code = ("(function(lb){"
            "var its=document.querySelectorAll('#submenu .si');"
            "for(var i=0;i<its.length;i++){if(its[i].querySelector('.lb').textContent.trim()===lb){"
            "its[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok';}}"
            "return 'nomatch'})(" + json.dumps(label, ensure_ascii=False) + ")")
    return js(code)


# 6a 列表：图表二级展开 → 无序列表
r = slash_pick("列表")
r2 = sub_pick("无序列表")
wait(700)
ck("S6a 插入列表（td 内 ul li）", js("!!document.querySelector('.b-table td ul li')") is True,
   f"{r}/{r2}")
ck("S6a 存储升级为 HTML 表含 <ul>", "<ul><li>" in raw0(), raw0()[:150])

# 6b 代码块
setmd(MD_E)
js(SLASH_OPEN)
r = slash_pick("代码块")
wait(700)
ck("S6b 插入代码块（td 内 pre code）", js("!!document.querySelector('.b-table td pre code')") is True,
   str(r))
ck("S6b 存储 <pre><code>", "<pre><code>" in raw0(), raw0()[:150])

# 6c 图片（URL 弹层）
setmd(MD_E)
js(SLASH_OPEN)
r = slash_pick("图片")
wait(400)
js("document.getElementById('link-url').value='https://img.example.com/a.png';"
   "document.getElementById('link-ok').click()"); wait(700)
ck("S6c 插入图片（td 内 img）", js("!!document.querySelector('.b-table td img[src]')") is True, str(r))
ck("S6c 存储 <img src>", '<img src="https://img.example.com/a.png"' in raw0(), raw0()[:150])

# 6d 图表（mermaid 渲染）
setmd(MD_E)
js(SLASH_OPEN)
r = slash_pick("图表")
wait(400)
r2 = sub_pick("流程图")
wait(400)
ok6d = None
for _ in range(24):
    wait(500)
    ok6d = jj("(function(){var m=document.querySelector('.b-table td .cell-mmd');"
              "return JSON.stringify({has:!!m,svg:!!(m&&m.querySelector('svg'))})})()")
    if ok6d.get("svg"):
        break
ck("S6d 插入图表并渲染 SVG", ok6d and ok6d.get("svg") is True, str(ok6d))
ck("S6d 存储 cell-mmd data-src", "cell-mmd" in raw0(), raw0()[:150])

# 6e 公式
setmd(MD_E)
js(SLASH_OPEN)
r = slash_pick("公式")
wait(400)
r2 = sub_pick("分式")
wait(700)
m6 = jj("(function(){var m=document.querySelector('.b-table td .cell-math .katex');"
        "return JSON.stringify({has:!!m})})()")
ck("S6e 插入公式并渲染 KaTeX", m6.get("has") is True, f"{r}/{r2}")
ck("S6e 存储 cell-math data-tex", "cell-math" in raw0(), raw0()[:150])

# 6f 有序列表（格内有文字 → 逐行转 li 不适用单行；验证空格占位）
setmd(MD_E)
js(SLASH_OPEN)
r = slash_pick("列表")
r2 = sub_pick("有序列表")
wait(700)
ck("S6f 插入有序列表（td 内 ol li）", js("!!document.querySelector('.b-table td ol li')") is True,
   f"{r}/{r2}")

# ==================== S8: 快捷键路由 ====================
setmd(MD_P)
FOCUS_CELL = ("(function(){var td=document.querySelectorAll('.b-table td')[5];td.focus();return 'ok'})()")
js(FOCUS_CELL)
js('window.cmd("fence")'); wait(700)
ck("S8 Ctrl+Shift+K 单元格内插入代码块", js("!!document.querySelector('.b-table td pre code')") is True)
setmd(MD_P)
js(FOCUS_CELL)
js('window.cmd("math")'); wait(700)
ck("S8 Ctrl+Shift+M 单元格内插入公式", js("!!document.querySelector('.b-table td .cell-math')") is True)
setmd(MD_P)
js(FOCUS_CELL)
r0s = raw0()
js('window.cmd("hr")'); wait(500)
ck("S8 不支持的 hr 无副作用", raw0() == r0s, raw0()[:80])

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
out.append("DONE")
flush()
print("done")
