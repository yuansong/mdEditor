# -*- coding: utf-8 -*-
"""m97 标题格式化完整回归：重复 toggle / 多格式组合 / 富标题交错 / 列表·引用·脚注·术语

用户要求（2026-09-30）：
 1) 先输入标题再输入正文；对标题应用不同组合的格式化按钮操作（含重复点击同一格式化按钮）
 2) 验证无论怎样组合或重复操作，内容都不出现源码（原始 Markdown）状态，渲染始终正确
 3) 标题若发现 bug，同法扩展列表/引用；脚注与术语（定义列表）同场景验证
衔接：_m96 已发现 S5 富标题 strike 交错 raw（# **~~已加粗**和普通~~）、
      S6 源码态 clearfmt 后停留源码编辑态（v3.31.3 均未修）
版本：src v3.31.3（2026-09-30 01:08，644394B，sha16 A9C1C25BD6529988）
结果：tests/_m97.txt
"""
import json, os, re, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m97.txt")
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


def sel_nth(selector, idx, a, b, ms=240):
    """在 selector 匹配的第 idx 个元素内部，按渲染文本偏移 [a,b) 构造选区"""
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


def apply_act(action, ms=330):
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


def stblk(selector, idx=0):
    """容器状态：isRaw / blk 类名 / 元素全文 / 各 inline 标签的覆盖文本"""
    return jj("(function(){var el=document.querySelectorAll(" + json.dumps(selector) + ")[" + str(idx) + "];"
              "if(!el)return JSON.stringify({err:1});"
              "var blk=el.closest('.blk');"
              "var tags=['strong','b','em','i','del','s','mark','code','a'];var cov={};"
              "for(var i=0;i<tags.length;i++){var x=el.querySelector(tags[i]);"
              "cov[tags[i]]=x?x.textContent:null;}"
              "return JSON.stringify({isRaw:blk?blk.classList.contains('raw-edit'):null,"
              "cls:blk?blk.className:'',txt:el.textContent,cov:cov})})()")


PAIR = {"bold": ("**", "**"), "italic": ("*", "*"), "strike": ("~~", "~~"),
        "mark": ("==", "=="), "code": ("`", "`"), "link": ("[", "](" + URL + ")")}
CN = {"bold": "加粗", "italic": "斜体", "strike": "删除线", "mark": "高亮",
      "code": "行内码", "link": "链接", "clearfmt": "清除格式"}
MARK_CHARS = ("*", "~", "=", "`", "[", "]")
TAG_OF = {"bold": ("strong", "b"), "italic": ("em", "i"), "strike": ("del", "s"),
          "mark": ("mark",), "code": ("code",), "link": ("a",)}


def leak_of(txt):
    return [c for c in MARK_CHARS if c in str(txt or "")]


def expect_of(content, stack):
    o = "".join(PAIR[a][0] for a in stack if a in PAIR)
    c = "".join(PAIR[a][1] for a in reversed(stack) if a in PAIR)
    return o + content + c


def toggle_stack(stack, action):
    if action == "clearfmt":
        return []
    if "code" in stack and action not in ("code", "clearfmt"):
        return stack  # FMT-1 行内码内拒绝叠加
    if stack and stack[-1] == action:
        return stack[:-1]
    return stack + [action]


def cover_check(step, inf, want, content):
    """断言 want 中每个格式对应的 inline 标签存在且覆盖全文；其余标签不出现"""
    txt = str(inf.get("txt", ""))
    for fmt in ("bold", "italic", "strike", "mark", "code", "link"):
        tags = TAG_OF[fmt]
        got = None
        for t in tags:
            if inf.get("cov", {}).get(t):
                got = got or inf["cov"][t]
        if fmt in want:
            check("%s %s覆盖全文" % (step, CN[fmt]), got == content,
                  "got=%s txt=%s" % (json.dumps(got, ensure_ascii=False), json.dumps(txt, ensure_ascii=False)))
        else:
            check("%s 无多余%s" % (step, CN[fmt]), got is None,
                  "got=%s txt=%s" % (json.dumps(got, ensure_ascii=False), json.dumps(txt, ensure_ascii=False)))


