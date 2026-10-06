# -*- coding: utf-8 -*-
"""m123：v3.38 ALIGN-1 —— 居中标题（tagForm）与块转换 / 回写的交互验收

用户报告：标题 3 居中对齐后切换为标题 1，界面显示 HTML 源码。
断言围绕「任何路径下渲染区都不得出现 <h…> / align= 这类原始标签」。
"""
import json, os, sys

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, "E:/WorkBuddy/md-editor/src")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication(sys.argv)
from mainwindow import MainWindow

win = MainWindow()
win.show()

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m123.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))


def js(code, t=15000):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(t, loop.quit); win._js_active(code, cb); loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def getmd():
    return js("window.getMarkdown()") or ""


def shown():
    v = js("(function(){var b=document.querySelector('#editor .blk');"
           "return b?JSON.stringify(b.textContent):''})()")
    try:
        return json.loads(v)
    except Exception:
        return v


def html_of():
    v = js("(function(){var b=document.querySelector('#editor .blk');"
           "return b?JSON.stringify(b.innerHTML.slice(0,160)):''})()")
    try:
        return json.loads(v)
    except Exception:
        return v


def sel_heading():
    return js("(function(){var h=document.querySelector('#editor h1,#editor h2,#editor h3,"
              "#editor h4,#editor h5,#editor h6');if(!h)return 'noh';"
              "var w=document.createTreeWalker(h,NodeFilter.SHOW_TEXT,null);var ns=[],n,t=0;"
              "while((n=w.nextNode())){ns.push([n,t]);t+=n.nodeValue.length;}"
              "if(!ns.length)return 'notext';"
              "var f=ns[0],l=ns[ns.length-1];"
              "var rg=document.createRange();rg.setStart(f[0],0);rg.setEnd(l[0],l[0].nodeValue.length);"
              "var s=getSelection();s.removeAllRanges();s.addRange(rg);"
              "return JSON.stringify(rg.toString())})()")


def center():
    sel_heading()
    js("window.__applyFloat('h1center')")
    wait(400)


def to(act):
    js("window.__blkAct('to:%s', 0)" % act)
    wait(400)


TXT = "我是一个好人"
NO_TAG = lambda t: ("<h" not in t) and ("align=" not in t) and ("</h" not in t)

wait(2800)

# ---------- A1 用户路径：h3 → 居中 → 切 h1 ----------
js("window.setMarkdown(" + json.dumps("### " + TXT) + ")")
wait(700)
center()
raw_c = getmd().strip()
check("A1 h3 居中 → 存为 <h3 align=center> 形态",
      raw_c == '<h3 align="center">%s</h3>' % TXT, "raw=%s" % raw_c)
check("A1 h3 居中后渲染无标签残留", NO_TAG(shown()), "shown=%s" % shown())

to("h1")
raw_h1 = getmd().strip()
check("A2 居中 h3 切 h1 → 纯 `# 文本`（无 HTML 外壳）",
      raw_h1 == "# " + TXT, "raw=%s" % raw_h1)
check("A2 切 h1 后渲染区无 HTML 源码（用户报告的核心缺陷）",
      NO_TAG(shown()) and shown() == TXT, "shown=%s" % shown())
check("A2 切 h1 后是 h1 元素且无 align 残留",
      "<h1" in html_of() and "align=" not in html_of(), "html=%s" % html_of())

# ---------- A3 h1 居中 → 切 h3 ----------
js("window.setMarkdown(" + json.dumps("# " + TXT) + ")")
wait(700)
center()
check("A3 h1 居中 → <h1 align=center>", getmd().strip() == '<h1 align="center">%s</h1>' % TXT,
      "raw=%s" % getmd())
to("h3")
check("A3 居中 h1 切 h3 → 纯 `### 文本`", getmd().strip() == "### " + TXT, "raw=%s" % getmd())
check("A3 渲染无标签残留", NO_TAG(shown()), "shown=%s" % shown())

# ---------- B 居中块转为其它块类型 ----------
for act, expect_prefix in (("p", ""), ("quote", "> "), ("ul", "- "), ("h2", "## ")):
    js("window.setMarkdown(" + json.dumps('<h1 align="center">%s</h1>' % TXT) + ")")
    wait(500)
    to(act)
    r = getmd().strip()
    check("B 居中 h1 → %s 无标签残留（%s）" % (act, expect_prefix or "纯文本"),
          NO_TAG(r) and r.startswith(expect_prefix) and r.endswith(TXT), "raw=%s" % r)
    check("B 居中 h1 → %s 渲染无标签残留" % act, NO_TAG(shown()), "shown=%s" % shown())

# ---------- C 居中态编辑回写：级别不被抬成 h1 ----------
js("window.setMarkdown(" + json.dumps('<h3 align="center">%s</h3>' % TXT) + ")")
wait(700)
js("(function(){var h=document.querySelector('#editor h3');if(!h)return 'noh';"
   "var w=document.createTreeWalker(h,NodeFilter.SHOW_TEXT,null);var n=w.nextNode();"
   "if(!n)return 'notext';var rg=document.createRange();"
   "rg.setStart(n,n.nodeValue.length);rg.collapse(true);"
   "var s=getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
js("(function(){var h=document.querySelector('#editor h3');"
   "h.focus&&h.focus();return 'ok'})()")
wait(300)
# 末尾追加一个字再失焦触发 syncHeadingEl
js("(function(){var h=document.querySelector('#editor h3');"
   "var w=document.createTreeWalker(h,NodeFilter.SHOW_TEXT,null);var n=w.nextNode();"
   "if(n){n.nodeValue=n.nodeValue+'呀';}"
   "var ev=document.createEvent('Event');ev.initEvent('input',true,true);h.dispatchEvent(ev);"
   "return 'ok'})()")
wait(300)
js("(function(){var b=document.querySelectorAll('#editor .blk')[0];"
   "if(b&&b.blur)b.blur();return 'ok'})()")
wait(500)
raw_w = getmd().strip()
check("C h3 居中态编辑回写仍为 h3（不被抬成 h1）",
      raw_w.startswith("<h3") or raw_w.startswith("###"),
      "raw=%s" % raw_w)

# ---------- D 悬浮栏：h2~h6 也有居中入口 ----------
for lv in (1, 2, 3, 4):
    js("window.setMarkdown(" + json.dumps("#" * lv + " " + TXT) + ")")
    wait(600)
    sel_heading()
    wait(500)
    # 悬浮栏按钮无 data-act，按 title（标题居中 / 标题向左对齐）判定
    has = js("(function(){var b=document.querySelector('#floatbar');"
             "if(!b)return 'nofb';"
             "var r=false;b.querySelectorAll('button').forEach(function(e){"
             "var t=e.title||'';if(t.indexOf('居中')>=0||t.indexOf('向左')>=0)r=true;});"
             "return String(r)})()")
    check("D h%d 标题出现居中按钮" % lv, str(has).lower() == "true", "has=%s" % has)

# ---------- E 往返：居中 → 向左 → 居中 ----------
js("window.setMarkdown(" + json.dumps("### " + TXT) + ")")
wait(600)
center()
check("E1 居中", getmd().strip().startswith("<h3"), "raw=%s" % getmd())
center()
check("E2 再点回到原生 ### 形态",
      getmd().strip() == "### " + TXT, "raw=%s" % getmd())
check("E2 渲染无标签残留", NO_TAG(shown()), "shown=%s" % shown())

with open(OUT, "w", encoding="utf-8") as f:
    for st, name, detail in _log:
        f.write("%s %s%s\n" % (st, name, (" | " + detail) if detail and st == "FAIL" else ""))
print("done")
