# -*- coding: utf-8 -*-
"""m115：列表模块 v3.38 修复验收（依据 docs/列表模块交互规范-v3.37.md）

覆盖：LIST-4 行中回车拆分（含行内格式）· LIST-5 待办回车继承 [ ] ·
      LIST-6 块菜单「转为列表」保项数 · L-14/E6 Esc 失焦退出编辑
      + 回归（行尾回车 / 空项回车退出 / 有序编号顺延 / Tab 缩进 / 富文本追加）
结果：tests/_m115_listfix.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m115_listfix.txt")
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
note("boot hooks=%s" % js("JSON.stringify({sm:typeof window.setMarkdown,rw:typeof window.__raw})"))


def rawof():
    try:
        return (json.loads(js("window.__raw()") or "{}").get("raw")) or []
    except Exception:
        return []


def setmd(md, ms=780):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def lstate():
    return jj("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
              "return JSON.stringify({n:lis.length,"
              "lines:lis.map(function(l){return l.getAttribute('data-line')}),"
              "txt:lis.map(function(l){return (l.textContent||'').slice(0,30)}),"
              "ncb:document.querySelectorAll('#editor li input[type=checkbox]').length,"
              "ae:(function(){var a=document.activeElement;"
              "return a?(a.tagName+':'+(a.getAttribute&&a.getAttribute('data-line'))):''})()})})()")


def caret_li(nth, off):
    """off=-1 = 最后一个文本节点末尾（v3.38 修正，见 _m103_listspec A4）"""
    if off == -1:
        js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
           "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
           "var w=document.createTreeWalker(li,NodeFilter.SHOW_TEXT,null);var n,last=null;"
           "while(n=w.nextNode()){last=n;}"
           "var s=window.getSelection();s.removeAllRanges();var rg=document.createRange();"
           "if(!last){rg.setStart(li,0);rg.collapse(true);s.addRange(rg);return 'empty'}"
           "rg.setStart(last,last.nodeValue.length);rg.collapse(true);s.addRange(rg);return 'ok'})()")
    else:
        js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
           "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
           "var w=document.createTreeWalker(li,NodeFilter.SHOW_TEXT,null);var n;"
           "while(n=w.nextNode()){var L=n.nodeValue.length;var o=" + str(off) + ";"
           "if(o<=L){var rg=document.createRange();rg.setStart(n,Math.min(o,L));rg.collapse(true);"
           "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'}}"
           "return 'fallback'})()")
    wait(220)


def key_li(nth, key, shift=False, ctrl=False, ms=520):
    js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
       "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
       "var ev=new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,shiftKey:" + ("true" if shift else "false") +
       ",ctrlKey:" + ("true" if ctrl else "false") + "});"
       "li.dispatchEvent(ev);return 'ok'})()")
    wait(ms)


def type_li(nth, txt, ms=520):
    js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
       "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
       "document.execCommand('insertText',false," + json.dumps(txt) + ");"
       "li.dispatchEvent(new Event('input',{bubbles:true}));return 'ok'})()")
    wait(ms)


def open_menu():
    js("window.openBlockMenu()")
    wait(560)


def open_list_sub():
    js("(function(){var BM=document.getElementById('blkmenu');"
       "var it=BM&&BM.querySelector('.mi[data-act=\"to-list\"]');"
       "if(!it)return 'no-item';"
       "it.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
       "it.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(560)


def pick_sub(k):
    js("(function(){var S=document.getElementById('submenu');"
       "var it=S&&S.querySelector('.si[data-k=\"" + str(k) + "\"]');"
       "if(!it)return 'no-si';"
       "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(640)


# ============ A 组：LIST-4 行中回车拆分 ============
note("========== A 组：LIST-4 行中回车拆分 ==========")
setmd("- 甲乙丙")
caret_li(0, 1)
key_li(0, "Enter")
g = rawof()
check("A1 行中回车（偏移 1）→ 后半移入新项",
      g and g[0] == "- 甲\n- 乙丙", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲乙丙")
caret_li(0, 2)
key_li(0, "Enter")
g = rawof()
check("A2 行中回车（偏移 2）→ 按光标位置拆分",
      g and g[0] == "- 甲乙\n- 丙", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲乙丙")
caret_li(0, 3)          # 行尾：不拆分，新增空项
key_li(0, "Enter")
g = rawof()
check("A3 行尾回车仍为「新增空项」（不误拆）",
      g and g[0] == "- 甲乙丙\n- ", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- **粗**体")
caret_li(0, 1)          # 纯文本「粗体」偏移 1 → 源码 **粗** 之后
key_li(0, "Enter")
g = rawof()
check("A4 含行内格式项拆分 → 标记不丢（前半带 **粗**，后半裸文本）",
      g and g[0] == "- **粗**\n- 体", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- **粗体**项")
caret_li(0, -1)
type_li(0, "追加")
g = rawof()
check("A5 富文本项末尾追加 → 标记与文字均正确（LIST-2 回归）",
      g and g[0] == "- **粗体**项追加", "raw=%s" % json.dumps(g, ensure_ascii=False))

# ============ B 组：LIST-5 待办回车继承 [ ] ============
note("========== B 组：LIST-5 待办回车继承 ==========")
setmd("- [ ] 甲\n- [ ] 乙")
caret_li(0, -1)
key_li(0, "Enter")
g = rawof()
s = lstate()
check("B1 未勾选项回车 → 新项继承 - [ ] ",
      g and g[0] == "- [ ] 甲\n- [ ] \n- [ ] 乙" and s.get("ncb") == 3,
      "raw=%s cb=%s" % (json.dumps(g, ensure_ascii=False), s.get("ncb")))

setmd("- [x] 甲\n- [ ] 乙")
caret_li(0, -1)
key_li(0, "Enter")
g = rawof()
check("B2 已勾选项回车 → 原项保持 [x]、新项为 [ ]",
      g and g[0] == "- [x] 甲\n- [ ] \n- [ ] 乙",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

# ============ C 组：LIST-6 块菜单转列表保项数 ============
note("========== C 组：LIST-6 转列表保项数 ==========")
setmd("- 甲项\n- 乙项\n- 丙项")
open_menu()
open_list_sub()
pick_sub(1)             # 有序列表
g = rawof()
s = lstate()
check("C1 三项列表 → 转为有序：仍 3 项且编号顺延",
      s.get("n") == 3 and g and g[0] == "1. 甲项\n2. 乙项\n3. 丙项",
      "n=%s raw=%s" % (s.get("n"), json.dumps(g, ensure_ascii=False)))

setmd("- 甲项\n- 乙项\n- 丙项")
open_menu()
open_list_sub()
pick_sub(2)             # 待办事项
g = rawof()
s = lstate()
check("C2 三项列表 → 转为待办：仍 3 项且各有 checkbox",
      s.get("n") == 3 and s.get("ncb") == 3 and g and g[0] == "- [ ] 甲项\n- [ ] 乙项\n- [ ] 丙项",
      "n=%s cb=%s raw=%s" % (s.get("n"), s.get("ncb"), json.dumps(g, ensure_ascii=False)))

setmd("- [ ] 甲\n- [x] 乙")
open_menu()
open_list_sub()
pick_sub(0)             # 无序列表：应剥掉待办盒
g = rawof()
s = lstate()
check("C3 待办 → 转为无序：checkbox 一并剥除",
      s.get("n") == 2 and s.get("ncb") == 0 and g and g[0] == "- 甲\n- 乙",
      "n=%s cb=%s raw=%s" % (s.get("n"), s.get("ncb"), json.dumps(g, ensure_ascii=False)))

setmd("甲项\n乙项\n丙项")
open_menu()
open_list_sub()
pick_sub(0)
g = rawof()
s = lstate()
check("C4 三行段落 → 转为无序：三行各成一项（不再压成延续行）",
      s.get("n") == 3, "n=%s raw=%s" % (s.get("n"), json.dumps(g, ensure_ascii=False)))

# ============ D 组：L-14 / E6 Esc 失焦退出 ============
note("========== D 组：L-14 Esc 失焦退出编辑 ==========")
setmd("前段\n\n- 甲项\n- 乙项")
caret_li(0, -1)
before = rawof()
key_li(0, "Escape")
g = rawof()
s = lstate()
check("D1 列表项按 Esc → 内容不动、焦点离开 li",
      g == before and "LI" not in str(s.get("ae")),
      "ae=%s raw=%s" % (s.get("ae"), json.dumps(g, ensure_ascii=False)))

setmd("- 甲项")
caret_li(0, -1)
key_li(0, "Escape")
g = rawof()
check("D2 Esc 不删项、不转段落（列表结构保留）",
      g and g[0] == "- 甲项", "raw=%s" % json.dumps(g, ensure_ascii=False))

# ============ E 组：既有行为回归 ============
note("========== E 组：既有行为回归 ==========")
setmd("- 甲项\n- 乙项")
caret_li(0, -1)
key_li(0, "Enter")
g = rawof()
check("E1 行尾回车 → 新增同级空项（marker 一致）",
      g and g[0] == "- 甲项\n- \n- 乙项", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲项\n- 乙项")
caret_li(1, -1)
key_li(1, "Enter")
key_li(2, "Enter")      # 空项上再回车 → 退出列表
g = rawof()
note("  空项回车退出 → raw=%s" % json.dumps(g, ensure_ascii=False))
check("E2 空项回车 → 列表保留 + 其后新建空段落",
      len(g) == 2 and g[0] == "- 甲项\n- 乙项" and g[1] == "",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("1. 甲\n2. 乙")
caret_li(0, -1)
key_li(0, "Enter")
g = rawof()
check("E3 有序列表回车 → 编号顺延",
      g and g[0] == "1. 甲\n2. \n3. 乙", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲项\n- 乙项")
caret_li(1, 0)
key_li(1, "Tab")
g = rawof()
check("E4 第 2 项 Tab → 缩进为子项（4 空格）",
      g and g[0] == "- 甲项\n    - 乙项", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲项\n- 乙项")
caret_li(1, 0)
key_li(1, "Backspace")
g = rawof()
check("E5 非空项行首退格 → 合并进上一项",
      g and g[0] == "- 甲项乙项", "raw=%s" % json.dumps(g, ensure_ascii=False))

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
