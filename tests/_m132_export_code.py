# -*- coding: utf-8 -*-
"""m132：v3.38 CODE-8 导出 HTML 代码着色 + MMD-8 补验（引用内图表 DEL 删除）
A组 CODE-8：getExportHTML 中代码块带 hlCodeHTML 着色 span（普通 + 引用内 + 无语言）
B组 MMD-8 DEL：引用内图表选中按 DEL → 只删围栏行、引用文字保留
"""
import os, sys, json, time

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication(sys.argv)
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m132.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  | " + str(detail)))


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


win = MainWindow()
win.show()
wait(2600)


def js_page(code):
    out = []
    lp = QEventLoop()

    def cb(r):
        out.append(r)
        lp.quit()

    win._js_active(code, cb)
    lp.exec()
    return out[0] if out else None


def setmd(text):
    win._js_active("window.setMarkdown(%s)" % json.dumps(text))
    wait(600)


# ---------- A CODE-8 导出着色 ----------
MD_A = ("# 演示\n\n```python\n"
        "def hello():\n"
        "    print('hi')  # 注释\n"
        "```\n\n```mermaid\ngraph TD\nA-->B\n```\n\n```\n无语言代码\n```\n\n"
        "> 引用内代码：\n>\n> ```js\n> var x = 1;\n> ```\n")
setmd(MD_A)
# flushLazyAll 由 getExportHTML 自身触发；取导出 HTML 分析代码块
html = js_page("window.getExportHTML()")
# python 块应含着色 span（着色后连续文本被 span 拆开，需按块检查而非子串）
has_span = js_page(
    "(function(){var h=" + json.dumps(html) + ";"
    "var p1=h.indexOf('<pre');"
    "var segPy=h.slice(p1, h.indexOf('</pre>', p1));"
    "var x1=h.indexOf('var x');"
    "var segJs=h.slice(x1-400, x1+300);"
    "return JSON.stringify({pySpan:segPy.indexOf('<span')>=0,"
    "pyHasDef:segPy.indexOf('def')>=0,"
    "jsSeg:segJs.indexOf('<span')>=0,"
    "langPlain:h.indexOf('无语言代码')>=0});})()")
d = json.loads(has_span) if isinstance(has_span, str) and has_span.startswith("{") else {}
check("A1 python 块导出带着色 span", d.get("pySpan") is True and d.get("pyHasDef") is True,
      str(d))
check("A2 引用内 js 块导出带着色 span", d.get("jsSeg") is True, str(d))
check("A3 无语言块导出保留原文", d.get("langPlain") is True, str(d))
check("A4 导出物中 mermaid 不着色（占位由 SVG 填充）",
      html is not None and "<svg" in (html or ""), "")

# ---------- B MMD-8 引用内图表 DEL 删除 ----------
MD_B = ("> 引用前置文字\n>\n> ```mermaid\n> graph TD\n>   A-->B\n> ```\n>\n"
        "> 引用后置文字\n")
setmd(MD_B)
js_page(
    "(function(){var m=document.querySelector('#editor blockquote .mermaidblock');"
    "if(!m)return 'NOCHART';"
    "var r=m.getBoundingClientRect();"
    "m.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
    "clientX:r.left+20,clientY:r.top+10,button:0}));return 1;})()")
wait(400)
# 源码框出现（focus:false，DEL 可删除整个图表）
opened = js_page("(function(){return JSON.stringify({t:!!document.querySelector('#editor .mmd-src')});})()")
check("B1 图表选中（源码框出现）", opened == '{"t":true}', str(opened))
# 模拟 DEL 键：查 DELETE 处理是否走 deleteMmdBlock —— 通过键盘事件派发到 document
js_page(
    "(function(){document.dispatchEvent(new KeyboardEvent('keydown',"
    "{key:'Delete',bubbles:true,cancelable:true}));return 1;})()")
wait(700)
md_b = js_page("window.getMarkdown()")
check("B2 DEL 后图表行已删除", "mermaid" not in (md_b or ""), repr((md_b or "")[:120]))
check("B3 引用前置文字保留", "引用前置文字" in (md_b or ""), "")
check("B4 引用后置文字保留", "引用后置文字" in (md_b or ""), "")

print("========== 汇总 ==========")
npass = sum(1 for st, _n, _d in _log if st == "PASS")
nfail = len(_log) - npass
print("PASS=%d FAIL=%d" % (npass, nfail))
with open(OUT, "w", encoding="utf-8") as f:
    for st, name, detail in _log:
        f.write("%s %s %s\n" % (st, name, detail))
    f.write("PASS=%d FAIL=%d\n" % (npass, nfail))
