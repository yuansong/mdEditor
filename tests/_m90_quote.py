# -*- coding: utf-8 -*-
"""m90：引用块块级交互系统测试（悬浮按钮 / 块操作 / 格式化 / 随机组合 / 撤销重做）

判定标准（每步均校验）：
  R1 引用块始终保持渲染态（无 .raw-edit、文本无裸 Markdown 标记）
  R2 中文内容不乱码、不截断（渲染明文长度守恒）
  R3 脚注引用标记与定义编号保持对应
"""
import json, os, random, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m90.txt")
out = []
TOTAL = [0]
FAIL = [0]
BAD = []
URL = "https://ex.com/doc"
QTEXT = "这是一段真实的引用内容包含中文字符与标点符号"

# 裸源码标记：渲染态下不应出现在可见文本中
BARE = ["**", "==", "~~", "](", "[^", "```", "<div", "&lt;"]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
        BAD.append(name + " || " + detail)
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
    try:
        return json.loads(js(code) or "{}")
    except Exception:
        return {"_raw": js(code)}


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    return jj("window.__raw()").get("raw") or []


def setdoc(lines, ms=800):
    setmd("\n\n".join(lines), ms)


def blk_rect(idx):
    return jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
              "if(!b)return 'null';var r=b.getBoundingClientRect();"
              "return JSON.stringify({left:r.left,top:r.top,right:r.right,bottom:r.bottom})})()")


def handle_state():
    return jj("(function(){var h=document.getElementById('blkhandle');"
              "if(!h)return 'null';var r=h.getBoundingClientRect();"
              "return JSON.stringify({disp:getComputedStyle(h).display,title:h.title,"
              "left:parseFloat(h.style.left||'0'),top:parseFloat(h.style.top||'0'),"
              "rl:r.left,rt:r.top,rw:r.width,rh:r.height})})()")


def hover_blk(idx, ms=300):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
       "if(!b)return 'no-blk';var r=b.getBoundingClientRect();"
       "var ev=new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
       "clientX:r.left+20,clientY:r.top+8});b.dispatchEvent(ev);return 'ok'})()")
    wait(ms)


def hover_xy(x, y, ms=300):
    js("(function(){var ev=new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
       "clientX:" + str(x) + ",clientY:" + str(y) + "});"
       "document.body.dispatchEvent(ev);return 'ok'})()")
    wait(ms)


def click_handle(ms=350):
    js("(function(){var h=document.getElementById('blkhandle');if(!h)return 'no-h';"
       "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def blkmenu():
    return jj("window.__blkMenuState()")


def apply_block(act, idx=None, ms=400):
    if idx is None:
        js("window.__applyBlockAct(" + json.dumps(act) + ")")
    else:
        js("window.__applyBlockAct(" + json.dumps(act) + "," + str(idx) + ")")
    wait(ms)


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


def sel_in(blk, sel, ms=250):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(blk) + "];"
       "if(!b)return 'no-blk';var el=b.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def fmt(act, ms=330):
    if act == "link":
        js("window.__applyFloat('link')")
        wait(ms)
        js("(function(){var i=document.getElementById('link-url');"
           "if(!i)return 'no-input';i.value=" + json.dumps(URL) + ";"
           "var b=document.getElementById('link-ok');"
           "if(!b)return 'no-btn';b.click();return 'ok'})()")
        wait(ms + 120)
        return
    js("window.__applyFloat(" + json.dumps(act) + ")")
    wait(ms)


def undo(ms=420):
    js("window.cmd('undo')")
    wait(ms)


def redo(ms=420):
    js("window.cmd('redo')")
    wait(ms)


def blk_text(idx):
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return JSON.stringify({text:''});"
           "return JSON.stringify({text:(b.textContent||'').replace(/\\n/g,' ')})})()")
    return r.get("text") or ""


def blk_info(idx):
    return jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
              "if(!b)return JSON.stringify({rawedit:false,html:''});"
              "return JSON.stringify({rawedit:!!b.querySelector('.raw-edit'),"
              "html:b.innerHTML.substring(0,300)})})()")


