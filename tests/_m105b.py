# -*- coding: utf-8 -*-
"""m105b：列表块内叠加行内格式后的「渲染 DOM 实况」深挖
关注：
  1. raw = **==x==** 时，渲染 DOM 是 <strong><mark> 还是字面标记
  2. 反复交替点击（bold/mark 各 3 次）后是否出现字面标记外露
  3. 渲染态直编（点进列表项再打字）会不会把标记当字面文本
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105b.txt")
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
    wait(450)

SEL_JS = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  if (!blk) return 'no-blk';
  var host = blk.querySelector('[contenteditable="true"]') || blk;
  var rg = document.createRange(); rg.selectNodeContents(host);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return JSON.stringify({host: host.tagName + '.' + (host.className||''), txt: rg.toString()});
})()"""

DUMP = r"""(function(){
  var blk = document.querySelectorAll('#editor .blk')[0];
  var raw = '';
  try { raw = (JSON.parse(window.__raw()).raw || [''])[0]; } catch(e) {}
  var st = blk.querySelector('strong'), mk = blk.querySelector('mark');
  var em = blk.querySelector('em'), dl = blk.querySelector('del, s, strike');
  var cw = st ? getComputedStyle(st).fontWeight : '';
  var cbg = mk ? getComputedStyle(mk).backgroundColor : '';
  return JSON.stringify({
    raw: raw, isRaw: blk.classList.contains('raw-edit'), cls: blk.className,
    hasStrong: !!st, hasMark: !!mk, hasEm: !!em, hasDel: !!dl,
    strongWeight: cw, markBg: cbg,
    blkHTML: blk.innerHTML
  });
})()"""


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    log("########## 列表：粗体 + 高亮 ##########")
    setmd(win, "- asfdsafdafd")
    for a in [None, "bold", "mark"]:
        js(win, SEL_JS)
        if a:
            js(win, "window.__applyFloat(%s)" % json.dumps(a)); wait(450)
        d = json.loads(js(win, DUMP) or "{}")
        log("[%-6s] raw=%s" % (str(a), json.dumps(d.get("raw"), ensure_ascii=False)))
        log("         hasStrong=%s(w=%s) hasMark=%s(bg=%s) isRaw=%s" %
            (d.get("hasStrong"), d.get("strongWeight"), d.get("hasMark"),
             d.get("markBg"), d.get("isRaw")))
        log("         blkHTML=%s" % json.dumps(d.get("blkHTML"), ensure_ascii=False))

    log("")
    log("########## 列表：bold/mark 交替 x6 ##########")
    setmd(win, "- asfdsafdafd")
    seq = ["bold", "mark", "bold", "mark", "bold", "mark"]
    for a in seq:
        js(win, SEL_JS)
        js(win, "window.__applyFloat(%s)" % json.dumps(a)); wait(420)
        d = json.loads(js(win, DUMP) or "{}")
        log("[%-6s] raw=%s" % (a, json.dumps(d.get("raw"), ensure_ascii=False)))
        log("         hasStrong=%s hasMark=%s isRaw=%s blkHTML=%s" %
            (d.get("hasStrong"), d.get("hasMark"), d.get("isRaw"),
             json.dumps(d.get("blkHTML"), ensure_ascii=False)[:200]))

    log("")
    log("########## 列表：bold→mark 后进入渲染态直编打字 ##########")
    setmd(win, "- asfdsafdafd")
    js(win, SEL_JS); js(win, "window.__applyFloat('bold')"); wait(420)
    js(win, SEL_JS); js(win, "window.__applyFloat('mark')"); wait(420)
    d0 = json.loads(js(win, DUMP) or "{}")
    log("[叠加后 ] raw=%s blkHTML=%s" % (json.dumps(d0.get("raw"), ensure_ascii=False),
                                       json.dumps(d0.get("blkHTML"), ensure_ascii=False)))
    # 点进列表项（模拟用户继续编辑）
    js(win, """(function(){var li=document.querySelector('#editor .blk li');
if(!li)return 'no-li';var r=li.getBoundingClientRect();
var o={bubbles:true,cancelable:true,button:0,clientX:r.left+10,clientY:r.top+8};
li.dispatchEvent(new MouseEvent('mousedown',o));li.dispatchEvent(new MouseEvent('mouseup',o));
li.dispatchEvent(new MouseEvent('click',o));return 'ok'})()""")
    wait(500)
    d1 = json.loads(js(win, DUMP) or "{}")
    log("[点击列表项后] isRaw=%s raw=%s" % (d1.get("isRaw"), json.dumps(d1.get("raw"), ensure_ascii=False)))
    log("               blkHTML=%s" % json.dumps(d1.get("blkHTML"), ensure_ascii=False))
    # 在渲染态末尾追加字符
    js(win, """(function(){var h=document.querySelector('#editor .blk [contenteditable="true"]');
if(!h)return 'no-host';
h.focus();
var rg=document.createRange();rg.selectNodeContents(h);rg.collapse(false);
var s=window.getSelection();s.removeAllRanges();s.addRange(rg);
document.execCommand('insertText',false,'XY');return 'ok'})()""")
    wait(700)
    d2 = json.loads(js(win, DUMP) or "{}")
    log("[渲染态追加 XY] isRaw=%s raw=%s" % (d2.get("isRaw"), json.dumps(d2.get("raw"), ensure_ascii=False)))
    log("               blkHTML=%s" % json.dumps(d2.get("blkHTML"), ensure_ascii=False))
    d3 = js(win, "window.getMarkdown()")
    log("[getMarkdown] %s" % json.dumps(d3, ensure_ascii=False))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES))
    print("\n".join(LINES))


if __name__ == "__main__":
    main()
