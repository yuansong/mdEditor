# -*- coding: utf-8 -*-
"""m35fmt2: 复刻 m81 L1 场景（前向 SEQ + 逆序还原），每步 dump raw 定位分歧点"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m35fmt2_out.txt")
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
LIST_INIT = "- 第一项内容文本\n- 第二项内容文本"
C1 = "第一项内容文本"

def sel_li(win, idx=0):
    js(win, """(function(){var b=document.querySelectorAll('#editor .blk')[0];
if(!b)return 'no-blk';var li=b.querySelectorAll('li')[""" + str(idx) + """];
if(!li)return 'no-li';var rg=document.createRange();rg.selectNodeContents(li);
var s=window.getSelection();s.removeAllRanges();s.addRange(rg);
document.dispatchEvent(new Event('selectionchange'));return 'ok'})()""")
    wait(280)

def act(win, action, ms=340):
    js(win, "window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)
    if action == "link":
        js(win, """(function(){var i=document.getElementById('link-url');
if(!i)return 'no-input';i.value=""" + json.dumps(URL) + """;
var b=document.getElementById('link-ok');if(!b)return 'no-btn';b.click();return 'ok'})()""")
        wait(ms + 120)

def raw0(win):
    return (js(win, "window.getMarkdown()") or "")

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"): break
        wait(500)

    SEQ = ["clearfmt", "code", "strike", "link", "clearfmt", "bold", "clearfmt", "italic", "bold"]
    js(win, "window.setMarkdown(" + json.dumps(LIST_INIT) + ")")
    wait(700)
    for i, a in enumerate(SEQ):
        sel_li(win, 0)
        act(win, a)
        log("FWD %02d %-8s raw=%s" % (i + 1, a, json.dumps(raw0(win), ensure_ascii=False)))
    for i, a in enumerate(reversed(SEQ)):
        sel_li(win, 0)
        act(win, a)
        log("REV %02d %-8s raw=%s" % (i + 1, a, json.dumps(raw0(win), ensure_ascii=False)))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")

if __name__ == "__main__":
    main()