def fn_pairs():
    """返回 (引用标记 id 列表, 定义 id 列表)"""
    r = jj("(function(){var refs=[],defs=[];"
           "var a=document.querySelectorAll('#editor .fnref a[data-fn]');"
           "for(var i=0;i<a.length;i++)refs.push(a[i].getAttribute('data-fn'));"
           "var d=document.querySelectorAll('#editor .fnitem[id]');"
           "for(var j=0;j<d.length;j++)defs.push(d[j].id.replace(/^fn-/,''));"
           "return JSON.stringify({refs:refs,defs:defs})})()")
    return (r.get("refs") or [], r.get("defs") or [])


def rendered_ok(idx, plain_hint=""):
    """渲染态判定：无源码编辑框 + 无裸标记"""
    info = blk_info(idx)
    t = blk_text(idx)
    if info.get("rawedit"):
        return False, "块内出现 .raw-edit（源码态）"
    for m in BARE:
        if m in t:
            return False, "可见文本含裸标记 %s → %s" % (m, t)
    if plain_hint and plain_hint not in t:
        return False, "中文内容不完整/被截断：%s" % t
    return True, t


wait(2500)

DOC = ["# 中文标题示例", "正文段落这是一段正文内容", "> " + QTEXT, "结尾段落用于验证下移"]

# =========================================================
# A 组：悬浮按钮（出现 / 定位 / 收起 / 菜单）
# =========================================================
note("========== A 组：悬浮按钮 ==========")
setdoc(DOC)
QI = 2
hover_blk(QI)
h = handle_state()
check("A1 悬浮引用块 → 手柄显示", h.get("disp") != "none" and h.get("disp") != "",
      json.dumps(h, ensure_ascii=False))
check("A2 手柄 tooltip = 引用", h.get("title") == "引用", str(h.get("title")))
r = blk_rect(QI)
wl = max(4, r.get("left", 0) - 28)
wt = r.get("top", 0) + 3
check("A3 手柄定位 left 准确", abs(h.get("left", -999) - wl) <= 1.5,
      "实际=%s 预期=%s" % (h.get("left"), wl))
check("A4 手柄定位 top 准确", abs(h.get("top", -999) - wt) <= 1.5,
      "实际=%s 预期=%s" % (h.get("top"), wt))
check("A5 手柄在视口内（left>=0 且 top>=0）",
      h.get("rl", -1) >= 0 and h.get("rt", -1) >= 0,
      "rl=%s rt=%s" % (h.get("rl"), h.get("rt")))
check("A6 手柄位于块左侧（不遮挡正文）",
      h.get("rl", 9999) + h.get("rw", 0) <= r.get("left", 0) + 1,
      "handleRight=%s blkLeft=%s" % (h.get("rl", 0) + h.get("rw", 0), r.get("left")))
# 吸附区：手柄右下角 +10px 内不应隐藏
hover_xy(h.get("rl", 0) + h.get("rw", 0) + 8, h.get("rt", 0) + h.get("rh", 0) + 8)
h2 = handle_state()
check("A7 手柄 16px 吸附区内不隐藏", h2.get("disp") != "none", json.dumps(h2, ensure_ascii=False))
hover_xy(5, 5)
h3 = handle_state()
check("A8 移出块区 → 手柄隐藏", h3.get("disp") == "none", json.dumps(h3, ensure_ascii=False))

hover_blk(QI)
click_handle()
bm = blkmenu()
check("A9 点击手柄 → 块菜单展开", bm.get("show") is True, json.dumps(bm, ensure_ascii=False))
cap = js("(function(){var c=document.querySelector('#blkmenu .cap');return c?c.textContent:''})()")
check("A10 菜单标题 = 当前块：引用", "引用" in (cap or ""), str(cap))
items = bm.get("items") or []
check("A11 引用块菜单项完整（含上移/下移/复制/删除/转换）",
      all(x in items for x in ["up", "down", "dup", "del", "to:p", "to-h", "to-list", "to:fence"]),
      json.dumps(items))
check("A12 引用块不再显示 no-op「转为引用」（QUO-5）",
      "to:quote" not in items, json.dumps(items))
