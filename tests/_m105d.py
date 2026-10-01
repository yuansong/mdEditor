# -*- coding: utf-8 -*-
"""m105d：列表块内「连续乱点格式按钮」模糊测试
目标：找出任何一步让标记字面外露（渲染层文本节点里出现 ** / == / ~~ / ` 等）。
每一步都记录 raw + 渲染层纯文本，一旦外露即打印该步与上一步。
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105d.txt")
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

STATE = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var raw = '';
  try { raw = (JSON.parse(window.__raw()).raw || [''])[0]; } catch(e) {}
  var txt = blk.textContent || '';
  var leak = /(\*\*|==|~~|<u>|<\/u>|__)/.test(txt);
  return JSON.stringify({raw: raw, txt: txt, isRaw: blk.classList.contains('raw-edit'),
    leak: leak, cls: blk.className, html: blk.innerHTML});
})()"""

SEQS = [
    ("S1 粗→斜→高→删→下", ["bold", "italic", "mark", "strike", "underline"]),
    ("S2 下→高→粗→斜", ["underline", "mark", "bold", "italic"]),
    ("S3 粗→高→下→高→粗", ["bold", "mark", "underline", "mark", "bold"]),
    ("S4 粗→下→粗→下", ["bold", "underline", "bold", "underline"]),
    ("S5 高→粗→高→粗→高→粗", ["mark", "bold", "mark", "bold", "mark", "bold"]),
    ("S6 粗→高→斜→删→下→粗", ["bold", "mark", "italic", "strike", "underline", "bold"]),
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

    for name, acts in SEQS:
        for host_md, tag in [("- asfdsafdafd", "列表"), ("asfdsafdafd", "段落")]:
            setmd(win, host_md)
            log("===== %s / %s =====" % (name, tag))
            prev = None
            for i, a in enumerate([None] + acts):
                if a:
                    js(win, SEL_JS)
                    js(win, "window.__applyFloat(%s)" % json.dumps(a))
                    wait(400)
                d = json.loads(js(win, STATE) or "{}")
                flag = ""
                if d.get("leak"):
                    flag = "  <<<<<< 标记外露"
                log("  [%-2s %-9s] raw=%-46s txt=%s%s" % (
                    i, str(a), json.dumps(d.get("raw"), ensure_ascii=False),
                    json.dumps(d.get("txt"), ensure_ascii=False), flag))
                if d.get("leak"):
                    log("       html=%s" % json.dumps(d.get("html"), ensure_ascii=False))
                prev = d
            log("")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES))
    nleak = sum(1 for x in LINES if "标记外露" in x)
    print("LEAK_STEPS=%d" % nleak)
    print("\n".join(LINES))


if __name__ == "__main__":
    main()
