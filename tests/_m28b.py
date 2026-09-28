# -*- coding: utf-8 -*-
"""v3.28 探针：表格操作菜单右键化 + 删除边框残留修复。
1) 单元格右键 → 表格操作菜单出现（等价旧悬浮栏）；
2) 拖选后松手不再自动弹出（只保留选区）；
3) 右键选区外的格 → 选区重置为该格；
4) 选中表格（缩放框出现）后经块菜单删除 → 边框 / 操作条无残留。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m28b.txt")
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


def jj(code):
    return json.loads(js(code) or "{}")


TBL = "| 甲 | 乙 | 丙 |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |"

# ==================== 1) 单元格右键 → 操作菜单 ====================
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
r = js("(function(){var td=document.querySelector('.b-table tbody td');"
       "td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:60,clientY:60}));"
       "var tb=document.getElementById('tblbar');"
       "var titles=[].map.call(tb.querySelectorAll('button'),function(x){return x.title});"
       "return JSON.stringify({show:tb.classList.contains('show'),titles:titles})})()")
wait(200)
d = json.loads(r or "{}")
check("单元格右键 → 操作菜单弹出", d.get("show") is True, d)
merge_state = js("(function(){var b=[].filter.call(document.getElementById('tblbar')"
                 ".querySelectorAll('button'),function(x){return x.title==='合并单元格'})[0];"
                 "return b?(b.classList.contains('dis')?'dis':'en'):'none'})()")
check("右键菜单（单选格）含插列 / 插行 / 对齐，合并隐藏（v3.30.10 动态菜单）",
      any("向右插入列" in t for t in d.get("titles", []))
      and any("向下插入行" in t for t in d.get("titles", []))
      and any("左对齐" in t for t in d.get("titles", []))
      and merge_state == "none", d.get("titles"))
sel1 = jj("window.__tblSel()")
check("右键的格成为单选区", sel1.get("r0") == 1 and sel1.get("c0") == 0, sel1)

# ==================== 1b) 拖选多格后右键 → 菜单出现「合并单元格」并可直接合并 ====================
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var a=tbl.tBodies[0].rows[0].cells[0];"
   "var b=tbl.tBodies[0].rows[0].cells[1];"
   "var ra=a.getBoundingClientRect();"
   "a.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1,buttons:1,"
   "clientX:ra.left+ra.width/2,clientY:ra.top+ra.height/2}));"
   "var rb=b.getBoundingClientRect();"
   "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,buttons:1,"
   "clientX:rb.left+rb.width/2,clientY:rb.top+rb.height/2}));"
   "b.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'd'})()")
wait(300)
r = js("(function(){var tb=document.getElementById('tblbar');"
       "var titles=[].map.call(tb.querySelectorAll('button'),function(x){return x.title});"
       "return JSON.stringify({show:tb.classList.contains('show'),titles:titles})})()")
d = json.loads(r or "{}")
check("拖选 1×2 后右键 → 菜单出现「合并单元格」",
      d.get("show") is True and any("合并单元格" in t for t in d.get("titles", [])), d.get("titles"))
js("(function(){var tb=document.getElementById('tblbar');"
   "var b=[].filter.call(tb.querySelectorAll('button'),function(x){return x.title.indexOf('合并单元格')>=0})[0];"
   "if(!b) return 'NOBTN';b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'})()")
wait(500)
r = jj("window.__raw()").get("raw", [""])[0]
check("右键菜单点「合并单元格」→ colspan 合并存储", 'colspan="2"' in r, r[:160])
# 合并后（keepSel 选区=合并框）右键 → 出现还原 / 拆分
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var td=tbl.tBodies[0].rows[0].cells[0];"
   "td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("(function(){var tb=document.getElementById('tblbar');"
       "var titles=[].map.call(tb.querySelectorAll('button'),function(x){return x.title});"
       "return JSON.stringify(titles)})()")
titles = json.loads(r or "[]")
check("合并框右键 → 出现还原 / 拆分",
      any("还原单元格" in t for t in titles) and any("拆分单元格" in t for t in titles), titles)

# ==================== 2) 拖选松手不再自动弹出 ====================
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var th=tbl.tHead.rows[0].cells[0];"
   "var r0=th.getBoundingClientRect();"
   "th.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1,buttons:1,"
   "clientX:r0.left+r0.width/2,clientY:r0.top+r0.height/2}));"
   "var last=tbl.tBodies[0].rows[0].cells[2];"
   "var r2=last.getBoundingClientRect();"
   "last.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,buttons:1,"
   "clientX:r2.left+r2.width/2,clientY:r2.top+r2.height/2}));"
   "last.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));return 'd'})()")
wait(300)
r2 = js("document.getElementById('tblbar').classList.contains('show')")
check("拖选松手 → 操作菜单不再自动弹出（仅选区高亮）", r2 is False, r2)
sel2 = jj("window.__tblSel()")
check("拖选选区仍生效（r0c0→r1c2）",
      sel2.get("r0") == 0 and sel2.get("c1") == 2, sel2)

# ==================== 3) 右键选区外 → 选区重置为该格 ====================
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var td=tbl.tBodies[0].rows[1].cells[2];"
   "td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'x'})()")
wait(250)
sel3 = jj("window.__tblSel()")
check("右键选区外 → 选区重置为该格单选", sel3.get("r0") == 2 and sel3.get("c0") == 2, sel3)

# ==================== 4) 删除表格 → 缩放边框无残留 ====================
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
# 先拖一次列边界：表格升级为 HTML + commitTblRz → selectTblFrame → 缩放框出现
js("(function(){var tbl=document.querySelector('.b-table table');"
   "var th=tbl.tHead.rows[0].cells[0];"
   "var r=th.getBoundingClientRect();"
   "th.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
   "clientX:r.right-2,clientY:r.top+r.height/2}));"
   "document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
   "clientX:r.right+58,clientY:r.top+r.height/2}));"
   "document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true}));return 'x'})()")
wait(500)
st = jj("window.__rzShow()")
check("列边界拖拽后 → 缩放框出现（前置）", st.get("frame") is True, st)
# 经块菜单删除（右键表格留白 → 删除块）
js("(function(){var b=document.querySelector('.b-table');"
   "b.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
   "clientX:8,clientY:8}));return 'x'})()")
wait(300)
js("(function(){var m=document.getElementById('blkmenu');"
   "var mi=m.querySelector('[data-act=del]');"
   "if(!mi) return 'NOMI';"
   "mi.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "mi.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'x'})()")
wait(500)
st2 = jj("window.__rzShow()")
md = jj("window.__raw()")
check("删除表格 → 缩放边框无残留", st2.get("frame") is False, st2)
check("删除表格 → 表格块已移除", all(".b-table" not in x for x in md.get("raw", [])), md.get("raw", [])[:2])

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results) + "\n")
    p = sum(1 for r in results if r.startswith("PASS"))
    fl = sum(1 for r in results if r.startswith("FAIL"))
    f.write(f"DONE PASS={p} FAIL={fl}\n")
win.close()
app.processEvents()
