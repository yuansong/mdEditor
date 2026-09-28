# -*- coding: utf-8 -*-
"""v3.29 诊断 6：标题渲染态选中后浮动栏 高亮/加粗 是否丢标题。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29i.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


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


def sel_h(text):
    """渲染态 h 内选中指定文字"""
    return js("(function(){var h=document.querySelector('#editor h1,#editor h2,#editor h3');"
              "if(!h)return 'noh';h.focus();"
              "var walker=document.createTreeWalker(h,NodeFilter.SHOW_TEXT,null,false);"
              "var tn;var full='';var nodes=[];while(tn=walker.nextNode()){nodes.push(tn);full+=tn.nodeValue;}"
              "var i=full.indexOf('" + text + "');if(i<0)return 'notfound';"
              "var acc=0,sn=null,so=0,en=null,eo=0;"
              "for(var k=0;k<nodes.length;k++){var L=nodes[k].nodeValue.length;"
              "if(sn===null&&acc+L>i){sn=nodes[k];so=i-acc;}"
              "if(acc+L>=i+" + str(len(text)) + "){en=nodes[k];eo=i+" + str(len(text)) + "-acc;break;}acc+=L;}"
              "var sel=getSelection();var rg=document.createRange();"
              "rg.setStart(sn,so);rg.setEnd(en,eo);sel.removeAllRanges();sel.addRange(rg);"
              "return 'sel:'+sel.toString()})()")


def click_fb(title):
    return js("(function(){var fb=document.getElementById('floatbar');"
              "var b=[].filter.call(fb.querySelectorAll('button'),function(x){"
              "return x.title==='" + title + "'})[0];if(!b)return 'nobtn';"
              "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
              "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'ok'})()")


wait(2500)

MD = "# 标题测试行"
js(f"window.setMarkdown({json.dumps(MD)})")
wait(700)

# 1) 渲染态选中「标题」→ 高亮
r = sel_h("标题测试")
wait(200)
note("A sel", str(r))
d = jj("(function(){var fb=document.getElementById('floatbar');"
       "return JSON.stringify({show:fb.classList.contains('show'),"
       "btns:[].map.call(fb.querySelectorAll('button'),function(x){return x.title})})})()")
note("A floatbar", str(d))
r = click_fb("高亮")
wait(400)
note("B click 高亮", str(r))
note("B raw", str(raw()))
d = jj("(function(){return JSON.stringify({edit:!!document.querySelector('#editor .raw-edit'),"
       "h:!!document.querySelector('#editor h1')})})()")
note("B dom", str(d))
check("高亮后回到渲染态（标题仍渲染）", d.get("edit") is False and d.get("h") is True, str(d))

# 2b) 渲染态再选中并加粗（连续第二次操作）
r = sel_h("==标题测试==".replace("==", ""))
wait(200)
r = click_fb("粗体")
wait(400)
note("B2 click 粗体", str(r))
note("B2 raw", str(raw()))
d = jj("(function(){return JSON.stringify({edit:!!document.querySelector('#editor .raw-edit'),"
       "h:!!document.querySelector('#editor h1')})})()")
check("加粗后仍为渲染态标题", d.get("edit") is False and d.get("h") is True, str(d))

# 2) 提交后（点击别处触发 commit）raw 应仍带 # 前缀
js("(function(){var b=document.querySelector('#editor .blk:last-child');"
   "if(b)b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 1})()")
wait(400)
note("C raw after commit", str(raw()))
r = raw()[0]
check("高亮后标题前缀保留", r.startswith("# "), r[:80])
check("高亮标记写入", "==" in r, r[:80])

out.append("DONE")
flush()
print("done")
