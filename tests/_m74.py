# -*- coding: utf-8 -*-
"""m74 回归：整表缩放（拖外框手柄）不得摊平合并格。

用户报告：3×4 合并成一个单元格后拖最下方边框，会「先还原成 3×4 再拖」——
根因是 mousedown 里为了量每列真实宽先调用了 tblExpandDom，整个拖拽期间
表格都处于摊平态。v3.30.16 改为从逻辑网格直接量基线，全程不拆合并。

本用例逐帧采样 down / mid / move 三帧，钉死：
  拖拽期间 DOM 单元格数与 rowspan 始终不变（没被摊平）
  缩放后表宽 / 表高达到目标，列宽 / 行高按基线等比
  落盘源码仍是完整合并（rowspan=3 colspan=4）
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m74.txt")
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

T34 = ('<table class="md-tbl">\n<tbody>\n'
       '<tr><td>a</td><td>b</td><td>c</td><td>d</td></tr>\n'
       '<tr><td>e</td><td>f</td><td>g</td><td>h</td></tr>\n'
       '<tr><td>i</td><td>j</td><td>k</td><td>l</td></tr>\n'
       '</tbody>\n</table>')

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
  var sp=t.querySelectorAll('[rowspan]').length, cp=t.querySelectorAll('[colspan]').length;
  return JSON.stringify({rows:hs, cols:cw, tblH:Math.round(r.height), tblW:Math.round(r.width),
                         ncell:t.querySelectorAll('td,th').length, rs:sp, cs:cp});
})()"""

# 拖整表缩放手柄：h in {s,n,e,w,se...}，dx/dy 为位移
RZDRAG = """(function(h,dx,dy){
  var t=document.querySelector('#editor .b-table table');
  if(!t) return JSON.stringify({err:'notable'});
  var hd=document.querySelector('.rz[data-h="'+h+'"]');
  if(!hd) return JSON.stringify({err:'nohandle '+h});
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
    window.__fr.push({tag:tag, rows:hs, cols:cw, tblH:Math.round(rr.height),
                      tblW:Math.round(rr.width), ncell:t.querySelectorAll('td,th').length,
                      rs:t.querySelectorAll('[rowspan]').length});
  }
  function fire(type,target,cx,cy,btn){
    var e=new MouseEvent(type,{bubbles:true,cancelable:true,clientX:cx,clientY:cy,
                               button:0,buttons:btn,view:window});
    target.dispatchEvent(e);
  }
  var x=100,y=100, o={h:h,dx:dx,dy:dy};
  fire('mousedown',hd,x,y,1);
  snap('down');
  fire('mousemove',document,x+Math.round(dx/2),y+Math.round(dy/2),1);
  snap('mid');
  fire('mousemove',document,x+dx,y+dy,1);
  snap('move');
  fire('mouseup',document,x+dx,y+dy,0);
  o.frames=window.__fr;
  return JSON.stringify(o);
})('%s',%d,%d)"""

RAW0 = "(function(){var x=JSON.parse(window.__raw());return JSON.stringify({raw:(x.raw||[])[0]})})()"


def parse(s):
    try:
        return json.loads(s)
    except Exception:
        return {"err": str(s)[:160]}


