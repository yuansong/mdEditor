# -*- coding: utf-8 -*-
"""v3.24 冒烟测试：
1) 表格块点击（含块内留白）保持渲染态，不再切源码；
2) 表格悬浮按钮按选中范围分类（1 格 / 整列 / 整行 / 多行多列）；
3) 整表缩放等比缩放列宽（拖拽提交后 colgroup 宽度落盘）；
4) 表格块菜单：删除置顶 + 还原尺寸移入 + 复制/上移/下移；
5) 代码块菜单精简；6) 查找对话框「查找 / 全局搜索」双页签。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke28.txt")
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


def raw():
    return jj("window.__raw()")["raw"]


def mdown(sel, x, y):
    js("(function(){var e=document.querySelector('" + sel + "');"
       "['mousedown'].forEach(function(t){e.dispatchEvent(new MouseEvent(t,"
       "{bubbles:true,cancelable:true,clientX:" + str(x) + ",clientY:" + str(y) + "}))});return 'x'})()")


def mmove(x, y):
    js("(function(){document.dispatchEvent(new MouseEvent('mousemove',"
       "{bubbles:true,cancelable:true,clientX:" + str(x) + ",clientY:" + str(y) + "}));return 'x'})()")


def mup():
    js("(function(){document.dispatchEvent(new MouseEvent('mouseup',"
       "{bubbles:true,cancelable:true}));return 'x'})()")


def rect(sel):
    d = js("(function(){var e=document.querySelector('" + sel + "');"
           "if(!e) return null;var r=e.getBoundingClientRect();"
           "return JSON.stringify({l:r.left,t:r.top,w:r.width,h:r.height,"
           "r:r.right,b:r.bottom})})()")
    return json.loads(d) if d else None


def tbl_titles():
    return jj("(function(){var tb=document.getElementById('tblbar');"
              "return JSON.stringify([].map.call(tb.querySelectorAll('button'),"
              "function(x){return x.title}))})()")


def tbl_state(title):
    """v3.30.2 右键菜单上下文过滤：条目要么可用（'en'）要么不显示（'none'）。
    兼容旧置灰语义：仍按 title 前缀命中"""
    return (js("(function(){var b=[].filter.call(document.getElementById('tblbar')"
               ".querySelectorAll('button'),function(x){return x.title.indexOf('"
               + title + "')===0})[0];"
               "return b?(b.classList.contains('dis')?'dis':'en'):'none'})()") or "")


def ctxmenu(sel, x, y):
    js("(function(){var e=document.querySelector('" + sel + "');"
       "var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
       "clientX:" + str(x) + ",clientY:" + str(y) + "});"
       "e.dispatchEvent(ev);return e.defaultPrevented ? 'prevented' : 'system'})()")


def click_act(menu_sel, act):
    js("(function(){var m=document.querySelector('" + menu_sel + "');"
       "var t=m.querySelector('[data-act=\\\"" + act + "\\\"]');"
       "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
       "t.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'})()")


TBL = "| 甲 | 乙 | 丙 |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |"

wait(2500)  # 等待编辑视图加载

# ==================== 1) 表格块点击保持渲染态 ====================
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
# 点表格块留白（.b-table 块的边距区，非 <table> 元素本身）
r = jj("(function(){var blk=document.querySelector('#editor .b-table');"
       "var r=blk.getBoundingClientRect();"
       "blk.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
       "clientX:r.left+2,clientY:r.bottom-2}));"
       "var d=JSON.parse(window.__raw());"
       "return JSON.stringify({editIdx:d.editIdx,"
       "rawEdit:!!document.querySelector('#editor .raw-edit')})})()")
check("点击表格块留白 → 保持渲染态（不切源码）",
      r.get("editIdx") == -1 and r.get("rawEdit") is False, r)
# 点 <table> 本身也不切源码
r = jj("(function(){var t=document.querySelector('#editor .b-table table');"
       "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,clientX:5,clientY:5}));"
       "var d=JSON.parse(window.__raw());"
       "return JSON.stringify({editIdx:d.editIdx})})()")
check("点击 <table> 本身 → 保持渲染态", r.get("editIdx") == -1, r)

# ==================== 2) 右键菜单上下文过滤（v3.30.2：只显示可执行项） ====================
# 2a) 1 个单元格
js("window.__tblSelSet(0, 1, 1, 1, 1)")
wait(250)
check("1 格：插行 / 插列 / 删除 / 对齐可用",
      tbl_state("向上插入行") == "en" and tbl_state("向下插入行") == "en"
      and tbl_state("向左插入列") == "en" and tbl_state("删除行") == "en"
      and tbl_state("删除列") == "en" and tbl_state("左对齐") == "en",
      [tbl_state(x) for x in ("向上插入行", "向下插入行", "向左插入列", "删除行", "删除列", "左对齐")])
check("1 格：拆分可用（v3.29c）/ 合并隐藏（v3.30.10 动态菜单）/ 还原不显示",
      tbl_state("合并单元格") == "none" and tbl_state("拆分单元格（选择行 × 列）") == "en"
      and tbl_state("还原单元格（拆回原格）") == "none",
      [tbl_state(x) for x in ("合并单元格", "拆分单元格（选择行 × 列）", "还原单元格（拆回原格）")])
# 2a-2) 菜单顺序（v3.29c：插入行列 → 删除行列 → 合并/拆分 → 对齐 → 清空/标注）
order = jj("(function(){var tb=document.getElementById('tblbar');"
           "var a=[].map.call(tb.querySelectorAll('button'),function(x){return x.title});"
           "return JSON.stringify(a)})()")
exp_head = ["向上插入行", "向下插入行", "删除行", "向左插入列", "向右插入列", "删除列",
            "合并单元格", "拆分单元格（选择行 × 列）", "还原单元格（拆回原格）",
            "上移该行", "下移该行", "左移该列", "右移该列"]
# v3.30.2：不可用项被隐藏 → 校验「可见项」的相对顺序与 exp_head 一致
def _norm_title(t):
    for e in exp_head:
        if t.startswith(e):
            return e
    return None
vis = [t for t in map(_norm_title, order or []) if t]
try:
    idxs = [exp_head.index(t) for t in vis]
    ok_order = len(vis) >= 8 and idxs == sorted(idxs)
except ValueError:
    ok_order = False
check("菜单顺序：插入行列 → 删除行列 → 合并/拆分/还原（可见项相对顺序）", ok_order, order)
# 2b) 整列（TBL = 表头 + 2 数据行，末行下标 2）
js("window.__tblSelSet(0, 0, 0, 2, 0)")
wait(250)
check("整列：合并 / 删除列 / 插行可用",
      tbl_state("合并单元格") == "en" and tbl_state("删除列") == "en"
      and tbl_state("向上插入行") == "en" and tbl_state("删除行") == "en",
      [tbl_state(x) for x in ("合并单元格", "删除列", "向上插入行", "删除行")])
check("整列：拆分隐藏（v3.30.10 动态菜单，多格不可拆）/ 还原不显示",
      tbl_state("拆分单元格（选择行 × 列）") == "none"
      and tbl_state("还原单元格（拆回原格）") == "none",
      [tbl_state(x) for x in ("拆分单元格（选择行 × 列）", "还原单元格（拆回原格）")])
# 2c) 整行
js("window.__tblSelSet(0, 1, 0, 1, 2)")
wait(250)
check("整行：合并 / 删除行 / 插列可用",
      tbl_state("合并单元格") == "en" and tbl_state("删除行") == "en"
      and tbl_state("向右插入列") == "en",
      [tbl_state(x) for x in ("合并单元格", "删除行", "向右插入列")])
check("整行：删除列不显示（须保留 ≥1 列，v3.30.2 过滤）",
      tbl_state("删除列") == "none", tbl_state("删除列"))
# 2d) 多行多列
js("window.__tblSelSet(0, 0, 0, 2, 2)")
wait(250)
check("多行多列：合并可用 / 删除列不显示 / 对齐常驻 / 标注入口已迁移（v3.30.17）",
      tbl_state("合并单元格") == "en" and tbl_state("删除列") == "none"
      and tbl_state("左对齐") == "en" and tbl_state("清空内容") == "en"
      and tbl_state("表格标注（上方 / 下方）") == "none",
      [tbl_state(x) for x in ("合并单元格", "删除列", "左对齐", "清空内容", "表格标注（上方 / 下方）")])

# ==================== 3) 整表缩放：列宽等比缩放并落盘 ====================
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
# 先拖一次列边界：表格升级为 HTML 存储 + colgroup 固定列宽 + 缩放框出现（与 smoke26 同路径）
th0 = rect("#editor .b-table th")
mdown("#editor .b-table th", th0["r"] - 2, th0["t"] + th0["h"] / 2)
mmove(th0["r"] + 58, th0["t"] + th0["h"] / 2)
mup()
wait(500)
r3a = raw()[0]
check("前置：列宽拖拉后 colgroup 已有固定宽度",
      r3a.startswith("<table class=\"md-tbl\"") and "<colgroup>" in r3a, r3a.split("\n")[1][:90])
# 整表 SE 角手柄向左上拖 150px → 表格缩小，列宽等比缩放（v3.24 新行为）
hbar = rect("#rzframe .rz.se")
mdown("#rzframe .rz.se", hbar["l"] + 4, hbar["t"] + 4)
mmove(hbar["l"] + 4 - 150, hbar["t"] + 4)
mup()
wait(500)
r3 = raw()[0]
check("整表缩小后 table style 仍记录宽度",
      r3.startswith("<table class=\"md-tbl\" style=\"") and "width:" in r3.split(">")[0],
      r3.split("\n")[0])
check("整表缩小 → 列宽等比缩放写入 colgroup（不再被固定列宽托住）",
      "<colgroup>" in r3 and r3.count('style="width:') >= 3,
      r3.split("\n")[1] if "<colgroup>" in r3 else r3[:120])

# 还原尺寸（块菜单）后回到管道表格
ctxmenu("#editor .b-table table", 200, 200)
wait(300)
st = jj("window.__blkMenuState()")
check("表格右键块菜单：删除在最前", (st.get("items") or [None])[0] == "del", st.get("items"))
check("表格块菜单 = 删除/还原尺寸/复制块/上移/下移",
      st.get("items") == ["del", "resetsize", "dup", "up", "down"], st.get("items"))
click_act("#blkmenu", "resetsize")
wait(500)
r4 = raw()[0]
check("块菜单「还原尺寸」→ 清空表格尺寸与列宽（colgroup 移除）",
      r4.startswith("<table") and "<colgroup>" not in r4 and "width:" not in r4,
      r4.split("\n")[0])

# ==================== 4) 代码块菜单精简 ====================
# 代码块右键保留系统菜单（可复制代码），块菜单走 ⠿ 手柄 / Ctrl+/ 入口
js("window.setMarkdown('```js\\nconsole.log(1)\\n```')")
wait(600)
r4b = js("window.openBlockMenu()")
wait(300)
st = jj("window.__blkMenuState()")
check("代码块菜单 = 复制块/上移/下移/删除块（无「转为」组）",
      r4b == "ok" and st.get("items") == ["dup", "up", "down", "del"], [r4b, st.get("items")])
js("(function(){document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'x'})()")
wait(200)

# ==================== 5) 查找对话框（v3.29 当前文件 + 全局搜索同页） ====================
win.show_search()
wait(400)
fd = win._find_dlg
check("Ctrl+Shift+F → 查找对话框且范围为「全局搜索」",
      fd.isVisible() and fd.scope_box.currentIndex() == fd.SCOPE_GLOBAL,
      fd.scope_box.currentIndex())
fd.show_replace(True)
wait(200)
check("Ctrl+H 入口（show_replace）→ 显示替换行（同页合一不再切换范围）",
      fd.replace_row.isVisible() and fd.search_panel.search_tree.isVisible(),
      fd.replace_row.isVisible())
fd.show_global()
wait(200)
check("可切回「全局搜索」入口状态", fd.scope_box.currentIndex() == fd.SCOPE_GLOBAL,
      fd.scope_box.currentIndex())
fd.close()

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
fails = [x for x in results if x.startswith("FAIL")]
sys.exit(1 if fails else 0)
