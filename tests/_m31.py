# -*- coding: utf-8 -*-
"""v3.30.1 探针（真实输入）：OS 级 SendInput 鼠标拖选 + 轨迹选区断言。

背景：合成 MouseEvent 探针无法暴露真实输入差异（v3.30 sticky 轴向在
真实拖选下仍误选）。本探针用真实系统鼠标输入验证「轨迹选区」语义：
选区 = 指针实际扫过的单元格，未划过的格绝不入选（T4/T5/T8 幽灵格判别用例），
并回归合并定位（T9/T10）。运行会短暂接管真实鼠标（结束恢复原位置）。
运行方式：python tests/_runner.py tests/_m31.py（结果写入 tests/_m31.txt）。"""
import ctypes
import json
import math
import os
import random
import sys
import time
from ctypes import wintypes

# 必须在 QApplication 之前声明 DPI 感知，保证物理像素坐标一致
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

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m31.txt")
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
# v3.30.3 诊断修复：宿主（WorkBuddy 桌面端）窗口可能覆盖探针窗口并吞掉
# SendInput 事件（实测 foreground=宿主、__dbgMoves 全空）——探针窗口强制置顶
from PySide6.QtCore import Qt as _Qt
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


def raw():
    return jj("window.__raw()").get("raw") or [""]


wait(2500)

# ---------- SendInput 基础设施 ----------
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
    """Qt 逻辑屏幕坐标 → 物理像素"""
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


def click(px, py):
    move_to(px, py)
    time.sleep(0.05)
    send_mouse(px, py, MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.04)
    send_mouse(px, py, MOUSEEVENTF_LEFTUP)
    time.sleep(0.08)


def real_drag(p0, p1, n=36, jit=3.0, seed=7, down_ms=40, step_ms=9):
    """真实拖拽：移动到起点 → 按下 → 逐点移动（带随机抖动）→ 松开"""
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
    time.sleep(0.12)


# ---------- 前置：置顶窗口（点标题栏确保前台） + 装载表格 ----------
MD = ("| A | B | C | D | E |\n| --- | --- | --- | --- | --- |\n"
      "| 1 | 2 | 3 | 4 | 5 |\n"
      "| 6 | 7 | 8 | 9 | 10 |\n"
      "| 11 | 12 | 13 | 14 | 15 |\n"
      "| 16 | 17 | 18 | 19 | 20 |\n"
      "| 21 | 22 | 23 | 24 | 25 |")

js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
js("window.__dbgMoves=[];document.addEventListener('mousemove',function(e){"
   "window.__dbgMoves.push([e.clientX,e.clientY,e.buttons]);},true);")
wait(200)

