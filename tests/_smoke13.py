# -*- coding: utf-8 -*-
"""v3.6 测试：行菜单点击修复 / 斜杠菜单修复与二级菜单 / 占位提示 / 标题7 / 公式模板。"""
import json
import sys

sys.path.insert(0, r"E:\WorkBuddy\md-editor\src")
import os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke13.txt")

results = []

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

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

    QTimer.singleShot(10000, loop.quit)  # 超时保护
    win._js_active(code, cb)
    loop.exec()
    return box.get("r")


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def check(name, cond, detail=""):
    results.append(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))


def open_slash(max_try=3):
    """打开斜杠菜单：Esc 清理 -> 派发空块 mousedown + '/' 键 -> 轮询直到菜单真正展开。

    直接派发 '/' 后立刻操作菜单会偶发失败（编辑器还没渲染出空块），
    这里轮询 #slashmenu.show 直到就绪，避免时序抖动导致的假 FAIL。
    """
    for _ in range(max_try):
        js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
           "var el=document.querySelector('#editor .blk');if(!el) return 'NOBLK';"
           "el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
           "var t=document.querySelector('#editor .raw-edit')||el;"
           "t.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true}));return 't'})()")
        wait(400)
        if js("document.getElementById('slashmenu').classList.contains('show')") is True:
            return True
    return False


wait(6000)

# ---------- 1) 占位提示（样式挂在空块 .blk 的 ::before 上，v3.13 起不再用 .blk.ph） ----------
js("window.setMarkdown('')")
wait(800)
r = js("(function(){var p=document.querySelector('#editor .blk');"
       "if(!p) return 'NO_BLK';"
       "return getComputedStyle(p,'::before').content})()")
check("placeholder shows on empty doc", isinstance(r, str) and "输入" in r, r)
js("window.setMarkdown('有内容了')")
wait(800)
r = js("(function(){var p=document.querySelector('#editor .blk');"
       "if(!p) return 'NO_BLK';"
       "return getComputedStyle(p,'::before').content})()")
check("placeholder hidden when content", not (isinstance(r, str) and "输入" in r), r)

# ---------- 2) 斜杠菜单：打开 + 防误关 ----------
js("window.setMarkdown('')")
wait(800)
check("斜杠菜单已打开", open_slash() is True, "")
r = js("(function(){var m=document.getElementById('slashmenu');"
       "return JSON.stringify({show:m.classList.contains('show'),items:m.querySelectorAll('.si').length,"
       "subs:m.querySelectorAll('.has-sub').length})})()")
d = json.loads(r or "{}")
# v3.30.3 一级菜单 12 → 11 项（按需求移除 上标/下标），带二级的项 6 → 5
check("slash opens with 11 top items", d.get("show") is True and d.get("items") == 11, d)
check("slash has 5 submenus (标题/列表/图表/公式/脚注)", d.get("subs") == 5, d)
# 修饰键不关闭
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Shift',bubbles:true}));return 's'})()")
wait(200)
r = js("document.getElementById('slashmenu').classList.contains('show')")
check("menu survives Shift key", r is True, r)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Control',bubbles:true}));return 'c'})()")
wait(200)
r = js("document.getElementById('slashmenu').classList.contains('show')")
check("menu survives Ctrl key", r is True, r)
# 过滤公式 -> 只剩公式父项
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'公',bubbles:true}));return 'f'})()")
wait(200)
r = js("(function(){return document.querySelectorAll('#slashmenu .si').length})()")
check("filter 公式 keeps parent", r == 1, r)
# 回车展开二级
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return 'e'})()")
wait(400)
r = js("(function(){var s=document.getElementById('submenu');"
       "return JSON.stringify({show:s.classList.contains('show'),items:s.querySelectorAll('.si').length,"
       "cap:(s.querySelector('.cap')||{}).textContent||''})})()")
d = json.loads(r or "{}")
check("公式 submenu opens (26 templates)", d.get("show") is True and d.get("items") == 26, d)
# v3.19：斜杠菜单二级不再显示父菜单名，cap 为空
check("公式 submenu 不显示父菜单名", (d.get("cap") or "") == "", d.get("cap"))
# v3.19：公式二级默认改为首项「上标」（旧版为中间项索引 13）
r = js("(function(){var s=document.getElementById('submenu');"
       "return [].indexOf.call(s.querySelectorAll('.si'),s.querySelector('.si.act'))})()")
