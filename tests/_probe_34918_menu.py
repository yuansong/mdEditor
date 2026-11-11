# -*- coding: utf-8 -*-
"""v3.49.18 交付自测：① 悬浮格式化栏恢复（展示 + 功能）② 文本块右键菜单
只保留复制 / 块转换，四项块操作移除 ③ 表格右键「拷贝整个表格」
④ 键盘 Delete 删块现状实测。结果 tests/_probe_34918_menu.txt"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MDEDITOR_SKIP_DRAFT", "1")
os.environ.setdefault("MDEDITOR_SINGLETON_KEY", "probe34918menu")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_probe_34918_menu.txt")
out = []


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code, timeout=25000):
    lp = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        lp.quit()
    QTimer.singleShot(timeout, lp.quit)
    win._js_active(code, cb)
    lp.exec()
    return box["r"]


def wait(ms):
    lp = QEventLoop()
    QTimer.singleShot(ms, lp.quit)
    lp.exec()


wait(3000)
MD = ("# 标题一\n\n这是第一段文字AAA。\n\n第二段文字BBB。\n\n"
      "- 列表甲\n- 列表乙\n\n> 引用文字\n\n结尾段落CCC。")
TBL = ("| 甲 | 乙 |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |")
MDT = "表格前的段落。\n\n" + TBL + "\n\n表格后的段落。"


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(ms)


js("""(function(){window.__errs=[];
window.addEventListener('error',function(e){window.__errs.push(String(e.message||e));});return 'ok';})()""")

log("===== A：悬浮格式化栏恢复（选中文字 → FB show + 定位 + 完整按钮集） =====")
setmd(MD)
log(js("""(function(){
var p=document.querySelector('#editor .blk.b-p p');
var tn=p.firstChild;var r=document.createRange();r.setStart(tn,0);r.setEnd(tn,4);
var s=getSelection();s.removeAllRanges();s.addRange(r);
return JSON.stringify({sel:s.toString()});})()"""))
wait(400)   # selectionchange 160ms 防抖
log(js("""(function(){
var FB=document.getElementById('floatbar');
return JSON.stringify({show:FB.classList.contains('show'),
 computed:getComputedStyle(FB).display,left:FB.style.left,top:FB.style.top,
 btns:[].map.call(FB.querySelectorAll('button'),function(b){return b.title;}),
 cnt:(FB.querySelector('.fbcnt')||{}).textContent||''});})()"""))

log("===== B：悬浮栏功能完整还原（点击「粗体」→ Markdown 出现 **） =====")
log(js("""(function(){
var FB=document.getElementById('floatbar');
var b=FB.querySelector('button[title="粗体"]');
if(!b)return JSON.stringify({err:'no bold button'});
b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
return JSON.stringify({clicked:true});})()"""))
wait(600)
log(js("""(function(){return JSON.stringify({md:window.getMarkdown().slice(0,90),
 hasBold:window.getMarkdown().indexOf('**')>=0});})()"""))

log("===== C：块手柄仍停用（Q1：只恢复 FB，不恢复 ⠿ 菜单） =====")
log(js("""(function(){var BH=document.getElementById('blkhandle');
return JSON.stringify({inline:BH.style.display,computed:getComputedStyle(BH).display});})()"""))

log("===== D：有选区右键 → 只保留复制 + 行内格式 + 块转换，无四项块操作 =====")
setmd(MD)
log(js("""(function(){
var p=document.querySelector('#editor .blk.b-p p');
var tn=p.firstChild;var r=document.createRange();r.setStart(tn,0);r.setEnd(tn,6);
var s=getSelection();s.removeAllRanges();s.addRange(r);
var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:300,clientY:220});
p.dispatchEvent(ev);
var bm=document.getElementById('blkmenu');
var acts=[].map.call(bm.querySelectorAll('.mi'),function(m){return m.getAttribute('data-act');});
return JSON.stringify({prevented:ev.defaultPrevented,shown:bm.classList.contains('show'),
 acts:acts,forbidden:acts.filter(function(a){return ['dup','up','down','del','fx:delblk'].indexOf(a)>=0;}),
 hasCopy:acts.indexOf('ctxcopy')>=0,hasFxBold:acts.indexOf('fx:bold')>=0,
 cap:[].map.call(bm.querySelectorAll('.cap'),function(c){return c.textContent;})});})()"""))

log("===== E：无选区右键 → 仅块转换（无四项块操作） =====")
setmd(MD)
log(js("""(function(){
var p=document.querySelector('#editor .blk.b-p p');
var tn=p.firstChild;var r=document.createRange();r.setStart(tn,2);r.collapse(true);
var s=getSelection();s.removeAllRanges();s.addRange(r);
var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:300,clientY:220});
p.dispatchEvent(ev);
var bm=document.getElementById('blkmenu');
var acts=[].map.call(bm.querySelectorAll('.mi'),function(m){return m.getAttribute('data-act');});
return JSON.stringify({prevented:ev.defaultPrevented,shown:bm.classList.contains('show'),acts:acts,
 forbidden:acts.filter(function(a){return ['dup','up','down','del','fx:delblk'].indexOf(a)>=0;}),
 hasCopy:acts.indexOf('ctxcopy')>=0});})()"""))

log("===== F：块转换能力未受影响（右键「转为引用」生效） =====")
log(js("""(function(){
var bm=document.getElementById('blkmenu');var mi=bm.querySelector('.mi[data-act="to:quote"]');
if(!mi)return JSON.stringify({err:'no to:quote'});
mi.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
return JSON.stringify({clicked:true});})()"""))
wait(600)
log(js("""(function(){var md=window.getMarkdown();
return JSON.stringify({hasQuote:md.indexOf('> ')>=0,head:md.slice(0,110)});})()"""))

log("===== G：表格右键菜单新增「拷贝整个表格」（菜单结构 + 其余项不变） =====")
setmd(MDT)
log(js("""(function(){
var td=document.querySelector('#editor .b-table td');
if(!td)return JSON.stringify({err:'no td'});
var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:300,clientY:260});
td.dispatchEvent(ev);
var TB=document.getElementById('tblbar');
return JSON.stringify({prevented:ev.defaultPrevented,shown:TB.classList.contains('show'),
 items:[].map.call(TB.querySelectorAll('.tmi'),function(b){return b.title;}),
 tblSel:window.__tblSel(),raw:window.__raw().slice(0,300)});})()"""))

log("===== H：点击「拷贝整个表格」→ 剪贴板拿到整表 Markdown 源码 =====")
log(js("""(function(){
window.__capCopy=null;window.__ecOrig=document.execCommand;
document.execCommand=function(c){
  if(c==='copy'){var ae=document.activeElement;
    window.__capCopy=(ae&&ae.tagName==='TEXTAREA')?ae.value:'';return true;}
  return window.__ecOrig.apply(document,arguments);};
var TB=document.getElementById('tblbar');var hit=null;
[].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title==='拷贝整个表格')hit=b;});
if(!hit){document.execCommand=window.__ecOrig;return JSON.stringify({err:'no copyall item'});}
hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
var cap=window.__capCopy;document.execCommand=window.__ecOrig;
var raw=JSON.parse(window.__raw()).raw;
return JSON.stringify({copied:cap,eqRaw:raw.indexOf(cap)>=0&&cap.length>0,
 rawTable:raw.filter(function(x){return x.indexOf('| 甲')>=0;})});})()"""))

log("===== I：「拷贝内容」原行为不变（只拷选中单元格 TAB 文本） =====")
log(js("""(function(){
window.__capCopy=null;window.__ecOrig=document.execCommand;
document.execCommand=function(c){
  if(c==='copy'){var ae=document.activeElement;
    window.__capCopy=(ae&&ae.tagName==='TEXTAREA')?ae.value:'';return true;}
  return window.__ecOrig.apply(document,arguments);};
var td=document.querySelector('#editor .b-table td');
td.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:300,clientY:260}));
var TB=document.getElementById('tblbar');var hit=null;
[].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title==='拷贝内容')hit=b;});
if(!hit){document.execCommand=window.__ecOrig;return JSON.stringify({err:'no copy item'});}
hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
var cap=window.__capCopy;document.execCommand=window.__ecOrig;
return JSON.stringify({copied:cap,hasPipe:cap.indexOf('|')>=0});})()"""))

log("===== J：HTML 表格同样可拷整表源码（copyall 置于 htable 分派之前） =====")
HTBL = "<table><tr><th>甲</th><th>乙</th></tr><tr><td>1</td><td>2</td></tr></table>"
setmd("HTML表前。\n\n" + HTBL + "\n\nHTML表后。")
log(js("""(function(){
var td=document.querySelector('#editor .b-table td, #editor table td');
if(!td)return JSON.stringify({err:'no htable td',raw:window.__raw().slice(0,200)});
window.__capCopy=null;window.__ecOrig=document.execCommand;
document.execCommand=function(c){
  if(c==='copy'){var ae=document.activeElement;
    window.__capCopy=(ae&&ae.tagName==='TEXTAREA')?ae.value:'';return true;}
  return window.__ecOrig.apply(document,arguments);};
var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:300,clientY:260});
td.dispatchEvent(ev);
var TB=document.getElementById('tblbar');var hit=null;
[].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title==='拷贝整个表格')hit=b;});
if(hit)hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
var cap=window.__capCopy;document.execCommand=window.__ecOrig;
var raw=JSON.parse(window.__raw()).raw;
return JSON.stringify({menuItem:!!hit,copied:cap,
 eqRaw:!!cap&&raw.some(function(x){return x===cap;})});})()"""))

log("===== K：键盘 Delete 删块现状实测（诊断，不改断言） =====")
# K1 整块文字选中 + Delete
setmd(MD)
log("K1 整块文字选中 + Delete:")
log(js("""(function(){
var before=JSON.parse(window.__raw()).raw.slice();
var p=document.querySelector('#editor .blk.b-p p');
var tn=p.firstChild;var r=document.createRange();r.setStart(tn,0);r.setEnd(tn,tn.length);
var s=getSelection();s.removeAllRanges();s.addRange(r);
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);
var after=JSON.parse(window.__raw()).raw.slice();
return JSON.stringify({prevented:ev.defaultPrevented,before:before,after:after,
 removed:before.length-after.length});})()"""))
wait(300)
log(js("""(function(){return JSON.stringify({raw:JSON.parse(window.__raw()).raw.slice(0,4)});})()"""))

# K2 图片对象选中 + Delete
IMG = "图片前段落。\n\n![示例](x.png)\n\n图片后段落。"
setmd(IMG)
log("K2 图片对象选中 + Delete:")
log(js("""(function(){
var before=JSON.parse(window.__raw()).raw.slice();
window.__objPick('img',1);
var sel=window.__objSel();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);
var after=JSON.parse(window.__raw()).raw.slice();
return JSON.stringify({objSel:sel,prevented:ev.defaultPrevented,
 active:document.activeElement&&document.activeElement.tagName,
 activeCE:!!(document.activeElement&&document.activeElement.isContentEditable),
 removed:before.length-after.length,before:before,after:after});})()"""))

# K3 分割线选中 + Delete
setmd("# 标题\n\n---\n\n结尾段。")
log("K3 分割线选中 + Delete:")
log(js("""(function(){
var hr=document.querySelector('#editor .blk hr');
if(!hr)return JSON.stringify({err:'no hr'});
hr.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,button:0,clientX:200,clientY:150}));
hr.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,button:0,clientX:200,clientY:150}));
var sel=hr.classList.contains('hrsel');
var before=JSON.parse(window.__raw()).raw.slice();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);
var after=JSON.parse(window.__raw()).raw.slice();
return JSON.stringify({hrSelected:sel,prevented:ev.defaultPrevented,
 removed:before.length-after.length,before:before,after:after});})()"""))

# K4 表格块对象选中 + Delete
setmd(MDT)
log("K4 表格对象选中 + Delete:")
log(js("""(function(){
window.__rzPick(1);
var sel=window.__objSel();
var before=JSON.parse(window.__raw()).raw.slice();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);
var after=JSON.parse(window.__raw()).raw.slice();
return JSON.stringify({objSel:sel,prevented:ev.defaultPrevented,
 removed:before.length-after.length,before:before,after:after});})()"""))

log("K5 表格单元格内编辑 + Backspace 不得误删整表（守卫）:")
setmd(MDT)
log(js("""(function(){
window.__rzPick(1);
var td=document.querySelector('#editor .b-table td');
var tn=td.firstChild;var r=document.createRange();
r.setStart(tn,Math.min(1,tn.length));r.collapse(true);
var s=getSelection();s.removeAllRanges();s.addRange(r);
var before=JSON.parse(window.__raw()).raw.slice();
var ev=new KeyboardEvent('keydown',{key:'Backspace',bubbles:true,cancelable:true});
document.dispatchEvent(ev);
var after=JSON.parse(window.__raw()).raw.slice();
return JSON.stringify({objSel:window.__objSel(),prevented:ev.defaultPrevented,
 removed:before.length-after.length,lenBefore:before.length,lenAfter:after.length});})()"""))

log("===== L：专属右键菜单未受影响（分割线仍有删除等块操作） =====")
setmd("# 标题\n\n---\n\n结尾段。")
log(js("""(function(){
var hr=document.querySelector('#editor .blk hr');
var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:260,clientY:200});
hr.dispatchEvent(ev);
var bm=document.getElementById('blkmenu');
return JSON.stringify({prevented:ev.defaultPrevented,shown:bm.classList.contains('show'),
 acts:[].map.call(bm.querySelectorAll('.mi'),function(m){return m.getAttribute('data-act');}).slice(0,12)});})()"""))

log("===== M：源码 / 预览模式回归 + JS 错误 + 最终往返 =====")
setmd(MD)
log(js("""(function(){window.setSourceMode(true);var ED=document.getElementById('editor');
return JSON.stringify({host:window.__oneHostActive(),edCE:ED.getAttribute('contenteditable'),
 srcWrap:!!document.querySelector('.src-wrap')});})()"""))
wait(300)
log(js("""(function(){window.setSourceMode(false);var ED=document.getElementById('editor');
return JSON.stringify({host:window.__oneHostActive(),edCE:ED.getAttribute('contenteditable'),
 n:ED.children.length,mdEq:window.getMarkdown()===%s});})()""" % json.dumps(MD, ensure_ascii=False)))
wait(400)
log(js("""(function(){window.setPreviewMode(true);window.setPreviewContent(%s);
var ED=document.getElementById('editor');
return JSON.stringify({host:window.__oneHostActive(),edCE:ED.getAttribute('contenteditable'),
 innerCE:ED.querySelectorAll('[contenteditable]').length});})()""" % json.dumps(MD, ensure_ascii=False)))
wait(400)
log(js("""(function(){window.setPreviewMode(false);
return JSON.stringify({host:window.__oneHostActive(),
 errs:(window.__errs||[]).slice(0,8),errN:(window.__errs||[]).length,
 mdEq:window.getMarkdown()===%s});})()""" % json.dumps(MD, ensure_ascii=False)))

log("DONE")
print("DONE")
