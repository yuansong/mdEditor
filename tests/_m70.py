# -*- coding: utf-8 -*-
"""m70 回归：行高拖拽（空表格 + 合并）—— 只许改「被拖行」的高度，
列宽 / 表宽 / 其他行高 一律不许变。

用户报告：纵向拖动（行高）时表格仍然会「改变」。
本用例逐帧采样：mousedown 后、每次 mousemove、mouseup 重建后，
记录 rows[] / tblH / tblW / cols[]，把任何不该变的量钉死。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m70.txt")
out = []
FAIL = [0]
TOTAL = [0]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


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

EMPTY = ('<table class="md-tbl">\n<thead>\n<tr><th></th><th></th><th></th><th></th></tr>\n</thead>\n'
         '<tbody>\n<tr><td></td><td></td><td></td></tr>\n'
         '<tr><td></td><td></td><td></td></tr>\n'
         '<tr><td></td><td></td><td></td></tr>\n</tbody>\n</table>')

MEASURE = """(function(){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var trs=t.querySelectorAll('tr'); var hs=[];
  for(var k=0;k<trs.length;k++) hs.push(Math.round(trs[k].getBoundingClientRect().height));
  var cg=t.querySelectorAll('colgroup > col'); var cw=[];
  for(var k=0;k<cg.length;k++){
    var m=(cg[k].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);
    cw.push(m?Math.round(parseFloat(m[1])):Math.round(cg[k].getBoundingClientRect().width));
  }
  var r=t.getBoundingClientRect();
  return JSON.stringify({rows:hs, cols:cw, tblH:Math.round(r.height), tblW:Math.round(r.width)});
})()"""

# 拖行边线：分帧执行，每帧记录一次量测
ROWDRAG = """(function(ri,dy){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var trs=t.querySelectorAll('tr');
  if(!trs[ri]) return JSON.stringify({err:'norow ri='+ri});
  var tr=trs[ri];
  var r=tr.getBoundingClientRect();
  var x=Math.round(r.left+r.width/2), y=Math.round(r.bottom);
  window.__fr=[];
  function snap(tag){
    var a=t.querySelectorAll('tr'); var hs=[];
    for(var k=0;k<a.length;k++) hs.push(Math.round(a[k].getBoundingClientRect().height));
    var cg=t.querySelectorAll('colgroup > col'); var cw=[];
    for(var k=0;k<cg.length;k++){
      var m=(cg[k].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);
      cw.push(m?Math.round(parseFloat(m[1])):Math.round(cg[k].getBoundingClientRect().width));
    }
    var rr=t.getBoundingClientRect();
    window.__fr.push({tag:tag, rows:hs, cols:cw, tblH:Math.round(rr.height), tblW:Math.round(rr.width)});
  }
  function fire(type,target,cx,cy,btn){
    var e=new MouseEvent(type,{bubbles:true,cancelable:true,clientX:cx,clientY:cy,
                               button:0,buttons:btn,view:window});
    target.dispatchEvent(e);
  }
  var o={ri:ri,x:x,y:y,h0:Math.round(r.height)};
  fire('mousedown',tr.cells[0],x,y,1);
  snap('down');
  fire('mousemove',document,x,y+Math.round(dy/2),1);
  snap('mid');
  fire('mousemove',document,x,y+dy,1);
  snap('move');
  fire('mouseup',document,x,y+dy,0);
  o.frames=window.__fr;
  return JSON.stringify(o);
})(%d,%d)"""

RAW0 = "(function(){var x=JSON.parse(window.__raw());return JSON.stringify({raw:(x.raw||[])[0]})})()"


def parse(s):
    try:
        return json.loads(s)
    except Exception:
        return {"err": str(s)[:120]}


def case(tag, merge, ri, dy):
    log("CASE %s begin" % tag)
    js("window.setMarkdown(%s)" % json.dumps(EMPTY))
    wait(900)
    if merge:
        js("window.__tblSelSet(0, 0, 1, 1, 1)")
        js("window.__tblOp('merge')")
        wait(900)
    b = parse(js(MEASURE))
    log("  %s before %s" % (tag, json.dumps(b)))
    d = parse(js(ROWDRAG % (ri, dy)))
    for fr in d.get("frames", []):
        log("  %s frame %s" % (tag, json.dumps(fr)))
    wait(1300)
    a = parse(js(MEASURE))
    log("  %s after %s" % (tag, json.dumps(a)))
    log("  %s raw %s" % (tag, str(js(RAW0))[:300]))
    if "err" in b or "err" in a:
        check("%s 表格可测" % tag, False, str(b.get("err") or a.get("err")))
        log("CASE %s end" % tag)
        return
    # A1 表宽不变
    check("%s A1 表宽不变" % tag, abs(a["tblW"] - b["tblW"]) <= 2,
          "%d->%d" % (b["tblW"], a["tblW"]))
    # A2 列宽不变
    badc = ["c%d:%d->%d" % (k, b["cols"][k], a["cols"][k])
            for k in range(min(len(b["cols"]), len(a["cols"])))
            if abs(a["cols"][k] - b["cols"][k]) > 2]
    check("%s A2 列宽不变" % tag, not badc, ",".join(badc) if badc else "ok")
    # A3 非被拖行高度不变
    badr = ["r%d:%d->%d" % (k, b["rows"][k], a["rows"][k])
            for k in range(min(len(b["rows"]), len(a["rows"])))
            if k != ri and abs(a["rows"][k] - b["rows"][k]) > 2]
    check("%s A3 其他行高不变" % tag, not badr, ",".join(badr) if badr else "ok")
    # A4 被拖行按方向变化
    if dy > 0:
        check("%s A4 被拖行变高" % tag, a["rows"][ri] - b["rows"][ri] >= dy - 4,
              "r%d %d->%d dy=%d" % (ri, b["rows"][ri], a["rows"][ri], dy))
    else:
        check("%s A4 被拖行变矮" % tag, b["rows"][ri] - a["rows"][ri] >= abs(dy) - 4,
              "r%d %d->%d dy=%d" % (ri, b["rows"][ri], a["rows"][ri], dy))
    # A5 逐帧无抖动：表宽/列宽/其他行在每帧都稳定
    drift = []
    for fr in d.get("frames", []):
        if abs(fr["tblW"] - b["tblW"]) > 2:
            drift.append("%s tblW=%d" % (fr["tag"], fr["tblW"]))
        for k in range(min(len(b["cols"]), len(fr["cols"]))):
            if abs(fr["cols"][k] - b["cols"][k]) > 2:
                drift.append("%s c%d=%d" % (fr["tag"], k, fr["cols"][k]))
        for k in range(min(len(b["rows"]), len(fr["rows"]))):
            if k != ri and abs(fr["rows"][k] - b["rows"][k]) > 2:
                drift.append("%s r%d=%d" % (fr["tag"], k, fr["rows"][k]))
    check("%s A5 逐帧无抖动" % tag, not drift, ";".join(drift[:6]) if drift else "ok")
    log("CASE %s end" % tag)


case("R1 无合并/行0 +30", False, 0, 30)
case("R2 合并/行0 +30", True, 0, 30)
case("R3 合并/行1 +30", True, 1, 30)
case("R4 合并/行2 +30", True, 2, 30)
case("R5 合并/行0 -20", True, 0, -20)

log("SUMMARY TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
os._exit(0)
