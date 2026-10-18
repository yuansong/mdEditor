# -*- coding: utf-8 -*-
"""v3.25 冒烟测试：
1) 代码块行号 + 代码风格（设置默认 / 代码栏「风格」按钮 / 轻量语法着色）；
2) 浮动工具栏新增高亮按钮（==xx==）；
3) 图片悬浮按钮重构：重命名 / 存储方式切换 / 无删除按钮 + DEL 键删除；
4) 图片块右键上移 / 下移保持渲染态（不再显示 <figure> 源码）；
5) 图注弹层输入 Backspace 不再误删整个图表；DEL（无输入焦点）仍可删图表；
6) 脚注 / 定义列表提示菜单（键入 [^ 或 : 触发，交互同 / 菜单）+ 脚注定义保持渲染态；
7) 插入图片编号命名（_numbered_asset_name）；8) 命令面板停靠顶端 + 输入才下拉。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke29.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")


app = QApplication(sys.argv)
# v3.29：代码块行号 / 风格被上次运行残留会污染「默认显示行号」断言（QSettings 跨运行持久化）
from PySide6.QtCore import QSettings as _QS
_q = _QS("WorkBuddy", "WorkBuddyMarkdown")
_q.setValue("codeLang", "C")
_q.setValue("codeLineNum", True)
_q.setValue("codeStyle", "classic")
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


def ctxmenu(sel, x, y):
    js("(function(){var e=document.querySelector('" + sel + "');"
       "var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
       "clientX:" + str(x) + ",clientY:" + str(y) + "});"
       "e.dispatchEvent(ev);return 'x'})()")


def click_act(menu_sel, act):
    js("(function(){var m=document.querySelector('" + menu_sel + "');"
       "var t=m.querySelector('[data-act=\\\"" + act + "\\\"]');"
       "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
       "t.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'})()")


def key(sel, k):
    return js("(function(){var e=document.querySelector('" + sel + "');"
              "e.dispatchEvent(new KeyboardEvent('keydown',{key:'" + k + "',"
              "bubbles:true,cancelable:true}));return 'ok'})()")


wait(2500)  # 等待编辑视图加载

# ==================== 1) 代码块行号 + 风格 ====================
js("window.setMarkdown('```js\\nvar a = 1; // hi\\n```')")
wait(700)
r1 = jj("(function(){var g=document.querySelector('#editor .codeblock .gutter');"
        "var sb=document.querySelector('#editor .codebar .style-btn');"
        "var code=document.querySelector('#editor .codeblock code');"
        "return JSON.stringify({gutter:!!g,nums:g?g.textContent.trim():'',"
        "styleBtn:!!sb,kw:code.innerHTML.indexOf('tk-kw')>=0,"
        "cmt:code.innerHTML.indexOf('tk-cmt')>=0})})()")
check("代码块默认显示行号（gutter 含 1/2）", r1.get("gutter") and "1" in r1.get("nums", ""), r1)
check("代码栏有「风格」按钮", r1.get("styleBtn") is True, r1)
check("轻量语法着色：var 高亮 / 注释识别", r1.get("kw") and r1.get("cmt"), r1)
js("window.setCodePrefs({lnum:false, style:'dark'})")
wait(500)
r1b = jj("(function(){var blk=document.querySelector('#editor .codeblock');"
         "return JSON.stringify({gutter:!!document.querySelector('#editor .codeblock .gutter'),"
         "dark:blk.className.indexOf('st-dark')>=0})})()")
check("setCodePrefs：关行号 + 深色风格生效", r1b.get("gutter") is False and r1b.get("dark") is True, r1b)
js("window.setCodePrefs({lnum:true, style:'classic'})")
wait(400)
# 风格按钮弹出选择并切换当前块
js("(function(){var b=document.querySelector('#editor .codebar .style-btn');"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r1c = jj("(function(){var items=[].map.call(document.querySelectorAll('#stylepop .si'),"
         "function(x){return x.getAttribute('data-st')});"
         "return JSON.stringify({show:document.getElementById('stylepop')"
         ".classList.contains('show'),items:items})})()")
check("「风格」按钮弹出 4 种风格", r1c.get("show") is True and
      r1c.get("items") == ["classic", "dark", "eye", "mini"], r1c)
js("(function(){var it=document.querySelector('#stylepop [data-st=\\\"eye\\\"]');"
   "it.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'x'})()")
wait(300)
r1d = jj("(function(){return JSON.stringify({eye:document.querySelector('#editor .codeblock')"
         ".className.indexOf('st-eye')>=0})})()")
check("选择「护眼」→ 当前块风格切换", r1d.get("eye") is True, r1d)

# ==================== 2) 浮动工具栏高亮按钮 ====================
js("window.setMarkdown('你好世界')")
wait(600)
r2 = js("(function(){var blk=document.querySelector('#editor .blk p');"
        "blk.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
        "blk.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true}));"
        "var fb=document.getElementById('floatbar');"
        "var labels=[].map.call(fb.querySelectorAll('button'),function(x){return x.title});"
        "return JSON.stringify({labels:labels})})()")
wait(300)
check("浮动工具栏含「高亮」按钮", "高亮" in json.loads(r2 or "{}").get("labels", []), r2)
r2b = js("(function(){var el=document.querySelector('#editor .raw-edit')||"
         "document.querySelector('#editor .blk p');"
         "if(!el) return 'NOEL';"
         "var t=el.firstChild;var sel=getSelection();var rg=document.createRange();"
         "rg.setStart(t,2);rg.setEnd(t,4);sel.removeAllRanges();sel.addRange(rg);"
         "return window.__applyFloat('mark')})()")
wait(400)
rw = raw()
check("高亮动作写回 ==世界==", len(rw) > 0 and "==世界==" in rw[0], rw[:1])

# ==================== 3) 图片右键菜单（v3.30.17：操作收进右键，悬浮按钮条移除） ====================
# v3.29c：存储类菜单项依赖 __docDir（文档已保存）。此前靠 QSettings 会话残留，
# 环境相关不可靠 → 显式 setDocDir，本节结束再清空
js("window.setDocDir('C:/Users/Administrator/AppData/Local/Temp/mded29_fakedoc')")
IMG = "![图](测试.assets/00001_图.png)\n\n尾段"
js(f"window.setMarkdown({json.dumps(IMG)})")
wait(700)


def img_menu_act(act):
    """右键图片弹出菜单后点指定 data-act 项（v3.30.17）"""
    return js("(function(){var img=document.querySelector('#editor .blk img');"
              "if(!img)return 'noimg';"
              "var r=img.getBoundingClientRect();"
              "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
              "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));"
              "var ms=document.querySelectorAll('#blkmenu .mi');"
              "for(var i=0;i<ms.length;i++){"
              "if(ms[i].getAttribute('data-act')==='" + act + "')"
              "{ms[i].dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'}}"
              "return 'noact'})()")


r3 = js("(function(){var img=document.querySelector('#editor .blk img');"
        "var r=img.getBoundingClientRect();"
        "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
        "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));"
        "return JSON.stringify({sel:JSON.parse(window.__objSel()),"
        "acts:[].map.call(document.querySelectorAll('#blkmenu .mi'),"
        "function(x){return x.getAttribute('data-act')})})})()")
wait(300)
d3 = json.loads(r3 or "{}")
check("相对路径图右键菜单 = 对齐动态两项/重置尺寸/大小设置/转内嵌/改名/替换/显示/裁剪/图注/复制图片/上移/下移/删除（v3.39.5 MENU-4 + v3.39.6 裁剪）",
      d3.get("sel", {}).get("kind") == "img" and d3.get("acts") ==
      ["imgalign:l", "imgalign:r", "imgreset", "imgsize", "imgmode", "imgrename", "imgreplace", "viewimg", "imgcrop", "edit", "copyimg", "dup", "up", "down", "del"], r3)
# 修改图片名称弹层 → 请求通道
r3b = img_menu_act("imgrename")
wait(300)
r3c = js("(function(){var rp=document.getElementById('renpop');"
         "if(!rp.classList.contains('show')) return 'NOP';"
         "document.getElementById('ren-input').value='00001_新名';"
         "document.getElementById('ren-ok').dispatchEvent("
         "new MouseEvent('click',{bubbles:true}));"
         "return window.collect()})()")
try:
    c3 = json.loads(r3c or "{}")
except Exception:
    c3 = {}
req = c3.get("req") or {}
check("重命名请求经 collect 上报（act/name 正确）",
      req.get("act") == "imgRename" and req.get("name") == "00001_新名"
      and "测试.assets/00001_图.png" in str(req.get("src")), req)
# 存储方式切换（相对路径 → 转化为内嵌式存储 → imgToEmbed）
# 注意：点击与读 __req 必须同一次 js() 完成 —— 中间进事件循环会被 _poll 抢先取走 __req
r3d = js("(function(){var img=document.querySelector('#editor .blk img');"
         "if(!img)return 'noimg';"
         "var r=img.getBoundingClientRect();"
         "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
         "clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));"
         "var ms=document.querySelectorAll('#blkmenu .mi');"
         "for(var i=0;i<ms.length;i++){"
         "if(ms[i].getAttribute('data-act')==='imgmode')"
         "{ms[i].dispatchEvent(new MouseEvent('click',{bubbles:true}));"
         "var q=window.__req;return JSON.stringify({clicked:1,act:q?q.act:null})}}"
         "return 'noact'})()")
wait(300)
try:
    c3d = json.loads(r3d or "{}")
except Exception:
    c3d = {}
check("存储方式切换请求（相对路径 → imgToEmbed）",
      c3d.get("clicked") == 1 and c3d.get("act") == "imgToEmbed", r3d)
js("window.setDocDir('')")   # 还原：后续章节回到未保存态
# DEL 删除整块（无输入焦点时）
n_before = len(raw())
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',"
   "{key:'Delete',bubbles:true,cancelable:true}));return 'x'})()")
wait(400)
check("图片选中按 DEL → 整块删除", len(raw()) == n_before - 1, [n_before, len(raw())])

# ==================== 4) 图片块右键上移保持渲染态 ====================
DOC4 = "第一段\n\n![图](测试.assets/00002_图2.png)\n\n第三段"
js(f"window.setMarkdown({json.dumps(DOC4)})")
wait(700)
ctxmenu("#editor .blk img", 10, 10)
wait(300)
st4 = jj("window.__blkMenuState()")
check("图片右键菜单（未保存文档，存储项置灰）= 对齐动态两项/重置尺寸/大小设置/转存置灰/替换/显示/裁剪/图注/复制图片/上移/下移/删除（v3.39.5 MENU-4 + v3.39.6 裁剪）",
      st4.get("items") == ["imgalign:l", "imgalign:r", "imgreset", "imgsize", "imgstorewait", "imgreplace", "viewimg", "imgcrop", "edit", "copyimg", "dup", "up", "down", "del"], st4.get("items"))
click_act("#blkmenu", "up")
wait(500)
rw4 = raw()
r4 = jj("(function(){return JSON.stringify({rawEdit:!!document.querySelector('#editor .raw-edit'),"
        "fig:document.querySelector('#editor .blk img')!==null})})()")
check("图片上移后保持渲染态（无源码态、图片仍渲染）",
      rw4[0].startswith("![图]") and r4.get("rawEdit") is False and r4.get("fig") is True,
      [rw4[:1], r4])

# ==================== 5) 图注弹层 Backspace 不误删图表 ====================
MMD = "```mermaid\\nflowchart TD\\n  A[开始] --> B[结束]\\n```"
js(f"window.setMarkdown({json.dumps(MMD)})")
wait(1500)
r5 = js("(function(){var blk=document.querySelector('#editor .blk');"
        "var mmb=blk.querySelector('.mermaidblock');"
        "mmb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
        "clientX:5,clientY:5}));return 'x'})()")
wait(300)
# 打开图表源码框（建立 mmdCtx），再经悬浮「图注」按钮打开图注弹层并聚焦输入框
r5b = js("window.__mmdHooks.open(0)")
wait(300)
r5c = js("(function(){window.__mmdHooks.cap(0);"
         "var inp=document.getElementById('cap-input');"
         "inp.focus();"
         "return JSON.stringify({focused:document.activeElement===inp,"
         "raw:JSON.parse(window.__raw()).raw.length})})()")
wait(300)
d5 = json.loads(r5c or "{}")
check("前置：图注输入框已聚焦", d5.get("focused") is True, r5c)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',"
   "{key:'Backspace',bubbles:true,cancelable:true}));return 'x'})()")
wait(400)
rw5 = raw()
check("图注输入框按 Backspace → 图表未被删除",
      any("mermaid" in b for b in rw5), [len(rw5), rw5[:1]])
# 焦点不在输入框：DEL 仍删除整个图表
js("(function(){document.activeElement.blur();"
   "document.dispatchEvent(new KeyboardEvent('keydown',"
   "{key:'Delete',bubbles:true,cancelable:true}));return 'x'})()")
wait(400)
rw5b = raw()
check("图表选中（无输入焦点）DEL → 正常删除", not any("mermaid" in b for b in rw5b), rw5b[:2])

# ==================== 6) 脚注 / 定义列表提示菜单 ====================
js("window.setMarkdown('')")
wait(600)
# 6a) 空块进入编辑 → 键入 ':' → 定义列表提示
js("(function(){var blk=document.querySelector('#editor .blk');"
   "blk.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(400)
key("#editor .raw-edit", ":")
wait(300)
r6 = jj("(function(){var sm=document.getElementById('slashmenu');"
        "var lbs=[].map.call(sm.querySelectorAll('.si .lb'),function(x){return x.textContent});"
        "return JSON.stringify({show:sm.classList.contains('show'),lbs:lbs})})()")
check("空块键入 : → 定义列表提示", r6.get("show") is True and "定义列表" in r6.get("lbs", []), r6)
key("#editor .raw-edit", "Enter")
wait(500)
rw6 = raw()
check("回车应用 → 定义列表模板", any("术语" in b for b in rw6), rw6[:1])
# 6b) 键入 [^ → 脚注提示（先把 [^ 写进块并落光标）
js("window.setMarkdown('')")
wait(600)
js("(function(){var blk=document.querySelector('#editor .blk');"
   "blk.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
   "return 'x'})()")
wait(400)
r6b = js("(function(){var el=document.querySelector('#editor .raw-edit');"
         "el.textContent='[^';"
         "var rg=document.createRange();rg.selectNodeContents(el);rg.collapse(false);"
         "var sel=getSelection();sel.removeAllRanges();sel.addRange(rg);return 'ok'})()")
key("#editor .raw-edit", "^")
wait(300)
r6c = jj("(function(){var sm=document.getElementById('slashmenu');"
         "var lbs=[].map.call(sm.querySelectorAll('.si .lb'),function(x){return x.textContent});"
         "return JSON.stringify({show:sm.classList.contains('show'),lbs:lbs})})()")
check("键入 [^ → 脚注引用/定义提示", r6c.get("show") is True and
      r6c.get("lbs") == ["脚注引用", "脚注定义"], r6c)
key("#editor .raw-edit", "Enter")
wait(600)
rw6b = raw()
check("回车应用 → 引用 [^1] 写入 + 定义块自动补",
      any("[^1]" in b for b in rw6b) and any(b.startswith("[^1]:") for b in rw6b), rw6b)
# 6c) 脚注定义块保持渲染态：编辑块应为引用块
r6d = jj("(function(){var d=JSON.parse(window.__raw());"
         "var edit=document.querySelector('#editor .raw-edit');"
         "var editBlk=edit?edit.closest('.blk'):null;"
         "var idx=-1;if(editBlk){for(var i=0;i<editBlk.parentNode.children.length;i++)"
         "if(editBlk.parentNode.children[i]===editBlk){idx=i;break}}"
         "return JSON.stringify({editIdx:d.editIdx,blkIdx:idx,"
         "lastIsFndef:/\\[\\^1\\]:/.test(d.raw[d.raw.length-1])})})()")
check("脚注引用块保持编辑、定义块保持渲染态",
      r6d.get("editIdx") == 0 and r6d.get("blkIdx") == 0 and r6d.get("lastIsFndef") is True, r6d)

# ==================== 7) 插入图片编号命名 ====================
import tempfile
tmp = tempfile.mkdtemp(prefix="mded29_")
doc = os.path.join(tmp, "笔记.md")
open(doc, "w", encoding="utf-8").write("# t\n")
assets = os.path.join(tmp, "笔记.assets")
os.makedirs(assets, exist_ok=True)
for i in range(10):
    open(os.path.join(assets, f"old{i}.png"), "w").write("x")
win.file_path = doc
nm = win._numbered_asset_name("我的图片", ".png")
check("默认存储名 = 00011_我的图片.png（现有 10 个文件）", nm == "00011_我的图片.png", nm)
nm2 = win._numbered_asset_name("图", ".jpg")
check("扩展名跟随源文件（00011_图.jpg，编号仍为 11）", nm2 == "00011_图.jpg", nm2)
win.file_path = None

# ==================== 8) 命令面板停靠顶端 + 输入才下拉 ====================
win.show_command_palette()
wait(500)
dlg = win._cmd_dlg
check("命令面板可见", dlg.isVisible(), dlg.isVisible())
menu_h = win.menuBar().height()
expected_y = win.geometry().y() + menu_h + 10
check("面板停靠在菜单栏下方顶端", abs(dlg.y() - expected_y) <= 2,
      [dlg.y(), expected_y])
check("未输入时不显示候选列表", not dlg.listw.isVisible(), dlg.listw.isVisible())
dlg.edit.setText("折叠")
wait(300)
check("输入后下拉显示候选", dlg.listw.isVisible() and dlg.listw.count() > 0,
      [dlg.listw.count()])
dlg.edit.setText("zz")
dlg.edit.setText("zd")   # 拼音首字母匹配「折叠全部标题」（zdqbt）
wait(300)
lbls = [dlg.listw.item(i).text() for i in range(dlg.listw.count())]
check("拼音首字母可匹配命令（zd → 折叠全部标题）",
      any("折叠全部标题" in t for t in lbls), lbls[:5])
dlg.close()
wait(200)

# ==================== 汇总 ====================
fails = [r for r in results if r.startswith("FAIL")]
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results) + f"\n\nSUMMARY: {len(results) - len(fails)}/{len(results)} passed\n")
print(f"SMOKE29: {len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
