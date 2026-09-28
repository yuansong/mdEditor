# -*- coding: utf-8 -*-
"""m64 探针：缺陷1（合并后拖内部竖边线 → 整表缩放/布局错乱）自动复现 + 回归判定。

场景（贴近用户操作）：
  1) 3x4 HTML 表格，内容不等宽（等宽新表探测不出漂移）
  2) 合并第 1~2 行第 2 列（r0=0,c0=1,r1=1,c1=1）
  3) 拖「内部」竖边线（非表格外框） +40px
判定：
  - 只有被拖列变宽 ≈ +40px
  - 其余列宽度变化 |Δ| <= 2px（超出 = 整表缩放/布局错乱复现）
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m64.txt")
out = []
PASS = 0
FAIL = 0


def log(s):
    out.append(str(s))
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        log("PASS %s %s" % (name, detail))
    else:
        FAIL += 1
        log("FAIL %s %s" % (name, detail))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


wait(3000)

# ---------- 测量工具：每列实测宽度（合并格按 cs 均分） ----------
MEASURE = """(function(){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var g=window.__core.buildTableGrid(t);
  var ws=[];
  for(var c=0;c<g.cols;c++){
    var ref=(g.grid[0]||[])[c];
    if(!ref){ws.push(0);continue;}
    var w=ref.el.getBoundingClientRect().width;
    if(ref.cs>1) w=w/ref.cs;
    ws.push(Math.round(w));
  }
  var cg=t.querySelectorAll('colgroup > col');
  var cw=[];
  for(var k=0;k<cg.length;k++){
    var wm=(cg[k].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);
    cw.push(wm?Math.round(parseFloat(wm[1])):0);
  }
  return JSON.stringify({cols:g.cols, ws:ws, cg:cw,
                         tblW:Math.round(t.getBoundingClientRect().width),
                         tl:getComputedStyle(t).tableLayout});
})()"""

# ---------- 用例表格：内容不等宽 ----------
HTML = ('<table class="md-tbl">\n<thead>\n<tr><th>A</th><th>name</th>'
        '<th>x</th><th>remark</th></tr>\n</thead>\n<tbody>\n'
        '<tr><td>a1</td><td>zhangsan-very-long-cell</td><td>1</td><td>ok</td></tr>\n'
        '<tr><td>b2</td><td>lisi</td><td>2</td><td>fine</td></tr>\n'
        '<tr><td>c3</td><td>wangwu</td><td>3</td><td>yes</td></tr>\n'
        '</tbody>\n</table>')
js("window.setMarkdown(%s)" % json.dumps(HTML))
wait(900)
DIAG = ("(function(){var x=JSON.parse(window.__raw());"
        "var r=x.raw||[];"
        "var b=document.querySelector('#editor .blk');"
        "return JSON.stringify({n:r.length, raw0:String(r[0]||'').slice(0,160),"
        "kids:document.querySelectorAll('#editor .blk').length,"
        "cls:b?b.className:'',"
        "html:b?String(b.innerHTML).slice(0,200):''});})()")
log("DIAG " + str(js(DIAG)))
base = js(MEASURE)
log("BASE " + str(base))
b = json.loads(base) if base else {}
check("T0 表格渲染", b.get("cols") == 4, str(b.get("cols")))

# ---------- 合并：第1~2行 第2列（r0=0,c0=1,r1=1,c1=1） ----------
r = js("window.__tblSelSet(0,0,1,1,1)")
log("SELSET " + str(r))
r = js("window.__tblOp('merge')")
log("MERGE " + str(r))
wait(900)
raw1 = js("(function(){var x=JSON.parse(window.__raw());return JSON.stringify({raw:(x.raw||[])[0]})})()")
log("RAW-AFTER-MERGE " + str(raw1))
m1 = js(MEASURE)
log("MEASURE-AFTER-MERGE " + str(m1))
a = json.loads(m1) if m1 else {}
check("T1 合并后仍 4 列", a.get("cols") == 4, str(a.get("cols")))

# ---------- 拖内部竖边线：找第一行中 cs==1 且非末列的列，拖其右边线 +40 ----------
DRAG = """(function(){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var g=window.__core.buildTableGrid(t);
  var pick=-1;
  for(var c=0;c<g.cols;c++){
    var ref=(g.grid[0]||[])[c];
    if(ref && ref.cs===1 && c<g.cols-1){pick=c;break;}
  }
  if(pick<0) return JSON.stringify({err:'nocol'});
  var cell=g.grid[0][pick].el;
  var r=cell.getBoundingClientRect();
  var x=Math.round(r.right), y=Math.round(r.top+r.height/2);
  function fire(type,target,cx,cy,btn){
    var e=new MouseEvent(type,{bubbles:true,cancelable:true,clientX:cx,clientY:cy,
                               button:0,buttons:btn,view:window});
    target.dispatchEvent(e);
  }
  fire('mousedown',cell,x,y,1);
  fire('mousemove',document,x+40,y,1);
  fire('mouseup',document,x+40,y,0);
  return JSON.stringify({pick:pick,x:x,y:y,cellW:Math.round(r.width)});
})()"""
d = js(DRAG)
log("DRAG " + str(d))
dj = json.loads(d) if d else {}
wait(1000)
m2 = js(MEASURE)
log("MEASURE-AFTER-DRAG " + str(m2))
c2 = json.loads(m2) if m2 else {}
raw2 = js("(function(){var x=JSON.parse(window.__raw());return JSON.stringify({raw:(x.raw||[])[0]})})()")
log("RAW-AFTER-DRAG " + str(raw2))

pick = dj.get("pick")
if isinstance(pick, int) and b.get("ws") and c2.get("ws"):
    w0, w2 = b["ws"], c2["ws"]
    log("DELTA base=%s after=%s pick=%s" % (w0, w2, pick))
    check("T2 被拖列变宽约 +40", abs((w2[pick] - w0[pick]) - 40) <= 3,
          "col%d %d->%d" % (pick, w0[pick], w2[pick]))
    nb = pick + 1
    if nb < len(w0):
        check("T3 右邻列补偿 -40", abs((w2[nb] - w0[nb]) + 40) <= 3,
              "c%d %d->%d" % (nb, w0[nb], w2[nb]))
    bad = []
    for c in range(len(w0)):
        if c == pick or c == nb:
            continue
        if len(w2) > c and abs(w2[c] - w0[c]) > 2:
            bad.append("c%d:%d->%d" % (c, w0[c], w2[c]))
    check("T4 其余列宽不漂移(<2px)", not bad, ",".join(bad) if bad else "ok")
    check("T5 总宽不变(v3.30.14)", abs(c2["tblW"] - b["tblW"]) <= 2,
          "%d->%d" % (b["tblW"], c2["tblW"]))
else:
    check("T2 拖拽执行", False, str(dj))

log("SUMMARY PASS=%d FAIL=%d" % (PASS, FAIL))
flush()
os._exit(0)
