# -*- coding: utf-8 -*-
"""v3.30.5 探针：锚点-指针矩形模型 边界情况专项。
C1 单击不拖 → 单格不误选；C2 拖出表格边界 → 冻结 + 表外释放保持；
C3 出界后回表 → 恢复更新（矩形 = 锚点 ∪ 当前格）；C4 拖远后回到锚点格 → 收缩回单格；
C5 拖入相邻表格 → 不串台（冻结）；C6 快甩单步跳格 → 矩形直达（无插值依赖）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m30b.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
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


def sel():
    return jj("window.__tblSel()")


def st():
    return jj("window.__tblDragState()")


wait(2500)

MD = ("| A | B | C |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |\n| 7 | 8 | 9 |")
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)


def cell_center(r, c):
    d = jj("(function(){var t=document.querySelector('.b-table table');"
           "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
           "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
           "var el=trs[" + str(r) + "].cells[" + str(c) + "];"
           "var rc=el.getBoundingClientRect();"
           "return JSON.stringify({x:rc.left+rc.width/2,y:rc.top+rc.height/2})})()")
    return d.get("x"), d.get("y")


def blank_point():
    """表格正下方 40px（出界点：不落在任何单元格上）"""
    d = jj("(function(){var t=document.querySelector('.b-table table');"
           "var rc=t.getBoundingClientRect();"
           "return JSON.stringify({x:rc.left+rc.width/2,y:rc.bottom+40,"
           "hit:(document.elementFromPoint(rc.left+rc.width/2,rc.bottom+40)||{}).tagName})})()")
    return d


def md_down(r, c):
    x, y = cell_center(r, c)
    return js(f"(function(){{var t=document.querySelector('.b-table table');"
              f"var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
              f"var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
              f"var el=trs[{r}].cells[{c}];el.dispatchEvent(new MouseEvent('mousedown',"
              f"{{bubbles:true,cancelable:true,detail:1,buttons:1,clientX:{x},clientY:{y}}}));"
              f"return 'down'}})()")


def mv(r, c):
    x, y = cell_center(r, c)
    return js(f"(function(){{var t=document.querySelector('.b-table table');"
              f"var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
              f"var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
              f"var el=trs[{r}].cells[{c}];el.dispatchEvent(new MouseEvent('mousemove',"
              f"{{bubbles:true,cancelable:true,buttons:1,clientX:{x},clientY:{y}}}));"
              f"return 'mv'}})()")


def mv_blank():
    d = blank_point()
    x, y = d.get("x"), d.get("y")
    return js(f"document.dispatchEvent(new MouseEvent('mousemove',"
              f"{{bubbles:true,cancelable:true,buttons:1,clientX:{x},clientY:{y}}}));'blank'")


def up(r=None, c=None):
    if r is None:
        d = blank_point()
        x, y = d.get("x"), d.get("y")
        return js(f"document.dispatchEvent(new MouseEvent('mouseup',"
                  f"{{bubbles:true,cancelable:true,buttons:0,clientX:{x},clientY:{y}}}));'up'")
    x, y = cell_center(r, c)
    return js(f"(function(){{var t=document.querySelector('.b-table table');"
              f"var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
              f"var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
              f"var el=trs[{r}].cells[{c}];el.dispatchEvent(new MouseEvent('mouseup',"
              f"{{bubbles:true,cancelable:true,buttons:0,clientX:{x},clientY:{y}}}));"
              f"return 'up'}})()")


# ---------- C1: 单击不拖（mousedown → mouseup 同点，无 mousemove）----------
md_down(1, 1)
up(1, 1)
wait(200)
s = sel()
check("C1 单击不拖 → 单格不误选",
      s.get("r0") == 1 and s.get("r1") == 1 and s.get("c0") == 1 and s.get("c1") == 1,
      json.dumps(s, ensure_ascii=False))

# ---------- C2: 拖到 (1,2) 扩两格 → 拖出表外 → 冻结 → 表外释放保持 ----------
md_down(1, 1)
mv(1, 2)
wait(150)
s_exp = sel()
mv_blank()
wait(150)
s_frozen = sel()
up()
wait(200)
s_final = sel()
check("C2 拖出表格边界 → 冻结在最后有效矩形，表外释放不误扩",
      s_exp.get("c1") == 2 and s_frozen == s_exp and s_final == s_exp,
      "exp=" + json.dumps(s_exp, ensure_ascii=False) +
      " frozen=" + json.dumps(s_frozen, ensure_ascii=False) +
      " final=" + json.dumps(s_final, ensure_ascii=False))

# ---------- C3: 出界后回到表内 → 恢复更新（矩形 = 锚点 ∪ 当前格）----------
md_down(1, 1)
mv(1, 2)
mv_blank()
mv(2, 0)
wait(150)
s = sel()
up(2, 0)
wait(200)
s2 = sel()
check("C3 出界回表 → 恢复为锚点∪当前格（1..2 行 × 0..1 列）",
      s.get("r0") == 1 and s.get("r1") == 2 and s.get("c0") == 0 and s.get("c1") == 1
      and s2 == s,
      "mv=" + json.dumps(s, ensure_ascii=False) + " up=" + json.dumps(s2, ensure_ascii=False))

# ---------- C4: 拖远后回到锚点格 → 实时收缩回单格 ----------
md_down(1, 1)
mv(2, 2)
wait(150)
s_big = sel()
mv(1, 1)
wait(150)
s_back = sel()
up(1, 1)
wait(200)
s_fin = sel()
check("C4 拖回锚点格 → 实时收缩回单格",
      s_big.get("r1") == 2 and s_big.get("c1") == 2
      and s_back.get("r0") == 1 and s_back.get("r1") == 1
      and s_back.get("c0") == 1 and s_back.get("c1") == 1 and s_fin == s_back,
      "big=" + json.dumps(s_big, ensure_ascii=False) +
      " back=" + json.dumps(s_back, ensure_ascii=False))

# ---------- C5: 拖入相邻表格 → 不串台（冻结在原表）----------
MD2 = ("| A | B |\n| --- | --- |\n| 1 | 2 |\n\n中转段落\n\n| C | D |\n| --- | --- |\n| 3 | 4 |")
js(f"window.setMarkdown({json.dumps(MD2)})")
wait(700)
r5 = js("(function(){var ts=document.querySelectorAll('.b-table table');"
        "if(ts.length<2)return 'need2';"
        "var a=ts[0].tBodies[0].rows[0].cells[0];var ra=a.getBoundingClientRect();"
        "a.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
        "clientX:ra.left+ra.width/2,clientY:ra.top+ra.height/2}));"
        "var b=ts[1].tBodies[0].rows[0].cells[1];var rb=b.getBoundingClientRect();"
        "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,buttons:1,"
        "clientX:rb.left+rb.width/2,clientY:rb.top+rb.height/2}));"
        "document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
        "clientX:rb.left+rb.width/2,clientY:rb.top+rb.height/2}));return 'cross'})()")
wait(250)
s = sel()
check("C5 拖入相邻表格 → 不串台（选区留在原表锚点格）",
      r5 == "cross" and s.get("idx") == 0 and s.get("r0") == 1 and s.get("r1") == 1
      and s.get("c0") == 0 and s.get("c1") == 0,
      json.dumps(s, ensure_ascii=False))

# ---------- C6: 快甩单步跳格（无插值路径）→ 矩形直达 ----------
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
r6 = js("(function(){var t=document.querySelector('.b-table table');"
        "var th=t.tHead.rows[0].cells[0];var r0=th.getBoundingClientRect();"
        "th.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
        "clientX:r0.left+r0.width/2,clientY:r0.top+r0.height/2}));"
        "var last=t.tBodies[0].rows[2].cells[2];var r1=last.getBoundingClientRect();"
        "last.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,buttons:1,"
        "clientX:r1.left+r1.width/2,clientY:r1.top+r1.height/2}));"
        "last.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
        "clientX:r1.left+r1.width/2,clientY:r1.top+r1.height/2}));return 'jump'})()")
wait(250)
s = sel()
check("C6 快甩单步跳格 → 矩形直达整表（3..3 行即 0..3）",
      r6 == "jump" and s.get("r0") == 0 and s.get("r1") == 3
      and s.get("c0") == 0 and s.get("c1") == 2,
      json.dumps(s, ensure_ascii=False))

# ---------- C7: 拖选高亮 CSS（v3.30.6 回归保护）----------
# 1) hover 豁免规则必须存在：.blk tbody tr:hover td.sel —— 缺了它，
#    tr:hover td { background: transparent } (0,2,3) 会把指针所在行的
#    选区高亮整行抹掉（横向拖动全程无高亮的根因）；
# 2) 同步重绘：C6 收尾时选区落在整表，此刻（无 rAF 延迟）选中格的
#    computed background 必须立即等于 --sel 而非 transparent。
r7 = js("(function(){var hit=0;"
        "for(var i=0;i<document.styleSheets.length;i++){var ss=document.styleSheets[i];"
        "if(!ss.cssRules)continue;"
        "for(var j=0;j<ss.cssRules.length;j++){var t=ss.cssRules[j].cssText||'';"
        "if(t.indexOf('tr:hover td.sel')>-1||t.indexOf('tr:hover th.sel')>-1)hit++;}}"
        "var c1=document.querySelector('.b-table table td.sel');"
        "var bg=c1?getComputedStyle(c1).backgroundColor:'nosel';"
        "var c0=document.querySelector('.b-table table td:not(.sel)');"
        "return JSON.stringify({exempt:hit,selbg:bg,"
        "plain:(c0?getComputedStyle(c0).backgroundColor:'no')})})()")
d7 = json.loads(r7) if r7.startswith("{") else {}
check("C7 hover 豁免规则存在（≥2 亮/暗主题）且选中格背景非透明",
      d7.get("exempt", 0) >= 2
      and d7.get("selbg", "transparent") not in ("", "transparent", "rgba(0, 0, 0, 0)")
      and d7.get("selbg") != d7.get("plain"),
      r7)

out.append("DONE")
flush()
print("done")