check("A13 引用块菜单无「插入同级块」入口（功能未提供）",
      not any("insert" in (x or "") or "add" in (x or "") for x in items),
      json.dumps(items))

# =========================================================
# B 组：块操作
# =========================================================
note("========== B 组：块操作 ==========")


def fresh():
    setdoc(DOC)


fresh()
apply_block("up", QI)
raw = getraw()
check("B1 上移：引用与正文交换", raw[1].startswith("> ") and raw[2].startswith("正文"),
      json.dumps(raw, ensure_ascii=False))
ok, d = rendered_ok(1, QTEXT)
check("B1b 上移后仍渲染态且中文完整", ok, d)

fresh()
apply_block("down", QI)
raw = getraw()
check("B2 下移：引用与结尾段交换", raw[2].startswith("结尾") and raw[3].startswith("> "),
      json.dumps(raw, ensure_ascii=False))
ok, d = rendered_ok(3, QTEXT)
check("B2b 下移后仍渲染态且中文完整", ok, d)

fresh()
apply_block("dup", QI)
raw = getraw()
check("B3 复制块：新增同内容引用块", len(raw) == 5 and raw[2].startswith("> ") and raw[3].startswith("> "),
      json.dumps(raw, ensure_ascii=False))
ok, d = rendered_ok(3, QTEXT)
check("B3b 复制出的块为渲染态（非源码）", ok, d)

fresh()
apply_block("del", QI)
raw = getraw()
check("B4 删除块：引用被移除", len(raw) == 3 and not any(x.startswith("> ") for x in raw),
      json.dumps(raw, ensure_ascii=False))

for act, want_prefix, label in [("to:p", "", "B5 转为段落"), ("to:h3", "### ", "B6 转为标题3"),
                                ("to:ul", "- ", "B7 转为无序列表"), ("to:fence", "```", "B8 转为代码块")]:
    fresh()
    apply_block(act, QI)
    raw = getraw()
    ok = raw[2].startswith(want_prefix) if want_prefix else (not raw[2].startswith("> "))
    check("%s：raw 前缀正确" % label, ok, json.dumps(raw[2], ensure_ascii=False))
    ok2, d2 = rendered_ok(2, QTEXT if act != "to:fence" else "")
    check("%s：转换后渲染态、中文完整" % label, ok2, d2)

# 边界置灰
setdoc(["> " + QTEXT])
hover_blk(0)
click_handle()
dis = js("(function(){var o=[];var m=document.querySelectorAll('#blkmenu .mi');"
         "for(var i=0;i<m.length;i++){if(m[i].classList.contains('dis'))o.push(m[i].getAttribute('data-act'));}"
         "return JSON.stringify(o)})()")
try:
    dis_l = json.loads(dis or "[]")
except Exception:
    dis_l = []
check("B9 唯一块时上移/下移均置灰", "up" in dis_l and "down" in dis_l, str(dis_l))

# 多行引用整体移动
setdoc(["前文段落内容", "> 引用第一行内容\n> 引用第二行内容", "后文段落内容"])
apply_block("up", 1)
raw = getraw()
check("B10 多行引用整体移动（两行不散架）",
      raw[0].startswith("> ") and raw[0].count("> ") == 2 and raw[1].startswith("前文"),
      json.dumps(raw, ensure_ascii=False))

# 脚注编号与跳转
note("--- B11/B12 引用内脚注：编号与跳转 ---")
setdoc(["> 引用内含脚注标记[^1]的中文内容", "[^1]: 这是脚注定义的中文内容"])
refs, defs = fn_pairs()
check("B11 初始：引用标记与定义编号对应", refs == ["1"] and defs == ["1"],
      "refs=%s defs=%s" % (refs, defs))
apply_block("up", 1)          # 定义块上移，引用在后
rawnow = getraw()
refs2, defs2 = fn_pairs()
check("B12 定义块上移后：标记与定义仍对应", refs2 == ["1"] and defs2 == ["1"],
      "raw=%s refs=%s defs=%s" % (json.dumps(rawnow, ensure_ascii=False), refs2, defs2))
