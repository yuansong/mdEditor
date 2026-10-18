# -*- coding: utf-8 -*-
"""m116：代码块模块 v3.38 修复验收（依据 docs/代码块模块交互规范-v3.37.md）

CODE-9  末块 Esc/Ctrl+Enter → 在其后新建空段落并进入（不再「假退出」）
CODE-10 顶栏 hover 显形「⧉ 复制」入口 + 语言栏 title 提示
CODE-11 >20 行长代码折叠 / 展开
CODE-12 顶栏「⛶」全屏编辑，Esc 退出
CODE-13 「风格」弹层自动换行开关（围栏 wrap=1）
新增    常见命令提示（按语言；空态命令条 / 顶栏「命令」弹层；无命令语言不显示）
结果：tests/_m116_code.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m116_code.txt")
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


def setmd(md, ms=820):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def cstate():
    return jj("(function(){var cb=document.querySelector('#editor .codeblock');"
              "if(!cb)return JSON.stringify({no:1});"
              "var pre=cb.querySelector('pre.fence'),code=pre?pre.querySelector('code'):null;"
              "return JSON.stringify({"
              "cls:cb.className,"
              "hasTri:!!cb.querySelector('.fold-tri'),"
              "hasCopy:!!cb.querySelector('.copy-btn'),"
              "copyTitle:(cb.querySelector('.copy-btn')||{}).title||'',"
              "langTitle:(cb.querySelector('.lang-btn')||{}).title||'',"
              "hasFs:!!cb.querySelector('.fs-btn'),"
              "hasCmd:!!cb.querySelector('.cmd-btn'),"
              "hasLnum:!!cb.querySelector('.lnum-btn'),"
              "hasWrap:!!cb.querySelector('.wrap-btn'),"
              "chips:[].slice.call(cb.querySelectorAll('.cmdbar .cmdc')).map(function(c){return c.textContent}),"
              "note:(cb.querySelector('.fold-note')||{}).textContent||'',"
              "noteShown:!!(cb.querySelector('.fold-note')&&getComputedStyle(cb.querySelector('.fold-note')).display!=='none'),"
              "txt:code?(code.textContent||'').slice(0,60):''})})()")


def click(sel, ms=520):
    js("(function(){var e=document.querySelector(" + json.dumps(sel) + ");"
       "if(!e)return 'no';"
       "e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def code_key(key, ctrl=False, ms=620):
    js("(function(){var c=document.querySelector('#editor .codeblock code');"
       "if(!c)return 'no';c.focus();"
       "c.dispatchEvent(new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,ctrlKey:" + ("true" if ctrl else "false") + "}));return 'ok'})()")
    wait(ms)


def setmd_pre(md):
    setmd(md)


# ============ A 组：CODE-9 末块退出 ============
note("========== A 组：CODE-9 末块 Esc / Ctrl+Enter ==========")
setmd("前段\n\n```python\nx = 1\n```")
g = rawof()
note("  初始块数=%d" % len(g))
code_key("Enter", ctrl=True)
g = rawof()
s = jj("JSON.stringify({editIdx:(JSON.parse(window.__raw()||'{}').editIdx)})")
check("A1 末块 Ctrl+Enter → 其后新建空段落（块数 +1，末块为空）",
      len(g) == 3 and g[2] == "", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("前段\n\n```python\nx = 1\n```")
code_key("Escape")
g = rawof()
check("A2 末块 Esc → 同样在其后新建空段落（不再「假退出」）",
      len(g) == 3 and g[2] == "", "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("```python\nx = 1\n```\n\n尾段")
code_key("Escape")
g = rawof()
s = jj("(function(){var d=JSON.parse(window.__raw()||'{}');return JSON.stringify({i:d.editIdx})})()")
# v3.38（WYS-4）：段落进入渲染态编辑白名单 → Esc 跳到下一块聚焦渲染态
# （editIdx=-1），不再切入源码态 —— 与「光标/键盘进入段落保持渲染态」一致
check("A3 非末块 Esc → 跳到下一块渲染态（WYS-4 后不切源码）",
      len(g) == 2 and str(s.get("i")) == "-1",
      "editIdx=%s raw=%s" % (s.get("i"), json.dumps(g, ensure_ascii=False)))

# ============ B 组：CODE-10 复制入口 ============
note("========== B 组：CODE-10 复制入口可见性 ==========")
setmd("```python\nx = 1\n```")
s = cstate()
check("B1 顶栏存在「⧉ 复制」按钮且 title 说明复制全部代码",
      s.get("hasCopy") and "复制" in str(s.get("copyTitle")),
      "hasCopy=%s title=%s" % (s.get("hasCopy"), s.get("copyTitle")))
check("B2 语言钮 title 提示「右键 = 复制全部代码」",
      "右键" in str(s.get("langTitle")) and "复制" in str(s.get("langTitle")),
      "title=%s" % s.get("langTitle"))

# ============ C 组：CODE-11 折叠 ============
note("========== C 组：CODE-11 长代码折叠 ==========")
long_md = "```python\n" + "\n".join("v%d = %d" % (i, i) for i in range(30)) + "\n```"
setmd(long_md)
s = cstate()
check("C1 30 行代码块 → 顶栏出现折叠三角",
      s.get("hasTri") is True, "hasTri=%s cls=%s" % (s.get("hasTri"), s.get("cls")))
click("#editor .codeblock .fold-tri")
s = cstate()
check("C2 点三角 → 折叠（.folded 且显示「N 行代码，点击展开」）",
      "folded" in str(s.get("cls")) and "行代码" in str(s.get("note")) and s.get("noteShown"),
      "cls=%s note=%s" % (s.get("cls"), s.get("note")))
click("#editor .codeblock .fold-tri")
s = cstate()
check("C3 再点 → 展开（去掉 .folded）",
      "folded" not in str(s.get("cls")), "cls=%s" % s.get("cls"))

setmd("```python\na = 1\nb = 2\n```")
s = cstate()
check("C4 短代码（3 行）不显示折叠三角",
      s.get("hasTri") is False, "hasTri=%s" % s.get("hasTri"))

# ============ D 组：CODE-14 自动换行（顶栏平级按钮） ============
note("========== D 组：CODE-14 自动换行顶栏按钮 ==========")
setmd("```python\nx = 1\n```")
s = cstate()
click("#editor .codeblock .style-btn")
pop = jj("(function(){var P=document.getElementById('stylepop');"
         "return JSON.stringify({show:P.classList.contains('show'),"
         "wr:[].slice.call(P.querySelectorAll('[data-wr]')).length,"
         "ln:[].slice.call(P.querySelectorAll('[data-ln]')).length,"
         "st:[].slice.call(P.querySelectorAll('[data-st]')).length})})()")
check("D1 风格弹层回归纯风格四项（无行号/换行项）",
      pop.get("show") and pop.get("wr") == 0 and pop.get("ln") == 0 and pop.get("st") == 4,
      "pop=%s" % json.dumps(pop, ensure_ascii=False))
click("#editor .codeblock .wrap-btn")
g = rawof()
s = cstate()
check("D2 点顶栏「换行」→ raw 首行写 wrap=1 且块加 .wrap-on",
      g and "wrap=1" in g[0] and "wrap-on" in str(s.get("cls")),
      "raw=%s cls=%s" % (json.dumps(g, ensure_ascii=False), s.get("cls")))
click("#editor .codeblock .wrap-btn")
g = rawof()
s = cstate()
check("D3 再点「换行」→ wrap=0 且去掉 .wrap-on",
      g and "wrap=0" in g[0] and "wrap-on" not in str(s.get("cls")),
      "raw=%s cls=%s" % (json.dumps(g, ensure_ascii=False), s.get("cls")))

# ============ E 组：CODE-12 全屏 ============
note("========== E 组：CODE-12 全屏编辑 ==========")
setmd("```python\nx = 1\n```")
s = cstate()
check("E1 顶栏存在「⛶」全屏按钮", s.get("hasFs") is True, "hasFs=%s" % s.get("hasFs"))
click("#editor .codeblock .fs-btn")
s = cstate()
check("E2 点击 → 进入全屏（.fs）", "fs" in str(s.get("cls")), "cls=%s" % s.get("cls"))
code_key("Escape")
s = cstate()
check("E3 全屏态 Esc → 退出全屏（不再误跳出块）",
      "fs" not in str(s.get("cls")), "cls=%s" % s.get("cls"))

# ============ F 组：命令项已移除（CODE-14） ============
note("========== F 组：命令入口已移除 ==========")
setmd("```python\n```")
s = cstate()
check("F1 空 python 块 → 不再铺命令 chips",
      not s.get("chips"), "chips=%s" % json.dumps(s.get("chips"), ensure_ascii=False))

setmd("```python\nprint(1)\n```")
s = cstate()
check("F2 顶栏无「命令」按钮",
      not s.get("hasCmd"), "hasCmd=%s" % s.get("hasCmd"))

setmd("```text\nhello\n```")
s = cstate()
check("F3 无收录命令的语言 → 同样无命令入口",
      not s.get("hasCmd") and not s.get("chips"),
      "hasCmd=%s chips=%s" % (s.get("hasCmd"), s.get("chips")))

# ============ H 组：CODE-14 行号顶栏平级按钮 ============
note("========== H 组：行号顶栏平级按钮 ==========")
setmd("```python\nx = 1\n```")
s = cstate()
check("H1 顶栏有「行号」「换行」平级按钮（lang-btn 同款）",
      s.get("hasLnum") is True and s.get("hasWrap") is True,
      "hasLnum=%s hasWrap=%s" % (s.get("hasLnum"), s.get("hasWrap")))
click("#editor .codeblock .lnum-btn")
g = rawof()
check("H2 点「行号」→ raw 首行写 lnum=0（默认开 → 关）",
      g and "lnum=0" in g[0], "raw=%s" % json.dumps(g, ensure_ascii=False))
click("#editor .codeblock .lnum-btn")
g = rawof()
check("H3 再点「行号」→ lnum=1",
      g and "lnum=1" in g[0], "raw=%s" % json.dumps(g, ensure_ascii=False))

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
