# -*- coding: utf-8 -*-
"""m111：v3.38 FMTB 批次验收（floatbar 全块型一致性审计修复）
- A 组 FMTB-1：单元格重复文字 —— 管道/HTML 双表型，选第二处重复文字，
  加粗/清除均落在选中处（报告验收口径）；含首现回归 + 标签跳过。
- B 组 FMTB-2：单元格行内码叠加守卫（FMT-1 上移覆盖单元格路径），
  正文守卫回归。
- C 组 FMTB-4：跨块选区尾部不报标题数（只报「已选 N 字」），
  单块标题选区仍报「标题 1」（FB-3 回归）。
版本：src v3.38（FMTB 补丁后）
结果：tests/_m111.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m111.txt")
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
    """单元素内选区构造 + 诊断"""
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


def sel_cross(ms=520):
    """跨块选区：h1 全文 → h2 全文（FMTB-4 场景）"""
    r = js("(function(){var h1=document.querySelector('#editor h1'),"
           "h2=document.querySelector('#editor h2');"
           "if(!h1||!h2)return JSON.stringify({err:'no-h'});"
           "var rg=document.createRange();"
           "rg.setStart(h1.firstChild,0);"
           "rg.setEnd(h2.firstChild,h2.firstChild.textContent.length);"
           "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
           "document.dispatchEvent(new Event('selectionchange'));"
           "return JSON.stringify({sel:s.toString()})})()")
    wait(ms)
    return jj(json.dumps(r)) if isinstance(r, str) and r.startswith("{") else r


def apply_act(action, ms=340):
    js("window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


def take_toast():
    return js("window.takeToast()") or ""


def blk_of(raw, key):
    return next((r for r in raw if key in r), "")


note("========== A 组 FMTB-1 单元格重复文字定位 ==========")

note("A1 管道表选第二处甲加粗")
setmd("预热段落", ms=900)   # 首测预热（首例偶发渲染未就绪）
setmd("| 表头 |\n| --- |\n| 甲乙甲乙 |")
d = sel_diag("#editor td", 0, 2, 3)
note("  A1 sel=%s" % json.dumps(d, ensure_ascii=False))
apply_act("bold")
raw = getraw()
blk = blk_of(raw, "甲乙")
check("A1 管道第二处加粗精确", "| 甲乙**甲**乙 |" in blk and "**甲**乙甲" not in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("A2 管道表选第二处甲清除格式")
setmd("| 表头 |\n| --- |\n| **甲**乙**甲**乙 |")
sel_diag("#editor td", 0, 2, 3)
apply_act("clearfmt")
raw = getraw()
blk = blk_of(raw, "甲乙")
check("A2 管道第二处清除精确", "| **甲**乙甲乙 |" in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("A3 管道表选第一处甲仍落首现（回归）")
setmd("| 表头 |\n| --- |\n| 甲乙甲乙 |")
sel_diag("#editor td", 0, 0, 1)
apply_act("bold")
raw = getraw()
blk = blk_of(raw, "甲乙")
check("A3 首现行为不变", "| **甲**乙甲乙 |" in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("A4 HTML 表选第二处甲清除格式")
setmd('<table><tr><th>名称</th></tr>'
      '<tr><td><strong>甲</strong>乙<strong>甲</strong>乙</td></tr></table>')
sel_diag("#editor td", 0, 2, 3)
apply_act("clearfmt")
md = js("window.getMarkdown()") or ""
check("A4 HTML第二处清除精确", "<td><strong>甲</strong>乙甲乙</td>" in md,
      "md=%s" % json.dumps(md, ensure_ascii=False)[:160])

note("A5 管道表标记相邻：**甲**甲 选第二处甲加粗（不误触首处 toggle）")
setmd("| 表头 |\n| --- |\n| **甲**甲 |")
sel_diag("#editor td", 0, 1, 2)
apply_act("bold")
raw = getraw()
blk = blk_of(raw, "甲")
check("A5 首处壳保留次处加包", "| **甲****甲** |" in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("A6 HTML 表标签相邻：<strong>甲</strong>甲 选第二处甲加粗")
setmd('<table><tr><th>名称</th></tr>'
      '<tr><td><strong>甲</strong>甲</td></tr></table>')
sel_diag("#editor td", 0, 1, 2)
apply_act("bold")
md = js("window.getMarkdown()") or ""
check("A6 标签内匹配被跳过", "<td><strong>甲</strong><strong>甲</strong></td>" in md,
      "md=%s" % json.dumps(md, ensure_ascii=False)[:160])

note("========== B 组 FMTB-2 行内码叠加守卫（单元格路径） ==========")

note("B1 管道表码内加粗拒绝")
setmd("| 表头 |\n| --- |\n| 前`码甲`后 |")
d = sel_diag("#editor td", 0, 1, 3)
note("  B1 sel=%s" % json.dumps(d, ensure_ascii=False))
tst = js("window.__applyFloat('bold'); window.takeToast()") or ""
wait(340)
raw = getraw()
blk = blk_of(raw, "码甲")
check("B1 管道码内加粗拒绝", "`码甲`" in blk and "**" not in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))
check("B1 守卫提示文案", "行内代码内不支持叠加行内格式" in tst, "toast=%s" % tst)

note("B2 HTML 表码内加粗拒绝")
setmd('<table><tr><th>名称</th></tr>'
      '<tr><td>前<code>码甲</code>后</td></tr></table>')
sel_diag("#editor td", 0, 1, 3)
apply_act("bold")
md = js("window.getMarkdown()") or ""
check("B2 HTML码内加粗拒绝", "<code>码甲</code>" in md and "<strong>" not in md,
      "md=%s" % json.dumps(md, ensure_ascii=False)[:160])

note("B3 正文码内加粗守卫回归（上移后仍在）")
setmd("前`码甲`后")
sel_diag("#editor p", 0, 1, 3)
apply_act("bold")
raw = getraw()
blk = blk_of(raw, "码甲")
check("B3 正文守卫仍生效", "`码甲`" in blk and "**" not in blk,
      "blk=%s" % json.dumps(blk, ensure_ascii=False))

note("========== C 组 FMTB-4 跨块选区尾部文案 ==========")

note("C1 跨块选区（标题一 → 标题二）尾部不报标题数")
setmd("# 标题一\n\n中间段落\n\n## 标题二")
d = sel_cross()
note("  C1 sel=%s" % json.dumps(d, ensure_ascii=False))
st = fb_state()
note("  C1 fb=%s" % json.dumps(st, ensure_ascii=False))
if st.get("show"):
    tail = st.get("tail", "")
    check("C1 跨块尾部不报标题数", ("标题" not in tail) and ("已选" in tail),
          "tail=%s" % tail)
else:
    check("C1 跨块尾部不报标题数", False, "floatbar 未显示")

note("C2 单块标题选区仍报「标题 1」（FB-3 回归）")
setmd("# 标题一\n\n中间段落")
sel_diag("#editor h1", 0, 0, 3)
st = fb_state()
note("  C2 fb=%s" % json.dumps(st, ensure_ascii=False))
if st.get("show"):
    tail = st.get("tail", "")
    check("C2 单块标题文案保留", ("标题 1" in tail) and ("已选" in tail),
          "tail=%s" % tail)
else:
    check("C2 单块标题文案保留", False, "floatbar 未显示")

note("========== 汇总 ==========")
log("SUMMARY total=%d fail=%d" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABN " + a)
print("DONE total=%d fail=%d" % (TOTAL[0], FAIL[0]))
