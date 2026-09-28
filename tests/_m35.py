# -*- coding: utf-8 -*-
"""v3.30.3 探针 _m35：标题×删除线 toggle（再点一次取消而非叠加 ~~）+
图片选中态滚动清除（滚轮滚动不残留蓝色边框）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m35.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + " | " + name + (" | " + str(extra) if extra else ""))
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def jj(code):
    r = js(code)
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md) + ")"); wait(ms)


def sel_range(sel, a, b):
    call = ("(function(){try{var el=document.querySelector(" + json.dumps(sel) + ");if(!el)return 'no-el';"
            "el.focus();var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT,null);"
            "var n,acc=0,s=null,e=null;"
            "while((n=w.nextNode())){var L=n.nodeValue.length;"
            "if(s===null&&acc+L>=" + str(a) + "){s={n:n,o:" + str(a) + "-acc};}"
            "if(e===null&&acc+L>=" + str(b) + "){e={n:n,o:" + str(b) + "-acc};}"
            "acc+=L;}"
            "if(!s||!e)return 'range-err';"
            "var r=document.createRange();r.setStart(s.n,s.o);r.setEnd(e.n,e.o);"
            "var g=getSelection();g.removeAllRanges();g.addRange(r);return 'ok';}"
            "catch(ex){return 'EXC:'+(ex&&ex.message||ex)}})()")
    return js(call)


wait(2500)

# C1: 渲染态标题 删除线 应用 → raw 含 ~~
setmd("## 我的标题")
r = sel_range("h2", 0, 4)
check("C1 选中标题文本", r == "ok", r)
js("window.cmd('strike')"); wait(300)
rr = raw()
check("C1 删除线写入 raw", len(rr) == 1 and rr[0] == "## ~~我的标题~~", json.dumps(rr, ensure_ascii=False))

# C2: 再次点击删除线 → 取消（raw 回到无标记），不出现 ~~~~ 或字面 ~~
r = sel_range("h2", 0, 4)
check("C2 选区恢复", r == "ok", r)
js("window.cmd('strike')"); wait(300)
rr = raw()
check("C2 二次点击取消删除线", len(rr) == 1 and rr[0] == "## 我的标题", json.dumps(rr, ensure_ascii=False))

# C3: 粗体 toggle 同语义（渲染态标题）
setmd("## 加粗标题")
r = sel_range("h2", 0, 4)
check("C3 选中", r == "ok", r)
js("window.cmd('bold')"); wait(300)
rr = raw()
check("C3 粗体写入", len(rr) == 1 and rr[0] == "## **加粗标题**", json.dumps(rr, ensure_ascii=False))
r = sel_range("h2", 0, 4)
js("window.cmd('bold')"); wait(300)
rr = raw()
check("C3 粗体取消", len(rr) == 1 and rr[0] == "## 加粗标题", json.dumps(rr, ensure_ascii=False))

# C4: 正文段落删除线 toggle（回归：普通段落同样可取消）
setmd("普通段落文字")
r = sel_range("#editor .blk p", 0, 6)
if r != "ok":
    d = jj("(function(){var b=document.querySelector('#editor .blk');"
           "return JSON.stringify({cls:b?b.className:null, html:b?b.innerHTML.slice(0,120):null})})()")
    out.append("C4 DIAG: " + json.dumps(d, ensure_ascii=False)); flush()
check("C4 段落选中", r == "ok", r)
js("window.cmd('strike')"); wait(300)
rr = raw()
check("C4 段落删除线写入", len(rr) == 1 and rr[0] == "~~普通段落文字~~", json.dumps(rr, ensure_ascii=False))
r = sel_range("#editor .blk p", 0, 6)
js("window.cmd('strike')"); wait(300)
rr = raw()
check("C4 段落删除线取消", len(rr) == 1 and rr[0] == "普通段落文字", json.dumps(rr, ensure_ascii=False))

# C5: 图片选中态 + 滚动 → 选中态清除（蓝框消失）
setmd("![图](x.png)", 900)
r = js("(function(){var img=document.querySelector('#editor img');"
       "img.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
       "var errs=[];window.onerror=function(m){errs.push(String(m));return false;};"
       "var ed=document.getElementById('editor');"
       "var r1=JSON.parse(window.__objSel()||'null');"
       "ed.dispatchEvent(new Event('scroll'));"
       "var r2=JSON.parse(window.__objSel()||'null');"
       "return JSON.stringify({before:r1, after:r2, errs:errs,"
       " imgSel:img.classList.contains('sel')})})()")
d = {}
try:
    d = json.loads(r or "{}")
except Exception:
    d = {}
check("C5 图片选中后滚动清除", d.get("before") and d.get("before", {}).get("kind") == "img"
      and d.get("after") is None and not d.get("imgSel") and not d.get("errs"), r)

out.append("DONE")
flush()
print("done")
