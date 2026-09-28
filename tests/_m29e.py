# -*- coding: utf-8 -*-
"""v3.29 诊断 2：'*' 包裹与 Enter 分支是否被接管（defaultPrevented 判定）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29e.txt")
out = []


def note(tag, extra):
    out.append(f"NOTE | {tag} | {extra}")
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


wait(2500)

Q1 = "> 第一行内容\n> 第二行内容"
js(f"window.setMarkdown({json.dumps(Q1)})")
wait(700)

# --- H1：环境探针：__previewLock、块类名、blockIndexOf 可达性 ---
d = jj("(function(){var bq=document.querySelector('#editor blockquote');"
       "var blk=bq?bq.closest('.blk'):null;"
       "return JSON.stringify({previewLock:!!window.__previewLock,"
       "blkClass:blk?blk.className:'none',isDirectChild:blk?blk.parentNode.id==='editor':false,"
       "bqEditable:bq.getAttribute('contenteditable')})})()")
note("H1 环境", str(d))

# --- H2：跨行选区 + '*'：捕获监听 defaultPrevented ---
d = jj("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
       "var sel=getSelection();var rg=document.createRange();"
       "rg.selectNodeContents(bq);sel.removeAllRanges();sel.addRange(rg);"
       "var r2=sel.rangeCount?sel.getRangeAt(0):null;"
       "var selTxt=(r2&&!r2.collapsed&&bq.contains(r2.startContainer))?r2.toString():'';"
       "var cap={seen:false,pd:false,tgt:''};"
       "var h=function(e){if(e.key==='*'){cap.seen=true;cap.pd=e.defaultPrevented;cap.tgt=e.target.tagName;}};"
       "document.addEventListener('keydown',h,true);"
       "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'*',bubbles:true,cancelable:true}));"
       "document.removeEventListener('keydown',h,true);"
       "cap.pdAfter=cap.pd;"
       "return JSON.stringify({selTxtLen:selTxt.length,selTxtNL:selTxt.indexOf('\\n')>=0,"
       "seen:cap.seen,prevented:cap.pd,tgt:cap.tgt})})()")
note("H2 跨行 * 接管判定", str(d))
wait(500)
note("H2 raw", str(raw()))

# --- H3：单行内选区 + '*'（同块内非跨行）---
js(f"window.setMarkdown({json.dumps(Q1)})")
wait(700)
d = jj("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
       "var tn=bq.firstChild;var sel=getSelection();var rg=document.createRange();"
       "rg.setStart(tn,0);rg.setEnd(tn,tn.textContent.length);"
       "sel.removeAllRanges();sel.addRange(rg);"
       "var h=function(e){if(e.key==='*'){window.__pd=e.defaultPrevented;}};"
       "document.addEventListener('keydown',h,true);"
       "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'*',bubbles:true,cancelable:true}));"
       "document.removeEventListener('keydown',h,true);"
       "return JSON.stringify({prevented:window.__pd})})()")
note("H3 单行 * 接管判定", str(d))
wait(500)
note("H3 raw", str(raw()))

# --- H4：Enter（非空行）：判定 + 现场条件 ---
js(f"window.setMarkdown({json.dumps(Q1)})")
wait(700)
d = jj("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
       "var sel=getSelection();var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
       "sel.removeAllRanges();sel.addRange(rg);"
       "var txt=bq.textContent.replace(/\\u00a0/g,' ');"
       "var h=function(e){if(e.key==='Enter'){window.__pd2=e.defaultPrevented;}};"
       "document.addEventListener('keydown',h,true);"
       "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
       "document.removeEventListener('keydown',h,true);"
       "return JSON.stringify({prevented:window.__pd2,txt:txt,tail:JSON.stringify(txt.slice(-8))})})()")
note("H4 Enter 接管判定", str(d))
wait(500)
note("H4 raw", str(raw()))

out.append("DONE")
flush()
print("done")
