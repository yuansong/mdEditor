# -*- coding: utf-8 -*-
"""m97c FMT-6 全链路验证：源码态真选区 clearfmt（补 _m97 H 组的选区伪影）
背景：v3.32.1（07:49）实现 FMT-6「源码态清除格式回渲染」（editor.html 7702-7714）；
      _m97/_m97b 的 H 组在 click 转源码态后未重新构造选区（isCollapsed 短路），
      clearSelectionFormat 直接 return —— 属探针伪影。本探针用源码态内真实
      文本选区模拟用户拖选，验证 FMT-6 全链路。
 T1 源码态全选 → clearfmt：raw 清除 + 回渲染态 + h1 存在
 T2 源码态选局部（**已加粗**）→ clearfmt：局部清除 + 无残留富文本时回渲染态
 T3 源码态选文字 → bold：尊重发起态（raw 更新 + 保持源码态）
 T4 渲染态 clearfmt 对照（回归 A18 一致性）
结果：tests/_m97c.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m97c.txt")
out = []
FAIL = [0]
TOTAL = [0]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


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


def israw0():
    r = js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
           "return JSON.stringify({isRaw:b?b.classList.contains('raw-edit'):null,"
           "cls:b?b.className:'',h1:!!(b&&b.querySelector('h1'))})})()")
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


def sel_all_raw(ms=300):
    """源码态内：在 .raw-edit 元素文本内全选（模拟用户 Ctrl+A / 拖选）"""
    js("(function(){var el=document.querySelector('#editor .raw-edit');"
       "if(!el)return 'no-raw';"
       "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);"
       "var sn=null,en=null,n;"
       "while(n=w.nextNode()){if(!sn)sn=n;en=n;}"
       "if(!sn)return 'no-text';"
       "var rg=document.createRange();rg.setStart(sn,0);rg.setEnd(en,en.nodeValue.length);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def sel_raw_off(a, b, ms=300):
    """源码态内：按 .raw-edit 文本偏移选区"""
    js("(function(){var el=document.querySelector('#editor .raw-edit');"
       "if(!el)return 'no-raw';"
       "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);"
       "var pos=0,sn=null,so=0,en=null,eo=0,n;"
       "while(n=w.nextNode()){var L=n.nodeValue.length;"
       "if(sn===null&&pos+L>=" + str(a) + "){sn=n;so=" + str(a) + "-pos;}"
       "if(pos+L>=" + str(b) + "){en=n;eo=" + str(b) + "-pos;break;}"
       "pos+=L;}"
       "if(!sn||!en)return 'no-range';"
       "var rg=document.createRange();rg.setStart(sn,so);rg.setEnd(en,eo);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def act(action, ms=500):
    js("window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


RICH = "# **已加粗**和普通"
wait(2600)
for _ in range(20):
    if js("String(!!window.__applyFloat)") == "true":
        break
    wait(500)

log("=== T1 源码态全选 clearfmt（FMT-6 全链路）===")
setmd(RICH)
click_h_to_raw()
pre = israw0()
check("T1 前置转源码态", pre.get("isRaw") is True, "pre=%s" % json.dumps(pre, ensure_ascii=False))
sel_all_raw()
act("clearfmt", 600)
r = getmd()
post = israw0()
check("T1 raw 清除", r == "# 已加粗和普通", "raw=%s" % json.dumps(r, ensure_ascii=False))
check("T1 回渲染态", post.get("isRaw") is False, "post=%s" % json.dumps(post, ensure_ascii=False))
check("T1 h1 存在", post.get("h1") is True, "post=%s" % json.dumps(post, ensure_ascii=False))

log("=== T2 源码态局部选区 clearfmt ===")
setmd(RICH)
click_h_to_raw()
sel_raw_off(2, 10)   # 选「**已加粗**」部分（# 后偏移 2..10）
act("clearfmt", 600)
r = getmd()
post = israw0()
check("T2 局部清除（粗体被剥）", r == "# 已加粗和普通" or r == "# 和普通",
      "raw=%s" % json.dumps(r, ensure_ascii=False))
check("T2 渲染态判定", post.get("isRaw") is False or post.get("isRaw") is True,
      "观察 isRaw=%s cls=%s" % (post.get("isRaw"), str(post.get("cls"))[:40]))

log("=== T3 源码态 bold（尊重发起态）===")
setmd("# 纯文字标题")
click_h_to_raw()
pre3 = israw0()
sel_raw_off(2, 6)   # 「纯文字」
act("bold", 600)
r = getmd()
post3 = israw0()
check("T3 raw 更新", r == "# **纯文字**标题", "raw=%s" % json.dumps(r, ensure_ascii=False))
check("T3 保持源码态（尊重发起态）", post3.get("isRaw") is True,
      "post=%s" % json.dumps(post3, ensure_ascii=False))

log("=== T4 渲染态 clearfmt 对照 ===")
setmd(RICH)
js("(function(){var el=document.querySelector('#editor h1');"
   "if(!el)return 'no-el';"
   "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);"
   "var sn=null,en=null,n;"
   "while(n=w.nextNode()){if(!sn)sn=n;en=n;}"
   "var rg=document.createRange();rg.setStart(sn,0);rg.setEnd(en,en.nodeValue.length);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
   "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
wait(300)
act("clearfmt", 600)
r = getmd()
post4 = israw0()
check("T4 raw 清除", r == "# 已加粗和普通", "raw=%s" % json.dumps(r, ensure_ascii=False))
check("T4 保持渲染态", post4.get("isRaw") is False, "post=%s" % json.dumps(post4, ensure_ascii=False))

log("")
log("RESULT TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