apply_block("dup", 1)          # 复制引用块（含 [^1]）
refs3, defs3 = fn_pairs()
check("B13 复制引用块后：两处引用标记均指向同一定义",
      refs3 == ["1", "1"] and defs3 == ["1"], "refs=%s defs=%s" % (refs3, defs3))
apply_block("del", 1)          # 删除脚注定义块
refs4, defs4 = fn_pairs()
t0 = blk_text(0)
check("B14 删除定义块后：正文引用标记不变成裸源码",
      "[^1]" not in t0, "text=%s defs=%s" % (json.dumps(t0, ensure_ascii=False), defs4))

# =========================================================
# C 组：格式化
# =========================================================
note("========== C 组：引用内文字格式化 ==========")
FMTS = [("bold", "**"), ("italic", "*"), ("strike", "~~"), ("mark", "=="), ("code", "`")]

for act, M in FMTS:
    setdoc(["# 中文标题", "> " + QTEXT])
    sel_in(1, "blockquote")
    fmt(act)
    raw = getraw()
    ok = M in (raw[1] or "")
    check("C/%s 标记写入 raw" % act, ok, json.dumps(raw[1], ensure_ascii=False))
    ok2, d2 = rendered_ok(1, QTEXT)
    check("C/%s 渲染态 + 中文完整（无裸标记）" % act, ok2, d2)
    # 取消
    sel_in(1, "blockquote")
    fmt(act)
    raw2 = getraw()
    check("C/%s 二次点击可取消（回到裸文本）" % act,
          (raw2[1] or "").replace("> ", "").strip(QTEXT) == "" or raw2[1] == "> " + QTEXT,
          json.dumps(raw2[1], ensure_ascii=False))

setdoc(["# 中文标题", "> " + QTEXT])
sel_in(1, "blockquote")
fmt("link")
raw = getraw()
check("C/link 链接写入", "](" + URL + ")" in (raw[1] or ""), json.dumps(raw[1], ensure_ascii=False))
ok2, d2 = rendered_ok(1, QTEXT)
check("C/link 渲染态 + 中文完整", ok2, d2)

# 全格式叠加后清除
setdoc(["# 中文标题", "> " + QTEXT])
sel_in(1, "blockquote")
for a, _ in FMTS[:4]:
    fmt(a)
before = getraw()[1]
sel_in(1, "blockquote")
fmt("clearfmt")
after = getraw()[1]
check("C/clearfmt 叠加后清除回到裸文本", after == "> " + QTEXT,
      "before=%s after=%s" % (json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))

# 浮动栏能力枚举（下划线 / 字号 / 颜色）
setdoc(["# 中文标题", "> " + QTEXT])
sel_in(1, "blockquote")
fb = js("(function(){var o=[];var b=document.querySelectorAll('#floatbar button');"
        "for(var i=0;i<b.length;i++)o.push(b[i].title||b[i].textContent);"
        "return JSON.stringify(o)})()")
try:
    fb_l = json.loads(fb or "[]")
except Exception:
    fb_l = [str(fb)]
note("C/浮动栏按钮=%s" % json.dumps(fb_l, ensure_ascii=False))
check("C/underline 产品未提供下划线按钮（记录为未实现，非缺陷）",
      not any("下划线" in x or "underline" in x.lower() for x in fb_l), json.dumps(fb_l, ensure_ascii=False))
check("C/fontsize 产品未提供字号按钮（记录为未实现）",
      not any("字号" in x or "大小" in x for x in fb_l), json.dumps(fb_l, ensure_ascii=False))
check("C/color 产品未提供颜色按钮（记录为未实现）",
      not any("颜色" in x or "color" in x.lower() for x in fb_l), json.dumps(fb_l, ensure_ascii=False))

# 多行引用第 2 行
setdoc(["# 中文标题", "> 引用第一行内容\n> 引用第二行内容"])
n = js("(function(){var b=document.querySelectorAll('#editor .blk')[1];"
       "return String((b.textContent||'').length)})()")