def step_state(step, selector, want_tags=(), content=None, blk_cls="b-h1", idx=0, leak=True):
    """通用渲染态断言：非源码态 + 类名 + 字面标记泄漏"""
    inf = stblk(selector, idx)
    if inf.get("err"):
        check(step + " 容器存在", False, "selector=%s err" % selector)
        return inf
    check(step + " 保持渲染态", inf.get("isRaw") is False,
          "isRaw=%s cls=%s" % (inf.get("isRaw"), str(inf.get("cls"))[:80]))
    check(step + " 块类型保持(%s)" % blk_cls, blk_cls in str(inf.get("cls", "")),
          "cls=%s" % str(inf.get("cls"))[:80])
    if leak and content:
        lk = leak_of(inf.get("txt"))
        check(step + " 无字面标记", not lk,
              "泄漏=%s txt=%s" % ("".join(lk), json.dumps(str(inf.get("txt")), ensure_ascii=False)[:120]))
        check(step + " 内容完整", str(inf.get("txt", "")) == content,
              "txt=%s 预期=%s" % (json.dumps(str(inf.get("txt")), ensure_ascii=False), content))
    return inf


wait(2600)
for _ in range(20):
    if jj("(function(){return JSON.stringify({a:!!window.__applyFloat,r:!!window.__raw,m:!!window.setMarkdown})})()").get("a"):
        break
    wait(500)

# ============================ A 组：标题重复点击同一按钮 ============================
note("========== A 组：标题重复 toggle（用户核心场景）==========")
H_DOC = "# 甲级标题文字\n\n这是正文段落内容。"
H_SEL = "#editor h1"
HC = "甲级标题文字"

setmd(H_DOC)
note("A0 初始 md=%s" % json.dumps(getmd(), ensure_ascii=False))

seq = [("A01 加粗×1", "bold", ["bold"]),
       ("A02 加粗×2(取消)", "bold", []),
       ("A03 加粗×3(再开)", "bold", ["bold"]),
       ("A04 加粗×4(取消)", "bold", []),
       ("A05 删除线×1", "strike", ["strike"]),
       ("A06 删除线×2(取消)", "strike", []),
       ("A07 删除线×3(再开)", "strike", ["strike"]),
       ("A08 高亮×1", "mark", ["mark"]),
       ("A09 高亮×2(取消)", "mark", []),
       ("A10 高亮×3(再开)", "mark", ["mark"]),
       ("A11 斜体×1", "italic", ["italic"]),
       ("A12 斜体×2(取消)", "italic", []),
       ("A13 行内码×1", "code", ["code"]),
       ("A14 行内码×2(取消)", "code", [])]
stack = []
for name, act, exp_stack in seq:
    stack = toggle_stack(stack, act)
    sel_nth(H_SEL, 0, 0, len(HC))
    apply_act(act)
    exp = "# " + expect_of(HC, exp_stack)
    r = getraw()
    got = r[0] if r else ""
    check(name + " raw", got == exp,
          "预期=%s 实际=%s" % (json.dumps(exp, ensure_ascii=False), json.dumps(got, ensure_ascii=False)))
    want = set(exp_stack) - {"code"}  # code 覆盖检查走 TAG_OF
    inf = step_state(name, H_SEL, content=HC)
    cover_check(name, inf, want, HC)
    check(name + " 正文不污染", "这是正文段落内容。" in getmd(), "md=%s" % json.dumps(getmd(), ensure_ascii=False)[:160])

note("A15 链接开→关（toggle 取消）")
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("link")
exp = "# [甲级标题文字](%s)" % URL
got = getraw()
got = got[0] if got else ""
check("A15 链接×1 raw", got == exp, "实际=%s" % json.dumps(got, ensure_ascii=False))
inf = step_state("A15", H_SEL, content=HC)
cover_check("A15", inf, {"link"}, HC)
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("link")
got = getraw()
got = got[0] if got else ""
check("A15b 链接×2 取消", got == "# " + HC, "实际=%s" % json.dumps(got, ensure_ascii=False))

