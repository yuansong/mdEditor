# -*- coding: utf-8 -*-
"""m131：v3.38 MMD-8 引用块内图表编辑路径（先实测取证，再修缺陷）
A组 渲染取证：引用内图表出图（.qblk / .mermaidblock）
B组 编辑入口：点击引用内图表 → 源码框出现 / 可输入
C组 回写取证：修改源码提交 → 引用结构是否保留（预期发现：整块被裸围栏替换）
D组 普通位置图表回归：同样路径下编辑回写正常（对照组）
"""
import os, sys, json, time

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication(sys.argv)
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m131.txt")
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

MMDSRC = "graph TD\n  A[开始] --> B[结束]"

QUOTE_MD = (
    "> 引用前置文字\n"
    ">\n"
    "> ```mermaid\n"
    "> %s\n"
    "> ```\n"
    ">\n"
    "> 引用后置文字\n" % MMDSRC.replace("\n", "\n> ")
)

PLAIN_MD = "普通段落文字\n\n```mermaid\n%s\n```\n\n收尾段落\n" % MMDSRC


def getmd():
    out = []
    lp = QEventLoop()

    def cb(r):
        out.append(r)
        lp.quit()

    win._js_active("window.getMarkdown()", cb)
    lp.exec()
    return out[0] if out else ""


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


def click_chart(sel):
    """对匹配 sel 的第一个 .mermaidblock 派发 mousedown（冒泡到 ED 处理器）。"""
    return js_page(
        "(function(){var m=document.querySelector('%s .mermaidblock')||"
        "document.querySelector('%s');if(!m)return 'NOCHART';"
        "var r=m.getBoundingClientRect();"
        "var ev=new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
        "clientX:r.left+Math.min(40,r.width/2),clientY:r.top+r.height/2,button:0});"
        "m.dispatchEvent(ev);return 'CLICKED';})()" % (sel, sel))


# ---------- A 渲染取证 ----------
setmd(QUOTE_MD)
info = js_page(
    "(function(){var q=document.querySelector('#editor blockquote');"
    "var m=document.querySelector('#editor .mermaidblock');"
    "var qb=document.querySelector('#editor .qblk');"
    "return JSON.stringify({hasQuote:!!q,hasChart:!!m,"
    "chartInQuote:!!(m&&q&&q.contains(m)),hasQblk:!!qb,"
    "qblkRaw:qb?(qb.getAttribute('data-raw')||'').slice(0,40):null,"
    "dataSrc:m?(m.getAttribute('data-src')||'').slice(0,20):null});})()")
d = json.loads(info) if isinstance(info, str) and info.startswith("{") else {}
check("A1 引用块渲染存在", d.get("hasQuote") is True, info)
check("A2 引用内图表已出图", d.get("chartInQuote") is True, info)
check("A3 图表 data-src 保留源码", str(d.get("dataSrc", "")).startswith("graph TD"),
      str(d.get("dataSrc")))

# ---------- B 编辑入口 ----------
r = click_chart("#editor blockquote")
wait(400)
opened = js_page(
    "(function(){var t=document.querySelector('#editor .mmd-src');"
    "return JSON.stringify({open:!!t,value:t?t.value.slice(0,30):null,"
    "inQuote:!!(t&&t.closest('blockquote'))});})()")
od = json.loads(opened) if isinstance(opened, str) and opened.startswith("{") else {}
check("B1 点击引用内图表 → 源码框出现", od.get("open") is True, opened)
check("B2 源码框初值 = 图表源码", str(od.get("value", "")).startswith("graph TD"), str(od.get("value")))
# 修改源码并提交（input 触发 450ms 防抖 commitMmdInput）
js_page(
    "(function(){var t=document.querySelector('#editor .mmd-src');if(!t)return;"
    "t.value='graph LR\\n  X-->Y';"
    "t.dispatchEvent(new Event('input',{bubbles:true}));return 1;})()")
wait(900)
# Escape 关闭（触发 closeMmdEditor 的统一渲染）
js_page(
    "(function(){var t=document.querySelector('#editor .mmd-src');if(!t)return 'NOTA';"
    "t.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
    "return 'ESC';})()")
wait(700)

# ---------- C 回写取证 ----------
md_after = getmd()
check("C1 图表源码已更新为 graph LR", "graph LR" in md_after, repr(md_after[:200]))
check("C2 引用前置文字未丢失", "引用前置文字" in md_after, "")
check("C3 引用后置文字未丢失", "引用后置文字" in md_after, "")
check("C4 引用前缀结构保留（仍存在 > 引用行）",
      any(ln.lstrip().startswith(">") for ln in md_after.split("\n")), "")

# ---------- D 对照组：普通位置图表 ----------
setmd(PLAIN_MD)
r = click_chart("#editor")
wait(400)
opened2 = js_page(
    "(function(){var t=document.querySelector('#editor .mmd-src');"
    "return JSON.stringify({open:!!t});})()")
check("D1 普通图表点击 → 源码框出现", opened2 == '{"open":true}', str(opened2))
js_page(
    "(function(){var t=document.querySelector('#editor .mmd-src');if(!t)return;"
    "t.value='graph TD\\n  P-->Q';"
    "t.dispatchEvent(new Event('input',{bubbles:true}));return 1;})()")
wait(900)
js_page(
    "(function(){var t=document.querySelector('#editor .mmd-src');if(!t)return;"
    "t.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
    "return 'ESC';})()")
wait(700)
md2 = getmd()
check("D2 普通图表回写正常（graph TD P-->Q）", "P-->Q" in md2 and "普通段落文字" in md2,
      repr(md2[:160]))

print("========== 汇总 ==========")
npass = sum(1 for st, _n, _d in _log if st == "PASS")
nfail = len(_log) - npass
print("PASS=%d FAIL=%d" % (npass, nfail))
with open(OUT, "w", encoding="utf-8") as f:
    for st, name, detail in _log:
        f.write("%s %s %s\n" % (st, name, detail))
    f.write("PASS=%d FAIL=%d\n" % (npass, nfail))
