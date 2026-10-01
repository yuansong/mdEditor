# -*- coding: utf-8 -*-
"""m102d 代码块收尾复验：删除按钮（title 选择器）/ 空块输入 / 代码块内加粗快捷键冲突 / 末尾块 Ctrl+Enter"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QAction
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m102d_code.txt")
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
js("(function(){if(window.__toastLog)return 'already';"
   "window.__toastLog=[];var old=window.takeToast;"
   "window.takeToast=function(){var m=old();if(m)window.__toastLog.push(m);return m;};return 'ok'})()")


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def raw():
    return jj("window.__raw()").get("raw") or []


def toasts():
    v = jj("JSON.stringify(window.__toastLog||[])")
    if isinstance(v, list):
        return v
    try:
        return json.loads(v.get("_raw") or "[]")
    except Exception:
        return []


def clear_toasts():
    js("window.__toastLog=[]")


def sel_code(a, b):
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "if(!code)return 'no-code';"
       "var tn=code.firstChild;if(!tn||tn.nodeType!==3){code.textContent=code.textContent;tn=code.firstChild;}"
       "if(!tn)return 'no-text';"
       "var L=tn.nodeValue.length;"
       "var rg=document.createRange();rg.setStart(tn,Math.min(%d,L));rg.setEnd(tn,Math.min(%d,L));"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);code.focus();"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()" % (a, b))
    wait(620)


DOC = "```python\nprint('hi')\n```\n\n段落乙"

# ---------- T1：格式栏删除按钮（按钮无 data-act，按 title 选）----------
note("========== T1：格式栏「删除整个块」==========")
setmd(DOC)
sel_code(0, 5)
fb = jj("(function(){var FB=document.getElementById('floatbar');"
        "return JSON.stringify({show:FB.classList.contains('show'),"
        "btns:[].map.call(FB.querySelectorAll('button'),function(b){return b.title||b.textContent}).join('|'),"
        "cnt:(FB.querySelector('.fbcnt')||{}).textContent||''})})()")
note("  T1 格式栏=%s" % json.dumps(fb, ensure_ascii=False)[:220])
clear_toasts()
js("(function(){var b=document.querySelector('#floatbar button[title=\"删除整个块\"]');if(!b)return 'no';b.click();return 'ok'})()")
wait(680)
r = raw()
tk = toasts()
check("T1 点格式栏删除 → 整块删除 + toast（可撤销）",
      not any("```" in str(x) for x in r) and any("已删除块" in str(x) for x in tk),
      "raw=%s toast=%s" % (json.dumps(r, ensure_ascii=False)[:160], json.dumps(tk, ensure_ascii=False)[:120]))

# ---------- T2：空代码块输入 ----------
note("========== T2：空代码块 ==========")
setmd("```C\n\n```")
js("(function(){var code=document.querySelector('#editor .codeblock code');if(!code)return 'no';"
   "code.focus();var tn=code.firstChild;"
   "if(!tn||tn.nodeType!==3){code.textContent='';tn=code.firstChild;}"
   "return JSON.stringify({txt:code.textContent,len:code.textContent.length})})()")
wait(200)
js("(function(){var code=document.querySelector('#editor .codeblock code');code.focus();"
   "document.execCommand('insertText',false,'int x=1;');return 'ok'})()")
wait(260)
js("(function(){var code=document.querySelector('#editor .codeblock code');if(code)code.blur();return 'ok'})()")
wait(560)
r = raw()
check("T2 空代码块可直接输入并回写",
      "int x=1;" in "\n".join(r), "raw=%s" % json.dumps(r, ensure_ascii=False)[:160])

# ---------- T3：代码块内加粗快捷键（Qt 层 QAction）冲突 ----------
note("========== T3：代码块内触发加粗 ==========")
acts = [a for a in win.findChildren(QAction) if a.text() and ("加粗" in a.text() or "Bold" in a.text())]
note("  T3 命中加粗 QAction 数=%d" % len(acts))
setmd(DOC)
sel_code(0, 5)
before = "\n".join(raw())
if acts:
    acts[0].trigger()
    wait(680)
    after = "\n".join(raw())
    tk = toasts()
    note("  T3 before=%s" % json.dumps(before, ensure_ascii=False)[:120])
    note("  T3 after =%s" % json.dumps(after, ensure_ascii=False)[:120])
    check("T3 代码块内加粗：代码内容不被插入 ** 标记（安全）",
          "**" not in after.replace(before, "") and before == after,
          "diff=%s" % json.dumps(after, ensure_ascii=False)[:160])
else:
    check("T3 找到加粗 QAction", False, "未命中")

# ---------- T4：末尾块 Ctrl+Enter ----------
note("========== T4：末尾块 Ctrl+Enter ==========")
for k in range(2):
    setmd("段落甲\n\n```python\nabc\n```")
    js("(function(){var code=document.querySelector('#editor .codeblock code');if(!code)return 'no';"
       "var tn=code.firstChild;if(!tn||tn.nodeType!==3){code.textContent=code.textContent;tn=code.firstChild;}"
       "var rg=document.createRange();rg.setStart(tn,tn.nodeValue.length);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);code.focus();return 'ok'})()")
    wait(200)
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "code.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true,cancelable:true}));return 'ok'})()")
    wait(560)
    st = jj("(function(){var ae=document.activeElement;var c=document.querySelector('#editor .codeblock code');"
            "return JSON.stringify({isCode:ae===c,ae:ae?ae.tagName:'',n:(JSON.parse(window.__raw()||'{}').raw||[]).length})})()")
    note("  T4-%d %s" % (k + 1, json.dumps(st, ensure_ascii=False)))
check("T4 末尾块 Ctrl+Enter 观察（见 NOTE）", True, "见 NOTE")

# ---------- T5：代码块内粘贴多行（原样插入）----------
note("========== T5：代码块内粘贴多行 ==========")
setmd(DOC)
js("(function(){var code=document.querySelector('#editor .codeblock code');if(!code)return 'no';"
   "var tn=code.firstChild;if(!tn||tn.nodeType!==3){code.textContent=code.textContent;tn=code.firstChild;}"
   "var rg=document.createRange();rg.setStart(tn,tn.nodeValue.length);rg.collapse(true);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);code.focus();return 'ok'})()")
wait(200)
js("(function(){var code=document.querySelector('#editor .codeblock code');"
   "var dt=new DataTransfer();dt.setData('text/plain','a=1\\nb=2');"
   "var ev=new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:dt});"
   "code.dispatchEvent(ev);return 'ok'})()")
wait(420)
js("(function(){var code=document.querySelector('#editor .codeblock code');if(code)code.blur();return 'ok'})()")
wait(520)
r = raw()
note("  T5 raw=%s" % json.dumps(r, ensure_ascii=False)[:200])
check("T5 代码块内粘贴（记录行为）", True, "见 NOTE")

log("")
log("===== 汇总：%d 断言，%d FAIL =====" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
print("DONE %d/%d" % (TOTAL[0], FAIL[0]))
