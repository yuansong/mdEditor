# -*- coding: utf-8 -*-
"""m81 行内格式化：修正版随机组合 + 链接/清除格式隔离定位

修正点（相对 m80）：
 - H1 容器改用「整行选区」，content 与 get_line 口径一致（消除预期字符串偏差）
 - H1 断言改判 class 含 b-h1（标题块容器是 DIV.blk.b-h1，内含 h1）
Part 2 隔离定位：
 I1~I4 不同嵌套深度下加链接，观察链接文字是否比选区短
 I5 链接二次点击是否取消（toggle）
 I6~I7 清除格式是否真的生效
"""
import json, os, random, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m81.txt")
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


def setmd(md, ms=780):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    r = jj("window.__raw()")
    return r.get("raw", [""]) if isinstance(r, dict) else [""]


def blkinfo(idx=0):
    return jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
              "if(!b)return JSON.stringify({err:1});"
              "return JSON.stringify({t:b.textContent||'',cls:b.className,"
              "hasRaw:!!b.querySelector('.raw-edit'),"
              "h1:!!b.querySelector('h1'),"
              "txtnodes:(function(){var w=document.createTreeWalker(b,NodeFilter.SHOW_TEXT),n=0,L=[];"
              "while(w.nextNode()){n++;if(L.length<8)L.push([n-1,w.currentNode.nodeValue]);}"
              "return L})()})})()")


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


def sellen(ms=120):
    return js("(function(){var s=window.getSelection();"
              "return s&&s.rangeCount?String(s.toString().length):'-1'})()")


def apply_act(action, ms=330):
    if action == "link":
        js("window.__applyFloat('link')")
        wait(ms)
        js("(function(){var i=document.getElementById('link-url');"
           "if(!i)return 'no-input';i.value=" + json.dumps(URL) + ";"
           "var b=document.getElementById('link-ok');"
           "if(!b)return 'no-btn';b.click();return 'ok'})()")
        wait(ms + 100)
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


PAIR = {"bold": ("**", "**"), "italic": ("*", "*"), "strike": ("~~", "~~"),
        "mark": ("==", "=="), "code": ("`", "`"), "link": ("[", "](" + URL + ")")}
CN = {"bold": "加粗B", "italic": "斜体I", "strike": "删除线S", "mark": "高亮A",
      "code": "行内码", "link": "链接", "clearfmt": "清除格式"}
MARK_CHARS = ("*", "~", "=", "`", "[", "]")


def expect_of(content, stack):
    o = "".join(PAIR[a][0] for a in stack if a in PAIR)
    c = "".join(PAIR[a][1] for a in reversed(stack) if a in PAIR)
    return o + content + c


def toggle_stack(stack, action):
    if action == "clearfmt":
        return []
    # v3.31.2 FMT-1：行内代码内叠加行内格式被拒绝（code/clearfmt 除外）→ 栈不变
    if "code" in stack and action not in ("code", "clearfmt"):
        return stack
    if stack and stack[-1] == action:
        return stack[:-1]
    return stack + [action]


def render_state_ok(info):
    if info.get("hasRaw"):
        return False, "停留在源码态(.raw-edit)"
    t = str(info.get("t", ""))
    for p in ("# ", "- ", "> "):
        if t.startswith(p):
            return False, "渲染明文残留前缀 %r" % p
    return True, ""


wait(2600)

H1_INIT = "# 演示标题这是新输入的内容"
H1_C = "演示标题这是新输入的内容"
H1_SELECT = lambda: sel_range(0, 0, len(H1_C))
LIST_INIT = "- 第一项内容文本\n- 第二项内容文本"
C1, C2 = "第一项内容文本", "第二项内容文本"
Q_INIT = "> 引用块内的文字内容"
Q_C = "引用块内的文字内容"


def h1_line(a):
    v = a[0] if a else ""
    return v[2:] if v.startswith("# ") else v


def l0(a):
    ls = a[0].split("\n") if a else []
    return ls[0][2:] if ls and ls[0].startswith("- ") else (ls[0] if ls else "")


def l1(a):
    ls = a[0].split("\n") if a else []
    v = ls[1] if len(ls) > 1 else ""
    return v[2:] if v.startswith("- ") else v