note("A16 行内码内叠加被拒绝（FMT-1 回归）")
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("code")
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("bold")
got = getraw()
got = got[0] if got else ""
check("A16 code内bold拒绝", got == "# `" + HC + "`", "实际=%s" % json.dumps(got, ensure_ascii=False))
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("code")
got = getraw()
got = got[0] if got else ""
check("A16b code取消复原", got == "# " + HC, "实际=%s" % json.dumps(got, ensure_ascii=False))

note("A17 选区保持连点（真实用户不重选）")
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("bold")
apply_act("bold", 380)  # 不重设选区，模拟用户连点
got = getraw()
got = got[0] if got else ""
check("A17 连点两次复原", got == "# " + HC, "实际=%s" % json.dumps(got, ensure_ascii=False))
inf = step_state("A17", H_SEL, content=HC)

note("A18 清除格式收尾")
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("bold")
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("clearfmt")
got = getraw()
got = got[0] if got else ""
check("A18 clearfmt 复原", got == "# " + HC, "实际=%s" % json.dumps(got, ensure_ascii=False))
step_state("A18", H_SEL, content=HC)

# ============================ B 组：标题多格式组合 ============================
note("========== B 组：标题多格式组合（v3.31.3 FMT-5b 回归）==========")
B_SEQS = [
    ("B01 全叠加 B>I>S>M", ["bold", "italic", "strike", "mark"]),
    ("B02 交叉 B>I>B>I", ["bold", "italic", "bold", "italic"]),
    ("B03 S>B>S (FMT-5b 取外层留内层)", ["strike", "bold", "strike"]),
    ("B04 M>S>M", ["mark", "strike", "mark"]),
    ("B05 B>M>M>B", ["bold", "mark", "mark", "bold"]),
    ("B06 B>link>B>link", ["bold", "link", "bold", "link"]),
]
for name, acts in B_SEQS:
    setmd(H_DOC)
    stack = []
    for act in acts:
        sel_nth(H_SEL, 0, 0, len(HC))
        apply_act(act)
        stack = toggle_stack(stack, act)
    exp = "# " + expect_of(HC, stack)
    r = getraw()
    got = r[0] if r else ""
    check(name + " raw", got == exp,
          "预期=%s 实际=%s" % (json.dumps(exp, ensure_ascii=False), json.dumps(got, ensure_ascii=False)))
    want = set(stack)
    inf = step_state(name, H_SEL, content=HC)
    if inf.get("err") is None and inf.get("isRaw") is False:
        cover_check(name, inf, want, HC)

note("B07 全叠加终态 clearfmt 复原")
setmd(H_DOC)
for act in ["bold", "italic", "strike", "mark"]:
    sel_nth(H_SEL, 0, 0, len(HC))
    apply_act(act)
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("clearfmt")
got = getraw()
got = got[0] if got else ""
check("B07 clearfmt 复原", got == "# " + HC, "实际=%s" % json.dumps(got, ensure_ascii=False))
step_state("B07", H_SEL, content=HC)

note("B08 B>code 嵌套与取消")
setmd(H_DOC)
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("bold")
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("code")
r = getraw()
got = r[0] if r else ""
note("  B08 中间态 raw=%s" % json.dumps(got, ensure_ascii=False))
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("code")
got = getraw()
got = got[0] if got else ""
check("B08 code取消后保留粗体", got == "# **" + HC + "**",
      "实际=%s" % json.dumps(got, ensure_ascii=False))
sel_nth(H_SEL, 0, 0, len(HC))
apply_act("bold")
got = getraw()
got = got[0] if got else ""
check("B08b 再取消粗体复原", got == "# " + HC, "实际=%s" % json.dumps(got, ensure_ascii=False))

# ============================ C 组：富标题交错 raw 深挖（衔接 _m96 S5）============================
note("========== C 组：富标题（部分加粗）交错 raw ==========")
RICH = "# **已加粗**和普通"
FULL = "已加粗和普通"
PART = "已加粗"

