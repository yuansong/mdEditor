# -*- coding: utf-8 -*-
"""v3.19 冒烟测试：图片插入即渲染态+DEL删整图 / 斜杠菜单去链接+固定顺序 /
公式二级默认上标+不显示父菜单名 / 菜单顺序与默认项可配置 /
代码块外点击光标移出 / 代码块内悬浮栏仅保留删除。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke23.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


app = QApplication(sys.argv)
from mainwindow import (MainWindow, SLASH_ORDER_DEFAULT, SLASH_SUB_DEFAULTS,
                        merge_slash_order)
win = MainWindow()
win.show()


def caret_end():
    """把当前 raw-edit 光标移到内容末尾"""
    js("(function(){var el=document.querySelector('.raw-edit');if(!el)return 'x';"
       "el.focus();var r=document.createRange();r.selectNodeContents(el);r.collapse(false);"
       "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'x'})()")
    wait(150)


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


def open_slash():
    """空块中唤起斜杠菜单"""
    js("(function(){var el=document.querySelector('.raw-edit');"
       "if(!el) return 'NOEDIT';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return 'x'})()")
    wait(300)


def clear_block():
    """把当前 raw-edit 内容清空（构造真实空段，绕过 setMarkdown 首尾空块裁剪）"""
    js("(function(){var el=document.querySelector('.raw-edit');"
       "el.focus();document.execCommand('selectAll');document.execCommand('delete');return 'x'})()")
    wait(250)


def raws():
    """返回 state.raw 数组"""
    d = json.loads(js("window.__raw()") or "{}")
    return d.get("raw") or [""]


def click_blk(k):
    js(f"(function(){{var b=document.querySelectorAll('#editor .blk');"
       f"b[{k}].dispatchEvent(new MouseEvent('mousedown',{{bubbles:true,detail:1}}));return 'x'}})()")
    wait(300)


IMG = "data:image/png;base64,iVBORw0KGgo="

wait(2500)

# ---------- 前置：还原斜杠菜单默认配置（清除上次运行持久化的自定义配置） ----------
win.set_slash_menu_config(list(SLASH_ORDER_DEFAULT), "heading", dict(SLASH_SUB_DEFAULTS))
wait(400)

# ---------- 1) 图片插入：立即渲染态（<img>），不显示源码，光标进下一行 ----------
js("window.setMarkdown('')")
wait(500)
r = js(f"window.insertImageMarkdown('{IMG}', '测试图')")
wait(600)
r = js("(function(){var img=document.querySelector('#editor .blk img');"
       "return JSON.stringify({img:!!img,src:img?(img.getAttribute('src')||'').slice(0,20):'',"
       "edit:!!document.querySelector('.raw-edit'),"
       # v3.30.10：范围收敛到 #editor —— body.textContent 会把内联 <script> 文本
       # （链接校验正则里的 data:image/ 字面量）也算进去，属脚本非渲染内容
       "noRawSrc:document.getElementById('editor').textContent.indexOf('data:image')===-1,"
       "n:document.querySelectorAll('#editor .blk').length,raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
rr = d2.get("raw") or [""]
check("insert image renders as <img> immediately (no raw data-url text)",
      d.get("img") is True and d.get("src") == "data:image/png;base6"
      and d.get("noRawSrc") is True, d)
check("image caret moved to next editable line", d.get("edit") is True and d.get("n") == 2
      and rr[0].startswith("![测试图](") and rr[1] == "", (d, rr))
check("image raw kept in markdown", rr[0] == f"![测试图]({IMG})", rr)

# ---------- 2) DEL 删除整张图片 ----------
# 空段在图片上方：Backspace 删除整图
js(f"window.setMarkdown('![]({IMG})\\n\\nX')")
wait(700)
click_blk(1)          # 点击末块 X
clear_block()         # 构造空段（图片下方）
key("Backspace", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){return JSON.stringify({img:!!document.querySelector('#editor .blk img'),"
       "n:document.querySelectorAll('#editor .blk').length,raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
rr = d2.get("raw") or [""]
check("Backspace on empty line below deletes whole image",
      d.get("img") is False and len(rr) == 1 and rr[0] == "", (d, rr))

# 空段在图片上方：DEL 删除整图
js(f"window.setMarkdown('X\\n\\n![]({IMG})')")
wait(700)
click_blk(0)
clear_block()
key("Delete", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){return JSON.stringify({img:!!document.querySelector('#editor .blk img'),"
       "n:document.querySelectorAll('#editor .blk').length,raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
rr = d2.get("raw") or [""]
check("Delete on empty line above deletes whole image",
      d.get("img") is False and len(rr) == 1 and rr[0] == "", (d, rr))

# 下方图片块：DEL 不把源码并进当前块，而是删除图片
js(f"window.setMarkdown('X\\n\\n![]({IMG})')")
wait(700)
click_blk(0)          # X 块（非空）
caret_end()           # 光标移到末尾
key("Delete", sel="document.querySelector('.raw-edit')")
wait(400)
r = js("(function(){return JSON.stringify({img:!!document.querySelector('#editor .blk img'),"
       "raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
rr = d2.get("raw") or [""]
check("Delete at end of text block removes image below (no merge)",
      d.get("img") is False and rr == ["X"], (d, rr))

# ---------- 3) 斜杠菜单：去掉链接 + 顺序固定 ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
r = js("(function(){var ms=document.querySelectorAll('#slashmenu .si');var out=[];"
       "for(var k=0;k<ms.length;k++)out.push(ms[k].querySelector('.lb').textContent);"
       "var act=document.querySelector('#slashmenu .si.act .lb');"
       "return JSON.stringify({items:out,act:act?act.textContent:''})})()")
d = json.loads(r or "{}")
check("slash menu order: 标题 列表 表格 代码块 分割线 引用 图片 图表 脚注与定义 模板 公式（v3.31.3 refs 合并 + v3.32 tpl）",
      d.get("items") == ["标题", "列表", "表格", "代码块", "分割线", "引用", "图片", "图表",
                         "脚注与定义", "模板", "公式"],
      d)
check("slash menu default highlight is 标题", d.get("act") == "标题", d)
key("Escape")

# ---------- 4) 公式二级：默认选中上标，且不显示父菜单名 ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
# 自适应：按菜单里 公式 的实际下标下移，菜单项数变化后断言不会失效
_n_math = js("(function(){var m=document.getElementById('slashmenu');"
             "var lbs=[].map.call(m.querySelectorAll('.si .lb'),function(x){return x.textContent});"
             "return lbs.indexOf('公式')})()")
for _ in range(int(_n_math or 0)):
    key("ArrowDown")   # → 公式（最后一项）
key("Enter")           # 展开公式二级
wait(400)
r = js("(function(){var act=document.querySelector('#submenu .si.act .lb');"
       "return JSON.stringify({act:act?act.textContent:'',"
       "caps:document.querySelectorAll('#submenu .cap').length,"
       "show:document.getElementById('submenu').classList.contains('show')})})()")
d = json.loads(r or "{}")
check("math submenu defaults to 上标, no parent-name caption",
      d.get("act") == "上标" and d.get("caps") == 0 and d.get("show") is True, d)
key("Enter")           # 应用上标
wait(500)
r = js("(function(){var ta=document.querySelector('#editor .math-src');"
       "return JSON.stringify({ta:!!ta,val:ta?ta.value:'',katex:!!document.querySelector('#editor .mathblock .katex')})})()")
d = json.loads(r or "{}")
check("applied math template is 上标 (x^{2})", d.get("ta") is True and d.get("val") == "x^{2}"
      and d.get("katex") is True, d)

# ---------- 5) 菜单顺序 / 默认项可配置（setSlashMenuConfig） ----------
cfg = '{"order":["math","heading","list","table","code","hr","quote","image","chart"],"def":"table","sub":{"math":5}}'
js("window.setSlashMenuConfig(" + json.dumps(cfg) + ")")
wait(300)
js("window.setMarkdown('')")
wait(500)
open_slash()
r = js("(function(){var ms=document.querySelectorAll('#slashmenu .si');var out=[];"
       "for(var k=0;k<ms.length;k++)out.push(ms[k].querySelector('.lb').textContent);"
       "var act=document.querySelector('#slashmenu .si.act .lb');"
       "return JSON.stringify({first:out[0]||'',act:act?act.textContent:'',n:out.length})})()")
d = json.loads(r or "{}")
check("config: 用户顺序生效（公式首位）+ 新增项补齐，共 11 项（v3.32 tpl）",
      d.get("first") == "公式" and d.get("act") == "表格" and d.get("n") == 11, d)
for _ in range(3):
    key("ArrowUp")     # 表格 → 公式（配置顺序 math 第 1 位）
key("Enter")           # 展开公式二级（默认下标 5 → 积分）
wait(400)
r = js("(function(){var act=document.querySelector('#submenu .si.act .lb');"
       "return JSON.stringify({act:act?act.textContent:''})})()")
d = json.loads(r or "{}")
check("config: math submenu default index 5 → 积分", d.get("act") == "积分", d)
key("Escape")
js("window.setSlashMenuConfig(null)")   # 还原默认
wait(300)

# ---------- 6) Python 侧 set_slash_menu_config 持久化 + 下发 ----------
win.set_slash_menu_config(["chart", "code"], "chart", {"heading": 1, "list": 2, "chart": 6, "math": 3})
wait(400)
js("window.setMarkdown('')")
wait(500)
open_slash()
r = js("(function(){var ms=document.querySelectorAll('#slashmenu .si');var out=[];"
       "for(var k=0;k<ms.length;k++)out.push(ms[k].querySelector('.lb').textContent);"
       "return JSON.stringify({first:out[0]||'',n:out.length})})()")
d = json.loads(r or "{}")
check("python set_slash_menu_config pushed to editor (chart first, 11 items kept)",
      d.get("first") == "图表" and d.get("n") == 11, d)
saved = win._settings.value("slashMenuOrder", "")
# 用户指定的 chart 仍在首位；未指定项按默认相对位置补齐（紧邻 chart 之后）；
# v3.30.3：supsub 已移除，老配置里的 supsub 不再出现在补齐结果中
check("menu order persisted to QSettings",
      saved == "chart,refs,tpl,math,heading,list,table,code,hr,quote,image",
      repr(saved))
# 还原默认
win.set_slash_menu_config(list(SLASH_ORDER_DEFAULT), "heading", dict(SLASH_SUB_DEFAULTS))
wait(300)

# ---------- 7) 代码块外点击：光标移出到最新可编辑位置 ----------
js("window.setMarkdown('')")
wait(500)
open_slash()
for _ in range(3):
    key("ArrowDown")   # → 代码块
key("Enter")
wait(400)
key("Enter", sel="document.getElementById('lang-q')")   # 确认语言，进代码区
wait(400)
r = js("(function(){var code=document.querySelector('.codeblock code');"
       "return JSON.stringify({inCode:document.activeElement===code})})()")
d = json.loads(r or "{}")
check("after insert cursor is in code area", d.get("inCode") is True, d)
# 点击编辑区空白（非块区域）
js("(function(){var ed=document.getElementById('editor');"
   "ed.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(400)
r = js("(function(){var code=document.querySelector('.codeblock code');"
       "return JSON.stringify({inCode:document.activeElement===code,"
       "edit:!!document.querySelector('.raw-edit'),"
       "n:document.querySelectorAll('#editor .blk').length,"
       "lastEmpty:(function(){var b=document.querySelectorAll('#editor .blk');"
       "return b[b.length-1].classList.contains('raw-edit')})()})})()")
d = json.loads(r or "{}")
check("clicking blank moves caret out of code block to latest editable spot",
      d.get("inCode") is False and d.get("edit") is True and d.get("lastEmpty") is True, d)

# 代码块是末块时点击空白：追加空段进入（不再跳回代码块）
js("window.setMarkdown('```c\\nhi\\n```')")
wait(700)
js("(function(){var ed=document.getElementById('editor');"
   "ed.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(400)
r = js("(function(){var code=document.querySelector('.codeblock code');"
       "return JSON.stringify({inCode:document.activeElement===code,"
       "edit:!!document.querySelector('.raw-edit'),"
       "n:document.querySelectorAll('#editor .blk').length})})()")
d = json.loads(r or "{}")
check("blank click with fence as last block appends editable empty block",
      d.get("inCode") is False and d.get("edit") is True and d.get("n") == 2, d)

# ---------- 8) 代码块内选中文本：悬浮栏仅保留删除，点击删除整块 ----------
js("window.setMarkdown('```c\\nhi\\n```')")
wait(700)
js("(function(){var code=document.querySelector('.codeblock code');"
   "var r=document.createRange();r.selectNodeContents(code);"
   "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'x'})()")
wait(600)   # selectionchange 160ms 定时器
r = js("(function(){var fb=document.getElementById('floatbar');"
       "var btns=fb.querySelectorAll('button');"
       "return JSON.stringify({show:fb.classList.contains('show'),n:btns.length,"
       "title:btns.length?btns[0].title:''})})()")
d = json.loads(r or "{}")
check("floatbar in code block shows only delete button",
      d.get("show") is True and d.get("n") == 1 and "删除" in (d.get("title") or ""), d)
js("(function(){var fb=document.getElementById('floatbar');"
   "var b=fb.querySelector('button');if(b)b.click();return 'x'})()")
wait(500)
r = js("(function(){return JSON.stringify({code:!!document.querySelector('#editor .codeblock'),"
       "n:document.querySelectorAll('#editor .blk').length,raw:window.__raw()})})()")
d = json.loads(r or "{}")
d2 = json.loads(d.get("raw") or "{}")
rr = d2.get("raw") or [""]
check("floatbar delete button removes whole code block",
      d.get("code") is False and rr == [""], (d, rr))

# 正文选区：悬浮栏仍是完整格式按钮
js("window.setMarkdown('hello world')")
wait(700)
click_blk(0)
wait(300)
js("(function(){var el=document.querySelector('.raw-edit')||document.querySelector('#editor .blk');"
   "var r=document.createRange();r.selectNodeContents(el);"
   "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'x'})()")
wait(600)
r = js("(function(){var fb=document.getElementById('floatbar');"
       "return JSON.stringify({show:fb.classList.contains('show'),"
       "n:fb.querySelectorAll('button').length})})()")
d = json.loads(r or "{}")
check("normal text selection keeps full floatbar", d.get("show") is True and d.get("n") >= 6, d)

# ---------- 9) 菜单顺序合并 merge_slash_order：老配置升级不丢项、不打乱用户排序 ----------
# v3.30.3：supsub 已从默认顺序移除；v3.31.3：footnote/deflist 合并为 refs，
# 老配置里的 footnote/deflist 被过滤，9 项老配置补齐为 10 项
_old10 = [x for x in SLASH_ORDER_DEFAULT if x not in ("refs", "tpl")]
check("merge: 老版 10 项顺序升级后 == 当前 11 项默认顺序",
      merge_slash_order(_old10) == list(SLASH_ORDER_DEFAULT), merge_slash_order(_old10))
check("merge: 从未保存过（空）== 当前默认顺序",
      merge_slash_order([]) == list(SLASH_ORDER_DEFAULT), "")
check("merge: 传完整默认顺序幂等",
      merge_slash_order(list(SLASH_ORDER_DEFAULT)) == list(SLASH_ORDER_DEFAULT), "")
check("merge: 老配置含 supsub 被过滤（不复活已移除项）",
      "supsub" not in merge_slash_order(["supsub"] + list(SLASH_ORDER_DEFAULT)),
      merge_slash_order(["supsub"] + list(SLASH_ORDER_DEFAULT)))
check("merge: 老配置含 footnote/deflist 被过滤（合并为 refs 不重复）",
      "footnote" not in merge_slash_order(["footnote", "deflist"] + list(SLASH_ORDER_DEFAULT))
      and "deflist" not in merge_slash_order(["footnote", "deflist"] + list(SLASH_ORDER_DEFAULT)),
      merge_slash_order(["footnote", "deflist"] + list(SLASH_ORDER_DEFAULT)))
_mf = merge_slash_order(["math", "heading", "list", "table", "code", "hr", "quote",
                         "image", "chart"])
check("merge: 用户拖到首位的 公式 仍是第一项，且补齐为 11 项无重复",
      _mf[0] == "math" and len(_mf) == 11 and len(set(_mf)) == 11, _mf)
check("merge: 公式仍固定在最后", merge_slash_order(_old10)[-1] == "math",
      merge_slash_order(_old10))

# ---------- 收尾 ----------
flush()
os._exit(0)
