# -*- coding: utf-8 -*-
"""m35sp3: 行首空格「存储 vs 视觉」对照探针"""
import os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m35sp3_out.txt")
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

    js(win, "window.setMarkdown('# 甲\\n\\n\\u3000段首全角空格\\n\\n  段首两半角空格')")
    wait(600)
    r = js(win, """(function(){
  var out = [];
  var blks = document.querySelectorAll('#editor .blk');
  [1, 2].forEach(function(bi){
    var blk = blks[bi];
    if (!blk) { out.push('NO_BLK' + bi); return; }
    var p = blk.querySelector('p') || blk.firstElementChild;
    if (!p) { out.push('NO_P' + bi); return; }
    var txt = p.textContent;
    var codes = Array.prototype.map.call(txt.slice(0, 4), function(c){ return c.charCodeAt(0).toString(16); }).join(',');
    // 度量第一个字符的可见宽度
    var w = -1;
    try {
      var rng = document.createRange();
      rng.setStart(p.firstChild, 0); rng.setEnd(p.firstChild, 1);
      w = Math.round(rng.getBoundingClientRect().width);
    } catch (e) { w = 'ERR'; }
    var ws = getComputedStyle(p).whiteSpace;
    out.push(JSON.stringify({blk: bi, text: txt.slice(0, 8), codes: codes, firstCharW: w, ws: ws}));
  });
  return out.join(' || ');
})()""")
    log("R1 两类行首空格块: %r" % (r,))
    md = js(win, "window.getMarkdown()")
    log("R2 getMarkdown: %r" % ((md or "")[:60],))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")

if __name__ == "__main__":
    main()
