# -*- coding: utf-8 -*-
"""_m40d：插桩定位弹层关闭调用链 + 补跑 m40c 中断的 D5/D6/D7。
DOMTokenList.remove 打补丁记录 'show' 移除时的调用堆栈。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m40d.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + " | " + name + (" | " + str(extra) if extra else ""))
    flush()


def note(msg):
    out.append("NOTE | " + msg)
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


def raw_():
    return jj("window.__raw()").get("raw") or [""]


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md) + ")"); wait(ms)


def shown(pop_id):
    return jj("(function(){var p=document.getElementById(" + json.dumps(pop_id) + ");"
              "return JSON.stringify({s:!!(p&&p.classList.contains('show'))})})()").get("s")


def click_el(sel, ms=300, ev="mousedown"):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "el.dispatchEvent(new MouseEvent(" + json.dumps(ev) + ",{bubbles:true,cancelable:true,detail:1}));"
       "return 'ok'})()")
    wait(ms)


def patch():
    js("(function(){if(window.__patched)return 'already';"
       "var orig=DOMTokenList.prototype.remove;window.__closes=[];"
       "DOMTokenList.prototype.remove=function(tok){"
       "if(tok==='show'){try{window.__closes.push(String(new Error().stack||'').split('\\n').slice(2,5).join(' <- '))}"
       "catch(e){window.__closes.push('err')}}"
       "return orig.call(this,tok)};window.__patched=true;return 'ok'})()")


def take_closes(ms=200):
    r = js("(function(){var c=window.__closes||[];window.__closes=[];return JSON.stringify(c)})()")
    wait(ms)
    try: return json.loads(r or "[]")
    except Exception: return [str(r)]


wait(2500)

# ===== S1: stylepop 打开 → 滚动 → 谁关的 =====
setmd("说明段落。\n\n```python\nprint(1)\n```")
wait(600)
patch()
click_el("#editor .codebar .style-btn", 350, ev="click")
sp1 = shown("stylepop")
js("(function(){var ed=document.getElementById('editor');ed.dispatchEvent(new Event('scroll'));return 'ok'})()")
wait(300)
sp2 = shown("stylepop")
cl = take_closes()
note("S1 stylepop 打开=%s 滚动后=%s 关闭堆栈=%s" % (sp1, sp2, json.dumps(cl, ensure_ascii=False)[:600]))
check("S1 stylepop 随滚动关闭（调用链已抓取）", sp1 and not sp2, json.dumps(cl, ensure_ascii=False)[:400])

# ===== S2: stylepop 打开 → 渲染态标题 mousedown → 谁关的 =====
setmd("# 大标题\n\n说明段落。\n\n```python\nprint(1)\n```")
wait(700)
click_el("#editor .codebar .style-btn", 350, ev="click")
sp1 = shown("stylepop")
click_el("#editor .blk:nth-child(1) h1", 300)
sp2 = shown("stylepop")
cl = take_closes()
note("S2 stylepop 打开=%s 点标题后=%s 关闭堆栈=%s" % (sp1, sp2, json.dumps(cl, ensure_ascii=False)[:600]))
check("S2 stylepop 点击渲染态标题关闭（调用链已抓取）", sp1 and not sp2, json.dumps(cl, ensure_ascii=False)[:400])

# ===== S3: langpop 打开 → 滚动 =====
setmd("说明段落。\n\n```python\nprint(1)\n```")
wait(600)
click_el("#editor .codebar .lang-btn", 350, ev="click")
lp1 = shown("langpop")
js("(function(){var ed=document.getElementById('editor');ed.dispatchEvent(new Event('scroll'));return 'ok'})()")
wait(300)
lp2 = shown("langpop")
cl = take_closes()
note("S3 langpop 打开=%s 滚动后=%s 关闭堆栈=%s" % (lp1, lp2, json.dumps(cl, ensure_ascii=False)[:600]))
check("S3 langpop 随滚动关闭", lp1 and not lp2, json.dumps(cl, ensure_ascii=False)[:400])

# ===== S4: linkpop 打开 → 滚动 =====
setmd("# 大标题\n\n第一段目标文本。\n\n第二段。")
wait(600)
js("(function(){var b=document.querySelectorAll('#editor .blk')[1];"
   "var t=b.querySelector('p,div');var tn=t?t.firstChild:null;if(!tn)return 'no';"
   "var r=document.createRange();r.setStart(tn,0);r.setEnd(tn,Math.min(6,tn.textContent.length));"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(r);"
   "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
wait(400)
js('(function(){var b=document.querySelector(\'#floatbar button[title="链接"]\');'
   'if(!b)return "no-btn";b.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true}));return "ok"})()')
wait(350)
lk1 = jj("window.__linkPop()").get("show")
js("(function(){var ed=document.getElementById('editor');ed.dispatchEvent(new Event('scroll'));return 'ok'})()")
wait(300)
lk2 = jj("window.__linkPop()").get("show")
cl = take_closes()
note("S4 linkpop 打开=%s 滚动后=%s 堆栈=%s" % (lk1, lk2, json.dumps(cl, ensure_ascii=False)[:400]))
check("S4 linkpop 随滚动关闭（activePop=link 生效）", lk1 and not lk2)

# ===== S5: 非空块 '/' 不触发（设计限制） =====
setmd("已有内容的段落")
wait(500)
click_el("#editor .blk", 350)
js("(function(){var el=document.querySelector('.raw-edit');"
   "if(!el)return 'no';el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(300)
s2 = shown("slashmenu")
rr = raw_()
note("S5 非空块 / menu=%s raw=%s" % (s2, json.dumps(rr)))
check("S5 非空块键入 / 不弹菜单（设计限制确认）", s2 is False)

# ===== S6: floatbar 顶部越界 =====
MD_TEXT = "\n\n".join(["这是第 %d 段测试文本，内容足够长以便换行显示。" % i for i in range(1, 40)])
setmd(MD_TEXT)
wait(700)
r = js("(function(){var ed=document.getElementById('editor');ed.scrollTop=500;"
       "ed.dispatchEvent(new Event('scroll'));"
       "var cands=ed.querySelectorAll('.blk p');"
       "for(var i=0;i<cands.length;i++){var rc=cands[i].getBoundingClientRect();"
       "if(rc.top>0&&rc.top<40){var tn=cands[i].firstChild;if(!tn)continue;"
       "var rg=document.createRange();rg.setStart(tn,0);rg.setEnd(tn,Math.min(6,tn.textContent.length));"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));"
       "return 'sel-at-'+Math.round(rc.top)}}return 'none'})()")
wait(450)
fbt = jj("(function(){var fb=document.getElementById('floatbar');"
         "return JSON.stringify({s:fb.classList.contains('show'),"
         "top:Math.round(fb.getBoundingClientRect().top)})})()")
note("S6 选区=%s floatbar=%s" % (r, json.dumps(fbt)))
check("S6 视口顶部选区浮动栏越出上边界（问题复现）",
      fbt.get("s") is True and fbt.get("top", 0) < 0, json.dumps(fbt))

# ===== S7: 块菜单打开 + 输入字符 =====
setmd("# 标题块\n\n正文段落")
wait(500)
js("(function(){var b=document.querySelector('#editor .blk');"
   "var rc=b.getBoundingClientRect();"
   "document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:rc.left+10,clientY:rc.top+10}));"
   "return 'ok'})()")
wait(200)
js("(function(){var h=document.getElementById('blkhandle');"
   "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(350)
bm1 = jj("window.__blkMenuState()").get("show")
note("S7 块菜单打开=%s" % bm1)
if bm1:
    js("(function(){var el=document.querySelector('.raw-edit')||document.querySelector('#editor .blk');"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'x',bubbles:true,cancelable:true}));return 'ok'})()")
    wait(300)
    bm2 = jj("window.__blkMenuState()").get("show")
    rr = raw_()
    note("S7 输入x后菜单=%s raw=%s" % (bm2, json.dumps(rr[:2], ensure_ascii=False)))
    check("S7 块菜单打开时输入字符菜单滞留（问题复现）", bm2, json.dumps(rr[:2], ensure_ascii=False))
else:
    note("S7 块菜单未能通过合成事件打开，静态记录")
    check("S7 块菜单打开（探针前提）", False, "无法合成打开")

flush()
out.append("DONE")
flush()
print("\n".join(out))
