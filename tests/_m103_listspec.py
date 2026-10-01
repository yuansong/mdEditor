# -*- coding: utf-8 -*-
"""m103 列表（ul / ol / todo）操作规范实证：进入 / 回车 / 退格 / 缩进 / 退出 / 内容类型

用户要求（2026-10-01）：按引用、代码块相同方式排查列表模块 ——
 1) 入口与创建   2) 换行与段落延续   3) 退出方式（全路径）
 4) 支持 / 不支持的内容类型   5) 快捷键交互   6) 竞品差异项
衔接：LIST-1/2/3（v3.30.18 已修）、QUO-8/9/10/11（引用规范，v3.38 修复范式）
版本：src v3.37（2026-10-01 08:36:05，697724B，sha16 D349A294171B46E9）
结果：tests/_m103_list.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m103_list.txt")
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


# 启动等待（_m101 教训：过早调 setMarkdown 报 not a function）
wait(2800)
note("boot hooks=%s" % js("JSON.stringify({sm:typeof window.setMarkdown,rw:typeof window.__raw,af:typeof window.__applyFloat})"))


def rawof():
    """返回当前文档 raw（块数组）"""
    r = js("window.__raw()")
    try:
        d = json.loads(r or "{}")
        return d.get("raw") or []
    except Exception:
        return []


def setmd(md, ms=760):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def lstate():
    """列表块状态：li 数量 / data-line / raw / 是否源码态 / 结构"""
    return jj("(function(){var blk=document.querySelector('#editor .blk');"
              "var scope=document.querySelector('#editor');"
              "var lis=[].slice.call(scope.querySelectorAll('li'));"
              "var rw={};try{rw=JSON.parse(window.__raw()||'{}')}catch(e){}"
              "return JSON.stringify({"
              "n:lis.length,"
              "lines:lis.map(function(l){return l.getAttribute('data-line')}),"
              "ce:lis.map(function(l){return l.getAttribute('contenteditable')}),"
              "txt:lis.map(function(l){return (l.textContent||'').slice(0,24)}),"
              "raw:rw.raw||[],editIdx:rw.editIdx,"
              "nul:scope.querySelectorAll('ul').length,"
              "nol:scope.querySelectorAll('ol').length,"
              "npre:scope.querySelectorAll('.blk pre, .blk .codeblock').length,"
              "ncb:scope.querySelectorAll('li input[type=checkbox]').length,"
              "cbOn:[].slice.call(scope.querySelectorAll('li input[type=checkbox]')).map(function(c){return c.checked}),"
              "olStart:(function(){var o=scope.querySelector('ol');return o?o.getAttribute('start'):null})(),"
              "blkCls:blk?blk.className:'',"
              "ae:document.activeElement?(document.activeElement.tagName+':'+(document.activeElement.getAttribute&&document.activeElement.getAttribute('data-line'))):''"
              "})})()")


def caret_li(nth, off):
    """光标置于第 nth 个 li（0 基）内第 off 个字符；off=-1 表示行尾。

    v3.38 修正：off=-1 旧实现落在**首个**文本节点末尾 —— 含行内格式的项
    （`<strong>粗体</strong>项`）里会把追加文字写进标记内部，得出
    `- **粗体追加**项` 这种假缺陷（A4）。现改为最后一个文本节点末尾。"""
    if off == -1:
        js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
           "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
           "var w=document.createTreeWalker(li,NodeFilter.SHOW_TEXT,null);var n,last=null;"
           "while(n=w.nextNode()){last=n;}"
           "var s=window.getSelection();s.removeAllRanges();"
           "var rg=document.createRange();"
           "if(!last){rg.setStart(li,0);rg.collapse(true);s.addRange(rg);return 'empty'}"
           "rg.setStart(last,last.nodeValue.length);rg.collapse(true);"
           "s.addRange(rg);return 'ok'})()")
    else:
        js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
           "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
           "var w=document.createTreeWalker(li,NodeFilter.SHOW_TEXT,null);var n,tot=0;"
           "while(n=w.nextNode()){var L=n.nodeValue.length;var o=" + str(off) + ";"
           "if(o<=L){"
           "var rg=document.createRange();rg.setStart(n,Math.min(o,L));rg.collapse(true);"
           "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'}"
           "tot+=L;}"
           "return 'fallback'})()")
    wait(200)


def key_li(nth, key, shift=False, ctrl=False, ms=430):
    js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
       "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
       "var ev=new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,shiftKey:" + ("true" if shift else "false") +
       ",ctrlKey:" + ("true" if ctrl else "false") + "});"
       "li.dispatchEvent(ev);return 'ok'})()")
    wait(ms)


def type_li(nth, txt, ms=430):
    """在 li 光标处插入文字（走 execCommand，触发 input → syncListLi）"""
    js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
       "var li=lis[" + str(nth) + "];if(!li)return 'no-li';li.focus();"
       "document.execCommand('insertText',false," + json.dumps(txt) + ");"
       "li.dispatchEvent(new Event('input',{bubbles:true}));return 'ok'})()")
    wait(ms)


note("========== A 组：渲染态结构与编辑回写 ==========")
setmd("- 甲项\n- 乙项")
s = lstate()
check("A1 两个 li 均 plaintext-only 且带 data-line",
      s.get("n") == 2 and all(c == "plaintext-only" for c in s.get("ce", []))
      and s.get("lines") == ["0", "1"],
      "inf=%s" % json.dumps({k: s.get(k) for k in ("n", "ce", "lines")}, ensure_ascii=False))
check("A2 渲染为单个 ul（无多余 pre/代码块）",
      s.get("nul") == 1 and s.get("nol") == 0 and s.get("npre") == 0,
      "ul=%s ol=%s pre=%s" % (s.get("nul"), s.get("nol"), s.get("npre")))
check("A3 列表块非源码态（渲染态可直编）",
      "raw-edit" not in str(s.get("blkCls", "")), "cls=%s" % s.get("blkCls"))

setmd("- **粗体**项")
caret_li(0, -1)
type_li(0, "追加")
g = rawof()
check("A4 含行内格式列表项编辑 → 标记保留（LIST-2 回归）",
      g and g[0] == "- **粗体**项追加", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("1. 甲\n2. 乙\n3. 丙")
s = lstate()
check("A5 有序列表渲染为 ol 且编号自 1 起", s.get("nol") == 1 and s.get("n") == 3,
      "inf=%s" % json.dumps(s.get("txt"), ensure_ascii=False))
setmd("3. 甲\n4. 乙")
s = lstate()
check("A6 有序列表保留原始起始编号（start 属性）", str(s.get("olStart")) == "3",
      "start=%s" % s.get("olStart"))

note("========== B 组：回车（新增 / 拆分 / 空项退出） ==========")
setmd("- 甲项\n- 乙项")
caret_li(0, -1)
key_li(0, "Enter")
g = rawof()
check("B1 行尾回车 → 插入同级新项（marker 一致）",
      g and g[0] == "- 甲项\n- \n- 乙项", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲乙")
caret_li(0, 1)      # 光标在「甲」「乙」之间（两字之间 = 偏移 1；2 已是行尾）
key_li(0, "Enter")
g = rawof()
check("B2 行中回车 → 后半文字移入新项（Typora 式拆分）",
      g and g[0] == "- 甲\n- 乙", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲项")
caret_li(0, -1)
key_li(0, "Enter")      # 产生空项
key_li(1, "Enter")      # 空项上再回车 → 退出
g = rawof()
s = lstate()
check("B3 空项回车 → 退出列表：列表保留 + 其后新建空段落",
      len(g) >= 2 and g[0] == "- 甲项" and g[1] == "",
      "raw=%s" % json.dumps(g, ensure_ascii=False))
check("B4 退出落点不是源码态（QUO-8 同型校验：无字面 - 泄漏）",
      "raw-edit" not in str(s.get("blkCls", "")), "cls=%s ae=%s" % (s.get("blkCls"), s.get("ae")))

setmd("- 甲项\n\n尾段")
caret_li(0, -1)
key_li(0, "Enter")
key_li(1, "Enter", ms=520)
g = rawof()
check("B5 连续两次回车（非空块后）→ 列表未被拍平、文档块数 +1",
      len(g) == 3 and g[0] == "- 甲项" and g[1] == "", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("1. 甲\n2. 乙")
caret_li(0, -1)
key_li(0, "Enter")
g = rawof()
check("B6 有序列表回车 → 新项编号 +1 且后续顺延",
      g and g[0] == "1. 甲\n2. \n3. 乙", "raw=%s" % json.dumps(g, ensure_ascii=False))

note("========== C 组：退格（合并 / 转段落 / 删空项） ==========")
setmd("- 甲项\n- 乙项")
caret_li(1, 0)
key_li(1, "Backspace")
g = rawof()
check("C1 第 2 项行首退格 → 合并进上一项",
      g and g[0] == "- 甲项乙项", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲项")
caret_li(0, 0)
key_li(0, "Backspace")
g = rawof()
check("C2 仅一项行首退格 → 转段落（去掉 marker）",
      g and g[0] == "甲项", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲项\n- \n- 乙项")
caret_li(1, 0)
key_li(1, "Backspace")
g = rawof()
check("C3 空项行首退格 → 仅删该行（列表保留）",
      g and g[0] == "- 甲项\n- 乙项", "raw=%s" % json.dumps(g, ensure_ascii=False))

note("========== D 组：Tab / Shift+Tab 缩进 ==========")
setmd("- 甲项\n- 乙项")
caret_li(1, 0)
key_li(1, "Tab")
g = rawof()
s = lstate()
check("D1 第 2 项 Tab → 缩进 4 空格", g and g[0] == "- 甲项\n    - 乙项",
      "raw=%s" % json.dumps(g, ensure_ascii=False))
check("D2 缩进后渲染为嵌套子列表（ul 内嵌 ul）", s.get("nul") == 2,
      "ul=%s txt=%s" % (s.get("nul"), json.dumps(s.get("txt"), ensure_ascii=False)))

setmd("- 甲项\n- 乙项")
caret_li(0, 0)
key_li(0, "Tab")
g = rawof()
s = lstate()
note("  D3 首项 Tab → raw=%s pre=%s" % (json.dumps(g, ensure_ascii=False), s.get("npre")))
check("D3 首项 Tab 不产生代码块（缩进不触发源码泄漏）", s.get("npre") == 0,
      "raw=%s pre=%s" % (json.dumps(g, ensure_ascii=False), s.get("npre")))

setmd("- 甲项\n    - 乙项")
caret_li(1, 0)
key_li(1, "Tab", shift=True)
g = rawof()
check("D4 Shift+Tab → 剥除一级缩进", g and g[0] == "- 甲项\n- 乙项",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

note("========== E 组：退出方式全路径 ==========")
setmd("前段\n\n- 甲项\n- 乙项\n\n尾段")
caret_li(0, 0)
key_li(0, "ArrowUp", ms=520)
s = lstate()
g = rawof()
check("E1 首项行首 ↑ → 跳出到上一块（列表内容不变）",
      len(g) == 3 and g[1] == "- 甲项\n- 乙项" and "LI" not in str(s.get("ae")),
      "ae=%s raw=%s" % (s.get("ae"), json.dumps(g, ensure_ascii=False)))

setmd("前段\n\n- 甲项\n- 乙项\n\n尾段")
caret_li(1, -1)
key_li(1, "ArrowDown", ms=520)
s = lstate()
check("E2 末项行尾 ↓ → 跳出到下一块", "LI" not in str(s.get("ae")), "ae=%s" % s.get("ae"))

setmd("- 甲项\n- 乙项")
caret_li(0, -1)
before = rawof()
key_li(0, "Escape", ms=520)
s = lstate()
after = rawof()
check("E3 Esc → 内容不变（不清空、不转段落）", before == after,
      "before=%s after=%s" % (json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))
note("  E3 Esc 后 activeElement=%s / 焦点是否仍在 li：%s" % (s.get("ae"), "LI" in str(s.get("ae"))))

setmd("- 甲项\n- 乙项\n\n尾段")
caret_li(0, -1)
js("(function(){var t=document.querySelector('#editor .blk:last-child');"
   "if(!t)return 'no';var r=t.getBoundingClientRect();"
   "document.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,clientX:r.left+5,clientY:r.top+5}));"
   "return 'ok'})()")
wait(520)
g = rawof()
s = lstate()
check("E4 点击列表外区域 → 列表保持渲染态且 raw 不变",
      g and g[0] == "- 甲项\n- 乙项" and "raw-edit" not in str(s.get("blkCls", "")),
      "raw=%s cls=%s" % (json.dumps(g, ensure_ascii=False), s.get("blkCls")))

note("========== F 组：内容类型（延续行 / 行内格式 / 嵌套） ==========")
setmd("- 第一行\n第二行\n第三行")
s = lstate()
note("  F1 lazy 延续行：li 数=%s data-line=%s txt=%s" %
     (s.get("n"), json.dumps(s.get("lines")), json.dumps(s.get("txt"), ensure_ascii=False)))
check("F1 延续行（无 marker 的后续行）不产生独立可编辑 li",
      s.get("n") == 1, "n=%s lines=%s" % (s.get("n"), json.dumps(s.get("lines"))))
caret_li(0, -1)
type_li(0, "X")
g = rawof()
note("  F1b 在延续行文本后输入 → raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲项\n  - 子项甲\n  - 子项乙\n- 乙项")
s = lstate()
check("F2 嵌套子列表渲染为嵌套结构且各层可编辑",
      s.get("n") == 4 and s.get("nul") == 2,
      "n=%s ul=%s lines=%s" % (s.get("n"), s.get("nul"), json.dumps(s.get("lines"))))
caret_li(1, -1)
type_li(1, "改")
g = rawof()
check("F3 子项编辑回写保留缩进与 marker",
      g and g[0] == "- 甲项\n  - 子项甲改\n  - 子项乙\n- 乙项",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("- 甲项\n- 乙项")
js("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
   "var li=lis[1];if(!li)return 'no';li.focus();"
   "var w=document.createTreeWalker(li,NodeFilter.SHOW_TEXT,null);var n=w.nextNode();"
   "if(!n)return 'no-text';var rg=document.createRange();rg.setStart(n,0);rg.setEnd(n,Math.min(2,n.nodeValue.length));"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
   "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
wait(320)
js("window.__applyFloat('bold')")
wait(520)
g = rawof()
check("F4 第 2 项加粗 → 标记落在选中项内（LIST-1 跨行回归）",
      g and g[0] == "- 甲项\n- **乙项**", "raw=%s" % json.dumps(g, ensure_ascii=False))

note("========== G 组：待办列表（checkbox） ==========")
setmd("- [ ] 待办甲\n- [ ] 待办乙")
s = lstate()
check("G1 待办渲染为 checkbox 且未勾选", s.get("ncb") == 2 and s.get("cbOn") == [False, False],
      "cb=%s on=%s" % (s.get("ncb"), json.dumps(s.get("cbOn"))))
js("(function(){var cb=document.querySelector('#editor li input[type=checkbox]');"
   "if(!cb)return 'no';cb.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(520)
g = rawof()
s = lstate()
check("G2 点击 checkbox → raw 变 [x] 且渲染勾选",
      g and g[0].startswith("- [x] 待办甲") and s.get("cbOn") == [True, False],
      "raw=%s on=%s" % (json.dumps(g, ensure_ascii=False), json.dumps(s.get("cbOn"))))
caret_li(0, -1)
type_li(0, "补")
g = rawof()
check("G3 待办项文字编辑 → [x] 状态保留",
      g and g[0] == "- [x] 待办甲补\n- [ ] 待办乙", "raw=%s" % json.dumps(g, ensure_ascii=False))
caret_li(1, -1)
key_li(1, "Enter", ms=520)
g = rawof()
check("G4 待办项回车 → 新项继承 [ ] 标记",
      g and g[0] == "- [x] 待办甲补\n- [ ] 待办乙\n- [ ] ",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
