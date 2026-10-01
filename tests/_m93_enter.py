# -*- coding: utf-8 -*-
"""m93：引用块内 Enter / Backspace（插入同级引用行 / 退出引用）
块菜单无「插入同级块」入口，引用内的同级新增实际由 Enter 承担。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m93.txt")
out = []
TOTAL = [0]
FAIL = [0]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def note(s):
    log("NOTE %s" % s)


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def jj(code):
    try:
        return json.loads(js(code) or "{}")
    except Exception:
        return {"_raw": js(code)}


def setdoc(lines, ms=800):
    js("window.setMarkdown(" + json.dumps("\n\n".join(lines)) + ")")
    wait(ms)


def getraw():
    return jj("window.__raw()").get("raw") or []


def focus_end(sel, ms=260):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';el.focus();"
       "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);var last=null,n;"
       "while(n=w.nextNode()){last=n;}"
       "var rg=document.createRange();"
       "if(last){rg.setStart(last,last.nodeValue.length);rg.collapse(true);}"
       "else{rg.selectNodeContents(el);rg.collapse(false);}"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(ms)


def focus_start(sel, ms=260):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';el.focus();"
       "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);var f=w.nextNode();"
       "var rg=document.createRange();"
       "if(f){rg.setStart(f,0);rg.collapse(true);}else{rg.selectNodeContents(el);rg.collapse(true);}"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(ms)


def key(sel, k, ms=380):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:" + json.dumps(k) +
       ",bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def blk_text(idx):
    r = jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
           "if(!b)return JSON.stringify({text:''});"
           "return JSON.stringify({text:(b.textContent||'').replace(/\\n/g,'|')})})()")
    return r.get("text") or ""


wait(2500)

note("========== 引用内 Enter / Backspace ==========")

# 1) 末尾 Enter → 新增同级引用行
setdoc(["前置段落", "> 引用第一行内容"])
focus_end("#editor .blk blockquote")
key("#editor .blk blockquote", "Enter")
r = getraw()
check("E1 引用末尾 Enter → 新增同级 '> ' 行",
      len(r) >= 2 and r[1].startswith("> 引用第一行内容\n> "),
      json.dumps(r, ensure_ascii=False))

# 2) 行首 Enter（引用中间）→ 拆分
setdoc(["前置段落", "> 引用第一行内容"])
focus_start("#editor .blk blockquote")
key("#editor .blk blockquote", "Enter")
r2 = getraw()
check("E2 引用行首 Enter → 拆分为两个引用行（不产生空段落）",
      r2[1].startswith("> ") and r2[1].count("> ") >= 2,
      json.dumps(r2, ensure_ascii=False))

# 3) 嵌套引用行首 Backspace → 退一级
setdoc(["前置段落", "> > 嵌套引用内容"])
focus_start("#editor .blk blockquote")
key("#editor .blk blockquote", "Backspace")
r3 = getraw()
check("E3 嵌套引用行首 Backspace → 退一级（> > → >）",
      r3[1].startswith("> ") and not r3[1].startswith("> >"),
      json.dumps(r3, ensure_ascii=False))

# 4) 单层引用行首 Backspace → 转段落
setdoc(["前置段落", "> 单层引用内容"])
focus_start("#editor .blk blockquote")
key("#editor .blk blockquote", "Backspace")
r4 = getraw()
check("E4 单层引用行首 Backspace → 退出引用转为段落",
      not r4[1].startswith("> "),
      json.dumps(r4, ensure_ascii=False))
t4 = blk_text(1)
check("E4b 退出引用后渲染态（无裸 '> '）", "> " not in t4 and t4.strip() != "",
      json.dumps(t4, ensure_ascii=False))

# 5) 引用末尾 Enter 后输入中文 → 渲染态
setdoc(["前置段落", "> 引用第一行内容"])
focus_end("#editor .blk blockquote")
key("#editor .blk blockquote", "Enter")
js("document.execCommand('insertText',false,'新增的第二行中文内容')")
wait(400)
r5 = getraw()
t5 = blk_text(1)
check("E5 新引用行输入中文 → 渲染态且内容完整",
      "新增的第二行中文内容" in (r5[1] or "") and "新增的第二行中文内容" in t5,
      "raw=%s text=%s" % (json.dumps(r5[1], ensure_ascii=False), json.dumps(t5, ensure_ascii=False)))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