def case(tag, merge, h, dx, dy):
    log("CASE %s begin" % tag)
    js("window.setMarkdown(%s)" % json.dumps(T34))
    wait(900)
    if merge:
        js("window.__tblSelSet(0, 0, 0, 2, 3)")
        js("window.__tblOp('merge')")
        wait(1000)
    r0 = js("window.__rzPick(0)")
    wait(400)
    r0f = js("window.__rzShow()")
    b = parse(js(MEASURE))
    log("  %s rzPick=%s frame=%s before %s" % (tag, r0, r0f, json.dumps(b)))
    d = parse(js(RZDRAG % (h, dx, dy)))
    for fr in d.get("frames", []):
        log("  %s frame %s" % (tag, json.dumps(fr)))
    wait(1400)
    a = parse(js(MEASURE))
    r1 = parse(js(RAW0))
    log("  %s after %s" % (tag, json.dumps(a)))
    log("  %s raw %s" % (tag, str(r1.get("raw", ""))[:400]))
    if "err" in b or "err" in a or "err" in d:
        check("%s 可驱动" % tag, False, str(d.get("err") or b.get("err") or a.get("err")))
        log("CASE %s end" % tag)
        return None
    # B1 拖拽期间不摊平：单元格数与 rowspan 数全程与拖拽前一致
    bad = []
    for fr in d.get("frames", []):
        if fr["ncell"] != b["ncell"]:
            bad.append("%s ncell=%d(%d)" % (fr["tag"], fr["ncell"], b["ncell"]))
        if fr["rs"] != b["rs"]:
            bad.append("%s rs=%d(%d)" % (fr["tag"], fr["rs"], b["rs"]))
    check("%s B1 拖拽期间未摊平合并" % tag, not bad, ";".join(bad) if bad else "ok")
    # B2 达到目标尺寸
    if dx:
        check("%s B2 表宽 %+d" % (tag, dx),
              abs((a["tblW"] - b["tblW"]) - dx) <= 8, "%d->%d" % (b["tblW"], a["tblW"]))
    if dy:
        if dy > 0:
            check("%s B2 表高 %+d" % (tag, dy),
                  abs((a["tblH"] - b["tblH"]) - dy) <= 8, "%d->%d" % (b["tblH"], a["tblH"]))
        else:
            # 缩小：内容 / 压缩态有下限，不要求精确到达目标，
            # 只要求「没变高」且落盘高度确实变小（说明缩放真的生效了）
            import re as _re
            _m = _re.search(r'height:\s*(\d+)px', str(r1.get("raw", "")))
            _sh = int(_m.group(1)) if _m else -1
            check("%s B2 表高缩小（落盘 %d < 原 %d）" % (tag, _sh, b["tblH"]),
                  a["tblH"] <= b["tblH"] and 0 < _sh <= b["tblH"] - 3,
                  "tblH %d->%d" % (b["tblH"], a["tblH"]))
    # B3 列宽 / 行高等比（相邻项比例保持）
    def ratio_keep(x, y):
        if len(x) < 2 or len(y) < 2:
            return True
        n = min(len(x), len(y))
        for k in range(1, n):
            if x[0] and y[0]:
                r1v = x[k] / float(x[0]) if x[0] else 0
                r2v = y[k] / float(y[0]) if y[0] else 0
                if abs(r1v - r2v) > 0.12:
                    return False
        return True
    if dx:
        check("%s B3 列宽等比" % tag, ratio_keep(b["cols"], a["cols"]),
              "%s->%s" % (b["cols"], a["cols"]))
    if dy:
        check("%s B3 行高等比" % tag, ratio_keep(b["rows"], a["rows"]),
              "%s->%s" % (b["rows"], a["rows"]))
    # B4 合并结构保留
    if merge:
        raw = str(r1.get("raw", ""))
        check("%s B4 存储保留 rowspan/colspan" % tag,
              'rowspan="3"' in raw and 'colspan="4"' in raw,
              raw.replace("\n", " ")[:180])
        check("%s B4b DOM 仍为单格" % tag, a["ncell"] == 1 and b["ncell"] == 1,
              "%d->%d" % (b["ncell"], a["ncell"]))
    log("CASE %s end" % tag)
    return (b, a, d)


case("V1 全合并 拖下边框 +60", True, "s", 0, 60)
case("V2 全合并 拖下边框 -50", True, "s", 0, -50)
case("V3 全合并 拖右边框 +80", True, "e", 80, 0)
case("V4 全合并 拖右下角 +60/+40", True, "se", 60, 40)
case("V5 未合并 拖下边框 +60", False, "s", 0, 60)
case("V6 未合并 拖右边框 -80", False, "e", -80, 0)

log("SUMMARY TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
os._exit(0)
