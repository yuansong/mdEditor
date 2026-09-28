# -*- coding: utf-8 -*-
"""m67：捕捉「拖内部边线 → 表格缩小一闪而过又还原」的过渡态。

方法：mousedown(不移动) 前后各测一次表宽（看按下瞬间是否跳变），
然后在 mouseup/rebuild 期间逐帧（rAF）采样表宽与各列宽，
若出现「中间某帧明显小于首/末帧」的 V 形 → 即用户看到的闪烁。
两组：无合并 / 先合并(第1~2行第2列) 再拖。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m67.txt")
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
  return JSON.stringify({cols:g.cols, ws:ws, rectW:Math.round(t.getBoundingClientRect().width),
                         st:(t.getAttribute('style')||'')});
})()"""

# 命中第 ci 列右边线，只按下不移动
DOWN = """(function(ci){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var g=window.__core.buildTableGrid(t);
  var ref=(g.grid[0]||[])[ci];
  if(!ref) return JSON.stringify({err:'nocell'});
  var r=ref.el.getBoundingClientRect();
  var w=r.width; if(ref.cs>1) w=w/ref.cs;
  var x=Math.round(r.left+w), y=Math.round(r.top+r.height/2);
  var e=new MouseEvent('mousedown',{bubbles:true,cancelable:true,clientX:x,clientY:y,
                                    button:0,buttons:1,view:window});
  ref.el.dispatchEvent(e);
  return JSON.stringify({x:x,y:y});
})(%d)"""

START_SAMPLE = """(function(){
  window.__rzF=[];
  var n=0;
  function tick(){
    var t=document.querySelector('#editor .b-table table');
    if(t){
      var g=window.__core.buildTableGrid(t);
      var ws=[];
      for(var c=0;c<g.cols;c++){
        var ref=(g.grid[0]||[])[c];
        if(!ref){ws.push(0);continue;}
        var w=ref.el.getBoundingClientRect().width;
        if(ref.cs>1) w=w/ref.cs;
        ws.push(Math.round(w));
      }
      window.__rzF.push({w:Math.round(t.getBoundingClientRect().width), ws:ws});
    } else { window.__rzF.push({w:-1, ws:[]}); }
    if(++n<10) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  return 'sampling';
})()"""

MOVE_UP = """(function(dx){
  function fire(type,target,cx,cy,btn){
    var e=new MouseEvent(type,{bubbles:true,cancelable:true,clientX:cx,clientY:cy,
                               button:0,buttons:btn,view:window});
    target.dispatchEvent(e);
  }
  var t=document.querySelector('#editor .b-table table');
  var g=window.__core.buildTableGrid(t);
  var ref=(g.grid[0]||[])[%d];
  var r=ref.el.getBoundingClientRect();
  var w=r.width; if(ref.cs>1) w=w/ref.cs;
  var x=Math.round(r.left+w), y=Math.round(r.top+r.height/2);
  fire('mousemove',document,x+dx,y,1);
  fire('mouseup',document,x+dx,y,0);
  return 'done';
})(%d)"""

HTML = ('<table class="md-tbl">\n<thead>\n<tr><th>A</th><th>name</th>'
        '<th>x</th><th>remark</th></tr>\n</thead>\n<tbody>\n'
        '<tr><td>a1</td><td>zhangsan-very-long-cell</td><td>1</td><td>ok</td></tr>\n'
        '<tr><td>b2</td><td>lisi</td><td>2</td><td>fine</td></tr>\n'
        '<tr><td>c3</td><td>wangwu</td><td>3</td><td>yes</td></tr>\n'
        '</tbody>\n</table>')


def run(tag, merge, ci, dx):
    js("window.setMarkdown(%s)" % json.dumps(HTML))
    wait(900)
    if merge:
        js("window.__tblSelSet(0,0,1,1,1)")
        js("window.__tblOp('merge')")
        wait(900)
    base = json.loads(js(MEASURE) or "{}")
    d = js(DOWN % ci)
    down = json.loads(js(MEASURE) or "{}")
    log("%s BASE %s" % (tag, base))
    log("%s DOWN %s -> %s" % (tag, d, down))
    check("%s 按下瞬间表宽不跳变" % tag,
          abs(down.get("rectW", 0) - base.get("rectW", 0)) <= 1,
          "%s->%s" % (base.get("rectW"), down.get("rectW")))
    js(START_SAMPLE)
    js(MOVE_UP % (ci, dx))
    wait(700)
    frames = js("JSON.stringify(window.__rzF||[])")
    log("%s FRAMES %s" % (tag, frames))
    fin = json.loads(js(MEASURE) or "{}")
    log("%s FINAL %s" % (tag, fin))
    if base.get("ws") and fin.get("ws"):
        # 总宽不变（v3.30.14）
        check("%s 总宽不变" % tag, abs(fin.get("rectW", 0) - base.get("rectW", 0)) <= 2,
              "%s->%s" % (base.get("rectW"), fin.get("rectW")))
        # 被拖列 ±dx、右邻列 ∓dx
        check("%s 被拖列 %+d" % (tag, dx), abs((fin["ws"][ci] - base["ws"][ci]) - dx) <= 3,
              "c%d %d->%d" % (ci, base["ws"][ci], fin["ws"][ci]))
        j = ci + 1
        if j < len(base["ws"]):
            check("%s 右邻列 %+d" % (tag, -dx), abs((fin["ws"][j] - base["ws"][j]) + dx) <= 3,
                  "c%d %d->%d" % (j, base["ws"][j], fin["ws"][j]))
        rest = [c for c in range(len(base["ws"])) if c not in (ci, j)]
        bad = ["c%d:%d->%d" % (c, base["ws"][c], fin["ws"][c])
               for c in rest if abs(fin["ws"][c] - base["ws"][c]) > 2]
        check("%s 其余列不动" % tag, not bad, ",".join(bad) if bad else "ok")
    try:
        fr = json.loads(frames or "[]")
    except Exception:
        fr = []
    if fr:
        ws = [f["w"] for f in fr if f["w"] > 0]
        if ws:
            lo = min(ws)
            first, last = ws[0], ws[-1]
            dip = min(first, last) - lo
            check("%s 无「缩小后还原」闪烁" % tag, dip <= 2,
                  "frames=%s min=%d first=%d last=%d dip=%d" % (ws, lo, first, last, dip))
        else:
            check("%s 采样有效" % tag, False, str(fr))
    else:
        check("%s 采样有效" % tag, False, "no frames")


run("NO-MERGE/c1", False, 1, 40)
run("MERGE/c1", True, 1, 40)
run("MERGE/c1-", True, 1, -40)

log("SUMMARY PASS=%d FAIL=%d" % (PASS, FAIL))
flush()
os._exit(0)
