# -*- coding: utf-8 -*-
"""m51 探针（真实输入）：合并后再拖拉边线——复刻用户流程。
R1 合并(rows1-2 x cols1-2)后真实拖合并格右缘 +50；R2 再真实拖 -60；
R3 真实拖行线 +30。拖动中/松手后均度量表宽、列宽、合并结构、raw。"""
import ctypes, json, os, random, sys, time
from ctypes import wintypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QPoint, QTimer
from PySide6.QtCore import Qt as _Qt

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m51.txt")
out = []
PASS = 0
FAIL = 0


def log(msg):
    out.append(str(msg)); flush()


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
win.setWindowFlag(_Qt.WindowStaysOnTopHint, True)
win.showMaximized()
win.raise_()
win.activateWindow()


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


def raw0():
    r = js("window.__raw()")
    try:
        d = json.loads(r)
        return d.get("raw", [""])[0] if isinstance(d, dict) else str(r)
    except Exception:
        return str(r or "")


wait(2500)

user32 = ctypes.windll.user32
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
SM_XVIRTUAL, SM_YVIRTUAL, SM_CXVIRTUAL, SM_CYVIRTUAL = 76, 77, 78, 79
VX, VY = user32.GetSystemMetrics(SM_XVIRTUAL), user32.GetSystemMetrics(SM_YVIRTUAL)
VW, VH = user32.GetSystemMetrics(SM_CXVIRTUAL), user32.GetSystemMetrics(SM_CYVIRTUAL)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]


class _INPUTU(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTU)]


def send_mouse(px, py, flags):
    nx = int((px - VX) * 65536 / max(1, VW - 1))
    ny = int((py - VY) * 65536 / max(1, VH - 1))
    inp = INPUT()
    inp.type = 0
    inp.mi.dx, inp.mi.dy = nx, ny
    inp.mi.dwFlags = flags | MOUSEEVENTF_ABSOLUTE
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


pt = wintypes.POINT()
user32.GetCursorPos(ctypes.byref(pt))
CURSOR_SAVE = (pt.x, pt.y)


def to_phys(lx, ly):
    dpr = win.devicePixelRatioF()
    return int(round(lx * dpr)), int(round(ly * dpr))


def cursor_pos():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def move_to(px, py, steps=8):
    cx, cy = cursor_pos()
    for i in range(1, steps + 1):
        t = i / steps
        send_mouse(int(cx + (px - cx) * t), int(cy + (py - cy) * t), MOUSEEVENTF_MOVE)
        time.sleep(0.006)


def real_drag(p0, p1, n=30, jit=2.0, seed=7, down_ms=40, step_ms=9):
    rnd = random.Random(seed)
    move_to(*p0)
    time.sleep(0.06)
    send_mouse(p0[0], p0[1], MOUSEEVENTF_LEFTDOWN)
    time.sleep(down_ms / 1000.0)
    for i in range(1, n + 1):
        t = i / n
        x = p0[0] + (p1[0] - p0[0]) * t + rnd.uniform(-jit, jit)
        y = p0[1] + (p1[1] - p0[1]) * t + rnd.uniform(-jit, jit)
        send_mouse(int(x), int(y), MOUSEEVENTF_MOVE)
        time.sleep(step_ms / 1000.0)
    send_mouse(p1[0], p1[1], MOUSEEVENTF_LEFTUP)
    time.sleep(0.15)


# ---------- 前置：点标题栏确保前台 ----------
MD = ("| A | B | C | D |\n| --- | --- | --- | --- |\n"
      "| 1 | 2 | 3 | 4 |\n| 5 | 6 | 7 | 8 |\n| 9 | 10 | 11 | 12 |")

