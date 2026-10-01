# -*- coding: utf-8 -*-
"""m88：HDR-1 —— 「全选后点标题 1 / 2」不再切到源码视图

用户实测：全选（Ctrl+A）后点「标题 1 / 标题 2」，编辑器切到源码视图。
根因：window.cmd('h1') → applyHeadingLevel() 用选区端点 closest('.blk') 求块索引；
     全选时 Range 端点落在 #editor 容器自身 → 求不到块 → 返回 false →
     退回 ensureEdit() + setHeadingLevel()（enterEdit → 源码态，且只改最后一块）。
修复：端点求不到块时逐块 intersectsNode 求覆盖范围（全选 = 整篇生效），
     并在渲染态执行（rebuild + focusWysiwyg），不再进源码态。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m88.txt")
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


def js(code, ms=15000):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(ms, loop.quit)
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


def raws():
    return jj("window.__raw()").get("raw") or []


def raw_edit_count():
    return jj("(function(){return JSON.stringify({n:"
              "document.querySelectorAll('#editor .blk.raw-edit').length})})()").get("n", -1)


def h_tags():
    r = jj("(function(){return JSON.stringify([].map.call("
           "document.querySelectorAll('#editor .blk'),function(b){"
           "var h=b.querySelector('h1,h2,h3,h4,h5,h6');return h?h.tagName:''}) )})()")
    return r if isinstance(r, list) else []


def sel_all(ms=300):
    js("(function(){var ed=document.getElementById('editor');"
       "var r=document.createRange();r.selectNodeContents(ed);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(r);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def sel_block(n, ms=300):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[%d];"
       "if(!b)return 'no-blk';var r=document.createRange();r.selectNodeContents(b);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(r);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()" % n)
    wait(ms)


def cmd(name, ms=600):
    js("window.cmd(" + json.dumps(name) + ")")
    wait(ms)


wait(3000)

DOC = "第一段内容文字\n\n第二段内容文字\n\n## 已有二级标题"

note("========== A) 全选后 cmd('h1') ==========")
setmd(DOC)
sel_all()
cmd("h1")
r = raws()
raw_n = raw_edit_count()
tags = h_tags()
note("raw=%s raw-edit=%s tags=%s" % (json.dumps(r, ensure_ascii=False), raw_n, tags))
check("A1 全选后 h1：全部文本块转为 H1",
      len(r) >= 3 and all(x.startswith("# ") and not x.startswith("## ") for x in r), str(r))
check("A2 未切到源码视图（无 raw-edit 块）", raw_n == 0, "raw-edit=%s" % raw_n)
check("A3 渲染层为 H1 标题", all(t == "H1" for t in tags if t), str(tags))

note("========== B) 全选后 cmd('h2') ==========")
setmd(DOC)
sel_all()
cmd("h2")
r = raws()
check("B1 全部转为 H2", all(x.startswith("## ") for x in r), str(r))
check("B2 未切到源码视图", raw_edit_count() == 0, "raw-edit=%s" % raw_edit_count())

note("========== C) 全选后 cmd('h3') ==========")
setmd(DOC)
sel_all()
cmd("h3")
r = raws()
check("C1 全部转为 H3", all(x.startswith("### ") for x in r), str(r))
check("C2 未切到源码视图", raw_edit_count() == 0, "raw-edit=%s" % raw_edit_count())

note("========== D) 全选后 cmd('p')（转正文） ==========")
setmd(DOC)
sel_all()
cmd("p")
r = raws()
check("D1 标题前缀全部剥除", all(not x.startswith("#") for x in r), str(r))
# 段落（p）在 mdEditor 中没有渲染态编辑入口（WYSIWYG 仅标题 / 列表 / 引用 /
# 定义列表），转正文后需进入该块的源码编辑态才能继续输入 —— 与「点击段落
# 直接输入」的既有行为一致，属设计而非缺陷；断言只要求「最多 1 块进入编辑态」
check("D2 转正文后至多 1 块进入段落编辑态（既有设计）", raw_edit_count() <= 1,
      "raw-edit=%s" % raw_edit_count())

note("========== E) 单块选区 cmd('h1')（仅该块生效） ==========")
setmd(DOC)
sel_block(0)
cmd("h1")
r = raws()
check("E1 仅第 1 块转 H1", r[0].startswith("# ") and not r[2].startswith("### "), str(r))
check("E2 未切到源码视图", raw_edit_count() == 0, "raw-edit=%s" % raw_edit_count())

note("========== F) 块菜单「转为 → 标题 1 / 标题 2」 ==========")
setmd("第一段内容文字\n\n第二段内容文字")
js("window.__applyBlockAct('to:h1', 0)")
wait(500)
r = raws()
check("F1 块菜单 to:h1 生效", len(r) > 0 and r[0].startswith("# "), str(r))
check("F2 块菜单转标题后未切到源码视图", raw_edit_count() == 0,
      "raw-edit=%s" % raw_edit_count())
setmd("第一段内容文字\n\n第二段内容文字")
js("window.__applyBlockAct('to:h2', 1)")
wait(500)
r = raws()
check("F3 块菜单 to:h2 生效（第 2 块）", len(r) > 1 and r[1].startswith("## "), str(r))
check("F4 未切到源码视图", raw_edit_count() == 0, "raw-edit=%s" % raw_edit_count())

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
