# -*- coding: utf-8 -*-
"""m98 格式栏（floatbar）全块型一致性审计：按钮矩阵 + 单元格语义 + 特殊块 + 守卫

用户要求（2026-10-01）：排查所有功能的格式栏功能是否统一、代码是否一致。
审计维度：
  A 组 按钮矩阵：13 类上下文选中文字 → dump floatbar 按钮 title / 尾部文案 / ＋ 按钮
  B 组 单元格 vs 正文语义一致性：首现匹配 vs 精确偏移、toggle、码内守卫（FMT-1 在单元格路径是否缺席）、
       下划线（FMT-12）、清除格式
  C 组 delOnly 特殊块：代码块 / mathdl / 图表的「仅删除」条与 delblk 动作
  D 组 正文守卫回归：跨行拒绝（LIST-1 止血）、跨块标题选区动作范围观察
版本：src v3.37（2026-10-01 07:02:55，683822B，sha16 C0D0D0DA8661B2CF）——快照期间并行会话仍高频修改
结果：tests/_m98.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m98.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []
URL = "https://ex.com/doc"


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
        ABN.append(name + " || " + detail)
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def note(s):
    log("NOTE %s" % s)


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code, timeout=15000):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(timeout, loop.quit)
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


def setmd(md, ms=750):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    r = jj("window.__raw()")
    return r.get("raw", []) if isinstance(r, dict) else []


def getmd():
    return js("window.getMarkdown()") or ""


FULL = ["粗体", "斜体", "下划线", "删除线", "高亮", "行内代码", "链接", "清除格式"]


def fb_state():
    """dump floatbar：按钮 title 列表 / 尾部文案 / 是否显示"""
    return jj("(function(){var fb=document.getElementById('floatbar');"
              "if(!fb)return JSON.stringify({show:false,err:'no-fb'});"
              "if(!fb.classList.contains('show'))return JSON.stringify({show:false});"
              "var ts=[].map.call(fb.querySelectorAll('button'),function(b){return b.title});"
              "var cnt=fb.querySelector('.fbcnt');"
              "return JSON.stringify({show:true,btns:ts,tail:cnt?cnt.textContent:''})})()")


def has_full(st):
    return all(x in st.get("btns", []) for x in FULL)


def sel_nth(selector, idx, a, b, ms=260):
    """selector 第 idx 个元素内部按渲染文本偏移 [a,b) 构造选区"""
    js("(function(){var el=document.querySelectorAll(" + json.dumps(selector) + ")[" + str(idx) + "];"
       "if(!el)return 'no-el';"
       "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);"
       "var pos=0,sn=null,so=0,en=null,eo=0,n;"
       "while(n=w.nextNode()){var L=n.nodeValue.length;"
       "if(sn===null&&pos+L>=" + str(a) + "){sn=n;so=" + str(a) + "-pos;}"
       "if(pos+L>=" + str(b) + "){en=n;eo=" + str(b) + "-pos;break;}"
       "pos+=L;}"
       "if(!sn||!en)return 'no-range';"
       "var rg=document.createRange();rg.setStart(sn,so);rg.setEnd(en,eo);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def sel_node(selector, idx=0, ms=260):
    """selectNodeContents 整元素选区（用于 SVG / KaTeX 等无常规文本流场景）"""
    js("(function(){var el=document.querySelectorAll(" + json.dumps(selector) + ")[" + str(idx) + "];"
       "if(!el)return 'no-el';"
       "var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def apply_act(action, ms=340):
    if action == "link":
        js("window.__applyFloat('link')")
        wait(ms)
        js("(function(){var i=document.getElementById('link-url');"
           "if(!i)return 'no-input';i.value=" + json.dumps(URL) + ";"
           "var b=document.getElementById('link-ok');"
           "if(!b)return 'no-btn';b.click();return 'ok'})()")
        wait(ms + 140)
        return
    js("window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


def toast():
    return js("window.takeToast()") or ""


P = "| 表头 | 数量 |\n| --- | --- |\n| 甲乙甲乙 | 3 |"
HT = '<table><tr><th>名称</th></tr><tr><td><code>x</code>和<code>x</code></td></tr></table>'

note("========== A 组：按钮矩阵（13 类上下文） ==========")

note("A1 段落")
setmd("普通段落文字")
sel_nth("#editor p", 0, 1, 3)
st = fb_state()
check("A1 显示", st.get("show") is True, json.dumps(st, ensure_ascii=False))
check("A1 全套按钮", has_full(st), str(st.get("btns")))
check("A1 无＋", "插入（列表 / 代码块 / 图片 / 图表 / 公式）" not in st.get("btns", []), str(st.get("btns")))
check("A1 无⇔", "标题居中" not in st.get("btns", []) and "标题向左对齐" not in st.get("btns", []), str(st.get("btns")))
check("A1 尾部字数", "已选" in st.get("tail", ""), st.get("tail"))

note("A2 标题1（⇔ 与标题计数）")
setmd("# 标题甲")
sel_nth("#editor h1", 0, 0, 3)
st = fb_state()
check("A2 全套按钮", has_full(st), str(st.get("btns")))
check("A2 有⇔", ("标题居中" in st.get("btns", [])) or ("标题向左对齐" in st.get("btns", [])), str(st.get("btns")))
check("A2 尾部含标题1", "标题 1" in st.get("tail", ""), st.get("tail"))

note("A3 标题2（v3.38 ALIGN-1：居中入口放开到 h1~h6，计数=1）")
setmd("## 标题乙")
sel_nth("#editor h2", 0, 0, 3)
st = fb_state()
check("A3 全套按钮", has_full(st), str(st.get("btns")))
# v3.38 ALIGN-1：blockInfo / 渲染本就支持任意级别 tagForm，居中不再只认 h1
check("A3 有⇔", ("标题居中" in st.get("btns", [])) or ("标题向左对齐" in st.get("btns", [])), str(st.get("btns")))
check("A3 尾部含标题1", "标题 1" in st.get("tail", ""), st.get("tail"))

note("A4 列表项")
setmd("- 列表项文字\n- 第二项")
sel_nth("#editor li", 0, 0, 4)
st = fb_state()
check("A4 全套按钮", has_full(st), str(st.get("btns")))

note("A5 引用块")
setmd("> 引用内文字")
sel_nth("#editor blockquote", 0, 0, 4)   # v3.38 甄别：纯文本引用为单容器，无内层 p（原 blockquote p 选择器伪影）
st = fb_state()
check("A5 全套按钮", has_full(st), str(st.get("btns")))

note("A6 定义列表 dt / dd")
setmd("术语甲\n: 定义内容文字")
sel_nth("#editor dt", 0, 0, 3)
st = fb_state()
check("A6a dt 全套按钮", has_full(st), str(st.get("btns")))
sel_nth("#editor dd", 0, 0, 4)
st = fb_state()
check("A6b dd 全套按钮", has_full(st), str(st.get("btns")))

note("A7 脚注定义（渲染态 fnedit）")
setmd("正文引用[^1]\n\n[^1]: 脚注说明文字")
sel_nth("#editor .fnedit", 0, 0, 4)
st = fb_state()
check("A7 全套按钮", has_full(st), str(st.get("btns")))

note("A8 管道表单元格（＋按钮）")
setmd(P)
sel_nth("#editor td", 0, 0, 4)
st = fb_state()
check("A8 全套按钮", has_full(st), str(st.get("btns")))
check("A8 无＋（TBL-F2 移除，插入走 / 菜单与块菜单）", "插入（列表 / 代码块 / 图片 / 图表 / 公式）" not in st.get("btns", []), str(st.get("btns")))

note("A9 HTML 表单元格（＋按钮）")
setmd(HT)
sel_nth("#editor td", 0, 2, 3, ms=320)
st = fb_state()
check("A9 全套按钮", has_full(st), str(st.get("btns")))
check("A9 无＋（TBL-F2 移除）", "插入（列表 / 代码块 / 图片 / 图表 / 公式）" not in st.get("btns", []), str(st.get("btns")))

note("A10 代码块（delOnly）")
setmd("```python\nprint('hello')\n```")
sel_nth("#editor .codeblock", 0, 0, 5)   # v3.38 甄别：选 .codeblock 整体（同 m98b R2b 口径）
st = fb_state()
note("  A10 fb=%s" % json.dumps(st, ensure_ascii=False))
if st.get("show"):
    check("A10 仅删除", st.get("btns") == ["删除整个块"], str(st.get("btns")))
else:
    note("  A10 浮条未显示（show=False），记观察项 —— delOnly+delblk 语义由 C1 与 m98b R2b 覆盖")

note("A11 mathdl 块（delOnly 探测）")
setmd("$$\nx^2 + y^2\n$$")
sel_node("#editor .mathblock", 0)
st = fb_state()
if st.get("show"):
    check("A11 仅删除", st.get("btns") == ["删除整个块"], str(st.get("btns")))
else:
    note("  A11 mathdl 选区未能构造（show=False），记观察项")

note("A12 图表 mmd（delOnly 探测）")
setmd("```mermaid\nflowchart LR\n  A[入口] --> B[核心]\n```")
sel_node("#editor .mermaidblock", 0)
st = fb_state()
if st.get("show"):
    check("A12 仅删除", st.get("btns") == ["删除整个块"], str(st.get("btns")))
else:
    note("  A12 mmd 选区未能构造（show=False），记观察项")

note("========== B 组：单元格 vs 正文语义一致性 ==========")

note("B1 首次出现匹配：重复文字选第二处（正文路径=精确偏移，单元格路径=indexOf 首现）")
setmd(P)
sel_nth("#editor td", 0, 2, 3, ms=300)   # 甲乙[甲]乙 → 选第二处「甲」
apply_act("bold")
raw = getraw()
row = next((r for r in raw if "甲乙甲乙" in r or "甲**" in r), "")
# 正文对照：同样的重复文字在段落中选第二处
setmd("甲乙甲乙")
sel_nth("#editor p", 0, 2, 3)
apply_act("bold")
praw = getraw()
prow = praw[0] if praw else ""
check("B1 正文第二处加粗精确", prow == "甲乙**甲**乙",
      "raw=%s" % json.dumps(prow, ensure_ascii=False))
check("B1 单元格第二处加粗精确", "**甲**乙" in row and not row.index("**") < row.index("甲乙") if row else False,
      "row=%s" % json.dumps(row, ensure_ascii=False))

note("B2 单元格 toggle 取消（已加粗再点粗体）")
setmd("| 表头 |\n| --- |\n| **甲**乙 |")
sel_nth("#editor td", 0, 0, 1, ms=300)
apply_act("bold")
raw = getraw()
row = next((r for r in raw if "甲" in r), "")   # v3.38 甄别：整表一条 raw
check("B2 取消加粗回裸文字", row is not None and "**" not in row,
      "row=%s" % json.dumps(row, ensure_ascii=False))

note("B3 码内守卫缺失探测：管道单元格内行内码文字加粗（正文路径 FMT-1 拒绝+toast）")
setmd("| 表头 |\n| --- |\n| 前`码甲`后 |")
sel_nth("#editor td", 0, 1, 3, ms=300)   # 选「码甲」
apply_act("bold")
raw = getraw()
row = next((r for r in raw if "码甲" in r), "")   # v3.38 甄别：整表一条 raw
note("  B3 raw=%s" % json.dumps(row, ensure_ascii=False))
if row and "`**" in row or (row and "**`" in row):
    check("B3 单元格码内加粗被拒绝（与正文 FMT-1 一致）", False,
          "码内包了 **：%s" % json.dumps(row, ensure_ascii=False))
elif row:
    check("B3 单元格码内加粗被拒绝（与正文 FMT-1 一致）", True, "row=%s" % row)
else:
    note("  B3 未命中目标行，观察")

note("B3b HTML 表码内加粗")
setmd(HT)
sel_nth("#editor td code", 0, 0, 1, ms=320)
apply_act("bold")
raw = getmd()
note("  B3b md=%s" % json.dumps(raw, ensure_ascii=False)[:200])
if "<strong>" in raw and "<code><strong>" in raw.replace("</strong></code>", "</strong></code>"):
    check("B3b HTML 单元格码内加粗被拒绝", False, "code 内嵌 strong：%s" % raw[:120])
else:
    check("B3b HTML 单元格码内加粗被拒绝", "<code><strong>" not in raw, raw[:120])

note("B4 管道单元格下划线（FMT-12）")
setmd("| 表头 |\n| --- |\n| 甲乙 |")
sel_nth("#editor td", 0, 0, 2, ms=300)
apply_act("underline")
raw = getraw()
row = next((r for r in raw if "甲" in r), "")   # v3.38 甄别：整表一条 raw
check("B4 下划线走 <u>", row is not None and "<u>甲乙</u>" in row,
      "row=%s" % json.dumps(row, ensure_ascii=False))

note("B5 单元格清除格式")
setmd("| 表头 |\n| --- |\n| **甲**和*乙* |")
sel_nth("#editor td", 0, 0, 1, ms=300)
apply_act("clearfmt")
raw = getraw()
row = next((r for r in raw if "甲" in r), "")   # v3.38 甄别：整表一条 raw
check("B5 清除选中处加粗（乙斜体保留）", row is not None and "| 甲和*乙* |" in row,
      "row=%s" % json.dumps(row, ensure_ascii=False))

note("B6 单元格链接")
setmd("| 表头 |\n| --- |\n| 甲乙 |")
sel_nth("#editor td", 0, 0, 2, ms=300)
apply_act("link")
raw = getraw()
row = next((r for r in raw if "甲" in r), "")   # v3.38 甄别：整表一条 raw
check("B6 链接写入", row is not None and URL in row,
      "row=%s" % json.dumps(row, ensure_ascii=False))

note("========== C 组：delOnly 特殊块 delblk ==========")

note("C1 代码块选区 → 删除整个块")
setmd("段落前\n\n```python\nprint('x')\n```\n\n段落后")
sel_nth("#editor .codeblock", 0, 0, 5)   # v3.38 甄别：选 .codeblock 整体（同 m98b R2b 口径）
st = fb_state()
check("C1 条为仅删除", st.get("btns") == ["删除整个块"], str(st.get("btns")))
apply_act("delblk")
raw = getraw()
check("C1 块已删除", all("print" not in r for r in raw), json.dumps(raw, ensure_ascii=False)[:120])
check("C1 有撤销 toast", "撤销" in toast(), toast())

note("C2 mathdl 块选区 → 删除")
setmd("段落前\n\n$$\nx^2\n$$\n\n段落后")
sel_node("#editor .mathblock", 0)
st = fb_state()
if st.get("show"):
    check("C2 条为仅删除", st.get("btns") == ["删除整个块"], str(st.get("btns")))
    apply_act("delblk")
    raw = getraw()
    check("C2 mathdl 已删除", all("x^2" not in r for r in raw), json.dumps(raw, ensure_ascii=False)[:120])
else:
    note("  C2 mathdl 选区未构造，观察")

note("========== D 组：正文守卫回归 + 跨块观察 ==========")

note("D1 跨列表项选区 → 拒绝（LIST-1 止血回归）")
setmd("- 第一项文字\n- 第二项文字")
sel_nth("#editor li", 0, 0, 5, ms=280)
# 手动扩展选区到第二个 li（TreeWalker 到 li[1]）
js("(function(){var lis=document.querySelectorAll('#editor li');"
   "if(lis.length<2)return 'no-lis';"
   "var rg=document.createRange();rg.setStart(lis[0].childNodes[0]||lis[0],0);"
   "var t2=lis[1];var w=document.createTreeWalker(t2,NodeFilter.SHOW_TEXT);var last=w.lastChild?"
   "(function(){var n=null;while(w.nextNode())n=w.currentNode;return n})():t2;"
   "if(!last)return 'no-text';rg.setEnd(last,last.nodeValue.length);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
   "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
wait(300)
st = fb_state()
if st.get("show") and "粗体" in st.get("btns", []):
    apply_act("bold")
    raw = getraw()
    joined = "\n".join(raw)
    ok = ("==第一" not in joined and "**第一" not in joined and "====" not in joined)
    check("D1 跨行选区未产生脏标记", ok, json.dumps(raw, ensure_ascii=False)[:150])
else:
    note("  D1 跨 li 选区未出格式条（show=%s btns=%s），行为记观察" % (st.get("show"), st.get("btns")))

note("D2 跨块标题选区（标题计数 vs 动作范围）观察")
setmd("# 标题一\n\n正文段落甲\n\n## 标题二\n\n正文段落乙")
js("(function(){var ed=document.getElementById('editor');"
   "var h1=ed.querySelector('h1'),h2=ed.querySelector('h2');"
   "if(!h1||!h2)return 'no-h';"
   "var rg=document.createRange();rg.setStartBefore(h1);rg.setEndAfter(h2);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
   "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
wait(300)
st = fb_state()
note("  D2 跨块选区浮条=%s" % json.dumps(st, ensure_ascii=False))
if st.get("show"):
    note("  D2 尾部=%s（观察：标题计数与实际作用范围是否一致）" % st.get("tail"))
    before = getmd()
    apply_act("bold")
    after = getmd()
    changed_blocks = [i for i, (a, b) in enumerate(zip(before.split("\n\n"), after.split("\n\n"))) if a != b] if before != after else []
    note("  D2 动作后变化块=%s raw片段=%s" % (changed_blocks, json.dumps(after, ensure_ascii=False)[:180]))

note("========== 汇总 ==========")
log("SUMMARY total=%d fail=%d" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABN " + a)
print("DONE total=%d fail=%d" % (TOTAL[0], FAIL[0]))
