# -*- coding: utf-8 -*-
"""v3.13 冒烟测试：菜单悬停高亮 / 表格行列选择弹窗与渲染态直编 /
表格工具栏删除按钮与整行整列删除 / 代码块语言选择 / 图片插入弹窗。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke17.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")


app = QApplication(sys.argv)
# v3.24 回归修复：默认代码语言被外部改动会污染断言（smoke17/19/21 依赖默认 C）
from PySide6.QtCore import QSettings as _QS
_QS("WorkBuddy", "WorkBuddyMarkdown").setValue("codeLang", "C")
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


def click_si(label):
    """在斜杠菜单中单击指定文字的一级项"""
    js("(function(){var m=document.getElementById('slashmenu');"
       "var it=[].filter.call(m.querySelectorAll('.si'),function(x){"
       "return x.textContent.indexOf('" + label + "')!==-1})[0];"
       "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")


def open_slash():
    js("window.setMarkdown('')")
    wait(300)
    js("window.openBlockMenu()")
    wait(300)


def tbl_btn(title_prefix):
    return ("(function(){var tb=document.getElementById('tblbar');"
            "var b=[].filter.call(tb.querySelectorAll('button'),function(x){"
            "return x.title.indexOf('" + title_prefix + "')===0})[0];"
            "return b ? (!b.classList.contains('hide') ? 'shown' : 'hidden') : 'none'})()")


def click_btn(title_prefix):
    js("(function(){var tb=document.getElementById('tblbar');"
       "var b=[].filter.call(tb.querySelectorAll('button'),function(x){"
       "return x.title.indexOf('" + title_prefix + "')===0})[0];"
       "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
       "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'c'})()")


wait(2500)  # 等待编辑视图加载

# ---------- 1) 斜杠菜单悬停高亮跟随（就地切换，无反应修复） ----------
open_slash()
r = js("(function(){var m=document.getElementById('slashmenu');"
       "var it=[].filter.call(m.querySelectorAll('.si'),function(x){"
       "return x.textContent.indexOf('表格')!==-1})[0];"
       "it.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
       "return it.classList.contains('act')?'hovered':'no'})()")
check("slash hover highlights item", r == "hovered", r)
r = js("(function(){var m=document.getElementById('slashmenu');"
       "var it=[].filter.call(m.querySelectorAll('.si'),function(x){"
       "return x.textContent.indexOf('图片')!==-1})[0];"
       "it.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
       "return JSON.stringify({act:it.classList.contains('act'),"
       "tblStays:[].filter.call(m.querySelectorAll('.si'),function(x){"
       "return x.textContent.indexOf('表格')!==-1})[0].classList.contains('act')})})()")
d = json.loads(r or "{}")
check("slash hover moves highlight", d.get("act") is True and d.get("tblStays") is False, d)

# ---------- 2) 表格：网格面板（悬停 3×2）→ 渲染态插入 → 光标进 (0,0) ----------
open_slash()
click_si("表格")
wait(400)
r = js("(function(){var tsz=document.getElementById('tblsize');"
       "return JSON.stringify({show:tsz.classList.contains('show'),"
       "hint:document.getElementById('tbl-hint').textContent,"
       "on:document.querySelectorAll('#tblgrid .gc.on').length})})()")
d = json.loads(r or "{}")
check("grid panel opens, default 3x4 selected",
      d.get("show") is True and "3 行 × 4 列" in (d.get("hint") or "")
      and d.get("on") == 12, d)
# 悬停第 3 行第 2 列 → 选中 3 行 × 2 列；renderGrid 会重建格子，点击需重新查询
js("(function(){var g=document.getElementById('tblgrid');"
   "var c=g.querySelector('.gc[data-r=\"2\"][data-c=\"1\"]');"
   "c.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return 'x'})()")
wait(200)
js("(function(){var g=document.getElementById('tblgrid');"
   "var c=g.querySelector('.gc[data-r=\"2\"][data-c=\"1\"]');"
   "c.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'x'})()")
wait(500)
r = js("(function(){var tbl=document.querySelector('#editor .b-table table');"
       "if(!tbl) return 'NOTBL';"
       "var rows=tbl.tHead.rows.length+tbl.tBodies[0].rows.length;"
       "var ae=document.activeElement;"
       "var rg=getSelection();"
       "return JSON.stringify({rows:rows,cols:tbl.tHead.rows[0].cells.length,"
       "ph:tbl.tHead.rows[0].cells[0].textContent,"
       "focused:ae&&ae.tagName==='TH',editable:ae&&ae.getAttribute('contenteditable'),"
       "raw:window.getMarkdown().split('\\n')[0]})})()")
d = json.loads(r or "{}")
check("table 3x2 rendered (no source mode)",
      d.get("rows") == 3 and d.get("cols") == 2, d)
check("no placeholder text in header", d.get("ph") == "", d)
check("cursor in cell r0c0 (contenteditable focused)",
      d.get("focused") is True and d.get("editable") == "plaintext-only", d)
check("table raw synced", (d.get("raw") or "").startswith("|  |"), d)

# ---------- 3) 单元格输入直接编辑 → 源码同步 ----------
r = js("(function(){var th=document.querySelector('#editor .b-table th');"
       "th.focus();document.execCommand('insertText',false,'姓名');"
       "return window.getMarkdown().split('\\n')[0]})()")
check("cell typing syncs markdown", "| 姓名 |" in (r or ""), r)
js("window.setMarkdown('')")
wait(300)

# ---------- 4) 工具栏：无 删行/删列/向上加行，有 删除；整列/整行隐藏逻辑 ----------
js("window.setMarkdown('| a | b | c |\\n| --- | --- | --- |\\n| 1 | 2 | 3 |\\n| 4 | 5 | 6 |\\n| 7 | 8 | 9 |')")
wait(600)
r = js("(function(){var td=document.querySelector('.b-table tbody td');"
       "td.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
       "td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 't'})()")
wait(300)
r = js("(function(){var tb=document.getElementById('tblbar');"
       "var titles=[].map.call(tb.querySelectorAll('button'),function(x){return x.title});"
       "return JSON.stringify({shown:tb.classList.contains('show'),titles:titles})})()")
d = json.loads(r or "{}")
titles = d.get("titles") or []
# v3.29 Office 风格右键菜单：条目常驻、不适用置灰
check("toolbar shown with cell-case buttons",
      d.get("shown") is True and any(t.startswith("向左插入列") for t in titles)
      and any(t.startswith("向上插入行") for t in titles)
      and any(t.startswith("左对齐") for t in titles), titles)
# v3.30.2 右键菜单上下文过滤：不适用项整体隐藏（不再置灰展示）
# v3.30.10 需求变更：菜单按可用性动态显示 —— 单格不可合并 → 合并项整体隐藏
check("cell case: 合并单元格隐藏（v3.30.10 动态菜单，单格不可合并不显示）",
      js("(function(){var b=[].filter.call(document.getElementById('tblbar')"
         ".querySelectorAll('button'),function(x){return x.title.indexOf('合并单元格')===0})[0];"
         "return b ? (b.classList.contains('dis') ? 'dis' : 'en') : 'none'})()") == "none", titles)
check("cell case: 删除行/删除列 enabled",
      js("(function(){var tb=document.getElementById('tblbar');"
         "var dr=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title==='删除行'})[0];"
         "var dc=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title==='删除列'})[0];"
         "return (dr&&!dr.classList.contains('dis')&&dc&&!dc.classList.contains('dis'))?'ok':'bad'})()") == "ok", titles)
check("menu has 清空内容（v3.30.17：表格标注迁至悬浮工具条，右键菜单不再有）",
      any(t.startswith("清空内容") for t in titles) and not any(t.startswith("表格标注") for t in titles), titles)
check("v3.22 T1 补回「向上插入行」按钮",
      any("向上插入行" in t for t in titles), titles)
check("v3.24 悬浮栏不再有「还原尺寸」（移入块菜单）",
      not any("尺寸" in t for t in titles), titles)
# 拖选整列（第 1 列：表头到末行）→ 插行按钮不再出现（v3.24：整列 = 插列/删除列/对齐/合并）
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var th=tbl.tHead.rows[0].cells[0];"
   "th.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
   "var last=tbl.tBodies[0].rows[tbl.tBodies[0].rows.length-1].cells[0];"
   "last.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,buttons:1}));"
   "last.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'd'})()")
wait(300)
r = js(tbl_btn("向下插入行"))
check("whole column: rowDown item stays (v3.29 菜单常驻)", r == "shown", r)
r = js(tbl_btn("向右插入列"))
check("whole column selected keeps colR", r == "shown", r)
r = js(tbl_btn("删除列"))
check("whole column selected: 删除列 enabled", r == "shown" and
      js("(function(){var b=[].filter.call(document.getElementById('tblbar')"
         ".querySelectorAll('button'),function(x){return x.title==='删除列'})[0];"
         "return b?(b.classList.contains('dis')?'dis':'en'):'none'})()") == "en", r)
# 删列：剩 2 列
click_btn("删除列")
wait(400)
r = js("window.getMarkdown().split('\\n')[0]")
check("delete whole column removes it", (r or "").count("|") == 3 and "a" not in (r or ""), r)
# 拖选整行（第 2 数据行）→ 加列按钮移除，删行生效
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var td=tbl.tBodies[0].rows[0].cells[0];"
   "td.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
   "var last=tbl.tBodies[0].rows[0].cells[tbl.tBodies[0].rows[0].cells.length-1];"
   "last.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,buttons:1}));"
   "last.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'd'})()")
wait(300)
r = js(tbl_btn("向右插入列"))
check("whole row: colR item stays (v3.29 菜单常驻)", r == "shown", r)
r = js(tbl_btn("向下插入行"))
check("whole row selected keeps rowDown", r == "shown", r)
r = js("window.__tblSel()")
check("dbg tblSel before row delete", True, r)
click_btn("删除行")
wait(400)
r = js("window.__tblSel()")
check("dbg tblSel after row delete", True, r)
r = js("window.getMarkdown()")
check("delete whole row removes it",
      "| 2 | 3 |" not in (r or "") and "| 5 | 6 |" in (r or ""), (r or "")[:80])
# 整表选中 → v3.29 菜单常驻：删除行可用（删数据行）/ 删除列置灰（须保留 ≥1 列）
# v3.30.5 锚点-指针矩形：单步跳到对角格即整表矩形（无阈值无插值）
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var th=tbl.tHead.rows[0].cells[0];"
   "var r0=th.getBoundingClientRect();"
   "th.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1,buttons:1,"
   "clientX:r0.left+r0.width/2,clientY:r0.top+r0.height/2}));"
   "var lastRow=tbl.tBodies[0].rows[tbl.tBodies[0].rows.length-1];"
   "var last=lastRow.cells[lastRow.cells.length-1];"
   "var r1=last.getBoundingClientRect();"
   "last.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,buttons:1,"
   "clientX:r1.left+r1.width/2,clientY:r1.top+r1.height/2}));"
   "last.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'd'})()")
wait(300)
r = js(tbl_btn("删除行"))
dc_dis = js("(function(){var b=[].filter.call(document.getElementById('tblbar')"
            ".querySelectorAll('button'),function(x){return x.title.indexOf('删除列')===0})[0];"
            "return b ? 'shown' : 'none'})()")
check("whole table: 删除行 enabled / 删除列 hidden（须保留 ≥1 列，v3.30.2 过滤）",
      r == "shown" and dc_dis == "none", r + " dc_dis=" + str(dc_dis))
r = js(tbl_btn("合并"))
check("whole table diagonal drag: merge shown（v3.30.4 矩形语义，对角=整表矩形）",
      r == "shown", r)
# 程序化矩形选区（按当前表格实际尺寸）→ 合并可用（Shift+点选等价路径）
try:
    dims = json.loads(js("(function(){var t=document.querySelector('.b-table table');"
                         "var n=(t.tHead?t.tHead.rows.length:0)+t.tBodies[0].rows.length;"
                         "var cs=(t.tHead||t.tBodies[0]).rows[0].cells.length;"
                         "return JSON.stringify({r:n-1,c:cs-1})})()") or "{}")
except Exception:
    dims = {}
js(f"window.__tblSelSet(0, 0, 0, {dims.get('r')}, {dims.get('c')})")
wait(250)
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var th=tbl.tHead.rows[0].cells[0];"
   "th.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'd'})()")
wait(300)
r = js(tbl_btn("合并"))
check("whole table rect select: merge shown（矩形选区可合并）", r == "shown", r)
js("window.__tblOp('del')")
wait(400)
r = js("window.getMarkdown()")
check("whole table delete removes block", ".b-table" not in (r or "") and "| --- |" not in (r or ""), (r or "")[:40])

# ---------- 5) 代码块：渲染态 + 语言选择（可搜索/自定义） ----------
open_slash()
click_si("代码块")
wait(400)
r = js("(function(){var cb=document.querySelector('#editor .codeblock');"
       "if(!cb) return 'NOCB';"
       "var code=cb.querySelector('code');"
       "var ae=document.activeElement;"
       "return JSON.stringify({hasBar:!!cb.querySelector('.codebar'),"
       "lang:cb.querySelector('.lang-btn').textContent,"
       "focused:ae===code,editable:code.getAttribute('contenteditable')})})()")
d = json.loads(r or "{}")
check("code block rendered with lang bar (default C preselected)",
      d.get("hasBar") is True and d.get("lang") == "C", d)
check("cursor waits in lang pop (v3.17)", d.get("focused") is False and
      d.get("editable") == "plaintext-only", d)
# 回车确认语言 → 光标进代码区
js("(function(){var q=document.getElementById('lang-q');"
   "q.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "code.focus();document.execCommand('insertText',false,'print(1)');"
       "return window.getMarkdown()})()")
check("code typing syncs markdown", "print(1)" in (r or ""), (r or "")[:40])
# 语言选择：输入过滤 + 自定义回车
js("(function(){var b=document.querySelector('#editor .lang-btn');"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'o'})()")
wait(300)
r = js("(function(){var lp=document.getElementById('langpop');"
       "return lp.classList.contains('show')?'open':'no'})()")
check("lang picker opens", r == "open", r)
js("(function(){var q=document.getElementById('lang-q');q.value='Pyth';"
   "q.dispatchEvent(new Event('input',{bubbles:true}));return 'i'})()")
wait(200)
r = js("(function(){var lis=document.querySelectorAll('#lang-list .li');"
       "return lis.length ? lis[0].textContent : 'EMPTY'})()")
check("lang list filters by input", r == "Python", r)
js("(function(){var q=document.getElementById('lang-q');q.value='Python';"
   "q.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return 'e'})()")
wait(300)
r = js("(function(){var b=document.querySelector('#editor .lang-btn');"
       "return JSON.stringify({btn:b.textContent,md:window.getMarkdown().split('\\n')[0]})})()")
d = json.loads(r or "{}")
# v3.30.18（CODE-7）：语言名统一小写写入源码（对齐 GitHub / VS Code 生态）
check("language set to Python（源码小写化）",
      d.get("btn") == "Python" and (d.get("md") or "").startswith("```python"), d)

# ---------- 6) 图片：v3.27 统一 Qt 面板（编辑器内 imgpop 已移除，不再双重面板） ----------
open_slash()
click_si("图片")
# v3.29：Python 轮询消费 __wantPick 后会弹出模态 InsertImageDialog（标志随即复位），
# 单次读取会与轮询竞态 —— 轮询断言，取到 pick 或超时为止
r = "no"
for _ in range(14):
    r = js("window.__wantPick === true ? 'pick' : 'no'")
    if r == "pick":
        break
    wait(150)
check("image insert → 请求 Qt 统一面板（__wantPick）", r == "pick", r)
js("window.__wantPick = false")
# 关闭轮询弹出的模态插图面板，避免影响后续断言
_mw = QApplication.activeModalWidget()
if _mw is not None and _mw is not win:
    _mw.close()
    wait(200)
# 网络 URL 插入路径（原 imgpop 的 URL 能力并入 Qt 面板；此处直调编辑器 API 验证落码与渲染）
js("window.insertImageMarkdown('https://example.com/a.png', '图片')")
wait(500)
r = js("(function(){var md=window.getMarkdown();"
       "var im=document.querySelector('#editor img');"
       "return JSON.stringify({md:md,img:im?(im.getAttribute('src')||''):''})})()")
d = json.loads(r or "{}")
check("url image inserted as markdown",
      "![图片](https://example.com/a.png)" in (d.get("md") or ""), d.get("md"))
check("url image renders as <img>", d.get("img") == "https://example.com/a.png", d.get("img"))

# ---------- 收尾 ----------
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
os._exit(0)