# 点击标题栏把窗口带到前台（标题栏不属于网页内容，不产生编辑副作用）
fg = win.frameGeometry()
tb = fg.topLeft() + QPoint(fg.width() // 2, 12)
click(*to_phys(tb.x(), tb.y()))
wait(300)
# v3.30.3 诊断：确认窗口是否真的到前台（SendInput 只对同完整性级别会话生效）
_hwnd = user32.GetForegroundWindow()
_buf = ctypes.create_unicode_buffer(256)
user32.GetWindowTextW(_hwnd, _buf, 256)
log(f"DIAG foreground hwnd={_hwnd} title={repr(_buf.value)} win_hwnd={int(win.winId())}")

DPR = win.devicePixelRatioF()
log(f"ENV dpr={DPR} view={win._view.width()}x{win._view.height()} "
    f"virtual=({VX},{VY},{VW},{VH})")


def cell_vp(r, c):
    """单元格中心（视口 CSS px）"""
    d = jj("(function(){var t=document.querySelector('.b-table table');"
           "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
           "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
           "var el=trs[" + str(r) + "].cells[" + str(c) + "];"
           "var rc=el.getBoundingClientRect();"
           "return JSON.stringify({x:rc.left+rc.width/2,y:rc.top+rc.height/2})})()")
    return d.get("x"), d.get("y")


def cell_phys(r, c):
    x, y = cell_vp(r, c)
    g = win._view.mapToGlobal(QPoint(int(x), int(y)))
    return to_phys(g.x(), g.y())


def sel():
    return jj("window.__tblSel()")


def axis():
    return jj("window.__tblDragState()")


def moves_tail(n=6):
    d = jj("(function(){var m=window.__dbgMoves||[];"
           "return JSON.stringify(m.slice(-" + str(n) + "))})()")
    return d


def reset_moves():
    js("window.__dbgMoves=[]")


def trial(name, r0, c0, r1, c1, jit=3.0, seed=7, click_first=True):
    p0 = cell_phys(r0, c0)
    p1 = cell_phys(r1, c1)
    if click_first:
        click(*p0)          # 真实用户流程：先单击选中单元格，再按住拖动
        wait(120)
    # 诊断：mousedown 前起点格中心的实际命中元素（不依赖外部注入变量）
    hit = jj("(function(){var t=document.querySelector('.b-table table');"
             "var trs=[];if(t.tHead)for(var i=0;i<t.tHead.rows.length;i++)trs.push(t.tHead.rows[i]);"
             "var b=t.tBodies[0];for(var k=0;k<b.rows.length;k++)trs.push(b.rows[k]);"
             "var el=trs[" + str(r0) + "].cells[" + str(c0) + "];"
             "var rc=el.getBoundingClientRect();"
             "var p=document.elementFromPoint(rc.left+rc.width/2, rc.top+rc.height/2);"
             "return p?p.tagName+'.'+(p.className||''):'null'})()")
    log(f"DIAG {name} p0hit={hit}")
    reset_moves()
    real_drag(p0, p1, jit=jit, seed=seed)
    wait(250)
    s = sel()
    a = axis()
    m = moves_tail()
    log(f"T {name} | sel={json.dumps(s, ensure_ascii=False)} | st={json.dumps(a, ensure_ascii=False)} | moves_tail={json.dumps(m, ensure_ascii=False)}")
    return s


def trail_set(s):
    """v3.30.4 矩形语义：由 r0..r1/c0..c1 生成选区键集合（旧轨迹字段已退役）"""
    if not s or "r0" not in s:
        return set()
    return {f"{r},{c}"
            for r in range(s["r0"], s["r1"] + 1)
            for c in range(s["c0"], s["c1"] + 1)}


results = []


def expect(name, cond, extra=""):
    results.append((name, cond, extra))
    log(f"{'PASS' if cond else 'FAIL'} | {name} | {extra}")


# ---------- 真实输入断言（v3.30.4 对角矩形 + 统一纳入门控语义） ----------
# T1: 下拖（点击后拖动）→ 锚点列 3 格（矩形）
s = trial("T1 下拖(2,1)->(4,1) 点击后拖动", 2, 1, 4, 1, jit=3.0, seed=11)
expect("T1 下拖 → 只选本列 3 格（矩形）",
       s.get("r0") == 2 and s.get("r1") == 4 and s.get("c0") == 1 and s.get("c1") == 1
       and len(trail_set(s)) == 3, json.dumps(s, ensure_ascii=False))

# T2: 右拖 → 锚点行 3 格（矩形）
s = trial("T2 右拖(2,1)->(2,3) 点击后拖动", 2, 1, 2, 3, jit=3.0, seed=12)
expect("T2 右拖 → 只选本行 3 格（矩形）",
       s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 3
       and len(trail_set(s)) == 3, json.dumps(s, ensure_ascii=False))

# T3: 下拖大抖动（±6px，仍在列内，远小于列阈值 T=min(宽50%,32px)）→ 仍只选本列
s = trial("T3 下拖(1,1)->(4,1) 直接按住大抖动", 1, 1, 4, 1, jit=6.0, seed=13, click_first=False)
expect("T3 下拖大抖动 → 只选本列 4 格",
       s.get("c0") == 1 and s.get("c1") == 1 and s.get("r0") == 1 and s.get("r1") == 4,
       json.dumps(s, ensure_ascii=False))

# T4: 右拖终点落在下一行 → 矩形语义：(3,1) 属于对角矩形（2..3 行 × 1..3 列）
s = trial("T4 右拖(2,1)->(3,3) 终点落下一行", 2, 1, 3, 3, jit=3.0, seed=14)
tk = trail_set(s)
expect("T4 右拖终点下一行 → 矩形 2..3×1..3 共 6 格",
       s.get("r0") == 2 and s.get("r1") == 3 and s.get("c0") == 1 and s.get("c1") == 3
       and "3,1" in tk and len(tk) == 6,
       "rect=" + json.dumps(sorted(tk), ensure_ascii=False))

# T5: 对角拖 → 矩形 = 全表 30 格（6 行 × 5 列；对角语义，L/Z 轨迹不再特殊处理）
s = trial("T5 对角(0,0)->(5,4)", 0, 0, 5, 4, jit=3.0, seed=15, click_first=False)
tk = trail_set(s)
expect("T5 对角拖 → 全表矩形 30 格",
       s.get("r0") == 0 and s.get("r1") == 5 and s.get("c0") == 0 and s.get("c1") == 4
       and len(tk) == 30,
       "rect=" + json.dumps(sorted(tk), ensure_ascii=False))

# T6/T7: 上拖 / 左拖
s = trial("T6 上拖(4,2)->(1,2)", 4, 2, 1, 2, jit=3.0, seed=16)
expect("T6 上拖 → 只选本列 4 格",
       s.get("c0") == 2 and s.get("c1") == 2 and s.get("r0") == 1 and s.get("r1") == 4,
       json.dumps(s, ensure_ascii=False))
s = trial("T7 左拖(2,3)->(2,1)", 2, 3, 2, 1, jit=3.0, seed=17)
expect("T7 左拖 → 只选本行 3 格",
       s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 3,
       json.dumps(s, ensure_ascii=False))

# T8: 下拖终点落右列 → 矩形语义：行 1..4 × 列 1..2 全部入选
s = trial("T8 下拖(1,1)->(4,2) 终点落右列", 1, 1, 4, 2, jit=3.0, seed=18)
tk = trail_set(s)
expect("T8 下拖终点右列 → 矩形 8 格（含左列全部行）",
       s.get("r0") == 1 and s.get("r1") == 4 and s.get("c0") == 1 and s.get("c1") == 2
       and len(tk) == 8,
       "rect=" + json.dumps(sorted(tk), ensure_ascii=False))

# T9: 干净矩形拖选 → 合并停在原位（合并定位回归）
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
x0, y0 = cell_vp(2, 1); g0 = win._view.mapToGlobal(QPoint(int(x0), int(y0))); p0 = to_phys(g0.x(), g0.y())
x1, y1 = cell_vp(2, 2); g1 = win._view.mapToGlobal(QPoint(int(x1), int(y1))); p1 = to_phys(g1.x(), g1.y())
click(*p0); wait(120)
real_drag(p0, p1, jit=2.0, seed=19)
wait(250)
s = sel()
pre_ok = s.get("r0") == 2 and s.get("r1") == 2 and s.get("c0") == 1 and s.get("c1") == 2
js("window.__tblOp('merge')")
wait(600)
r = raw()[0]
expect("T9 真实拖选(2,1)->(2,2) → 合并格停在原位",
       pre_ok and '<td>6</td><td colspan="2">7 8</td><td>9</td>' in r,
       "sel=" + json.dumps(s, ensure_ascii=False) + " | " + r[:260])

# T10: 程序化选区合并中间两格（存储链路回归）
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)
js("window.__tblSelSet(0, 2, 1, 2, 2)")
wait(300)
js("window.__tblOp('merge')")
wait(600)
r = raw()[0]
expect("T10 程序化合并中间两格 → colspan=2 停在原位",
       '<td>6</td><td colspan="2">7 8</td><td>9</td>' in r, r[:260])

# 恢复真实鼠标位置
send_mouse(CURSOR_SAVE[0], CURSOR_SAVE[1], MOUSEEVENTF_MOVE)
out.append("DONE")
flush()
print("done")
