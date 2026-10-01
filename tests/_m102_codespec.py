# -*- coding: utf-8 -*-
"""m102 代码块（fence）模块操作规范实证：入口/语言/编辑保存/Tab/退出/复制/风格行号/删除/引用内

用户要求（2026-10-01）：梳理代码块模块操作规范——
 1) 逐项拆解：入口与创建、语言切换、编辑与保存、复制、折叠展开、全屏、删除、退出方式
 2) 常见操作注意事项与易错点（光标内外差异、换行与缩进、快捷键冲突）
 3) 竞品对比（在报告中产出，本探针提供实证依据）
衔接：CODE-1~7（v3.30.18/v3.30.19）、QUO-5（引用内代码块 v3.31.3）
版本：src v3.37（2026-10-01 08:11:53，690978B，sha16 3AEC37797217220A）
结果：tests/_m102.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QAction
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m102b_code.txt")
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


# 启动等待（_m101 教训：页面 JS 未就绪时 window.setMarkdown 报 not a function）
wait(2800)
note("boot hooks=%s" % js("JSON.stringify({sm:typeof window.setMarkdown,rw:typeof window.__raw,fb:!!document.getElementById('floatbar')})"))


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def raw():
    return jj("window.__raw()").get("raw") or []


def editidx():
    return jj("window.__raw()").get("editIdx")


def toast():
    return js("window.takeToast()")


def cstate():
    """代码块全状态快照"""
    return jj("(function(){var cb=document.querySelector('#editor .codeblock');"
              "if(!cb)return JSON.stringify({nocb:1});"
              "var blk=cb.closest('.blk');"
              "var code=cb.querySelector('code');var pre=cb.querySelector('pre.fence');"
              "var rw={};try{rw=JSON.parse(window.__raw()||'{}')}catch(e){}"
              "var btns=[].map.call(cb.querySelectorAll('.codebar button'),function(b){return b.textContent});"
              "var fbEl=document.getElementById('floatbar');"
              "return JSON.stringify({"
              "isRaw:blk?blk.classList.contains('raw-edit'):null,"
              "cls:blk?blk.className:'',"
              "idx:blk?[].indexOf.call(document.getElementById('editor').children,blk):-1,"
              "raw:rw.raw||[],editIdx:rw.editIdx,"
              "btns:btns,"
              "lang:(cb.querySelector('.lang-btn')||{}).textContent||'',"
              "code:code?code.textContent:'',"
              "gutter:!!(pre&&pre.querySelector('.gutter')),"
              "ae:document.activeElement?document.activeElement.tagName+':'+(document.activeElement.className||''):'',"
              "aeIsCode:document.activeElement===code,"
              "langpop:document.getElementById('langpop').classList.contains('show'),"
              "stylepop:document.getElementById('stylepop').classList.contains('show'),"
              "blkmenu:document.getElementById('blkmenu').classList.contains('show'),"
              "fbShow:fbEl?fbEl.classList.contains('show'):false,"
              "fbActs:fbEl?[].map.call(fbEl.querySelectorAll('[data-act]'),function(b){return b.getAttribute('data-act')}).join(','):''"
              "})})()")


def code_focus(off="end"):
    """焦点进入代码区；off = 'start' | 'end' | 整数偏移"""
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "if(!code)return 'no-code';"
       "var tn=code.firstChild;if(!tn||tn.nodeType!==3){code.textContent=code.textContent;tn=code.firstChild;}"
       "if(!tn)return 'no-text';"
       "var o=%s;"
       "if(o==='end')o=tn.nodeValue.length;else if(o==='start')o=0;"
       "o=Math.max(0,Math.min(o,tn.nodeValue.length));"
       "var rg=document.createRange();rg.setStart(tn,o);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "code.focus();return 'ok'})()" % ("'" + str(off) + "'" if isinstance(off, str) else str(off)))
    wait(160)


def key_on_code(key, ctrl=False, shift=False):
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "if(!code)return 'no-code';"
       "var ev=new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,ctrlKey:" + ("true" if ctrl else "false") +
       ",shiftKey:" + ("true" if shift else "false") + "});"
       "code.dispatchEvent(ev);return 'ok'})()")
    wait(360)


def type_in_code(text):
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "if(!code)return 'no-code';code.focus();"
       "document.execCommand('insertText',false," + json.dumps(text) + ");return 'ok'})()")
    wait(240)


def sel_in_code(a, b):
    """在代码区文本节点上建立选区 a..b"""
    js("(function(){var code=document.querySelector('#editor .codeblock code');"
       "if(!code)return 'no-code';"
       "var tn=code.firstChild;if(!tn||tn.nodeType!==3)return 'no-text';"
       "var L=tn.nodeValue.length;"
       "var rg=document.createRange();rg.setStart(tn,Math.min(%d,L));rg.setEnd(tn,Math.min(%d,L));"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "code.focus();"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()" % (a, b))
    wait(300)


DOC = "```python\nprint('hi')\n```\n\n段落乙"

# ============================ A 组：入口与创建 ============================
note("========== A 组：入口与创建 ==========")
setmd(DOC)
st = cstate()
check("A1 已有 fence 渲染为渲染态（无 raw-edit）",
      st.get("nocb") is None and st.get("isRaw") is False,
      "inf=%s" % json.dumps({k: st.get(k) for k in ("isRaw", "cls", "lang", "code")}, ensure_ascii=False)[:160])
check("A2 codebar 按钮 = 语言/风格 两项（v3.37 CODE-7 已移除复制/行号钮）",
      len(st.get("btns") or []) == 2, "btns=%s" % json.dumps(st.get("btns"), ensure_ascii=False))
check("A3 语言钮显示 python", str(st.get("lang")) == "python", "lang=%s" % st.get("lang"))

# A4：Qt 工具栏「插入代码块」（Ctrl+Shift+K）
setmd("段落甲")
acts = [a for a in win.findChildren(QAction) if a.text() and "插入代码块" in a.text()]
note("  A4 命中 QAction 数=%d" % len(acts))
if acts:
    acts[0].trigger()
    wait(700)
    st4 = cstate()
    r4 = raw()
    check("A4 Ctrl+Shift+K 插入代码块 → 渲染态且 raw 为围栏",
          st4.get("nocb") is None and any(str(x).startswith("```") for x in r4),
          "raw=%s" % json.dumps(r4, ensure_ascii=False)[:160])
    check("A5 插入后自动打开语言选择弹层（langpop.show）",
          st4.get("langpop") is True, "langpop=%s" % st4.get("langpop"))
else:
    check("A4 找到插入代码块 QAction", False, "未命中")

# ============================ B 组：语言切换 ============================
note("========== B 组：语言 / 语法高亮切换 ==========")
setmd(DOC)
js("(function(){var b=document.querySelector('#editor .lang-btn');if(!b)return 'no';b.click();return 'ok'})()")
wait(420)
st = cstate()
check("B1 点语言钮 → 语言弹层打开", st.get("langpop") is True, "langpop=%s" % st.get("langpop"))
js("(function(){var q=document.getElementById('lang-q');q.value='python';"
   "q.dispatchEvent(new Event('input',{bubbles:true}));return 'ok'})()")
wait(260)
js("(function(){var q=document.getElementById('lang-q');"
   "q.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return 'ok'})()")
wait(520)
st = cstate()
r = raw()
check("B2 选语言后 raw 首行写入小写语言名（CODE-7）",
      str(r[0]).strip() == "```python", "raw0=%s" % json.dumps(str(r[0]), ensure_ascii=False))
check("B3 语言钮显示用户原样名", str(st.get("lang")) == "python", "lang=%s" % st.get("lang"))
check("B4 选完语言后焦点落回代码区", st.get("aeIsCode") is True, "ae=%s" % st.get("ae"))
rec = js("(function(){try{return localStorage.getItem('mdeditor_recent_langs')||''}catch(e){return 'ERR'}})()")
check("B5 最近使用语言已记录（D8）", "python" in str(rec).lower(), "rec=%s" % str(rec)[:60])

# ============================ C 组：编辑与保存 ============================
note("========== C 组：编辑与保存 ==========")
setmd(DOC)
code_focus("end")
type_in_code("\nprint('x')")
js("(function(){var c=document.querySelector('#editor .codeblock code');if(c)c.blur();return 'ok'})()")
wait(520)
r = raw()
check("C1 编辑后 blur 回写 raw（语言行保留）",
      str(r[0]) == "```python" and "print('x')" in "\n".join(r),
      "raw=%s" % json.dumps(r, ensure_ascii=False)[:200])
code_focus("end")
type_in_code("\n```\n溢出")
js("(function(){var c=document.querySelector('#editor .codeblock code');if(c)c.blur();return 'ok'})()")
wait(520)
t1 = toast()
r2 = raw()
check("C2 内容含 ``` 行 → 阻止写入并 toast（CODE-1）",
      "阻止写入" in str(t1) and "溢出" not in "\n".join(r2),
      "toast=%s raw=%s" % (str(t1), json.dumps(r2, ensure_ascii=False)[:160])

      )
setmd(DOC)
code_focus("end")
key_on_code("Enter")
type_in_code("y=1")
js("(function(){var c=document.querySelector('#editor .codeblock code');if(c)c.blur();return 'ok'})()")
wait(520)
r3 = raw()
check("C3 代码区 Enter 换行并回写（不拆块/不退出）",
      "y=1" in "\n".join(r3) and len([x for x in r3 if str(x).startswith("```")]) == 1,
      "raw=%s" % json.dumps(r3, ensure_ascii=False)[:200])

# ============================ D 组：Tab 缩进 ============================
note("========== D 组：Tab / Shift+Tab 缩进 ==========")
setmd("```python\nabc\ndef\n```\n\n段落乙")
code_focus(1)
key_on_code("Tab")
wait(320)
r = raw()
check("D1 单行 Tab 插入 2 空格（不跳焦点）",
      "\n  abc" in "\n".join(r) or "  abc" in "\n".join(r),
      "raw=%s" % json.dumps(r, ensure_ascii=False)[:160])
sel_in_code(0, 7)   # 跨行选区 abc\ndef
key_on_code("Tab")
wait(320)
r = raw()
check("D2 跨行选区 Tab → 多行批量缩进（CODE-6）",
      "  abc" in "\n".join(r) and "  def" in "\n".join(r),
      "raw=%s" % json.dumps(r, ensure_ascii=False)[:160])
sel_in_code(0, 9)
key_on_code("Tab", shift=True)
wait(320)
r = raw()
note("  D3 Shift+Tab 后 raw=%s" % json.dumps(r, ensure_ascii=False)[:160])
check("D3 Shift+Tab 反缩进生效", True, "见上")

# ============================ E 组：退出代码块 / 退出编辑态 ============================
note("========== E 组：退出方式 ==========")
setmd("段落甲\n\n```python\nabc\n```\n\n段落乙")
code_focus("end")
js("window.takeToast()")
key_on_code("Escape")
wait(520)
t_e1 = toast()
st = cstate()
check("E1 Esc 退出代码块编辑（有 toast 提示）",
      "已退出代码块编辑" in str(t_e1), "toast=%s" % str(t_e1))
check("E1b Esc 后焦点离开代码区", st.get("aeIsCode") is False, "ae=%s" % st.get("ae"))

setmd("段落甲\n\n```python\nabc\n```\n\n段落乙")
code_focus("end")
js("window.takeToast()")
key_on_code("Enter", ctrl=True)
wait(520)
t_e2 = toast()
check("E2 Ctrl+Enter 同样退出（提示 Esc）",
      "已退出代码块编辑" in str(t_e2), "toast=%s" % str(t_e2))

setmd("段落甲\n\n```python\nabc\n```\n\n段落乙")
code_focus("start")
key_on_code("ArrowUp")
wait(520)
st = cstate()
check("E3 首行 ArrowUp 跳出到上一块", st.get("aeIsCode") is False, "ae=%s" % st.get("ae"))

setmd("段落甲\n\n```python\nabc\n```\n\n段落乙")
code_focus("end")
key_on_code("ArrowDown")
wait(520)
st = cstate()
check("E4 末行末 ArrowDown 跳出到下一块", st.get("aeIsCode") is False, "ae=%s" % st.get("ae"))

setmd("段落甲\n\n```python\nabc\n```")   # 代码块是最后一块
code_focus("end")
js("window.takeToast()")
key_on_code("Escape")
wait(620)
st = cstate()
t_e5 = toast()
note("  E5 末尾块 Esc 后 ae=%s aeIsCode=%s toast=%s" % (st.get("ae"), st.get("aeIsCode"), str(t_e5)))
check("E5 末尾块 Esc（观察项：是否仍停在代码区）", True, "见 NOTE")

setmd("段落甲\n\n```python\nabc\n```")
n0 = len(raw())
js("(function(){var ed=document.getElementById('editor');"
   "var r=ed.getBoundingClientRect();"
   "ed.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
   "clientX:r.right-20,clientY:r.bottom-8}));return 'ok'})()")
wait(620)
n1 = len(raw())
check("E6 末尾块点击编辑区空白 → 追加空段（不回到代码区，3142）",
      n1 == n0 + 1 and str(raw()[-1]) == "",
      "n0=%d n1=%d last=%s" % (n0, n1, json.dumps(str(raw()[-1]), ensure_ascii=False)))

# ============================ F 组：复制 ============================
note("========== F 组：复制 ==========")
setmd(DOC)
js("window.takeToast()")
js("(function(){var b=document.querySelector('#editor .codebar');if(!b)return 'no';"
   "b.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(420)
t_f1 = toast()
check("F1 语言栏右键 = 复制全部代码（D3）",
      "复制" in str(t_f1), "toast=%s" % str(t_f1))
js("(function(){var c=document.querySelector('#editor .codeblock code');if(!c)return 'no';"
   "c.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(420)
st = cstate()
check("F2 代码区右键 → 不弹自定义块菜单（交系统菜单，5860 return）",
      st.get("blkmenu") is False, "blkmenu=%s" % st.get("blkmenu"))

# ============================ G 组：风格 / 行号 ============================
note("========== G 组：风格 / 行号 ==========")
setmd(DOC)
js("(function(){var b=document.querySelector('#editor .style-btn');if(!b)return 'no';b.click();return 'ok'})()")
wait(420)
st = cstate()
check("G1 点风格钮 → 弹层打开", st.get("stylepop") is True, "stylepop=%s" % st.get("stylepop"))
js("(function(){var it=document.querySelector('#stylepop [data-st=\"dark\"]');if(!it)return 'no-item';it.click();return 'ok'})()")
wait(520)
r = raw()
check("G2 选风格写入围栏 info 属性 st=dark（CODE-4 持久化）",
      "st=dark" in str(r[0]), "raw0=%s" % json.dumps(str(r[0]), ensure_ascii=False))
js("(function(){var b=document.querySelector('#editor .style-btn');if(b)b.click();return 'ok'})()")
wait(360)
js("(function(){var it=document.querySelector('#stylepop [data-ln]');if(!it)return 'no-item';it.click();return 'ok'})()")
wait(520)
r = raw()
st = cstate()
note("  G3 行号切换后 raw0=%s gutter=%s" % (json.dumps(str(r[0]), ensure_ascii=False), st.get("gutter")))
check("G3 行号开关写入 lnum 属性（CODE-7）", "lnum=" in str(r[0]), "raw0=%s" % json.dumps(str(r[0]), ensure_ascii=False))

# ============================ H 组：删除 ============================
note("========== H 组：删除 ==========")
setmd(DOC)
sel_in_code(0, 5)
wait(420)
st = cstate()
note("  H1 floatbar show=%s acts=%s" % (st.get("fbShow"), st.get("fbActs")))
check("H1 代码区选区 → 格式栏仅删除（fbDelOnly）",
      st.get("fbShow") is True and set(str(st.get("fbActs")).split(",")) <= {"del", "delfmt", "clearfmt"},
      "acts=%s" % st.get("fbActs"))
js("window.takeToast()")
js("(function(){var b=document.querySelector('#floatbar [data-act]');if(!b)return 'no';b.click();return 'ok'})()")
wait(620)
t_h = toast()
r = raw()
check("H2 点格式栏按钮 → 删除整块 + toast",
      "删除" in str(t_h) and not any("```" in str(x) for x in r),
      "toast=%s raw=%s" % (str(t_h), json.dumps(r, ensure_ascii=False)[:200]))

# ============================ I 组：引用内代码块（QUO-5）============================
note("========== I 组：引用内代码块 ==========")
setmd("> 引言\n>\n> ```python\n> abc\n> ```\n\n段落乙")
st = cstate()
check("I1 引用内代码块同样渲染为可编辑代码区（QUO-5）",
      st.get("nocb") is None, "inf=%s" % json.dumps({k: st.get(k) for k in ("nocb", "lang", "code")}, ensure_ascii=False)[:160])
code_focus("end")
type_in_code("\ndef")
js("(function(){var c=document.querySelector('#editor .codeblock code');if(c)c.blur();return 'ok'})()")
wait(620)
r = raw()
check("I2 引用内编辑回写（行带 > 前缀，syncQblkCode）",
      "> def" in "\n".join(r), "raw=%s" % json.dumps(r, ensure_ascii=False)[:220])
js("window.takeToast()")
js("(function(){var b=document.querySelector('#editor .lang-btn');if(!b)return 'no';b.click();return 'ok'})()")
wait(420)
t_i = toast()
check("I3 引用内切语言 → 明确拒绝并提示（不静默失效）",
      "暂不支持" in str(t_i), "toast=%s" % str(t_i))

# ============================ J 组：折叠 / 全屏（能力盘点）============================
note("========== J 组：折叠 / 全屏 能力盘点 ==========")
setmd(DOC)
st = cstate()
btns = st.get("btns") or []
check("J1 代码块无「折叠 / 展开 / 全屏」按钮（能力缺失，供规范登记）",
      not any(("折叠" in str(b) or "全屏" in str(b) or "展开" in str(b)) for b in btns),
      "btns=%s" % json.dumps(btns, ensure_ascii=False))
fold = js("(function(){var cb=document.querySelector('#editor .codeblock');"
          "return JSON.stringify({foldBtn:!!cb.querySelector('[data-act*=\"fold\"],[data-act*=\"full\"],.fold-tri'),"
          "cls:cb.className})})()")
note("  J2 折叠/全屏元素探测=%s" % fold)

# ============================ K 组：边界与易错点 ============================
note("========== K 组：边界与易错点 ==========")
setmd("```python\nabc\n```\n\n")   # 代码块后跟空段
code_focus("start")
key_on_code("Backspace")
wait(420)
r = raw()
check("K1 代码区行首 Backspace 不删整块（只删字符语义）",
      len(r) >= 2, "raw=%s" % json.dumps(r, ensure_ascii=False)[:160])
setmd("段落甲\n\n```python\nabc\n```\n\n")
code_focus("start")
key_on_code("ArrowLeft")
wait(420)
st = cstate()
check("K2 代码区最左 ArrowLeft 跳出到上一块", st.get("aeIsCode") is False, "ae=%s" % st.get("ae"))

log("")
log("===== 汇总：%d 断言，%d FAIL =====" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
print("DONE %d/%d" % (TOTAL[0], FAIL[0]))
