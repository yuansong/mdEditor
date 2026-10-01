# -*- coding: utf-8 -*-
"""m105d 分割线收尾复验：HR-3 真实场景（hr 下方段首 Backspace / 上方段末 Delete）、
      块菜单是否覆盖 hr、连续 hr 的键盘删除、撤销粒度"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105d_hr.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
        ABN.append(name + " || " + detail)
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def note(s):
    log("NOTE %s" % s)


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


def jj(code):
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


wait(2800)


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getmd():
    return js("window.getMarkdown()") or ""


def caret_in(idx, at_start=True):
    """把光标放到第 idx 个可编辑块的开头/结尾（plaintext-only 渲染态编辑）"""
    return js("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
              "var b=bs[" + str(idx) + "];if(!b)return 'noblk';"
              "var t=b.querySelector('[contenteditable]')||b;"
              "t.setAttribute('contenteditable','plaintext-only');t.focus();"
              "var rg=document.createRange();rg.selectNodeContents(t);rg.collapse(" +
              ("true" if at_start else "false") + ");"
              "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
              "return (t.textContent||'').slice(0,10)})()")


def keyel(k):
    js("(function(){var t=document.activeElement||document.body;"
       "t.dispatchEvent(new KeyboardEvent('keydown',{key:'" + k +
       "',bubbles:true,cancelable:true}));return 'ok'})()")


note("========== T1 HR-3：hr 下方段首 Backspace ==========")
setmd("甲\n\n---\n\n乙")
note("  T1 块序列=%s" % js("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
                          "return JSON.stringify(bs.map(function(b){return (b.querySelector('hr')?'HR':'P')"
                          "+'['+(b.textContent||'').slice(0,4)+']'}))})()"))
caret_in(2, True)
wait(400)
note("  T1 光标块=%s" % js("(function(){var t=document.activeElement;"
                          "return t?(t.textContent||'').slice(0,8):'none'})()"))
keyel("Backspace")
wait(700)
md = getmd()
note("  T1 Backspace 后 md=%s" % json.dumps(md, ensure_ascii=False))
check("T1 hr 下方段首 Backspace → 删除 hr 且文本保留",
      "---" not in md and "乙" in md, "md=%s" % json.dumps(md, ensure_ascii=False))
js("window.cmd('undo')")
wait(800)
note("  T1 撤销后 md=%s" % json.dumps(getmd(), ensure_ascii=False))
check("T1b 撤销可恢复 hr", "---" in getmd(), "md=%s" % json.dumps(getmd(), ensure_ascii=False))

note("========== T2 hr 上方段末 Delete（5001 场景）==========")
setmd("甲\n\n---\n\n乙")
caret_in(0, False)
wait(400)
note("  T2 光标块=%s" % js("(function(){var t=document.activeElement;"
                          "return t?(t.textContent||'').slice(0,8):'none'})()"))
keyel("Delete")
wait(700)
md = getmd()
note("  T2 Delete 后 md=%s" % json.dumps(md, ensure_ascii=False))
check("T2 hr 上方段末 Delete → 删除 hr（不把 --- 并入文本）",
      "---" not in md and "甲" in md, "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== T3 块菜单是否覆盖 hr（7964 自述不进菜单）==========")
setmd("甲\n\n---\n\n乙")
bm = js("(function(){var h=document.querySelector('#editor hr');if(!h)return 'nohr';"
        "h.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));"
        "var BM=document.getElementById('blkmenu');"
        "return BM?String(BM.classList.contains('show')):'nobm'})()")
wait(500)
bmtxt = js("(function(){var BM=document.getElementById('blkmenu');"
           "return BM?(BM.textContent||'').slice(0,120):'nobm'})()")
note("  T3 hr 上右键 → blkmenu show=%s txt=%s" % (bm, str(bmtxt)[:160]))
sysmenu = js("(function(){return 'n/a'})()")
note("  T3 说明：hr 上右键走系统菜单与否由 mainwindow 层决定（Qt 层）")

note("========== T4 相邻连续 hr 的键盘删除精度 ==========")
setmd("甲\n\n---\n\n---\n\n乙")
s0 = js("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
        "return JSON.stringify(bs.map(function(b){return (b.querySelector('hr')?'HR':'P')}))})()")
note("  T4 初始=%s" % s0)
# 选中第 1 条 hr 后 Delete
js("(function(){var hs=document.querySelectorAll('#editor hr');var h=hs[0];"
   "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(400)
js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}))")
wait(700)
md = getmd()
note("  T4 删 1 条后 md=%s" % json.dumps(md, ensure_ascii=False))
check("T4 连续 hr 删除只影响选中那一条",
      md.count("---") == 1 and "甲" in md and "乙" in md,
      "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== T5 选中态在 rebuild 后的失效（注释自述）==========")
setmd("甲\n\n---\n\n乙")
js("(function(){var h=document.querySelector('#editor hr');"
   "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(400)
pre = js("(function(){var h=document.querySelector('#editor hr');"
         "return h?String(h.classList.contains('hrsel')):'nohr'})()")
# 触发 rebuild
js("window.setMarkdown(" + json.dumps("甲\n\n---\n\n乙\n\n丙") + ")")
wait(800)
post = js("(function(){var h=document.querySelector('#editor hr');"
          "return h?String(h.classList.contains('hrsel')):'nohr'})()")
note("  T5 pre=%s post=%s" % (pre, post))
check("T5 rebuild 后旧选中态自动失效（不误删）", post == "false",
      "pre=%s post=%s" % (pre, post))
js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}))")
wait(600)
md = getmd()
note("  T5 失效后按 Delete 的 md=%s" % json.dumps(md, ensure_ascii=False))
check("T5b 失效后 Delete 不误删 hr", "---" in md, "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== T6 文档首块为 hr 时向上导航 ==========")
setmd("---\n\n甲")
js("(function(){var f=window.goToBlock||window.__goToBlock;"
   "if(typeof f==='function'){f(1,'start')}return 'ok'})()")
wait(600)
s = js("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
       "return JSON.stringify(bs.map(function(b){return b.className}))})()")
note("  T6=%s md=%s" % (s, json.dumps(getmd(), ensure_ascii=False)))
check("T6 首块为 hr 时导航进入不切源码态", "raw-edit" not in str(s), "cls=%s" % s)

log("\n==== 合计 %d 项，FAIL %d ====" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABNORMAL " + a)
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
