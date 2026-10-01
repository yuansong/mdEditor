# -*- coding: utf-8 -*-
"""探针 m34a：复现「输入标题后切双栏，左栏显示渲染态而非源码」。
只读调查，不改产品代码。输出：tests/_m34a_out.txt
"""
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m34a_out.txt")
lines = []


def out(s):
    lines.append(str(s))


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


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


def js_view(view, code):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(15000, loop.quit)
    win._js_view(view, code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


wait(3000)

# ---- 场景1：基础切换（无编辑态）----
js("window.setMarkdown('# 标题甲\\n\\n正文乙')")
wait(400)
out("A1 mode=" + str(win._mode) + " dual=" + str(win._dual))
win._set_mode("dual")
wait(4000)   # src/prev 视图首次惰性创建 + 加载
out("A2 mode=" + str(win._mode) + " dual=" + str(win._dual)
    + " view_src=" + str(win._view_src is not None)
    + " vstate_src=" + str(win._vstate["src"]))
if win._view_src is not None:
    r = js_view(win._view_src,
                "JSON.stringify({srcEl: !!document.querySelector('.raw-edit.t-src'),"
                " blocks: document.querySelectorAll('#editor .blk').length,"
                " h1: document.querySelectorAll('#editor h1').length,"
                " txt: (document.querySelector('.raw-edit.t-src')||{}).textContent||''})")
    out("A3 src视图DOM=" + str(r))
    r2 = js_view(win._view_src, "window.getMarkdown()")
    out("A4 src视图getMarkdown=" + str(r2)[:80])

# 回单栏，再模拟「正在输入标题」的编辑态后切换
win._set_mode("edit")
wait(1500)
# ---- 场景2：让标题块进入编辑态（模拟正在输入）后再切双栏 ----
r = js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
       "if(!b) return 'no blk';"
       "var ev=new MouseEvent('dblclick',{bubbles:true});"
       "b.dispatchEvent(ev);"
       "return JSON.stringify({editing: b.classList.contains('raw-edit'),"
       " txt: b.textContent.slice(0,20)});})()")
out("B1 进入编辑态=" + str(r))
wait(300)
r = js("JSON.stringify(window.collect? window.collect(): null)")
out("B2 collect=" + str(r)[:120])
win._set_mode("dual")
wait(2500)
if win._view_src is not None:
    r = js_view(win._view_src,
                "JSON.stringify({srcEl: !!document.querySelector('.raw-edit.t-src'),"
                " h1: document.querySelectorAll('#editor h1').length,"
                " txt: (document.querySelector('.raw-edit.t-src')||{}).textContent||''})")
    out("B3 src视图DOM(编辑态切换)=" + str(r))

# ---- 场景3：已进过分屏后，编辑再切回双栏（第二次进入路径）----
win._set_mode("edit")
wait(1500)
js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
   "if(b){b.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));}})()")
wait(300)
win._set_mode("dual")
wait(2500)
if win._view_src is not None:
    r = js_view(win._view_src,
                "JSON.stringify({srcEl: !!document.querySelector('.raw-edit.t-src'),"
                " h1: document.querySelectorAll('#editor h1').length,"
                " txt: (document.querySelector('.raw-edit.t-src')||{}).textContent||''})")
    out("C1 src视图DOM(二次进入)=" + str(r))

out("DONE")
flush()