note("C1 富标题全选 strike（复现 _m96 S5）")
setmd(RICH)
sel_nth(H_SEL, 0, 0, len(FULL))
apply_act("strike")
r1 = getraw()
r1l = r1[0] if r1 else ""
note("  C1 raw=%s" % json.dumps(r1l, ensure_ascii=False))
inf = step_state("C1", H_SEL, content=FULL)
check("C1 strike 覆盖全文", inf.get("cov", {}).get("del") == FULL or inf.get("cov", {}).get("s") == FULL,
      "cov=%s" % json.dumps(inf.get("cov", {}), ensure_ascii=False))
check("C1 bold 覆盖不变", inf.get("cov", {}).get("strong") == PART,
      "cov=%s" % json.dumps(inf.get("cov", {}), ensure_ascii=False))
check("C1 无字面标记", not leak_of(inf.get("txt")), "txt=%s" % json.dumps(str(inf.get("txt")), ensure_ascii=False))

note("C2 交错 raw 重载往返（保存再打开语义）")
if r1l and r1l != RICH:
    setmd(r1l)
    inf2 = stblk(H_SEL)
    check("C2 重载后渲染态", inf2.get("isRaw") is False and inf2.get("err") is None,
          "inf=%s" % json.dumps(inf2, ensure_ascii=False)[:140])
    check("C2 重载后 strike 覆盖全文", inf2.get("cov", {}).get("del") == FULL or inf2.get("cov", {}).get("s") == FULL,
          "cov=%s" % json.dumps(inf2.get("cov", {}), ensure_ascii=False))
    check("C2 重载后 bold 覆盖不变", inf2.get("cov", {}).get("strong") == PART,
          "cov=%s" % json.dumps(inf2.get("cov", {}), ensure_ascii=False))
    check("C2 重载后无字面标记", not leak_of(inf2.get("txt")),
          "txt=%s" % json.dumps(str(inf2.get("txt")), ensure_ascii=False))
else:
    note("  C2 跳过：raw 未变化或为空")

note("C3 交错态 strike 再点击可逆")
setmd(RICH)
sel_nth(H_SEL, 0, 0, len(FULL))
apply_act("strike")
sel_nth(H_SEL, 0, 0, len(FULL))
apply_act("strike")
got = getraw()
got = got[0] if got else ""
check("C3 strike 再点击还原为 RICH 原状", got == RICH, "实际=%s" % json.dumps(got, ensure_ascii=False))
inf = step_state("C3", H_SEL, content=FULL)
check("C3 bold 覆盖不变", inf.get("cov", {}).get("strong") == PART,
      "cov=%s" % json.dumps(inf.get("cov", {}), ensure_ascii=False))

note("C4 富标题 mark 交错")
setmd(RICH)
sel_nth(H_SEL, 0, 0, len(FULL))
apply_act("mark")
r4 = getraw()
r4l = r4[0] if r4 else ""
note("  C4 raw=%s" % json.dumps(r4l, ensure_ascii=False))
inf = step_state("C4", H_SEL, content=FULL)
check("C4 mark 覆盖全文", inf.get("cov", {}).get("mark") == FULL,
      "cov=%s" % json.dumps(inf.get("cov", {}), ensure_ascii=False))
check("C4 bold 覆盖不变", inf.get("cov", {}).get("strong") == PART,
      "cov=%s" % json.dumps(inf.get("cov", {}), ensure_ascii=False))
if r4l and r4l != RICH:
    setmd(r4l)
    inf2 = stblk(H_SEL)
    check("C4b 重载后 mark 覆盖全文", inf2.get("cov", {}).get("mark") == FULL,
          "cov=%s" % json.dumps(inf2.get("cov", {}), ensure_ascii=False))
    check("C4b 重载后 bold 覆盖不变", inf2.get("cov", {}).get("strong") == PART,
          "cov=%s" % json.dumps(inf2.get("cov", {}), ensure_ascii=False))