def q_line(a):
    v = a[0] if a else ""
    return v[2:] if v.startswith("> ") else v


note("========== Part1：修正后随机组合序列 ==========")
rnd = random.Random(20260928)
ACTS = ["bold", "italic", "strike", "mark", "code", "clearfmt"]
SEQ = [rnd.choice(ACTS) for _ in range(7)]
SEQ.insert(3, "link")
SEQ.insert(6, "clearfmt")
note("随机序列 = " + " -> ".join(CN[a] for a in SEQ))
note("序列明细 = " + ",".join(SEQ))

note("--- 场景 1：H1 标题 ---")
setmd("# 演示标题")
st = blkinfo(0)
check("H1.0 标题渲染（含 h1 元素）", bool(st.get("h1")) or "b-h1" in str(st.get("cls", "")),
      "cls=%s h1=%s" % (st.get("cls"), st.get("h1")))
focus_end("#editor h1", 300)
type_text("这是新输入的内容", 450)
r0 = getraw()
check("H1.1 输入生效且保持一级标题", len(r0) == 1 and r0[0] == H1_INIT, json.dumps(r0, ensure_ascii=False))

setmd(H1_INIT)
stack = []
for i, act in enumerate(SEQ):
    H1_SELECT()
    apply_act(act)
    stack = toggle_stack(stack, act)
    after = getraw()
    line = h1_line(after)
    exp = expect_of(H1_C, stack)
    inf = blkinfo(0)
    okok = line == exp
    step = "H1.%02d %s" % (i + 1, CN[act])
    log("  %s 预期=%s 实际=%s %s" % (step, json.dumps(exp, ensure_ascii=False),
                                    json.dumps(line, ensure_ascii=False), "OK" if okok else "DIFF"))
    check(step + " 落位", okok, "预期=%s 实际=%s" % (json.dumps(exp, ensure_ascii=False), json.dumps(line, ensure_ascii=False)))
    ok, why = render_state_ok(inf)
    check(step + " 渲染态", ok, why + " text=" + json.dumps(str(inf.get("t")), ensure_ascii=False)[:130])
    if "code" not in stack:
        bad = [c for c in MARK_CHARS if c in str(inf.get("t", ""))]
        check(step + " 无字面标记", not bad, "泄漏=%s text=%s" % ("".join(bad), json.dumps(str(inf.get("t")), ensure_ascii=False)[:130]))
for act in reversed(SEQ):
    H1_SELECT()
    apply_act(act)
    wait(140)
aft = getraw()
check("H1 逆序取消完全还原", aft[0] == H1_INIT, "actual=%s" % json.dumps(aft[0], ensure_ascii=False))

note("--- 场景 2：列表第 1 项 ---")
setmd(LIST_INIT)
stack = []
for i, act in enumerate(SEQ):
    sel_li(0)
    apply_act(act)
    stack = toggle_stack(stack, act)
    after = getraw()
    line = l0(after)
    exp = expect_of(C1, stack)
    step = "L1.%02d %s" % (i + 1, CN[act])
    log("  %s 预期=%s 实际=%s %s" % (step, json.dumps(exp, ensure_ascii=False),
                                    json.dumps(line, ensure_ascii=False), "OK" if line == exp else "DIFF"))
    check(step + " 落位", line == exp, "预期=%s 实际=%s" % (json.dumps(exp, ensure_ascii=False), json.dumps(line, ensure_ascii=False)))
    ls = after[0].split("\n") if after else []
    check(step + " 第二项未被污染", len(ls) == 2 and ls[1] == "- " + C2, json.dumps(after[0], ensure_ascii=False))
    inf = blkinfo(0)
    ok, why = render_state_ok(inf)
    check(step + " 渲染态", ok, why)
for act in reversed(SEQ):
    sel_li(0)
    apply_act(act)
    wait(140)
aft = getraw()
check("L1 逆序取消完全还原", aft[0] == LIST_INIT, "actual=%s" % json.dumps(aft[0], ensure_ascii=False))

