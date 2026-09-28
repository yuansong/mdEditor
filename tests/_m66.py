# -*- coding: utf-8 -*-
"""m66 矩阵诊断：严格「先合并 → 再拖内部边线」，穷举表格类型 × 合并位置 × 拖点。

表格类型：PIPE(管道表格，无 colgroup) / HT_NE(HTML 不等宽 colgroup)
合并位置：M0 无 / MA 第4列第2~3行 / MB 第1~2行第2列
拖点：第 row 行 × 第 ci 列右边线（内部边线，ci=0..2），+40px
判定：被拖列 +40±3；其余列 |Δ|<=2；表宽 +40±4；合并跨度保留
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m66.txt")
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
    else:
        FAIL += 1
        log("FAIL | %s | %s" % (name, detail))


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
  return JSON.stringify({cols:g.cols, rows:g.grid.length, ws:ws,
                         tblW:Math.round(t.getBoundingClientRect().width)});
})()"""

DRAG = """(function(ri,ci,dx){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var g=window.__core.buildTableGrid(t);
  var ref=(g.grid[ri]||[])[ci];
  if(!ref) return JSON.stringify({err:'nocell'});
  var r=ref.el.getBoundingClientRect();
  var w=r.width; if(ref.cs>1) w=w/ref.cs;
  var x=Math.round(r.left+w), y=Math.round(r.top+r.height/2);
  function fire(type,target,cx,cy,btn){
    var e=new MouseEvent(type,{bubbles:true,cancelable:true,clientX:cx,clientY:cy,
                               button:0,buttons:btn,view:window});
    target.dispatchEvent(e);
  }
  fire('mousedown',ref.el,x,y,1);
  fire('mousemove',document,x+dx,y,1);
  fire('mouseup',document,x+dx,y,0);
  return JSON.stringify({ok:1});
})(%d,%d,%d)"""

RAW0 = "(function(){var x=JSON.parse(window.__raw());return JSON.stringify({raw:(x.raw||[])[0]})})()"

PIPE = ('| A | name | x | remark |\n| --- | --- | --- | --- |\n'
        '| a1 | zhangsan-very-long-cell | 1 | ok |\n'
        '| b2 | lisi | 2 | fine |\n'
        '| c3 | wangwu | 3 | yes |')

HT_NE = ('<table class="md-tbl" style="width: 400px;">\n'
         '<colgroup><col style="width:40px"><col style="width:200px">'
         '<col style="width:60px"><col style="width:100px"></colgroup>\n'
         '<thead>\n<tr><th>A</th><th>name</th><th>x</th><th>remark</th></tr>\n</thead>\n'
         '<tbody>\n'
         '<tr><td>a1</td><td>zhangsan-very-long-cell</td><td>1</td><td>ok</td></tr>\n'
         '<tr><td>b2</td><td>lisi</td><td>2</td><td>fine</td></tr>\n'
         '<tr><td>c3</td><td>wangwu</td><td>3</td><td>yes</td></tr>\n'
         '</tbody>\n</table>')

TPL = {"PIPE": PIPE, "HT_NE": HT_NE}
MERGES = {"M0": None, "MA": (1, 3, 2, 3), "MB": (0, 1, 1, 1)}


def build(tname, mg):
    js("window.setMarkdown(%s)" % json.dumps(TPL[tname]))
    wait(700)
    if mg:
        js("window.__tblSelSet(0,%d,%d,%d,%d)" % mg)
        js("window.__tblOp('merge')")
        wait(700)


for tname in ("PIPE", "HT_NE"):
    for mname, mg in MERGES.items():
        for ri in (0, 1, 2):
            for ci in (0, 1, 2):
                build(tname, mg)
                b = json.loads(js(MEASURE) or "{}")
                d = js(DRAG % (ri, ci, 40))
                wait(800)
                a = json.loads(js(MEASURE) or "{}")
                raw = str(js(RAW0))
                tag = "%s/%s/row%d/col%d" % (tname, mname, ri, ci)
                if not b.get("ws") or not a.get("ws"):
                    check(tag + " 可测量", False, str(a))
                    continue
                w0, w1 = b["ws"], a["ws"]
                ok_drag = abs((w1[ci] - w0[ci]) - 40) <= 3
                bad = []
                for c in range(len(w0)):
                    if c == ci or c >= len(w1):
                        continue
                    if abs(w1[c] - w0[c]) > 2:
                        bad.append("c%d:%d->%d" % (c, w0[c], w1[c]))
                ok_w = abs((a["tblW"] - b["tblW"]) - 40) <= 4
                keep = True
                if mg:
                    keep = ("rowspan" in raw) or ("colspan" in raw)
                check(tag + " 被拖列+40", ok_drag, "%s->%s (w0=%s w1=%s)" % (w0[ci], w1[ci], w0, w1))
                check(tag + " 其余列不漂移", not bad, ",".join(bad) if bad else "ok")
                check(tag + " 表宽+40", ok_w, "%d->%d" % (b["tblW"], a["tblW"]))
                check(tag + " 合并保留", keep, raw[:160])
                if not (ok_drag and not bad and ok_w and keep):
                    log("  DETAIL %s base=%s after=%s" % (tag, w0, w1))

log("SUMMARY PASS=%d FAIL=%d" % (PASS, FAIL))
flush()
os._exit(0)
