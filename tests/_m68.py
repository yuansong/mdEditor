# -*- coding: utf-8 -*-
"""m68 回归：空内容表格「合并 → 拖内部列边线」（用户真实场景）。

背景：用户表格每个单元格都是空的。空表 + 合并格时，拖边线若走「临时展开合并格」
路径，展开瞬间合并格被拆开、行高按默认重排 → 高度抽动 / 宽度一闪（用户报告的
「缩小后又还原，一闪而过」）。v3.30.14 起列宽拖拽不再展开合并格。

断言：
  T1 表格总宽不变
  T2 表格总高不变（空表关键：高度不许抽动）
  T3 被拖列 +40、右邻列 -40
  T4 逐帧采样无「高度/宽度先塌陷再还原」的 V 形
  T5 合并跨度保留（rowspan 仍在）
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m68.txt")
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
  var r=t.getBoundingClientRect();
  return JSON.stringify({cols:g.cols, ws:ws,
                         rectW:Math.round(r.width), rectH:Math.round(r.height)});
})()"""

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

# 逐帧采样：宽度 + 高度
SAMPLE = """(function(){
  window.__rzF=[];
  var n=0;
  function tick(){
    var t=document.querySelector('#editor .b-table table');
    if(t){ var r=t.getBoundingClientRect();
      window.__rzF.push({w:Math.round(r.width), h:Math.round(r.height)}); }
    else { window.__rzF.push({w:-1,h:-1}); }
    if(++n<12) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  return 'sampling';
})()"""

MOVE_UP = """(function(ci,dx){
  function fire(type,target,cx,cy,btn){
    var e=new MouseEvent(type,{bubbles:true,cancelable:true,clientX:cx,clientY:cy,
                               button:0,buttons:btn,view:window});
    target.dispatchEvent(e);
  }
  var t=document.querySelector('#editor .b-table table');
  var g=window.__core.buildTableGrid(t);
  var ref=(g.grid[0]||[])[ci];
  var r=ref.el.getBoundingClientRect();
  var w=r.width; if(ref.cs>1) w=w/ref.cs;
  var x=Math.round(r.left+w), y=Math.round(r.top+r.height/2);
  fire('mousemove',document,x+dx,y,1);
  fire('mouseup',document,x+dx,y,0);
  return 'done';
})(%d,%d)"""

RAW0 = "(function(){var x=JSON.parse(window.__raw());return JSON.stringify({raw:(x.raw||[])[0]})})()"

# 空内容表格（用户场景）：4 列 × 3 行 + 表头，全部无文字
EMPTY = ('<table class="md-tbl">\n<thead>\n<tr><th></th><th></th><th></th><th></th></tr>\n</thead>\n'
         '<tbody>\n<tr><td></td><td></td><td></td></tr>\n'
         '<tr><td></td><td></td><td></td></tr>\n'
         '<tr><td></td><td></td><td></td></tr>\n</tbody>\n</table>')

CI, DX = 1, 40

js("window.setMarkdown(%s)" % json.dumps(EMPTY))
wait(900)
js("window.__tblSelSet(0,0,1,1,1)")     # 合并第1~2行第2列
js("window.__tblOp('merge')")
wait(900)
base = json.loads(js(MEASURE) or "{}")
log("BASE(merge) %s" % base)
check("T0 空表+合并渲染", base.get("cols") == 4, str(base.get("cols")))

js(DOWN % CI)
down = json.loads(js(MEASURE) or "{}")
log("DOWN %s" % down)
check("T0b 按下瞬间几何不变", abs(down.get("rectW", 0) - base.get("rectW", 0)) <= 1 and
      abs(down.get("rectH", 0) - base.get("rectH", 0)) <= 1,
      "W %s->%s H %s->%s" % (base.get("rectW"), down.get("rectW"), base.get("rectH"), down.get("rectH")))

js(SAMPLE)
js(MOVE_UP % (CI, DX))
wait(800)
fin = json.loads(js(MEASURE) or "{}")
frames = js("JSON.stringify(window.__rzF||[])")
raw = str(js(RAW0))
log("FINAL %s" % fin)
log("FRAMES %s" % frames)
log("RAW %s" % raw[:300])

if base.get("ws") and fin.get("ws"):
    check("T1 总宽不变", abs(fin["rectW"] - base["rectW"]) <= 2,
          "%d->%d" % (base["rectW"], fin["rectW"]))
    check("T2 总高不变", abs(fin["rectH"] - base["rectH"]) <= 2,
          "%d->%d" % (base["rectH"], fin["rectH"]))
    check("T3a 被拖列 +40", abs((fin["ws"][CI] - base["ws"][CI]) - DX) <= 3,
          "c%d %d->%d" % (CI, base["ws"][CI], fin["ws"][CI]))
    nb = CI + 1
    if nb < len(base["ws"]):
        check("T3b 右邻列 -40", abs((fin["ws"][nb] - base["ws"][nb]) + DX) <= 3,
              "c%d %d->%d" % (nb, base["ws"][nb], fin["ws"][nb]))
    rest = [c for c in range(len(base["ws"])) if c not in (CI, nb)]
    bad = ["c%d:%d->%d" % (c, base["ws"][c], fin["ws"][c]) for c in rest
           if abs(fin["ws"][c] - base["ws"][c]) > 2]
    check("T3c 其余列不动", not bad, ",".join(bad) if bad else "ok")
check("T5 合并保留", ("rowspan" in raw) or ("colspan" in raw), raw[:120])

try:
    fr = json.loads(frames or "[]")
except Exception:
    fr = []
if fr:
    hs = [f["h"] for f in fr if f["h"] > 0]
    ws = [f["w"] for f in fr if f["w"] > 0]
    if hs:
        dipH = min(ws and [hs[0], hs[-1]] or [hs[0]]) - min(hs)
        check("T4a 无高度塌陷闪烁", dipH <= 2, "hs=%s" % hs)
    if ws:
        dipW = min(ws[0], ws[-1]) - min(ws)
        check("T4b 无宽度塌陷闪烁", dipW <= 2, "ws=%s" % ws)
else:
    check("T4 采样有效", False, "no frames")

log("SUMMARY PASS=%d FAIL=%d" % (PASS, FAIL))
flush()
os._exit(0)
