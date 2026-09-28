# -*- coding: utf-8 -*-
"""v3.29 诊断 L：引用块回车行为 + 引用内格式化 / 插入块能力盘点。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29l.txt")
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
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


def focus_quote_caret(line, col):
    """进入引用渲染态编辑，光标放到渲染文本第 line 行第 col 列（原子操作）。
    v3.29b：BR 计为一个换行（尾部空行由未转换的 <br> 承载，落在其上时
    用 setStartAfter(br) 定位）。"""
    return js("""
(function(){try{
var b=document.querySelector('#editor .blk');var q=b?b.querySelector('blockquote'):null;
if(!q)return 'noq';q.focus();
var nodes=[],full='';
(function walk(el){for(var c=el.firstChild;c;c=c.nextSibling){
if(c.nodeType===3){nodes.push({t:c,v:c.nodeValue});full+=c.nodeValue;}
else if(c.tagName==='BR'){if(c.closest('.qblk'))continue;nodes.push({br:c});full+='\\n';}
else if(c.nodeType===1)walk(c);}})(q);
var lines=full.split('\\n');var off=0;
for(var k=0;k<""" + str(line) + """&&k<lines.length;k++)off+=lines[k].length+1;
var lineLen=(lines[""" + str(line) + """]!==undefined)?lines[""" + str(line) + """].length:0;
off+=Math.min(""" + str(col) + """,lineLen);
var acc=0,pos=null;
for(var k2=0;k2<nodes.length;k2++){var n2=nodes[k2];var L=n2.t?n2.v.length:1;
if(acc+L>=off){pos={n:n2,o:off-acc};break;}acc+=L;}
if(!pos&&nodes.length){var nl=nodes[nodes.length-1];pos={n:nl,o:nl.t?nl.v.length:1};}
if(!pos)return 'notext';
var sel=getSelection();var rg=document.createRange();
if(pos.n.t)rg.setStart(pos.n.t,Math.min(pos.n.v.length,pos.o));
else if(pos.o>=1)rg.setStartAfter(pos.n.br);else rg.setStartBefore(pos.n.br);
rg.collapse(true);sel.removeAllRanges();sel.addRange(rg);
return 'off:'+off+' full:['+full+']';
}catch(e){return 'ERR:'+e.message}})()""")


def press_enter():
    return js("""
(function(){var q=document.querySelector('#editor blockquote');
if(!q)return 'noq';
var ev=new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true,cancelable:true});
q.dispatchEvent(ev);
var s=getSelection();
var bk=document.querySelector('#editor blockquote');
return 'sent|rc:'+s.rangeCount+'|an:'+(s.anchorNode?(s.anchorNode.nodeName+'@'+s.anchorOffset):'null')
 +'|inBq:'+!!(s.anchorNode&&bk&&bk.contains(s.anchorNode))})()""")


def type_text(s):
    return js("(function(){document.execCommand('insertText',false," + json.dumps(s) + ");return 'ok'})()")


def sel_quote_word(word):
    return js("""
