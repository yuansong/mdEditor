# -*- coding: utf-8 -*-
"""v3.30.3 探针（真实输入）：复现用户拖选三抱怨的判别性场景。

用户反馈（针对 v3.30.1 轨迹选区仍报）：
  1) 向下拖动时，必须划过目标单元格最低边框线才判定选中；
  2) 向左/向右拖动时，单元格很难被选中；
  3) 拖动过程中仍出现误选。

本探针用 OS 级 SendInput 真实鼠标输入逐项复现（按住中途暂停读 DOM .sel 类，
直接回答「指针进入目标格中上部时是否已高亮」）。场景：
  D1 下拖慢速、在目标格中部暂停（按住不放）→ 目标格应已高亮（判别抱怨1）
  D2 慢速左拖 / 右拖跨 2 列 → 恰好锚点行 3 格（判别抱怨2）
  D3 锚点距竖边框 5px 起步横向拖（避开 TBL_TOL=3 列宽误触）→ 正常选格
  D4 快速下甩（大步长事件）→ 沿途全部格入选（判别插值补齐）
  D5 锚点距底边框 5px 起步下拖 → 正常选格
  D6 右拖中途暂停 → 目标格应已高亮（判别抱怨2 的实时性）
运行方式：python tests/_runner.py tests/_m37.py（结果写入 tests/_m37.txt）。
运行会短暂接管真实鼠标（结束恢复原位置）。"""
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QPoint, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m37.txt")
out = []


def log(msg):
    out.append(msg)
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow

win = MainWindow()
win.showMaximized()
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


wait(2500)

# ---------- SendInput 基础设施（与 _m31 相同） ----------
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
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]


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


def move_to(px, py, steps=6):
    cx, cy = cursor_pos()
    for i in range(1, steps + 1):
        t = i / steps
        send_mouse(int(cx + (px - cx) * t), int(cy + (py - cy) * t), MOUSEEVENTF_MOVE)
        time.sleep(0.006)


def click(px, py):
    move_to(px, py)
    time.sleep(0.05)
    send_mouse(px, py, MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.04)
    send_mouse(px, py, MOUSEEVENTF_LEFTUP)
    time.sleep(0.08)


def slow_drag(p0, p1, n=40, step_ms=20, hold_after=None, hold_ms=500):
    """真实慢速拖拽；hold_after=(x,y) 时在该点暂停 hold_ms（仍按住），返回时仍按住。
    返回 'held' 表示在暂停点按住返回；否则拖完松开。"""
    move_to(*p0)
    time.sleep(0.06)
    send_mouse(p0[0], p0[1], MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.05)
    if hold_after is not None:
        # 先走到暂停点
        for i in range(1, n + 1):
            t = i / n
            x = p0[0] + (hold_after[0] - p0[0]) * t
            y = p0[1] + (hold_after[1] - p0[1]) * t
            send_mouse(int(x), int(y), MOUSEEVENTF_MOVE)
            time.sleep(step_ms / 1000.0)
        time.sleep(hold_ms / 1000.0)
        return "held"
    for i in range(1, n + 1):
        t = i / n
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t
        send_mouse(int(x), int(y), MOUSEEVENTF_MOVE)
        time.sleep(step_ms / 1000.0)
    send_mouse(p1[0], p1[1], MOUSEEVENTF_LEFTUP)
    time.sleep(0.15)
    return "done"


def release_at(px, py):
    send_mouse(px, py, MOUSEEVENTF_LEFTUP)
    time.sleep(0.15)


# ---------- 前置：置顶 + 装载表格 ----------
MD = ("| A | B | C | D | E |\n| --- | --- | --- | --- | --- |\n"
      "| 1 | 2 | 3 | 4 | 5 |\n"
      "| 6 | 7 | 8 | 9 | 10 |\n"
      "| 11 | 12 | 13 | 14 | 15 |\n"
      "| 16 | 17 | 18 | 19 | 20 |\n"
      "| 21 | 22 | 23 | 24 | 25 |")

js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)

