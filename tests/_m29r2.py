# -*- coding: utf-8 -*-
"""v3.29c 诊断 R2：用真实 UI 交互路径复测合并落位。
反方向拖选（右下→左上）+ 右键 + 菜单点击「合并单元格」，
对比存储 HTML 与 DOM 网格坐标；另测「正方向拖选 + 合并」与
「选中后右键点在选区内边缘格」两种用户常见操作。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29r2.txt")
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

# 场景 D：真实拖选（右下 7 → 左上 2），右键点在选区左上格，菜单点合并
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
d = js("""(function(){
var t=document.querySelector('#editor table');
function center(el){var r=el.getBoundingClientRect();return [r.left+r.width/2, r.top+r.height/2];}
var from=t.rows[2].cells[2], to=t.rows[1].cells[1];
var f=center(from), tt=center(to);
from.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1,buttons:1,clientX:f[0],clientY:f[1]}));
to.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,buttons:1,clientX:tt[0],clientY:tt[1]}));
document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
var sel=window.__tblSel();
to.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:tt[0],clientY:tt[1]}));
var tb=document.getElementById('tblbar');
var btn=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title==='合并单元格'})[0];
var st=btn?(btn.classList.contains('dis')?'dis':'en'):'none';
if(btn&&st==='en'){btn.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));btn.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
return JSON.stringify({sel:sel,btn:st});
})()""")
note("D sel+btn", str(d))
wait(600)
r = str(jj("window.__raw()").get("raw", [""])[0])
note("D raw", r[:400])
note("D dom pos", str(jj(GRID_JS)))

# 场景 E：真实拖选（左上 6 → 右下 11，跨中间 2×2 (2,1)-(3,2)），右键点在末格
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
d = js("""(function(){
var t=document.querySelector('#editor table');
function center(el){var r=el.getBoundingClientRect();return [r.left+r.width/2, r.top+r.height/2];}
var from=t.rows[2].cells[1], to=t.rows[3].cells[2];
var f=center(from), tt=center(to);
from.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1,buttons:1,clientX:f[0],clientY:f[1]}));
to.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,buttons:1,clientX:tt[0],clientY:tt[1]}));
document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
var sel=window.__tblSel();
to.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:tt[0],clientY:tt[1]}));
var tb=document.getElementById('tblbar');
var btn=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title==='合并单元格'})[0];
var st=btn?(btn.classList.contains('dis')?'dis':'en'):'none';
if(btn&&st==='en'){btn.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));btn.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
return JSON.stringify({sel:sel,btn:st});
})()""")
note("E sel+btn", str(d))
wait(600)
r = str(jj("window.__raw()").get("raw", [""])[0])
note("E raw", r[:400])
note("E dom pos", str(jj(GRID_JS)))
note("errs", str(jj("JSON.stringify(window.__errs||[])")))
out.append("DONE")
flush()
print("done")
