# -*- coding: utf-8 -*-
"""m130：v3.38 SYN-3 预览 → 源码反向滚动同步
A组 JS 接口自检：pollPrevScroll 结构 / scrollSrcToBlock 存在 / 预览侧调用无效
B组 反向主路径：用户滚动预览 → 源码跟随（scrollY 变化 + 块号对应 + 内部状态）
C组 循环防护：源码滚动 → 预览跟随（正向仍在），随后两侧位置稳定不振荡
D组 让权窗口：_sync_ts_prev2src 未过期时 _on_src_scroll 早退（不重发）
"""
import os, sys, time, json

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication(sys.argv)
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m130.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  | " + str(detail)))


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def js(view, code):
    out = []
    lp = QEventLoop()

    def cb(r):
        out.append(r)
        lp.quit()

    win._js_view(view, code, cb)
    lp.exec()
    return out[0] if out else None


win = MainWindow()
_sa_backup = win._settings.value("startupAction")
_lf_backup = win._settings.value("lastFile")
win.show()
wait(2600)

# ---------- 准备：30 段长文档 + 进入双栏 ----------
md = "\n\n".join("## 段落%02d\n\n这是第 %d 段的正文内容，用于拉开文档高度以测试滚动同步。" % (i, i)
                 for i in range(30))
win._push_text(md)
wait(600)
win._set_mode("dual")
_t0 = time.monotonic()
while time.monotonic() - _t0 < 12:
    if (win._dual and win._vstate.get("src", {}).get("loaded")
            and win._vstate.get("prev", {}).get("loaded")):
        break
    wait(200)
check("P0 双栏就绪（src/prev 均 loaded）",
      win._dual and win._vstate.get("src", {}).get("loaded")
      and win._vstate.get("prev", {}).get("loaded"), "")
wait(1500)   # 让初始源码→预览同步发生，且程序性滚动 guard（0.6s）过期

# ---------- A JS 接口自检 ----------
r = json.loads(js(win._view_prev, "window.pollPrevScroll()"))
check("A1 预览侧 pollPrevScroll 返回合法结构（顶部 idx=0）",
      isinstance(r, dict) and r.get("idx") == 0 and "frac" in r, str(r))
check("A2 源码侧 scrollSrcToBlock 已注入", js(
    win._view_src, "String(typeof window.scrollSrcToBlock)") == "function", "")
_y0 = js(win._view_prev, "window.scrollY")
js(win._view_prev, "window.scrollSrcToBlock(5,0)")   # 预览页调用应被 __previewLock 拦截
wait(250)
check("A3 预览侧调用 scrollSrcToBlock 无效果",
      js(win._view_prev, "window.scrollY") == _y0, "%s -> %s" % (_y0, js(win._view_prev, "window.scrollY")))

# ---------- B 反向主路径：用户滚动预览 → 源码跟随 ----------
print("---- B 组时间线 ----")
sy0 = js(win._view_src, "window.scrollY")
_rt = js(win._view_prev,
         "(function(){var b=document.querySelectorAll('#editor > *')[20];"
         "if(!b)return 'NOBLK';"
         "var y=b.getBoundingClientRect().top+window.scrollY-40;"
         "window.scrollTo(0,y);return 'scrolled:'+Math.round(y)+':'+document.querySelectorAll('#editor > *').length;})()")
print("scrollTo ret:", _rt, "prevY:", js(win._view_prev, "window.scrollY"))
for _i in range(7):
    wait(400)
    pp = json.loads(js(win._view_prev, "window.pollPrevScroll()"))
    ps2 = json.loads(js(win._view_src, "window.pollSrcScroll()"))
    print("[%dms] prevPoll=%s srcPoll=%s srcY=%s lastSrc=%s lastPrev=%s d_prev2src=%.2f d_src2prev=%.2f" % (
        (_i + 1) * 400, pp, ps2, js(win._view_src, "window.scrollY"),
        win._last_src_pair, win._last_prev_pair,
        time.monotonic() - win._sync_ts_prev2src,
        time.monotonic() - win._sync_ts_src2prev))
sy1 = js(win._view_src, "window.scrollY")
ps = json.loads(js(win._view_src, "window.pollSrcScroll()"))
check("B1 用户滚预览后源码 scrollY 发生变化", isinstance(sy1, (int, float)) and sy1 > sy0 + 50,
      "before=%s after=%s" % (sy0, sy1))
check("B2 源码视口顶部块号与预览目标块(20)对应",
      isinstance(ps.get("idx"), int) and 14 <= ps["idx"] <= 26, str(ps))
check("B3 反向同步内部状态已推进（_last_prev_pair / 时间戳）",
      win._last_prev_pair is not None and win._sync_ts_prev2src > 0,
      "pair=%s ts=%.3f" % (win._last_prev_pair, win._sync_ts_prev2src))

# ---------- C 循环防护：正向仍在 + 稳定不振荡 ----------
js(win._view_src, "window.scrollTo(0, 0)")
wait(1800)
py1 = js(win._view_prev, "window.scrollY")
check("C1 源码回顶后预览跟随回顶（正向路径未破坏）",
      isinstance(py1, (int, float)) and py1 < 120, str(py1))
s_a = js(win._view_src, "window.scrollY")
p_a = js(win._view_prev, "window.scrollY")
wait(2200)
s_b = js(win._view_src, "window.scrollY")
p_b = js(win._view_prev, "window.scrollY")
check("C2 静置后两侧位置稳定（无回环振荡）", abs(s_a - s_b) < 2 and abs(p_a - p_b) < 2,
      "src %s->%s prev %s->%s" % (s_a, s_b, p_a, p_b))

# ---------- D 让权窗口：_on_src_scroll 在 prev2src 未过期时早退 ----------
# 先滚源码到中部让正向同步建立基线（_last_src_pair 变为中部块）
js(win._view_src, "window.scrollTo(0, 1200)")
wait(900)
_mid = win._last_src_pair
check("D0 基线：滚源码后 _last_src_pair 已离开 (0,0)",
      _mid is not None and _mid != (0, 0.0), str(_mid))
win._sync_ts_prev2src = time.monotonic()     # 模拟「用户刚滚过预览」
js(win._view_src, "window.scrollTo(0, 0)")   # 让权窗口内源码再变化
win._poll_sync_scroll()
wait(500)
check("D1 让权窗口内源码侧不重发（_last_src_pair 保持中部基线）",
      win._last_src_pair == _mid, "%s -> %s" % (_mid, win._last_src_pair))
win._sync_ts_prev2src = 0.0                  # 解除让权
win._poll_sync_scroll()
wait(600)
check("D2 解除让权后源码侧恢复同步（_last_src_pair 已更新到新位置）",
      win._last_src_pair is not None and win._last_src_pair != _mid,
      "%s -> %s" % (_mid, win._last_src_pair))

# ---------- 收尾复位（防 QSettings 污染） ----------
win._set_mode("edit")
wait(600)
win._settings.setValue("startupAction", _sa_backup)
win._settings.setValue("lastFile", _lf_backup)
win._settings.sync()

print("========== 汇总 ==========")
npass = sum(1 for st, _n, _d in _log if st == "PASS")
nfail = len(_log) - npass
print("PASS=%d FAIL=%d" % (npass, nfail))
with open(OUT, "w", encoding="utf-8") as f:
    for st, name, detail in _log:
        f.write("%s %s %s\n" % (st, name, detail))
    f.write("PASS=%d FAIL=%d\n" % (npass, nfail))