check("公式 submenu default 上标（索引 0）", r == 0, r)
# 二级中选「向量」（索引 9）
js("(function(){var s=document.getElementById('submenu');"
   "var c=s.querySelector('.si[data-k=\"9\"]');"
   "c.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'p'})()")
wait(500)
r = js("window.getMarkdown()")
# v3.18：公式模板由行内 $...$ 改为插入 ```math 块
check("vector formula inserted", "\\vec{a}" in (r or "") and (r or "").startswith("```math"), (r or "")[:60])
r = js("(function(){return JSON.stringify({sm:document.getElementById('slashmenu').classList.contains('show'),"
       "sub:document.getElementById('submenu').classList.contains('show')})})()")
d = json.loads(r or "{}")
check("menus closed after formula apply", d.get("sm") is False and d.get("sub") is False, d)

# ---------- 3) 斜杠菜单：标题二级（点击路径） ----------
js("window.setMarkdown('')")
wait(800)
check("标题二级：斜杠菜单已打开", open_slash() is True, "")
# 单击「标题」父项 -> 二级展开 7 项
js("(function(){var m=document.getElementById('slashmenu');"
   "var t=m.querySelectorAll('.si')[0];"
   "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'c'})()")
wait(400)
r = js("(function(){var s=document.getElementById('submenu');"
       "return JSON.stringify({show:s.classList.contains('show'),items:s.querySelectorAll('.si').length,"
       "last:(s.querySelector('.si:last-child .lb')||{}).textContent||''})})()")
d = json.loads(r or "{}")
check("标题 submenu 7 levels", d.get("show") is True and d.get("items") == 7 and d.get("last") == "标题 7", d)
# 点二级第 3 项（标题 3）
js("(function(){var s=document.getElementById('submenu');"
   "var c=s.querySelector('.si[data-k=\"2\"]');"
   "c.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'p'})()")
wait(500)
r = js("window.getMarkdown()")
check("apply 标题3 via submenu", (r or "").startswith("### "), (r or "")[:30])

# ---------- 4) 标题 7 全链路 ----------
js("window.setMarkdown('####### 七级标题内容')")
wait(800)
r = js("(function(){var b=document.querySelector('.blk');"
       "return JSON.stringify({cls:b.className,tag:b.querySelector('h1,h2,h3,h4,h5,h6')?"
       "b.querySelector('h1,h2,h3,h4,h5,h6').tagName:''})})()")
d = json.loads(r or "{}")
check("h7 block type", "b-h7" in (d.get("cls") or ""), d)
r = js("window.__core.blockInfo('####### t').type")
check("blockInfo h7", r == "h7", r)
r = js("window.getMarkdown()")
check("h7 roundtrip", (r or "").startswith("####### 七级"), (r or "")[:40])

# ---------- 5) 块菜单二级（标题 -> 标题7，默认选中标题3） ----------
js("window.setMarkdown('普通段落文字')")
wait(800)
js("(function(){var b=document.querySelector('.blk');"
   "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:100,clientY:100}));"
   "document.getElementById('blkhandle').dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'h'})()")
wait(300)
js("(function(){var m=document.getElementById('blkmenu');"
   "var t=m.querySelector('[data-act=\"to-h\"]');"
   "t.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return 's'})()")
wait(400)
r = js("(function(){var s=document.getElementById('submenu');"
       "var act=s.querySelector('.si.act');"
       "return JSON.stringify({show:s.classList.contains('show'),items:s.querySelectorAll('.si').length,"
       "def:act?act.textContent:''})})()")
d = json.loads(r or "{}")
check("block 标题 submenu 7 items", d.get("show") is True and d.get("items") == 7, d)
check("标题 submenu default 标题3", "标题 3" in (d.get("def") or ""), d)
js("(function(){var s=document.getElementById('submenu');"
   "var c=s.querySelector('.si[data-k=\"6\"]');"  # 标题 7 索引 6
   "c.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'p'})()")
