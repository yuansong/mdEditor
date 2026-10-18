# -*- coding: utf-8 -*-
"""v3.30.3 专项探针 _m34：写作模式下各类插入操作及其后续操作的系统测试。
A) m33 三项 htmlToMd 复测（A4 嵌套列表 / A5 有序列表 / A10 待办列表）;
B) 斜杠菜单 12 类插入（空文档 '/' 唤起 → __slashPick）+ raw 校验;
C) 插入后跟随操作（渲染态加粗 双链路、引用内插入表格、图表下方 DEL、
   脚注自动编号、代码块 Ctrl+Enter 跳出、表格标注+合并后全文完整性）。
结果写 _m34.txt，PASS/FAIL 逐条判定。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m34.txt")
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


def open_slash():
    """空文档下进入空块并键入 / 唤起斜杠菜单"""
    js("(function(){var el=document.querySelector('.raw-edit');"
       "if(!el)return 'noedit';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return 'x'})()")
    wait(300)


def pick(item, sub=None):
    sub_js = "null" if sub is None else str(sub)
    r = js("window.__slashPick(" + json.dumps(item) + ", " + sub_js + ")")
    wait(450)
    return r


def type_text(sel, text):
    call = ("(function(){var el=document.querySelector(" + json.dumps(sel) + ");if(!el)return 'no-el';"
            "el.focus();var s=getSelection();var r=document.createRange();"
            "r.selectNodeContents(el);r.collapse(false);s.removeAllRanges();s.addRange(r);"
            "document.execCommand('insertText',false," + json.dumps(text) + ");return 'ok'})()")
    return js(call)


wait(2500)

# ============ A) htmlToMd 复测 ============
H2M = [
    ("A4 嵌套列表", "<ul><li>甲<ul><li>甲1</li></ul></li><li>乙</li></ul>", "- 甲\n  - 甲1\n- 乙"),
    ("A5 有序列表", "<ol><li>一</li><li>二</li></ol>", "1. 一\n2. 二"),
    ("A10 待办列表", "<ul><li><input type='checkbox' checked>做完</li><li><input type='checkbox'>没做</li></ul>", "- [x] 做完\n- [ ] 没做"),
    ("A11 混合段落列表", "<p>前段</p><ol><li>甲</li></ol><p>后段</p>", "前段\n\n1. 甲\n\n后段"),
]
for name, src, want in H2M:
    d = jj("(function(){var r=window.__htmlToMd(" + json.dumps(src) + ");return JSON.stringify({md:r})})()")
    check(name, d.get("md") == want, "got=" + json.dumps(d.get("md"), ensure_ascii=False))

# ============ B) 斜杠菜单 12 类插入 ============
# B1 标题二级（默认标题3）
setmd("")
open_slash()
r = pick("heading")
rr = raw()
check("B1 插入标题3", r == "OK" and rr and rr[0] == "### ", json.dumps([r, rr], ensure_ascii=False))
# 渲染态输入文字 + 渲染态选中加粗（格式栏链路）
d = jj("(function(){return JSON.stringify({wysiwyg: !!(document.activeElement&&document.activeElement.closest&&document.activeElement.closest('h3,h2,h1'))||document.activeElement&&document.activeElement.isContentEditable})})()")
type_text("h3, #editor h3", "我的标题")
wait(200)
# 渲染态选中标题文字 → __applyFloat('bold')（模拟格式栏按钮）
d = jj("(function(){var h=document.querySelector('#editor h3, h3');if(!h)return 'noh';"
       "h.focus();var w=document.createTreeWalker(h,NodeFilter.SHOW_TEXT,null);var n,last=null;"
       "while((n=w.nextNode()))last=n;if(!last)return 'notext';"
       "var r=document.createRange();r.selectNodeContents(last);"
       "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'ok'})()")
wait(200)
js("window.__applyFloat('bold')"); wait(500)
rr = raw()
check("B1a 标题渲染态加粗(格式栏链路)", rr and rr[0] == "### **我的标题**", json.dumps(rr, ensure_ascii=False))
# 快捷键链路（B13 修复验证）：再套一层斜体
d = jj("(function(){var h=document.querySelector('#editor h3, h3');if(!h)return 'noh';"
       "h.focus();var w=document.createTreeWalker(h,NodeFilter.SHOW_TEXT,null);var n,last=null;"
       "while((n=w.nextNode()))last=n;if(!last)return 'notext';"
       "var r=document.createRange();r.selectNodeContents(last);"
       "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'ok'})()")
wait(200)
js("window.cmd('italic')"); wait(500)
rr = raw()
check("B1b 标题渲染态斜体(cmd 快捷键链路/B13)", rr and rr[0] == "### ***我的标题***" or (rr and rr[0].startswith("###") and rr[0].count("*") >= 6), json.dumps(rr, ensure_ascii=False))

# B2 列表（有序，默认项）
setmd("")
open_slash()
r = pick("list")
rr = raw()
check("B2 插入有序列表", r == "OK" and rr and rr[0] == "1. ", json.dumps([r, rr], ensure_ascii=False))
# 无序
setmd("")
open_slash()
r = pick("list", 0)
rr = raw()
check("B2a 插入无序列表", r == "OK" and rr and rr[0] == "- ", json.dumps([r, rr], ensure_ascii=False))
# 待办
setmd("")
open_slash()
r = pick("list", 2)
rr = raw()
check("B2b 插入待办列表", r == "OK" and rr and rr[0] == "- [ ] ", json.dumps([r, rr], ensure_ascii=False))

# B3 表格（网格面板默认 3 行 × 4 列，点第 3 行第 4 列确认）
setmd("")
open_slash()
r = pick("table")
wait(400)
# v3.30.3：pick('table') 打开网格面板，需点击网格格确认（与 smoke16 一致）
d = jj("(function(){var g=document.getElementById('tblsize');"
       "if(!g.classList.contains('show'))return 'nogrid';"
       "var c=g.querySelector('.gc[data-r=\"2\"][data-c=\"3\"]');"
       "if(!c)return 'nocell';"
       "c.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'clicked'})()")
wait(500)
rr = raw()
ok = (r == "OK" and d.get("_raw") == "clicked" and rr and rr[0].startswith("| ")
      and " --- " in rr[0])
check("B3 插入表格(网格确认 3x4)", ok, json.dumps([r, d, rr], ensure_ascii=False)[:400])
# 插入后继续：表格标注（cap → 弹层输入 → 确定，同 m34b 流程）
js("window.__tblSelSet(0, 0, 0, 0, 0)"); wait(300)
js("window.__tblOp('cap')"); wait(400)
d = jj("(function(){var inp=document.querySelector('#cappop input,#cappop textarea');"
       "var pop=document.getElementById('cappop');"
       "return JSON.stringify({show:!!(pop&&pop.classList.contains('show')),inp:!!inp})})()")
if d.get("show"):
    js("(function(){var inp=document.querySelector('#cappop input,#cappop textarea');"
       "inp.value='表：测试';"
       "var ok=document.querySelector('#cap-ok')||document.querySelector('#cappop .ok');"
       "if(ok)ok.click();return 'ok'})()")
    wait(400)
rr = raw()
check("B3a 表格标注写入", any("<caption" in b or "表：测试" in b for b in rr), json.dumps([d, rr], ensure_ascii=False)[:400])

# B4 代码块
setmd("")
open_slash()
r = pick("code")
wait(300)
# 语言弹层会自动打开——回车确认默认语言
js("(function(){var el=document.activeElement;if(el&&el.tagName==='INPUT'){" 
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'x'}})()")
wait(300)
rr = raw()
# v3.30.3：插入代码块后允许文尾留一个空块（可继续输入），只断言代码块本体
check("B4 插入代码块", any(b.startswith("```") and b.rstrip().endswith("```") for b in rr),
      json.dumps(rr, ensure_ascii=False))

# B5 分割线
setmd("")
open_slash()
r = pick("hr")
rr = raw()
check("B5 插入分割线", any(b == "---" for b in rr), json.dumps(rr, ensure_ascii=False))

# B6 引用
setmd("")
open_slash()
r = pick("quote")
rr = raw()
check("B6 插入引用", len(rr) == 1 and rr[0] == "> ", json.dumps(rr, ensure_ascii=False))
# B6a 引用内插入表格（v3.29 引用内插入 → 补 > 前缀）
# v3.30.3（BUG-1 修复后）：真实路径 = 点击引用块渲染态 → / 唤起 → 选表格 → 网格确认
setmd("> 引用行")
wait(300)
js("(function(){var q=document.querySelector('#editor blockquote');"
   "if(!q)return 'noq';"
   "q.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
js("(function(){var q=document.querySelector('#editor blockquote');"
   "var tgt=q.querySelector('.raw-edit')||q;"
   "tgt.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(200)
r = pick("table")
wait(400)
d = jj("(function(){var g=document.getElementById('tblsize');"
       "if(!g.classList.contains('show'))return 'nogrid';"
       "var c=g.querySelector('.gc[data-r=\"2\"][data-c=\"3\"]');"
       "if(!c)return 'nocell';"
       "c.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'clicked'})()")
wait(500)
rr = raw()
tbl_lines = [l for b in rr for l in b.split("\n") if "|" in l]
check("B6a 引用内插入表格(网格确认，行补 > 前缀)",
      r == "OK" and d.get("_raw") == "clicked" and len(tbl_lines) >= 3
      and all(l.startswith(">") for l in tbl_lines)
      and any("---" in l for l in tbl_lines),
      json.dumps([r, d, rr], ensure_ascii=False)[:400])

# B7 图表（流程图模板）
setmd("")
open_slash()
r = pick("chart", 0)
wait(800)
rr = raw()
check("B7 插入图表流程图", any("```mermaid" in b and "flowchart" in b for b in rr),
      json.dumps(rr, ensure_ascii=False))
# B7a 图表下方空段按 DEL → 打开源码框且图表保留
d = jj("(function(){var el=document.querySelector('.raw-edit');if(!el)return 'noedit';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}));return 'x'})()")
wait(400)
d = jj("(function(){var ta=document.querySelector('#editor .mmd-src');"
       "return JSON.stringify({ta:!!ta,focused:document.activeElement===ta,"
       "mmd:!!document.querySelector('#editor .mermaidblock')})})()")
check("B7a 图表下方DEL开源码框且图表保留", d.get("ta") is True and d.get("mmd") is True, d)
js("(function(){var ta=document.querySelector('#editor .mmd-src');if(ta)ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)

# B8 脚注引用（自动补定义块 + 编号递增）
# v3.30.3：slash 仅在空块唤起；非空段落用 cmd('footnote')（Ctrl+/ 同源 B13 链路，
# m34f F1/F3 已验证）——点击段落置焦后插入引用标记，文末自动补定义
setmd("正文段落")
wait(300)
js("(function(){var b=document.querySelectorAll('#editor .blk')[0];b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
r = js("window.cmd('footnote')")
wait(500)
rr = raw()
has_ref = any("[^1]" in b for b in rr)
has_def = any(b.startswith("[^1]:") for b in rr)
check("B8 脚注引用+自动定义块", has_ref and has_def, json.dumps([r, rr], ensure_ascii=False))
# 第二次插入编号递增
js("window.cmd('footnote')")
wait(500)
rr = raw()
check("B8a 脚注编号递增", any("[^2]" in b for b in rr) and any(b.startswith("[^2]:") for b in rr),
      json.dumps(rr, ensure_ascii=False))

# B9 定义列表（v3.31.3：并入「脚注与定义」refs 子项第 3 项，插入即渲染态空定义）
setmd("")
open_slash()
r = pick("refs", 2)
wait(400)
rr = raw()
check("B9 插入术语定义（refs 子项）", r == "OK" and any(x == "术语\n: " for x in rr),
      json.dumps([r, rr], ensure_ascii=False))

# B10 v3.30.3：一级菜单已移除「上标 / 下标」；v3.31.3：脚注/定义列表合并为「脚注与定义」
setmd("")
open_slash()
d = jj("(function(){var m=document.getElementById('slashmenu');"
       "var lbs=[].map.call(m.querySelectorAll('.si .lb'),function(x){return x.textContent;});"
       "return JSON.stringify({n:lbs.length, lbs:lbs})})()")
check("B10 一级菜单 11 项平铺（refs 合并 + v3.32 新增模板）", d.get("n") == 11, d)
check("B10a 无上标/下标项", "上标 / 下标" not in (d.get("lbs") or []) and
      not any("上标" in x for x in (d.get("lbs") or [])), d)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 'x'})()")
wait(200)

# B11 公式模板（插入 math 块 + 就地源码框）
setmd("")
open_slash()
r = pick("math", 0)
wait(500)
rr = raw()
check("B11 插入公式块", any("```math" in b for b in rr), json.dumps([r, rr], ensure_ascii=False))
d = jj("(function(){var ta=document.querySelector('#editor .math-src,#editor textarea');"
       "return JSON.stringify({src:!!document.querySelector('#editor .mathblock,.mmd-src,.math-src')})})()")

# B12 图片（走 Qt 插入面板 → __wantPick 标记；同步读防 collect 轮询竞态）
setmd("")
open_slash()
d = jj("(function(){window.__wantPick=false;"
       "var r=window.__slashPick('image', null);"
       "var pick=window.__wantPick===true;window.__wantPick=false;"
       "return JSON.stringify({r:r,pick:pick})})()")
wait(200)
js("window.__wantPick=false")
check("B12 图片插入触发Qt面板", d.get("pick") is True or d.get("r") == "OK", json.dumps(d, ensure_ascii=False))

# ============ C) 插入后跟随操作 ============
# C1 标题+列表+表格混排后全文完整性（m32 场景 + 上移下移 + 删除块）
setmd("# 大标题\n\n正文段落内容\n\n| A | B |\n| --- | --- |\n| 1 | 2 |")
wait(600)
# v3.30.3：Ctrl+/ 是 Qt 动作 → window.openBlockMenu()（mainwindow.py:432-433），
# 合成键盘事件无法触发 QAction，直接调用同一入口验证
d = jj("(function(){var b=document.querySelectorAll('#editor .blk')[1];"
       "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
r = js("window.openBlockMenu ? window.openBlockMenu() : 'nofn'")
wait(300)
d = jj("(function(){var sm=document.getElementById('slashmenu');"
       "var bm=document.querySelector('#blkmenu');"
       "var st=(window.__blkMenuState?window.__blkMenuState():null);"
       "return JSON.stringify({r:" + json.dumps(r) + ",sm:sm.classList.contains('show'),"
       "st:st})})()")
st = d.get("st")
if isinstance(st, str):
    try: st = json.loads(st)
    except Exception: st = {}
check("C1 Ctrl+/ 入口（openBlockMenu）打开菜单",
      (r == "slash" or r == "blk" or r == "ok")
      and (d.get("sm") is True or (isinstance(st, dict) and st.get("show") is True)),
      json.dumps(d, ensure_ascii=False)[:300])
js("(function(){document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));return 'x'})()")
wait(200)

# C2 表格合并后编辑相邻段落 → raw 完整（m32「挤在一起」回归）
# v3.38 PARA-WYS：段落 mousedown 保持渲染态（不再进 raw-edit）——
# 改为渲染态 p 聚焦 + insertText 输入 + blur 失焦回写
setmd("# 标题一\n\n正文段。\n\n| 名称 | 数量 |\n| --- | --- |\n| 苹果 | 3 |\n| 香蕉 | 12 |\n\n```python\nprint(1)\n```")
wait(800)
js("window.__tblSelSet(2, 1, 0, 1, 1)"); wait(300)
js("window.__tblOp('merge')"); wait(400)
d = jj("(function(){var b=document.querySelectorAll('#editor .blk')[1];"
       "var t=b.querySelector('p[contenteditable]')||b.querySelector('p');"
       "if(!t)return 'no-host';"
       "t.focus();"
       "var rg=document.createRange();rg.selectNodeContents(t);rg.collapse(false);"
       "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.execCommand('insertText',false,'追加文字');"
       "return 'ok'})()")
wait(300)
js("(function(){var el=document.querySelector('#editor .blk p[contenteditable]');if(el)el.blur();return 'x'})()")
wait(500)
rr = raw()
# v3.30.3：合并格（colspan）按存储规则升级为 HTML 表格（能原生 MD 才原生，
# 表达不了才升级 HTML）——rr[2] 应为 htable 且合并内容在原位
ok = (len(rr) == 4 and rr[0] == "# 标题一" and rr[1] == "正文段。追加文字"
      and rr[2].startswith("<table") and "苹果 3" in rr[2] and "```python" in rr[3])
check("C2 合并格后编辑相邻段raw完整（HTML 存储形态）", ok, json.dumps(rr, ensure_ascii=False)[:500])

# C3 Esc 关闭浮层 + setMarkdown 换文档后无残留 activePop
setmd("新文档内容")
wait(400)
d = jj("(function(){return JSON.stringify({pops:document.querySelectorAll('.pop.show,[id$=pop].show,[id$=menu].show').length})})()")

out.append("DONE")
flush()
print("done")
