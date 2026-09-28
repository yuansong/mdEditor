# -*- coding: utf-8 -*-
"""v3.30.3 专项探针 _m34b（修正版）：写作模式插入操作 + 后续操作。
修正点：heading 为真实 id；表格走网格面板需 Enter 确认；引用内插入需先点进引用；
脚注需文档末尾空块；Ctrl+/ 走 window.openBlockMenu()；合并格 raw=htable 为合法存储。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m34b.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + " | " + name + (" | " + str(extra) if extra else ""))
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def jj(code):
    r = js(code)
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md) + ")"); wait(ms)


def click(sel):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'ok'})()")
    wait(300)


def slash_open_in(sel):
    """在指定元素上键入 / 唤起斜杠菜单"""
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return 'ok'})()")
    wait(300)


def pick(item, sub=None):
    sub_js = "null" if sub is None else str(sub)
    r = js("window.__slashPick(" + json.dumps(item) + ", " + sub_js + ")")
    wait(450)
    return r


def grid_enter():
    js("(function(){document.activeElement&&document.activeElement.blur&&document.activeElement.blur();"
       "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
       "return 'ok'})()")
    wait(500)


def select_all_text(sel):
    return jj("(function(){var h=document.querySelector(" + json.dumps(sel) + ");"
              "if(!h)return 'no-el';var w=document.createTreeWalker(h,NodeFilter.SHOW_TEXT,null);"
              "var n,last=null;while((n=w.nextNode()))last=n;if(!last)return 'notext';"
              "h.focus?h.focus():0;var r=document.createRange();r.selectNodeContents(last);"
              "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'ok'})()")


wait(2500)

# ============ A) 标题插入 + 渲染态加粗双链路（B13 修复验证） ============
setmd("")
click(".raw-edit")
slash_open_in(".raw-edit")
r = pick("heading")
rr = raw()
check("A1 插入标题3(默认)", r == "OK" and rr and rr[0] == "### ", json.dumps([r, rr], ensure_ascii=False))
type_r = js("(function(){var h=document.querySelector('#editor h3')||document.querySelector('h3');"
            "if(!h)return 'noh';h.focus();document.execCommand('insertText',false,'我的标题');return 'ok'})()")
wait(200)
rr = raw()
check("A2 渲染态输入文字", rr and rr[0] == "### 我的标题", json.dumps(rr, ensure_ascii=False))
d = select_all_text("h3")
wait(200)
js("window.__applyFloat('bold')"); wait(500)
rr = raw()
check("A3 标题渲染态加粗(格式栏)", rr and rr[0] == "### **我的标题**", json.dumps(rr, ensure_ascii=False))
d = select_all_text("h3")
wait(200)
js("window.cmd('bold')"); wait(500)
rr = raw()
check("A4 标题渲染态加粗(cmd/B13统一链路)", rr and rr[0] == "### ****我的标题****", json.dumps(rr, ensure_ascii=False))
# 撤销校验：A4 应可通过 undo 回退
js("window.cmd('undo')"); wait(400)
rr = raw()
check("A5 undo 回退加粗", rr and rr[0] == "### **我的标题**", json.dumps(rr, ensure_ascii=False))

# ============ B) 表格：slash → 网格面板 → Enter；标注弹层 ============
setmd("")
click(".raw-edit")
slash_open_in(".raw-edit")
r = pick("table")
rr = raw()
d = jj("(function(){var g=document.getElementById('tblsize');"
       "return JSON.stringify({grid:!!(g&&g.classList.contains('show'))})})()")
check("B1 slash表格→网格面板打开", d.get("grid") is True, json.dumps([d, rr], ensure_ascii=False))
grid_enter()
rr = raw()
check("B2 Enter确认插入表格", len(rr) >= 1 and rr[0].count("|") >= 8 and " --- " in rr[0],
      json.dumps(rr, ensure_ascii=False))
# 标注：设选区 → cap → 弹层输入 → 确定
setmd("| A | B |\n| --- | --- |\n| 1 | 2 |")
wait(500)
js("window.__tblSelSet(0, 0, 0, 0, 0)"); wait(300)
js("window.__tblOp('cap')"); wait(400)
d = jj("(function(){var inp=document.querySelector('#cappop input,#cappop textarea');"
       "var pop=document.getElementById('cappop');"
       "return JSON.stringify({show:!!(pop&&pop.classList.contains('show')),"
       "inp:!!inp})})()")
check("B3 表格标注弹层打开", d.get("show") is True and d.get("inp") is True, d)
if d.get("show"):
    js("(function(){var inp=document.querySelector('#cappop input,#cappop textarea');"
       "inp.value='表：测试标注';"
       "var ok=document.querySelector('#cap-ok')||document.querySelector('#cappop .ok');"
       "if(ok)ok.click();return 'ok'})()")
    wait(400)
    rr = raw()
    check("B4 表格标注写入raw", any("表：测试标注" in b for b in rr), json.dumps(rr, ensure_ascii=False))

# ============ C) 引用内插入表格（v3.29 补 > 前缀） ============
setmd("> 引用行")
wait(500)
click("#editor blockquote")
slash_open_in("#editor blockquote")
r = pick("table")
check("C1 引用内slash菜单可开", r == "OK", r)
grid_enter()
rr = raw()
ok = (len(rr) >= 1 and all(l == "" or l.startswith(">") for b in rr for l in b.split("\n")))
check("C2 引用内插入表格(所有行带>)", ok, json.dumps(rr, ensure_ascii=False))
js("(function(){var el=document.querySelector('.raw-edit');if(el)el.blur();return 'x'})()")
wait(400)
rr = raw()
ok2 = (len(rr) >= 1 and any("|" in b for b in rr) and
       all(l == "" or l.startswith(">") for b in rr for l in b.split("\n")))
check("C3 引用内表格blur后仍带>前缀", ok2, json.dumps(rr, ensure_ascii=False))

# ============ D) 脚注：末尾空块触发 + 编号递增 ============
setmd("正文段落\n\n")
wait(500)
rr0 = raw()
if len(rr0) < 2 or rr0[1] != "":
    js("(function(){var b=document.querySelectorAll('#editor .blk');"
       "b[b.length-1].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
       "if(document.querySelector('.raw-edit'))document.execCommand('insertText',false,'\\n');"
       "return 'ok'})()")
    wait(300)
click("#editor .blk:last-child")
d = jj("(function(){return JSON.stringify({empty:(window.__raw()|0)===0})})()")
slash_open_in(".raw-edit")
r = pick("footnote", 0)
wait(500)
rr = raw()
has_ref = any("[^1]" in b for b in rr)
has_def = any(b.startswith("[^1]:") for b in rr)
check("D1 脚注引用+自动定义块", r == "OK" and has_ref and has_def, json.dumps([r, rr], ensure_ascii=False))
# 第二次：编号应递增到 2
click("#editor .blk:last-child")
slash_open_in(".raw-edit")
r = pick("footnote", 0)
wait(500)
rr = raw()
check("D2 脚注编号递增[^2]", any("[^2]" in b for b in rr) and any(b.startswith("[^2]:") for b in rr),
      json.dumps([r, rr], ensure_ascii=False))

# ============ E) 空块快捷键加粗（无选区行为） ============
setmd("")
click(".raw-edit")
js("window.cmd('bold')"); wait(400)
rr = raw()
check("E1 空块Ctrl+B行为记录(空标记对?)", rr and rr[0] in ("", "**"), json.dumps(rr, ensure_ascii=False))

# ============ F) 合并格后编辑相邻段（m32 挤在一起回归，htable 为合法存储） ============
setmd("# 标题一\n\n正文段。\n\n| 名称 | 数量 |\n| --- | --- |\n| 苹果 | 3 |\n| 香蕉 | 12 |\n\n```python\nprint(1)\n```")
wait(800)
js("window.__tblSelSet(2, 1, 0, 1, 1)"); wait(300)
js("window.__tblOp('merge')"); wait(400)
click("#editor .blk:nth-child(2)")
type_text_r = js("(function(){var el=document.querySelector('.raw-edit');if(!el)return 'no-el';"
                 "el.focus();var s=getSelection();var r=document.createRange();"
                 "r.selectNodeContents(el);r.collapse(false);s.removeAllRanges();s.addRange(r);"
                 "document.execCommand('insertText',false,'追加文字');return 'ok'})()")
wait(300)
js("(function(){var el=document.querySelector('.raw-edit');if(el)el.blur();return 'x'})()")
wait(600)
rr = raw()
ok = (len(rr) == 5 and rr[0] == "# 标题一" and rr[1] == "正文段。追加文字"
      and ("colspan" in rr[2] or "苹果" in rr[2]) and "```python" in rr[3])
md_full = js("window.getMarkdown()")
check("F1 合并格后编辑相邻段raw完整", ok, json.dumps(rr, ensure_ascii=False))
check("F2 getMarkdown与raw一致(无挤行)", (md_full or "").count("\n\n") >= 4, md_full)

# ============ G) 代码块插入 + 语言弹层 Esc + 输入代码 ============
setmd("")
click(".raw-edit")
slash_open_in(".raw-edit")
r = pick("code")
wait(400)
d = jj("(function(){var lp=document.getElementById('langpop');"
       "return JSON.stringify({lang:!!(lp&&lp.classList.contains('show'))})})()")
check("G1 代码块插入后语言弹层自动打开", d.get("lang") is True, d)
js("(function(){var inp=document.querySelector('#langpop input');if(inp){inp.focus();"
   "inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));}return 'x'})()")
wait(300)
d = jj("(function(){var code=document.querySelector('#editor .codeblock code');"
       "return JSON.stringify({code:!!code,focused:document.activeElement===code})})()")
check("G2 Esc后光标进入代码区", d.get("code") is True and d.get("focused") is True, d)
if d.get("code"):
    js("(function(){var code=document.querySelector('#editor .codeblock code');code.focus();"
       "document.execCommand('insertText',false,'print(42)');return 'ok'})()")
    wait(300)
    js("(function(){var code=document.querySelector('#editor .codeblock code');code.blur();return 'x'})()")
    wait(500)
    rr = raw()
    check("G3 代码区输入回写raw", any("print(42)" in b for b in rr), json.dumps(rr, ensure_ascii=False))

out.append("DONE")
flush()
print("done")
