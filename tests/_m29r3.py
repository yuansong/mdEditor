# -*- coding: utf-8 -*-
"""v3.29c 诊断 R3：合并后往返（getMarkdown → setMarkdown）是否位置偏移。
另测：既有合并的表格上做第二次合并（相邻区域）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29r3.txt")
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

# 场景 F：合并 (1,1)-(2,2) → getMarkdown → setMarkdown 往返 → DOM 位置
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("window.__tblSelSet(0, 1, 1, 2, 2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
md = js("window.getMarkdown()")
note("F md", str(md)[:400])
js(f"window.setMarkdown({json.dumps(str(md))})")
wait(700)
note("F dom pos after roundtrip", str(jj(GRID_JS)))

# 场景 G：既有合并 (1,1)-(2,2) 的表上，再合并右侧 (1,3)-(2,3)
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("window.__tblSelSet(0, 1, 1, 2, 2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
js("window.__tblSelSet(0, 1, 3, 2, 3)")
wait(300)
d = js("(function(){var tb=document.getElementById('tblbar');"
       "var b=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title==='合并单元格'})[0];"
       "return b?(b.classList.contains('dis')?'dis':'en'):'none'})()")
note("G merge btn state", str(d))
js("window.__tblOp('merge')")
wait(600)
r = str(jj("window.__raw()").get("raw", [""])[0])
note("G raw", r[:500])
note("G dom pos", str(jj(GRID_JS)))

# 场景 H：既有合并下侧 (3,1)-(3,2) 横向合并
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("window.__tblSelSet(0, 1, 1, 2, 2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
js("window.__tblSelSet(0, 3, 1, 3, 2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
r = str(jj("window.__raw()").get("raw", [""])[0])
note("H raw", r[:500])
note("H dom pos", str(jj(GRID_JS)))
note("errs", str(jj("JSON.stringify(window.__errs||[])")))
out.append("DONE")
flush()
print("done")