# ============================ D 组：标题+正文完整文档（用户原话场景）============================
note("========== D 组：标题+正文完整文档交替格式化 ==========")
D_DOC = "# 甲级标题文字\n\n这是正文第一段的内容。\n\n## 二级标题备用\n\n正文第二段的内容继续。"
BODY1 = "这是正文第一段的内容。"
BODY2 = "正文第二段的内容继续。"
H2C = "二级标题备用"

setmd(D_DOC)
note("D0 blk=%s" % json.dumps(jj("(function(){var bs=document.querySelectorAll('#editor .blk');var r=[];"
                                 "for(var i=0;i<bs.length;i++)r.push([i,bs[i].className,bs[i].textContent]);"
                                 "return JSON.stringify(r)})()"), ensure_ascii=False)[:300])
md0 = getmd()
note("D0 md=%s" % json.dumps(md0, ensure_ascii=False))


def body_ok(md):
    return BODY1 in md and BODY2 in md


def hline(md, prefix):
    for l in md.split("\n"):
        if l.startswith(prefix):
            return l
    return None


sel_nth(H_SEL, 0, 0, len(HC))
apply_act("bold")
md = getmd()
check("D1 h1 加粗行", hline(md, "# ") == "# **甲级标题文字**",
      "实际=%s" % json.dumps(hline(md, "# ") or "", ensure_ascii=False))
check("D1 正文不污染", body_ok(md), "md=%s" % json.dumps(md, ensure_ascii=False)[:200])
step_state("D1", H_SEL, content=HC)

sel_nth(H_SEL, 0, 0, len(HC))
apply_act("strike")
md = getmd()
got1 = hline(md, "# ")
ok1 = got1 in ("# **~~甲级标题文字~~**", "# ~~**甲级标题文字**~~")
check("D2 h1 叠加删除线(允许两种排列)", ok1, "实际=%s" % json.dumps(got1 or "", ensure_ascii=False))
check("D2 正文不污染", body_ok(md), "md=%s" % json.dumps(md, ensure_ascii=False)[:200])

sel_nth("#editor h2", 0, 0, len(H2C))
apply_act("mark")
md = getmd()
check("D3 h2 高亮行", hline(md, "## ") == "## ==二级标题备用==",
      "实际=%s" % json.dumps(hline(md, "## ") or "", ensure_ascii=False))
step_state("D3", "#editor h2", content=H2C, blk_cls="b-h2")

sel_nth(H_SEL, 0, 0, len(HC))
apply_act("clearfmt")
md = getmd()
check("D4 h1 clearfmt 复原", hline(md, "# ") == "# 甲级标题文字",
      "实际=%s" % json.dumps(hline(md, "# ") or "", ensure_ascii=False))
step_state("D4", H_SEL, content=HC)

sel_nth("#editor h2", 0, 0, len(H2C))
apply_act("clearfmt")
md = getmd()
check("D5 h2 clearfmt 复原", hline(md, "## ") == "## 二级标题备用",
      "实际=%s" % json.dumps(hline(md, "## ") or "", ensure_ascii=False))
check("D5 全文复原", md == md0, "md=%s" % json.dumps(md, ensure_ascii=False)[:200])

# ============================ E 组：列表同类（精简）============================
note("========== E 组：列表 ==========")
L_DOC = "- 甲项文字内容\n- 乙项文字内容"
L1 = "甲项文字内容"
setmd(L_DOC)
sel_nth("#editor li", 0, 0, len(L1))
apply_act("bold")
got = getraw()
got = got[0] if got else ""
check("E1 列表项加粗", got == "- **" + L1 + "**\n- 乙项文字内容",
      "实际=%s" % json.dumps(got, ensure_ascii=False))
step_state("E1", "#editor li", content=L1, blk_cls="b-ul", leak=True)

sel_nth("#editor li", 0, 0, len(L1))
apply_act("strike")
sel_nth("#editor li", 0, 0, len(L1))
apply_act("strike")
got = getraw()
got = got[0] if got else ""
check("E2 S>B>S FMT-5b 取外层留内层", got == "- **" + L1 + "**\n- 乙项文字内容",
      "实际=%s" % json.dumps(got, ensure_ascii=False))
