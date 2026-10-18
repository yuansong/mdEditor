# -*- coding: utf-8 -*-
"""v3.17 冒烟测试：有序列表跨块序号(start) / 标题·列表·引用·分割线渲染态编辑 /
公式就地编辑（上源码下渲染）/ 表格 DEL 进末格 / 点击下方空白进最后可编辑位置 /
代码块插入默认语言选择（C，↑↓切换，回车进代码区）/ 代码区无输入外框。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke21.txt")
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


def caret_end(sel):
    return js(f"(function(){{var t={sel};t.focus();"
              f"var r=document.createRange();r.selectNodeContents(t);r.collapse(false);"
              f"var s=getSelection();s.removeAllRanges();s.addRange(r);return 'x'}})()")


def caret_start(sel):
    return js(f"(function(){{var t={sel};t.focus();"
              f"var r=document.createRange();r.selectNodeContents(t);r.collapse(true);"
              f"var s=getSelection();s.removeAllRanges();s.addRange(r);return 'x'}})()")


wait(2500)

# ---------- 1) 有序列表跨块序号：blockHTML 输出 start 属性 ----------
r = js("(function(){return JSON.stringify({a:window.__core.blockHTML('3. 三\\n4. 四'),"
       "b:window.__core.blockHTML('1. 一\\n2. 二')})})()")
d = json.loads(r or "{}")
check("ordered list start attr (num>1)",
      '<ol start="3">' in (d.get("a") or ""), d)
check("ordered list from 1 has no start attr",
      (d.get("b") or "").startswith("<ol>"), d)

# ---------- 2) 标题渲染态编辑：点击不进源码态，输入直接改渲染标题 ----------
js("window.setMarkdown('## 标题一')")
wait(600)
js("(function(){var b=document.querySelector('#editor .b-h2');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({src:!!document.querySelector('.raw-edit'),"
       "h:!!document.querySelector('#editor .b-h2 h2[contenteditable]')})})()")
d = json.loads(r or "{}")
check("click heading stays rendered (no source mode)",
      d.get("src") is False and d.get("h") is True, d)
caret_end("document.querySelector('#editor .b-h2 h2')")
js("(function(){document.execCommand('insertText',false,'!');return 'x'})()")
wait(300)
r = js("window.__raw()")
d = json.loads(r or "{}")
check("typing in rendered heading syncs markdown raw",
      (d.get("raw") or [""])[0] == "## 标题一!", d)
key("Enter", sel="document.querySelector('#editor .b-h2 h2')")
wait(400)
r = js("window.__raw()")
d = json.loads(r or "{}")
check("Enter in heading splits to paragraph below",
      (d.get("raw") or [])[0] == "## 标题一!" and len(d.get("raw") or []) == 2, d)

# ---------- 3) 标题退格转正文 ----------
js("window.setMarkdown('## 标题一')")
wait(600)
caret_start("document.querySelector('#editor .b-h2 h2')")
key("Backspace", sel="document.querySelector('#editor .b-h2 h2')")
wait(400)
r = js("(function(){return JSON.stringify({raw:window.__raw(),"
       "src:!!document.querySelector('.raw-edit')})})()")
d = json.loads(r or "{}")
check("Backspace at heading start converts to paragraph",
      (json.loads(d.get("raw") or "{}").get("raw") or [None])[0] == "标题一", d)

# ---------- 4) 无序列表渲染态编辑 + 回车新增项 ----------
js("window.setMarkdown('- 苹果\\n- 香蕉')")
wait(600)
js("(function(){var b=document.querySelector('#editor .b-list');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({src:!!document.querySelector('.raw-edit'),"
       "li:!!document.querySelector('#editor .b-list li[contenteditable]')})})()")
d = json.loads(r or "{}")
check("click list stays rendered (no source mode)",
      d.get("src") is False and d.get("li") is True, d)
js("(function(){var li=document.querySelector('#editor .b-list li[contenteditable]');"
   "li.focus();var r=document.createRange();r.selectNodeContents(li);r.collapse(false);"
   "var s=getSelection();s.removeAllRanges();s.addRange(r);"
   "document.execCommand('insertText',false,'X');return 'x'})()")
wait(300)
r = js("window.__raw()")
d = json.loads(r or "{}")
check("typing in rendered list item syncs raw",
      (d.get("raw") or [""])[0] == "- 苹果X\n- 香蕉", d)
key("Enter", sel="document.querySelector('#editor .b-list li[contenteditable]')")
wait(400)
r = js("(function(){return JSON.stringify({raw:window.__raw(),"
       "n:document.querySelectorAll('#editor .b-list li').length})})()")
d = json.loads(r or "{}")
check("Enter in list item inserts new item",
      (json.loads(d.get("raw") or "{}").get("raw") or [""])[0] == "- 苹果X\n- \n- 香蕉"
      and d.get("n") == 3, d)

# ---------- 5) 有序列表回车：编号顺延 ----------
js("window.setMarkdown('1. 一\\n2. 二')")
wait(600)
js("(function(){var li=document.querySelector('#editor .b-list li[contenteditable]');"
   "li.focus();var r=document.createRange();r.selectNodeContents(li);r.collapse(false);"
   "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'x'})()")
key("Enter", sel="document.querySelector('#editor .b-list li[contenteditable]')")
wait(400)
r = js("window.__raw()")
d = json.loads(r or "{}")
check("Enter in ordered list renumbers (3. 二)",
      "3. 二" in (d.get("raw") or [""])[0], d)

# ---------- 6) 引用渲染态编辑 / 分割线点击无源码态 ----------
js("window.setMarkdown('> 引用行')")
wait(600)
js("(function(){var b=document.querySelector('#editor .b-quote');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
js("(function(){var bq=document.querySelector('#editor .b-quote blockquote[contenteditable]');"
   "if(!bq) return 'NO';bq.focus();"
   "var r=document.createRange();r.selectNodeContents(bq);r.collapse(false);"
   "var s=getSelection();s.removeAllRanges();s.addRange(r);"
   "document.execCommand('insertText',false,'!');return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({raw:window.__raw(),"
       "src:!!document.querySelector('.raw-edit')})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
check("quote rendered edit syncs raw",
      (d2.get("raw") or [""])[0] == "> 引用行!" and d.get("src") is False, d)
js("window.setMarkdown('---')")
wait(500)
js("(function(){var b=document.querySelector('#editor .b-hr');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
r = js("(function(){return JSON.stringify({src:!!document.querySelector('.raw-edit'),"
       "hr:!!document.querySelector('#editor .b-hr hr')})})()")
d = json.loads(r or "{}")
check("hr click shows no source mode",
      d.get("src") is False and d.get("hr") is True, d)

# ---------- 7) 公式就地编辑：点击选中（上源码框，公式可见）→ 编辑实时重渲染 → DEL 删除 ----------
js("window.setMarkdown('```math\\nE=mc^2\\n```')")
wait(900)
js("(function(){var mb=document.querySelector('#editor .mathblock');"
   "mb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(400)
r = js("(function(){var ta=document.querySelector('#editor .math-src');"
       "return JSON.stringify({ta:!!ta,focused:document.activeElement===ta,"
       "val:ta?ta.value:''})})()")
d = json.loads(r or "{}")
check("click math selects (source box above, not focused, no fences)",
      d.get("ta") is True and d.get("focused") is False
      and d.get("val") == "E=mc^2", d)
js("(function(){var ta=document.querySelector('#editor .math-src');"
   "ta.focus();ta.value='E=mc^3';ta.dispatchEvent(new Event('input',{bubbles:true}));return 'x'})()")
wait(900)
r = js("(function(){return JSON.stringify({raw:window.__raw(),"
       "katex:!!document.querySelector('#editor .mathblock .katex')})})()")
d = json.loads(r or "{}")
check("math edit live re-renders (katex visible)",
      "E=mc^3" in ((json.loads(d.get("raw") or "{}").get("raw")) or [""])[0]
      and d.get("katex") is True, d)
key("Escape", sel="document.querySelector('#editor .math-src')")      # 退出编辑态（源码框关闭）
wait(300)
js("(function(){var mb=document.querySelector('#editor .mathblock');"
   "mb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
key("Delete")      # 选中态下 DEL 删除整个公式块
wait(400)
r = js("(function(){return JSON.stringify({m:!!document.querySelector('#editor .mathblock'),"
       "ta:!!document.querySelector('#editor .math-src')})})()")
d = json.loads(r or "{}")
check("DEL with math selected deletes whole block",
      d.get("m") is False and d.get("ta") is False, d)

# ---------- 8) 表格下方空段按 DEL：光标进最后一行最后一列（渲染态） ----------
TBL = "| a | b |\n| --- | --- |\n| 1 | 2 |"
js(f"window.setMarkdown({json.dumps(TBL + chr(10) + chr(10) + 'x')})")
wait(700)
js("(function(){var b=document.querySelectorAll('#editor .blk');"
   "b[b.length-1].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
# v3.38（WYS-4）：双态兼容 —— raw-edit 或渲染态 p，清空后派发 Backspace
# （渲染态空段走 WYS-4b 兜底重派 → 源码态分支进表格末格）
js("(function(){var el=document.querySelector('.raw-edit');if(!el){"
   "var bs=document.querySelectorAll('#editor .blk');"
   "for(var i=0;i<bs.length;i++){var pp=bs[i].querySelector('p[contenteditable]');"
   "if(pp){el=pp;break;}}}"
   "if(!el) return 'NOHOST';"
   "el.focus();document.execCommand('selectAll');document.execCommand('delete');return 'x'})()")
wait(300)
js("(function(){var el=document.querySelector('.raw-edit');if(!el){"
   "var bs=document.querySelectorAll('#editor .blk');"
   "for(var i=0;i<bs.length;i++){var pp=bs[i].querySelector('p[contenteditable]');"
   "if(pp){el=pp;break;}}}"
   "if(!el) return 'NOHOST';el.focus();"
   "var rg=document.createRange();rg.selectNodeContents(el);rg.collapse(true);"
   "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Backspace',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(400)
r = js("(function(){return JSON.stringify({src:!!document.querySelector('.raw-edit'),"
       "sel:window.__tblSel ? window.__tblSel() : null})})()")
d = json.loads(r or "{}")
sel = json.loads(d.get("sel") or "{}")
check("DEL below table focuses last row/last col cell (rendered)",
      d.get("src") is False and sel.get("r1") == 1 and sel.get("c1") == 1, d)

# ---------- 9) 点击编辑区下方空白：光标进最后可编辑位置 ----------
js("window.setMarkdown('# 标题\\n\\n正文段落')")
wait(700)
js("(function(){ED.dispatchEvent && window;return 'x'})()")
js("(function(){var ed=document.getElementById('editor');"
   "ed.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(400)
r = js("(function(){return JSON.stringify({tag:document.activeElement.tagName})})()")
d = json.loads(r or "{}")
# v3.38（WYS-4）：末块（正文段落）渲染态聚焦 —— activeElement 为渲染态 p
# （旧实现进源码态 raw-edit 容器 DIV）；「聚焦最后可编辑位置」语义不变
check("click below content focuses last editable block (WYS-4 rendered p)",
      d.get("tag") == "P", d)

# ---------- 10) 代码块插入：语言选择优先，默认 C，↑↓切换，回车进代码区 ----------
js("window.setMarkdown('')")
wait(500)
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(300)
for _ in range(3):
    key("ArrowDown")   # 标题→列表→表格→代码块
key("Enter")
wait(700)
r = js("(function(){var pop=document.getElementById('langpop');"
       "var act=pop.querySelector('.li.act');"
       "return JSON.stringify({show:pop.classList.contains('show'),"
       "act:act?act.textContent:'',"
       "btn:(document.querySelector('.lang-btn')||{}).textContent})})()")
d = json.loads(r or "{}")
check("insert codeblock opens lang pop with C preselected",
      d.get("show") is True and d.get("act") == "C" and d.get("btn") == "C", d)
key("ArrowDown", sel="document.getElementById('lang-q')")
r = js("(function(){var act=document.querySelector('#langpop .li.act');return act?act.textContent:''})()")
check("ArrowDown moves selection (C -> C#)", r == "C#", r)
key("ArrowUp", sel="document.getElementById('lang-q')")
r = js("(function(){var act=document.querySelector('#langpop .li.act');return act?act.textContent:''})()")
check("ArrowUp moves selection back (C# -> C)", r == "C", r)
key("Enter", sel="document.getElementById('lang-q')")
wait(500)
r = js("(function(){return JSON.stringify({"
       "show:document.getElementById('langpop').classList.contains('show'),"
       "focus:document.activeElement===document.querySelector('.codeblock code'),"
       "raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
check("Enter in lang pop applies C and focuses code area",
      d.get("show") is False and d.get("focus") is True
      and (d2.get("raw") or [""])[0].lower().startswith("```c"), d)
r = js("(function(){var code=document.querySelector('.codeblock code');"
       "return JSON.stringify({ce:code.getAttribute('contenteditable'),"
       "outline:getComputedStyle(code).outlineStyle})})()")
d = json.loads(r or "{}")
check("code editing has no input outline",
      d.get("ce") == "plaintext-only" and d.get("outline") == "none", d)

# ---------- 收尾 ----------
flush()
os._exit(0)
