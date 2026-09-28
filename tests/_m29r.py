# -*- coding: utf-8 -*-
"""v3.29c 诊断 R：合并中间区域单元格 → 位置偏移排查。
对 4×4 表格分别做：中间 2×2 合并、2×1 跨行合并、1×2 跨列合并，
dump 存储 HTML 与渲染 DOM 的网格坐标，检查每个单元格实际落位。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29r.txt")
out = []


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


# 渲染 DOM 网格坐标 dump：每个 td/th 的逻辑 (r,c) 与文本
GRID_JS = """(function(){
var t=document.querySelector('#editor table');
var marks=[];var pos={};
for(var i=0;i<t.rows.length;i++)marks.push([]);
for(var i=0;i<t.rows.length;i++){
  var cells=t.rows[i].cells,ci=0;
  for(var j=0;j<cells.length;j++){
    var el=cells[j],cs=el.colSpan||1,rs=el.rowSpan||1;
    while(marks[i][ci])ci++;
    pos[el.textContent]=i+','+ci;
    for(var a=0;a<rs;a++)for(var b=0;b<cs;b++){if(marks[i+a])marks[i+a][ci+b]=1;}
    ci+=cs;
  }
}
return JSON.stringify(pos);
})()"""

TBL = ("| 甲 | 乙 | 丙 | 丁 |\n| --- | --- | --- | --- |\n"
       "| 1 | 2 | 3 | 4 |\n| 5 | 6 | 7 | 8 |\n| 9 | 10 | 11 | 12 |")

wait(2500)
js("window.__errs=[];window.onerror=function(m,s,l){window.__errs.push(String(m)+'@'+l);return false;}")

# 场景 A：中间 2×2 合并 (1,1)-(2,2)，期望 2@(1,1)，6/7/10 消失，11@(2,1)... 不对：
# 选中 (1,1)-(2,2) 覆盖 2,3,6,7 → 合并锚 (1,1)=2
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("window.__tblSelSet(0, 1, 1, 2, 2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
r = str(jj("window.__raw()").get("raw", [""])[0])
note("A raw", r[:400])
note("A dom pos", str(jj(GRID_JS)))

# 场景 B：跨行 2×1 (1,2)-(2,2)，期望 3@(1,2)
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("window.__tblSelSet(0, 1, 2, 2, 2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
r = str(jj("window.__raw()").get("raw", [""])[0])
note("B raw", r[:400])
note("B dom pos", str(jj(GRID_JS)))

# 场景 C：先合并中间 2×2，再在其右侧合并 1×2 —— 二次合并是否偏移
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("window.__tblSelSet(0, 1, 1, 2, 2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
js("window.__tblSelSet(0, 1, 3, 1, 3)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
r = str(jj("window.__raw()").get("raw", [""])[0])
note("C raw", r[:500])
note("C dom pos", str(jj(GRID_JS)))
d = jj("JSON.stringify(window.__errs||[])")
note("errs", str(d))
out.append("DONE")
flush()
print("done")
