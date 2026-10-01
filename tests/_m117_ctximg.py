# -*- coding: utf-8 -*-
"""m117：代码区右键菜单 + 图片/HR/SYN 批次验收（依据 docs/未落地功能点排查清单-v3.38.md）

A 组 代码区右键（CODE-10）：菜单项 / 复制代码（剥围栏保缩进）/ 删除块
B 组 图片：IMG-10 复制块 / IMG-11 边界置灰 / IMG-12 保存提示 / IMG-13 DEL 删图
C 组 分割线：HR-10 键盘选中 / HR-11 toast
D 组 图表：MMD-16 objbar 单钮 + blkmenu 补项 / MMD-14 格内图表弹层
E 组 双栏：SYN-2 预览禁编辑
结果：tests/_m117_ctximg.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m117_ctximg.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []

GIF = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"


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
js("window.setMarkdown('')")
wait(400)


def rawof():
    try:
        return (json.loads(js("window.__raw()") or "{}").get("raw")) or []
    except Exception:
        return []


def toasts():
    r = js("window.takeToast()")
    return [r] if r else []


def setmd(md, ms=820):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def ctxmenu(sel, ms=560):
    """对选中元素派发右键，返回 BM 菜单内容摘要"""
    js("(function(){var e=document.querySelector(" + json.dumps(sel) + ");"
       "if(!e)return 'no';"
       "e.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:200,clientY:200}));return 'ok'})()")
    wait(ms)
    return jj("(function(){var B=document.getElementById('blkmenu');"
              "return JSON.stringify({show:B.classList.contains('show'),"
              "cap:(B.querySelector('.cap')||{}).textContent||'',"
              "acts:[].slice.call(B.querySelectorAll('.mi')).map(function(m){return m.getAttribute('data-act')}),"
              "dis:[].slice.call(B.querySelectorAll('.mi.dis')).map(function(m){return m.getAttribute('data-act')})})})()")


def clickact(act, ms=620):
    js("(function(){var m=document.querySelector('#blkmenu .mi[data-act=\"" + act + "\"]');"
       "if(!m)return 'no';m.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def clickact_toast(act, ms=620):
    """点击菜单项并在同一 JS tick 内取 toast（避免被 700ms collect 轮询先取走）"""
    r = js("(function(){var m=document.querySelector('#blkmenu .mi[data-act=\"" + act + "\"]');"
           "if(!m)return 'no';m.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
           "return window.takeToast()||''})()")
    wait(ms)
    return r or ""


# ============ A 组：代码区右键 ============
note("========== A 组：代码区右键（CODE-10） ==========")
setmd("前段\n\n```python\nx = 1\n  y = 2\n```\n\n尾段")
s = ctxmenu("#editor .codeblock pre.fence code")
check("A1 代码区右键 → 菜单含 复制代码/复制（选区）/粘贴/删除块",
      s.get("cap") == "代码块" and
      s.get("acts") == ["codecpl", "codecpsel", "codepaste", "del"],
      "cap=%s acts=%s" % (s.get("cap"), s.get("acts")))
t2 = clickact_toast("codecpl")
check("A2 复制代码 → 复制路径执行（探针离屏环境允许剪贴板失败降级提示），raw 不变",
      ("复制" in t2) and len(rawof()) == 3,
      "toast=%s raw=%s" % (t2, json.dumps(rawof(), ensure_ascii=False)[:120]))
g = rawof()
check("A2b 围栏内缩进行原样保留", g and any("  y = 2" in ln for ln in g),
      "raw=%s" % json.dumps(g, ensure_ascii=False))
setmd("前段\n\n```python\nx = 1\n```\n\n尾段")
ctxmenu("#editor .codeblock pre.fence code")
t3 = clickact_toast("del")
g = rawof()
check("A3 删除块 → 代码块删除且 toast 可撤销",
      "已删除块" in t3 and not any("```" in ln for ln in g),
      "toast=%s raw=%s" % (t3, json.dumps(g, ensure_ascii=False)))

# ============ B 组：图片 ============
note("========== B 组：图片 IMG-10/11/12/13 ==========")
setmd("![" + "图" + "](" + GIF + ")\n\n段落甲")
s = ctxmenu("#editor img")
check("B1 图片右键菜单含「复制块」(dup)", "dup" in (s.get("acts") or []),
      "acts=%s" % s.get("acts"))
n0 = len(rawof())
clickact("dup")
g = rawof()
check("B2 点复制块 → 文档内多一份图片块", len(g) == n0 + 1,
      "n0=%d n1=%d" % (n0, len(g)))
setmd("![" + "图" + "](" + GIF + ")\n\n段落甲")
s = ctxmenu("#editor img")
check("B3 首块图片 → 「上移」置灰 (IMG-11)", "up" in (s.get("dis") or []),
      "dis=%s" % s.get("dis"))
setmd("段落甲\n\n![" + "图" + "](" + GIF + ")")
s = ctxmenu("#editor img")
check("B4 末块图片 → 「下移」置灰 (IMG-11)", "down" in (s.get("dis") or []),
      "dis=%s" % s.get("dis"))
setmd("![图](assets/pic.png)\n\n段落甲")
s = ctxmenu("#editor img")
check("B5 未保存文档 + 相对路径图 → 出现「转存本地（请先保存文档）」置灰条 (IMG-12)",
      "imgstorewait" in (s.get("acts") or []) and "imgstorewait" in (s.get("dis") or []),
      "acts=%s dis=%s" % (s.get("acts"), s.get("dis")))
t6 = clickact_toast("imgstorewait")
check("B6 点置灰条 → toast 说明原因（不静默）", "请先保存文档" in t6,
      "toast=%s" % t6)
setmd("段落甲\n\n![" + "图" + "](" + GIF + ")")
sel = jj("(function(){var img=document.querySelector('#editor img');"
         "img.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
         "img.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true}));"
         "return 'ok'})()")
wait(500)
st = jj("(function(){var ae=document.activeElement;"
        "return JSON.stringify({sel:!!document.querySelector('#editor img.sel'),"
        "inField:!!(ae&&(ae.tagName==='INPUT'||ae.tagName==='TEXTAREA'||ae.isContentEditable))})})()")
js("(function(){var e={key:'Delete',bubbles:true,cancelable:true};document.activeElement&&document.activeElement.dispatchEvent(new KeyboardEvent('keydown',e));document.dispatchEvent(new KeyboardEvent('keydown',e));return 'ok'})()")
wait(600)
g = rawof()
check("B7 选中图片后焦点已让出 → DEL 删除整块 (IMG-13)",
      st.get("sel") is True and st.get("inField") is False and len(g) == 1,
      "sel=%s inField=%s raw=%s" % (st.get("sel"), st.get("inField"), json.dumps(g, ensure_ascii=False)))

# ============ C 组：分割线 ============
note("========== C 组：分割线 HR-10/11 ==========")
setmd("段落甲\n\n---\n\n段落乙\n\n段落丙")
# 进入块 0 编辑态（mousedown → enterEdit），光标置末尾后按 ↓ 跨过分割线
js("(function(){var p=document.querySelectorAll('#editor .blk')[0].querySelector('p');"
   "p.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,clientX:8,clientY:8}));"
   "p.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,clientX:8,clientY:8}));return 'ok'})()")
wait(600)
js("(function(){var ed=document.querySelector('#editor .blk.raw-edit');"
   "var t=ed && (ed.querySelector('[contenteditable]')||ed);if(!t)return 'no';"
   "t.focus();var r=document.createRange();r.selectNodeContents(t);r.collapse(false);"
   "var s2=getSelection();s2.removeAllRanges();s2.addRange(r);"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(600)
st = jj("(function(){return JSON.stringify({hrsel:!!document.querySelector('#editor hr.hrsel')})})()")
check("C1 ↓ 跨过分割线 → 自动建立选中态 (HR-10)", st.get("hrsel") is True,
      "st=%s" % json.dumps(st))
js("(function(){var t=document.activeElement;"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}));return 'ok'})()")
wait(600)
g = rawof()
check("C2 选中态按 Delete → 分割线删除", not any(ln.strip() == '---' for ln in g),
      "raw=%s" % json.dumps(g, ensure_ascii=False))
setmd("段落甲\n\n---\n\n段落乙")
t9 = js("(function(){var hr=document.querySelector('#editor hr');"
        "hr.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
        "return window.takeToast()||''})()")
wait(400)
check("C3 点击选中 toast 含「Esc 取消」(HR-11)", "Esc 取消" in (t9 or ""),
      "toast=%s" % t9)

# ============ D 组：图表 MMD-16 / MMD-14 ============
note("========== D 组：图表 MMD-16 / MMD-14 ==========")
setmd("段落甲\n\n```mermaid\nflowchart TD\n A --> B\n```\n\n段落乙")
js("(function(){var mb=document.querySelector('#editor .mermaidblock');"
   "mb.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(500)
st = jj("(function(){var O=document.getElementById('objbar');"
        "return JSON.stringify({show:O.classList.contains('show'),"
        "btns:[].slice.call(O.querySelectorAll('button')).map(function(b){return b.textContent})})})()")
check("D1 图表 objbar 收缩为「源码」单钮 (MMD-16)",
      st.get("btns") == ["源码"], "st=%s" % json.dumps(st))
s = ctxmenu("#editor .mermaidblock")
check("D2 图表 blkmenu 含 图注/重置尺寸 (MMD-16)",
      "mmdcap" in (s.get("acts") or []) and "mmdreset" in (s.get("acts") or []),
      "acts=%s" % s.get("acts"))
setmd("段落甲\n\n<table><tr><td>格子</td></tr><tr><td>"
      '<span class="cell-mmd" data-src="flowchart TD\n X --> Y"></span>'
      "</td></tr></table>\n\n段落乙")
wait(1200)
js("(function(){var c=document.querySelector('#editor .cell-mmd');"
   "c.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(560)
st = jj("(function(){var P=document.getElementById('mmdcellpop');"
        "return JSON.stringify({show:P.classList.contains('show'),"
        "val:(document.getElementById('mmdcell-src')||{}).value||''})})()")
check("D3 双击格内图表 → 弹层编辑器带出源码 (MMD-14)",
      st.get("show") is True and "X --> Y" in str(st.get("val")),
      "st=%s" % json.dumps(st))
js("(function(){var t=document.getElementById('mmdcell-src');"
   "t.value='flowchart TD\\n M --> N';"
   "document.getElementById('mmdcell-ok').click();return 'ok'})()")
wait(900)
g = rawof()
check("D4 弹层确定 → raw 的 data-src 回写", any("M --&gt; N" in ln or "M --> N" in ln for ln in g),
      "raw=%s" % json.dumps(g, ensure_ascii=False)[:200])

# ============ E 组：双栏 SYN-2 ============
note("========== E 组：双栏预览 SYN-2 ==========")
js("window.setPreviewMode(true)")
wait(300)
js("window.setPreviewContent(" + json.dumps("# 标题\n\n段落文字") + ")")
wait(800)
st = jj("(function(){return JSON.stringify({ce:document.querySelectorAll('#editor [contenteditable]').length,"
        "blk:document.querySelectorAll('#editor .blk').length})})()")
check("E1 预览侧 contenteditable 全部剥离 (SYN-2)", st.get("ce") == 0 and st.get("blk") == 2,
      "st=%s" % json.dumps(st))
js("window.setPreviewMode(false)")
wait(300)
js("window.setMarkdown(" + json.dumps("# 标题\n\n段落文字") + ")")
wait(700)
st = jj("(function(){return JSON.stringify({ce:document.querySelectorAll('#editor [contenteditable]').length})})()")
check("E2 退出预览 → 编辑态恢复可编辑", (st.get("ce") or 0) > 0, "st=%s" % json.dumps(st))

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
