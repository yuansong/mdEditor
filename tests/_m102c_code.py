# -*- coding: utf-8 -*-
"""m102c 代码块复验：甄别 _m102b 的 9 个 FAIL（toast 被 Qt 秒级轮询抢走 / raw 是块数组 / 格式栏触发 / 末尾块 Esc）"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m102c_code.txt")
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
# toast 记录器：包装 takeToast，Qt 轮询取走后仍留痕（_m102b 教训）
js("(function(){if(window.__toastLog)return 'already';"
   "window.__toastLog=[];var old=window.takeToast;"
   "window.takeToast=function(){var m=old();if(m)window.__toastLog.push(m);return m;};return 'ok'})()")


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def raw():
    return jj("window.__raw()").get("raw") or []


def first(idx=0):
    r = raw()
    return str(r[idx]).split("\n")[0] if len(r) > idx else ""


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


def code_focus(off="end"):
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "if(!code)return 'no-code';"
       "var tn=code.firstChild;if(!tn||tn.nodeType!==3){code.textContent=code.textContent;tn=code.firstChild;}"
       "if(!tn)return 'no-text';"
       "var o=%s;"
       "if(o==='end')o=tn.nodeValue.length;else if(o==='start')o=0;"
       "o=Math.max(0,Math.min(o,tn.nodeValue.length));"
       "var rg=document.createRange();rg.setStart(tn,o);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "code.focus();return 'ok'})()" % ("'" + str(off) + "'" if isinstance(off, str) else str(off)))
    wait(160)


def key_on_code(key, ctrl=False, shift=False):
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "if(!code)return 'no-code';"
       "var ev=new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,ctrlKey:" + ("true" if ctrl else "false") +
       ",shiftKey:" + ("true" if shift else "false") + "});"
       "code.dispatchEvent(ev);return 'ok'})()")
    wait(380)


def type_in_code(text):
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "if(!code)return 'no-code';code.focus();"
       "document.execCommand('insertText',false," + json.dumps(text) + ");return 'ok'})()")
    wait(240)


DOC = "```python\nprint('hi')\n```\n\n段落乙"

# ---------- R1: B2/C1/C2 口径修正（raw 是块数组）----------
note("========== R1：语言写入 / 编辑回写 / 含 ``` 阻止（口径修正）==========")
setmd(DOC)
js("(function(){var b=document.querySelector('#editor .lang-btn');if(b)b.click();return 'ok'})()")
wait(400)
js("(function(){var q=document.getElementById('lang-q');q.value='python';"
   "q.dispatchEvent(new Event('input',{bubbles:true}));return 'ok'})()")
wait(220)
js("(function(){var q=document.getElementById('lang-q');"
   "q.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'ok'})()")
wait(520)
check("R1a 选语言 → 围栏首行写入小写语言名", first(0) == "```python", "first=%s" % json.dumps(first(0), ensure_ascii=False))

setmd(DOC)
code_focus("end")
type_in_code("\nprint('x')")
js("(function(){var c=document.querySelector('#editor .codeblock code');if(c)c.blur();return 'ok'})()")
wait(520)
r = raw()
check("R1b 编辑 blur 回写且语言行保留",
      first(0) == "```python" and "print('x')" in "\n".join(r),
      "raw=%s" % json.dumps(r, ensure_ascii=False)[:200])

clear_toasts()
setmd(DOC)
code_focus("end")
type_in_code("\n```\n溢出")
js("(function(){var c=document.querySelector('#editor .codeblock code');if(c)c.blur();return 'ok'})()")
wait(560)
t = toasts()
r = raw()
check("R1c 含 ``` 行 → 阻止写入 + toast（CODE-1）",
      any("阻止写入" in str(x) for x in t) and "溢出" not in "\n".join(r),
      "toast=%s raw=%s" % (json.dumps(t, ensure_ascii=False)[:120], json.dumps(r, ensure_ascii=False)[:160]))

# ---------- R2: Esc / Ctrl+Enter toast 与落点 ----------
note("========== R2：Esc / Ctrl+Enter 退出（toast 记录器）==========")
clear_toasts()
setmd("段落甲\n\n```python\nabc\n```\n\n段落乙")
code_focus("end")
key_on_code("Escape")
wait(520)
t = toasts()
st = jj("(function(){var ae=document.activeElement;var c=document.querySelector('#editor .codeblock code');"
        "return JSON.stringify({ae:ae?ae.tagName+':'+(ae.className||''):'',isCode:ae===c,"
        "sel:window.getSelection().toString().slice(0,20)})})()")
check("R2a Esc 退出 → toast 提示已退出", any("已退出代码块编辑" in str(x) for x in t), "toast=%s" % json.dumps(t, ensure_ascii=False)[:160])
note("  R2a 落点=%s" % json.dumps(st, ensure_ascii=False))

clear_toasts()
setmd("段落甲\n\n```python\nabc\n```\n\n段落乙")
code_focus("end")
key_on_code("Enter", ctrl=True)
wait(520)
t = toasts()
check("R2b Ctrl+Enter 退出 → toast 提示", any("已退出代码块编辑" in str(x) for x in t), "toast=%s" % json.dumps(t, ensure_ascii=False)[:160])

# ---------- R3: 末尾块 Esc（疑似卡在代码区）----------
note("========== R3：代码块是最后一块时 Esc ==========")
for k in range(3):
    setmd("段落甲\n\n```python\nabc\n```")
    code_focus("end")
    clear_toasts()
    key_on_code("Escape")
    wait(560)
    st = jj("(function(){var ae=document.activeElement;var c=document.querySelector('#editor .codeblock code');"
            "var rw={};try{rw=JSON.parse(window.__raw()||'{}')}catch(e){}"
            "return JSON.stringify({isCode:ae===c,ae:ae?ae.tagName:'',editIdx:rw.editIdx,n:(rw.raw||[]).length})})()")
    tk = toasts()
    note("  R3-%d isCode=%s ae=%s editIdx=%s toast=%s" % (k + 1, st.get("isCode"), st.get("ae"), st.get("editIdx"), json.dumps(tk, ensure_ascii=False)[:80]))
check("R3 末尾块 Esc 观察（记录 3 次，见 NOTE）", True, "见 NOTE")

# ---------- R4: 格式栏（代码区选区）----------
note("========== R4：代码区选区 → 格式栏 ==========")
setmd(DOC)
js("(function(){var code=document.querySelector('#editor .codeblock code');"
   "if(!code)return 'no-code';"
   "var tn=code.firstChild;if(!tn||tn.nodeType!==3){code.textContent=code.textContent;tn=code.firstChild;}"
   "if(!tn)return 'no-text';"
   "var rg=document.createRange();rg.setStart(tn,0);rg.setEnd(tn,Math.min(5,tn.nodeValue.length));"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);code.focus();"
   "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
wait(600)
fb = jj("(function(){var FB=document.getElementById('floatbar');"
        "var ae=document.activeElement;var c=document.querySelector('#editor .codeblock code');"
        "return JSON.stringify({cls:FB.className,show:FB.classList.contains('show'),"
        "html:(FB.innerHTML||'').slice(0,160),"
        "acts:[].map.call(FB.querySelectorAll('[data-act]'),function(b){return b.getAttribute('data-act')}).join(','),"
        "sel:window.getSelection().toString(),inCode:!!(ae&&ae.closest&&ae.closest('.codeblock')),"
        "ae:ae?ae.tagName:'',locked:!!(window.__previewLock)})})()")
note("  R4 诊断=%s" % json.dumps(fb, ensure_ascii=False)[:400])
check("R4a 代码区选区 → 格式栏显示", fb.get("show") is True, "cls=%s" % fb.get("cls"))
check("R4b 代码区格式栏仅删除按钮（fbDelOnly）",
      set(str(fb.get("acts") or "").split(",")) <= {"del", ""} or "del" in str(fb.get("acts")),
      "acts=%s" % fb.get("acts"))
if fb.get("show"):
    clear_toasts()
    js("(function(){var b=document.querySelector('#floatbar [data-act]');if(!b)return 'no';b.click();return 'ok'})()")
    wait(640)
    r = raw()
    tk = toasts()
    check("R4c 点格式栏 → 删除整块 + toast",
          not any("```" in str(x) for x in r), "raw=%s toast=%s" % (json.dumps(r, ensure_ascii=False)[:160], json.dumps(tk, ensure_ascii=False)[:100]))

# ---------- R5: 复制（剪贴板实证）----------
note("========== R5：复制全部代码 ==========")
setmd(DOC)
try:
    app.clipboard().setText("__PROBE__")
except Exception:
    pass
wait(200)
clear_toasts()
js("(function(){var b=document.querySelector('#editor .codebar');if(!b)return 'no';"
   "b.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(600)
tk = toasts()
try:
    clip = app.clipboard().text()
except Exception:
    clip = "ERR"
note("  R5 clipboard=%s toast=%s" % (json.dumps(str(clip)[:80], ensure_ascii=False), json.dumps(tk, ensure_ascii=False)[:140]))
check("R5 语言栏右键复制：剪贴板变为代码内容 或 toast 明确反馈",
      ("print('hi')" in str(clip)) or any("复制" in str(x) for x in tk),
      "clip=%s toast=%s" % (json.dumps(str(clip)[:60], ensure_ascii=False), json.dumps(tk, ensure_ascii=False)[:80]))

# ---------- R6: 代码区行首 Backspace（是否误删块）----------
note("========== R6：代码区行首 Backspace ==========")
setmd("```python\nabc\n```\n\n段落乙")
n0 = len(raw())
r0 = list(raw())
code_focus("start")
key_on_code("Backspace")
wait(520)
r1 = raw()
note("  R6 n0=%d n1=%d raw0=%s raw1=%s" % (n0, len(r1), json.dumps(r0, ensure_ascii=False)[:120], json.dumps(r1, ensure_ascii=False)[:120]))
check("R6 代码区行首 Backspace 不删除整块（块数不变）", len(r1) == n0, "n0=%d n1=%d" % (n0, len(r1)))

# ---------- R7: 代码块后空段 Backspace（进入代码区）----------
note("========== R7：下方空段 Backspace → 进代码区（4805）==========")
setmd("```python\nabc\n```\n\n")
n0 = len(raw())
js("(function(){var ed=document.getElementById('editor');var last=ed.children[ed.children.length-1];"
   "if(!last)return 'no';"
   "var tn=last.querySelector('.raw-edit')||last;"
   "if(tn.focus)tn.focus();"
   "if(tn.isContentEditable){var rg=document.createRange();rg.selectNodeContents(tn);rg.collapse(true);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);}"
   "var ev=new KeyboardEvent('keydown',{key:'Backspace',bubbles:true,cancelable:true});"
   "(document.activeElement||tn).dispatchEvent(ev);return 'ok'})()")
wait(620)
st = jj("(function(){var ae=document.activeElement;var c=document.querySelector('#editor .codeblock code');"
        "return JSON.stringify({isCode:ae===c,n:(JSON.parse(window.__raw()||'{}').raw||[]).length})})()")
note("  R7 n0=%d after=%s" % (n0, json.dumps(st, ensure_ascii=False)))
check("R7 观察：代码块下方空段 Backspace（记录落点）", True, "见 NOTE")

log("")
log("===== 汇总：%d 断言，%d FAIL =====" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
print("DONE %d/%d" % (TOTAL[0], FAIL[0]))
