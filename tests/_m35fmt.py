# -*- coding: utf-8 -*-
"""m35fmt: 复合行内格式态的 clearfmt / toggle 快速验证
S1: setmd 直置复合态 `# [~~\`C\`~~](url)` → 全选渲染文字 → T× → 应回 `# C`
S2: `# [C](url)` → 全选 → strike → 应回 `# [~~C~~](url)`
S3: `# [~~C~~](url)` → 全选 → code → 应回 `# [~~\`C\`~~](url)`
S4: `# [C](url)` → 全选 → link → 应回 `# C`（FMT-2 toggle）
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m35fmt_out.txt")
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

URL = "https://ex.com/doc"
C = "演示标题这是新输入的内容"

def sel_all(win):
    js(win, """(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var w = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT);
  var sn = null, en = null, n;
  while (n = w.nextNode()) { if (!sn) sn = n; en = n; }
  if (!sn) return 'no-text';
  var rg = document.createRange();
  rg.setStart(sn, 0); rg.setEnd(en, en.nodeValue.length);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()""")
    wait(300)

def act(win, action, ms=350):
    js(win, "window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)

def raw0(win):
    return js(win, "window.getMarkdown()") or ""

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"): break
        wait(500)

    # S1 复合态 clearfmt
    js(win, "window.setMarkdown(" + json.dumps("# [~~`" + C + "`~~](" + URL + ")") + ")")
    wait(700)
    sel_all(win); act(win, "clearfmt")
    r = raw0(win)
    log("S1 clearfmt 复合态: %r  期望=# %s" % (r[:60], C))
    check1 = r == "# " + C

    # S2 链接文字加删除线
    js(win, "window.setMarkdown(" + json.dumps("# [" + C + "](" + URL + ")") + ")")
    wait(700)
    sel_all(win); act(win, "strike")
    r2 = raw0(win)
    log("S2 strike on link: %r  期望=# [~~C~~](url)" % (r2[:60],))
    check2 = r2 == "# [~~" + C + "~~](" + URL + ")"

    # S3 链接+删除线加行内码
    js(win, "window.setMarkdown(" + json.dumps("# [~~" + C + "~~](" + URL + ")") + ")")
    wait(700)
    sel_all(win); act(win, "code")
    r3 = raw0(win)
    log("S3 code on link+strike: %r" % (r3[:60],))
    check3 = r3 == "# [~~`" + C + "`~~](" + URL + ")"

    # S4 链接 toggle
    js(win, "window.setMarkdown(" + json.dumps("# [" + C + "](" + URL + ")") + ")")
    wait(700)
    sel_all(win); act(win, "link")
    r4 = raw0(win)
    log("S4 link toggle: %r  期望=# C" % (r4[:60],))
    check4 = r4 == "# " + C

    log("RESULT S1=%s S2=%s S3=%s S4=%s" % (check1, check2, check3, check4))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")

if __name__ == "__main__":
    main()
