# -*- coding: utf-8 -*-
"""_m40e：抓 stylepop 在渲染态块点击下的关闭调用链（过滤 setMarkdown 噪声），
补 floatbar 顶部越界（放宽选区带）与块菜单打字滞留（mousemove 派发到块元素）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m40e.txt")
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


def patch():
    js("(function(){if(window.__patched)return 'already';"
       "var orig=DOMTokenList.prototype.remove;window.__closes=[];"
       "DOMTokenList.prototype.remove=function(tok){"
       "if(tok==='show'){var el=this._el||(this._el=null);"
       "try{window.__closes.push(String(new Error().stack||'').split('\\n').slice(2,4).join(' <- '))}"
       "catch(e){window.__closes.push('err')}}"
       "return orig.call(this,tok)};window.__patched=true;return 'ok'})()")


def closes_filtered():
    r = js("(function(){var c=(window.__closes||[]).filter(function(s){"
           "return s.indexOf('setMarkdown')===-1});window.__closes=[];"
           "return JSON.stringify(c)})()")
    try: return json.loads(r or "[]")
    except Exception: return [str(r)]


wait(2500)

# ===== E1: stylepop 打开 → 渲染态标题 mousedown → 关闭链 =====
setmd("# 大标题\n\n说明段落。\n\n```python\nprint(1)\n```")
wait(700)
patch()
closes_filtered()   # 清空 setmd 噪声
click_el("#editor .codebar .style-btn", 350, ev="click")
sp1 = shown("stylepop")
click_el("#editor .blk:nth-child(1) h1", 300)
sp2 = shown("stylepop")
cl = closes_filtered()
note("E1 stylepop 打开=%s 点标题后=%s 非setmd关闭链=%s" % (sp1, sp2, json.dumps(cl, ensure_ascii=False)[:500]))
check("E1 stylepop 点击渲染态标题后关闭（调用链）", sp1 and not sp2, json.dumps(cl, ensure_ascii=False)[:400])

# ===== E2: langpop 打开 → 渲染态标题 mousedown → 关闭链 =====
setmd("# 大标题\n\n说明段落。\n\n```python\nprint(1)\n```")
wait(700)
patch()
closes_filtered()
click_el("#editor .codebar .lang-btn", 350, ev="click")
lp1 = shown("langpop")
click_el("#editor .blk:nth-child(1) h1", 300)
lp2 = shown("langpop")
cl = closes_filtered()
note("E2 langpop 打开=%s 点标题后=%s 非setmd关闭链=%s" % (lp1, lp2, json.dumps(cl, ensure_ascii=False)[:500]))
check("E2 langpop 点击渲染态标题后关闭（调用链）", lp1 and not lp2, json.dumps(cl, ensure_ascii=False)[:400])

# ===== E3: floatbar 顶部越界（放宽） =====
MD_TEXT = "\n\n".join(["这是第 %d 段测试文本，内容足够长以便换行显示。" % i for i in range(1, 60)])
setmd(MD_TEXT)
wait(700)
r = js("(function(){var ed=document.getElementById('editor');ed.scrollTop=420;"
       "ed.dispatchEvent(new Event('scroll'));"
       "var best=null,bt=1e9;"
       "var cands=ed.querySelectorAll('.blk p');"
       "for(var i=0;i<cands.length;i++){var rc=cands[i].getBoundingClientRect();"
       "if(rc.top>4&&rc.top<bt&&rc.height>0){bt=rc.top;best=cands[i]}}"
       "if(!best)return 'none';"
       "var tn=best.firstChild;if(!tn)return 'no-tn';"
       "var rg=document.createRange();rg.setStart(tn,0);rg.setEnd(tn,Math.min(6,tn.textContent.length));"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));"
       "return 'sel-at-'+Math.round(bt)})()")
wait(450)
fbt = jj("(function(){var fb=document.getElementById('floatbar');"
         "return JSON.stringify({s:fb.classList.contains('show'),"
         "top:Math.round(fb.getBoundingClientRect().top)})})()")
note("E3 选区=%s floatbar=%s" % (r, json.dumps(fbt)))
check("E3 视口顶部选区浮动栏越出上边界（问题复现）",
      fbt.get("s") is True and fbt.get("top", 0) < 0, json.dumps(fbt))

# ===== E4: 块菜单打开 + 输入字符（mousemove 派发到块） =====
setmd("# 标题块\n\n正文段落")
wait(500)
js("(function(){var b=document.querySelector('#editor .blk');"
   "var rc=b.getBoundingClientRect();"
   "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:rc.left+10,clientY:rc.top+10}));"
   "return 'ok'})()")
wait(200)
js("(function(){var h=document.getElementById('blkhandle');"
   "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(350)
bm1 = jj("window.__blkMenuState()").get("show")
note("E4 块菜单打开=%s" % bm1)
if bm1:
    click_el("#editor .blk:nth-child(2)", 250)
    js("(function(){var el=document.querySelector('.raw-edit')||document.querySelector('#editor .blk');"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'x',bubbles:true,cancelable:true}));return 'ok'})()")
    wait(300)
    bm2 = jj("window.__blkMenuState()").get("show")
    rr = jj("window.__raw()").get("raw") or []
    note("E4 输入x后菜单=%s raw=%s" % (bm2, json.dumps(rr[:2], ensure_ascii=False)))
    check("E4 块菜单打开时输入字符菜单滞留（问题复现）", bm2, json.dumps(rr[:2], ensure_ascii=False))
else:
    check("E4 块菜单打开（探针前提）", False, "无法合成打开")

flush()
out.append("DONE")
flush()
print("\n".join(out))
