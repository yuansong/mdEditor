# -*- coding: utf-8 -*-
"""v3.29c 探针 P：表格右键菜单 v2（排序 / 任意拆分 / 拖选阈值）。
1) 菜单顺序：插入行列 → 删除行列 → 合并/拆分/还原 → 对齐 → 清空/标注；
2) 未合并格拆分 2×2：新增行/列、邻格补位、网格覆盖完整；
3) 拆分面板：未合并格默认 2×2、上限 12×12（面板可扩到 12）；
4) 拖选阈值：<5px 抖动不扩选，跨格移动扩选，松开保留；
5) 全程 window.onerror 无 JS 异常。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29p.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def note(tag, extra):
    out.append(f"NOTE | {tag} | {extra}")
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
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


TBL = "| 甲 | 乙 | 丙 |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 5 | 6 | 7 |"

wait(2500)
js("window.__errs=[];window.onerror=function(m,s,l){window.__errs.push(String(m)+'@'+l);return false;}")
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)

# ===== 1. 菜单顺序 =====
js("window.__tblSelSet(0, 1, 1, 1, 1)")
wait(300)
titles = jj("(function(){var tb=document.getElementById('tblbar');"
            "return JSON.stringify([].map.call(tb.querySelectorAll('button'),"
            "function(x){return x.title}))})()")
# v3.30.10 需求变更：菜单按可用性动态显示 —— 单格不可合并 → 合并项隐藏；
# 拆分 / 还原按需显示。v3.30.17：「表格标注」迁出右键菜单（悬浮工具条「标注」）
exp = ["向上插入行", "向下插入行", "删除行", "向左插入列", "向右插入列", "删除列",
       "拆分单元格（选择行 × 列）",
       "下移该行", "左移该列", "右移该列",
       "左对齐", "居中", "右对齐", "清空内容"]
note("1 titles", str(titles))
check("菜单顺序 = 插入行列→删除行列→合并拆分→对齐→清空标注",
      isinstance(titles, list) and [t for t in titles if not t.startswith("align")] == exp,
      str(titles))

# ===== 2. 拆分面板（未合并格）默认 2×2 =====
d = jj("(function(){window.__tblOp('splitgrid');"
       "return JSON.stringify({show:document.getElementById('tblsize').classList.contains('show'),"
       "hint:document.getElementById('tbl-hint').textContent})})()")
note("2 panel", str(d))
check("未合并格拆分面板打开且默认 2×2",
      d.get("show") is True and "拆分为 2 行 × 2 列" in (d.get("hint") or ""), str(d))

# 点面板 (2×2) 确认 → 拆分
d = jj("(function(){var gc=document.querySelector('#tblgrid .gc[data-r=\"1\"][data-c=\"1\"]');"
       "gc.dispatchEvent(new MouseEvent('click',{bubbles:true}));"
       "return 'clicked'})()")
wait(600)
r = str(raw()[0])
note("2 raw after split", r[:300])
check("未合并格拆分 → 存储升级 HTML 表格", r.startswith("<table"), r[:80])

# ===== 3. 拆分后网格覆盖完整（4 列 × 4 行）=====
d = jj("""(function(){
var t=document.querySelector('#editor table');
var rows=t.rows, marks=[];
for(var i=0;i<rows.length;i++)marks.push([]);
for(var i=0;i<rows.length;i++){
  var cells=rows[i].cells, ci=0;
  for(var j=0;j<cells.length;j++){
    var cs=cells[j].colSpan||1, rs=cells[j].rowSpan||1;
    while(marks[i][ci])ci++;
    for(var a=0;a<rs;a++)for(var b=0;b<cs;b++){if(marks[i+a])marks[i+a][ci+b]=1;}
    ci+=cs;
  }
}
var w=marks[0]?marks[0].length:0;
var complete=true, holes=[];
for(var i2=0;i2<marks.length;i2++){
  if(marks[i2].length!==w)complete=false;
  for(var k=0;k<w;k++)if(!marks[i2][k]){complete=false;holes.push(i2+':'+k);}
}
var counts=[].map.call(rows,function(x){return x.cells.length;});
return JSON.stringify({rows:rows.length,width:w,complete:complete,holes:holes,counts:counts});
})()""")
note("3 grid", str(d))
check("拆分后 4 行 × 4 列", d.get("rows") == 4 and d.get("width") == 4, str(d))
check("网格覆盖完整无空洞", d.get("complete") is True, str(d))
check("各行列数 = 3/4/2/3（邻格跨行补位）",
      d.get("counts") == [3, 4, 2, 3], str(d.get("counts")))
check("原内容 2 / 6 / 7 保留", all(x in r for x in (">2<", ">6<", ">7<")), r[:200])
check("乙 / 6 跨两列（colspan=2）", r.count('colspan="2"') == 2, str(r.count('colspan="2"')))

# ===== 4. 拆分面板上限：方向键扩到 12×12（未合并格）=====
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)
d = jj("(function(){window.__tblSelSet(0, 2, 2, 2, 2);window.__tblOp('splitgrid');"
       "for(var i=0;i<10;i++)document.dispatchEvent(new KeyboardEvent('keydown',"
       "{key:'ArrowDown',bubbles:true,cancelable:true}));"
       "for(var j=0;j<10;j++)document.dispatchEvent(new KeyboardEvent('keydown',"
       "{key:'ArrowRight',bubbles:true,cancelable:true}));"
       "return JSON.stringify({has12:true,"
       "hint:document.getElementById('tbl-hint').textContent})})()")
note("4 max12", str(d))
check("未合并格拆分上限 12×12", d.get("has12") is True and "12 行 × 12 列" in (d.get("hint") or ""), str(d))
js("(function(){document.getElementById('tblsize').classList.remove('show');return 1})()")
wait(200)

# ===== 5. 拖选阈值：<5px 抖动不扩选 =====
d = jj("""(function(){
var t=document.querySelector('#editor table');
var c11=t.rows[1].cells[1];
var r11=c11.getBoundingClientRect();
var x=r11.left+r11.width/2, y=r11.top+r11.height/2;
c11.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0,buttons:1,clientX:x,clientY:y}));
c11.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,buttons:1,clientX:x+3,clientY:y+3}));
var s1=window.__tblSel();
document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
return JSON.stringify({small:s1});
})()""")
note("5 small drag", str(d))
s1 = d.get("small")
if isinstance(s1, str):
    try:
        s1 = json.loads(s1)
    except Exception:
        s1 = {}
check("抖动 3px 不扩选（仍单格）",
      isinstance(s1, dict) and s1.get("r0") == s1.get("r1") == 1
      and s1.get("c0") == s1.get("c1") == 1, str(s1))

# ===== 6. 拖选跨格：扩选并保留 =====
d = jj("""(function(){
var t=document.querySelector('#editor table');
var c11=t.rows[1].cells[1], c12=t.rows[1].cells[2], c22=t.rows[2].cells[2];
var r11=c11.getBoundingClientRect();
var x=r11.left+r11.width/2, y=r11.top+r11.height/2;
c11.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0,buttons:1,clientX:x,clientY:y}));
var r22=c22.getBoundingClientRect();
c22.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,buttons:1,
  clientX:r22.left+r22.width/2,clientY:r22.top+r22.height/2}));
var s1=window.__tblSel();
document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
var s2=window.__tblSel();
return JSON.stringify({during:s1,after:s2});
})()""")
note("6 big drag", str(d))
dg, af = d.get("during"), d.get("after")
if isinstance(dg, str):
    try:
        dg = json.loads(dg)
    except Exception:
        dg = {}
if isinstance(af, str):
    try:
        af = json.loads(af)
    except Exception:
        af = {}
check("跨格拖选 → 矩形扩选 (1,1)-(2,2)",
      isinstance(dg, dict) and dg.get("r0") == 1 and dg.get("r1") == 2
      and dg.get("c0") == 1 and dg.get("c1") == 2, str(dg))
check("松开后选区保留",
      isinstance(af, dict) and af.get("r0") == 1 and af.get("r1") == 2
      and af.get("c0") == 1 and af.get("c1") == 2, str(af))

# ===== 7. 全程无 JS 异常 =====
d = jj("JSON.stringify(window.__errs||[])")
check("全程无 JS 异常", str(d) == "[]", str(d))

out.append("DONE")
flush()
print("done")