wait(500)
r = js("window.getMarkdown()")
check("transform to 标题7", (r or "").startswith("####### 普通段落"), (r or "")[:40])

# ---------- 5b) 块菜单「列表」子菜单（默认有序） + 空块唤起斜杠菜单 ----------
js("window.setMarkdown('普通段落文字')")
wait(800)
js("(function(){var b=document.querySelector('.blk');"
   "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:100,clientY:100}));"
   "document.getElementById('blkhandle').dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'h'})()")
wait(300)
js("(function(){var m=document.getElementById('blkmenu');"
   "var t=m.querySelector('[data-act=\"to-list\"]');"
   "t.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return 's'})()")
wait(400)
r = js("(function(){var s=document.getElementById('submenu');"
       "var act=s.querySelector('.si.act');"
       "return JSON.stringify({show:s.classList.contains('show'),items:s.querySelectorAll('.si').length,"
       "def:act?act.textContent:''})})()")
d = json.loads(r or "{}")
check("列表 submenu 3 items", d.get("show") is True and d.get("items") == 3, d)
check("列表 submenu default 有序", "有序" in (d.get("def") or ""), d)
js("(function(){var s=document.getElementById('submenu');"
   "var c=s.querySelector('.si[data-k=\"1\"]');"  # 有序列表
   "c.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'p'})()")
wait(500)
r = js("window.getMarkdown()")
check("transform to 有序列表", (r or "").startswith("1. 普通段落"), (r or "")[:40])
# 空块：块菜单直接唤起斜杠菜单
js("window.setMarkdown('')")
wait(600)
r = js("(function(){var b=document.querySelector('.blk');"
   "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:100,clientY:100}));"
   "document.getElementById('blkhandle').dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "return JSON.stringify({slash:document.getElementById('slashmenu').classList.contains('show'),"
   "blk:document.getElementById('blkmenu').classList.contains('show')})})()")
d = json.loads(r or "{}")
check("empty block opens slash menu", d.get("slash") is True and d.get("blk") is False, d)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 'e'})()")
# Ctrl+/ 唤起块菜单（有内容块）
js("window.setMarkdown('一段文字')")
wait(600)
r = js("(function(){window.openBlockMenu();"
       "return JSON.stringify({blk:document.getElementById('blkmenu').classList.contains('show')})})()")
d = json.loads(r or "{}")
check("openBlockMenu works", d.get("blk") is True, d)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 'e'})()")

# ---------- 6) 行编辑菜单：选区塌陷后点击仍生效 ----------
js("window.setMarkdown('这是一段可以被加粗的文字')")
wait(800)
js("""
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
# 模拟浏览器在点击瞬间塌陷选区：清空选区后直接点按钮
js("(function(){getSelection().removeAllRanges();return 'collapse'})()")
wait(100)
js("(function(){var fb=document.getElementById('floatbar');"
   "var b=fb.querySelector('button');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'b'})()")
wait(400)
r = js("window.getMarkdown()")
check("floatbar works with collapsed selection", "**可以被加粗**" in (r or ""), (r or "")[:40])
# 正常选区点击（回归）：重置文档后再选取（上一例结束后块处于编辑态，无 <p>）
js("window.setMarkdown('正常路径的斜体测试')")
wait(800)
js("(function(){var p=document.querySelector('.blk p');var tn=p.firstChild;"
   "var sel=getSelection();var range=document.createRange();"
   "range.setStart(tn,0);range.setEnd(tn,4);"
   "sel.removeAllRanges();sel.addRange(range);"
   "document.dispatchEvent(new Event('selectionchange'));return 'sel2'})()")
wait(500)
js("(function(){var fb=document.getElementById('floatbar');"
   "var b=fb.querySelectorAll('button')[1];"  # 斜体
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'i'})()")
wait(400)
r = js("window.getMarkdown()")
check("floatbar italic normal path", (r or "").startswith("*正常路径*"), (r or "")[:60])

# 公式块渲染回归
js("window.setMarkdown('```math\\nx^2 + y^2 = z^2\\n```')")
wait(1200)
r = js("document.querySelectorAll('.mathblock .katex').length")
check("math block still renders", r == 1, r)

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
import os
os._exit(0)  # 强制退出，避免未保存弹窗阻塞测试进程
