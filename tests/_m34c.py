# -*- coding: utf-8 -*-
"""v3.30.3 甄别探针 _m34c：
C-fix) 引用内 slash→表格：逐步检查网格面板状态、Enter 后 raw（甄别「引用内插表格失效」真伪）;
C-x)   引用内插代码块 / 分割线（quoteAppendBlock 路径）;
D-fix) 用 Enter 拆块造空块 → 脚注引用 / 编号递增;
E-fix) 空块 Ctrl+B 空标记对复现（含连续两次）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m34c.txt")
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


def click(sel):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'ok'})()")
    wait(300)


def slash_open_in(sel):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return 'ok'})()")
    wait(300)


def pick(item, sub=None):
    sub_js = "null" if sub is None else str(sub)
    r = js("window.__slashPick(" + json.dumps(item) + ", " + sub_js + ")")
    wait(450)
    return r


def grid_state():
    return jj("(function(){var g=document.getElementById('tblsize');"
              "return JSON.stringify({grid:!!(g&&g.classList.contains('show')),"
              "pop:(window.__tblDragState?window.__tblDragState():null)})})()")


def grid_enter():
    js("(function(){document.activeElement&&document.activeElement.blur&&document.activeElement.blur();"
       "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
       "return 'ok'})()")
    wait(500)


wait(2500)

# ============ C-fix) 引用内插表格逐步甄别 ============
setmd("> 引用行")
wait(500)
click("#editor blockquote")
slash_open_in("#editor blockquote")
r = pick("table")
st = grid_state()
check("C0 引用内选表格后网格面板打开", r == "OK" and st.get("grid") is True, json.dumps([r, st], ensure_ascii=False))
grid_enter()
rr = raw()
st2 = grid_state()
out.append("DIAG after enter: " + json.dumps(rr, ensure_ascii=False) + " | " + json.dumps(st2))
flush()
tbl_rows = [l for b in rr for l in b.split("\n") if "|" in l]
check("C-fix 引用内表格插入且带>前缀", len(tbl_rows) >= 2 and all(l.startswith(">") for l in tbl_rows),
      json.dumps(rr, ensure_ascii=False))

# ============ C-x) 引用内插分割线 / 代码块 ============
setmd("> 引用行")
wait(500)
click("#editor blockquote")
slash_open_in("#editor blockquote")
r = pick("hr")
rr = raw()
out.append("DIAG quote-hr: " + json.dumps(rr, ensure_ascii=False)); flush()
check("C-x1 引用内插分割线", r == "OK" and any(l == "> ---" or l == "---" for b in rr for l in b.split("\n")),
      json.dumps([r, rr], ensure_ascii=False))

setmd("> 引用行")
wait(500)
click("#editor blockquote")
slash_open_in("#editor blockquote")
r = pick("code")
wait(300)
st = grid_state()
d = jj("(function(){var lp=document.getElementById('langpop');"
       "return JSON.stringify({lang:!!(lp&&lp.classList.contains('show'))})})()")
grid_enter2 = None
# 语言弹层 Esc → 代码区
js("(function(){var inp=document.querySelector('#langpop input');if(inp){inp.focus();"
   "inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));}return 'x'})()")
wait(300)
rr = raw()
out.append("DIAG quote-code: " + json.dumps([r, d, rr], ensure_ascii=False)); flush()
tbl_lines = [l for b in rr for l in b.split("\n")]
ok = any(l.startswith("> ```") or l == "> ```" for l in tbl_lines) or any("```" in l and l.startswith(">") for l in tbl_lines)
check("C-x2 引用内插代码块", ok, json.dumps([r, d, rr], ensure_ascii=False))

# ============ D-fix) Enter 拆块造空块 → 脚注 ============
setmd("正文段落")
wait(500)
click(".raw-edit")
# 光标到末尾后回车拆出新空块
js("(function(){var el=document.querySelector('.raw-edit');el.focus();"
   "var s=getSelection();var r=document.createRange();r.selectNodeContents(el);r.collapse(false);"
   "s.removeAllRanges();s.addRange(r);"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(400)
rr = raw()
out.append("DIAG enter-split: " + json.dumps(rr, ensure_ascii=False)); flush()
# 新空块应处于编辑态
slash_open_in(".raw-edit")
r = pick("footnote", 0)
wait(500)
rr = raw()
has_ref = any("[^1]" in b for b in rr)
has_def = any(b.startswith("[^1]:") for b in rr)
check("D-fix 脚注引用+自动定义块", r == "OK" and has_ref and has_def, json.dumps([r, rr], ensure_ascii=False))
# 再来一次 → [^2]
click("#editor .blk:last-child")
slash_open_in(".raw-edit")
r = pick("footnote", 0)
wait(500)
rr = raw()
check("D-fix2 脚注编号递增[^2]", any("[^2]" in b for b in rr) and any(b.startswith("[^2]:") for b in rr),
      json.dumps([r, rr], ensure_ascii=False))

# ============ E-fix) 空块 Ctrl+B 复现（含连续） ============
setmd("")
click(".raw-edit")
js("window.cmd('bold')"); wait(300)
js("window.cmd('bold')"); wait(300)
rr = raw()
check("E-fix 空块Ctrl+B×2记录", True, json.dumps(rr, ensure_ascii=False))  # 只记录

out.append("DONE")
flush()
print("done")
