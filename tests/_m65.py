# -*- coding: utf-8 -*-
"""m65 诊断：不等宽列宽表格「合并 → 拖内部边线」是否漂移（缺陷1 真场景）。

m64 用默认等宽新表（列宽均分）全部通过 —— 说明漂移需要「列宽不等」才暴露。
本探针构造显式不等宽 colgroup，分四组：
  A 不等宽、无合并 → 拖第0列右边线 +40
  B 不等宽 + 合并(第1~2行第2列) → 拖第0列右边线 +40
  C 不等宽 + 合并 → 拖第2列右边线 +40（合并格右侧区域）
  D 不等宽 + 合并 → 拖第1列右边线 +40，再拖第3列 +40（连拖两次）
判定：仅被拖列变化 ≈ +40，其余列 |Δ| <= 2，表宽增量 = 被拖列增量
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m65.txt")
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
                         tblW:Math.round(t.getBoundingClientRect().width)});
})()"""

DRAGCOL = """(function(ci,dx){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var g=window.__core.buildTableGrid(t);
  var ref=(g.grid[0]||[])[ci];
  if(!ref) return JSON.stringify({err:'nocol'});
  var cell=ref.el;
  var r=cell.getBoundingClientRect();
  var w=r.width; if(ref.cs>1) w=w/ref.cs;
  var x=Math.round(r.left+w), y=Math.round(r.top+r.height/2);
  function fire(type,target,cx,cy,btn){
    var e=new MouseEvent(type,{bubbles:true,cancelable:true,clientX:cx,clientY:cy,
                               button:0,buttons:btn,view:window});
    target.dispatchEvent(e);
  }
  fire('mousedown',cell,x,y,1);
  fire('mousemove',document,x+dx,y,1);
  fire('mouseup',document,x+dx,y,0);
  return JSON.stringify({ci:ci,cs:ref.cs,x:x,y:y});
})(%d,%d)"""

RAW0 = "(function(){var x=JSON.parse(window.__raw());return JSON.stringify({raw:(x.raw||[])[0]})})()"

HTML = ('<table class="md-tbl" style="width: 400px;">\n'
        '<colgroup><col style="width:40px"><col style="width:200px">'
        '<col style="width:60px"><col style="width:100px"></colgroup>\n'
        '<thead>\n<tr><th>A</th><th>name</th><th>x</th><th>remark</th></tr>\n</thead>\n'
        '<tbody>\n'
        '<tr><td>a1</td><td>zhangsan-very-long-cell</td><td>1</td><td>ok</td></tr>\n'
        '<tr><td>b2</td><td>lisi</td><td>2</td><td>fine</td></tr>\n'
        '<tr><td>c3</td><td>wangwu</td><td>3</td><td>yes</td></tr>\n'
        '</tbody>\n</table>')


def setup(merge):
    js("window.setMarkdown(%s)" % json.dumps(HTML))
    wait(900)
    if merge:
        js("window.__tblSelSet(0,0,1,1,1)")
        js("window.__tblOp('merge')")
        wait(900)
    return json.loads(js(MEASURE) or "{}")


def case(tag, merge, ci, dx):
    b = setup(merge)
    log("%s BASE %s" % (tag, b))
    d = js(DRAGCOL % (ci, dx))
    wait(1000)
    a = json.loads(js(MEASURE) or "{}")
    log("%s DRAG %s AFTER %s" % (tag, d, a))
    log("%s RAW %s" % (tag, str(js(RAW0))[:400]))
    if not b.get("ws") or not a.get("ws"):
        check("%s 可测量" % tag, False, str(a))
        return
    w0, w1 = b["ws"], a["ws"]
    check("%s 被拖列 +%d" % (tag, dx), abs((w1[ci] - w0[ci]) - dx) <= 3,
          "c%d %d->%d" % (ci, w0[ci], w1[ci]))
    nb = ci + 1
    if nb < len(w0):
        check("%s 右邻列补偿 %+d" % (tag, -dx), abs((w1[nb] - w0[nb]) + dx) <= 3,
              "c%d %d->%d" % (nb, w0[nb], w1[nb]))
    bad = []
    for c in range(len(w0)):
        if c == ci or c == nb or c >= len(w1):
            continue
        if abs(w1[c] - w0[c]) > 2:
            bad.append("c%d:%d->%d" % (c, w0[c], w1[c]))
    check("%s 其余列不漂移" % tag, not bad, ",".join(bad) if bad else "ok")
    check("%s 总宽不变(v3.30.14)" % tag, abs(a["tblW"] - b["tblW"]) <= 2,
          "%d->%d" % (b["tblW"], a["tblW"]))


case("A 无合并/拖c0", False, 0, 40)
case("B 合并/拖c0", True, 0, 40)
case("C 合并/拖c2", True, 2, 40)
case("D 合并/拖c1", True, 1, -30)

log("SUMMARY PASS=%d FAIL=%d" % (PASS, FAIL))
flush()
os._exit(0)
