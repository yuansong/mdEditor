# -*- coding: utf-8 -*-
"""v3.30.3 修复验证探针 _m39：BUG 清单（docs/BUG清单-dist40测试-v3.30.3.md）四项。

BUG-1 引用块内 / → 表格：网格面板打开 + 插入带 '> ' 前缀管道表（P1 修复验证）
BUG-2 引用块内 / → 代码块：插入 '> ```C … ``` 引用行（P1 修复验证）
BUG-4 空块折叠光标 Ctrl+B：raw 不变（不再插入 ****）；非空选区加粗仍正常
BUG-5 语言弹层 Esc 关闭：光标落回代码区（与 Enter 路径一致）
另验证：引用内 / → 图片入口可达（__wantPick）。
结果写 _m39.txt。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m39.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + " | " + name + " | " + str(extra))
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


wait(2500)

# ---------- BUG-1: 引用内 / → 表格 ----------
setmd("> 引用行")
wait(300)
js("(function(){var q=document.querySelector('#editor blockquote');"
   "if(!q)return 'noq';"
   "q.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
d = jj("(function(){var q=document.querySelector('#editor blockquote');"
       "var tgt=q.querySelector('.raw-edit')||q;"
       "tgt.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return JSON.stringify({sm:document.getElementById('slashmenu').classList.contains('show')})})()")
r = js("window.__slashPick('table', null)")
wait(400)
d = jj("(function(){var g=document.getElementById('tblsize');"
       "return JSON.stringify({pick:" + json.dumps(r) + ",grid:g.classList.contains('show')})})()")
check("BUG-1a 引用内选表格 → 网格面板打开",
      d.get("pick") == "OK" and d.get("grid") is True, json.dumps(d, ensure_ascii=False))
d = jj("(function(){var g=document.getElementById('tblsize');"
       "if(!g.classList.contains('show'))return 'nogrid';"
       "var c=g.querySelector('.gc[data-r=\"2\"][data-c=\"3\"]');"
       "if(!c)return 'nocell';"
       "c.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'clicked'})()")
wait(500)
rr = raw()
qtbl = jj("(function(){var q=document.querySelector('#editor blockquote table');"
          "return JSON.stringify({tbl:!!q,rows:q?q.querySelectorAll('tr').length:0,"
          "cols:q?q.tHead.rows[0].cells.length:0})})()")
ok1 = (d.get("_raw") == "clicked" and rr and rr[0].startswith("> 引用行")
       and "> | --- | --- | --- | --- |" in rr[0] and qtbl.get("tbl") is True
       and qtbl.get("rows") == 3 and qtbl.get("cols") == 4)
check("BUG-1b 引用内插入 3x4 管道表（行带 > 前缀，DOM 表格在引用内）",
      ok1, json.dumps([d, rr[:1], qtbl], ensure_ascii=False)[:600])

# ---------- BUG-2: 引用内 / → 代码块 ----------
setmd("> 引用行")
wait(300)
js("(function(){var q=document.querySelector('#editor blockquote');"
   "q.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
js("(function(){var q=document.querySelector('#editor blockquote');"
   "var tgt=q.querySelector('.raw-edit')||q;"
   "tgt.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(200)
r = js("window.__slashPick('code', null)")
wait(500)
rr = raw()
ok2 = (r == "OK" and rr and rr[0].startswith("> 引用行")
       and "> ```C" in rr[0] and rr[0].rstrip().endswith("```"))
d = jj("(function(){var q=document.querySelector('#editor blockquote');"
       "var ta=q?q.querySelector('textarea,.codeblock code'):null;"
       "return JSON.stringify({qcode:!!q,ed:!!(q&&q.querySelector('.qblk')),ta:!!ta})})()")
check("BUG-2 引用内插入代码块（> ```C … ```）",
      ok2, json.dumps([r, rr, d], ensure_ascii=False)[:600])

# ---------- BUG-2b: 引用内 / → 图片入口可达 ----------
setmd("> 引用行")
wait(300)
js("(function(){var q=document.querySelector('#editor blockquote');"
   "q.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,detail:1}));return 'x'})()")
wait(300)
js("(function(){var q=document.querySelector('#editor blockquote');"
   "var tgt=q.querySelector('.raw-edit')||q;"
   "tgt.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(200)
# 同步读取：__slashPick 置位 __wantPick 后立即读，再复位（避免 Qt collect 轮询竞态消费）
d = jj("(function(){window.__wantPick=false;"
       "var r=window.__slashPick('image', null);"
       "var pick=window.__wantPick===true;window.__wantPick=false;"
       "return JSON.stringify({r:r,pick:pick})})()")
wait(200)
js("window.__wantPick=false")
check("BUG-2b 引用内选图片 → Qt 面板接力标记置位（入口可达）",
      d.get("r") == "OK" and d.get("pick") is True, json.dumps(d, ensure_ascii=False))

# ---------- BUG-4: 空块折叠光标 Ctrl+B ----------
setmd("")
wait(300)
d = jj("(function(){var el=document.querySelector('.raw-edit');if(!el)return 'noraw';"
       "el.focus();var s=getSelection();var r2=document.createRange();"
       "r2.selectNodeContents(el);r2.collapse(false);s.removeAllRanges();s.addRange(r2);"
       "return 'ok'})()")
wait(200)
js("window.cmd('bold')"); wait(400)
rr = raw()
check("BUG-4a 空块折叠光标 Ctrl+B → raw 不变（无 ****）",
      rr == [""] or rr == [""], json.dumps([rr], ensure_ascii=False))
# 回归：非空选区加粗仍正常
d = jj("(function(){var el=document.querySelector('.raw-edit');if(!el)return 'noraw';"
       "el.focus();document.execCommand('insertText',false,'加粗文字');"
       "var s=getSelection();var r2=document.createRange();r2.selectNodeContents(el);"
       "s.removeAllRanges();s.addRange(r2);return 'ok'})()")
wait(200)
js("window.cmd('bold')"); wait(400)
rr = raw()
check("BUG-4b 非空选区 Ctrl+B 仍正常包裹 **…**",
      rr and rr[0] == "**加粗文字**", json.dumps(rr, ensure_ascii=False))

# ---------- BUG-5: 语言弹层 Esc → 光标回代码区 ----------
setmd("")
wait(300)
js("(function(){var el=document.querySelector('.raw-edit');"
   "if(el)el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
r = js("window.__slashPick('code', null)")
wait(400)
d = jj("(function(){var lp=document.getElementById('langpop');"
       "var q=document.getElementById('lang-q');"
       "return JSON.stringify({lp:lp.classList.contains('show'),qfocus:document.activeElement===q})})()")
check("BUG-5a 插入代码块 → 语言弹层自动打开且输入框聚焦",
      d.get("lp") is True and d.get("qfocus") is True, json.dumps([r, d], ensure_ascii=False))
js("(function(){var q=document.getElementById('lang-q');"
   "q.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
d = jj("(function(){var code=document.querySelector('#editor .codeblock code');"
       "return JSON.stringify({lpshown:document.getElementById('langpop').classList.contains('show'),"
       "focused:document.activeElement===code,hascode:!!code})})()")
check("BUG-5b Esc 关闭语言弹层 → 光标落回代码区",
      d.get("lpshown") is False and d.get("focused") is True and d.get("hascode") is True,
      json.dumps(d, ensure_ascii=False))
# 回归：Enter 确认路径仍正常
setmd("")
wait(300)
js("(function(){var el=document.querySelector('.raw-edit');"
   "if(el)el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'x'})()")
wait(300)
js("window.__slashPick('code', null)")
wait(400)
js("(function(){var q=document.getElementById('lang-q');"
   "q.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'x'})()")
wait(400)
d = jj("(function(){var code=document.querySelector('#editor .codeblock code');"
       "return JSON.stringify({focused:document.activeElement===code})})()")
rr = raw()
check("BUG-5c Enter 确认路径回归：光标进代码区 + raw 写回（v3.30.18 CODE-7 小写化）",
      d.get("focused") is True and any(b.startswith("```c") for b in rr),
      json.dumps([d, rr], ensure_ascii=False)[:400])

out.append("DONE")
flush()
print("done")