fg = win.frameGeometry()
tb = fg.topLeft() + QPoint(fg.width() // 2, 12)
click(*to_phys(tb.x(), tb.y()))
wait(300)

DPR = win.devicePixelRatioF()
log(f"ENV dpr={DPR} view={win._view.width()}x{win._view.height()}")


def cell_vp(r, c):
    d = jj("(function(){var t=document.querySelector('.b-table table');"
           "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
           "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
           "var el=trs[" + str(r) + "].cells[" + str(c) + "];"
           "var rc=el.getBoundingClientRect();"
           "return JSON.stringify({x:rc.left+rc.width/2,y:rc.top+rc.height/2,"
           "l:rc.left,t:rc.top,r:rc.right,b:rc.bottom})})()")
    return d


def pt_phys(vp_x, vp_y):
    g = win._view.mapToGlobal(QPoint(int(vp_x), int(vp_y)))
    return to_phys(g.x(), g.y())


def sel():
    return jj("window.__tblSel()")


def sel_texts():
    """当前高亮（.sel）格的文本集合 —— 用户实际看见的选中态"""
    d = jj("(function(){var els=document.querySelectorAll('.b-table table td.sel,.b-table table th.sel');"
           "var a=[];for(var i=0;i<els.length;i++)a.push(els[i].textContent);"
           "return JSON.stringify(a)})()")
    return set(d) if isinstance(d, list) else d


results = []


def expect(name, cond, extra=""):
    results.append((name, cond, extra))
    log(f"{'PASS' if cond else 'FAIL'} | {name} | {extra}")


def reset():
    js(f"window.setMarkdown({json.dumps(MD)})")
    wait(600)


# ---------- D1: 下拖慢速，在目标格(3,1)中部暂停（按住）→ 应已高亮 ----------
reset()
c21 = cell_vp(2, 1); c31 = cell_vp(3, 1)
p0 = pt_phys(c21["x"], c21["y"])
mid = pt_phys(c31["x"], c31["t"] + (c31["b"] - c31["t"]) * 0.5)
st = slow_drag(p0, None, n=36, step_ms=18, hold_after=mid, hold_ms=600)
held_sel = sel_texts()
release_at(*mid)
wait(250)
s = sel()
expect("D1 下拖按住停在(3,1)中部 → 目标格已高亮（抱怨1判别）",
       st == "held" and "7" in held_sel and "12" in held_sel
       and s.get("r0") == 2 and s.get("r1") == 3 and s.get("c0") == 1 and s.get("c1") == 1,
       f"held_sel={sorted(held_sel)} sel={json.dumps(s, ensure_ascii=False)}")

# ---------- D2a: 慢速左拖 (2,3)->(2,1) ----------
reset()
c23 = cell_vp(2, 3); c21 = cell_vp(2, 1)
p0 = pt_phys(c23["x"], c23["y"]); p1 = pt_phys(c21["x"], c21["y"])
slow_drag(p0, p1, n=60, step_ms=18)
s = sel()
expect("D2a 慢速左拖跨2列 → 锚点行3格（抱怨2判别）",
       s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 3,
       json.dumps(s, ensure_ascii=False))

# ---------- D2b: 慢速右拖 (2,1)->(2,3) ----------
reset()
c21 = cell_vp(2, 1); c23 = cell_vp(2, 3)
p0 = pt_phys(c21["x"], c21["y"]); p1 = pt_phys(c23["x"], c23["y"])
slow_drag(p0, p1, n=60, step_ms=18)
s = sel()
expect("D2b 慢速右拖跨2列 → 锚点行3格（抱怨2判别）",
       s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 3,
       json.dumps(s, ensure_ascii=False))

# ---------- D3: 锚点距竖边框 5px 起步横向拖 ----------
reset()
c21 = cell_vp(2, 1); c22 = cell_vp(2, 2)
start = pt_phys(c21["r"] - 5, c21["y"])          # 距右边框 5px（>TBL_TOL=3）
p1 = pt_phys(c22["x"], c22["y"])
slow_drag(start, p1, n=40, step_ms=18)
s = sel()
expect("D3 距竖边框5px起步右拖 → 选(2,1)(2,2)（边框起步判别）",
       s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 2,
       json.dumps(s, ensure_ascii=False))

# ---------- D4: 快速下甩 (1,1)->(5,1) ----------
reset()
c11 = cell_vp(1, 1); c51 = cell_vp(5, 1)
p0 = pt_phys(c11["x"], c11["y"]); p1 = pt_phys(c51["x"], c51["y"])
slow_drag(p0, p1, n=12, step_ms=5)
s = sel()
tk = set((s.get("trail") or []))
expect("D4 快速下甩4行 → 行1~5列1全部入选（插值补齐）",
       s.get("c0") == 1 and s.get("c1") == 1 and s.get("r0") == 1 and s.get("r1") == 5
       and len(tk) == 5,
       json.dumps(s, ensure_ascii=False))

# ---------- D5: 锚点距底边框 5px 起步下拖 ----------
reset()
c21 = cell_vp(2, 1); c41 = cell_vp(4, 1)
start = pt_phys(c21["x"], c21["b"] - 5)          # 距底边框 5px
p1 = pt_phys(c41["x"], c41["y"])
slow_drag(start, p1, n=40, step_ms=18)
s = sel()
expect("D5 距底边框5px起步下拖 → 选行2~4列1",
       s.get("c0") == 1 and s.get("c1") == 1 and s.get("r0") == 2 and s.get("r1") == 4,
       json.dumps(s, ensure_ascii=False))

# ---------- D6: 右拖按住停在(2,2)中部 → 目标格应已高亮 ----------
reset()
c21 = cell_vp(2, 1); c22 = cell_vp(2, 2)
p0 = pt_phys(c21["x"], c21["y"])
mid = pt_phys(c22["x"], c22["y"])
st = slow_drag(p0, None, n=36, step_ms=18, hold_after=mid, hold_ms=600)
held_sel = sel_texts()
release_at(*mid)
wait(250)
s = sel()
expect("D6 右拖按住停在(2,2)中部 → 目标格已高亮（抱怨2实时性判别）",
       st == "held" and "7" in held_sel and "8" in held_sel
       and s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 2,
       f"held_sel={sorted(held_sel)} sel={json.dumps(s, ensure_ascii=False)}")

# 恢复真实鼠标位置
send_mouse(CURSOR_SAVE[0], CURSOR_SAVE[1], MOUSEEVENTF_MOVE)
out.append("DONE")
flush()
print("done")
