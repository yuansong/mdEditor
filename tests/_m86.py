# -*- coding: utf-8 -*-
"""m86：行内格式 LIFO 取消（粗 / 斜 / 删除线 / 高亮 / 行内码）四容器验证

用户实测：标题 1 内容「加粗 → 斜体 → 再斜体」第二次斜体不取消而是再套一层，
出现字面 `*`。根因：wrapSelection 的 toggle 判定用「外侧游程平衡 + _lr < mlen」，
对 mlen=1（斜体）恒不成立 → `***C***` 上按斜体无法取消。
v3.31.2 重做为「按 CommonMark 强调游程判定是否已含该格式」：
  mlen=1（斜体/行内码）：游程 n 为奇数 → 已含 → 取消；偶数 → 包裹升级
  mlen=2（粗体/删除线/高亮）：游程 n ≥ 2 → 已含 → 取消；n=1 → 包裹升级

本探针覆盖：标题 1 / 列表项 / 引用 / 段落 四容器 × 8 条序列。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m86.txt")
out = []
FAIL = [0]
TOTAL = [0]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
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


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    return (jj("window.__raw()").get("raw") or [""])[0]


def sel_in(sel, ms=280):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def fmt(act, ms=400):
    js("window.__applyFloat(" + json.dumps(act) + ")")
    wait(ms)


def text_of(idx=0):
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return JSON.stringify({text:''});"
           "return JSON.stringify({text:(b.textContent||'').replace(/\\n/g,' ')})})()")
    return r.get("text") or ""


def raw_edit_shown():
    """当前块是否处于源码态（渲染态应为 False）"""
    return jj("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
              "return JSON.stringify({raw:!!(b&&b.classList.contains('raw-edit'))})})()").get("raw")


wait(2500)

CASES = [
    ("标题1", "# 演示标题内容文字", "#editor .blk h1", "演示标题内容文字", "# "),
    ("列表", "- 第一项内容文本", "#editor .blk li", "第一项内容文本", "- "),
    ("引用", "> 引用块内的文字内容", "#editor .blk blockquote", "引用块内的文字内容", "> "),
    ("段落", "段落内容文字示例", "#editor .blk p", "段落内容文字示例", ""),
]

# 序列：[(动作, 期望源码), ...]  逐条断言
SEQS = [
    ("B→I→I（第二次斜体应取消，回粗体）",
     [("bold", "**{C}**"), ("italic", "***{C}***"), ("italic", "**{C}**")]),
    ("I→B→B（第二次加粗应取消，回斜体）",
     [("italic", "*{C}*"), ("bold", "***{C}***"), ("bold", "*{C}*")]),
    ("B→I→B（加粗取消，留斜体）",
     [("bold", "**{C}**"), ("italic", "***{C}***"), ("bold", "*{C}*")]),
    ("I→B→I（斜体取消，留粗体）",
     [("italic", "*{C}*"), ("bold", "***{C}***"), ("italic", "**{C}**")]),
    ("B→B（同动作闭环回裸文字）",
     [("bold", "**{C}**"), ("bold", "{C}")]),
    ("I→I（同动作闭环回裸文字）",
     [("italic", "*{C}*"), ("italic", "{C}")]),
    ("B→S→S（粗体内删除线闭环）",
     [("bold", "**{C}**"), ("strike", "**~~{C}~~**"), ("strike", "**{C}**")]),
    ("B→MK→MK（粗体内高亮闭环）",
     [("bold", "**{C}**"), ("mark", "**=={C}==**"), ("mark", "**{C}**")]),
    ("CODE→CODE（行内码闭环）",
     [("code", "`{C}`"), ("code", "{C}")]),
]

for cname, md, sel, plain, pre in CASES:
    note("========== %s ==========" % cname)
    for sname, steps in SEQS:
        setmd(md)
        got = []
        bad_render = []
        for k, (act, want_tpl) in enumerate(steps):
            sel_in(sel)
            fmt(act)
            r = getraw()
            got.append(r)
            t = text_of(0)
            want = pre + want_tpl.replace("{C}", plain)
            check("%s/%s 第%d步 %s" % (cname, sname, k + 1, act), r == want,
                  "实际=%s 预期=%s" % (r, want))
            # 渲染态：不应出现字面标记泄漏（裸 * / ~~ / == / `）
            leak = [m for m in ("**", "*", "~~", "==", "`") if m in t]
            if leak:
                bad_render.append((t, leak))
            # 渲染态：块不应停在源码态
            if raw_edit_shown():
                check("%s/%s 第%d步 应用后仍为渲染态" % (cname, sname, k + 1), False,
                      "块处于 raw-edit 源码态")
        check("%s/%s 渲染无字面标记" % (cname, sname), not bad_render,
              json.dumps(bad_render, ensure_ascii=False))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