check("E2 第二项不污染", "乙项文字内容" in (getraw()[0] if getraw() else ""), "raw=%s" % json.dumps(getraw(), ensure_ascii=False)[:160])

sel_nth("#editor li", 0, 0, len(L1))
apply_act("clearfmt")
got = getraw()
got = got[0] if got else ""
check("E3 clearfmt 复原", got == L_DOC, "实际=%s" % json.dumps(got, ensure_ascii=False))

# ============================ F 组：引用同类（精简）============================
note("========== F 组：引用 ==========")
Q_DOC = "> 引用文字内容"
QC = "引用文字内容"
setmd(Q_DOC)
sel_nth("#editor blockquote", 0, 0, len(QC))
apply_act("bold")
got = getraw()
got = got[0] if got else ""
check("F1 引用加粗", got == "> **" + QC + "**", "实际=%s" % json.dumps(got, ensure_ascii=False))
step_state("F1", "#editor blockquote", content=QC, blk_cls="b-quote")

sel_nth("#editor blockquote", 0, 0, len(QC))
apply_act("strike")
sel_nth("#editor blockquote", 0, 0, len(QC))
apply_act("strike")
got = getraw()
got = got[0] if got else ""
check("F2 S>B>S 取外层留内层", got == "> **" + QC + "**", "实际=%s" % json.dumps(got, ensure_ascii=False))
check("F2 > 前缀保持", got.startswith("> "), "实际=%s" % json.dumps(got, ensure_ascii=False))

sel_nth("#editor blockquote", 0, 0, len(QC))
apply_act("clearfmt")
got = getraw()
got = got[0] if got else ""
check("F3 clearfmt 复原", got == Q_DOC, "实际=%s" % json.dumps(got, ensure_ascii=False))

# ============================ G 组：脚注与定义列表（术语）============================
note("========== G 组：脚注 / 定义列表 ==========")
FN_DOC = "正文引用脚注[^1]的说明文字。\n\n[^1]: 脚注说明内容甲"
FNC = "脚注说明内容甲"
setmd(FN_DOC)
note("G0 md=%s" % json.dumps(getmd(), ensure_ascii=False))
fne = jj("(function(){var e=document.querySelectorAll('#editor .fnedit');"
         "return JSON.stringify({n:e.length,txt:e.length?e[0].textContent:null})})()")
note("G0 fnedit=%s" % json.dumps(fne, ensure_ascii=False))

if fne.get("n"):
    sel_nth("#editor .fnedit", 0, 0, len(FNC))
    apply_act("bold")
    md = getmd()
    fnline = None
    for l in md.split("\n"):
        if l.startswith("[^1]:"):
            fnline = l
    check("G1 脚注说明加粗", fnline == "[^1]: **" + FNC + "**",
          "实际=%s" % json.dumps(fnline or "", ensure_ascii=False))
    step_state("G1", "#editor .fnedit", content=FNC, blk_cls="b-p")

    sel_nth("#editor .fnedit", 0, 0, len(FNC))
    apply_act("strike")
    sel_nth("#editor .fnedit", 0, 0, len(FNC))
    apply_act("strike")
    md = getmd()
    fnline = None
    for l in md.split("\n"):
        if l.startswith("[^1]:"):
            fnline = l
    check("G2 脚注 S>B>S 取外层留内层", fnline == "[^1]: **" + FNC + "**",
          "实际=%s" % json.dumps(fnline or "", ensure_ascii=False))

    sel_nth("#editor .fnedit", 0, 0, len(FNC))
    apply_act("clearfmt")
    md = getmd()
    fnline = None
    for l in md.split("\n"):
        if l.startswith("[^1]:"):
            fnline = l
    check("G3 脚注 clearfmt 复原", fnline == "[^1]: " + FNC,
          "实际=%s" % json.dumps(fnline or "", ensure_ascii=False))
    check("G3 正文行不污染", "正文引用脚注[^1]的说明文字。" in md,
          "md=%s" % json.dumps(md, ensure_ascii=False)[:180])
