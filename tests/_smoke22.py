# -*- coding: utf-8 -*-
"""v3.18 冒烟测试：代码块 DEL 不显示源码 / 默认语言可设置 /
无序列表·引用·分割线·公式插入直接渲染态 / 分割线 Backspace 删除 /
点击编辑区关闭残留菜单（防吞键）/ 菜单中再按 / 转义为字面斜杠。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke22.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


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


def key(k, sel=None):
    tgt = sel or "document"
    js(f"(function(){{var t={tgt};"
       f"t.dispatchEvent(new KeyboardEvent('keydown',{{key:'{k}',bubbles:true,cancelable:true}}));"
       f"return 'x'}})()")
    wait(150)


def open_slash():
    """空块中唤起斜杠菜单"""
    js("(function(){var el=document.querySelector('.raw-edit');"
       "if(!el) return 'NOEDIT';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return 'x'})()")
    wait(300)


def slash_pick(item_id, sub=None):
    """按一级项 id 直接选中并应用（不依赖方向键计数，菜单顺序可被系统设置调整）"""
    sub_js = "null" if sub is None else str(sub)
    r = js(f"window.__slashPick({json.dumps(item_id)}, {sub_js})")
    wait(400)
    return r


def clear_block():
    """把当前 raw-edit 内容清空（构造真实空段，绕过 setMarkdown 首尾空块裁剪）"""
    js("(function(){var el=document.querySelector('.raw-edit');"
       "el.focus();document.execCommand('selectAll');document.execCommand('delete');return 'x'})()")
    wait(250)


def raw0():
    r = js("window.__raw()")
    d = json.loads(r or "{}")
    return (d.get("raw") or [""])


wait(2500)

# ---------- 1) 代码块：下方空段 Backspace 不显示源码，进代码区 ----------
js("window.setMarkdown('```c\\nhi\\n```\\n\\nX')")
wait(700)
js("(function(){var b=document.querySelectorAll('#editor .blk');"
   "b[b.length-1].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
clear_block()
key("Backspace", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){return JSON.stringify({src:!!document.querySelector('.raw-edit'),"
       "focus:document.activeElement===document.querySelector('.codeblock code'),"
       "n:document.querySelectorAll('#editor .blk').length})})()")
d = json.loads(r or "{}")
check("Backspace below code block enters code area (no source shown)",
      d.get("src") is False and d.get("focus") is True and d.get("n") == 1, d)

# 空段上方代码块：DEL 同样进代码区
js("window.setMarkdown('X\\n\\n```c\\nhi\\n```')")
wait(700)
js("(function(){var b=document.querySelectorAll('#editor .blk');"
   "b[0].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
clear_block()
key("Delete", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){return JSON.stringify({src:!!document.querySelector('.raw-edit'),"
       "focus:document.activeElement===document.querySelector('.codeblock code'),"
       "n:document.querySelectorAll('#editor .blk').length})})()")
d = json.loads(r or "{}")
check("Delete above code block enters code area (no merge to source)",
      d.get("src") is False and d.get("focus") is True and d.get("n") == 2, d)

# ---------- 2) 斜杠插入无序列表：直接渲染态（实心圆，不显示 - 源码） ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
slash_pick("list", 0)   # 无序列表（二级第 1 项）
r = js("(function(){return JSON.stringify({src:!!document.querySelector('.raw-edit'),"
       "ul:!!document.querySelector('#editor .b-list ul'),"
       "li:!!document.querySelector('#editor .b-list li[contenteditable]'),"
       "focus:document.activeElement===document.querySelector('#editor .b-list li')})})()")
d = json.loads(r or "{}")
check("slash insert unordered list is rendered bullet (no '- ' source)",
      d.get("src") is False and d.get("ul") is True and d.get("li") is True
      and d.get("focus") is True, d)
check("unordered list raw kept as '- '", raw0()[0] == "- ", raw0())

# ---------- 3) 斜杠插入分割线：渲染态 + 光标进下一行；Backspace 删除分割线 ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
slash_pick("hr")
r = js("(function(){return JSON.stringify({srcT:!!document.querySelector('.raw-edit.t-hr'),"
       "hr:!!document.querySelector('#editor .b-hr hr'),"
       "focus:document.activeElement===document.querySelector('.raw-edit'),"
       "hrEmpty:(document.querySelector('#editor .b-hr')||{}).textContent===''})})()")
d = json.loads(r or "{}")
check("slash insert hr rendered, caret moves to next line",
      d.get("hr") is True and d.get("srcT") is False and d.get("focus") is True, d)
key("Backspace", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){return JSON.stringify({hr:!!document.querySelector('#editor .b-hr hr'),"
       "bhr:!!document.querySelector('#editor .b-hr'),"
       "raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
check("Backspace on line below deletes whole hr",
      d.get("hr") is False and d.get("bhr") is False
      and (d2.get("raw") or [""])[0] == "" and len(d2.get("raw") or []) == 1, d)

# 空段在分割线上方：DEL 也删除分割线
js("window.setMarkdown('X\\n\\n---')")
wait(700)
js("(function(){var b=document.querySelectorAll('#editor .blk');"
   "b[0].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
clear_block()
key("Delete", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){return JSON.stringify({bhr:!!document.querySelector('#editor .b-hr'),"
       "n:document.querySelectorAll('#editor .blk').length,"
       "raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
check("Delete above hr deletes the hr",
      d.get("bhr") is False and d.get("n") == 1
      and (d2.get("raw") or [""])[0] == "", d)

# ---------- 4) 斜杠菜单开着时点击编辑区：菜单关闭，按键不再被吞 ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
r = js("(function(){return document.getElementById('slashmenu').classList.contains('show')})()")
check("slash menu opens", r is True, r)
js("(function(){var b=document.querySelector('#editor .blk');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({menu:document.getElementById('slashmenu').classList.contains('show'),"
       "edit:!!document.querySelector('.raw-edit')})})()")
d = json.loads(r or "{}")
check("clicking editor closes stale slash menu (keys not swallowed)",
      d.get("menu") is False and d.get("edit") is True, d)

# ---------- 5) 菜单中再按 /：转义为字面 '/' ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
key("/", sel="document.querySelector('.raw-edit')")   # 菜单开着再按 /
wait(400)
r = js("(function(){return JSON.stringify({menu:document.getElementById('slashmenu').classList.contains('show'),"
       "raw:window.__raw(),src:!!document.querySelector('.raw-edit')})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
check("pressing / in menu escapes to literal '/' (no dead no-match state)",
      d.get("menu") is False and (d2.get("raw") or [""])[0] == "/"
      and d.get("src") is True, d)

# ---------- 6) 斜杠插入引用：渲染态；行首 Backspace 去掉 > 标记 ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
slash_pick("quote")
r = js("(function(){return JSON.stringify({src:!!document.querySelector('.raw-edit'),"
       "bq:!!document.querySelector('#editor .b-quote blockquote[contenteditable]'),"
       "focus:document.activeElement===document.querySelector('#editor .b-quote blockquote')})})()")
d = json.loads(r or "{}")
check("slash insert quote is rendered (no '> ' source)",
      d.get("src") is False and d.get("bq") is True and d.get("focus") is True, d)
key("Backspace", sel="document.querySelector('#editor .b-quote blockquote')")
wait(400)
r = js("(function(){return JSON.stringify({bq:!!document.querySelector('#editor .b-quote'),"
       "raw:window.__raw(),src:!!document.querySelector('.raw-edit')})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
check("Backspace at quote start removes quote marker",
      d.get("bq") is False and (d2.get("raw") or [""])[0] == "" and d.get("src") is True, d)

# ---------- 7) 斜杠插入公式：渲染公式块 + 上方源码框聚焦（同图表） ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
slash_pick("math", 0)   # 公式：应用二级第 1 个模板
wait(600)
r = js("(function(){var ta=document.querySelector('#editor .math-src');"
       "return JSON.stringify({ta:!!ta,focus:document.activeElement===ta,"
       "katex:!!document.querySelector('#editor .mathblock .katex'),"
       "next:document.querySelectorAll('#editor .blk').length,"
       "src:!!document.querySelector('.raw-edit'),raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
rr = d2.get("raw") or [""]
check("slash insert math: rendered formula + focused source box above",
      d.get("ta") is True and d.get("focus") is True and d.get("katex") is True
      and d.get("src") is False and rr[0].startswith("```math"), d)
check("math block followed by editable empty paragraph", d.get("next") == 2, d)

# ---------- 8) 默认代码语言可经设置接口修改 ----------
js("window.setMarkdown('')")
wait(500)
js("window.setDefaultCodeLang('Python')")
wait(200)
open_slash()
slash_pick("code")
wait(600)
r = js("(function(){var pop=document.getElementById('langpop');"
       "var act=pop.querySelector('.li.act');"
       "return JSON.stringify({show:pop.classList.contains('show'),"
       "act:act?act.textContent:'',"
       "btn:(document.querySelector('.lang-btn')||{}).textContent})})()")
d = json.loads(r or "{}")
check("default code lang from settings preselected (Python)",
      d.get("show") is True and d.get("act") == "Python" and d.get("btn") == "Python", d)
key("Enter", sel="document.getElementById('lang-q')")
wait(400)
rr = raw0()
check("Enter applies configured default lang（v3.30.18 CODE-7 小写化）",
      rr[0].startswith("```python"), rr)
js("window.setDefaultCodeLang('C')")   # 还原，避免影响后续
wait(200)

# ---------- 收尾 ----------
flush()
os._exit(0)
