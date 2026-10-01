# -*- coding: utf-8 -*-
"""m98b 复验：甄别 _m98 的 9 个 FAIL（探针伪影 vs 真缺陷）
- A5 引用块 / A10+C1 代码块：dump 选择器命中与浮条原始返回
- B2/B3/B4/B5/B6：按整块 raw 取数据（_m98 行过滤把含「表头」的整表 raw 滤掉 = 伪影）
版本：src v3.37（2026-10-01 07:02:55，683822B，sha16 C0D0D0DA8661B2CF）
结果：tests/_m98b.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m98b.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []
URL = "https://ex.com/doc"


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


def setmd(md, ms=750):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    r = jj("window.__raw()")
    return r.get("raw", []) if isinstance(r, dict) else []


def fb_state():
    return jj("(function(){var fb=document.getElementById('floatbar');"
              "if(!fb)return JSON.stringify({show:false,err:'no-fb'});"
              "if(!fb.classList.contains('show'))return JSON.stringify({show:false});"
              "var ts=[].map.call(fb.querySelectorAll('button'),function(b){return b.title});"
              "var cnt=fb.querySelector('.fbcnt');"
              "return JSON.stringify({show:true,btns:ts,tail:cnt?cnt.textContent:''})})()")


def sel_diag(selector, idx, a, b, ms=280):
    """选区构造 + 诊断：命中数 / sel_nth 返回值 / 选区文本"""
    r = js("(function(){var els=document.querySelectorAll(" + json.dumps(selector) + ");"
           "if(els.length<=" + str(idx) + ")return JSON.stringify({hit:els.length,err:'no-el'});"
           "var el=els[" + str(idx) + "];"
           "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);"
           "var pos=0,sn=null,so=0,en=null,eo=0,n;"
           "while(n=w.nextNode()){var L=n.nodeValue.length;"
           "if(sn===null&&pos+L>=" + str(a) + "){sn=n;so=" + str(a) + "-pos;}"
           "if(pos+L>=" + str(b) + "){en=n;eo=" + str(b) + "-pos;break;}"
           "pos+=L;}"
           "if(!sn||!en)return JSON.stringify({hit:els.length,err:'no-range',txt:el.textContent});"
           "var rg=document.createRange();rg.setStart(sn,so);rg.setEnd(en,eo);"
           "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
           "document.dispatchEvent(new Event('selectionchange'));"
           "return JSON.stringify({hit:els.length,sel:s.toString(),txt:el.textContent})})()")
    wait(ms)
    return jj(json.dumps(r)) if isinstance(r, str) and r.startswith("{") else r


def apply_act(action, ms=340):
    if action == "link":
        js("window.__applyFloat('link')")
        wait(ms)
        js("(function(){var i=document.getElementById('link-url');"
           "if(!i)return 'no-input';i.value=" + json.dumps(URL) + ";"
           "var b=document.getElementById('link-ok');"
           "if(!b)return 'no-btn';b.click();return 'ok'})()")
        wait(ms + 140)
        return
    js("window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


FULL = ["粗体", "斜体", "下划线", "删除线", "高亮", "行内代码", "链接", "清除格式"]

note("========== R1 引用块甄别 ==========")
setmd("> 引用内文字")
d = sel_diag("#editor blockquote p", 0, 0, 4)
note("  R1 sel=%s" % json.dumps(d, ensure_ascii=False))
st = fb_state()
note("  R1 fb=%s" % json.dumps(st, ensure_ascii=False))
d2 = sel_diag("#editor blockquote", 0, 0, 4)
note("  R1b blockquote 整体 sel=%s" % json.dumps(d2, ensure_ascii=False))
st2 = fb_state()
note("  R1b fb=%s" % json.dumps(st2, ensure_ascii=False))
if st2.get("show"):
    check("R1 引用块浮条全套", all(x in st2.get("btns", []) for x in FULL), str(st2.get("btns")))

note("========== R2 代码块甄别 ==========")
setmd("```python\nprint('hello')\n```")
d = sel_diag("#editor .codeblock code", 0, 0, 5)
note("  R2 sel=%s" % json.dumps(d, ensure_ascii=False))
st = fb_state()
note("  R2 fb=%s" % json.dumps(st, ensure_ascii=False))
d2 = sel_diag("#editor .codeblock", 0, 0, 5)
note("  R2b .codeblock 整体 sel=%s" % json.dumps(d2, ensure_ascii=False))
st2 = fb_state()
note("  R2b fb=%s" % json.dumps(st2, ensure_ascii=False))
if st2.get("show"):
    check("R2 代码块浮条仅删除", st2.get("btns") == ["删除整个块"], str(st2.get("btns")))
    apply_act("delblk")
    raw = getraw()
    check("R2 delblk 生效", all("print" not in r for r in raw), json.dumps(raw, ensure_ascii=False)[:120])

note("========== R3 单元格组复验（整块 raw 取数） ==========")

note("R3a toggle 取消（已加粗再点粗体）")
setmd("| 表头 |\n| --- |\n| **甲**乙 |")
sel_diag("#editor td", 0, 0, 1)
apply_act("bold")
raw = getraw()
blk = next((r for r in raw if "甲" in r), "")
check("R3a 取消加粗回裸文字", blk != "" and "**" not in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("R3b 管道码内加粗（FMT-1 单元格路径守卫缺失？）")
setmd("| 表头 |\n| --- |\n| 前`码甲`后 |")
d = sel_diag("#editor td", 0, 1, 3)
note("  R3b sel=%s" % json.dumps(d, ensure_ascii=False))
apply_act("bold")
raw = getraw()
blk = next((r for r in raw if "码甲" in r), "")
note("  R3b blk=%s" % json.dumps(blk, ensure_ascii=False))
if blk:
    leaked = ("`**" in blk) or ("**`" in blk)
    check("R3b 码内加粗拒绝（与正文 FMT-1 一致）", not leaked,
          "码内包 **：%s" % json.dumps(blk, ensure_ascii=False))

note("R3c 管道单元格下划线（FMT-12）")
setmd("| 表头 |\n| --- |\n| 甲乙 |")
sel_diag("#editor td", 0, 0, 2)
apply_act("underline")
raw = getraw()
blk = next((r for r in raw if "甲" in r), "")
check("R3c 下划线走 <u>", blk != "" and "<u>甲乙</u>" in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("R3d 单元格清除格式")
setmd("| 表头 |\n| --- |\n| **甲**和*乙* |")
sel_diag("#editor td", 0, 0, 1)
apply_act("clearfmt")
raw = getraw()
blk = next((r for r in raw if "甲" in r), "")
check("R3d 清除选中处加粗（乙斜体保留）", blk.endswith("| 甲和*乙* |"),
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("R3e 单元格链接")
setmd("| 表头 |\n| --- |\n| 甲乙 |")
sel_diag("#editor td", 0, 0, 2)
apply_act("link")
raw = getraw()
blk = next((r for r in raw if "甲" in r), "")
check("R3e 链接写入", blk != "" and URL in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("R3f HTML 表重复文字首现错位（B1 缺陷的 HTML 表对照）")
setmd('<table><tr><th>名称</th></tr><tr><td>甲乙甲乙</td></tr></table>')
d = sel_diag("#editor td", 0, 2, 3)
note("  R3f sel=%s" % json.dumps(d, ensure_ascii=False))
apply_act("bold")
md = js("window.getMarkdown()") or ""
note("  R3f md=%s" % json.dumps(md, ensure_ascii=False)[:200])
check("R3f HTML 单元格第二处加粗精确", "<strong>甲乙</strong>" not in md and "甲乙<strong>甲</strong>乙" in md,
      json.dumps(md, ensure_ascii=False)[:150])

note("========== 汇总 ==========")
log("SUMMARY total=%d fail=%d" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABN " + a)
print("DONE total=%d fail=%d" % (TOTAL[0], FAIL[0]))
