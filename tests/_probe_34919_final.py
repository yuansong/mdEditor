# -*- coding: utf-8 -*-
"""v3.49.19 交付自测（发布门禁）。

① CTX-FMT-STRIP：选中文本右键不再出现行内格式项，只保留复制 + 结构转换；
   未选中与其他区域菜单原样；保留项仍可触发；悬浮栏承接格式能力。
② TBL-COPYTABLE：整表拷贝位于「拷贝内容」之后且使用专属网格图标；
   ③ 整表选中 Delete / 拷贝 / 删除边界：未选中、空白表格、首尾、唯一块、
   单元格内编辑、先拷贝再删除、前后内容不受影响。
结果 tests/_probe_34919_final.txt；有 FAIL 时退出码 1。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MDEDITOR_SKIP_DRAFT", "1")
os.environ.setdefault("MDEDITOR_SINGLETON_KEY", "probe34919final")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_probe_34919_final.txt")
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


PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    log("%s %s | %s" % ("PASS" if cond else "FAIL", name, str(detail)[:430]))


def jval(code):
    r = js(code)
    try:
        return json.loads(r)
    except Exception:
        return {"_bad": str(r)[:400]}


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(ms)


def brief(v):
    log(json.dumps(v, ensure_ascii=False)[:900])


wait(3000)
MD = ("# 标题一\n\n这是第一段文字AAA。\n\n第二段文字BBB。\n\n"
      "- 列表甲\n- 列表乙\n\n> 引用文字\n\n结尾段落CCC。")
TBL = "| 甲 | 乙 |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
MDT = "表格前的段落。\n\n" + TBL + "\n\n表格后的段落。"
EMPTY_TBL = "|  |  |\n| --- | --- |\n|  |  |"
HTBL = "<table><tr><th>甲</th><th>乙</th></tr><tr><td>1</td><td>2</td></tr></table>"

log("===== 注入测试辅助 =====")
log(js("""(function(){
window.__t19={
 raw:function(){return JSON.parse(window.__raw()).raw.slice();},
 sel:function(n,tag){
   var el=document.querySelector('#editor .blk.b-'+(tag||'p')+' '+(tag||'p'));
   if(!el||!el.firstChild)return false;
   var tn=el.firstChild,r=document.createRange();
   r.setStart(tn,0);r.setEnd(tn,Math.min(n,tn.length));
   var s=getSelection();s.removeAllRanges();s.addRange(r);return true;
 },
 collapse:function(tag){
   var el=document.querySelector('#editor .blk.b-'+(tag||'p')+' '+(tag||'p'));
   if(!el||!el.firstChild)return false;
   var tn=el.firstChild,r=document.createRange();
   r.setStart(tn,Math.min(2,tn.length));r.collapse(true);
   var s=getSelection();s.removeAllRanges();s.addRange(r);return true;
 },
 ctx:function(el){
   var ev=new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:300,clientY:220});
   el.dispatchEvent(ev);return ev.defaultPrevented;
 },
 acts:function(){
   var bm=document.getElementById('blkmenu');
   return [].map.call(bm.querySelectorAll('.mi'),function(m){return m.getAttribute('data-act');});
 },
 tbTitles:function(){
   var TB=document.getElementById('tblbar');
   return [].map.call(TB.querySelectorAll('.tmi'),function(b){return b.title;});
 },
 tbIcon:function(title){
   var TB=document.getElementById('tblbar'),hit=null;
   [].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title===title)hit=b;});
   var sv=hit&&hit.querySelector('svg');return sv?sv.outerHTML:null;
 },
 grab:function(fn){
   window.__cap19=null;var orig=document.execCommand;
   document.execCommand=function(c){
     if(c==='copy'){var ae=document.activeElement;
       window.__cap19=(ae&&ae.tagName==='TEXTAREA')?ae.value:'';return true;}
     return orig.apply(document,arguments);};
   try{fn();}finally{document.execCommand=orig;}
   return window.__cap19;
 }
};
window.__errs=[];
window.addEventListener('error',function(e){window.__errs.push(String(e.message||e));});
return 'helper-ok';})()"""))

# ---------------------------------------------------------------- T0
log("")
log("===== T0 边界：未选中表格 + Delete 不删任何块 =====")
setmd(MDT)
v = jval("""(function(){
var obj=window.__objSel();var before=window.__t19.raw();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);var after=window.__t19.raw();
return JSON.stringify({obj:obj,prevented:ev.defaultPrevented,before:before,after:after,
 same:JSON.stringify(before)===JSON.stringify(after)});})()""")
brief(v)
check("T0 未选中表格 Delete 不删块", v.get("obj") is None and v.get("prevented") is False
      and v.get("same") is True, {"obj": v.get("obj"), "prevented": v.get("prevented"), "same": v.get("same")})

# ---------------------------------------------------------------- A
log("")
log("===== A 选中文本右键：无行内格式项，仅复制 + 结构项 =====")
setmd(MD)
v = jval("""(function(){
var ok=window.__t19.sel(6,'p');
var p=document.querySelector('#editor .blk.b-p p');
var prevented=window.__t19.ctx(p);var bm=document.getElementById('blkmenu');
return JSON.stringify({selOk:ok,prevented:prevented,shown:bm.classList.contains('show'),
 acts:window.__t19.acts(),
 texts:[].map.call(bm.querySelectorAll('.mi'),function(m){return m.textContent.trim();}),
 caps:[].map.call(bm.querySelectorAll('.cap'),function(c){return c.textContent;})});})()""")
brief(v)
EXP = ["ctxcopy", "to-h", "to:p", "to-list", "to:fence", "to:quote"]
check("A 菜单项与预期完全一致（复制 + 5 项结构转换）", v.get("acts") == EXP, v.get("acts"))
check("A 无任何 fx: 行内格式项", not any(str(a).startswith("fx:") for a in v.get("acts", [])), v.get("acts"))
BAD = ["粗体", "斜体", "下划线", "删除线", "高亮", "行内代码", "链接", "清除格式", "居中", "对齐"]
check("A 无格式化 / 对齐 / 清除格式文案",
      not any(any(k in t for k in BAD) for t in v.get("texts", [])), v.get("texts"))
check("A 保留复制 / 标题 / 段落 / 列表入口",
      all(any(k in t for t in v.get("texts", [])) for k in ["复制", "标题", "段落", "列表"]), v.get("texts"))
check("A 菜单弹出且 preventDefault 生效", v.get("shown") is True and v.get("prevented") is True,
      {"shown": v.get("shown"), "prevented": v.get("prevented")})

# ---------------------------------------------------------------- B
log("")
log("===== B 未选中右键：保持原样（仅结构转换，无复制） =====")
setmd(MD)
v = jval("""(function(){
window.__t19.collapse('p');
var p=document.querySelector('#editor .blk.b-p p');
var prevented=window.__t19.ctx(p);
return JSON.stringify({prevented:prevented,shown:document.getElementById('blkmenu').classList.contains('show'),
 acts:window.__t19.acts()});})()""")
brief(v)
check("B 未选中菜单仍是原有 5 项结构转换", v.get("acts") == EXP[1:], v.get("acts"))
check("B 未选中菜单不出现复制项", "ctxcopy" not in v.get("acts", []), v.get("acts"))

# ---------------------------------------------------------------- C
log("")
log("===== C 标题选区右键：无「标题居中」对齐项 =====")
setmd("# 标题文字ABC\n\n普通段落文字。")
v = jval("""(function(){
var h=document.querySelector('#editor .blk h1, #editor .blk.b-h h1');
if(!h||!h.firstChild)return JSON.stringify({err:'no h1'});
var tn=h.firstChild,r=document.createRange();
r.setStart(tn,0);r.setEnd(tn,Math.min(6,tn.length));
var s=getSelection();s.removeAllRanges();s.addRange(r);
var prevented=window.__t19.ctx(h);var bm=document.getElementById('blkmenu');
return JSON.stringify({prevented:prevented,acts:window.__t19.acts(),
 texts:[].map.call(bm.querySelectorAll('.mi'),function(m){return m.textContent.trim();})});})()""")
brief(v)
check("C 标题选区无居中 / 对齐项",
      not any(("居中" in t or "对齐" in t) for t in v.get("texts", [])), v.get("texts"))
check("C 标题选区无 fx: 行内格式项",
      not any(str(a).startswith("fx:") for a in v.get("acts", [])), v.get("acts"))
check("C 标题结构转换项仍在", "to-h" in v.get("acts", []), v.get("acts"))

# ---------------------------------------------------------------- D
log("")
log("===== D 悬浮格式化栏仍完整（格式能力未丢失） =====")
setmd(MD)
log(js("""(function(){return String(window.__t19.sel(4,'p'));})()"""))
wait(400)
v = jval("""(function(){
var FB=document.getElementById('floatbar');
return JSON.stringify({show:FB.classList.contains('show'),display:getComputedStyle(FB).display,
 btns:[].map.call(FB.querySelectorAll('button'),function(b){return b.title;}),
 cnt:(FB.querySelector('.fbcnt')||{}).textContent||''});})()""")
brief(v)
check("D 选中文字仍浮现格式化栏且 8 按钮齐全",
      v.get("show") is True and len(v.get("btns", [])) >= 8, {"show": v.get("show"), "btns": v.get("btns")})
log(js("""(function(){
var FB=document.getElementById('floatbar');var b=FB.querySelector('button[title="粗体"]');
if(!b)return 'no-bold';b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'clicked';})()"""))
wait(600)
v = jval("""(function(){return JSON.stringify({hasBold:window.getMarkdown().indexOf('**')>=0,
 head:window.getMarkdown().slice(0,60)});})()""")
brief(v)
check("D 悬浮栏粗体仍生效", v.get("hasBold") is True, v)

# ---------------------------------------------------------------- E
log("")
log("===== E 保留项仍可正常触发（复制 / 转引用 / 标题二级） =====")
setmd(MD)
v = jval("""(function(){
window.__t19.sel(4,'p');var p=document.querySelector('#editor .blk.b-p p');
window.__t19.ctx(p);var bm=document.getElementById('blkmenu');
var mi=bm.querySelector('.mi[data-act="ctxcopy"]');
if(!mi)return JSON.stringify({err:'no ctxcopy'});
var called=false,orig=document.execCommand;
document.execCommand=function(c){if(c==='copy'){called=true;return true;}return orig.apply(document,arguments);};
mi.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
document.execCommand=orig;
return JSON.stringify({called:called,hidden:!bm.classList.contains('show')});})()""")
brief(v)
check("E1 「复制」仍触发原生 copy", v.get("called") is True, v)

setmd(MD)
log(js("""(function(){
window.__t19.sel(4,'p');var p=document.querySelector('#editor .blk.b-p p');
window.__t19.ctx(p);var mi=document.querySelector('#blkmenu .mi[data-act="to:quote"]');
if(!mi)return 'no-quote';mi.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'clicked';})()"""))
wait(600)
v = jval("""(function(){return JSON.stringify({hasQuote:window.getMarkdown().indexOf('> ')>=0});})()""")
brief(v)
check("E2 「引用」块转换仍生效", v.get("hasQuote") is True, v)

setmd(MD)
v = jval("""(function(){
window.__t19.collapse('p');var p=document.querySelector('#editor .blk.b-p p');
window.__t19.ctx(p);var mi=document.querySelector('#blkmenu .mi[data-act="to-h"]');
if(!mi)return JSON.stringify({err:'no to-h'});
mi.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
return JSON.stringify({subs:document.querySelectorAll('.si').length});})()""")
brief(v)
check("E3 「标题」二级子菜单仍展开", v.get("subs", 0) >= 6, v)

# ---------------------------------------------------------------- F
log("")
log("===== F 表格右键：整表拷贝位置 + 专属图标区分度 =====")
setmd(MDT)
v = jval("""(function(){
var td=document.querySelector('#editor .b-table td');
if(!td)return JSON.stringify({err:'no td'});
var prevented=window.__t19.ctx(td);
return JSON.stringify({prevented:prevented,
 shown:document.getElementById('tblbar').classList.contains('show'),
 titles:window.__t19.tbTitles(),copyIcon:window.__t19.tbIcon('拷贝内容'),
 allIcon:window.__t19.tbIcon('拷贝整个表格')});})()""")
brief(v)
titles = v.get("titles", [])
i1 = titles.index("拷贝内容") if "拷贝内容" in titles else -1
i2 = titles.index("拷贝整个表格") if "拷贝整个表格" in titles else -1
ci, ai = v.get("copyIcon") or "", v.get("allIcon") or ""
check("F 「拷贝整个表格」紧跟在「拷贝内容」之后", i1 >= 0 and i2 == i1 + 1, {"copy": i1, "copyall": i2, "top": titles[:4]})
check("F 两个图标明确不同", bool(ci) and bool(ai) and ci != ai, {"same": ci == ai})
check("F 整表图标含表格网格且沿用两矩形复制叠层",
      "<path" in ai and ai.count("<rect") >= 2, ai[:220])
check("F 两图标都用 currentColor（随拷贝状态同步）",
      'stroke="currentColor"' in ci and 'stroke="currentColor"' in ai,
      {"copy": 'stroke="currentColor"' in ci, "copyall": 'stroke="currentColor"' in ai})

# ---------------------------------------------------------------- G / H / I
log("")
log("===== G 点击整表拷贝 → 剪贴板拿到整表源码 =====")
v = jval("""(function(){
var td=document.querySelector('#editor .b-table td');window.__t19.ctx(td);
var cap=window.__t19.grab(function(){
  var TB=document.getElementById('tblbar'),hit=null;
  [].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title==='拷贝整个表格')hit=b;});
  if(hit)hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
});
var raw=window.__t19.raw();
return JSON.stringify({copied:cap,eq:!!cap&&raw.indexOf(cap)>=0});})()""")
brief(v)
check("G 整表拷贝内容 = state.raw 中的表格块", v.get("eq") is True, v)

log("")
log("===== H 「拷贝内容」原行为不变（≠ 整表源码） =====")
setmd(MDT)
v = jval("""(function(){
var td=document.querySelector('#editor .b-table td');window.__t19.ctx(td);
var cap=window.__t19.grab(function(){
  var TB=document.getElementById('tblbar'),hit=null;
  [].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title==='拷贝内容')hit=b;});
  if(hit)hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
});
return JSON.stringify({copied:cap,neq:!!cap&&cap.indexOf('|')<0});})()""")
brief(v)
check("H 拷贝内容仍只拷选中单元格（不含表格管道符）", v.get("neq") is True, v)

log("")
log("===== I HTML 表格同样可拷整表且图标一致 =====")
setmd("HTML表前。\n\n" + HTBL + "\n\nHTML表后。")
v = jval("""(function(){
var td=document.querySelector('#editor .b-table td, #editor table td');
if(!td)return JSON.stringify({err:'no htable td'});
window.__t19.ctx(td);
var icon=window.__t19.tbIcon('拷贝整个表格');
var titles=window.__t19.tbTitles();
var cap=window.__t19.grab(function(){
  var TB=document.getElementById('tblbar'),hit=null;
  [].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title==='拷贝整个表格')hit=b;});
  if(hit)hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
});
var raw=window.__t19.raw();
return JSON.stringify({hasItem:titles.indexOf('拷贝整个表格')>=0,icon:icon,
 copied:cap,eq:!!cap&&raw.indexOf(cap)>=0});})()""")
brief(v)
check("I HTML 表有整表拷贝入口", v.get("hasItem") is True, v.get("hasItem"))
check("I HTML 表图标与管道表一致（含网格）", "<path" in (v.get("icon") or ""), (v.get("icon") or "")[:160])
check("I HTML 表拷到原始 HTML 源码", v.get("eq") is True, v.get("copied"))

# ---------------------------------------------------------------- K
log("")
log("===== K 选中整表 + Delete：只删该表，前后内容不变 =====")
setmd(MDT)
v = jval("""(function(){
window.__rzPick(1);var obj=window.__objSel();var before=window.__t19.raw();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);var after=window.__t19.raw();
return JSON.stringify({obj:obj,prevented:ev.defaultPrevented,before:before,after:after,
 removed:before.length-after.length});})()""")
brief(v)
check("K 选中整表 Delete 只删 1 块且前后段落保留",
      v.get("removed") == 1 and v.get("after") == ["表格前的段落。", "表格后的段落。"]
      and v.get("prevented") is True, {"removed": v.get("removed"), "after": v.get("after")})

# ---------------------------------------------------------------- L / M / O
log("")
log("===== L 表格位于文档首位 =====")
setmd(TBL + "\n\n表格后的段落。")
v = jval("""(function(){
window.__rzPick(0);var obj=window.__objSel();var before=window.__t19.raw();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);var after=window.__t19.raw();
return JSON.stringify({obj:obj,prevented:ev.defaultPrevented,before:before,after:after,
 removed:before.length-after.length});})()""")
brief(v)
check("L 首块表格删除后仅剩后续段落",
      v.get("after") == ["表格后的段落。"] and v.get("prevented") is True, v.get("after"))

log("")
log("===== M 表格位于文档末位 =====")
setmd("表格前的段落。\n\n" + TBL)
v = jval("""(function(){
window.__rzPick(1);var before=window.__t19.raw();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);var after=window.__t19.raw();
return JSON.stringify({prevented:ev.defaultPrevented,before:before,after:after,
 removed:before.length-after.length});})()""")
brief(v)
check("M 末块表格删除后仅剩前序段落",
      v.get("after") == ["表格前的段落。"] and v.get("prevented") is True, v.get("after"))

log("")
log("===== O 表格是唯一块 =====")
setmd(TBL)
v = jval("""(function(){
window.__rzPick(0);var before=window.__t19.raw();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);var after=window.__t19.raw();
return JSON.stringify({prevented:ev.defaultPrevented,before:before,after:after});})()""")
brief(v)
check("O 唯一块表格删除后回落为空文档且不报错",
      v.get("after") == [""] and v.get("prevented") is True, v.get("after"))

# ---------------------------------------------------------------- N
log("")
log("===== N 空白表格：可选中 / 可拷贝 / 可删除 =====")
setmd("前段。\n\n" + EMPTY_TBL + "\n\n后段。")
v = jval("""(function(){
var pick=window.__rzPick(1);var obj=window.__objSel();
var td=document.querySelector('#editor .b-table td');
var prevented=td?window.__t19.ctx(td):null;
var titles=window.__t19.tbTitles();
var cap=window.__t19.grab(function(){
  var TB=document.getElementById('tblbar'),hit=null;
  [].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title==='拷贝整个表格')hit=b;});
  if(hit)hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
});
var raw0=window.__t19.raw();
return JSON.stringify({pick:pick,obj:obj,hasItem:titles.indexOf('拷贝整个表格')>=0,
 cap:cap,capEq:!!cap&&raw0.indexOf(cap)>=0,before:raw0});})()""")
brief(v)
check("N 空白表格可整块选中", v.get("pick") == "ok" and v.get("obj") and "table" in v.get("obj"), v.get("obj"))
check("N 空白表格菜单有整表拷贝且能拷到源码",
      v.get("hasItem") is True and v.get("capEq") is True, {"cap": v.get("cap")})

v = jval("""(function(){
window.__rzPick(1);var before=window.__t19.raw();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);var after=window.__t19.raw();
return JSON.stringify({prevented:ev.defaultPrevented,before:before,after:after});})()""")
brief(v)
check("N 空白表格 Delete 只删该表且前后段落保留",
      v.get("after") == ["前段。", "后段。"] and v.get("prevented") is True, v.get("after"))

log("")
log("===== N2 兼容性：先「拷贝整个表格」再按 Delete 仍能删表 =====")
setmd(MDT)
v = jval("""(function(){
var td=document.querySelector('#editor .b-table td');window.__t19.ctx(td);
window.__t19.grab(function(){
  var TB=document.getElementById('tblbar'),hit=null;
  [].forEach.call(TB.querySelectorAll('.tmi'),function(b){if(b.title==='拷贝整个表格')hit=b;});
  if(hit)hit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
});
window.__rzPick(1);var obj=window.__objSel();var before=window.__t19.raw();
var ev=new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true});
document.dispatchEvent(ev);var after=window.__t19.raw();
return JSON.stringify({obj:obj,active:document.activeElement&&document.activeElement.tagName,
 prevented:ev.defaultPrevented,before:before,after:after});})()""")
brief(v)
check("N2 拷贝后 Delete 仍可删整表（焦点 / 选区兼容）",
      v.get("after") == ["表格前的段落。", "表格后的段落。"] and v.get("prevented") is True, v)

# ---------------------------------------------------------------- P
log("")
log("===== P 守卫：单元格内编辑 Backspace 不误删整表 =====")
setmd(MDT)
v = jval("""(function(){
window.__rzPick(1);
var td=document.querySelector('#editor .b-table td');
var tn=td.firstChild||td;var r=document.createRange();
r.setStart(tn,0);r.collapse(true);
var s=getSelection();s.removeAllRanges();s.addRange(r);
var before=window.__t19.raw();
var ev=new KeyboardEvent('keydown',{key:'Backspace',bubbles:true,cancelable:true});
document.dispatchEvent(ev);var after=window.__t19.raw();
return JSON.stringify({obj:window.__objSel(),prevented:ev.defaultPrevented,
 before:before,after:after,removed:before.length-after.length});})()""")
brief(v)
check("P 单元格内 Backspace 不删整表",
      v.get("removed") == 0 and v.get("prevented") is False, {"removed": v.get("removed"), "prevented": v.get("prevented")})

# ---------------------------------------------------------------- Q
log("")
log("===== Q 其他区域右键菜单保持原样 =====")
setmd("# 标题\n\n---\n\n结尾段。")
v = jval("""(function(){
var hr=document.querySelector('#editor .blk hr');
if(!hr)return JSON.stringify({err:'no hr'});
var prevented=window.__t19.ctx(hr);
return JSON.stringify({prevented:prevented,acts:window.__t19.acts()});})()""")
brief(v)
check("Q1 分割线专属菜单仍含删除等块操作", "del" in v.get("acts", []), v.get("acts"))

setmd("```js\nlet a = 1;\n```\n\n普通段落。")
v = jval("""(function(){
var cb=document.querySelector('#editor .codebar')||
       document.querySelector('#editor .codeblock')||
       document.querySelector('#editor .blk.b-fence');
if(!cb)return JSON.stringify({err:'no codeblock'});
var prevented=window.__t19.ctx(cb);
return JSON.stringify({target:String(cb.className),prevented:prevented,
 acts:window.__t19.acts(),
 texts:[].map.call(document.getElementById('blkmenu').querySelectorAll('.mi'),
        function(m){return m.textContent.trim();})});})()""")
brief(v)
_acts = v.get("acts", [])
check("Q2 代码块菜单未被改动（无行内格式项，专属动作仍在）",
      v.get("prevented") is True
      and not any(str(a).startswith("fx:") for a in _acts)
      and (("codecpl" in _acts or "del" in _acts) if _acts else True), v)

# ---------------------------------------------------------------- R
log("")
log("===== R 源码 / 预览模式回归 + JS 错误 + Markdown 往返 =====")
setmd(MD)
v = jval("""(function(){window.setSourceMode(true);var ED=document.getElementById('editor');
return JSON.stringify({host:window.__oneHostActive(),edCE:ED.getAttribute('contenteditable'),
 srcWrap:!!document.querySelector('.src-wrap')});})()""")
brief(v)
wait(300)
v = jval("""(function(){window.setSourceMode(false);var ED=document.getElementById('editor');
return JSON.stringify({host:window.__oneHostActive(),edCE:ED.getAttribute('contenteditable'),
 n:ED.children.length,mdEq:window.getMarkdown()===%s});})()""" % json.dumps(MD, ensure_ascii=False))
brief(v)
check("R1 源码模式切换后 Markdown 往返一致", v.get("mdEq") is True and v.get("host") is True, v)
wait(300)
v = jval("""(function(){window.setPreviewMode(true);window.setPreviewContent(%s);
var ED=document.getElementById('editor');
return JSON.stringify({host:window.__oneHostActive(),edCE:ED.getAttribute('contenteditable')});})()""" % json.dumps(MD, ensure_ascii=False))
brief(v)
wait(400)
v = jval("""(function(){window.setPreviewMode(false);
return JSON.stringify({host:window.__oneHostActive(),
 errN:(window.__errs||[]).length,errs:(window.__errs||[]).slice(0,6),
 mdEq:window.getMarkdown()===%s});})()""" % json.dumps(MD, ensure_ascii=False))
brief(v)
check("R2 预览模式退出后 Markdown 往返一致", v.get("mdEq") is True, v)
check("R3 全程 0 个 JS 错误", v.get("errN") == 0, {"errN": v.get("errN"), "errs": v.get("errs")})

log("")
log("SUMMARY: %d PASS / %d FAIL" % (len(PASS), len(FAIL)))
if FAIL:
    log("FAILED ITEMS: " + " | ".join(FAIL))
print("SUMMARY: %d PASS / %d FAIL" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
