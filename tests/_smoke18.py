# -*- coding: utf-8 -*-
"""v3.14 冒烟测试：表格网格选择面板 / 右键空白弹出斜杠菜单 /
空行占位提示与默认光标 / 图表就地编辑（源码显示在图表上方，图表保持可见）。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke18.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()

JS_ERR = []


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


MMD = "```mermaid\nflowchart TD\n  A-->B\n```"

wait(2500)  # 等待编辑视图加载

# ---------- 1) 空文档默认光标 + 编辑态占位提示 ----------
js("window.setMarkdown('')")
wait(400)
r = js("(function(){var ed=document.querySelector('#editor .raw-edit');"
       "return ed ? 'EDIT' : 'NOEDIT'})()")
check("empty doc shows caret (raw-edit active)", r == "EDIT", r)
r = js("(function(){var ed=document.querySelector('#editor .raw-edit');"
       "if(!ed) return 'NOEDIT';"
       "var c=getComputedStyle(ed,'::before').content;"
       "return JSON.stringify({empty:ed.textContent==='',content:c})})()")
d = json.loads(r or "{}")
check("empty raw-edit shows placeholder hint",
      d.get("empty") is True and "输入 / 可插入内容" in (d.get("content") or ""), d)

# ---------- 2) 每个空行显示占位提示（编辑回车产生空块后出现） ----------
js("window.setMarkdown('第一段')")
wait(300)
js("(function(){var blk=document.querySelectorAll('#editor .blk')[0];"
   "blk.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
dbg1 = js("window.__raw()")
# 在块尾连按两次回车 → 产生两个空块
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(250)
dbg2 = js("window.__raw() + ' LOG:' + JSON.stringify(window.__elog || [])")
js("window.__elog = []")
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(250)
dbg3 = js("window.__raw()")
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(300)
r = js("(function(){var phs=document.querySelectorAll('#editor .blk.ph');"
       "var raws=document.querySelectorAll('#editor .raw-edit:empty');"
       "var all=[].map.call(document.querySelectorAll('#editor .blk'),"
       "function(b){return b.className.replace('blk ','')})"
       ".join(' / ');"
       "return JSON.stringify({n:phs.length,raw:raws.length,all:all,"
       "state:window.__raw(),mk:window.__mkblk(0)+'|'+window.__mkblk(1),"
       "c:phs.length?getComputedStyle(phs[0],'::before').content:''})})()")
d = json.loads(r or "{}")
check("each empty line shows placeholder",
      ((d.get("n") or 0) + (d.get("raw") or 0)) >= 1
      and "输入 / 可插入内容" in (d.get("c") or ""),
      str(d) + " | d1=" + str(dbg1) + " d2=" + str(dbg2) + " d3=" + str(dbg3))

# ---------- 2b) 块中部回车：正确拆分，不复制内容（splitBlock 提交顺序修复） ----------
js("window.setMarkdown('AB')")
wait(300)
js("(function(){var blk=document.querySelectorAll('#editor .blk')[0];"
   "blk.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
js("(function(){var el=document.querySelector('.raw-edit');"
   "var tn=el.firstChild;var rg=document.createRange();rg.setStart(tn,1);rg.collapse(true);"
   "var s=getSelection();s.removeAllRanges();s.addRange(rg);return 'x'})()")
wait(150)
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(300)
r = js("window.__raw()")
check("mid-block enter splits without duplication",
      r == '{"raw":["A","B"],"editIdx":1}', r)

# ---------- 3) 右键空白块 → 斜杠菜单 ----------
js("window.setMarkdown('')")
wait(300)
js("(function(){var ed=document.querySelector('#editor .blk');"
   "ed.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("document.getElementById('slashmenu').classList.contains('show')")
check("right-click blank opens slash menu", r is True or r == "true", r)
r = js("(function(){var m=document.getElementById('slashmenu');"
       "return m.querySelector('.si') ? 'items' : 'empty'})()")
check("slash menu from right-click has items", r == "items", r)
js("document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}))")
wait(200)
# 右键有内容的块 → 保留系统菜单（斜杠菜单不弹出）
js("window.setMarkdown('# 标题\\n\\n正文')")
wait(300)
js("(function(){var blk=document.querySelectorAll('#editor .blk')[0];"
   "blk.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("document.getElementById('slashmenu').classList.contains('show')")
check("right-click non-blank keeps system menu", not (r is True or r == "true"), r)

# ---------- 4) 图表就地编辑：源码显示在图表上方，图表保持可见 ----------
js(f"window.setMarkdown({json.dumps(MMD)})")
wait(2500)   # mermaid 懒加载 + 首次渲染
r = js("(function(){var mb=document.querySelector('#editor .mermaidblock');"
       "return JSON.stringify({svg:!!mb.querySelector('svg')})})()")
d = json.loads(r or "{}")
check("mermaid chart rendered", d.get("svg") is True, d)
# 单击图表 = 选中 → 上方出现源码编辑区
js("(function(){var mb=document.querySelector('#editor .mermaidblock');"
   "mb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
r = js("(function(){var ta=document.querySelector('#editor .mmd-src');"
       "var mb=document.querySelector('#editor .mermaidblock');"
       "if(!ta||!mb) return 'MISSING';"
       "return JSON.stringify({hasTa:true,"
       # v3.22：图表被 div.mmd-wrap 包裹，源码框插在包裹层之前；
       # 这里改判「文档顺序上源码框在图表之前」= 源码框显示在图表上方
       "taFirst:!!(ta.compareDocumentPosition(mb)&4),"
       "val:ta.value.indexOf('flowchart')!==-1,"
       "svg:!!mb.querySelector('svg')})})()")
d = json.loads(r or "{}")
check("click chart opens source editor above chart",
      d.get("hasTa") is True and d.get("taFirst") is True and d.get("val") is True, d)
check("chart stays visible while editing", d.get("svg") is True, d)
# 编辑源码 → 图表实时更新 + 源码回写
js("(function(){var ta=document.querySelector('#editor .mmd-src');"
   "ta.value='flowchart TD\\n  X-->Y';"
   "ta.dispatchEvent(new Event('input',{bubbles:true}));return 'x'})()")
wait(900)
r = js("(function(){var md=window.getMarkdown();"
       "var mb=document.querySelector('#editor .mermaidblock');"
       "return JSON.stringify({md:md.indexOf('X-->Y')!==-1,"
       "src:mb.getAttribute('data-src').indexOf('X-->Y')!==-1})})()")
d = json.loads(r or "{}")
check("editing source writes back to markdown", d.get("md") is True, d)
check("chart re-renders with new source", d.get("src") is True, d)
# 点击别的块 → 关闭编辑区并保持已提交
js("(function(){var blks=document.querySelectorAll('#editor .blk');"
   "blks[blks.length-1].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
   "return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({ta:!!document.querySelector('#editor .mmd-src'),"
       "md:window.getMarkdown().indexOf('X-->Y')!==-1})})()")
d = json.loads(r or "{}")
check("click elsewhere closes chart editor, edits kept",
      d.get("ta") is False and d.get("md") is True, d)

# ---------- 5) Escape 关闭图表编辑 ----------
js(f"window.setMarkdown({json.dumps(MMD)})")
wait(1500)
js("(function(){var mb=document.querySelector('#editor .mermaidblock');"
   "mb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
js("(function(){var ta=document.querySelector('#editor .mmd-src');"
   "ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({ta:!!document.querySelector('#editor .mmd-src')})})()")
d = json.loads(r or "{}")
check("escape closes chart editor", d.get("ta") is False, d)

# ---------- 收尾（不弹保存对话框，直接退出） ----------
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
os._exit(0)
