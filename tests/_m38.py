# -*- coding: utf-8 -*-
"""v3.30.3 诊断 _m38：m34 三个失败场景的真实现状甄别。
Q1 引用块内 / 唤起斜杠 → 选表格 → 网格面板是否打开（v3.29 特性回归？）
Q2 非空段落后的空块脚注插入（slash 仅空块唤起的正确流程）
Q3 Ctrl+/ 块菜单（C1 场景）
结果写 _m38.txt。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m38.txt")
out = []


def log(m):
    out.append(m); flush()


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

# ---------- Q1: 引用内斜杠 → 表格 ----------
setmd("> 引用行")
wait(300)
d = jj("(function(){var q=document.querySelector('#editor blockquote');"
       "if(!q)return 'noq';"
       "q.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
log("Q1 after mousedown: " + json.dumps(d, ensure_ascii=False))
d = jj("(function(){var q=document.querySelector('#editor blockquote');"
       "var tgt=q.querySelector('.raw-edit')||q;"
       "tgt.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return JSON.stringify({tgt:tgt.tagName+'.'+(tgt.className||''),"
       "sm:document.getElementById('slashmenu').classList.contains('show')})})()")
wait(200)
log("Q1 after slash: " + json.dumps(d, ensure_ascii=False))
r = js("window.__slashPick('table', null)")
wait(400)
d = jj("(function(){var g=document.getElementById('tblsize');"
       "return JSON.stringify({pick:" + json.dumps(r) + ",grid:g.classList.contains('show'),"
       "editIdx:(window.__editIdx?window.__editIdx():'nohook')})})()")
log("Q1 after pick: " + json.dumps(d, ensure_ascii=False))
# 若网格开了 → 点 3x4 确认
d = jj("(function(){var g=document.getElementById('tblsize');"
       "if(!g.classList.contains('show'))return 'nogrid';"
       "var c=g.querySelector('.gc[data-r=\"2\"][data-c=\"3\"]');"
       "if(!c)return 'nocell';"
       "c.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'clicked'})()")
wait(500)
log("Q1 grid click: " + json.dumps(d, ensure_ascii=False) + " raw=" + json.dumps(raw(), ensure_ascii=False))

# ---------- Q2: 段落后空块脚注 ----------
setmd("正文段落\n\nX")
wait(500)
# 最后块是 X 占位 → 清空成真正空块
d = jj("(function(){var els=document.querySelectorAll('.raw-edit');"
       "if(!els.length)return 'noraw';"
       "var el=els[els.length-1];el.focus();"
       "var s=getSelection();var r2=document.createRange();r2.selectNodeContents(el);"
       "s.removeAllRanges();s.addRange(r2);"
       "document.execCommand('delete');"
       "return JSON.stringify({n:els.length,txt:el.textContent})})()")
wait(300)
log("Q2 clear placeholder: " + json.dumps(d, ensure_ascii=False))
d = jj("(function(){var els=document.querySelectorAll('.raw-edit');"
       "var el=els[els.length-1];"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return JSON.stringify({sm:document.getElementById('slashmenu').classList.contains('show')})})()")
wait(200)
log("Q2 after slash: " + json.dumps(d, ensure_ascii=False))
r = js("window.__slashPick('footnote', 0)")
wait(500)
log("Q2 footnote: pick=" + json.dumps(r) + " raw=" + json.dumps(raw(), ensure_ascii=False))

# ---------- Q3: Ctrl+/ 块菜单 ----------
setmd("# 大标题\n\n正文段落内容")
wait(500)
d = jj("(function(){var b=document.querySelectorAll('#editor .blk')[1];"
       "if(!b)return 'noblk';"
       "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));"
       "return 'x'})()")
wait(300)
d = jj("(function(){var el=document.querySelector('.raw-edit');"
       "if(!el)return 'noraw';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',keyCode:191,ctrlKey:true,bubbles:true,cancelable:true}));"
       "return JSON.stringify({st:(window.__blkMenuState?window.__blkMenuState():'nohook')})})()")
wait(300)
log("Q3 ctrl+/: " + json.dumps(d, ensure_ascii=False))

out.append("DONE")
flush()
print("done")
