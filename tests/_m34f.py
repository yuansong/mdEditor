# -*- coding: utf-8 -*-
"""v3.30.3 补充探针 _m34f：脚注完整链路（空文档路径）+ 空块快捷键空标记对复现。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m34f.txt")
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


wait(2500)

# ---- 脚注：空文档 slash 路径 ----
setmd("")
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("window.__slashPick('footnote', 0)")
wait(600)
rr = raw()
check("F1 脚注引用插入+文末自动定义", any("[^1]" in b for b in rr) and any(b.startswith("[^1]:") for b in rr),
      json.dumps([r, rr], ensure_ascii=False))
# 第二次 → [^2]（当前最后一个块应为空块可再触发 slash）
setmd("")
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("window.__slashPick('footnote', 0)")
wait(500)
rr = raw()
check("F2 空文档首个脚注编号=1(重置后)", any("[^1]" in b for b in rr), json.dumps(rr, ensure_ascii=False))
# 同文档连续两次
setmd("")
js("(function(){var el=document.querySelector('.raw-edit');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
js("window.__slashPick('footnote', 0)"); wait(500)
# 插入后光标在引用标记后，slashState 已关——再开菜单需新的空块；
# 脚注引用插入后当前块是编辑态带 [^1] 内容——非空，无法再触发 slash。
# 改为直接调用 cmd('footnote') 二次插入
js("window.cmd('footnote')"); wait(500)
rr = raw()
check("F3 二次脚注编号递增[^2]", any("[^2]" in b for b in rr) and any(b.startswith("[^2]:") for b in rr),
      json.dumps(rr, ensure_ascii=False))

# ---- 空块快捷键空标记对（折叠光标） ----
setmd("")
js("(function(){var el=document.querySelector('.raw-edit');if(!el)return 'no-el';el.focus();"
   "var s=getSelection();var r=document.createRange();r.selectNodeContents(el);r.collapse(true);"
   "s.removeAllRanges();s.addRange(r);return 'ok'})()")
wait(200)
js("window.cmd('bold')"); wait(300)
rr = raw()
check("F4 空块(折叠光标)Ctrl+B记录", True, json.dumps(rr, ensure_ascii=False))
js("window.cmd('bold')"); wait(300)
rr = raw()
check("F5 再按一次记录", True, json.dumps(rr, ensure_ascii=False))

# ---- 引用内图片（menu=image → __wantPick） ----
setmd("> 引用行")
wait(500)
js("(function(){var el=document.querySelector('#editor blockquote');"
   "el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
js("(function(){var el=document.querySelector('#editor blockquote');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("window.__slashPick('image')")
wait(200)
d = jj("(function(){return JSON.stringify({pick:!!window.__wantPick})})()")
check("F6 引用内图片触发Qt面板", d.get("pick") is True, json.dumps([r, d], ensure_ascii=False))

out.append("DONE")
flush()
print("done")
