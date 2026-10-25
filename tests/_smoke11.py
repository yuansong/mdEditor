# -*- coding: utf-8 -*-
"""v3.4 测试：KaTeX 数学公式 / 斜杠菜单 / 块编辑菜单 / 行编辑菜单 / 表格快速编辑。"""
import json
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke11.txt")

results = []

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEventLoop, QTimer

app = QApplication.instance() or QApplication([])
from mainwindow import MainWindow

win = MainWindow()
win.show()


def js(code):
    box = {}
    loop = QEventLoop()

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(10000, loop.quit)  # 超时保护，避免死等
    win._js_active(code, cb)
    loop.exec()
    return box.get("r")


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def check(name, cond, detail=""):
    results.append(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))


wait(6000)

# ---------- 1) KaTeX 数学公式 ----------
r = js("typeof window.katex")
check("katex loaded", r == "object", r)
js("window.setMarkdown('# 公式\\n\\n```math\\ne^{i\\\\pi} + 1 = 0\\n```\\n\\n行内 $E=mc^2$ 公式。\\n\\n价格 $5，再 $6 不应是公式。')")
wait(1500)
r = js("(function(){return JSON.stringify({mb: document.querySelectorAll('.mathblock .katex').length,"
       " im: document.querySelectorAll('.inlinemath .katex').length,"
       " total_inline: document.querySelectorAll('.inlinemath').length})})()")
d = json.loads(r or "{}")
check("block math rendered", d.get("mb") == 1, d)
check("inline math rendered", d.get("im") == 1 and d.get("total_inline") == 1, d)
back = js("window.getMarkdown()")
check("math roundtrip", "```math" in back and "$E=mc^2$" in back, (back or "")[:80])

# ---------- 2) 斜杠菜单 ----------
js("window.setMarkdown('')")  # 空文档 -> 唯一空块
wait(800)
js("(function(){var el=document.querySelector('.blk');"
   "el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "var t=document.querySelector('.raw-edit')||el;"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true}));return 't'})()")
wait(300)
r = js("(function(){var m=document.getElementById('slashmenu');"
       "return JSON.stringify({show:m.classList.contains('show'),items:m.querySelectorAll('.si').length})})()")
d = json.loads(r or "{}")
check("slash menu opens", d.get("show") is True and (d.get("items") or 0) >= 9, d)
# 过滤 + 应用 标题1（v3.6：Enter 先展开「标题」二级菜单，再 Enter 应用第一项）
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'标',bubbles:true}));return 'f'})()")
wait(200)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return 'a'})()")
wait(400)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return 'a2'})()")
wait(400)
# v3.9：标题二级默认选中「标题 3」，Enter 应用默认项
r = js("window.getMarkdown()")
check("slash applies default heading3", (r or "").startswith("### "), (r or "")[:30])
r = js("!!document.getElementById('slashmenu').classList.contains('show')")
check("slash menu closed after apply", r is False, r)

# ---------- 3) 块编辑菜单 ----------
js("window.setMarkdown('普通段落文字')")  # 单个段落块
wait(800)
js("(function(){var b=document.querySelector('.blk');"
   "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:100,clientY:100}));return 'h'})()")
wait(200)
r = js("document.getElementById('blkhandle').style.display")
check("block handle shows on hover", r == "flex", r)
js("(function(){var h=document.getElementById('blkhandle');"
   "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'c'})()")
wait(300)
r = js("(function(){var m=document.getElementById('blkmenu');"
       "return JSON.stringify({show:m.classList.contains('show'),items:m.querySelectorAll('.mi').length,"
       "cap:(m.querySelector('.cap')||{}).textContent||''})})()")
d = json.loads(r or "{}")
check("block menu opens", d.get("show") is True and (d.get("items") or 0) == 9, d)
check("block menu shows type", "正文段落" in (d.get("cap") or ""), d.get("cap"))
# v3.9：转为拆分为 标题/段落/列表/代码块/引用，引用为直接项
js("(function(){var m=document.getElementById('blkmenu');"
   "var t=m.querySelector('[data-act=\"to:quote\"]');"
   "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "t.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'x'})()")
wait(400)
r = js("window.getMarkdown()")
check("block transform to quote", (r or "").startswith("> 普通段落"), (r or "")[:30])
# 删除块
js("(function(){var b=document.querySelector('.blk');"
   "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:100,clientY:100}));"
   "document.getElementById('blkhandle').dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'y'})()")
wait(250)
js("(function(){var m=document.getElementById('blkmenu');"
   "var t=m.querySelector('[data-act=\"del\"]');"
   "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "t.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'z'})()")
wait(400)
r = js("(function(){return JSON.stringify({n:document.querySelectorAll('.blk').length})})()")
d = json.loads(r or "{}")
check("block delete keeps editor", d.get("n", 0) >= 1, d)

# ---------- 4) 行编辑菜单（选中文字浮动栏） ----------
js("window.setMarkdown('这是一段可以被加粗的文字')")
wait(800)
r = js("""
(function(){
  var p = document.querySelector('.blk p');
  var tn = p.firstChild;
  var sel = getSelection();
  var range = document.createRange();
  range.setStart(tn, 4); range.setEnd(tn, 9);
  sel.removeAllRanges(); sel.addRange(range);
  document.dispatchEvent(new Event('selectionchange'));
  return 'sel';
})()
""")
wait(500)
r2 = js("document.getElementById('floatbar').classList.contains('show')")
check("floatbar shows on selection", r2 is True, r2)
js("(function(){var fb=document.getElementById('floatbar');"
   "var b=fb.querySelector('button');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'b'})()")
wait(400)
r = js("window.getMarkdown()")
check("floatbar bold applies", "**可以被加粗**" in (r or ""), (r or "")[:40])

# ---------- 5) 表格快速编辑 ----------
js("window.setMarkdown('| A | B |\\n| --- | --- |\\n| 1 | 2 |\\n| 3 | 4 |')")
wait(800)
js("(function(){var td=document.querySelector('.b-table tbody td');"
   "td.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
   "td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 't'})()")
wait(300)
r = js("document.getElementById('tblbar').classList.contains('show')")
check("table toolbar shows", r is True, r)
# 向右插入一列
js("(function(){var tb=document.getElementById('tblbar');"
   "var b=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title==='向右插入列'})[0];"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'c'})()")
wait(400)
r = js("window.getMarkdown()")
check("table insert col", (r or "").count("|") >= 6 and "| A | B |" in (r or "") is False if False else "| A | B |" not in (r or "") and "A" in (r or ""), (r or "")[:60])
# 右对齐第一列（当前列上下文被 rebuild 重置，重新点一次）
js("(function(){var td=document.querySelector('.b-table tbody td');"
   "td.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
   "td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 't2'})()")
wait(300)
js("(function(){var tb=document.getElementById('tblbar');"
   "var b=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title==='右对齐'})[0];"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'r'})()")
wait(400)
r = js("window.getMarkdown()")
check("table align right", "---:" in (r or ""), (r or "")[:60])

# 状态栏统计不崩
r = js("window.collect()")
check("collect ok", bool(r), (r or "")[:60])

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
import os
os._exit(0)  # 强制退出，避免未保存弹窗阻塞测试进程
