# -*- coding: utf-8 -*-
"""m80 行内格式化交互测试（v3.30.19 / v3.31.1）

覆盖动作：加粗 / 斜体 / 删除线 / 高亮 / 行内代码 / 链接 / 清除格式  随机组合
容器位点：H1 标题、列表第 1 项、列表第 2 项、引用块
核心验收：操作后必须回到渲染态（不出现源码态 / 不裸 # - > 前缀 / 不裸 ** == ~~ `）

断言模型：
  A) LIFO toggle 模型算「预期 raw」：同动作作用于最外层 → 去掉，否则再包一层
     · clearfmt → 清空全部行内标记回到裸内容
     · link → 视为一层外壳 ('[' , '](url)')
  B) 渲染态不变量：块内不得残留 .raw-edit；渲染明文不得以 '# ' / '- ' / '> ' 开头
  C) 泄漏不变量：stack 不含 code 时，渲染明文不得出现 * ~ = ` [ ] 等标记字符
     （含 code 时内部标记按 Markdown 规范字面显示，属正确行为，跳过该条）
  D) 逆序取消必须完全还原到初始 raw（格式零残留）
"""
import json, os, random, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m80.txt")
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


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    r = jj("window.__raw()")
    return r.get("raw", [""]) if isinstance(r, dict) else [""]


def blkinfo(idx=0):
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return JSON.stringify({err:1});"
           "return JSON.stringify({t:b.textContent||'',tag:b.tagName,"
           "hasRaw:!!b.querySelector('.raw-edit'),cls:b.className})})()")
    return r


