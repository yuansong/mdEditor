# -*- coding: utf-8 -*-
"""v3.15 冒烟测试：表格网格面板键盘操作（方向键调整选中行列 / 面板随选区扩缩 /
最小 1×1 / 最大 12×12 / 回车插入 / Esc 关闭）+ 代码块（语言按钮左上角 /
默认显示效果模式光标在代码区 / 代码区回车换行）。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke19.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


app = QApplication(sys.argv)
# v3.24 回归修复：默认代码语言被外部改动会污染断言（smoke17/19/21 依赖默认 C）
from PySide6.QtCore import QSettings as _QS
_QS("WorkBuddy", "WorkBuddyMarkdown").setValue("codeLang", "C")
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
    if box["r"] is None:
        results.append("TIMEOUT | js eval | " + code[:100])
        flush()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def key(k):
    js(f"(function(){{document.dispatchEvent(new KeyboardEvent('keydown',{{key:'{k}',bubbles:true,cancelable:true}}));return 'x'}})()")
    wait(120)


def grid_state():
    r = js("(function(){var g=document.getElementById('tblgrid');"
           "return JSON.stringify({show:document.getElementById('tblsize').classList.contains('show'),"
           "hint:document.getElementById('tbl-hint').textContent,"
           "on:g.querySelectorAll('.gc.on').length,"
           "cells:g.querySelectorAll('.gc').length})})()")
    return json.loads(r or "{}")


wait(2500)  # 等待编辑视图加载

# ---------- 1) 键盘打开表格网格面板（斜杠菜单 → 方向键 → 回车） ----------
js("window.setMarkdown('')")
wait(400)
r = js("window.openBlockMenu()")
check("empty doc opens slash menu", r == "slash", r)
wait(250)
key("Escape")      # 关闭自动展开的「标题」二级菜单（菜单保持）
key("ArrowDown")   # 标题 → 列表
key("ArrowDown")   # 列表 → 表格
r = js("(function(){var m=document.getElementById('slashmenu');"
       "var act=m.querySelector('.si.act');return act?act.textContent:''})()")
check("keyboard selects 表格 item", "表格" in (r or ""), r)
key("Enter")
wait(300)
d = grid_state()
check("keyboard Enter opens grid panel, default 3x4 selected",
      d.get("show") is True and "3 行 × 4 列" in (d.get("hint") or "")
      and d.get("on") == 12, d)
check("panel visible size stays 6x6 at default selection",
      d.get("cells") == 36, d)

# ---------- 2) 方向键调整选中行列 ----------
key("ArrowDown")   # 3→4 行
d = grid_state()
check("ArrowDown adds one row (4x4)", "4 行 × 4 列" in d.get("hint", ""), d)
key("ArrowRight")  # 4→5 列
d = grid_state()
check("ArrowRight adds one col (4x5)", "4 行 × 5 列" in d.get("hint", ""), d)
key("ArrowUp")     # 4→3 行
key("ArrowLeft")   # 5→4 列
d = grid_state()
check("ArrowUp/ArrowLeft shrink back (3x4)", "3 行 × 4 列" in d.get("hint", ""), d)

# ---------- 3) 最小 1×1 ----------
for _ in range(5):
    key("ArrowUp")
for _ in range(5):
    key("ArrowLeft")
d = grid_state()
check("min clamp 1x1", "1 行 × 1 列" in d.get("hint", "") and d.get("on") == 1, d)

# ---------- 4) 最大 12×12，面板随选区扩大 ----------
for _ in range(20):
    key("ArrowDown")
for _ in range(20):
    key("ArrowRight")
d = grid_state()
check("max clamp 12x12", "12 行 × 12 列" in d.get("hint", ""), d)
check("panel grows to 12x12 (144 cells)", d.get("cells") == 144, d)

# ---------- 5) 回车插入当前选中表格 ----------
key("Enter")
wait(500)
r = js("(function(){var tbl=document.querySelector('#editor .blk table');"
       "if(!tbl) return 'NOTBL';"
       "return JSON.stringify({rows:tbl.querySelectorAll('tr').length,"
       "cols:tbl.tHead.rows[0].cells.length,"
       "panel:document.getElementById('tblsize').classList.contains('show')})})()")
d = json.loads(r or "{}")
check("Enter inserts 12x12 table and closes panel",
      d.get("rows") == 12 and d.get("cols") == 12 and d.get("panel") is False, d)
js("window.setMarkdown('')")
wait(300)

# ---------- 6) 中间选区面板扩展（选 7 行 → 面板 8 行可见） ----------
r = js("window.cmd('table')")
wait(300)
for _ in range(4):
    key("ArrowDown")   # 3→7 行
d = grid_state()
check("sel 7x4 grows panel to 8x6 visible cells (48 cells)",
      "7 行 × 4 列" in d.get("hint", "") and d.get("cells") == 48, d)
# ---------- 7) Esc 关闭面板 ----------
key("Escape")
wait(200)
d = grid_state()
check("Escape closes grid panel", d.get("show") is False, d)
js("window.setMarkdown('')")
wait(300)

# ---------- 8) 代码块：默认显示效果模式，语言按钮左上角，光标在代码区 ----------
r = js("window.cmd('fence')")
wait(300)
r = js("(function(){var cb=document.querySelector('#editor .codeblock');"
       "if(!cb) return 'NOCB';"
       "var bar=cb.querySelector('.codebar'),btn=cb.querySelector('.lang-btn');"
       "var br=bar.getBoundingClientRect(),tr=btn.getBoundingClientRect();"
       "var code=cb.querySelector('pre.fence code');"
       "return JSON.stringify({bar:!!bar,btn:!!btn,code:!!code,"
       "focused:document.activeElement===code,"
       "btnLeft:Math.round(tr.left-br.left),"
       "editable:code.getAttribute('contenteditable')})})()")
d = json.loads(r or "{}")
check("codeblock rendered with codebar + lang button", d.get("bar") and d.get("btn") and d.get("code"), d)
check("lang button at top-left of codebar", d.get("btnLeft", 99) < 30, d)
# v3.17：插入后光标先停在语言选择（lang pop），回车确认后才进代码区
check("cursor waits in lang pop first (v3.17)", d.get("focused") is False, d)
js("(function(){var q=document.getElementById('lang-q');"
   "q.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "return document.activeElement===code})()")
check("Enter in lang pop focuses code area", r is True or r == "true", r)
check("code area is editable", d.get("editable") == "plaintext-only", d)

# ---------- 9) 代码区回车换行（不拆块 / 不退出） ----------
js("(function(){var code=document.querySelector('#editor .codeblock code');"
   "code.focus();document.execCommand('insertText',false,'line1');"
   "code.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
   "document.execCommand('insertText',false,'line2');return 'x'})()")
wait(300)
r = js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "return JSON.stringify({text:code.textContent,"
       "md:window.getMarkdown()})})()")
d = json.loads(r or "{}")
check("Enter inserts newline in code area",
      "line1\nline2" in (d.get("text") or ""), d)
check("newline written back to markdown raw",
      ("```c" + chr(10) + "line1" + chr(10) + "line2" + chr(10) + "```") in (d.get("md") or "").lower(), d)
r = js("(function(){return document.querySelectorAll('#editor .blk').length})()")
check("Enter in code does not split into extra blocks", (r or "0") in ("2", 2, 2.0), r)

# ---------- 10) 代码区 Tab 缩进 ----------
js("(function(){var code=document.querySelector('#editor .codeblock code');"
   "code.focus();"
   "code.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(300)
r = js("(function(){return window.getMarkdown()})()")
check("Tab inserts indent in code area", "line2  " in (r or ""), r)

# ---------- 收尾（不弹保存对话框，直接退出） ----------
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
os._exit(0)