else:
    check("G1 脚注渲染存在(.fnedit)", False, "fnedit 未找到")

DL_DOC = "术语甲\n: 这是术语甲的定义说明内容"
DLC = "这是术语甲的定义说明内容"
setmd(DL_DOC)
note("G4 md=%s" % json.dumps(getmd(), ensure_ascii=False))
dde = jj("(function(){var e=document.querySelectorAll('#editor dl.deflist dd');"
         "return JSON.stringify({n:e.length,txt:e.length?e[0].textContent:null})})()")
note("G4 dd=%s" % json.dumps(dde, ensure_ascii=False))

if dde.get("n"):
    sel_nth("#editor dl.deflist dd", 0, 0, len(DLC))
    apply_act("strike")
    md = getmd()
    dline = None
    for l in md.split("\n"):
        if DLC.replace(DLC, "") is not None and ("定义说明内容" in l):
            dline = l
    # 定义行匹配：容许 ": " 或 ":" 前缀
    okd = dline is not None and re.match(r"^:\s*~~" + re.escape(DLC) + "~~$", dline) is not None
    check("G5 定义内容删除线", okd, "实际=%s" % json.dumps(dline or "", ensure_ascii=False))
    step_state("G5", "#editor dl.deflist dd", content=DLC, blk_cls="b-p")

    sel_nth("#editor dl.deflist dd", 0, 0, len(DLC))
    apply_act("strike")
    md = getmd()
    dline = None
    for l in md.split("\n"):
        if "定义说明内容" in l:
            dline = l
    okd2 = dline is not None and re.match(r"^:\s*" + re.escape(DLC) + "$", dline) is not None
    check("G6 定义删除线取消复原", okd2, "实际=%s" % json.dumps(dline or "", ensure_ascii=False))
else:
    check("G5 定义列表渲染存在(dd)", False, "dd 未找到")

note("G7 观察项：正文选区含脚注标记应用粗体（记录形态，不断言精确值）")
setmd(FN_DOC)
sel_nth("#editor .blk.b-p", 0, 0, 6)  # 「正文引用脚注」6 字
apply_act("bold")
note("  G7 raw=%s md=%s" % (json.dumps(getraw(), ensure_ascii=False)[:160], json.dumps(getmd(), ensure_ascii=False)[:160]))

# ============================ H 组：源码态 clearfmt（复验 _m96 S6）============================
note("========== H 组：源码态 clearfmt 回渲染态（_m96 S6 复验）==========")
setmd(RICH)
wait(300)


def israw0():
    return jj("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
              "return JSON.stringify({isRaw:b?b.classList.contains('raw-edit'):null,"
              "cls:b?b.className:'',txt:b?b.textContent:null})})()")


js("(function(){var h=document.querySelector('#editor h1');"
   "if(!h)return 'no-h';h.focus();"
   "var rg=document.createRange();rg.selectNodeContents(h);rg.collapse(true);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
   "h.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(420)
st_pre = israw0()
check("H1 点击富标题转源码态(前置)", st_pre.get("isRaw") is True,
      "inf=%s" % json.dumps(st_pre, ensure_ascii=False)[:140])
apply_act("clearfmt")
got = getmd()
st_post = israw0()
check("H1 源码态clearfmt raw正确", got == "# 已加粗和普通", "实际=%s" % json.dumps(got, ensure_ascii=False))
check("H1 clearfmt 后回渲染态", st_post.get("isRaw") is False,
      "inf=%s" % json.dumps(st_post, ensure_ascii=False)[:140])

note("H2 观察项：clearfmt 后点击标题能否恢复渲染态")
js("(function(){var h=document.querySelector('#editor h1');"
   "if(!h)return 'no-h1';h.focus();"
   "h.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(420)
st_h2 = israw0()
note("  H2 点击后 isRaw=%s cls=%s" % (st_h2.get("isRaw"), str(st_h2.get("cls"))[:60]))

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