(function(){var q=document.querySelector('#editor blockquote');if(!q)return 'noq';q.focus();
var w=document.createTreeWalker(q,NodeFilter.SHOW_TEXT,null,false);var tn,sn=null,so=0,en=null,eo=0,acc=0;
while(tn=w.nextNode()){var i=tn.nodeValue.indexOf('""" + word + """');
if(i>=0&&sn===null){sn=tn;so=i;}
if(sn!==null&&acc+tn.nodeValue.length>=so+""" + str(len(word)) + """){en=tn;eo=so+""" + str(len(word)) + """-acc+ (acc>so?acc-so:0);break;}
acc+=tn.nodeValue.length;}
if(sn===null)return 'notfound';
if(eo<=so){eo=so+""" + str(len(word)) + """;}
var sel=getSelection();var rg=document.createRange();rg.setStart(sn,so);rg.setEnd(en,eo);
sel.removeAllRanges();sel.addRange(rg);return 'sel:'+sel.toString()})()""")


wait(2500)

# ===== A. 单行引用：行尾回车应换行（不退出），空行再回车才退出 =====
js("window.setMarkdown('> 第一行内容')")
wait(700)
js("(function(){var b=document.querySelector('#editor .blk');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 1})()")
wait(300)
note("A raw", str(raw()[0]))
d = jj("(function(){var q=document.querySelector('#editor blockquote');"
       "return JSON.stringify({q:!!q,edit:q?q.getAttribute('contenteditable'):null})})()")
note("A dom", str(d))
r = focus_quote_caret(0, 5)
note("A caret", str(r))
r = press_enter()
wait(400)
r2 = raw()[0]
note("A raw after enter", str(r2))
d = jj("(function(){var q=document.querySelector('#editor blockquote');"
       "var b=document.querySelector('#editor .raw-edit');"
       "return JSON.stringify({q:!!q,edit:!!b})})()")
lns = str(r2).split('\n')
check("行尾回车 → 仍在引用内且新增一行",
      d.get("q") is True and d.get("edit") is False and len(lns) == 2
      and lns[0] == "> 第一行内容" and lns[1] == "> ", str(d) + " | " + str(r2))

# ===== B. 新行继续输入后回车 → 仍应换行不退出 =====
r = focus_quote_caret(1, 0)
type_text("第二行内容")
wait(300)
note("B raw", str(raw()[0]))
r = focus_quote_caret(1, 5)
r = press_enter()
note("B enter ret", str(r))
note("B qdbg", str(js("JSON.stringify(window.__qdbg||null)")))
wait(400)
r3 = raw()[0]
note("B raw after enter", str(r3))
check("第二行行尾回车 → 仍在引用内换行",
      str(r3) == "> 第一行内容\n> 第二行内容\n> ", str(r3))

# 诊断：B 之后选区是否存活（C 依赖 B 回车后设置的光标）
d = jj("(function(){var s=getSelection();var q=document.querySelector('#editor blockquote');"
       "return JSON.stringify({rc:s.rangeCount,"
       "an:s.anchorNode?(s.anchorNode.nodeName+'@'+s.anchorOffset):null,"
       "inq:!!(s.anchorNode&&q&&q.contains(s.anchorNode))})})()")
note("B caret", str(d))

# ===== C. 空行回车 → 退出引用（切回源码态，尾部空行剥离，前缀保留） =====
r = press_enter()
note("C enter ret", str(r))
wait(400)
r4 = raw()[0]
d = jj("(function(){return JSON.stringify({edit:!!document.querySelector('#editor .raw-edit')})})()")
note("C raw", str(r4))
check("空行回车 → 退出引用（切回源码态，尾部空行剥离）",
      d.get("edit") is True and str(r4) == "> 第一行内容\n> 第二行内容",
      str(d) + " | " + str(r4))

# ===== D. 引用内选中文本 → 浮动栏（加粗等格式化） =====
js("window.setMarkdown('> 需要加粗的文字')")
wait(700)
js("(function(){var b=document.querySelector('#editor .blk');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 1})()")
wait(300)
r = sel_quote_word("加粗")
wait(300)
note("D sel", str(r))
d = jj("(function(){var fb=document.getElementById('floatbar');"
       "return JSON.stringify({show:fb.classList.contains('show')})})()")
note("D floatbar", str(d))
check("引用内选中文本出现浮动栏", d.get("show") is True, str(d))

# ===== E. 引用内斜杠菜单（插入块入口） =====
js("window.setMarkdown('> ')")
wait(700)
js("(function(){var b=document.querySelector('#editor .blk');"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 1})()")
wait(300)
focus_quote_caret(0, 2)
type_text("表格")
wait(300)
d = jj("(function(){var sm=document.getElementById('slashmenu');"
       "return JSON.stringify({show:sm.classList.contains('show')})})()")
note("E slash", str(d))

out.append("DONE")
flush()
print("done")
