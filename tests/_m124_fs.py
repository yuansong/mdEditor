import os
# -*- coding: utf-8 -*-
"""m124：v3.38 CODE-12b —— 代码块全屏的关闭 / 还原入口验收

用户报告：代码块进入全屏后没有关闭和缩小的按钮。
断言：全屏态必须有**可见**的「✕ 退出全屏」按钮，且还原按钮的 title 要跟随状态。
"""
import json, os, sys

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication(sys.argv)
from mainwindow import MainWindow

win = MainWindow()
win.show()

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m124.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))


def js(code, t=15000):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(t, loop.quit); win._js_active(code, cb); loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def fs_state():
    v = js("(function(){var cb=document.querySelector('#editor .codeblock');"
           "if(!cb)return '{}';"
           "var fs=cb.querySelector('.fs-btn'), fx=cb.querySelector('.fs-x');"
           "return JSON.stringify({"
           " isFs: cb.classList.contains('fs'),"
           " fsText: fs?fs.textContent:'', fsTitle: fs?fs.title:'',"
           " hasX: !!fx, xText: fx?fx.textContent:'',"
           " xDisp: fx?getComputedStyle(fx).display:''})})()")
    try:
        return json.loads(v)
    except Exception:
        return {}


def click_fs():
    return js("(function(){var b=document.querySelector('#editor .codeblock .fs-btn');"
              "if(!b)return 'nobtn';b.click();return 'ok'})()")


def click_x():
    return js("(function(){var b=document.querySelector('#editor .codeblock .fs-x');"
              "if(!b)return 'nobtn';b.click();return 'ok'})()")


wait(2800)
SRC = "```python\nprint('hello')\nprint('world')\n```"
js("window.setMarkdown(" + json.dumps(SRC) + ")")
wait(900)

# ---------- A 初始态 ----------
st = fs_state()
check("A1 代码块有全屏按钮 ⛶", st.get("fsText") == "⛶", str(st))
check("A1 非全屏时 ✕ 按钮隐藏", st.get("xDisp") == "none", str(st))
check("A1 非全屏 title 提示「全屏编辑」", "全屏编辑" in st.get("fsTitle", ""), st.get("fsTitle"))

# ---------- B 进入全屏 ----------
click_fs()
wait(500)
st = fs_state()
check("B1 进入全屏（.fs）", st.get("isFs") is True, str(st))
check("B2 全屏态出现 ✕ 退出全屏按钮且**可见**（用户报告的核心缺陷）",
      st.get("hasX") and st.get("xDisp") != "none" and "退出全屏" in st.get("xText", ""), str(st))
check("B3 全屏态还原按钮 title 更新为「还原」（不再恒写「全屏编辑」）",
      "还原" in st.get("fsTitle", ""), st.get("fsTitle"))
check("B4 还原按钮图标为 ⤡", st.get("fsText") == "⤡", st.get("fsText"))

# ---------- C 点 ✕ 退出 ----------
click_x()
wait(500)
st = fs_state()
check("C1 点 ✕ 退出全屏", st.get("isFs") is False, str(st))
check("C2 退出后 ✕ 按钮重新隐藏", st.get("xDisp") == "none", str(st))
check("C3 退出后 title 复位为「全屏编辑」", "全屏编辑" in st.get("fsTitle", ""), st.get("fsTitle"))
check("C4 退出后图标复位为 ⛶", st.get("fsText") == "⛶", st.get("fsText"))

# ---------- D Esc 退出路径状态一致 ----------
click_fs()
wait(400)
check("D0 再次进入全屏", fs_state().get("isFs") is True, str(fs_state()))
js("(function(){var cb=document.querySelector('#editor .codeblock');"
   "var ev=new KeyboardEvent('keydown',{key:'Escape',bubbles:true});"
   "(cb.querySelector('pre.fence code')||cb).dispatchEvent(ev);return 'ok'})()")
wait(500)
st = fs_state()
check("D1 Esc 退出全屏", st.get("isFs") is False, str(st))
check("D2 Esc 退出后 title 也复位（点击 / Esc 两条路径一致）",
      "全屏编辑" in st.get("fsTitle", ""), st.get("fsTitle"))
check("D3 Esc 退出后 ✕ 隐藏", st.get("xDisp") == "none", str(st))

# ---------- E 退出后自动换行态按源码还原 ----------
js("window.setMarkdown(" + json.dumps("```python wrap=1\nprint('hi')\n```") + ")")
wait(800)
wr0 = js("(function(){var cb=document.querySelector('#editor .codeblock');"
         "return String(cb.classList.contains('wrap-on'))})()")
click_fs()
wait(400)
click_x()
wait(400)
wr1 = js("(function(){var cb=document.querySelector('#editor .codeblock');"
         "return String(cb.classList.contains('wrap-on'))})()")
check("E1 源码 wrap=1 → 初始换行开启", str(wr0).lower() == "true", "wrap-on=%s" % wr0)
check("E2 全屏往返后换行态按源码还原（不残留强制换行）", str(wr1).lower() == "true", "wrap-on=%s" % wr1)

with open(OUT, "w", encoding="utf-8") as f:
    for s_, name, detail in _log:
        f.write("%s %s%s\n" % (s_, name, (" | " + detail) if detail and s_ == "FAIL" else ""))
print("done")
