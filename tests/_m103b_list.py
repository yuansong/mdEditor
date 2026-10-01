# -*- coding: utf-8 -*-
"""m103b 列表规范复验：甄别 _m103 的 4 个 FAIL + 补测块菜单转换 / Shift+Enter / 有序编号

R1 A4 行内格式保留（光标修正到 li 末文本节点）
R2 行中回车拆分（多位置复验）+ Shift+Enter
R3 待办回车继承 checkbox（重复复验）
R4 ↑ 跳出（断言口径修正）
R5 块菜单「转为列表」在列表块上的结构影响（transformTo 只加首行 marker）
R6 有序列表缩进后编号 / Shift+Enter / Tab 观察
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QAction
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m103b_list.txt")
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


def rawof():
    r = js("window.__raw()")
    try:
        return (json.loads(r or "{}").get("raw")) or []
    except Exception:
        return []


def setmd(md, ms=760):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def lstate():
    return jj("(function(){var scope=document.querySelector('#editor');"
              "var lis=[].slice.call(scope.querySelectorAll('li'));"
              "var rw={};try{rw=JSON.parse(window.__raw()||'{}')}catch(e){}"
              "return JSON.stringify({n:lis.length,"
              "txt:lis.map(function(l){return (l.textContent||'').slice(0,24)}),"
              "raw:rw.raw||[],"
              "nul:scope.querySelectorAll('ul').length,"
              "nol:scope.querySelectorAll('ol').length,"
              "ncb:scope.querySelectorAll('li input[type=checkbox]').length,"
              "ae:document.activeElement?document.activeElement.tagName:''})})()")


def caret_li_tail(nth):
    """光标置于 li 内【最后一个】文本节点末尾（修正 _m103 取首个节点的伪影）"""
    js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
       "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
       "var w=document.createTreeWalker(li,NodeFilter.SHOW_TEXT,null);var n,last=null;"
       "while(n=w.nextNode()){if(n.nodeValue.length)last=n}"
       "if(!last)return 'no-text';"
       "var rg=document.createRange();rg.setStart(last,last.nodeValue.length);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(200)


def caret_li(nth, off):
    js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
       "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
       "var w=document.createTreeWalker(li,NodeFilter.SHOW_TEXT,null);var n,tot=0,hit=null;"
       "while(n=w.nextNode()){var L=n.nodeValue.length;"
       "if(" + str(off) + "<=tot+L){hit={n:n,o:" + str(off) + "-tot};break}tot+=L}"
       "if(!hit)return 'oob';"
       "var rg=document.createRange();rg.setStart(hit.n,hit.o);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(200)


def key_li(nth, key, shift=False, ctrl=False, ms=430):
    js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
       "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
       "var ev=new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,shiftKey:" + ("true" if shift else "false") +
       ",ctrlKey:" + ("true" if ctrl else "false") + "});"
       "li.dispatchEvent(ev);return 'ok'})()")
    wait(ms)


def type_li(nth, txt):
    js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
       "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
       "document.execCommand('insertText',false," + json.dumps(txt) + ");"
       "li.dispatchEvent(new Event('input',{bubbles:true}));return 'ok'})()")
    wait(430)


note("========== R1 行内格式保留（光标修正） ==========")
setmd("- **粗体**项")
caret_li_tail(0)
type_li(0, "追加")
g = rawof()
check("R1 含行内格式列表项末尾编辑 → 标记与文字均正确（LIST-2 回归）",
      g and g[0] == "- **粗体**项追加", "raw=%s" % json.dumps(g, ensure_ascii=False))

note("========== R2 行中回车（拆分）多位置复验 ==========")
for pos in (1, 2, 3):
    setmd("- 甲乙丙")
    caret_li(0, pos)
    key_li(0, "Enter")
    g = rawof()
    note("  行中 pos=%d → raw=%s" % (pos, json.dumps(g, ensure_ascii=False)))
setmd("- 甲乙丙")
caret_li(0, 2)
key_li(0, "Enter")
g = rawof()
check("R2 行中回车按光标拆分（v3.38 LIST-4 修复：后半文字移入新项）",
      g and g[0] == "- 甲乙\n- 丙", "raw=%s" % json.dumps(g, ensure_ascii=False))

note("========== R2b Shift+Enter / Ctrl+Enter ==========")
setmd("- 甲乙")
caret_li(0, 1)
key_li(0, "Enter", shift=True)
g = rawof()
note("  Shift+Enter → raw=%s" % json.dumps(g, ensure_ascii=False))
check("R2b Shift+Enter 与 Enter 行为相同（无软换行，随 LIST-4 一并拆分）",
      g and g[0] == "- 甲\n- 乙", "raw=%s" % json.dumps(g, ensure_ascii=False))
setmd("- 甲乙")
caret_li(0, 1)
key_li(0, "Enter", ctrl=True)
g = rawof()
note("  Ctrl+Enter → raw=%s（未被拦截=浏览器默认无动作）" % json.dumps(g, ensure_ascii=False))

note("========== R3 待办回车继承（重复复验） ==========")
for rnd in range(3):
    setmd("- [ ] 甲\n- [ ] 乙")
    caret_li(1, -1)
    key_li(1, "Enter")
    g = rawof()
    note("  round%d → raw=%s" % (rnd, json.dumps(g, ensure_ascii=False)))
setmd("- [x] 甲\n- [ ] 乙")
caret_li(0, -1)
key_li(0, "Enter")
g = rawof()
s = lstate()
check("R3 待办项回车新项继承 [ ]（v3.38 LIST-5 修复）",
      g and g[0] == "- [x] 甲\n- [ ] \n- [ ] 乙" and s.get("ncb") == 3,
      "raw=%s cb=%s" % (json.dumps(g, ensure_ascii=False), s.get("ncb")))

note("========== R4 ↑ 跳出（断言口径修正） ==========")
setmd("前段\n\n- 甲项\n- 乙项\n\n尾段")
caret_li(0, 0)
before = rawof()
key_li(0, "ArrowUp", ms=520)
s = lstate()
after = rawof()
check("R4 首项行首 ↑ → 焦点离开 li 且文档内容不变",
      str(s.get("ae")) != "LI" and before == after,
      "ae=%s same=%s" % (s.get("ae"), before == after))

note("========== R5 块菜单「转为列表」在列表块上的效果 ==========")
note("  可用 QAction：%s" % json.dumps(
    [a.text() for a in win.findChildren(QAction) if a.text() in ("块菜单", "插入菜单")],
    ensure_ascii=False))
setmd("- 甲项\n- 乙项\n- 丙项")
caret_li(0, 0)
acts = [a for a in win.findChildren(QAction) if a.text() == "块菜单"]
if acts:
    acts[0].trigger()
    wait(620)
    bm = jj("(function(){var BM=document.getElementById('blkmenu');"
            "if(!BM)return JSON.stringify({no:1});"
            "return JSON.stringify({vis:getComputedStyle(BM).display,"
            "items:[].slice.call(BM.querySelectorAll('.mi')).map(function(m){return m.getAttribute('data-act')})})})()")
    note("  块菜单=%s" % json.dumps(bm, ensure_ascii=False))
    js("(function(){var BM=document.getElementById('blkmenu');"
       "var it=BM&&BM.querySelector('.mi[data-act=\"to-list\"]');"
       "if(!it)return 'no-item';"
       "it.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
       "it.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(520)
    sub = jj("(function(){var BM=document.getElementById('blkmenu');"
             "var ps=document.querySelectorAll('.mi[data-act^=\"to:\"]');"
             "return JSON.stringify({acts:[].slice.call(ps).map(function(m){return m.getAttribute('data-act')}),"
             "bmItems:[].slice.call(BM.querySelectorAll('.mi')).map(function(m){return m.getAttribute('data-act')})})})()")
    note("  二级=%s" % json.dumps(sub, ensure_ascii=False))
    js("(function(){var ps=document.querySelectorAll('.mi[data-act=\"to:ol\"]');"
       "for(var k=0;k<ps.length;k++){var m=ps[k];"
       "if(m.offsetParent||getComputedStyle(m).display!=='none'){"
       "m.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'hit'+k}}"
       "return 'no-target'})()")
    wait(620)
    g = rawof()
    s = lstate()
    note("  转有序后 raw=%s li=%s" % (json.dumps(g, ensure_ascii=False), s.get("n")))
    check("R5 列表块「转为→有序列表」后仍是 3 个独立项",
          g and g[0].count("\n") >= 2 and s.get("n") == 3,
          "raw=%s n=%s" % (json.dumps(g, ensure_ascii=False), s.get("n")))
else:
    note("  未找到「块菜单」QAction，R5 跳过")

note("========== R6 有序列表缩进后编号 ==========")
setmd("1. 甲\n2. 乙")
caret_li(1, 0)
key_li(1, "Tab")
g = rawof()
s = lstate()
note("  缩进后 raw=%s ol=%s txt=%s" % (json.dumps(g, ensure_ascii=False), s.get("nol"),
                                    json.dumps(s.get("txt"), ensure_ascii=False)))
check("R6 有序列表子项缩进后编号仍从 1 起（子列表独立编号）",
      g and "    2. 乙" in g[0], "raw=%s" % json.dumps(g, ensure_ascii=False))

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
