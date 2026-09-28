# -*- coding: utf-8 -*-
"""m77 复现：3×4 全合并成一个单元格后，拖表格最下方边框线（单元格边缘路径）
调整行高时，表格被还原成合并前的 3×4 结构。

对照 _m74（只覆盖了蓝色缩放框 's' 手柄路径），本用例覆盖 tableBorderHit 的
row 边缘路径（startTblRz hit.kind='row' → tblExpandDom → commitTblRz replay）：
  A1 无表头 HTML 表：全合并 → 拖下边框 +40 → DOM/存储均保持 rowspan=3 colspan=4
  A2 同 A1，但拖前先点击文档其它位置（触发重建后再选）
  B  管道表（带表头）：全合并（v3.30.13 归一 headRows=0）→ 重建 → 拖下边框
  C  带标注 caption 的全合并表 → 重建 → 拖下边框（标注不丢）
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m77.txt")
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


def ready(timeout=20000):
    t0 = QTimer; import time as _t
    start = _t.time()
    while (_t.time() - start) * 1000 < timeout:
        r = js("(function(){return String(!!(document.getElementById('editor') && window.setMarkdown))})()")
        if str(r).strip().lower() == "true":
            return True
        wait(300)
    return False


if not ready():
    log("FATAL page not ready")
    print("\n".join(out))
    sys.exit(1)

HT = ('<table class="md-tbl">\n<tbody>\n'
      '<tr><td>a</td><td>b</td><td>c</td><td>d</td></tr>\n'
      '<tr><td>e</td><td>f</td><td>g</td><td>h</td></tr>\n'
      '<tr><td>i</td><td>j</td><td>k</td><td>l</td></tr>\n'
      '</tbody>\n</table>')
PIPE = ("| A1 | B1 | C1 | D1 |\n| --- | --- | --- | --- |\n"
        "| A2 | B2 | C2 | D2 |\n| A3 | B3 | C3 | D3 |")

SETMD = "window.setMarkdown(%s)"
SNAP = """(function(){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var trs=t.querySelectorAll('tr'); var hs=[];
  for(var k=0;k<trs.length;k++) hs.push(Math.round(trs[k].getBoundingClientRect().height));
  var r=t.getBoundingClientRect();
  return JSON.stringify({tblH:Math.round(r.height), tblW:Math.round(r.width),
    ncell:t.querySelectorAll('td,th').length,
    rs:t.querySelectorAll('[rowspan]').length, cs:t.querySelectorAll('[colspan]').length,
    rows:trs.length, cap:(t.querySelector('caption')||{}).textContent||''});
})()"""

RAW0 = "window.__raw()"


def raw_first():
    r = js(RAW0)
    try:
        d = json.loads(r)
        return d.get("raw", [""])[0] if isinstance(d, dict) else str(r)
    except Exception:
        return str(r or "")


# 拖表格最下方边框（单元格边缘路径）：mousedown 在合并格底边中点，下移 dy
DRAG_BOTTOM = """(function(dy){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var cell=t.querySelector('td,th');
  if(!cell) return JSON.stringify({err:'nocell'});
  var rc=t.getBoundingClientRect();
  var x0=rc.left+rc.width/2, y0=rc.bottom-2;
  window.__fr=[];
  function snap(tag){
    var a=t.querySelectorAll('tr'); var hs=[];
    for(var k=0;k<a.length;k++) hs.push(Math.round(a[k].getBoundingClientRect().height));
    window.__fr.push({tag:tag, rows:hs, ncell:t.querySelectorAll('td,th').length,
                      rs:t.querySelectorAll('[rowspan]').length,
                      cs:t.querySelectorAll('[colspan]').length});
  }
  function fire(type,target,cx,cy,btn){
    target.dispatchEvent(new MouseEvent(type,{bubbles:true,cancelable:true,
      clientX:cx,clientY:cy,button:0,buttons:btn,view:window}));
  }
  fire('mousedown',cell,x0,y0,1); snap('down');
  fire('mousemove',document,x0,y0+Math.round(dy/2),1); snap('mid');
  fire('mousemove',document,x0,y0+dy,1); snap('move');
  var mid=window.__fr[1], mv=window.__fr[2];
  fire('mouseup',document,x0,y0+dy,0);
  return JSON.stringify({mid:mid, mv:mv});
})(%d)"""


def setup(md, merge_all=True, click_away=True):
    js(SETMD % json.dumps(md))
    wait(700)
    if merge_all:
        js("window.__tblSelSet(0,0,0,2,3)")
        wait(200)
        js("window.__tblOp('merge')")
        wait(700)
    if click_away:
        # 点文档其它位置（末尾段落块），触发失焦/重建
        js("(function(){var bls=document.querySelectorAll('#editor .blk');"
           "var b=bls[bls.length-1];"
           "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0}));"
           "b.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,button:0}));"
           "return 'ok'})()")
        wait(500)
        # 重新点回表格选中蓝框
        js("(function(){var t=document.querySelector('#editor .b-table table');"
           "if(!t)return 'notable';"
           "var cell=t.querySelector('td,th');"
           "var rc=cell.getBoundingClientRect();"
           "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0,"
           "clientX:rc.left+5,clientY:rc.top+5}));"
           "cell.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,button:0,"
           "clientX:rc.left+5,clientY:rc.top+5}));"
           "return 'ok'})()")
        wait(500)


def merged_in_storage():
    s = raw_first()
    return ('rowspan="3"' in s and 'colspan="4"' in s), s[:160]


# ============ A1: 无表头 HTML 表，全合并 → 拖下边框 ============
setup(HT, click_away=False)
s0 = json.loads(js(SNAP))
log("A1 before = %s" % json.dumps(s0))
r = json.loads(js(DRAG_BOTTOM % 40))
log("A1 frames = %s" % json.dumps(r)[:220])
wait(700)
s1 = json.loads(js(SNAP))
log("A1 after = %s" % json.dumps(s1))
ok, s = merged_in_storage()
check("A1 拖拽期间未被摊平（down/mid ncell=1）",
      r.get("mid", {}).get("ncell") == 1 and r.get("mv", {}).get("ncell") == 1, json.dumps(r)[:160])
check("A1 拖后 DOM 仍为单格（rs/cs 各 1）", s1.get("ncell") == 1 and s1.get("rs") == 1 and s1.get("cs") == 1, json.dumps(s1))
check("A1 存储仍含 rowspan=3 colspan=4", ok, s)
check("A1 表高增加（+40 生效）", s1.get("tblH", 0) >= s0.get("tblH", 0) + 30,
      "%s -> %s" % (s0.get("tblH"), s1.get("tblH")))

# ============ A2: 同 A1，但拖前先点击别处再选回 ============
setup(HT, click_away=True)
s0 = json.loads(js(SNAP))
log("A2 before = %s" % json.dumps(s0))
r = json.loads(js(DRAG_BOTTOM % 40))
log("A2 frames = %s" % json.dumps(r)[:220])
wait(700)
s1 = json.loads(js(SNAP))
log("A2 after = %s" % json.dumps(s1))
ok, s = merged_in_storage()
check("A2 拖拽期间未被摊平", r.get("mid", {}).get("ncell") == 1 and r.get("mv", {}).get("ncell") == 1, json.dumps(r)[:160])
check("A2 拖后 DOM 仍为单格", s1.get("ncell") == 1 and s1.get("rs") == 1 and s1.get("cs") == 1, json.dumps(s1))
check("A2 存储仍含 rowspan=3 colspan=4", ok, s)

# ============ B: 管道表（带表头）全合并 → 拖下边框 ============
setup(PIPE, click_away=True)
s0 = json.loads(js(SNAP))
log("B before = %s" % json.dumps(s0))
r = json.loads(js(DRAG_BOTTOM % 40))
log("B frames = %s" % json.dumps(r)[:220])
wait(700)
s1 = json.loads(js(SNAP))
log("B after = %s" % json.dumps(s1))
ok, s = merged_in_storage()
check("B 拖拽期间未被摊平", r.get("mid", {}).get("ncell") == 1 and r.get("mv", {}).get("ncell") == 1, json.dumps(r)[:160])
check("B 拖后 DOM 仍为单格", s1.get("ncell") == 1 and s1.get("rs") == 1 and s1.get("cs") == 1, json.dumps(s1))
check("B 存储仍含 rowspan=3 colspan=4", ok, s)

# ============ C: 带标注的全合并表 → 拖下边框，标注不丢 ============
HT_CAP = ('<table class="md-tbl">\n'
          '<caption class="md-tblcap top">表1</caption>\n<tbody>\n'
          '<tr><td>a</td><td>b</td><td>c</td><td>d</td></tr>\n'
          '<tr><td>e</td><td>f</td><td>g</td><td>h</td></tr>\n'
          '<tr><td>i</td><td>j</td><td>k</td><td>l</td></tr>\n'
          '</tbody>\n</table>')
setup(HT_CAP, click_away=True)
r = json.loads(js(DRAG_BOTTOM % 40))
log("C frames = %s" % json.dumps(r)[:220])
wait(700)
s1 = json.loads(js(SNAP))
log("C after = %s" % json.dumps(s1))
ok, s = merged_in_storage()
check("C 拖后 DOM 仍为单格", s1.get("ncell") == 1 and s1.get("rs") == 1 and s1.get("cs") == 1, json.dumps(s1))
check("C 标注保留", s1.get("cap") == "表1", json.dumps(s1))
check("C 存储仍含 rowspan=3 colspan=4", ok, s)

log("SUMMARY TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
out.append("DONE")
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("\n".join(out))