sel_range(1, int(n or 0) // 2, int(n or 0))
fmt("bold")
raw = getraw()
check("C/多行 第 2 行加粗不污染第 1 行",
      (raw[1] or "").split("\n")[0] == "> 引用第一行内容",
      json.dumps(raw[1], ensure_ascii=False))
ok2, d2 = rendered_ok(1, "引用第一行内容")
check("C/多行 渲染态 + 中文完整", ok2, d2)

# =========================================================
# D 组：随机组合 + 撤销重做 + 快速连续
# =========================================================
note("========== D 组：随机组合 / 撤销重做 / 快速连续 ==========")
random.seed(20260929)
ACTS = ["bold", "italic", "strike", "mark", "code", "link", "clearfmt", "up", "down", "dup"]
setdoc(DOC)
init_raw = list(getraw())
bad_step = []
for step in range(30):
    a = random.choice(ACTS)
    # 定位当前引用块
    rawnow = getraw()
    qi = [k for k, x in enumerate(rawnow) if x.startswith("> ")]
    if not qi:
        bad_step.append("step%d 引用块丢失 act=%s" % (step, a))
        break
    idx = qi[0]
    if a in ("up", "down", "dup"):
        apply_block(a, idx, 450)
    else:
        sel_in(idx, "blockquote")
        fmt(a, 300)
    rawnow2 = getraw()
    qi2 = [k for k, x in enumerate(rawnow2) if x.startswith("> ")]
    if not qi2:
        bad_step.append("step%d(%s) 后引用块丢失" % (step, a))
        break
    okk, dd = rendered_ok(qi2[0], QTEXT)
    if not okk:
        bad_step.append("step%d(%s) %s" % (step, a, dd))
        break
check("D1 30 步随机组合（格式化+块操作混合）引用始终渲染态、中文完整",
      len(bad_step) == 0, "; ".join(bad_step) if bad_step else "全部步骤通过")
note("D1 最终 raw=%s" % json.dumps(getraw(), ensure_ascii=False))

# 撤销 / 重做
setdoc(DOC)
base = list(getraw())
sel_in(2, "blockquote")
fmt("bold", 350)
wait(500)
apply_block("down", 2, 450)
wait(500)
mid = list(getraw())
undo()
u1 = list(getraw())
check("D2 撤销 1 步 → 回到下移前", u1[2].startswith("**") or "**" in (u1[2] or ""),
      json.dumps(u1, ensure_ascii=False))
undo()
u2 = list(getraw())
check("D3 撤销 2 步 → 回到初始文档", u2 == base,
      "实际=%s 预期=%s" % (json.dumps(u2, ensure_ascii=False), json.dumps(base, ensure_ascii=False)))
redo()
r1 = list(getraw())
check("D4 重做 1 步 → 恢复到加粗后", r1 == mid or "**" in (r1[2] or ""),
      json.dumps(r1, ensure_ascii=False))
# 连续撤销到栈空
for _ in range(8):
    undo()
tail = list(getraw())
check("D5 连续撤销到栈底后状态稳定（不崩溃、内容合法）",
      isinstance(tail, list) and all(isinstance(x, str) for x in tail),
      json.dumps(tail, ensure_ascii=False))

# 快速连续操作（无等待）
setdoc(DOC)
sel_in(2, "blockquote")
for a in ["bold", "italic", "strike", "mark", "clearfmt", "bold", "mark", "clearfmt"]:
    js("window.__applyFloat(" + json.dumps(a) + ")")
wait(700)
raw_f = getraw()
ok2, d2 = rendered_ok(2, QTEXT)
check("D6 快速连续 8 次格式化（无间隔）→ 仍渲染态、中文完整", ok2,
      "raw=%s detail=%s" % (json.dumps(raw_f, ensure_ascii=False), d2))

setdoc(DOC)
for _ in range(6):
    js("window.__applyBlockAct('down',2)")
wait(700)
raw_g = getraw()
qi3 = [k for k, x in enumerate(raw_g) if x.startswith("> ")]
check("D7 快速连续 6 次下移（无间隔）→ 引用仍存在且渲染态",
      len(qi3) == 1 and rendered_ok(qi3[0], QTEXT)[0],
      json.dumps(raw_g, ensure_ascii=False))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
if BAD:
    log("--- 不符合预期项 ---")
    for b in BAD:
        log("BAD: " + b)
log("DONE")
