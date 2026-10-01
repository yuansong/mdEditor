# -*- coding: utf-8 -*-
"""m97b 复验探针：甄别 _m97 与 _m96 的两处矛盾结果
 R1 精确复刻 _m96 S5：sel_all(TreeWalker blk 首尾) + strike(wait500) + getMarkdown → 是否交错 raw
 R5 C1 场景重复 6 次：交错是否偶发（时序敏感）
 R2 精确复刻 _m96 S6：click 转源码态 + clearfmt(wait500) → raw 是否清除
 R3/R4 clearfmt wait 加长变体（880ms）×2 → _m97 H1 未清除是否时序伪影
结果：tests/_m97b.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m97b.txt")
out = []


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code, timeout=15000):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(timeout, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def setmd(md, ms=750):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getmd():
    return js("window.getMarkdown()") or ""


def sel_all_blk0(ms=300):
    """_m96 sel_all 精确复刻"""
    js("""(function(){
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
    wait(ms)


def sel_all_h(ms=300):
    """_m97 sel_nth 变体：从 h1 元素内取文本"""
    js("""(function(){
  var el = document.querySelector('#editor h1');
  if (!el) return 'no-el';
  var w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  var sn = null, en = null, n;
  while (n = w.nextNode()) { if (!sn) sn = n; en = n; }
  if (!sn) return 'no-text';
  var rg = document.createRange();
  rg.setStart(sn, 0); rg.setEnd(en, en.nodeValue.length);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(rg);
  document.dispatchEvent(new Event('selectionchange'));
  return 'ok';
})()""")
    wait(ms)


def act(action, ms=500):
    js("window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


def israw0():
    r = js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
           "return JSON.stringify({isRaw:b?b.classList.contains('raw-edit'):null,"
           "cls:b?b.className:''})})()")
    try:
        return json.loads(r or "{}")
    except Exception:
        return {}


def click_h_to_raw(ms=420):
    js("(function(){var h=document.querySelector('#editor h1');"
       "if(!h)return 'no-h';h.focus();"
       "var rg=document.createRange();rg.selectNodeContents(h);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "h.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


RICH = "# **已加粗**和普通"
wait(2600)
for _ in range(20):
    if "true" in str(js("String(!!window.__applyFloat)")).lower() or js("String(!!window.__applyFloat)") == "true":
        break
    wait(500)

log("=== R1 精确复刻 _m96 S5（sel_all_blk0 + strike wait500）x3 ===")
for i in range(3):
    setmd(RICH)
    sel_all_blk0()
    act("strike", 500)
    r = getmd()
    log("R1-%d raw=%s %s" % (i + 1, json.dumps(r, ensure_ascii=False),
                             "交错!" if "~~**" not in r and "**~~" in r else ("嵌套OK" if "~~**" in r else "其他")))

log("=== R5 C1 场景（sel_all_h）重复 6 次 ===")
for i in range(6):
    setmd(RICH)
    sel_all_h()
    act("strike", 330)
    r = getmd()
    log("R5-%d raw=%s" % (i + 1, json.dumps(r, ensure_ascii=False)))

log("=== R2 精确复刻 _m96 S6（click 转源码态 + clearfmt wait500）x3 ===")
for i in range(3):
    setmd(RICH)
    wait(300)
    click_h_to_raw(420)
    pre = israw0()
    act("clearfmt", 500)
    r = getmd()
    post = israw0()
    log("R2-%d pre_isRaw=%s raw=%s post_isRaw=%s cls=%s" % (
        i + 1, pre.get("isRaw"), json.dumps(r, ensure_ascii=False), post.get("isRaw"), str(post.get("cls"))[:40]))

log("=== R3/R4 clearfmt wait 加长 880ms x2 ===")
for i in range(2):
    setmd(RICH)
    wait(300)
    click_h_to_raw(420)
    act("clearfmt", 880)
    r = getmd()
    post = israw0()
    log("R34-%d raw=%s post_isRaw=%s" % (i + 1, json.dumps(r, ensure_ascii=False), post.get("isRaw")))

log("=== R6 附加：源码态 clearfmt 后再点击（_m96 S6 场景人工恢复观察）===")
setmd(RICH)
wait(300)
click_h_to_raw(420)
act("clearfmt", 500)
r1 = getmd()
click_h_to_raw(420)
post = israw0()
log("R6 clearfmt后raw=%s 再点击后isRaw=%s cls=%s" % (
    json.dumps(r1, ensure_ascii=False), post.get("isRaw"), str(post.get("cls"))[:40]))

log("DONE")
print("DONE")
