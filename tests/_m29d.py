# -*- coding: utf-8 -*-
"""v3.29 诊断探针：引用块 FAIL 项定位（不判 PASS/FAIL，只输出现场）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29d.txt")
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

# --- 诊断 A：blockquote DOM 结构与内部函数可用性 ---
d = jj("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return JSON.stringify({bq:false});"
       "var fc=bq.firstChild;"
       "return JSON.stringify({bq:true,html:bq.innerHTML.slice(0,80),"
       "fcType:fc?(fc.nodeType===3?'text':'el:'+fc.tagName):'none',"
       "fcText:fc?fc.textContent.slice(0,20):'',"
       "fnAP:typeof autoPairKey,fnSel:typeof selTextIn,fnMap:typeof mapPlainToRaw,"
       "modeAP:modes.autoPair,apPairStar:!!AP_PAIRS['*'],apSkipStar:!!AP_SKIP['*']})})()")
note("A quote DOM + 内部函数", str(d))

# --- 诊断 B：设置跨行选区后，selTextIn / caretRawOffset 返回什么 ---
d = jj("(function(){try{var bq=document.querySelector('#editor blockquote');bq.focus();"
       "var sel=getSelection();var rg=document.createRange();"
       "rg.selectNodeContents(bq);sel.removeAllRanges();sel.addRange(rg);"
       "var t=sel.toString();"
       "return JSON.stringify({selLen:t.length,hasNL:t.indexOf('\\n')>=0,"
       "selTxt:selTextIn(bq),caretOff:caretRawOffset(bq),selCollapsed:sel.isCollapsed})}catch(e){"
       "return JSON.stringify({err:String(e)})}})()")
note("B 选区 + selTextIn", str(d))

# --- 诊断 C：手动 dispatch '*'，try/catch 捕获异常 ---
d = jj("(function(){try{var bq=document.querySelector('#editor blockquote');"
       "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'*',bubbles:true,cancelable:true}));"
       "return JSON.stringify({ok:true})}catch(e){return JSON.stringify({err:String(e),stack:e.stack})}})()")
note("C dispatch *", str(d))
wait(500)
note("C2 raw after *", str(raw()))

# --- 诊断 D：Enter 分支条件现场 ---
js(f"window.setMarkdown({json.dumps(Q1)})")
wait(700)
d = jj("(function(){try{var bq=document.querySelector('#editor blockquote');bq.focus();"
       "var sel=getSelection();var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
       "sel.removeAllRanges();sel.addRange(rg);"
       "var txt=bq.textContent.replace(/\\u00a0/g,' ');"
       "var off=caretRawOffset(bq);"
       "return JSON.stringify({txt:txt,off:off,lines:txt.split('\\n'),"
       "qi:txt.slice(0,off).split('\\n').length-1,"
       "lastLine:txt.split('\\n')[txt.split('\\n').length-1]})}catch(e){"
       "return JSON.stringify({err:String(e)})}})()")
note("D Enter 分支条件", str(d))
d = jj("(function(){try{document.querySelector('#editor blockquote')"
       ".dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
       "return JSON.stringify({ok:true})}catch(e){return JSON.stringify({err:String(e),stack:e.stack})}})()")
note("E dispatch Enter#1", str(d))
wait(500)
note("E2 raw after Enter#1", str(raw()))
d = jj("(function(){try{var bq=document.querySelector('#editor blockquote');if(!bq)return JSON.stringify({bq:false});"
       "bq.focus();var sel=getSelection();var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
       "sel.removeAllRanges();sel.addRange(rg);"
       "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
       "return JSON.stringify({ok:true})}catch(e){return JSON.stringify({err:String(e),stack:e.stack})}})()")
note("F dispatch Enter#2", str(d))
wait(500)
note("F2 raw after Enter#2", str(raw()))
d = jj("(function(){return JSON.stringify({edit:!!document.querySelector('#editor .raw-edit')})})()")
note("F3 inEdit", str(d))

# --- 诊断 G：qblk 表格渲染现场 ---
Q5 = "> 前文\n> | a | b |\n> | --- | --- |\n> | 1 | 2 |\n> 后文"
js(f"window.setMarkdown({json.dumps(Q5)})")
wait(700)
d = jj("(function(){var q=document.querySelector('#editor .b-quote .qblk');"
       "return JSON.stringify({qblk:!!q,inner:q?q.innerHTML.slice(0,120):null,"
       "raw:q?q.getAttribute('data-raw'):null})})()")
note("G qblk inner", str(d))
d = jj("(function(){var bq=document.querySelector('#editor .b-quote blockquote');"
       "return JSON.stringify({html:bq?bq.innerHTML.slice(0,200):null})})()")
note("G2 quote html", str(d))

out.append("DONE")
flush()
print("done")
