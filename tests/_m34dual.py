# -*- coding: utf-8 -*-
"""探针 m34dual：首次进入双栏的推送时序打点（定位 setSourceMode 丢失点）。
只读调查。输出：tests/_m34dual_out.txt
"""
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, QTime

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m34dual_out.txt")
lines = []
_t0 = [None]


def tick():
    if _t0[0] is None:
        _t0[0] = QTime.currentTime()
    return _t0[0].msecsTo(QTime.currentTime())


def out(s):
    lines.append("[%5d] %s" % (tick(), s))


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


app = QApplication(sys.argv)
from mainwindow import MainWindow

win = MainWindow()

# ---- 打点：_on_loaded / _push_text ----
_orig_loaded = win._on_loaded


def spy_loaded(ok, role):
    st = win._vstate.get(role, {})
    out("_on_loaded(ok=%s, role=%s) loaded=%s pending=%r src=%s preview=%s"
        % (ok, role, st.get("loaded"), (st.get("pending") or "")[:24],
           st.get("src"), st.get("preview")))
    r = _orig_loaded(ok, role)
    st2 = win._vstate.get(role, {})
    out("  _on_loaded done: loaded=%s pending=%r" % (st2.get("loaded"), (st2.get("pending") or "")[:24]))
    return r


win._on_loaded = spy_loaded

_orig_push = win._push_text


def spy_push(text):
    if win._dual:
        st = win._vstate["src"]
        out("_push_text(dual) len=%d src.loaded=%s -> %s"
            % (len(text), st["loaded"],
               "直接推送" if st["loaded"] else "写入pending"))
    else:
        out("_push_text(edit) len=%d" % len(text))
    return _orig_push(text)


win._push_text = spy_push

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
out("== 场景：输入标题后切双栏 ==")
js("window.setMarkdown('# 标题甲\\n\\n正文乙')")
wait(400)
out("-- 调用 _set_mode('dual') --")
win._set_mode("dual")
wait(4000)
if win._view_src is not None:
    r = js_view(win._view_src,
                "JSON.stringify({srcEl: !!document.querySelector('.raw-edit.t-src'),"
                " h1: document.querySelectorAll('#editor h1').length,"
                " txt: (document.querySelector('.raw-edit.t-src')||{}).textContent||''})")
    out("src视图DOM=" + str(r))
out("DONE")
flush()
