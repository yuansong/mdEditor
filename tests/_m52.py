# -*- coding: utf-8 -*-
"""m52 验证探针（v3.30.9 六项修复）：
S1 拆分后边框完整（3x4 表 (1,1) 拆 2x2，逐格校验收边类与计算样式一致）
S2 右键菜单：合并/拆分两个独立项恒显示（不可用置灰），还原仅在合并格出现
S3 合并后拖合并格边线：只有被拖列变、总宽跟随、蓝框在
S4 蓝框滚动同步：滚动后缩放框仍覆盖表格实际区域
S5 单元格内文字选中与格式化（管道表 ** 标记 + HTML 表 <em> 标签，可切换）
S6 列表格式组合状态：mark→link、bold→link、strike→mark、code→mark（末项 v3.31.2 起按 FMT-1 守卫「拒绝」）
S7 代码块首行右上字母 C（::after 语言徽标已移除）"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m52.txt")
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


wait(2500)

MD_P = ("| A1 | B1 | C1 | D1 |\n| --- | --- | --- | --- |\n"
        "| A2 | B2 | C2 | D2 |\n| A3 | B3 | C3 | D3 |")
MD_L = "- 项目符号与内容文字"
MD_C = "```C\nint main(){return 0;}\n```"


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


def editidx():
    r = js("window.__raw()")
    try:
        d = json.loads(r)
        return d.get("editIdx", -2)
    except Exception:
        return -2


SNAP = ("(function(){var t=document.querySelector('.b-table table');"
        "if(!t)return JSON.stringify({none:1});"
        "var cw=[],cg=t.querySelectorAll('colgroup > col');"
        "for(var q=0;q<cg.length;q++){var m=(cg[q].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
        "cw.push(m?parseFloat(m[1]):null);}"
        "var rc=t.getBoundingClientRect();"
        "return JSON.stringify({tblW:Math.round(rc.width),colW:cw})})()")

MERGED_DRAG = ("(function(dx,n){"
               "var t=document.querySelector('.b-table table');"
               "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
               "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
               "var cell=trs[1].cells[1];var rc=cell.getBoundingClientRect();"
               "var x0=rc.right-1,y0=rc.top+rc.height/2;"
               "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
               "clientX:x0,clientY:y0}));"
               "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
               "buttons:1,clientX:x0+dx*i/n,clientY:y0}));}"
               "return 'held'})")

UP = ("document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
      "clientX:0,clientY:0}));'up'")

# 选中文本节点里的一段文字（单元格 / 列表通用）
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

BORDERS = ("(function(){"
           "var t=document.querySelector('.b-table table');"
           "if(!t)return JSON.stringify({none:1});"
           "var g=window.__core.buildTableGrid(t);"
           "var seen=[],cells=[];"
           "for(var r=0;r<g.grid.length;r++){for(var c=0;c<g.grid[r].length;c++){"
           "var ref=g.grid[r][c];if(!ref||seen.indexOf(ref.el)!==-1)continue;seen.push(ref.el);"
           "var cs=getComputedStyle(ref.el);"
           "cells.push({r0:ref.r0,c0:ref.c0,rs:ref.rs,cs2:ref.cs,"
           "brs:cs.borderRightStyle,bbs:cs.borderBottomStyle});}}"
           "return JSON.stringify({cols:g.cols,rows:g.rows,cells:cells})})()")

FRAMEPOS = ("(function(){"
            "var t=document.querySelector('.b-table table');"
            "var box=document.querySelector('#rzframe .rbox');"
            "if(!t||!box)return JSON.stringify({none:1});"
            "var a=t.getBoundingClientRect(),b=box.getBoundingClientRect();"
            "return JSON.stringify({tbl:{l:a.left,tp:a.top,w:a.width,h:a.height},"
            "box:{l:b.left,tp:b.top,w:b.width,h:b.height}})})()")

SCROLL = ("(function(){"
          "var t=document.querySelector('.b-table table');"
          "var el=t;var sc=null;"
          "while(el&&el!==document.documentElement){"
          "if(el.scrollHeight>el.clientHeight+4&&el.clientHeight>60){sc=el;break;}el=el.parentElement;}"
          "if(sc){sc.scrollTop+=200;return 'scrolled '+sc.tagName+'.'+sc.className;}"
          "window.scrollBy(0,200);return 'scrolled window'})()")


# ---------- S1: 拆分后边框完整 ----------
setmd(MD_P)
js("window.__tblSelSet(0,1,1,1,1)"); wait(300)
r = js("window.__tblSplitInto(0,2,2)"); wait(700)
log(f"S1 split={r} raw={raw0()[:160]}")
b = jj(BORDERS)
log(f"S1 cols={b.get('cols')} rows={b.get('rows')} ncells={len(b.get('cells', []))}")
ck("S1 网格 4x5", b.get("cols") == 5 and b.get("rows") == 4, f"{b.get('cols')}x{b.get('rows')}")
ok = True; bad = []
for cd in b.get("cells", []):
    rightEdge = cd["c0"] + cd["cs2"] - 1 == b["cols"] - 1
    bottomEdge = cd["r0"] + cd["rs"] - 1 == b["rows"] - 1
    if (cd["brs"] == "none") != rightEdge: ok = False; bad.append(("R", cd))
    if (cd["bbs"] == "none") != bottomEdge: ok = False; bad.append(("B", cd))
ck("S1 全部单元格收边与网格位置一致", ok and not bad, str(bad[:3]))
prev = [cd for cd in b.get("cells", []) if cd["r0"] == 2 and cd["c0"] == 2]
ck("S1 原缺线格 (2,2) 有右边框", prev and prev[0]["brs"] != "none",
   str(prev[0]["brs"] if prev else "missing"))

# ---------- S2: 右键菜单两个独立项 ----------
setmd(MD_P)
js("window.__tblSelSet(0,0,0,0,0)"); wait(200)
m = ctxmenu(1, 0)          # 右键所选格本身（选区外右键会重置为单选）
md = {x["t"]: x["d"] for x in m}
log(f"S2A 单格菜单={json.dumps(m, ensure_ascii=False)}")
ck("S2A 合并单元格隐藏（v3.30.10 动态菜单）", "合并单元格" not in md)
ck("S2A 拆分单元格存在且可用", "拆分单元格（选择行 × 列）" in md and md["拆分单元格（选择行 × 列）"] is False)
js("window.__tblSelSet(0,0,0,0,1)"); wait(200)
m = ctxmenu(0, 0)          # 右键选区内格 → 保留多选
md = {x["t"]: x["d"] for x in m}
log(f"S2B 两格菜单={json.dumps(m, ensure_ascii=False)}")
ck("S2B 合并单元格可用", "合并单元格" in md and md["合并单元格"] is False)
ck("S2B 拆分单元格隐藏（多格不可拆）", "拆分单元格（选择行 × 列）" not in md)
js("window.__tblOp('merge')"); wait(500)
m = ctxmenu(0, 0)          # 右键合并格（S2B 合并的是表头 (0,0)-(0,1)）
md = {x["t"]: x["d"] for x in m}
log(f"S2C 合并格菜单={json.dumps(m, ensure_ascii=False)}")
ck("S2C 合并隐藏 / 拆分显示（v3.30.10 动态菜单）",
   "合并单元格" not in md and "拆分单元格（选择行 × 列）" in md)
ck("S2C 还原单元格出现", "还原单元格（拆回原格）" in md)

# ---------- S3: 合并后拖合并格边线 ----------
setmd(MD_P)
js("window.__tblOp('noop')")   # 占位：下面用一次 0px 列拖拽让 colgroup 物化
COL_DRAG0 = ("(function(){"
             "var t=document.querySelector('.b-table table');"
             "var cell=t.tHead.rows[0].cells[0];var rc=cell.getBoundingClientRect();"
             "var x0=rc.right-1,y0=rc.top+rc.height/2;"
             "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
             "clientX:x0,clientY:y0}));"
             "document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,buttons:1,"
             "clientX:x0,clientY:y0}));"
             "document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
             "clientX:x0,clientY:y0}));return 'ok'})()")
js(COL_DRAG0); wait(500)
js("window.__tblSelSet(0,1,1,1,2)"); wait(200)
js("window.__tblOp('merge')"); wait(600)
s0 = jj(SNAP)
r = js(MERGED_DRAG + "(50,10)")
s1 = jj(SNAP)
js(UP); wait(600)
s2 = jj(SNAP)
log(f"S3 w {s0['tblW']}->{s2['tblW']} colW {s0['colW']}->{s2['colW']} drag={r}")
# v3.30.14 起内部列边线改为「宽度在 被拖列 ↔ 右邻列 之间转移，总宽不变」
# （Typora / Word 语义；旧的「拖一条边线整表跟着伸缩」v3.30.6 语义已退役）
ck("S3 内部边线总宽不变（v3.30.14 语义）", abs(s2["tblW"] - s0["tblW"]) <= 2,
   f"{s0['tblW']}->{s2['tblW']}")
diffs = [(i, (s2["colW"][i] or 0) - (s0["colW"][i] or 0)) for i in range(min(len(s0["colW"]), len(s2["colW"])))]
moved = [d for d in diffs if abs(d[1]) > 2]
ck("S3 被拖列 +50 且右邻列 -50（宽度转移）",
   len(moved) == 2 and moved[0][1] > 0 and abs(moved[1][1] + moved[0][1]) <= 2,
   str(diffs))
fs = jj("window.__rzShow ? window.__rzShow() : JSON.stringify({frame:'nohook'})")
ck("S3 缩放框在", fs.get("frame") is True, str(fs))

# ---------- S4: 蓝框滚动同步 ----------
p0 = jj(FRAMEPOS)
sr = js(SCROLL); wait(400)
p1 = jj(FRAMEPOS)
log(f"S4 scroll={sr} tbl@{p1['tbl']['l']:.0f},{p1['tbl']['tp']:.0f} box@{p1['box']['l']:.0f},{p1['box']['tp']:.0f}")
dx = abs(p1["tbl"]["l"] - p1["box"]["l"]); dy = abs(p1["tbl"]["tp"] - p1["box"]["tp"])
dw = abs(p1["tbl"]["w"] - p1["box"]["w"]); dh = abs(p1["tbl"]["h"] - p1["box"]["h"])
ck("S4 滚动后蓝框覆盖表格(≤2px)", max(dx, dy, dw, dh) <= 2,
   f"d=({dx:.1f},{dy:.1f},{dw:.1f},{dh:.1f})")

# ---------- S5: 单元格内文字选中与格式化 ----------
setmd(MD_P)
r = js(SELTEXT + '("B2")')
ck("S5 选中B2", r == "sel", str(r))
js("window.__applyFloat('bold')"); wait(600)
ck("S5 加粗写入 **B2**", "**B2**" in raw0(), raw0()[:120])
r = js(SELTEXT + '("B2")')
js("window.__applyFloat('bold')"); wait(600)
ck("S5 再次加粗=取消", "**B2**" not in raw0(), raw0()[:120])
r = js(SELTEXT + '("A2")')
js("window.__applyFloat('mark')"); wait(600)
ck("S5 高亮写入 ==A2==", "==A2==" in raw0(), raw0()[:120])
# HTML 表格：<em> 标签
setmd(MD_P)
js("window.__tblSelSet(0,1,1,1,2)"); wait(200)
js("window.__tblOp('merge')"); wait(600)
r = js(SELTEXT + '("B2")')
js("window.__applyFloat('italic')"); wait(600)
ck("S5 HTML表写入 <em>B2</em>", "<em>B2</em>" in raw0(), raw0()[:200])

# ---------- S6: 列表格式组合状态 ----------
setmd(MD_L)
r = js(SELTEXT + '("内容文字")')
js("window.__applyFloat('mark')"); wait(600)
ck("S6 列表高亮 ==内容文字==", "==内容文字==" in raw0(), raw0()[:80])
ck("S6 保持渲染态(editIdx=-1)", editidx() == -1, str(editidx()))
ck("S6 列表仍渲染 li", js("!!document.querySelector('#editor .blk li')") is True)
r = js(SELTEXT + '("内容文字")')
js("window.__applyFloat('link')"); wait(400)
js("document.getElementById('link-url').value='https://example.com';"
   "document.getElementById('link-ok').click()"); wait(600)
ck("S6 高亮后加链接 ==[内容文字](url)==", "==[内容文字](https://example.com)==" in raw0(),
   raw0()[:120])
ck("S6 链接后保持渲染态", editidx() == -1, str(editidx()))
li_dbg = js("(function(){var li=document.querySelector('#editor .blk li');"
            "return li ? li.innerHTML : 'noli'})()")
log(f"S6 li={li_dbg}")
log("S6 render=" + str(js("(function(){return window.__core.inlineHTML("
                          "'==[\\u5185\\u5bb9\\u6587\\u5b57](https://example.com)==')})()")))
ck("S6 列表 li 仍渲染且无脏 == 可见",
   js("(function(){var li=document.querySelector('#editor .blk li');"
      "return !!li && li.textContent.indexOf('==')===-1 && !!li.querySelector('mark a')})()") is True)
setmd(MD_L)
r = js(SELTEXT + '("内容文字")')
js("window.__applyFloat('bold')"); wait(600)
r = js(SELTEXT + '("内容文字")')
js("window.__applyFloat('link')"); wait(400)
js("document.getElementById('link-url').value='https://b.cn';"
   "document.getElementById('link-ok').click()"); wait(600)
ck("S6 加粗后加链接 **[内容文字](url)**", "**[内容文字](https://b.cn)**" in raw0(), raw0()[:120])
setmd(MD_L)
r = js(SELTEXT + '("内容文字")')
js("window.__applyFloat('strike')"); wait(600)
r = js(SELTEXT + '("内容文字")')
js("window.__applyFloat('mark')"); wait(600)
ck("S6 删除线后高亮 ~~==文字==~~", "~~==内容文字==~~" in raw0(), raw0()[:120])
setmd(MD_L)
r = js(SELTEXT + '("内容文字")')
js("window.__applyFloat('code')"); wait(600)
r = js(SELTEXT + '("内容文字")')
js("window.__applyFloat('mark')"); wait(600)
ck("S6 行内代码后高亮被拒（v3.31.2 FMT-1：行内码内拒绝叠加标记）",
   raw0().strip() == "- 项目符号与`内容文字`", raw0()[:120])

# ---------- S7: 代码块首行右上字母 C ----------
setmd(MD_C)
s7 = jj("(function(){var p=document.querySelector('.blk pre.fence');"
        "if(!p)return JSON.stringify({none:1});"
        "var cs=getComputedStyle(p,'::after');"
        "var btn=document.querySelector('.codebar .lang-btn');"
        "return JSON.stringify({content:cs.content,lang:btn?btn.textContent:null})})()")
ck("S7 语言徽标已移除", s7.get("content") in ("none", "normal"), str(s7.get("content")))
ck("S7 代码栏仍显示语言 C", s7.get("lang") == "C", str(s7.get("lang")))

# ---------- S8: mermaid 校验失败 → 显示源码 ----------
setmd("```mermaid\ngraph XYZ\nA-->B\n```")
ok8 = None
for _ in range(24):                      # 引擎懒加载 + 350ms 重试，最多等 ~12s
    wait(500)
    ok8 = jj("(function(){var m=document.querySelector('.mermaidblock');"
             "if(!m)return JSON.stringify({none:1});"
             "var pre=m.querySelector('.mmd-src-show');"
             "var err=m.querySelector('.mmd-err');"
             "return JSON.stringify({src:pre?pre.textContent:null,"
             "tip:err?err.textContent.slice(0,60):null,"
             "hasSvg:!!m.querySelector('svg')})})()")
    if ok8.get("src") is not None or ok8.get("hasSvg"):
        break
log(f"S8 mermaid={json.dumps(ok8, ensure_ascii=False)}")
ck("S8 校验失败显示源码", isinstance(ok8.get("src"), str) and "graph XYZ" in ok8["src"],
   str(ok8.get("src"))[:60])
ck("S8 提示含失败原因", isinstance(ok8.get("tip"), str) and "校验" in ok8["tip"],
   str(ok8.get("tip")))
ck("S8 无 SVG（未静默成功）", not ok8.get("hasSvg"))
setmd("```mermaid\ngraph TD\nA-->B\n```")
ok8b = None
for _ in range(24):
    wait(500)
    ok8b = jj("(function(){var m=document.querySelector('.mermaidblock');"
              "if(!m)return JSON.stringify({none:1});"
              "return JSON.stringify({hasSvg:!!m.querySelector('svg'),"
              "src:!!m.querySelector('.mmd-src-show')})})()")
    if ok8b.get("hasSvg") or ok8b.get("src"):
        break
ck("S8 合法图表正常渲染不受影响", ok8b.get("hasSvg") is True, str(ok8b))

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
out.append("DONE")
flush()
print("done")