note("--- 场景 3：列表第 2 项 ---")
setmd(LIST_INIT)
stack = []
for i, act in enumerate(SEQ):
    sel_li(1)
    apply_act(act)
    stack = toggle_stack(stack, act)
    after = getraw()
    line = l1(after)
    exp = expect_of(C2, stack)
    step = "L2.%02d %s" % (i + 1, CN[act])
    log("  %s 预期=%s 实际=%s %s" % (step, json.dumps(exp, ensure_ascii=False),
                                    json.dumps(line, ensure_ascii=False), "OK" if line == exp else "DIFF"))
    check(step + " 落位", line == exp, "预期=%s 实际=%s" % (json.dumps(exp, ensure_ascii=False), json.dumps(line, ensure_ascii=False)))
    ls = after[0].split("\n") if after else []
    check(step + " 第一项未被污染", len(ls) == 2 and ls[0] == "- " + C1, json.dumps(after[0], ensure_ascii=False))
for act in reversed(SEQ):
    sel_li(1)
    apply_act(act)
    wait(140)
aft = getraw()
check("L2 逆序取消完全还原", aft[0] == LIST_INIT, "actual=%s" % json.dumps(aft[0], ensure_ascii=False))

note("--- 场景 4：引用块 ---")
setmd(Q_INIT)
stack = []
for i, act in enumerate(SEQ):
    sel_range(0, 0, len(Q_C))
    apply_act(act)
    stack = toggle_stack(stack, act)
    after = getraw()
    line = q_line(after)
    exp = expect_of(Q_C, stack)
    step = "Q.%02d %s" % (i + 1, CN[act])
    log("  %s 预期=%s 实际=%s %s" % (step, json.dumps(exp, ensure_ascii=False),
                                    json.dumps(line, ensure_ascii=False), "OK" if line == exp else "DIFF"))
    check(step + " 落位", line == exp, "预期=%s 实际=%s" % (json.dumps(exp, ensure_ascii=False), json.dumps(line, ensure_ascii=False)))
    check(step + " > 前缀保持", bool(after and after[0].startswith("> ")), json.dumps(after[0] if after else "", ensure_ascii=False))
    inf = blkinfo(0)
    ok, why = render_state_ok(inf)
    check(step + " 渲染态", ok, why)
    if "code" not in stack:
        bad = [c for c in MARK_CHARS if c in str(inf.get("t", ""))]
        check(step + " 无字面标记", not bad, "泄漏=%s text=%s" % ("".join(bad), json.dumps(str(inf.get("t")), ensure_ascii=False)[:130]))
for act in reversed(SEQ):
    sel_range(0, 0, len(Q_C))
    apply_act(act)
    wait(140)
aft = getraw()
check("Q 逆序取消完全还原", aft[0] == Q_INIT, "actual=%s" % json.dumps(aft[0], ensure_ascii=False))

note("--- 场景 5：单动作开关闭环（6 项 x 4 容器）---")
SITES = [("标题", H1_INIT, H1_SELECT, H1_C, h1_line),
         ("列表1", LIST_INIT, lambda: sel_li(0), C1, l0),
         ("列表2", LIST_INIT, lambda: sel_li(1), C2, l1),
         ("引用", Q_INIT, lambda: sel_range(0, 0, len(Q_C)), Q_C, q_line)]
for sname, init, selfn, content, getter in SITES:
    for act in ["bold", "italic", "strike", "mark", "code", "link"]:
        setmd(init)
        selfn()
        apply_act(act)
        after = getraw()
        got = getter(after)
        exp = expect_of(content, [act])
        check("单/%s/%s 应用" % (sname, CN[act]), got == exp,
              "预期=%s 实际=%s" % (json.dumps(exp, ensure_ascii=False), json.dumps(got, ensure_ascii=False)))
        selfn()
        apply_act(act)
        off = getraw()
        got2 = getter(off)
        exp2 = expect_of(content, toggle_stack([act], act))
        check("单/%s/%s 取消" % (sname, CN[act]), got2 == exp2,
              "预期=%s 实际=%s" % (json.dumps(exp2, ensure_ascii=False), json.dumps(got2, ensure_ascii=False)))

# =========================================================
note("========== Part2：链接 / 清除格式 隔离定位 ==========")


def link_text_len(after_line):
    import re as _re
    m = _re.search(r"\[([^\]]*)\]\(", after_line or "")
    return len(m.group(1)) if m else -1


