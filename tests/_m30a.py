# -*- coding: utf-8 -*-
"""v3.30 探针：表格拖选四方向（含手部弧线）+ 合并定位。
A) 真实轨迹模拟：mousedown 后多步 mousemove（带正弦弧线），验证选区 = 实际划过格；
B) 合并定位：程序化选区 + 真实拖选选区两种路径合并，验证合并格停在原位。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m30a.txt")
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


def raw():
    return jj("window.__raw()").get("raw") or [""]


wait(2500)

# 5 列 × 5 数据行（grid 行 0 = 表头，1..5 = 数据行；列 0..4）
MD = ("| A | B | C | D | E |\n| --- | --- | --- | --- | --- |\n"
      "| 1 | 2 | 3 | 4 | 5 |\n"
      "| 6 | 7 | 8 | 9 | 10 |\n"
      "| 11 | 12 | 13 | 14 | 15 |\n"
      "| 16 | 17 | 18 | 19 | 20 |\n"
      "| 21 | 22 | 23 | 24 | 25 |")

js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)

# 真实轨迹拖拽：mousedown 起点 → n 步 mousemove（横向拖动可带垂直弧线）→ mouseup
DRAG = ("(function(x0,y0,x1,y1,n,arc){"
        "var sp=document.elementFromPoint(x0,y0);"
        "if(!sp)return 'noStart';"
        "sp.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
        "clientX:x0,clientY:y0}));"
        "for(var i=1;i<=n;i++){var t=i/n;"
        "var x=x0+(x1-x0)*t, y=y0+(y1-y0)*t+(arc?arc*Math.sin(Math.PI*t):0);"
        "document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,buttons:1,"
        "clientX:x,clientY:y}));}"
        "document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
        "clientX:x1,clientY:y1}));"
        "return 'dragged'})")


def cell_center(r, c):
    d = jj("(function(){var t=document.querySelector('.b-table table');"
           "var g=(function(tbl){var trs=[];if(tbl.tHead)for(var i=0;i<tbl.tHead.rows.length;i++)trs.push(tbl.tHead.rows[i]);"
           "var b=tbl.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);return trs})(t);"
           "var el=g[" + str(r) + "].cells[" + str(c) + "];"
           "var rc=el.getBoundingClientRect();"
           "return JSON.stringify({x:rc.left+rc.width/2,y:rc.top+rc.height/2})})()")
    return d.get("x"), d.get("y")


def sel():
    return jj("window.__tblSel()")


def trail_keys(s):
    """v3.30.4 矩形语义：由 r0..r1/c0..c1 生成选区键集合"""
    if not s or "r0" not in s:
        return set()
    return {f"{r},{c}"
            for r in range(s["r0"], s["r1"] + 1)
            for c in range(s["c0"], s["c1"] + 1)}


# ---------- A1: 向右拖（跨 3 列，弧线 12px——真实手抖量级，不出行） ----------
x0, y0 = cell_center(2, 1)
x1, y1 = cell_center(2, 3)
r = js(DRAG + f"({x0},{y0},{x1},{y1},16,12)")
wait(300)
s = sel()
check("A1 向右拖+12px 抖动 → 只选本行 3 格",
      r == "dragged" and s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 3,
      json.dumps(s, ensure_ascii=False))

# ---------- A2: 向下拖（跨 3 行，水平抖动 15px——不出列） ----------
x0, y0 = cell_center(1, 1)
x1, y1 = cell_center(4, 1)
r = js(DRAG + f"({x0},{y0},{x1},{y1},16,-15)")
wait(300)
s = sel()
check("A2 向下拖+15px 抖动 → 只选本列 4 行",
      r == "dragged" and s.get("c0") == 1 and s.get("c1") == 1 and s.get("r0") == 1 and s.get("r1") == 4,
      json.dumps(s, ensure_ascii=False))

# ---------- A3: 向左拖 ----------
x0, y0 = cell_center(2, 3)
x1, y1 = cell_center(2, 1)
r = js(DRAG + f"({x0},{y0},{x1},{y1},16,10)")
wait(300)
s = sel()
check("A3 向左拖+10px 抖动 → 只选本行 3 格",
      r == "dragged" and s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 3,
      json.dumps(s, ensure_ascii=False))

# ---------- A4: 向上拖 ----------
x0, y0 = cell_center(4, 2)
x1, y1 = cell_center(1, 2)
r = js(DRAG + f"({x0},{y0},{x1},{y1},16,-12)")
wait(300)
s = sel()
check("A4 向上拖+12px 抖动 → 只选本列 4 行",
      r == "dragged" and s.get("c0") == 2 and s.get("c1") == 2 and s.get("r0") == 1 and s.get("r1") == 4,
      json.dumps(s, ensure_ascii=False))

# ---------- A5: 四方向短拖（直线，无弧线） ----------
cases = [
    ("右", 2, 1, 2, 2, {"r0": 2, "r1": 2, "c0": 1, "c1": 2}),
    ("左", 2, 2, 2, 1, {"r0": 2, "r1": 2, "c0": 1, "c1": 2}),
    ("下", 2, 1, 3, 1, {"r0": 2, "r1": 3, "c0": 1, "c1": 1}),
    ("上", 3, 1, 2, 1, {"r0": 2, "r1": 3, "c0": 1, "c1": 1}),
]
ok_all = True
det = []
for name, r0, c0, r1, c1, exp in cases:
    x0, y0 = cell_center(r0, c0)
    x1, y1 = cell_center(r1, c1)
    js(DRAG + f"({x0},{y0},{x1},{y1},10,0)")
    wait(200)
    s = sel()
    ok = all(s.get(k) == v for k, v in exp.items())
    ok_all = ok_all and ok
    det.append(f"{name}:{json.dumps(s, ensure_ascii=False)}")
check("A5 四方向短拖选区正确", ok_all, " | ".join(det))

# ---------- A7: 向右拖但终点落在下一行（真实手部轨迹）→ 矩形语义 ----------
# v3.30.4：选区 = 锚点(2,1) + 终点(3,3) 对角矩形 → (3,1) 属于矩形（语义变更）
x0, y0 = cell_center(2, 1)
x1, y1 = cell_center(3, 3)
r = js(DRAG + f"({x0},{y0},{x1},{y1},20,0)")
wait(300)
s = sel()
check("A7 右拖终点落在下一行 → 矩形 2..3×1..3",
      r == "dragged" and s.get("r0") == 2 and s.get("r1") == 3
      and s.get("c0") == 1 and s.get("c1") == 3
      and "3,1" in trail_keys(s),
      json.dumps(s, ensure_ascii=False))

# ---------- A6: 斜向对角（表头 → 右下角）→ 包围盒整表（矩形语义恒为整表） ----------
x0, y0 = cell_center(0, 0)
x1, y1 = cell_center(5, 4)
r = js(DRAG + f"({x0},{y0},{x1},{y1},16,0)")
wait(300)
s = sel()
tk = trail_keys(s)
check("A6 对角拖 → 全表矩形 30 格（6 行 × 5 列）",
      r == "dragged" and s.get("r0") == 0 and s.get("r1") == 5 and s.get("c0") == 0 and s.get("c1") == 4
      and len(tk) == 30,
      json.dumps(s, ensure_ascii=False))

# ---------- B1: 程序化选区 → 合并中间两格 → 合并格停在原位 ----------
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
js("window.__tblSelSet(0, 2, 1, 2, 2)")   # grid 行 2（值 6~10），列 1~2（值 7、8）
wait(300)
js("window.__tblOp('merge')")
wait(600)
r = raw()[0]
check("B1 合并中间两格 → colspan=2 停在原位（7 8 前后是 6 / 9）",
      '<td>6</td><td colspan="2">7 8</td><td>9</td>' in r, r[:400])
d = jj("(function(){var t=document.querySelector('.b-table table');"
       "var g=(function(tbl){var trs=[];if(tbl.tHead)for(var i=0;i<tbl.tHead.rows.length;i++)trs.push(tbl.tHead.rows[i]);"
       "var b=tbl.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);return trs})(t);"
       "var td=g[2].cells[1];"
       "return JSON.stringify({ci:td.cellIndex,cs:td.colSpan,txt:td.textContent})})()")
check("B1 DOM：合并格 cellIndex=1（非边缘）、colspan=2",
      d.get("ci") == 1 and d.get("cs") == 2, json.dumps(d, ensure_ascii=False))

# ---------- B2: 真实拖选（带弧线）→ 合并 → 合并格停在原位 ----------
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
x0, y0 = cell_center(2, 1)
x1, y1 = cell_center(2, 2)
r = js(DRAG + f"({x0},{y0},{x1},{y1},16,12)")
wait(300)
s = sel()
pre_ok = s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 2
js("window.__tblOp('merge')")
wait(600)
r = raw()[0]
check("B2 真实拖选（12px 抖动）→ 合并格停在原位",
      pre_ok and '<td>6</td><td colspan="2">7 8</td><td>9</td>' in r,
      "sel=" + json.dumps(s, ensure_ascii=False) + " | " + r[:300])

# ---------- B3: 合并后内容守恒 + 拆回还原 ----------
js("window.__tblSelSet(0, 2, 1, 2, 2)")
wait(250)
js("window.__tblOp('unmerge')")
wait(600)
r = raw()[0]
check("B3 拆回 → 合并区还原两格且位置正确（内容留在首格）",
      "<td>6</td><td>7 8</td><td></td><td>9</td>" in r, r[:300])

out.append("DONE")
flush()
print("done")
