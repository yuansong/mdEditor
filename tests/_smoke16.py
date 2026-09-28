# -*- coding: utf-8 -*-
"""v3.11 冒烟测试：图表插入后可继续编辑 / 本地图片插入 / 粘贴图片通道 /
大纲选中样式 / 状态栏行列 / 表格颜色一体与首格光标。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, QSettings

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke16.txt")
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


wait(2500)  # 等待编辑视图加载

# ---------- 1) 状态栏行列随光标 ----------
r = js("window.setMarkdown('# 标题\\n\\n第一段文字'); 'ok'")
wait(500)
# 点击第三块（第一段文字）进入编辑，光标移到块末，应上报 行3·列6
r = js("(function(){try{var blks=document.querySelectorAll('#editor .blk');"
       "var b=blks[1];if(!b) return 'NOBLOCK:'+blks.length;var rct=b.getBoundingClientRect();"
       "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,"
       "clientX:rct.left+10,clientY:rct.top+5}));"
       "return 'EDIT:'+!!document.querySelector('.raw-edit')}catch(e){return 'ERR:'+e.message}})()")
check("click enters edit on block", (r or "").startswith("EDIT:true"), r)
r = js("(function(){try{var el=document.querySelector('.raw-edit');"
       "el.focus();var sel=getSelection();var rg=document.createRange();"
       "rg.selectNodeContents(el);rg.collapse(false);"
       "sel.removeAllRanges();sel.addRange(rg);"
       "return window.getCaretLineCol()}catch(e){return 'ERR:'+e.message}})()")
d = json.loads(r or "{}") if (r or "").startswith("{") else {"raw": r}
check("caret line/col follows cursor", d.get("line") == 3 and d.get("col") == 6, d)
js("window.setMarkdown('')")
wait(300)

# ---------- 2) 图表插入后焦点可继续编辑 ----------
r = js("window.openBlockMenu()")
check("ctrl+/ opens slash on empty", r == "slash", r)
wait(300)
# 一级菜单：点击「图表」展开二级，再点「流程图」
js("(function(){var m=document.getElementById('slashmenu');"
   "var it=[].filter.call(m.querySelectorAll('.si'),function(x){return x.textContent.indexOf('图表')!==-1})[0];"
   "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")
wait(300)
js("(function(){var s=document.getElementById('submenu');"
   "var it=[].filter.call(s.querySelectorAll('.si'),function(x){return x.textContent.indexOf('流程图')!==-1})[0];"
   "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")
wait(400)
r = js("window.getMarkdown()")
check("chart inserted", (r or "").startswith("```mermaid"), (r or "")[:24])
# 焦点应已落到下方新的空段落（raw-edit 存在且内容为空）
d = {}
for _ in range(30):
    wait(500)
    r = js("(function(){var el=document.querySelector('.raw-edit');"
           "var m=document.querySelector('.mermaidblock');"
           "return JSON.stringify({edit:!!el, empty:el?el.textContent==='':null,"
           "svg:m?!!m.querySelector('svg'):false})})()")
    d = json.loads(r or "{}")
    if d.get("edit") and d.get("svg"):
        break
check("chart rendered", d.get("svg") is True, d)
check("focus moved to editable empty block", d.get("edit") is True and d.get("empty") is True, d)
# 在焦点块直接输入文字（模拟 execCommand）确认可继续编辑
r = js("(function(){var el=document.querySelector('.raw-edit');"
       "el.focus();document.execCommand('insertText',false,'继续编辑');"
       "return el.textContent})()")
check("can type after chart insert", r == "继续编辑", r)
js("window.setMarkdown('')")
wait(300)

# ---------- 3) 本地图片插入（insertImageMarkdown / collect.pick） ----------
r = js("window.insertImageMarkdown('data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==','测试')")
check("insert image ok", r == "ok", r)
r = js("window.getMarkdown()")
check("image markdown embedded", "![测试](data:image/png;base64," in (r or ""), (r or "")[:60])
js("window.setMarkdown(window.getMarkdown())")
wait(500)
r = js("(function(){var im=document.querySelector('#editor img');"
       "return im ? (im.getAttribute('src')||'').slice(0,22) : 'NOIMG'})()")
check("image renders as <img> data url", (r or "").startswith("data:image/png"), r)
# pick 接力标记（同步取值复位，避免触发真实对话框）
r = js("window.__wantPick=true; var d=JSON.parse(window.collect()); window.__wantPick=false; d.pick")
check("collect exposes pick flag", r is True or r == "true", r)
js("window.setMarkdown('')")
wait(300)

# ---------- 4) 表格：颜色一体 + v3.14 网格选择面板（默认 6×6） ----------
js("window.setMarkdown('| a | b |\\n| --- | --- |\\n| 1 | 2 |')")
wait(600)
r = js("(function(){var th=document.querySelector('#editor .blk th');"
       "if(!th) return 'NOTH';"
       "return JSON.stringify({bg:getComputedStyle(th).backgroundColor})})()")
d = json.loads(r or "{}")
check("table header transparent", d.get("bg") in ("rgba(0, 0, 0, 0)", "transparent"), d)
js("window.setMarkdown('')")   # 清空文档：空块上 openBlockMenu 才是斜杠菜单
wait(300)
r = js("window.openBlockMenu()")
check("empty doc opens slash for table", r == "slash", r)
wait(300)
js("(function(){var m=document.getElementById('slashmenu');"
   "var it=[].filter.call(m.querySelectorAll('.si'),function(x){return x.textContent.indexOf('表格')!==-1})[0];"
   "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")
wait(400)
r = js("(function(){var tsz=document.getElementById('tblsize');"
       "return JSON.stringify({show:tsz.classList.contains('show'),"
       "hint:document.getElementById('tbl-hint').textContent,"
       "on:document.querySelectorAll('#tblgrid .gc.on').length})})()")
d = json.loads(r or "{}")
check("grid panel opens default 3x4 selected (panel 6x6)",
      d.get("show") is True and "3 行 × 4 列" in (d.get("hint") or "")
      and d.get("on") == 12, d)
# 悬停面板右下角（第 6 行第 6 列）→ 选中 6×6，面板扩到 7 行可见；
# 再次悬停新增的边缘格 → 选区继续扩大
js("(function(){var g=document.getElementById('tblgrid');"
   "var c=g.querySelector('.gc[data-r=\"5\"][data-c=\"5\"]');"
   "c.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return 'x'})()")
wait(200)
r = js("document.getElementById('tbl-hint').textContent")
check("hover bottom-right corner selects 6x6",
      "6 行 × 6 列" in (r or ""), r)
js("(function(){var g=document.getElementById('tblgrid');"
   "var c=g.querySelector('.gc[data-r=\"6\"][data-c=\"6\"]');"
   "c.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return 'x'})()")
wait(200)
r = js("document.getElementById('tbl-hint').textContent")
check("panel grows beyond 6x6 to 7x7 selection",
      "7 行 × 7 列" in (r or ""), r)
js("(function(){var g=document.getElementById('tblgrid');"
   "var c=g.querySelector('.gc[data-r=\"2\"][data-c=\"1\"]');"
   "c.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'x'})()")
wait(500)
r = js("(function(){var md=window.getMarkdown();"
       "var tbl=document.querySelector('#editor .blk table');"
       "if(!tbl) return 'NOTBL';"
       "return JSON.stringify({rows:tbl.querySelectorAll('tr').length,"
       "cols:tbl.tHead.rows[0].cells.length})})()")
d = json.loads(r or "{}")
check("grid click inserts 3x2 table (click selects hovered cell)",
      d.get("rows") == 3 and d.get("cols") == 2, d)
js("window.setMarkdown('')")
wait(300)

# ---------- 4b) 表格列均匀分布（table-layout: fixed，首末列等宽） ----------
js("window.setMarkdown('| a | bbbb | cccccc |\\n| --- | --- | --- |\\n| 1 | 2 | 3 |')")
wait(600)
r = js("(function(){var tbl=document.querySelector('#editor .blk table');"
       "if(!tbl) return 'NOTBL';"
       "var cs=getComputedStyle(tbl);"
       "var ths=tbl.querySelectorAll('th');"
       "var w0=ths[0].getBoundingClientRect().width,w2=ths[ths.length-1].getBoundingClientRect().width;"
       "return JSON.stringify({layout:cs.tableLayout,w:cs.width,w0:Math.round(w0),w2:Math.round(w2)})})()")
d = json.loads(r or "{}")
check("table layout fixed full width", d.get("layout") == "fixed" and
      str(d.get("w", "")).endswith("%") is False and d.get("w") not in (None, "auto"), d)
check("columns evenly distributed", abs((d.get("w0") or 0) - (d.get("w2") or 0)) <= 2, d)
js("window.setMarkdown('')")
wait(300)

# ---------- 5) 大纲选中样式（无绿色系统阴影） ----------
qss = win._sidebar.styleSheet()
check("outline branch transparent qss", "QTreeWidget::branch" in qss and
      "show-decoration-selected: 0" in qss, qss[:120])

# ---------- 收尾（不弹保存对话框，直接退出） ----------
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
os._exit(0)
