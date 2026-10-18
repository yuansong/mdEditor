# -*- coding: utf-8 -*-
"""v3.16 冒烟测试：图表选中后 DEL 删除整个图表 / 图表下方空段按 DEL(或 Backspace)
打开源码框且光标在开始处 / 源码框只显示图表源码（无 ```mermaid 围栏）/
写作模式下代码块与表格始终渲染态（点击空白、双击、方向键进入都不切源码态）。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke20.txt")
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


def slash_pick(item_id, sub=None):
    """按一级项 id 直接选中并应用（不依赖方向键计数，菜单顺序可被系统设置调整）"""
    sub_js = "null" if sub is None else str(sub)
    r = js(f"window.__slashPick({json.dumps(item_id)}, {sub_js})")
    wait(400)
    return r


MMD = "```mermaid\nflowchart TD\n  A-->B\n```"
wait(2500)

# ---------- 1) 单击图表 = 选中：源码框显示但不聚焦；源码框无 ```mermaid 围栏 ----------
js(f"window.setMarkdown({json.dumps(MMD)})")
wait(1500)
js("(function(){var mb=document.querySelector('#editor .mermaidblock');"
   "mb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
r = js("(function(){var ta=document.querySelector('#editor .mmd-src');"
       "return JSON.stringify({ta:!!ta,focused:document.activeElement===ta,"
       "val:ta?ta.value:''})})()")
d = json.loads(r or "{}")
check("click chart selects (source box shown, not focused)",
      d.get("ta") is True and d.get("focused") is False, d)
check("source box shows chart code without fences",
      d.get("val", "").startswith("flowchart") and "```" not in d.get("val", ""), d)

# ---------- 2) 选中图表后按 DEL：删除整个图表块 ----------
key("Delete")
wait(400)
r = js("(function(){return JSON.stringify({"
       "mmd:!!document.querySelector('#editor .mermaidblock'),"
       "ta:!!document.querySelector('#editor .mmd-src'),"
       "md:window.getMarkdown()})})()")
d = json.loads(r or "{}")
check("DEL deletes whole chart block",
      d.get("mmd") is False and d.get("ta") is False
      and "flowchart" not in (d.get("md") or ""), d)

# ---------- 3) 插入图表后光标在下方空段：按 DEL 打开源码框且光标在开始处 ----------
js("window.setMarkdown('')")
wait(400)
r = js("(function(){var el=document.querySelector('.raw-edit');"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return 'x'})()")
wait(300)
slash_pick("chart", 0)   # 图表 → 流程图
wait(600)
r = js("(function(){return JSON.stringify({"
       "mmd:!!document.querySelector('#editor .mermaidblock'),"
       "raw:window.__raw()})})()")
d = json.loads(r or "{}")
check("slash menu inserts chart (cursor in empty para below)",
      d.get("mmd") is True and (d.get("raw") or "").count("```mermaid") == 1, d)
key("Delete", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){var ta=document.querySelector('#editor .mmd-src');"
       "return JSON.stringify({ta:!!ta,focused:document.activeElement===ta,"
       "pos:ta?ta.selectionStart:-1,"
       "mmd:!!document.querySelector('#editor .mermaidblock')})})()")
d = json.loads(r or "{}")
check("DEL below chart opens source box, cursor at start, chart kept",
      d.get("ta") is True and d.get("focused") is True
      and d.get("pos") == 0 and d.get("mmd") is True, d)
# Backspace 同样打开源码框（不把空块合并进图表源码）
key("Escape")
wait(200)
js("(function(){var blks=document.querySelectorAll('#editor .blk');"
   "blks[blks.length-1].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
   "return 'x'})()")
wait(300)
# v3.38（WYS-4）：空段保持渲染态 —— p[contenteditable] 派发 Backspace，
# WYS-4b 分支 enterEdit+重派 → 源码态分支打开图表源码框（兼容源码态）
js("(function(){var blks=document.querySelectorAll('#editor .blk');"
   "var last=blks[blks.length-1];"
   "var h=last.matches('.raw-edit')?last:"
   "(last.querySelector('.raw-edit')||last.querySelector('p[contenteditable]'));"
   "if(!h) return 'NOHOST';"
   "h.focus();"
   "var rg=document.createRange();rg.selectNodeContents(h);rg.collapse(true);"
   "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
   "h.dispatchEvent(new KeyboardEvent('keydown',{key:'Backspace',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(300)
r = js("(function(){var ta=document.querySelector('#editor .mmd-src');"
       "return JSON.stringify({ta:!!ta,focused:document.activeElement===ta,"
       "raw:window.__raw()})})()")
d = json.loads(r or "{}")
check("Backspace below chart opens source box (no raw merge)",
      d.get("ta") is True and d.get("focused") is True
      and (d.get("raw") or "").count("```mermaid") == 1, d)
key("Escape")
wait(200)

# ---------- 4) 写作模式：双击表格单元格 = 选中编辑，不切源码态 ----------
TBL = "| a | b |\n| --- | --- |\n| 1 | 2 |"
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(600)
js("(function(){var c=document.querySelector('#editor .b-table td');"
   "c.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:2,cancelable:true}));"
   "return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({"
       "src:!!document.querySelector('#editor .raw-edit.t-table'),"
       "sel:!!(window.__tblSel && window.__tblSel()),"
       "tbl:!!document.querySelector('#editor .b-table')})})()")
d = json.loads(r or "{}")
check("double-click table cell keeps rendered mode (no source)",
      d.get("src") is False and d.get("sel") is True and d.get("tbl") is True, d)

# ---------- 5) 写作模式：点击代码块空白处（pre 边距）不切源码态 ----------
js("window.setMarkdown('```\\nabc\\n```')")
wait(600)
js("(function(){var pre=document.querySelector('#editor .codeblock pre.fence');"
   "pre.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1,cancelable:true}));"
   "return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({"
       "src:!!document.querySelector('#editor .raw-edit.t-fence'),"
       "cb:!!document.querySelector('#editor .codeblock')})})()")
d = json.loads(r or "{}")
check("click codeblock padding stays rendered (no source)",
      d.get("src") is False and d.get("cb") is True, d)

# ---------- 6) 写作模式：方向键进入表格 → 选中首格渲染态，不切源码态 ----------
js(f"window.setMarkdown({json.dumps('段落文字\\n\\n' + TBL)})")
wait(600)
js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
key("ArrowDown", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){return JSON.stringify({"
       "src:!!document.querySelector('#editor .raw-edit.t-table'),"
       "sel:!!(window.__tblSel && window.__tblSel())})})()")
d = json.loads(r or "{}")
check("ArrowDown into table selects first cell (rendered, no source)",
      d.get("src") is False and d.get("sel") is True, d)

# ---------- 7) 写作模式：方向键进入代码块 → 光标进代码区渲染态 ----------
js("window.setMarkdown('段落文字\\n\\n```\\nabc\\n```')")
wait(600)
js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
# v3.38（WYS-4c）：段落渲染态段尾 ArrowDown → enterEdit+重派 → 代码区聚焦
js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
   "var h=b.querySelector('.raw-edit')||b.querySelector('p[contenteditable]');"
   "if(!h) return 'NOHOST';h.focus();"
   "var rg=document.createRange();rg.selectNodeContents(h);rg.collapse(false);"
   "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
   "h.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(400)
r = js("(function(){return JSON.stringify({"
       "src:!!document.querySelector('#editor .raw-edit.t-fence'),"
       "focus:document.activeElement===document.querySelector('#editor .codeblock code')})})()")
d = json.loads(r or "{}")
check("ArrowDown into codeblock focuses code area (rendered, no source)",
      d.get("src") is False and d.get("focus") is True, d)

# ---------- 收尾 ----------
flush()
os._exit(0)
