# -*- coding: utf-8 -*-
"""m69 诊断：行高拖拽（含合并格）是否导致进程退出（用户报告「行高拖动自动关闭」）。

每一步立即落盘，进程若崩溃，日志停在崩溃前那一步 → 定位到具体调用。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m69.txt")
out = []


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
log("STEP app created")
from mainwindow import MainWindow
win = MainWindow()
win.show()
log("STEP window shown")


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
log("STEP ready")

EMPTY = ('<table class="md-tbl">\n<thead>\n<tr><th></th><th></th><th></th><th></th></tr>\n</thead>\n'
         '<tbody>\n<tr><td></td><td></td><td></td></tr>\n'
         '<tr><td></td><td></td><td></td></tr>\n'
         '<tr><td></td><td></td><td></td></tr>\n</tbody>\n</table>')

ROWDRAG = """(function(ri,dy){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var trs=t.querySelectorAll('tr');
  if(!trs[ri]) return JSON.stringify({err:'norow'});
  var tr=trs[ri];
  var cell=tr.cells[0];
  var r=tr.getBoundingClientRect();
  var x=Math.round(r.left+r.width/2), y=Math.round(r.bottom);
  function fire(type,target,cx,cy,btn){
    var e=new MouseEvent(type,{bubbles:true,cancelable:true,clientX:cx,clientY:cy,
                               button:0,buttons:btn,view:window});
    target.dispatchEvent(e);
  }
  var out={ri:ri,x:x,y:y,h0:Math.round(r.height)};
  fire('mousedown',cell,x,y,1);
  out.afterDown=Math.round(tr.getBoundingClientRect().height);
  fire('mousemove',document,x,y+dy,1);
  out.afterMove=Math.round(tr.getBoundingClientRect().height);
  fire('mouseup',document,x,y+dy,0);
  return JSON.stringify(out);
})(%d,%d)"""

ROWS = """(function(){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var trs=t.querySelectorAll('tr'); var hs=[];
  for(var k=0;k<trs.length;k++) hs.push(Math.round(trs[k].getBoundingClientRect().height));
  return JSON.stringify({rows:hs, tblH:Math.round(t.getBoundingClientRect().height)});
})()"""

RAW0 = "(function(){var x=JSON.parse(window.__raw());return JSON.stringify({raw:(x.raw||[])[0]})})()"


def case(tag, merge, ri, dy):
    log("CASE %s begin" % tag)
    js("window.setMarkdown(%s)" % json.dumps(EMPTY))
    wait(900)
    if merge:
        js("window.__tblSelSet(0,0,1,1,1)")
        js("window.__tblOp('merge')")
        wait(900)
        log("  %s merged" % tag)
    log("  %s before %s" % (tag, str(js(ROWS))))
    d = js(ROWDRAG % (ri, dy))
    log("  %s drag %s" % (tag, d))
    wait(1200)
    log("  %s after %s" % (tag, str(js(ROWS))))
    log("  %s raw %s" % (tag, str(js(RAW0))[:260]))
    log("CASE %s end" % tag)


case("R1 无合并/行0 +30", False, 0, 30)
case("R2 合并/行0 +30", True, 0, 30)
case("R3 合并/行1 +30", True, 1, 30)
case("R4 合并/行0 -20", True, 0, -20)

log("SUMMARY OK")
os._exit(0)
