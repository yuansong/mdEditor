# -*- coding: utf-8 -*-
"""_m40c：甄别输入框型弹层（stylepop/langpop/linkpop/cappop）在
「渲染态块点击」与「滚动」两条不走 hidePops 的路径下是否滞留；
并用空块修正斜杠菜单驱动，验证 '/' 仅空块触发的设计限制。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m40c.txt")
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


def esc_global(ms=250):
    js("(function(){document.activeElement&&document.activeElement.blur&&document.activeElement.blur();"
       "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));"
       "return 'ok'})()")
    wait(ms)


def ed_scroll_top(px, ms=300):
    js("(function(){var ed=document.getElementById('editor');ed.scrollTop=" + str(px) + ";"
       "ed.dispatchEvent(new Event('scroll'));return 'ok'})()")
    wait(ms)


wait(2500)

# ===== 斜杠菜单：空块驱动修正版 =====
setmd("")
wait(400)
click_el("#editor .blk", 350)
e1 = jj("(function(){return JSON.stringify({e:!!document.querySelector('.raw-edit')})})()")
js("(function(){var el=document.querySelector('.raw-edit');"
   "if(!el)return 'no-edit';"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'ok'})()")
wait(350)
s1 = jj("(function(){var sm=document.getElementById('slashmenu');"
        "return JSON.stringify({s:sm.classList.contains('show'),n:sm.querySelectorAll('.si').length,"
        "e:!!document.querySelector('.raw-edit')})})()")
note("D0 enterEdit=" + json.dumps(e1) + " slash=" + json.dumps(s1))
check("D0 空块键入 / 打开斜杠菜单", s1.get("s") is True and s1.get("n", 0) >= 11, json.dumps(s1))

# 网格面板滚动关闭（空块版）
js("window.__slashPick('table', null)"); wait(400)
g1 = shown("tblsize")
ed_scroll_top(0)
check("D0b 网格面板随滚动关闭", g1 and shown("tblsize") is False)
esc_global()

# 斜杠菜单滚动关闭（空块版）
js("(function(){var el=document.querySelector('.raw-edit')||document.querySelector('#editor .blk');"
   "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'ok'})()")
wait(300)
o1 = shown("slashmenu")
ed_scroll_top(0)
check("D0c 斜杠菜单随滚动关闭", o1 and shown("slashmenu") is False)
esc_global()

# ===== stylepop：渲染态标题点击 / 滚动 =====
setmd("# 大标题\n\n说明段落。\n\n```python\nprint(1)\n```")
wait(700)
click_el("#editor .codebar .style-btn", 350, ev="click")
sp1 = shown("stylepop")
click_el("#editor .blk:nth-child(1) h1", 300)
sp2 = shown("stylepop")
note("D1 stylepop 打开=%s 点标题(渲染态)后=%s" % (sp1, sp2))
check("D1a stylepop 点击渲染态标题后仍显示（问题复现）", sp1 and sp2)
ed_scroll_top(30)
sp3 = shown("stylepop")
note("D1b stylepop 滚动后=%s" % sp3)
check("D1b stylepop 滚动后仍显示（问题复现，activePop 未置位）", sp3)
esc_global()

# ===== langpop：渲染态标题点击 / 滚动 =====
setmd("# 大标题\n\n说明段落。\n\n```python\nprint(1)\n```")
wait(700)
click_el("#editor .codebar .lang-btn", 350, ev="click")
lp1 = shown("langpop")
click_el("#editor .blk:nth-child(1) h1", 300)
lp2 = shown("langpop")
note("D2 langpop 打开=%s 点标题后=%s" % (lp1, lp2))
check("D2a langpop 点击渲染态标题后仍显示（问题复现）", lp1 and lp2)
ed_scroll_top(30)
lp3 = shown("langpop")
note("D2b langpop 滚动后=%s" % lp3)
check("D2b langpop 滚动后仍显示（问题复现）", lp3)
esc_global()

# ===== linkpop：渲染态标题点击 / 滚动 =====
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
click_el("#editor .blk:nth-child(1) h1", 300)
lk2 = jj("window.__linkPop()").get("show")
note("D3 linkpop 打开=%s 点标题后=%s" % (lk1, lk2))
check("D3a linkpop 点击渲染态标题后仍显示（问题复现）", lk1 and lk2)
ed_scroll_top(30)
lk3 = jj("window.__linkPop()").get("show")
note("D3b linkpop 滚动后=%s（activePop=link 应被关闭）" % lk3)
check("D3b linkpop 随滚动关闭", lk1 and not lk3)
esc_global()

# ===== cappop：渲染态标题点击 / 滚动 =====
setmd("# 大标题\n\n```mermaid\nflowchart TD\n  A --> B\n```")
wait(1000)
js("window.__mmdHooks.cap(0)"); wait(350)
cp1 = shown("cappop")
click_el("#editor .blk:nth-child(1) h1", 300)
cp2 = shown("cappop")
note("D4 cappop 打开=%s 点标题后=%s" % (cp1, cp2))
check("D4a cappop 点击渲染态标题后仍显示（问题复现）", cp1 and cp2)
ed_scroll_top(30)
cp3 = shown("cappop")
note("D4b cappop 滚动后=%s" % cp3)
check("D4b cappop 随滚动关闭", cp1 and not cp3)
esc_global()

# ===== '/' 非空块不触发（设计限制确认） =====
setmd("已有内容的段落")
wait(500)
click_el("#editor .blk", 350)
js("(function(){var el=document.querySelector('.raw-edit');"
   "if(!el)return 'no';el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(300)
s2 = shown("slashmenu")
rr = raw()
note("D5 非空块按 / menu=%s raw=%s" % (s2, json.dumps(rr)))
check("D5 非空块键入 / 不弹菜单（设计限制确认）", s2 is False)

# ===== floatbar 顶部越界（多段落 + 滚动 + 顶部选区） =====
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
note("D6 选区=%s floatbar=%s" % (r, json.dumps(fbt)))
check("D6 视口顶部选区浮动栏越出上边界（问题复现）",
      fbt.get("s") is True and fbt.get("top", 0) < 0, json.dumps(fbt))

# ===== 块菜单打开 + 输入字符滞留 =====
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
note("D7 块菜单打开=%s" % bm1)
if bm1:
    js("(function(){var el=document.querySelector('.raw-edit');"
       "if(!el){el=document.querySelector('#editor .blk');}"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'x',bubbles:true,cancelable:true}));return 'ok'})()")
    wait(300)
    bm2 = jj("window.__blkMenuState()").get("show")
    rr = raw()
    note("D7 输入x后菜单=%s raw=%s" % (bm2, json.dumps(rr[:2], ensure_ascii=False)))
    check("D7 块菜单打开时输入字符菜单滞留（问题复现）", bm2)
else:
    note("D7 块菜单未能通过合成事件打开（handleIdx 依赖真实 mousemove 命中），静态记录")
esc_global()

flush()
out.append("DONE")
flush()
print("\n".join(out))
