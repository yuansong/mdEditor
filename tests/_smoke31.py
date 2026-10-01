# -*- coding: utf-8 -*-
"""v3.30.19 冒烟测试：本批新特性回归（清单遗留项批次）。

覆盖：MATH-6（$$ 块级公式识别渲染 + 存储保留）、CODE-4（st= 风格持久化）、
CODE-5（首行属性 + 尾空行）、CODE-6（选区 Tab 批量缩进）、QUO-3/4（退格退级 /
多行批量缩进）、FN-3/4/5（跳转高亮 / 重排 / 清理）、DL-3/4（Tab 新增定义 /
空定义往返）、IMG-5/6/7（对齐 / 菜单项 / 精确尺寸）、MMD-7（图表主题 API）、
U1（非空块行首 / 触发）、U2（斜杠菜单滚动重锚定）。
输出：tests/_smoke31.txt
"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke31.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
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


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(400)


def raw():
    return json.loads(js("window.__raw()") or "{}").get("raw") or []


wait(3000)
js("window.setSlashMenuConfig(null)")

# ---------- MATH-6：$$ 块级公式 ----------
setmd("$$E=mc^2$$")
r = js("(function(){var m=document.querySelector('#editor .mathblock');"
       "return JSON.stringify({has:!!m,tex:m?m.getAttribute('data-tex'):null});})()")
d = json.loads(r or "{}")
check("MATH-6 单行 $$ 渲染为 mathblock", d.get("has") is True, r)
check("MATH-6 单行 data-tex=E=mc^2", d.get("tex") == "E=mc^2", r)

setmd("$$\nx^2 + y^2 = z^2\n$$")
r = js("(function(){var m=document.querySelector('#editor .mathblock');"
       "return JSON.stringify({has:!!m,tex:m?m.getAttribute('data-tex'):null});})()")
d = json.loads(r or "{}")
check("MATH-6 多行 $$ 渲染", d.get("has") is True and d.get("tex") == "x^2 + y^2 = z^2", r)
check("MATH-6 存储保留 $$ 原语法", "$$" in "\n".join(raw()), str(raw())[:80])

# ---------- CODE-4：st= 风格持久化 ----------
setmd("```js st=dark\nvar a = 1;\n```")
wait(300)
r = js("(function(){var cb=document.querySelector('#editor .codeblock');"
       "return JSON.stringify({cls:cb?cb.className:''});})()")
d = json.loads(r or "{}")
check("CODE-4 st=dark 渲染为 st-dark 类", "st-dark" in (d.get("cls") or ""), r)
# 风格按钮切换 → 写回围栏 info
r = js("(function(){var b=document.querySelector('#editor .style-btn');"
       "if(!b)return 'NOBTN';b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "return 'OK';})()")
wait(300)
r = js("(function(){var it=document.querySelector('#stylepop .si[data-st=\\'eye\\']');"
       "if(!it)return 'NOITEM';"
       "it.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "return 'OK';})()")
wait(400)
rr = "\n".join(raw())
check("CODE-4 风格切换写回 st=eye", "st=eye" in rr, rr[:80])
r = js("(function(){var cb=document.querySelector('#editor .codeblock');"
       "return JSON.stringify({cls:cb?cb.className:''});})()")
d = json.loads(r or "{}")
check("CODE-4 切换后类为 st-eye", "st-eye" in (d.get("cls") or ""), r)

# ---------- CODE-5：首行属性保留 + 尾空行 ≤2 ----------
setmd("```py w=100\nA\n```")
wait(300)
r = js("(function(){var c=document.querySelector('#editor .codeblock code');"
       "if(!c)return 'NOCODE';"
       "c.textContent='B\\n\\n\\n';"
       "c.dispatchEvent(new Event('input',{bubbles:true}));"
       "return 'OK';})()")
rr = raw()
check("CODE-5 首行属性保留", rr and rr[0].startswith("```py w=100"), str(rr)[:60])
check("CODE-5 尾空行保留 ≤2", rr and rr[0].endswith("B\n\n\n```"), str(rr)[:80])

# ---------- CODE-6：选区 Tab 批量缩进 ----------
setmd("```\naa\nbb\ncc\n```")
wait(300)
r = js("(function(){var c=document.querySelector('#editor .codeblock code');"
       "if(!c)return 'NOCODE';"
       "c.focus();"
       "var tn=c.firstChild;var rg=document.createRange();"
       "rg.setStart(tn,0);rg.setEnd(tn,6);"   # 覆盖 aa\nbb\n
       "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
       "c.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));"
       "return 'OK';})()")
rr = "\n".join(raw())
check("CODE-6 选区 Tab 批量缩进", "  aa\n  bb\ncc" in rr, rr[:80])
r = js("(function(){var c=document.querySelector('#editor .codeblock code');"
       "if(!c)return 'NOCODE';"
       "var tn=c.firstChild;var rg=document.createRange();"
       "rg.setStart(tn,0);rg.setEnd(tn,8);"
       "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
       "c.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true,cancelable:true}));"
       "return 'OK';})()")
rr = "\n".join(raw())
check("CODE-6 Shift+Tab 反缩进", "\naa\nbb" in rr and "  aa" not in rr, rr[:80])

# ---------- QUO-4：引用多行选区批量缩进 ----------
setmd("> aa\n> bb\n> cc")
wait(300)
r = js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'NOBQ';"
       "bq.focus();"
       "if(bq.childNodes.length<5)return 'NOKIDS:'+bq.childNodes.length;"
       "var rg=document.createRange();"
       "rg.setStart(bq.childNodes[0],0);rg.setEnd(bq.childNodes[4],0);"   # 覆盖 aa 行至 cc 行行首
       "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
       "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));"
       "return 'OK';})()")
rr = "\n".join(raw())
check("QUO-4 多行选区 Tab 批量嵌套", "> > aa\n> > bb" in rr and "> > cc" not in rr, rr[:80])

# Shift+Tab：在深度 2 的引用上批量退级
setmd("> > aa\n> > bb\n> cc")
wait(300)
r = js("(function(){var outer=document.querySelector('#editor blockquote');"
       "if(!outer)return 'NOBQ';"
       "var inner=outer.querySelector('blockquote')||outer;"
       "inner.focus();"
       "if(inner.childNodes.length<3)return 'NOKIDS:'+inner.childNodes.length;"
       "var rg=document.createRange();"
       "rg.setStart(inner.childNodes[0],0);rg.setEnd(inner.childNodes[2],2);"
       "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
       "outer.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true,cancelable:true}));"
       "return 'OK';})()")
rr = "\n".join(raw())
check("QUO-4 Shift+Tab 批量退级", "> > aa" not in rr and "> aa" in rr, rr[:80])

# ---------- QUO-3：行首退格先退一级嵌套 ----------
setmd("> > 深\n> 浅")
wait(300)
r = js("(function(){var outer=document.querySelector('#editor blockquote');"
       "if(!outer)return 'NOBQ';"
       "var inner=outer.querySelector('blockquote');"
       "var tgt=inner||outer;var tn=tgt.firstChild;"
       "if(!tn)return 'NOTN';"
       "var rg=document.createRange();rg.setStart(tn,0);rg.collapse(true);"
       "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
       "tgt.dispatchEvent(new KeyboardEvent('keydown',{key:'Backspace',bubbles:true,cancelable:true}));"
       "return 'OK';})()")
rr = raw()
check("QUO-3 行首退格退一级嵌套", rr and rr[0].startswith("> 深\n> 浅"), str(rr)[:60])

# ---------- FN-4 / FN-5：重排 + 清理 ----------
setmd("引用[^b]与[^a]。\n\n[^a]: 甲\n\n[^b]: 乙\n\n[^9]: 孤儿")
wait(300)
js("window.__fnRenum()")
wait(300)
rr = "\n".join(raw())
check("FN-4 按出现顺序重排引用", "[^1]与[^2]" in rr, rr[:60])
check("FN-4 定义跟随改号", "[^2]: 甲" in rr and "[^1]: 乙" in rr, rr[:80])
check("FN-4 孤儿定义不改号", "[^9]: 孤儿" in rr, rr[-30:])
js("window.__fnClean()")
wait(300)
rr = "\n".join(raw())
check("FN-5 清理未引用定义", "[^9]" not in rr and "[^1]" in rr, rr[:80])

# ---------- FN-3：跳转高亮 ----------
r = js("(function(){var a=document.querySelector('#editor .fnref a');"
       "if(!a)return 'NOA';"
       "a.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "return 'OK';})()")
wait(250)
r = js("(function(){return String(!!document.querySelector('#editor .fn-flash'));})()") or "false"
check("FN-3 引用→定义跳转高亮", r == "true", r)
r = js("(function(){var m=document.querySelector('#editor .fnmark');"
       "if(!m)return 'NOM';"
       "m.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "return 'OK';})()")
wait(250)
r = js("(function(){return String(!!document.querySelector('#editor sup.fnref.fn-flash'));})()") or "false"
check("FN-3 fnmark→引用跳转高亮", r == "true", r)

# ---------- DL-3：Tab 新增定义 ----------
setmd("术语\n: 甲")
wait(300)
r = js("(function(){var dd=document.querySelector('#editor dl dd');"
       "if(!dd)return 'NODD';"
       "dd.focus();"
       "dd.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));"
       "return 'OK';})()")
rr = raw()
check("DL-3 Tab 新增定义", len(rr) == 1 and rr[0] == "术语\n: 甲\n: ", str(rr)[:60])

# ---------- DL-4：空定义往返 ----------
setmd("术语\n: \n: 甲")
wait(300)
r = js("(function(){var dds=document.querySelectorAll('#editor dl dd');"
       "return JSON.stringify({n:dds.length,ph:dds.length?(dds[0].getAttribute('data-ph')||''):null,"
       "empty:dds.length?(dds[0].textContent||'').trim()==='':false});})()")
d = json.loads(r or "{}")
check("DL-4 空定义渲染 data-ph 隐藏提示（v3.31.3：不再 nbsp 占位）",
      d.get("n") == 2 and d.get("ph") == "定义内容" and d.get("empty") is True, r)
rr = "\n".join(raw())
check("DL-4 空定义存储往返不漂移", ": \n: 甲" in rr, rr[:60])
r = js("(function(){var dds=document.querySelectorAll('#editor dl dd');"
       "var t=dds[1];t.focus();"
       "document.execCommand('insertText',false,'乙');"
       "t.dispatchEvent(new Event('input',{bubbles:true}));"
       "return 'OK';})()")
rr = "\n".join(raw())
check("DL-4 空定义编辑后保留", ": \n: 乙" in rr, rr[:60])

# ---------- IMG-5/6/7：右键菜单链路 ----------
setmd("![图](x.png)")
wait(400)
r = js("(function(){var img=document.querySelector('#editor img');"
       "if(!img)return 'NOIMG';"
       "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:200}));"
       "return 'OK';})()")
wait(300)
r = js("(function(){var bm=document.getElementById('blkmenu');"
       "return JSON.stringify({size:!!bm.querySelector('.mi[data-act=imgsize]'),"
       "align:!!bm.querySelector('.mi[data-act=imgalign-sub]'),"
       "align1:!!bm.querySelector('.mi[data-act=\"imgalign:l\"]'),"
       "local:!!bm.querySelector('.mi[data-act=imglocalall]')});})()")
d = json.loads(r or "{}")
check("IMG 菜单含大小设置 / 对齐一级化 / 批量本地化（v3.31.3 IMG-8/9）",
      d.get("size") and d.get("align1") and d.get("local") and not d.get("align"), r)
r = js("(function(){var mi=document.querySelector('#blkmenu .mi[data-act=\"imgalign:l\"]');"
       "mi.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "return 'OK';})()")
wait(400)
rr = "\n".join(raw())
check("IMG-5 对齐靠左写回 fig-l", "fig-l" in rr, rr[:80])
r = js("(function(){var img=document.querySelector('#editor img');"
       "img.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:200}));"
       "return 'OK';})()")
wait(300)
r = js("(function(){var mi=document.querySelector('#blkmenu .mi[data-act=imgsize]');"
       "if(!mi)return 'NOMI';"
       "mi.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
       "return 'OK';})()")
wait(300)
r = js("(function(){var p=document.getElementById('imgsizepop');"
       "if(!p||!p.classList.contains('show'))return 'NOPOP';"
       "document.getElementById('imgsize-w').value='120';"
       "p.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
       "return 'OK';})()")
wait(400)
rr = "\n".join(raw())
check("IMG-7 大小设置写回 width:120px", "width:120px" in rr, rr[:100])

# ---------- MMD-7→MMD-11：图表主题 API（v3.34 起旧值自动映射到新主题） ----------
js("window.setMmdTheme('forest')")
r = js("(function(){return window.__mmdThemeOverride || '';})()") or ""
check("MMD-11 setMmdTheme 旧值 forest 映射为 mint", r == "mint", r)
js("window.setMmdTheme('')")

# ---------- U1：非空块行首 / 触发 ----------
setmd("第一行内容")
wait(300)
js("window.__enterEditAt(0, 0)")
wait(200)
r = js("(function(){var el=document.querySelector('#editor .raw-edit');"
       "if(!el)return 'NOEL';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return 'OK';})()")
wait(300)
r = js("(function(){var sm=document.getElementById('slashmenu');"
       "return JSON.stringify({open:sm.classList.contains('show')});})()")
d = json.loads(r or "{}")
check("U1 非空块行首 / 打开菜单", d.get("open") is True, r)
js("window.__slashPick('hr')")
wait(300)
rr = raw()
check("U1 应用后在当前块后插入（原块保留）",
      rr[0] == "第一行内容" and rr[1] == "---", str(rr)[:60])

# ---------- U2：斜杠菜单滚动重锚定 ----------
setmd("内容一段")
wait(300)
js("window.__enterEditAt(0, 0)")
wait(200)
js("(function(){var el=document.querySelector('#editor .raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
   "return 'OK';})()")
wait(200)
r = js("(function(){var ed=document.getElementById('editor');"
       "ed.dispatchEvent(new Event('scroll'));"
       "var sm=document.getElementById('slashmenu');"
       "return JSON.stringify({open:sm.classList.contains('show')});})()")
d = json.loads(r or "{}")
check("U2 斜杠菜单滚动重锚定（不关闭）", d.get("open") is True, r)

results.append("DONE")
flush()
print("SMOKE31 DONE")