fg = win.frameGeometry()
tb = fg.topLeft() + QPoint(fg.width() // 2, 12)
move_to(*to_phys(tb.x(), tb.y()))
time.sleep(0.05)
send_mouse(*to_phys(tb.x(), tb.y()), MOUSEEVENTF_LEFTDOWN)
time.sleep(0.04)
send_mouse(*to_phys(tb.x(), tb.y()), MOUSEEVENTF_LEFTUP)
wait(300)
_hwnd = user32.GetForegroundWindow()
_buf = ctypes.create_unicode_buffer(256)
user32.GetWindowTextW(_hwnd, _buf, 256)
log(f"DIAG foreground title={repr(_buf.value)} win_hwnd={int(win.winId())}")
DPR = win.devicePixelRatioF()
log(f"ENV dpr={DPR}")

SNAP = ("(function(){var t=document.querySelector('.b-table table');"
        "if(!t)return JSON.stringify({none:1});"
        "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
        "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
        "var rows=trs.map(function(tr){var cs=[];"
        "for(var j=0;j<tr.cells.length;j++){var c=tr.cells[j].getBoundingClientRect();"
        "cs.push([Math.round(c.left),Math.round(c.right)]);}"
        "return cs;});"
        "var cw=[],cg=t.querySelectorAll('colgroup > col');"
        "for(var q=0;q<cg.length;q++){var m=(cg[q].getAttribute('style')||'').match(/width\\s*:\\s*([\\d.]+)px/i);"
        "cw.push(m?parseFloat(m[1]):null);}"
        "var rc=t.getBoundingClientRect();"
        "return JSON.stringify({tblW:Math.round(rc.width),tblH:Math.round(rc.height),"
        "tblStyle:t.getAttribute('style')||'',rows:rows,colW:cw})})()")


def border_vp(ri, ci):
    """行 ri 第 ci 个 DOM 格右缘中点（视口 CSS px）"""
    d = jj("(function(){var t=document.querySelector('.b-table table');"
           "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
           "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
           "var el=trs[" + str(ri) + "].cells[" + str(ci) + "];"
           "var rc=el.getBoundingClientRect();"
           "return JSON.stringify({x:rc.right-2,y:rc.top+rc.height/2})})()")
    return d.get("x"), d.get("y")


def rowline_vp(ri, ci):
    d = jj("(function(){var t=document.querySelector('.b-table table');"
           "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
           "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
           "var el=trs[" + str(ri) + "].cells[" + str(ci) + "];"
           "var rc=el.getBoundingClientRect();"
           "return JSON.stringify({x:rc.left+rc.width/2,y:rc.bottom-2})})()")
    return d.get("x"), d.get("y")


def _view_global(x, y):
    return win._view.mapToGlobal(QPoint(int(x), int(y)))


def vp_phys(x, y):
    g = win._view.mapToGlobal(QPoint(int(x + OFFX), int(y + OFFY)))
    return to_phys(g.x(), g.y())


# ---------- 坐标自校准：mapToGlobal 与实际 page 坐标存在偏差，实测偏移 ----------
OFFX, OFFY = 0, 0
js("window.__cal=[];document.addEventListener('mousemove',function(e){"
   "if(window.__cal.length<400)window.__cal.push([e.clientX,e.clientY]);},true);")
CALX, CALY = 400, 300
move_to(*to_phys(_view_global(CALX, CALY).x(), _view_global(CALX, CALY).y()), steps=12)
wait(150)
cal = jj("JSON.stringify((window.__cal||[]).slice(-1))")
try:
    _c = json.loads(cal) if isinstance(cal, str) else cal
    OFFX, OFFY = CALX - _c[0][0], CALY - _c[0][1]
except Exception:
    OFFX, OFFY = 0, 0
log(f"CALIB 实际落点={cal} 偏移=({OFFX},{OFFY})")
js("delete window.__cal")


def scene(name, setup=None):
    js(f"window.setMarkdown({json.dumps(MD)})")
    wait(700)
    if setup:
        for step in setup:
            js(step)
            wait(500)
    log(f"=== {name} 初始 ===")
    log(json.dumps(jj(SNAP), ensure_ascii=False))


# ---------- R1: 合并 rows1-2 x cols1-2 → 真实拖合并格右缘 +50 ----------
scene("R1 合并后拖右缘", ["window.__tblSelSet(0,1,1,2,2)", "window.__tblOp('merge')"])
s0 = jj(SNAP)
x, y = border_vp(1, 1)     # 体行1 现有 cells=[c0, 合并(c1-c2), c3] → 索引1=合并格
# 诊断：命中测试 + 事件记录
js("window.__dbg=[];document.addEventListener('mousedown',function(e){"
   "var el=document.elementFromPoint(e.clientX,e.clientY);"
   "window.__dbg.push(['down',e.clientX,e.clientY,"
   "el?(el.tagName+'.'+(el.className||'')):'null']);},true);"
   "document.addEventListener('mousemove',function(e){"
   "if(window.__dbg.length<12)window.__dbg.push(['mv',e.clientX,e.clientY,e.buttons]);},true);")
hit = jj(f"(function(){{var el=document.elementFromPoint({x},{y});"
         "return JSON.stringify({tag:el?el.tagName:'null',cls:el?(el.className||''):'',"
         "txt:el?(el.textContent||'').slice(0,10):''})})()")
log(f"R1 命中测试 @({x},{y}) = {json.dumps(hit, ensure_ascii=False)}")
p0 = vp_phys(x, y)
p1 = vp_phys(x + 50, y)
real_drag(p0, p1)
wait(500)
dbg = jj("JSON.stringify((window.__dbg||[]).slice(0,12))")
log(f"R1 事件流 = {dbg}")
s1 = jj(SNAP)
log("=== R1 松手后 ===")
log(json.dumps(s1, ensure_ascii=False))
ck("R1 总宽+50", abs(s1["tblW"] - s0["tblW"] - 50) <= 3, f"{s0['tblW']}→{s1['tblW']}")
ck("R1 合并保持(行1三格)", len(s1["rows"][1]) == 3, str(s1["rows"][1]))
ck("R1 合并保持(行2两格)", len(s1["rows"][2]) == 2, str(s1["rows"][2]))
r = raw0()
ck("R1 raw 有 rowspan 且含 colgroup", ("rowspan" in r) and ("colgroup" in r), r[:120])

# ---------- R2: 同表再真实拖 -60（缩窄）----------
x2, y2 = border_vp(1, 1)
p0 = vp_phys(x2, y2)
p1 = vp_phys(x2 - 60, y2)
real_drag(p0, p1, seed=11)
wait(500)
s2 = jj(SNAP)
log("=== R2 再拖-60 松手后 ===")
log(json.dumps(s2, ensure_ascii=False))
ck("R2 总宽-60", abs(s2["tblW"] - s1["tblW"] + 60) <= 3, f"{s1['tblW']}→{s2['tblW']}")
ck("R2 合并保持", len(s2["rows"][1]) == 3 and len(s2["rows"][2]) == 2)

# ---------- R3: 真实拖行线 +30 ----------
x3, y3 = rowline_vp(2, 0)
p0 = vp_phys(x3, y3)
p1 = vp_phys(x3, y3 + 30)
real_drag(p0, p1, seed=13)
wait(500)
s3 = jj(SNAP)
log("=== R3 拖行线+30 松手后 ===")
log(json.dumps(s3, ensure_ascii=False))
ck("R3 表高+30", abs(s3["tblH"] - s2["tblH"] - 30) <= 4, f"{s2['tblH']}→{s3['tblH']}")
log(f"SUMMARY PASS={PASS} FAIL={FAIL}")

# 恢复光标
move_to(*CURSOR_SAVE)
out.append("DONE")
flush()
print("done")