# I1 干净状态加链接
note("--- I1 干净状态加链接（4 容器）---")
for sname, init, selfn, content, getter in SITES:
    setmd(init)
    selfn()
    sl = sellen()
    apply_act("link")
    after = getraw()
    got = getter(after)
    tl = link_text_len(got)
    log("  I1/%s 选区长度=%s 链接文字长度=%s line=%s" % (sname, sl, tl, json.dumps(got, ensure_ascii=False)))
    check("I1/%s 链接覆盖完整选区（%s字）" % (sname, len(content)), tl == len(content),
          "选区=%s 链接文字=%s 实际=%s" % (sl, tl, json.dumps(got, ensure_ascii=False)))

# I2 一层嵌套后加链接
note("--- I2 先加 1 层标记再加链接 ---")
for pre in ["bold", "strike", "mark", "code"]:
    setmd(Q_INIT)
    sel_range(0, 0, len(Q_C))
    apply_act(pre)
    sel_range(0, 0, len(Q_C))
    sl = sellen()
    apply_act("link")
    after = getraw()
    got = q_line(after)
    if pre == "code":
        # v3.31.2 FMT-1：行内码内加链接被拒绝（源码不变，不再错位包裹）
        check("I2/code 行内码内加链接被拒绝（源码不变）", got == "`" + Q_C + "`",
              "actual=%s" % json.dumps(got, ensure_ascii=False))
        continue
    tl = link_text_len(got)
    log("  I2/%s 选区=%s 链接文字=%s line=%s" % (pre, sl, tl, json.dumps(got, ensure_ascii=False)))
    check("I2/%s 链接覆盖完整选区（9字）" % pre, tl == len(Q_C),
          "选区=%s 链接文字=%s 实际=%s" % (sl, tl, json.dumps(got, ensure_ascii=False)))

# I3 两层嵌套后加链接（原失败场景）
note("--- I3 code + strike 两层嵌套后加链接 ---")
setmd(Q_INIT)
sel_range(0, 0, len(Q_C))
apply_act("code")
sel_range(0, 0, len(Q_C))
apply_act("strike")
note("  I3 前置 raw=%s" % json.dumps(getraw(), ensure_ascii=False))
sel_range(0, 0, len(Q_C))
sl = sellen()
apply_act("link")
after = getraw()
got = q_line(after)
log("  I3 选区=%s line=%s" % (sl, json.dumps(got, ensure_ascii=False)))
# v3.31.2 FMT-1：code+strike 后加链接被拒绝 —— 源码保持 code 形态，不再错位损坏
check("I3 行内码内加链接被拒绝（源码不变、零污染）", got == "`" + Q_C + "`",
      "actual=%s" % json.dumps(got, ensure_ascii=False))

# I4 链接二次点击（toggle 取消）
note("--- I4 链接二次点击是否取消 ---")
setmd(Q_INIT)
sel_range(0, 0, len(Q_C))
apply_act("link")
r1 = getraw()[0]
note("  I4 第一次=%s" % json.dumps(r1, ensure_ascii=False))
sel_range(0, 0, len(Q_C))
apply_act("link")
r2 = getraw()[0]
note("  I4 第二次=%s" % json.dumps(r2, ensure_ascii=False))
check("I4 链接可二次点击取消（不嵌套）", r2 == Q_INIT, "actual=%s" % json.dumps(r2, ensure_ascii=False))

# I5 清除格式有效性
note("--- I5 清除格式（T×）有效性 ---")
cases = [
    ("单行内", [("bold",), ("mark",), ("code",), ("link",)], False),
    ("嵌套后", [("bold", "mark"), ("code", "strike"), ("bold", "link")], True),
]
for cname, combos, _ in cases:
    for combo in combos:
        setmd(Q_INIT)
        sel_range(0, 0, len(Q_C))
        for a in combo:
            sel_range(0, 0, len(Q_C))
            apply_act(a)
        before = getraw()[0]
        sel_range(0, 0, len(Q_C))
        apply_act("clearfmt")
        after = getraw()[0]
        log("  I5/%s/%s before=%s after=%s" % (
            cname, "+".join(combo), json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))
        check("I5/%s/%s 清除格式生效（回到裸文本）" % (cname, "+".join(combo)), after == Q_INIT,
              "before=%s after=%s" % (json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))

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
