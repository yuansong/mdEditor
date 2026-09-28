# -*- coding: utf-8 -*-
"""_m40b：悬浮菜单全面功能探针（v3.30.9，修正驱动方式版）。
覆盖：快速反复开关 / 滚动关闭 / 窗口缩放表现 / 输入框型弹层外点关闭 /
floatbar 顶部越界 / 表格工具栏外点与块间点击 / 块菜单打字残留 / 层叠共存 / 引用内图表。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m40.txt")
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


def raw():
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


def key_in(sel, key, ms=250):
    js("(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def esc_global(ms=250):
    js("(function(){document.activeElement&&document.activeElement.blur&&document.activeElement.blur();"
       "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));"
       "return 'ok'})()")
    wait(ms)


def doc_mousedown(ms=250):
    js("(function(){document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'ok'})()")
    wait(ms)


def ed_scroll(ms=300):
    js("(function(){var ed=document.getElementById('editor');ed.dispatchEvent(new Event('scroll'));return 'ok'})()")
    wait(ms)


def enter_edit(sel, ms=350):
    click_el(sel, ms)
    return jj("(function(){return JSON.stringify({e:!!document.querySelector('.raw-edit')})})()").get("e")


def slash_open_edited(ms=300):
    js("(function(){var el=document.querySelector('.raw-edit');"
       "if(!el)return 'no-edit';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def select_block_text(n=0, ms=400):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(n) + "];"
       "if(!b)return 'no-blk';"
       "var t=b.querySelector('p,div,h1,h2,h3')||b;"
       "var tn=t.firstChild;if(!tn)return 'no-tn';"
       "var r=document.createRange();r.setStart(tn,0);"
       "r.setEnd(tn,Math.min(8,tn.textContent.length));"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(r);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


MD_TEXT = "\n\n".join(["这是第 %d 段测试文本，内容足够长以便换行显示。" % i for i in range(1, 40)])

wait(2500)

# ============ T01/T02 快速反复开关 ============
setmd("# 标题\n\n正文段落内容")
enter_edit("#editor .blk:nth-child(2)")
slash_open_edited()
st = jj("(function(){var sm=document.getElementById('slashmenu');"
        "return JSON.stringify({s:sm.classList.contains('show'),n:sm.querySelectorAll('.si').length})})()")
check("T01 斜杠菜单打开且项齐全", st.get("s") is True and st.get("n", 0) >= 11, json.dumps(st))
esc_global()
check("T02a Esc 关闭斜杠菜单", shown("slashmenu") is False)
slash_open_edited()
check("T02b 重开正常", shown("slashmenu") is True)
esc_global()

# ============ T03 快速连开连关×6 ============
for i in range(6):
    slash_open_edited(120)
    esc_global(60)
st = jj("(function(){var sm=document.getElementById('slashmenu');"
        "return JSON.stringify({s:sm.classList.contains('show'),"
        "fb:document.getElementById('floatbar').classList.contains('show')})})()")
check("T03 快速连开连关6次后无残留", st.get("s") is False and st.get("fb") is False, json.dumps(st))

# ============ T04 滚动关闭斜杠菜单（v3.29d C2 回归） ============
slash_open_edited()
ok_open = shown("slashmenu")
ed_scroll()
check("T04 斜杠菜单随编辑区滚动关闭", ok_open and shown("slashmenu") is False)

# ============ T05 网格面板滚动关闭 ============
enter_edit("#editor .blk:nth-child(2)")
slash_open_edited()
r = js("window.__slashPick('table', null)"); wait(400)
g_open = shown("tblsize")
ed_scroll()
check("T05 网格面板随滚动关闭", g_open and shown("tblsize") is False, "pick=" + str(r))

# ============ T06 窗口缩放：浮层滞留 ============
slash_open_edited()
before = jj("(function(){var sm=document.getElementById('slashmenu');"
            "return JSON.stringify({t:sm.style.top,l:sm.style.left})})()")
js("(function(){window.dispatchEvent(new Event('resize'));return 'ok'})()")
wait(300)
after = jj("(function(){var sm=document.getElementById('slashmenu');"
           "return JSON.stringify({t:sm.style.top,l:sm.style.left,s:sm.classList.contains('show')})})()")
note("T06 before=" + json.dumps(before) + " after=" + json.dumps(after))
check("T06 resize 后浮层原位滞留（无重定位/关闭处理，问题复现）",
      after.get("s") is True and before.get("t") == after.get("t"))
esc_global()

# ============ T07 stylepop：外点不关闭 ============
setmd("说明段落。\n\n```python\nprint(1)\n```")
wait(600)
click_el("#editor .codebar .style-btn", 350, ev="click")
sp_open = shown("stylepop")
click_el("#editor .blk:nth-child(1)", 300)
sp_after = shown("stylepop")
note("T07 stylepop 打开=%s 点击段落(编辑态)后=%s" % (sp_open, sp_after))
check("T07a stylepop 点击其它块后仍显示（问题复现）", sp_open and sp_after)
esc_global()
check("T07b Esc 可关闭 stylepop", shown("stylepop") is False)

# ============ T08 langpop：外点不关闭 / Esc 焦点回代码区 ============
setmd("说明段落。\n\n```python\nprint(1)\n```")
wait(600)
click_el("#editor .codebar .lang-btn", 350, ev="click")
lp_open = shown("langpop")
click_el("#editor .blk:nth-child(1)", 300)
lp_after = shown("langpop")
note("T08 langpop 打开=%s 点击段落后=%s" % (lp_open, lp_after))
check("T08a langpop 点击其它块后仍显示（问题复现）", lp_open and lp_after)
esc_global()
d = jj("(function(){var c=document.querySelector('#editor .codeblock code');"
       "return JSON.stringify({lp:!document.getElementById('langpop').classList.contains('show'),"
       "f:document.activeElement===c})})()")
check("T08b Esc 关闭 langpop 且焦点回代码区", d.get("lp") is True and d.get("f") is True, json.dumps(d))

# ============ T09 linkpop：外点不关闭 ============
setmd("第一段目标文本内容。\n\n第二段对照文本内容。")
wait(500)
select_block_text(0)
fb = jj("(function(){var fb=document.getElementById('floatbar');"
        "return JSON.stringify({s:fb.classList.contains('show'),n:fb.querySelectorAll('button').length})})()")
js('(function(){var b=document.querySelector(\'#floatbar button[title="链接"]\');'
   'if(!b)return "no-btn";b.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true}));return "ok"})()')
wait(350)
lk1 = jj("window.__linkPop()").get("show")
click_el("#editor .blk:nth-child(2)", 300)
lk2 = jj("window.__linkPop()").get("show")
note("T09 fb=%s linkpop 打开=%s 点击块后=%s" % (json.dumps(fb), lk1, lk2))
check("T09a linkpop 点击其它块后仍显示（问题复现）", lk1 and lk2)
esc_global()
check("T09b Esc 关闭 linkpop", jj("window.__linkPop()").get("show") is False)

# ============ T10 cappop：中性目标外点不关闭 ============
setmd("```mermaid\nflowchart TD\n  A --> B\n```\n\n说明文字段落。")
wait(900)
js("window.__mmdHooks.cap(0)"); wait(350)
cp1 = shown("cappop")
click_el("#editor .blk:nth-child(2)", 300)
cp2 = shown("cappop")
note("T10 cappop 打开=%s 点击段落后=%s" % (cp1, cp2))
check("T10a cappop 点击普通块后仍显示（问题复现）", cp1 and cp2)
esc_global()
check("T10b Esc 关闭 cappop", shown("cappop") is False)

# ============ T11 floatbar 顶部越界 ============
setmd(MD_TEXT)
wait(600)
js("(function(){var ed=document.getElementById('editor');ed.scrollTop=600;"
   "ed.dispatchEvent(new Event('scroll'));return 'ok'})()")
wait(300)
r = js("(function(){var ed=document.getElementById('editor');"
       "var cands=ed.querySelectorAll('.blk p, .blk h1, .blk h2');"
       "for(var i=0;i<cands.length;i++){var rc=cands[i].getBoundingClientRect();"
       "if(rc.top>0&&rc.top<40&&rc.height>0&&rc.bottom>rc.top){"
       "var tn=cands[i].childNodes.length?cands[i].firstChild:null;"
       "if(!tn)continue;var rg=document.createRange();"
       "rg.setStart(tn,0);rg.setEnd(tn,Math.min(6,tn.textContent.length));"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));"
       "return 'sel-at-'+Math.round(rc.top)}}return 'none'})()")
wait(450)
fbt = jj("(function(){var fb=document.getElementById('floatbar');"
         "return JSON.stringify({s:fb.classList.contains('show'),"
         "top:Math.round(fb.getBoundingClientRect().top)})})()")
note("T11 选区=%s floatbar=%s" % (r, json.dumps(fbt)))
check("T11 视口顶部选区浮动栏越出上边界（top<0，问题复现）",
      fbt.get("s") is True and isinstance(fbt.get("top"), (int, float)) and fbt.get("top") < 0,
      json.dumps(fbt))

# ============ T12 表格工具栏：块间点击滞留 + Esc ============
setmd("| A | B |\n| --- | --- |\n| 1 | 2 |\n\n表格后的普通段落。")
wait(600)
js("(function(){var td=document.querySelector('#editor .blk table td');if(!td)return 'no-td';"
   "var rc=td.getBoundingClientRect();"
   "td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
   "clientX:rc.left+5,clientY:rc.top+5}));return 'ok'})()")
wait(350)
tb1 = shown("tblbar")
click_el("#editor .blk:nth-child(2)", 300)
tb2 = shown("tblbar")
note("T12 tblbar 打开=%s 点击其它块后=%s" % (tb1, tb2))
check("T12a 表格工具栏点击其它块后仍显示（问题复现）", tb1 and tb2)
doc_mousedown()
tb3 = shown("tblbar")
note("T12 doc_mousedown 后 tblbar=%s" % tb3)
esc_global()
check("T12b Esc 关闭表格工具栏", shown("tblbar") is False)

# ============ T13 块菜单打开 + 普通字符输入 ============
setmd("# 标题块\n\n正文段落")
wait(500)
js("(function(){var b=document.querySelector('#editor .blk:nth-child(1)');"
   "document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:b.getBoundingClientRect().left+10,"
   "clientY:b.getBoundingClientRect().top+10}));return 'ok'})()")
wait(200)
js("(function(){var h=document.getElementById('blkhandle');"
   "if(h.style.display!=='flex')h.style.display='flex';"
   "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(350)
bm1 = jj("window.__blkMenuState()").get("show")
enter_edit("#editor .blk:nth-child(2)", 250)
key_in(".raw-edit", 'x', 300)
bm2 = jj("window.__blkMenuState()").get("show")
rr = raw()
note("T13 块菜单打开=%s 输入x后=%s raw0=%s" % (bm1, bm2, json.dumps(rr[:2], ensure_ascii=False)))
check("T13 块菜单打开时输入字符菜单滞留（问题复现）", bm1 and bm2)
esc_global()

# ============ T14 浮动栏与斜杠菜单共存（B14 设计） ============
setmd("第一段用于选择文本。\n\n第二段。")
wait(500)
select_block_text(1)
fb1 = shown("floatbar")
click_el("#editor .blk:nth-child(2)", 200)
slash_open_edited()
sm1 = shown("slashmenu")
fb2 = shown("floatbar")
note("T14 fb选区后=%s slash后={sm:%s,fb:%s}" % (fb1, sm1, fb2))
check("T14 格式栏与斜杠菜单共存（B14）", sm1 is True and fb2 is True)
esc_global()

# ============ T15 引用内插图表（MMD-8 实测） ============
setmd("> 引用行")
wait(500)
click_el("#editor blockquote")
key_in("#editor blockquote", '/')
r = js("window.__slashPick('chart', 0)")
wait(1200)
mmd = jj("(function(){var q=document.querySelector('#editor blockquote');"
         "var m=q?q.querySelector('.mermaidblock'):null;"
         "return JSON.stringify({has:!!m,svg:m?!!m.querySelector('svg'):false})})()")
note("T15 pick=%s 引用内图表=%s" % (r, json.dumps(mmd)))
check("T15 引用内插图表可渲染出 SVG", mmd.get("has") is True and mmd.get("svg") is True, json.dumps(mmd))

# ============ T16 z-index 层叠 ============
z = jj("(function(){var ids=['floatbar','objbar','slashmenu','blkmenu','submenu','tblbar',"
       "'tblsize','langpop','stylepop','renpop','linkpop','cappop','emojipop'];"
       "var o={};ids.forEach(function(i){var el=document.getElementById(i);"
       "o[i]=el?getComputedStyle(el).zIndex:'missing'});return JSON.stringify(o)})()")
zj = z if isinstance(z, dict) else json.loads(z)
note("T16 z-index=" + json.dumps(zj, ensure_ascii=False))
check("T16 全部浮层 z-index 一致（9999，层叠靠 DOM 顺序）",
      all(str(v) == "9999" for v in zj.values() if v != "missing"),
      json.dumps(zj, ensure_ascii=False))

flush()
out.append("DONE")
flush()
print("\n".join(out))
