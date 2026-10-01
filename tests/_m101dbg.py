# -*- coding: utf-8 -*-
"""m101 调试：定义列表点击为何转 raw-edit。"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m101dbg.txt")
LINES = ["start"]


def flush():
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(str(x) for x in LINES))


def js(win, code, timeout=8000):
    res = {"v": None, "done": False}
    def cb(r):
        res["v"] = r; res["done"] = True
    win._js_active(code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)
    return res["v"]


def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)


app = QApplication(sys.argv)
win = MainWindow()
win.show()
wait(3000)
for _ in range(20):
    if js(win, "!!window.setMarkdown"):
        break
    wait(500)

js(win, "window.setMarkdown(" + json.dumps("术语\n: **定义**内容") + ")")
wait(700)
LINES.append("RAW = " + str(js(win, "window.__raw()")))
LINES.append("DOM = " + str(js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var dd = blk.querySelector('dd');
  return JSON.stringify({blkCls: blk.className, blkHTML: blk.innerHTML.slice(0,300),
    ddCE: dd ? dd.getAttribute('contenteditable') : null,
    ddHTML: dd ? dd.innerHTML : null});
})()""")))

LINES.append("FOCUS = " + str(js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var dd = blk.querySelector('dd');
  dd.focus();
  var rg = document.createRange(); rg.selectNodeContents(dd); rg.collapse(true);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  return JSON.stringify({ae: document.activeElement.tagName,
    raw: blk.classList.contains('raw-edit')});
})()""")))
wait(300)
LINES.append("AFTER-FOCUS RAW = " + str(js(win, "window.__raw()")))

LINES.append("CLICK = " + str(js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var dd = blk.querySelector('dd');
  dd.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, button: 0}));
  dd.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, button: 0}));
  dd.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, button: 0}));
  var b2 = document.querySelectorAll('#editor .blk')[0];
  return JSON.stringify({isRaw: b2.classList.contains('raw-edit'), cls: b2.className,
    html: b2.innerHTML.slice(0,200)});
})()""")))
wait(400)
LINES.append("AFTER-CLICK RAW = " + str(js(win, "window.__raw()")))
LINES.append("DONE")
flush()
print("DONE")
