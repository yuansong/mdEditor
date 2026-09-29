# -*- coding: utf-8 -*-
"""v3.22 P1 冒烟测试

覆盖五项 P1 优化：
  R1 渲染态特殊块（图片 / 分割线 / 图表 / 表格）右键弹自定义块菜单
  F1 格式栏 🔗 改为页内小弹层（不再 window.prompt）
  G1 打字机模式给编辑区上下加 40vh 内边距（首/尾块也能居中）
  T1 表格工具栏补「向上插入行」（管道表格 + HTML 表格）
  G5 块菜单三入口（Ctrl+/ / ⠿ 手柄 / 右键）默认展开行为统一
"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke27.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
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


def jj(code):
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


def raw():
    d = jj("window.__raw()")
    return d.get("raw") or [""]


def close_pops():
    js("document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
       "clientX:5,clientY:5}))")
    wait(160)


def ctxmenu(sel, x=200, y=200):
    """在元素上派发可取消的 contextmenu，返回 'prevented'（被接管）/ 'system'（保留系统菜单）"""
    return js("(function(){var e=document.querySelector(" + json.dumps(sel) + ");"
              "if(!e) return 'NOEL';"
              "var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
              "clientX:" + str(x) + ",clientY:" + str(y) + "});"
              "e.dispatchEvent(ev);return ev.defaultPrevented?'prevented':'system';})()")


def click_btn(bar, part):
    return js("(function(){var b=document.querySelectorAll(" + json.dumps(bar + ' button') + ");"
              "for(var i=0;i<b.length;i++){if((b[i].title||'').indexOf(" + json.dumps(part) + ")>=0"
              "||(b[i].textContent||'').indexOf(" + json.dumps(part) + ")>=0)"
              "{b[i].click();return 'ok';}}return 'nobtn';})()")


def click_act(bar, act):
    return js("(function(){var m=document.querySelector(" + json.dumps(bar) + ");"
              "if(!m) return 'nobar';"
              "var t=m.querySelector('[data-act=\"" + act + "\"]');"
              "if(!t) return 'noitem';"
              "t.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok';})()")


def select_block_text(sel):
    """把某个块的渲染文本整体设为当前选区（触发格式栏）"""
    js("(function(){var p=document.querySelector(" + json.dumps(sel) + ");if(!p) return 'NOEL';"
       "var r=document.createRange();r.selectNodeContents(p);"
       "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'x';})()")
    wait(500)


wait(2500)

IMG = ("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='120'"
       "%20height='60'%3E%3Crect%20width='120'%20height='60'%20fill='%23dde'/%3E%3C/svg%3E")

# ==================== 1) G1 打字机模式首尾 40vh 内边距 ====================
d0 = jj("(function(){var e=document.getElementById('editor');"
        "return JSON.stringify({cls:e.classList.contains('typing'),"
        "pt:parseFloat(getComputedStyle(e).paddingTop)})})()")
check("G1 初始（非打字机）无 typing 类且顶部内边距较小",
      d0.get("cls") is False and d0.get("pt", 999) < 100, d0)

js("window.setMode({typewriter:true})")
wait(300)
d1 = jj("(function(){var e=document.getElementById('editor');var vh=window.innerHeight;"
        "return JSON.stringify({cls:e.classList.contains('typing'),"
        "pt:parseFloat(getComputedStyle(e).paddingTop),pb:parseFloat(getComputedStyle(e).paddingBottom),"
        "vh40:vh*0.4})})()")
check("G1 开打字机 → 编辑区加 typing 类", d1.get("cls") is True, d1)
check("G1 开打字机 → 顶部内边距≈40vh",
      abs(d1.get("pt", 0) - d1.get("vh40", 0)) <= 2, [d1.get("pt"), d1.get("vh40")])
check("G1 开打字机 → 底部内边距仍≥40vh", d1.get("pb", 0) >= d1.get("vh40", 0) - 2,
      [d1.get("pb"), d1.get("vh40")])

js("window.setMode({typewriter:false})")
wait(300)
d2 = jj("(function(){var e=document.getElementById('editor');"
        "return JSON.stringify({cls:e.classList.contains('typing'),"
        "pt:parseFloat(getComputedStyle(e).paddingTop)})})()")
check("G1 关打字机 → typing 类移除、内边距还原",
      d2.get("cls") is False and d2.get("pt", 999) < 100, d2)

# ==================== 2) R1 图片块右键块菜单 ====================
js("window.setMarkdown(" + json.dumps("![示意图](" + IMG + ")") + ")")
wait(700)
r = ctxmenu("#editor .b-p img", 120, 90)
wait(300)
st = jj("window.__blkMenuState()")
check("R1 图片块右键被接管（不再只给系统复制菜单）", r == "prevented", r)
check("R1 图片块右键弹出自定义块菜单", st.get("show") is True, st)
check("R1 图片块菜单项 = 图注/重置尺寸/精确尺寸/对齐/全部转本地/显示图片/复制图片/上移/下移/删除块（v3.30.17 右键菜单化；v3.30.19 增 IMG-5/6/7 项，未存文档无存储项）",
      st.get("items") == ["edit", "imgreset", "imgsize", "imgalign-sub", "imglocalall", "viewimg", "copyimg", "up", "down", "del"], st.get("items"))

res = click_act("#blkmenu", "edit")
wait(400)
d = jj("(function(){return JSON.stringify({cp:document.getElementById('cappop').classList.contains('show')})})()")
check("R1 图片块「图注」打开图注弹层", res == "ok" and d.get("cp") is True, [res, d])
close_pops()

# R1 分割线：块菜单里没有「编辑」项
js("window.setMarkdown('---')")
wait(600)
r = ctxmenu("#editor .b-hr", 120, 90)
wait(300)
st = jj("window.__blkMenuState()")
check("R1 分割线右键弹出块菜单", r == "prevented" and st.get("show") is True, [r, st])
check("R1 分割线菜单只留必要块级操作（v3.30.10 HR-5：复制/上移/下移/删除）",
      st.get("items") == ["dup", "up", "down", "del"], st.get("items"))
close_pops()

# R1 图表块
js("window.setMarkdown('```mermaid\\nflowchart TD\\n  A-->B\\n```')")
wait(1400)
r = ctxmenu("#editor .mermaidblock", 200, 200)
wait(300)
st = jj("window.__blkMenuState()")
check("R1 图表块右键弹出块菜单（编辑源码 + v3.30.10 MMD-5 复制块）",
      r == "prevented" and st.get("items") == ["edit", "dup", "up", "down", "del"], [r, st.get("items")])
close_pops()

# R1 普通段落仍保留系统右键菜单
js("window.setMarkdown('普通段落文字')")
wait(600)
r = ctxmenu("#editor .b-p", 120, 90)
wait(200)
check("R1 普通段落仍保留系统右键菜单（复制 / 粘贴）", r == "system", r)
close_pops()

# R1 块菜单「删除块」
js("window.setMarkdown(" + json.dumps("![示意图](" + IMG + ")") + ")")
wait(700)
ctxmenu("#editor .b-p img", 120, 90)
wait(300)
click_act("#blkmenu", "del")
wait(500)
rr = raw()
check("R1 块菜单「删除块」把整块删掉",
      not any(("![示意图]" in x) or ("<img" in x) for x in rr), rr)
close_pops()

# ==================== 3) F1 链接页内弹层 ====================
TEXT = "这是一段用来加链接的文字"
EXPECT = "[" + TEXT + "](https://example.com)"
js("window.setMarkdown(" + json.dumps(TEXT) + ")")
wait(700)
select_block_text("#editor .b-p")
d = jj("(function(){return JSON.stringify({fb:document.getElementById('floatbar').classList.contains('show'),"
       "n:document.querySelectorAll('#floatbar button').length})})()")
# v3.25：浮动格式栏新增「高亮」按钮，按钮数 6 → 7
check("F1 选中正文 → 格式栏出现", d.get("fb") is True and d.get("n") == 7, d)

res = click_btn("#floatbar", "链接")
wait(400)
lp = jj("window.__linkPop()")
check("F1 点🔗 → 弹的是页内输入层（不是 window.prompt）",
      res == "ok" and lp.get("show") is True, [res, lp])

js("(function(){document.getElementById('link-url').value='https://example.com';return 'x'})()")
js("document.getElementById('link-ok').click()")
wait(500)
check("F1 确认后按选区写入 Markdown 链接", raw()[0] == EXPECT, raw()[0])

# 取消 / toggle：v3.31.2（FMT-2）链接 toggle 语义 —— 已链接文字再点 🔗 = 直接移除
# 链接（与其余 6 个动作的 toggle 行为对齐，不弹输入层、不产生嵌套）
select_block_text("#editor .b-p")
click_btn("#floatbar", "链接")
wait(400)
d = jj("(function(){var d=JSON.parse(window.__raw());"
       "return JSON.stringify({lp:document.getElementById('linkpop').classList.contains('show'),"
       "editIdx:d.editIdx,raw:d.raw[0]})})()")
check("F1 已链接文字再点 🔗 → toggle 移除链接（不嵌套、不弹层）",
      d.get("lp") is False and d.get("editIdx") == -1
      and d.get("raw") == "这是一段用来加链接的文字", d)

# 非链接文字：弹层取消路径仍然不改内容、不残留源码态
select_block_text("#editor .b-p")
click_btn("#floatbar", "链接")
wait(400)
close_pops()
d = jj("(function(){var d=JSON.parse(window.__raw());"
       "return JSON.stringify({lp:document.getElementById('linkpop').classList.contains('show'),"
       "editIdx:d.editIdx,raw:d.raw[0]})})()")
check("F1 链接输入弹层取消 → 不改内容、不残留源码态",
      d.get("lp") is False and d.get("editIdx") == -1
      and d.get("raw") == "这是一段用来加链接的文字", d)

# ==================== 4) T1 表格向上插行 ====================
TBL = "| 甲 | 乙 | 丙 |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |"
js("window.setMarkdown(" + json.dumps(TBL) + ")")
wait(700)
js("window.__tblSelSet(0, 1, 0, 1, 0)")
wait(250)
res = click_btn("#tblbar", "向上插入行")
wait(400)
lines = raw()[0].split("\n")
check("T1 工具栏出现「向上插入行」按钮", res == "ok", res)
check("T1 管道表格：向上插行 → 行数 +1", len(lines) == 5, lines)
check("T1 新空行插在选中行上方（表头正下方）",
      "| --- |" in lines[1] and lines[2].count("|") == 4 and lines[3].strip() == "| 1 | 2 | 3 |",
      lines)
check("T1 原有数据行顺序不变", lines[3].strip() == "| 1 | 2 | 3 |" and lines[4].strip() == "| 4 | 5 | 6 |",
      [lines[3], lines[4]])

# 表头行被选中时，向上插行落到表头正下方（不越过表头）
js("window.setMarkdown(" + json.dumps(TBL) + ")")
wait(700)
js("window.__tblSelSet(0, 0, 0, 0, 0)")
wait(250)
click_btn("#tblbar", "向上插入行")
wait(400)
lines2 = raw()[0].split("\n")
check("T1 选中表头时向上插行 → 不越过表头（表头/分隔行不动）",
      lines2[0].strip() == "| 甲 | 乙 | 丙 |" and "| --- |" in lines2[1] and len(lines2) == 5, lines2)

# HTML 表格
HTBL = ('<table class="md-tbl">\n  <thead>\n    <tr><th>甲</th><th>乙</th></tr>\n  </thead>\n'
        '  <tbody>\n    <tr><td>1</td><td>2</td></tr>\n    <tr><td>3</td><td>4</td></tr>\n  </tbody>\n</table>')
js("window.setMarkdown(" + json.dumps(HTBL) + ")")
wait(700)
js("window.__tblSelSet(0, 1, 0, 1, 0)")
wait(250)
click_btn("#tblbar", "向上插入行")
wait(400)
r = raw()[0]
check("T1 HTML 表格：向上插行 → 多一个空 <tr>", r.count("<tr>") == 4, r.count("<tr>"))
check("T1 HTML 表格：空行插在选中行上方",
      r.index("</thead>") < r.index("<tr><td></td><td></td></tr>") < r.index("<tr><td>1</td>"),
      r[:260])

# ==================== 5) G5 块菜单三入口展开行为统一 ====================
js("window.setMarkdown('第一段内容')")
wait(700)
js("window.openBlockMenu()")
wait(450)
st = jj("window.__blkMenuState()")
check("G5 Ctrl+/ 入口：块菜单打开", st.get("show") is True, st)
check("G5 Ctrl+/ 入口：默认展开「标题」二级（6 级，v3.31.1 移除标题7）",
      st.get("sub") is True and len(st.get("subItems") or []) == 6, st.get("subItems"))
close_pops()

# ⠿ 手柄入口（与 Ctrl+/ 行为一致）
r = js("(function(){var b=document.querySelector('#editor .blk');"
       "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:300,clientY:200}));"
       "var h=document.getElementById('blkhandle');"
       "if(h.style.display!=='flex') return 'NOHANDLE';"
       "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'ok';})()")
wait(450)
st2 = jj("window.__blkMenuState()")
check("G5 ⠿ 手柄入口：块菜单打开", r == "ok" and st2.get("show") is True, [r, st2])
check("G5 ⠿ 手柄入口与 Ctrl+/ 一致：同样默认展开标题二级（6 级）",
      st2.get("sub") is True and len(st2.get("subItems") or []) == 6, st2.get("subItems"))
check("G5 两入口菜单项一致", (st.get("items") or []) == (st2.get("items") or []),
      [st.get("items"), st2.get("items")])
close_pops()

# ---------- 收尾 ----------
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
os._exit(0)
