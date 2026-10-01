# -*- coding: utf-8 -*-
"""m105e 分割线最终复验：先真实点击进入编辑态，再验 HR-3（行首 Backspace 删 hr）
      与段末 Delete 的正确预期（进入 hr 渲染态而非删除）"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105e_hr.txt")
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


def setmd(md, ms=850):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getmd():
    return js("window.getMarkdown()") or ""


def enter_block(idx):
    """真实点击第 idx 块使其进入编辑态，返回编辑态信息"""
    js("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
       "var b=bs[" + str(idx) + "];if(!b)return 'noblk';"
       "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
       "b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(600)
    return js("(function(){var ae=document.activeElement;"
              "return JSON.stringify({tag:ae?ae.tagName:'none',"
              "ce:ae?ae.getAttribute('contenteditable'):null,"
              "txt:ae?(ae.textContent||ae.value||'').slice(0,10):''})})()")


def caret_start():
    return js("(function(){var ae=document.activeElement;if(!ae)return 'noae';"
              "var rg=document.createRange();"
              "try{rg.selectNodeContents(ae)}catch(e){return 'norang'}"
              "rg.collapse(true);"
              "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
              "return 'ok'})()")


def caret_end():
    return js("(function(){var ae=document.activeElement;if(!ae)return 'noae';"
              "if(ae.tagName==='TEXTAREA'){ae.setSelectionRange(ae.value.length,ae.value.length);return 'ta'}"
              "var rg=document.createRange();"
              "try{rg.selectNodeContents(ae)}catch(e){return 'norang'}"
              "rg.collapse(false);"
              "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
              "return 'ok'})()")


def keyel(k):
    return js("(function(){var t=document.activeElement||document.body;"
              "t.dispatchEvent(new KeyboardEvent('keydown',{key:'" + k +
              "',bubbles:true,cancelable:true}));return 'ok'})()")


note("========== U1 HR-3：hr 下方段首 Backspace（真实编辑态）==========")
setmd("甲\n\n---\n\n乙")
note("  U1 进入乙段：%s" % enter_block(2))
note("  U1 活动元素=%s" % js("(function(){var ae=document.activeElement;"
                            "return ae?(ae.tagName+'|'+(ae.textContent||ae.value||'').slice(0,8)):'none'})()"))
note("  U1 caret=%s" % caret_start())
wait(300)
keyel("Backspace")
wait(800)
md = getmd()
note("  U1 Backspace 后 md=%s" % json.dumps(md, ensure_ascii=False))
check("U1[HR-3] hr 下方段首 Backspace → 删除 hr、文本保留",
      "---" not in md and "甲" in md and "乙" in md,
      "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== U2 段末 Delete（下方是 hr）正确预期 ==========")
setmd("甲\n\n---\n\n乙")
note("  U2 进入甲段：%s" % enter_block(0))
caret_end()
wait(300)
keyel("Delete")
wait(800)
md = getmd()
note("  U2 Delete 后 md=%s" % json.dumps(md, ensure_ascii=False))
check("U2 段末 Delete 不把 hr 并入文本（raw 保持 ---）",
      "---" in md and md.count("---") == 1, "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== U3 空段上方是 hr（5001 场景）==========")
setmd("甲\n\n---\n\n乙")
# 构造：在 hr 后插入空段 —— 用 Ctrl+Enter 或 goToBlock 后回车
js("(function(){var f=window.goToBlock||window.__goToBlock;"
   "if(typeof f==='function'){f(1,'end')}return 'ok'})()")
wait(500)
note("  U3 goToBlock 后活动元素=%s" % js("(function(){var ae=document.activeElement;"
                                        "return ae?(ae.tagName+'|'+(ae.textContent||ae.value||'').slice(0,8)):'none'})()"))
keyel("Enter")
wait(700)
md1 = getmd()
note("  U3 回车后 md=%s" % json.dumps(md1, ensure_ascii=False))
keyel("Enter")
wait(700)
md2 = getmd()
note("  U3 再回车后 md=%s" % json.dumps(md2, ensure_ascii=False))
note("  U3 说明：末尾 hr 后回车按 HR-1 应追加空段并进入")

note("========== U4 块菜单覆盖度（修正 7964 误读）==========")
setmd("甲\n\n---\n\n乙")
menu = js("(function(){var h=document.querySelector('#editor hr');if(!h)return 'nohr';"
          "h.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));"
          "var BM=document.getElementById('blkmenu');"
          "return JSON.stringify({show:BM?BM.classList.contains('show'):null,"
          "txt:BM?(BM.textContent||''):''})})()")
wait(500)
note("  U4=%s" % str(menu)[:300])
check("U4 hr 右键块菜单含「删除块」", "删除块" in str(menu), "menu=%s" % str(menu)[:240])
check("U4b hr 右键块菜单含「复制块」", "复制块" in str(menu), "menu=%s" % str(menu)[:240])
check("U4c hr 右键块菜单含「上移/下移」", "上移" in str(menu) and "下移" in str(menu),
      "menu=%s" % str(menu)[:240])

note("========== U5 块菜单删除 hr ==========")
setmd("甲\n\n---\n\n乙")
js("(function(){var h=document.querySelector('#editor hr');if(!h)return 'nohr';"
   "h.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(600)
js("(function(){var BM=document.getElementById('blkmenu');if(!BM)return 'nobm';"
   "var items=[].slice.call(BM.querySelectorAll('[data-act]'));"
   "for(var k=0;k<items.length;k++){if((items[k].textContent||'').indexOf('删除块')>=0)"
   "{items[k].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'clicked'}}"
   "return 'notfound:'+items.map(function(i){return i.getAttribute('data-act')}).join(',')})()")
wait(800)
md = getmd()
note("  U5 块菜单删除后 md=%s" % json.dumps(md, ensure_ascii=False))
check("U5 块菜单「删除块」可删除 hr", "---" not in md, "md=%s" % json.dumps(md, ensure_ascii=False))

log("\n==== 合计 %d 项，FAIL %d ====" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABNORMAL " + a)
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
