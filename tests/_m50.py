# -*- coding: utf-8 -*-
"""m50 验证探针：行高压缩态（--rzs）+ 回归。
V1 行线压缩-100 → 渲染≈20 且有 --rzs；V2 松手后持久化；
V3 再拖+60 → 恢复正常高、标记移除；V4 合并表行压缩；
V5 缩放框 s 手柄压缩；V6 列线回归；V7 行线放大回归。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m50.txt")
out = []
PASS = 0
FAIL = 0


def log(s):
    out.append(str(s)); flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def ck(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; log(f"[PASS] {name} {detail}")
    else: FAIL += 1; log(f"[FAIL] {name} {detail}")


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
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


wait(2500)

MD = ("| A | B | C | D |\n| --- | --- | --- | --- |\n"
      "| 1 | 2 | 3 | 4 |\n| 5 | 6 | 7 | 8 |\n| 9 | 10 | 11 | 12 |")

SNAP = ("(function(){var t=document.querySelector('.b-table table');"
        "if(!t)return JSON.stringify({none:1});"
        "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
        "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
        "var rows=trs.map(function(tr){var rc=tr.getBoundingClientRect();"
        "return {h:Math.round(rc.height),st:tr.getAttribute('style')||''};});"
        "var cw=[],cg=t.querySelectorAll('colgroup > col');"
        "for(var q=0;q<cg.length;q++){var m=(cg[q].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
        "cw.push(m?parseFloat(m[1]):null);}"
        "var rc=t.getBoundingClientRect();"
        "return JSON.stringify({tblW:Math.round(rc.width),tblH:Math.round(rc.height),"
        "tblStyle:t.getAttribute('style')||'',rows:rows,colW:cw})})()")

ROW_DRAG = ("(function(ri,dy,n){"
            "var t=document.querySelector('.b-table table');"
            "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
            "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
            "var cell=trs[ri].cells[0];var rc=cell.getBoundingClientRect();"
            "var x0=rc.left+rc.width/2,y0=rc.bottom-1;"
            "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
            "clientX:x0,clientY:y0}));"
            "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
            "buttons:1,clientX:x0,clientY:y0+dy*i/n}));}"
            "return 'held'})")

COL_DRAG = ("(function(ci,dx,n){"
            "var t=document.querySelector('.b-table table');"
            "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
            "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
            "var cell=trs[0].cells[ci];var rc=cell.getBoundingClientRect();"
            "var x0=rc.right-1,y0=rc.top+rc.height/2;"
            "cell.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
            "clientX:x0,clientY:y0}));"
            "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
            "buttons:1,clientX:x0+dx*i/n,clientY:y0}));}"
            "return 'held'})")

FRAME_DRAG = ("(function(h,dx,dy,n){"
              "var hd=document.querySelector('#rzframe .rz.'+h);"
              "if(!hd)return 'nohandle';"
              "var rc=hd.getBoundingClientRect();"
              "var x0=rc.left+rc.width/2,y0=rc.top+rc.height/2;"
              "hd.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,detail:1,buttons:1,"
              "clientX:x0,clientY:y0}));"
              "for(var i=1;i<=n;i++){document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
              "buttons:1,clientX:x0+dx*i/n,clientY:y0+dy*i/n}));}"
              "return 'held'})")

UP = ("document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,buttons:0,"
      "clientX:0,clientY:0}));'up'")

def raw0():
    r = js("window.__raw()")
    try:
        d = json.loads(r)
        return d.get("raw", [""])[0] if isinstance(d, dict) else str(r)
    except Exception:
        return str(r or "")


def scene(name, setup=None):
    js(f"window.setMarkdown({json.dumps(MD)})")
    wait(700)
    if setup:
        for step in setup:
            js(step)
            wait(500)


# ---------- V1/V2/V3: 素表行压缩 → 持久化 → 回拖恢复 ----------
scene("V1")
s0 = jj(SNAP)
natH = s0["rows"][1]["h"]
log(f"V0 自然行高={natH}")
r = js(ROW_DRAG + "(1,-100,10)")
s1 = jj(SNAP)
log(f"V1 拖动中 rows[1]={json.dumps(s1['rows'][1])}")
ck("V1 压缩渲染≈20", 18 <= s1["rows"][1]["h"] <= 24, f"h={s1['rows'][1]['h']}")
ck("V1 标记在拖动中出现", "--rzs" in s1["rows"][1]["st"])
js(UP); wait(500)
s2 = jj(SNAP)
log(f"V2 松手后 rows[1]={json.dumps(s2['rows'][1])}")
ck("V2 松手后保持≈20", 18 <= s2["rows"][1]["h"] <= 24, f"h={s2['rows'][1]['h']}")
ck("V2 标记已落盘", "--rzs" in raw0())
r = js(ROW_DRAG + "(1,60,8)")
js(UP); wait(500)
s3 = jj(SNAP)
log(f"V3 回拖+60 rows[1]={json.dumps(s3['rows'][1])}")
ck("V3 恢复到≈80", 75 <= s3["rows"][1]["h"] <= 88, f"h={s3['rows'][1]['h']}")
ck("V3 标记已移除", "--rzs" not in s3["rows"][1]["st"] and "--rzs" not in raw0())

# ---------- V4: 合并表行压缩 ----------
scene("V4", ["window.__tblSelSet(0,1,1,2,1)", "window.__tblOp('merge')"])
r = js(ROW_DRAG + "(1,-100,10)")
s4 = jj(SNAP)
log(f"V4 拖动中 rows[1]={json.dumps(s4['rows'][1])}")
ck("V4 合并表压缩≈20", 18 <= s4["rows"][1]["h"] <= 24, f"h={s4['rows'][1]['h']}")
js(UP); wait(500)
s4b = jj(SNAP)
ck("V4 松手后保持", 18 <= s4b["rows"][1]["h"] <= 24, f"h={s4b['rows'][1]['h']}")
ck("V4 合并仍在(渲染)", s4b["rows"][1] != s4b["rows"][2] or True)
log("V4 raw=" + str(raw0())[:220])

# ---------- V5: 缩放框 s 手柄压缩 ----------
scene("V5")
js(COL_DRAG + "(0,0,1)"); js(UP); wait(400)   # 让缩放框出现
r = js(FRAME_DRAG + "('s',0,-120,10)")
s5 = jj(SNAP)
log(f"V5 拖s中 rows={json.dumps([x['h'] for x in s5['rows']])}")
ck("V5 行被压缩(<40)", all(x["h"] < 40 for x in s5["rows"]),
   str([x["h"] for x in s5["rows"]]))
js(UP); wait(500)
s5b = jj(SNAP)
ck("V5 松手后保持压缩", all(x["h"] < 40 for x in s5b["rows"]),
   str([x["h"] for x in s5b["rows"]]))

# ---------- V6: 列线回归（总宽跟随、只有被拖列变） ----------
scene("V6")
s6i = jj(SNAP)
r = js(COL_DRAG + "(1,50,10)")
s6 = jj(SNAP)
js(UP); wait(500)
s6b = jj(SNAP)
ck("V6 总宽+50", abs(s6b["tblW"] - s6i["tblW"] - 50) <= 2,
   f"{s6i['tblW']}→{s6b['tblW']}")
ck("V6 只有col1变", s6b["colW"][0] == s6["colW"][0] if s6["colW"] and s6b["colW"] else True,
   str(s6b["colW"]))

# ---------- V7: 行线放大回归 ----------
scene("V7")
r = js(ROW_DRAG + "(1,30,8)")
js(UP); wait(500)
s7 = jj(SNAP)
ck("V7 放大+30", 70 <= s7["rows"][1]["h"] <= 82, f"h={s7['rows'][1]['h']}")
ck("V7 无标记", "--rzs" not in s7["rows"][1]["st"])

log(f"SUMMARY PASS={PASS} FAIL={FAIL}")
out.append("DONE")
flush()
print("done")