def sel_range(blk, a, b, ms=250):
    js("(function(){var blk=document.querySelectorAll('#editor .blk')[" + str(blk) + "];"
       "if(!blk)return 'no-blk';"
       "var w=document.createTreeWalker(blk,NodeFilter.SHOW_TEXT);"
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


def sel_li(li, blk=0, ms=250):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(blk) + "];"
       "if(!b)return 'no-blk';var li=b.querySelectorAll('li')[" + str(li) + "];"
       "if(!li)return 'no-li';var rg=document.createRange();rg.selectNodeContents(li);"
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
        wait(ms + 120)
        return
    js("window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


def focus_end(sel, ms=260):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';el.focus();"
       "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);var last=null,n;"
       "while(n=w.nextNode()){last=n;}"
       "var rg=document.createRange();"
       "if(last){rg.setStart(last,last.nodeValue.length);rg.collapse(true);}"
       "else{rg.selectNodeContents(el);rg.collapse(false);}"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(ms)


def type_text(text, ms=380):
    js("(function(){document.execCommand('insertText',false," + json.dumps(text) + ");return 'ok'})()")
    wait(ms)


PAIR = {
    "bold": ("**", "**"), "italic": ("*", "*"), "strike": ("~~", "~~"),
    "mark": ("==", "=="), "code": ("`", "`"), "link": ("[", "](" + URL + ")"),
}
CN = {"bold": "加粗B", "italic": "斜体I", "strike": "删除线S", "mark": "高亮A",
      "code": "行内码", "link": "链接", "clearfmt": "清除格式"}
MARK_CHARS = ("*", "~", "=", "`", "[", "]")


def expect_of(content, stack):
    opens = "".join(PAIR[a][0] for a in stack if a in PAIR)
    closes = "".join(PAIR[a][1] for a in reversed(stack) if a in PAIR)
    return opens + content + closes


def toggle_stack(stack, action):
    if action == "clearfmt":
        return []
    if stack and stack[-1] == action:
        return stack[:-1]
    return stack + [action]


def render_state_ok(info):
    if info.get("hasRaw"):
        return False, "块停留在源码态(.raw-edit)"
    t = str(info.get("t", ""))
    for pre in ("# ", "- ", "> "):
        if t.startswith(pre):
            return False, "渲染明文残留 Markdown 前缀 %r" % pre
    return True, ""


wait(2600)

rnd = random.Random(20260928)
ACTS = ["bold", "italic", "strike", "mark", "code", "clearfmt"]
SEQ = [rnd.choice(ACTS) for _ in range(7)]
SEQ.insert(3, "link")
SEQ.insert(6, "clearfmt")
note("随机序列 = " + " -> ".join(CN[a] for a in SEQ))
note("序列明细 = " + ",".join(SEQ))

H1_INIT = "# 演示标题这是新输入的内容"
H1_C = "这是新输入的"
LIST_INIT = "- 第一项内容文本\n- 第二项内容文本"
C1, C2 = "第一项内容文本", "第二项内容文本"
Q_INIT = "> 引用块内的文字内容"
Q_C = "引用块内的文字内容"


def run_seq(tag, select_fn, get_line, expect_base, content, blkidx=0, extra=None):
    stack = []
    for i, act in enumerate(SEQ):
        select_fn()
        apply_act(act)
        stack = toggle_stack(stack, act)
        after = getraw()
        line = get_line(after)
        exp = expect_base + expect_of(content, stack)
        inf = blkinfo(blkidx)
        okline = line == exp
        step = "%s.%02d %s" % (tag, i + 1, CN[act])
        log("  %s 预期=%s 实际=%s %s" % (step, json.dumps(exp, ensure_ascii=False),
                                        json.dumps(line, ensure_ascii=False),
                                        "OK" if okline else "DIFF"))
        check(step + " 标记落位", okline,
              "预期=%s 实际=%s" % (json.dumps(exp, ensure_ascii=False), json.dumps(line, ensure_ascii=False)))
        okst, why = render_state_ok(inf)
        check(step + " 渲染态", okst, why + " text=" + json.dumps(str(inf.get("t")), ensure_ascii=False)[:150])
        if "code" not in stack:
            bad = [c for c in MARK_CHARS if c in str(inf.get("t", ""))]
            check(step + " 无字面标记", not bad,
                  "泄漏=%s text=%s" % ("".join(bad), json.dumps(str(inf.get("t")), ensure_ascii=False)[:150]))
        if extra:
            check(step + " 结构守恒", extra(after), json.dumps(after[0] if after else "", ensure_ascii=False))
    for act in reversed(SEQ):
        select_fn()
        apply_act(act)
        wait(150)
    return getraw()


note("========== 场景 1：H1 标题 ==========")
setmd("# 演示标题")
st = blkinfo(0)
check("H1.0 标题渲染为 h1", str(st.get("tag")) == "H1", "tag=%s cls=%s" % (st.get("tag"), st.get("cls")))
focus_end("#editor h1", 300)
type_text("这是新输入的内容", 450)
r0 = getraw()
check("H1.1 输入生效且保持一级标题", len(r0) == 1 and r0[0] == H1_INIT, json.dumps(r0, ensure_ascii=False))

setmd(H1_INIT)
aft = run_seq("H1", lambda: sel_range(0, 4, 9), lambda a: (a[0] if a else ""), "# ", H1_C, 0)
check("H1 逆序取消完全还原", aft[0] == H1_INIT, "actual=%s" % json.dumps(aft[0], ensure_ascii=False))


def l0(after):
    ls = after[0].split("\n") if after else []
    return ls[0] if ls else ""


def l1(after):
    ls = after[0].split("\n") if after else []
    return ls[1] if len(ls) > 1 else ""


def q_line(after):
    v = after[0] if after else ""
    return v[2:] if v.startswith("> ") else v


note("========== 场景 2：列表第 1 项 ==========")
setmd(LIST_INIT)
aft = run_seq("L1", lambda: sel_li(0), l0, "- ", C1, 0,
              lambda a: len(a[0].split("\n")) == 2 and a[0].split("\n")[1] == "- " + C2)
check("L1 逆序取消完全还原", aft[0] == LIST_INIT, "actual=%s" % json.dumps(aft[0], ensure_ascii=False))

note("========== 场景 3：列表第 2 项 ==========")
setmd(LIST_INIT)
aft = run_seq("L2", lambda: sel_li(1), l1, "- ", C2, 0,
              lambda a: len(a[0].split("\n")) == 2 and a[0].split("\n")[0] == "- " + C1)
check("L2 逆序取消完全还原", aft[0] == LIST_INIT, "actual=%s" % json.dumps(aft[0], ensure_ascii=False))

note("========== 场景 4：引用块 ==========")
setmd(Q_INIT)
st = blkinfo(0)
note("Q.0 初始 blk=%s" % json.dumps(st, ensure_ascii=False))
aft = run_seq("Q", lambda: sel_range(0, 0, len(Q_C)), q_line, "", Q_C, 0,
              lambda a: bool(a and a[0].startswith("> ")))
check("Q 引用 > 前缀保持", bool(aft and aft[0].startswith("> ")), json.dumps(aft[0] if aft else "", ensure_ascii=False))
check("Q 逆序取消完全还原", aft[0] == Q_INIT, "actual=%s" % json.dumps(aft[0], ensure_ascii=False))

note("========== 场景 5：单动作应用/取消闭环（6 项 x 4 容器）==========")
SITES = [
    ("标题", H1_INIT, lambda: sel_range(0, 4, 9), H1_C, lambda a: (a[0] if a else ""), "# "),
    ("列表1", LIST_INIT, lambda: sel_li(0), C1, l0, "- "),
    ("列表2", LIST_INIT, lambda: sel_li(1), C2, l1, "- "),
    ("引用", Q_INIT, lambda: sel_range(0, 0, len(Q_C)), Q_C, q_line, ""),
]
for sname, init, selfn, content, getter, base in SITES:
    for act in ["bold", "italic", "strike", "mark", "code", "link"]:
        setmd(init)
        selfn()
        apply_act(act)
        after = getraw()
        on_line = getter(after)
        exp_on = base + expect_of(content, [act])
        check("单/%s/%s 应用" % (sname, CN[act]), on_line == exp_on,
              "预期=%s 实际=%s" % (json.dumps(exp_on, ensure_ascii=False), json.dumps(on_line, ensure_ascii=False)))
        selfn()
        apply_act(act)
        off = getraw()
        off_line = getter(off)
        exp_off = base + expect_of(content, toggle_stack([act], act))
        check("单/%s/%s 取消无残留" % (sname, CN[act]), off_line == exp_off,
              "预期=%s 实际=%s" % (json.dumps(exp_off, ensure_ascii=False), json.dumps(off_line, ensure_ascii=False)))

log("")
log("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
if ABN:
    log("--- 异常清单（%d）---" % len(ABN))
    for a in ABN:
        log("ABN " + a)
else:
    log("全部通过，无异常")
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
