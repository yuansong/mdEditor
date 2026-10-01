# -*- coding: utf-8 -*-
"""m94c：v2 遗留项甄别（C4/C6/C7 滚动映射根因诊断 + C2 预览可写性 + D2/D3 顺序修正）"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m94c.txt")
out = []
TOTAL = [0]
FAIL = [0]


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def note(s):
    log("NOTE %s" % s)


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js_view(view, code, ms=15000):
    loop = QEventLoop()
    box = {"r": None, "done": False}

    def cb(res):
        box["r"] = res
        box["done"] = True
        loop.quit()
    QTimer.singleShot(ms, loop.quit)
    win._js_view(view, code, cb)
    loop.exec()
    return box["r"] if box["done"] else None


def jj(view, code):
    r = js_view(view, code)
    try:
        v = json.loads(r if r is not None else "{}")
        return v if isinstance(v, dict) else {"_v": v}
    except Exception:
        return {"_err": str(r)[:120]}


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


V = win._view

DOC_BLOCKS = ["# 双屏同步滚动测试文档"]
for i in range(1, 40):
    DOC_BLOCKS.append(("## 小节 %d" % i) if i % 2 else
                      ("这是第 %d 段的正文内容，用于验证双屏同步滚动的定位精度，包含中文与标点符号。" % i))
DOC_BLOCKS.append("超长行：" + "字" * 800)
DOC = "\n\n".join(DOC_BLOCKS)
N_HEADINGS = sum(1 for b in DOC_BLOCKS if b.startswith("#"))


def js_view0(view, code, ms=15000):
    return js_view(view, code, ms)


def src_end_focus(view):
    return js_view(view,
                   "(function(){var el=document.querySelector('#editor .raw-edit.t-src');"
                   "if(!el)return 'no-src';el.focus();"
                   "var s=getSelection();var rg=document.createRange();"
                   "rg.selectNodeContents(el);rg.collapse(false);"
                   "s.removeAllRanges();s.addRange(rg);return 'ok'})()")


def src_type_end(view, text, ms=420):
    src_end_focus(view)
    js_view(view, "document.execCommand('insertText',false," + json.dumps(text) + ")")
    wait(ms)


def src_goto_block(view, k):
    return jj(view,
              "(function(k){var el=document.querySelector('#editor .raw-edit.t-src');"
              "if(!el)return JSON.stringify({e:1});"
              "var md=window.getMarkdown();var off=0,raws=md.split('\\n\\n');"
              "for(var i=0;i<k&&i<raws.length;i++)off+=raws[i].length+2;"
              "var tn=el.firstChild;if(!tn||tn.nodeType!==3)return JSON.stringify({e:2});"
              "var r=document.createRange();r.setStart(tn,Math.min(off,tn.length));"
              "r.collapse(true);var rect=r.getBoundingClientRect();"
              "window.scrollTo(0,window.scrollY+rect.top-48);"
              "return JSON.stringify({y:Math.round(window.scrollY)})})(" + str(k) + ")")


def src_caret_block(view, k, vp):
    return jj(view,
              "(function(k){var el=document.querySelector('#editor .raw-edit.t-src');"
              "if(!el)return JSON.stringify({e:1});"
              "var md=window.getMarkdown();var off=0,raws=md.split('\\n\\n');"
              "for(var i=0;i<k&&i<raws.length;i++)off+=raws[i].length+2;"
              "var tn=el.firstChild;if(!tn||tn.nodeType!==3)return JSON.stringify({e:2});"
              "var r=document.createRange();r.setStart(tn,Math.min(off,tn.length));"
              "r.collapse(true);var s=getSelection();s.removeAllRanges();s.addRange(r);"
              "el.focus();var rect=r.getBoundingClientRect();"
              "window.scrollTo(0,window.scrollY+rect.top-window.innerHeight*" + str(vp) + ");"
              "return JSON.stringify({y:Math.round(window.scrollY)})})(" + str(k) + ")")


def prev_top(view):
    return jj(view,
              "(function(){var p=window.innerHeight*0.08+48,b=-1;"
              "var bl=document.querySelectorAll('#editor .blk:not(.src-hl)');"
              "for(var i=0;i<bl.length;i++){"
              "if(bl[i].getBoundingClientRect().top<=p+1)b=i;}"
              "return JSON.stringify({top:b,n:bl.length,y:Math.round(window.scrollY),"
              "h:Math.round(document.documentElement.scrollHeight)})})()")


def poll(view):
    return jj(view, "window.pollSrcScroll()")


wait(2500)

note("===== 准备：直接进入分屏 =====")
js_view(V, "window.setMarkdown(" + json.dumps(DOC) + ")")
wait(900)
win._set_mode("dual")
t = 0
while t < 100:
    if (win._vstate.get("src", {}).get("loaded") and
            win._vstate.get("prev", {}).get("loaded")):
        break
    wait(250)
    t += 1
wait(3000)
L = win._view_src
R = win._view_prev
note("dual ready, mode=%s" % win._mode)

note("===== T1 滚动映射根因诊断（无光标干扰：不设选区） =====")
# 左侧光标此时在哪里？进入分屏 setSourceMode(true) 会 srcEl.focus() → 光标在文首块0
r = poll(L)
note("T1a 初始 poll（滚到块20前）=%s" % json.dumps(r, ensure_ascii=False))
g = src_goto_block(L, 20)
note("T1b goto(20) 源码 scrollY=%s" % json.dumps(g, ensure_ascii=False))
wait(200)
r = poll(L)
note("T1c goto(20) 后 poll=%s" % json.dumps(r, ensure_ascii=False))
wait(800)
pt = prev_top(R)
r2 = poll(L)
note("T1d 稳定后 poll=%s prev=%s" % (json.dumps(r2, ensure_ascii=False), json.dumps(pt, ensure_ascii=False)))
check("T1 滚动映射：poll.idx=20 且预览 top≈20（当前实现二者须同时成立）",
      r2.get("idx") == 20 and pt.get("top") is not None and abs(pt["top"] - 20) <= 2,
      "poll.idx=%s prev.top=%s" % (r2.get("idx"), pt.get("top")))

note("===== T2 光标在视口内时的优先级（编辑跟随分支） =====")
src_caret_block(L, 30, 0.6)
wait(250)
r = poll(L)
note("T2a 光标块30可见 poll=%s" % json.dumps(r, ensure_ascii=False))
wait(800)
pt = prev_top(R)
r2 = poll(L)
note("T2b 稳定后 poll=%s prev=%s" % (json.dumps(r2, ensure_ascii=False), json.dumps(pt, ensure_ascii=False)))
check("T2 光标优先：poll.cv=true 且预览 top≈30",
      r2.get("cv") is True and r2.get("cidx") == 30 and
      pt.get("top") is not None and abs(pt["top"] - 30) <= 2,
      "poll=%s prev.top=%s" % (json.dumps(r2, ensure_ascii=False), pt.get("top")))

note("===== T3 预览侧可写性复核（纯 DOM 污染 vs 内容破坏） =====")
md0 = js_view(R, "JSON.stringify(window.__lastPreviewMd||'')") or ""
r = js_view(R, "(function(){var b=document.querySelector('#editor h1');"
               "if(!b)return 'no-h1';b.focus();"
               "document.execCommand('insertText',false,'PREVIEWTYPED');return 'ok'})()")
wait(300)
md1 = js_view(R, "JSON.stringify(window.__lastPreviewMd||'')") or ""
r2 = jj(R, "(function(){var b=document.querySelector('#editor h1');"
           "return JSON.stringify({dom:b?b.textContent.indexOf('PREVIEWTYPED')>=0:false,"
           "ce:b?b.getAttribute('contenteditable'):null})})()")
check("T3 预览侧 DOM 可被键盘输入污染（contenteditable=%s）" % r2.get("ce"),
      r2.get("dom") is True, "md_unchanged=%s" % (md0 == md1))

note("===== T4 大纲（分屏左侧，41 块文档未动） =====")
col = jj(L, "window.collect()")
ol = col.get("outline")
check("T4 分屏下大纲完整（≥%d 个标题）" % N_HEADINGS,
      isinstance(ol, list) and len(ol) >= N_HEADINGS,
      "outline=%s" % (len(ol) if isinstance(ol, list) else json.dumps(ol, ensure_ascii=False)[:80]))

note("===== T5 收敛一致性（快速滚动后 预览==poll.idx） =====")
for k in (12, 25, 33):
    src_goto_block(L, k)
    wait(70)
wait(1100)
r = poll(L)
pt = prev_top(R)
pt2 = prev_top(R)
check("T5 快速滚动收敛：预览稳定且与 poll.idx 一致",
      (pt.get("top") is not None) and (pt.get("top") == pt2.get("top")) and
      (pt.get("top") == r.get("idx")),
      "poll.idx=%s prev=%s/%s" % (r.get("idx"), pt.get("top"), pt2.get("top")))

note("===== T6 退出分屏内容保全（恢复文档后验证） =====")
js_view(L, "window.setMarkdown(" + json.dumps(DOC) + ");window.setSourceMode(true)")
wait(1300)
src_type_end(L, " 退出分屏保留ZZZ", 300)
wait(1500)
win._set_mode("edit")
wait(1200)
r = jj(V, "window.__raw()")
raws = r.get("raw") or []
check("T6 退出分屏：左栏编辑保留到写作视图",
      any("退出分屏保留ZZZ" in (b or "") for b in raws),
      "blocks=%d" % len(raws))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
