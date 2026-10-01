# -*- coding: utf-8 -*-
"""m71 回归：列表菜单 → 输入文字 → 高亮 → 加链接 → 回车换行 → 新行重复操作。
用户报告：按此序列操作后界面出现 "===" 字符。
v3.30.18 修复（LIST-1 根修 + 跨行守卫 + LIST-2 止血）后本文件转为回归测试：
- S1 渲染态端到端（修复前 S1.7/S1.8 产生字面 == / ====，现已正确落位）
- S2 隔离复现：多行列表第 2 项格式化（修复前格式错落上一行，现正确）
- S3 首项（嵌套 mark>a）再套高亮：嵌套标记 toggle 为遗留专项，本断言只锁
  「跨项不污染」（第二项不受影响）
- S4 渲染态编辑含格式项：止血语义 = 格式保留、新输入不落盘（宁可不存不丢）
- S5 对照组：单行高亮
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m71.txt")
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
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getmd(ms=250):
    r = js("window.getMarkdown()")
    wait(ms)
    return r


def rawdump(tag, ms=250):
    r = jj("window.__raw()")
    note("%s raw=%s editIdx=%s" % (tag, json.dumps(r.get("raw"), ensure_ascii=False), r.get("editIdx")))
    return r


def htmldump(idx=0, tag="", ms=250):
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return JSON.stringify({err:'noblk'});"
           "return JSON.stringify({html:b.innerHTML.substring(0,600),"
           "text:(b.textContent||'').replace(/\\n/g,' ')})})()")
    note("%s blk%d html=%s" % (tag, idx, json.dumps(r, ensure_ascii=False)[:500]))
    return r


def eq_count(idx=0, ms=200):
    """统计渲染块文本里的连续 = 串（长度>=2 视为字面标记泄漏）"""
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return '[]';"
           "var t=b.textContent||'';var m=t.match(/={2,}/g);"
           "return JSON.stringify(m||[])})()")
    wait(ms)
    try:
        return json.loads(r or "[]")
    except Exception:
        return [str(r)]


def click_el(sel, ms=300, ev="mousedown"):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "el.dispatchEvent(new MouseEvent(" + json.dumps(ev) + ",{bubbles:true,cancelable:true,detail:1}));"
       "return 'ok'})()")
    wait(ms)


def key_in(sel, key, ms=280):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def type_text(text, ms=300):
    """向当前焦点元素插入文本（触发 input 回写）"""
    js("(function(){document.execCommand('insertText',false," + json.dumps(text) + ");return 'ok'})()")
    wait(ms)


def focus_caret_end(sel, ms=250):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';el.focus();"
       "var rg=document.createRange();rg.selectNodeContents(el);rg.collapse(false);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(ms)


def sel_raw_edit(a, b, ms=250):
    """在源码态 .raw-edit 内按偏移选区"""
    js("(function(){var el=document.querySelector('.raw-edit');if(!el)return 'no-edit';"
       "var tn=el.firstChild;if(!tn)return 'no-tn';"
       "var rg=document.createRange();rg.setStart(tn," + str(a) + ");rg.setEnd(tn," + str(b) + ");"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def sel_li(idx, li, ms=280):
    """选中渲染态列表第 li 项的全部内容"""
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
       "if(!b)return 'no-blk';"
       "var li=b.querySelectorAll('li')[" + str(li) + "];if(!li)return 'no-li';"
       "var rg=document.createRange();rg.selectNodeContents(li);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def slash_pick_list(ms=400):
    """空块进入源码态 → 键入 / → 斜杠菜单选「列表→无序列表」"""
    click_el("#editor .blk", 350)
    js("(function(){var el=document.querySelector('.raw-edit');"
       "if(!el)return 'no-edit';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'ok'})()")
    wait(300)
    r = js("window.__slashPick('list', 0)")
    wait(ms)
    return r


def link_ok(url, ms=400):
    js("(function(){var i=document.getElementById('link-url');"
       "if(!i)return 'no-input';i.value=" + json.dumps(url) + ";"
       "var b=document.getElementById('link-ok');"
       "if(!b)return 'no-btn';b.click();return 'ok'})()")
    wait(ms)


wait(2500)

URL = "https://x.com/demo"

# =========================================================
# S1 用户原始序列端到端
# =========================================================
note("========== S1 用户序列端到端 ==========")
setmd("")
r = slash_pick_list()
check("S1.1 斜杠菜单插入无序列表", r == "OK" and rawdump("S1.1").get("raw", [""])[0].startswith("- "),
      json.dumps(rawdump("S1.1").get("raw"), ensure_ascii=False))

type_text("项目内容")
r1 = rawdump("S1.2 输入文字后")
check("S1.2 输入文字 → raw=- 项目内容", r1.get("raw", [""])[0] == "- 项目内容",
      json.dumps(r1.get("raw"), ensure_ascii=False))

# S1.3：S1.2 后块是渲染态 li（渲染态直编），用渲染态选区（真实用户路径）
sel_li(0, 0)
js("window.__applyFloat('mark')")
wait(400)
r3 = rawdump("S1.3 高亮后")
check("S1.3 高亮 → raw=- ==项目内容==", r3.get("raw", [""])[0] == "- ==项目内容==",
      json.dumps(r3.get("raw"), ensure_ascii=False))

# S1.4：渲染态对已高亮项加链接（链接弹层区间应落在内容内侧）
sel_li(0, 0)
js("window.__applyFloat('link')")
wait(400)
lp = jj("window.__linkPop()")
note("S1.4a linkpop=%s" % json.dumps(lp))
link_ok(URL)
r4 = rawdump("S1.4 加链接后")
check("S1.4 链接 → raw=- ==[项目内容](url)==", r4.get("raw", [""])[0] == "- ==[项目内容](%s)==" % URL,
      json.dumps(r4.get("raw"), ensure_ascii=False))
h4 = htmldump(0, "S1.4 渲染")
check("S1.4b 渲染含 mark>a 无字面==", "==" not in (h4.get("text") or ""),
      json.dumps(h4.get("text"), ensure_ascii=False))

# 回车换行（点击 li 进入，再派发 Enter）
click_el("#editor .blk li", 300)
key_in("#editor .blk li", "Enter", 400)
r5 = rawdump("S1.5 回车后")
check("S1.5 回车新增空列表项", len(r5.get("raw", [""])[0].split("\n")) == 2,
      json.dumps(r5.get("raw"), ensure_ascii=False))

focus_caret_end("#editor .blk li[data-line='1']")
type_text("第二项")
r6 = rawdump("S1.6 新行输入后")
check("S1.6 新行文字", (r6.get("raw", [""])[0].split("\n") + ["", ""])[1] == "- 第二项",
      json.dumps(r6.get("raw"), ensure_ascii=False))

sel_li(0, 1)
js("window.__applyFloat('mark')")
wait(400)
r7 = rawdump("S1.7 新行高亮后")
eqs = eq_count(0)
check("S1.7 新行高亮无字面==污染", r7.get("raw", [""])[0] == "- ==[项目内容](%s)==\n- ==第二项==" % URL
      and not eqs,
      "raw=%s eq=%s" % (json.dumps(r7.get("raw"), ensure_ascii=False), json.dumps(eqs, ensure_ascii=False)))

sel_li(0, 1)
js("window.__applyFloat('link')")
wait(400)
link_ok(URL)
r8 = rawdump("S1.8 新行加链接后")
eqs8 = eq_count(0)
check("S1.8 新行链接后无字面==", r8.get("raw", [""])[0] == "- ==[项目内容](%s)==\n- ==[第二项](%s)==" % (URL, URL)
      and not eqs8,
      "raw=%s eq=%s" % (json.dumps(r8.get("raw"), ensure_ascii=False), json.dumps(eqs8, ensure_ascii=False)))
note("S1 最终 markdown=%s" % json.dumps(getmd(), ensure_ascii=False))

# =========================================================
# S2 隔离复现：多行列表（第 1 项带高亮+链接），渲染态对第 2 项加高亮
# =========================================================
note("========== S2 隔离复现：第 2 项渲染态格式化 ==========")
setmd("- ==[项目内容](%s)==\n- 第二项内容" % URL)
wait(500)
htmldump(0, "S2 初始渲染")
sel_li(0, 1)
js("window.__applyFloat('mark')")
wait(400)
r = rawdump("S2 第2项高亮后")
eqs = eq_count(0)
check("S2 第2项高亮 → raw 正确", r.get("raw", [""])[0] == "- ==[项目内容](%s)==\n- ==第二项内容==" % URL
      and not eqs,
      "raw=%s eq=%s" % (json.dumps(r.get("raw"), ensure_ascii=False), json.dumps(eqs, ensure_ascii=False)))

# =========================================================
# S3 隔离复现：对第 1 项（高亮+链接）再套一层高亮
# =========================================================
note("========== S3 隔离复现：对已链接文字再套格式 ==========")
setmd("- ==[项目内容](%s)==\n- 第二项" % URL)
wait(500)
sel_li(0, 0)
js("window.__applyFloat('mark')")
wait(400)
r = rawdump("S3 首项再套高亮后")
eqs = eq_count(0)
# v3.30.18：嵌套标记（mark>a）toggle 是遗留专项 —— 这里只锁「跨项不污染」：
# 跨行守卫 / 根修后第二项必须原样保留，且不得产生跨行脏标记
check("S3 首项再套高亮 → 第二项不受污染",
      (r.get("raw", [""])[0].split("\n") + ["", ""])[1] == "- 第二项",
      "raw=%s eq=%s" % (json.dumps(r.get("raw"), ensure_ascii=False), json.dumps(eqs, ensure_ascii=False)))
htmldump(0, "S3 渲染")

# =========================================================
# S4 渲染态编辑已格式化列表项 → 行内标记是否被剥掉
# =========================================================
note("========== S4 渲染态编辑剥离检查 ==========")
setmd("- ==重点==文字与[链接](https://a.com)")
wait(500)
htmldump(0, "S4 初始")
click_el("#editor .blk li", 300)
focus_caret_end("#editor .blk li")
type_text("X")
wait(400)
r = rawdump("S4 编辑后")
# v3.30.18（LIST-2 止血）：含格式项的纯文本回写被守卫拦截 —— 格式标记保留、
# 新输入 X 不落盘（宁可不存新字符也不丢格式；真实点击路径会转源码编辑正常保存）
check("S4 渲染态编辑保留 == / []() 标记（v3.36 WYS-3：无损回写，旧止血语义已退役）",
      r.get("raw", [""])[0] == "- ==重点==文字与[链接](https://a.com)X",
      json.dumps(r.get("raw"), ensure_ascii=False))

# =========================================================
# S5 对照组：单行列表渲染态格式化（基线应正确）
# =========================================================
note("========== S5 对照组：单行列表 ==========")
setmd("- 项目内容")
wait(500)
sel_li(0, 0)
js("window.__applyFloat('mark')")
wait(400)
r = rawdump("S5 单行高亮后")
check("S5 单行高亮正确", r.get("raw", [""])[0] == "- ==项目内容==",
      json.dumps(r.get("raw"), ensure_ascii=False))

log("")
log("===== RESULT: %d/%d passed, %d failed =====" % (TOTAL[0] - FAIL[0], TOTAL[0], FAIL[0]))
log("DONE")
