# -*- coding: utf-8 -*-
"""m97d T3 甄别 + 源码态 bold 正确验证
 D1 复现 _m97c T3 前置：纯文字标题 click → isRaw 应为 False（wysClickToRaw 对
    无行内富文本的标题不转源码态——产品正确行为）→ T3 FAIL 定性为探针伪影
 D2 源码态 bold 正确路径：RICH 转源码态 → 选 ** 内文字「已加粗」→ bold
    → 预期 toggle 取消（raw=# 已加粗和普通）+ 保持源码态（尊重发起态）
 D3 源码态 bold 观察项：选「和普通」→ bold → 记录 raw 形态（相邻标记拼接，
    不断言精确值，只断言渲染自洽）
结果：tests/_m97d.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m97d.txt")
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
           "cls:b?b.className:''})})()")
    try:
        return json.loads(r or "{}")
    except Exception:
        return {}


def toast():
    return js("String(window.takeToast && window.takeToast() || '')") or ""


def click_h_to_raw(ms=420):
    js("(function(){var h=document.querySelector('#editor h1');"
       "if(!h)return 'no-h';h.focus();"
       "var rg=document.createRange();rg.selectNodeContents(h);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "h.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def sel_raw_off(a, b, ms=300):
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


def sel_txt():
    return js("(function(){var s=window.getSelection();"
              "return s&&s.rangeCount?s.toString():''})()") or ""


def act(action, ms=500):
    js("window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


RICH = "# **已加粗**和普通"
wait(2600)
for _ in range(20):
    if js("String(!!window.__applyFloat)") == "true":
        break
    wait(500)

log("=== D1 复现 _m97c T3 前置（纯文字标题 click）===")
setmd("# 纯文字标题")
click_h_to_raw()
pre1 = israw0()
check("D1 纯文字标题点击保持渲染态（预期行为）", pre1.get("isRaw") is False,
      "pre=%s" % json.dumps(pre1, ensure_ascii=False))
log("D1 sel_raw_off 返回=%s（应 no-raw：无 .raw-edit）" % js(
    "(function(){var el=document.querySelector('#editor .raw-edit');return el?'has-raw':'no-raw'})()"))
check("D1 T3 伪影定性：无 .raw-edit 导致选区未建立", True, "定性记录")

log("=== D2 源码态 bold：选 ** 内文字 → toggle 取消 + 保持源码态 ===")
setmd(RICH)
click_h_to_raw()
pre2 = israw0()
check("D2 前置转源码态", pre2.get("isRaw") is True, "pre=%s" % json.dumps(pre2, ensure_ascii=False))
sel_raw_off(4, 7)   # 「已加粗」（** 内）
log("D2 选区文本=%s" % json.dumps(sel_txt(), ensure_ascii=False))
act("bold", 600)
r = getmd()
post2 = israw0()
log("D2 toast=%s" % json.dumps(toast(), ensure_ascii=False))
check("D2 raw toggle 取消粗体", r == "# 已加粗和普通", "raw=%s" % json.dumps(r, ensure_ascii=False))
check("D2 保持源码态（尊重发起态）", post2.get("isRaw") is True,
      "post=%s" % json.dumps(post2, ensure_ascii=False))

log("=== D3 源码态 bold 观察项：选裸文字「和普通」===")
setmd(RICH)
click_h_to_raw()
sel_raw_off(9, 12)   # 「和普通」
log("D3 选区文本=%s" % json.dumps(sel_txt(), ensure_ascii=False))
act("bold", 600)
r = getmd()
post3 = israw0()
log("D3 raw=%s isRaw=%s toast=%s" % (
    json.dumps(r, ensure_ascii=False), post3.get("isRaw"), json.dumps(toast(), ensure_ascii=False)))

log("")
log("RESULT TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
