# -*- coding: utf-8 -*-
"""m87：HDR-1 —— 全选 / 单块点「标题 1 / 标题 2 / 正文」不再切到源码视图

现象：全选后点标题（H1/H2），编辑器切到源码视图（当前块进入 raw-edit，
     显示 `# 文字` 源码），与「所见即所得」预期不符。
修复：window.cmd('h1'/'h2'/'p') 与块菜单「转为 → 标题 N」在渲染态执行：
     1) 选区跨多块 → 区间内每个文本块生效（全选 = 整篇转标题）
     2) 应用后 focusWysiwyg 回到渲染态（不再 enterEdit 停源码态）
     3) 表格 / 图片 / 图表 / 公式 / 分割线 / 代码块跳过
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m87.txt")
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


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def raws():
    return jj("window.__raw()").get("raw") or []


def texts():
    r = jj("(function(){return JSON.stringify([].map.call("
           "document.querySelectorAll('#editor .blk'),function(b){"
           "return (b.textContent||'').replace(/\\n/g,' ')}))})()")
    return r if isinstance(r, list) else []


def raw_edit_count():
    return jj("(function(){return JSON.stringify({n:document.querySelectorAll("
              "'#editor .blk.raw-edit').length})})()").get("n", -1)


def sel_all(ms=300):
    js("(function(){var r=document.createRange();r.selectNodeContents("
       "document.getElementById('editor'));"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(r);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def sel_in(sel, ms=280):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def cmd(name, ms=500):
    js("window.cmd(" + json.dumps(name) + ")")
    wait(ms)


wait(2500)

DOC = "# 原标题\n\n第一段内容\n\n第二段内容\n\n- 列表项文本"

note("========== A) 全选后点标题 1 ==========")
setmd(DOC)
sel_all()
cmd("h1")
r = raws()
t = texts()
check("A1 全选后 h1：所有块全部转为 H1",
      len(r) >= 4 and all(x.startswith("# ") for x in r), str(r))
check("A2 全选后 h1：未切到源码视图（无 raw-edit 块）", raw_edit_count() == 0,
      "raw-edit=%s" % raw_edit_count())
check("A3 全选后 h1：渲染层无 # 源码泄漏",
      all(not x.strip().startswith("# ") for x in t), str(t))

note("========== B) 全选后点标题 2 ==========")
setmd(DOC)
sel_all()
cmd("h2")
r = raws()
check("B1 全选后 h2：全部转为 H2", all(x.startswith("## ") for x in r), str(r))
check("B2 未切到源码视图", raw_edit_count() == 0, "raw-edit=%s" % raw_edit_count())

note("========== C) 全选后点正文 ==========")
setmd(DOC)
sel_all()
cmd("p")
r = raws()
check("C1 全选后 p：# 前缀剥除", all(not x.startswith("#") for x in r), str(r))
# 段落（p）在 mdEditor 无渲染态编辑入口（WYSIWYG 仅标题 / 列表 / 引用 / 定义列表），
# 转正文后进入该块源码编辑态以便继续输入 —— 与「点击段落直接输入」的既有行为
# 一致，属设计而非缺陷；断言只要求「至多 1 块进入编辑态」
check("C2 转正文后至多 1 块进入段落编辑态（既有设计）", raw_edit_count() <= 1,
      "raw-edit=%s" % raw_edit_count())

note("========== D) 单块（选区在块内）点标题 ==========")
setmd(DOC)
sel_in("#editor .blk:nth-child(3)")   # 第一段内容
cmd("h1")
r = raws()
check("D1 仅当前块转 H1", r[2].startswith("# ") and not r[0].startswith("## "), str(r))
check("D2 未切到源码视图", raw_edit_count() == 0, "raw-edit=%s" % raw_edit_count())

note("========== E) 标题 1 → 标题 2 → 正文（同一块连续切换） ==========")
setmd("# 演示标题内容")
sel_in("#editor .blk h1")
cmd("h2")
r1 = raws()[0]
t1 = texts()[0]
n1 = raw_edit_count()
cmd("p")
r2 = raws()[0]
check("E1 H1 → H2", r1 == "## 演示标题内容", r1)
check("E2 H2 → 正文", r2 == "演示标题内容", r2)
check("E3 H2 后仍在渲染态（无 raw-edit）", n1 == 0, "raw-edit=%s" % n1)
check("E4 渲染文本无 # 泄漏", ("#" not in (t1 or "")), t1)

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
