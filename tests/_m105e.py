# -*- coding: utf-8 -*-
"""m105e：取准 wrapSelection 的内部数值（配合 v3.37 诊断钩子）
对已知会外露标记的序列，逐步打印 __fmtDbg / __wrapDbg。
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105e.txt")
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

def setmd(win, md):
    js(win, "window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(400)

SEL_JS = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var host = blk.querySelector('[contenteditable]') || blk;
  var rg = document.createRange(); rg.selectNodeContents(host);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()"""

CASES = [
    ("C1 粗体→下划线→粗体（外露）", "asfdsafdafd", ["bold", "underline", "bold"]),
    ("C2 粗体→高亮→下划线→高亮（外露）", "asfdsafdafd", ["bold", "mark", "underline", "mark"]),
    ("C3 粗体→高亮→斜→删→下→粗（大段外露）", "asfdsafdafd",
     ["bold", "mark", "italic", "strike", "underline", "bold"]),
    ("C4 对照：粗体→高亮→粗体（正常）", "asfdsafdafd", ["bold", "mark", "bold"]),
]


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    for name, text, acts in CASES:
        setmd(win, text)
        log("===== %s =====" % name)
        for a in [None] + acts:
            if a:
                js(win, SEL_JS)
                js(win, "window.__applyFloat(%s)" % json.dumps(a))
                wait(400)
            fd = js(win, "window.__fmtDbg ? JSON.stringify(window.__fmtDbg) : 'null'")
            wd = js(win, "window.__wrapDbg ? JSON.stringify(window.__wrapDbg) : 'null'")
            try:
                f = json.loads(fd or "null")
            except Exception:
                f = None
            try:
                w = json.loads(wd or "null")
            except Exception:
                w = None
            log("  act=%-9s" % str(a))
            if f:
                log("     fmt raw=%s" % json.dumps(f.get("raw"), ensure_ascii=False))
                log("       plainOff=%s plainLen=%s off=%s len=%s seg=%s" % (
                    f.get("plainOff"), f.get("plainLen"), f.get("off"), f.get("len"),
                    json.dumps(f.get("seg"), ensure_ascii=False)))
            else:
                log("     fmt = null")
            if w:
                log("     wrap a=%s b=%s _oa=%s _ob=%s _L=%s _R=%s mlen=%s marker=%s" % (
                    w.get("a"), w.get("b"), w.get("_oa"), w.get("_ob"), w.get("_L"),
                    w.get("_R"), w.get("mlen"), json.dumps(w.get("marker"))))
                log("       selected=%s" % json.dumps(w.get("selected"), ensure_ascii=False))
            else:
                log("     wrap = null")
        log("")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES))
    print("\n".join(LINES))


if __name__ == "__main__":
    main()
