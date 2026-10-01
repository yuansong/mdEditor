# -*- coding: utf-8 -*-
"""m35sp2: 段落行首空格（真实点击激活后键入）"""
import os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m35sp2_out.txt")
LINES = []
def log(s): LINES.append(str(s))

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

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"): break
        wait(500)

    js(win, "window.setMarkdown('# 甲\\n\\n段落一\\n\\n段落二')")
    wait(600)

    # 真实点击第 2 块（段落一）中部激活
    r = js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[1];
  var rc = blk.getBoundingClientRect();
  var x = rc.left + Math.min(40, rc.width/2), y = rc.top + rc.height/2;
  var el = document.elementFromPoint(x, y) || blk;
  ['mousedown','mouseup','click'].forEach(function(t){
    el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, clientX:x, clientY:y}));
  });
  var ce = blk.querySelector('[contenteditable="true"]');
  return JSON.stringify({tag: el.tagName, cls: el.className && String(el.className).slice(0,30),
                         ceTag: ce ? ce.tagName : null});
})()""")
    log("P1 点击激活: %r" % (r,))
    wait(400)

    r2 = js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[1];
  var ce = blk.querySelector('[contenteditable="true"]');
  if (!ce) return 'NO_CE';
  ce.focus();
  var sel = window.getSelection();
  var rng = document.createRange();
  if (!ce.firstChild) return 'NO_TEXT';
  rng.setStart(ce.firstChild, 0);
  rng.collapse(true);
  sel.removeAllRanges(); sel.addRange(rng);
  document.execCommand('insertText', false, ' ');
  var txt = ce.textContent;
  return JSON.stringify({after: txt.slice(0, 8),
    codes: Array.prototype.map.call(txt.slice(0,4), function(c){return c.charCodeAt(0).toString(16);}).join(',')});
})()""")
    log("P2 激活后行首敲空格: %r" % (r2,))
    wait(500)
    md = js(win, "window.getMarkdown()")
    log("P3 getMarkdown: %r" % ((md or "")[:40],))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")

if __name__ == "__main__":
    main()
