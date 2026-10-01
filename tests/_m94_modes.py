# -*- coding: utf-8 -*-
"""m94b：源码模式 / 双屏模式系统测试（v2，全部经 window.* / DOM，禁用闭包裸标识符）
A 模式切换（写作/源码/分屏三态 + cycle 按钮路径）
B 源码模式细节（层结构/行号/横向滚动垫层/undo 观察）
C 双屏：只读锁、内容同步（左→右）、滚动同步（映射/收敛/光标优先/单向性）
D 一致性（缩放/大纲/退出后内容保全）
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m94.txt")
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
        return {"_err": str(r)[:80]}


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


V = win._view
L = None
R = None

DOC_BLOCKS = ["# 双屏同步滚动测试文档"]
for i in range(1, 40):
    DOC_BLOCKS.append(("## 小节 %d" % i) if i % 2 else
                      ("这是第 %d 段的正文内容，用于验证双屏同步滚动的定位精度，包含中文与标点符号。" % i))
DOC_BLOCKS.append("超长行：" + "字" * 800)
DOC = "\n\n".join(DOC_BLOCKS)
N_LINES = DOC.split("\n").__len__()          # 源码总行数（含块间空行）
N_HEADINGS = sum(1 for b in DOC_BLOCKS if b.startswith("#"))


def setdoc(lines, ms=900):
    js_view(V, "window.setMarkdown(" + json.dumps("\n\n".join(lines)) + ")")


def wait_dual_loaded(max_s=25):
    t = 0
    while t < max_s * 4:
        if (win._vstate.get("src", {}).get("loaded") and
                win._vstate.get("prev", {}).get("loaded")):
            return True
        wait(250)
        t += 1
    return False


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
    """把源码第 k 块滚到视口探测位（不设选区，避免触发光标优先）"""
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
    """光标定位到块 k 并滚到视口 vp 比例处（保持可见）"""
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
              "return JSON.stringify({y:Math.round(window.scrollY),"
              "vis:Math.round(r.getBoundingClientRect().top)})})(" + str(k) + ")")


def prev_top(view):
    """预览侧视口顶部所在块序号（探测位与 pollSrcScroll 的 probe 对齐）"""
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

# ================= A 模式切换 =================
note("===== A 模式切换 =====")
setdoc(DOC_BLOCKS)
wait(900)

win._set_mode("src")
wait(800)
check("A1 进入源码模式 _mode=src", win._mode == "src")
r = poll(V)
check("A2 源码态 srcEl 生效（pollSrcScroll 可解析）", r.get("idx") is not None,
      json.dumps(r, ensure_ascii=False))
md = js_view(V, "window.getMarkdown()")
check("A2b 源码视图内容 = 原文", md == DOC, "len=%s" % (len(md) if md else None))

src_type_end(V, "源码新增XYZ", 500)
col = jj(V, "window.collect()")
check("A3 源码编辑经 collect 回传",
      "源码新增XYZ" in (col.get("md") or ""), "")

win._set_mode("edit")
wait(800)
r = jj(V, "(function(){return JSON.stringify({h1:!!document.querySelector('#editor h1'),"
          "src:!!document.querySelector('#editor .raw-edit.t-src')})})()")
raws = jj(V, "window.__raw()").get("raw") or []
check("A4 源码→写作：渲染恢复且编辑保留",
      r.get("h1") and (not r.get("src")) and any("源码新增XYZ" in (b or "") for b in raws),
      "h1=%s src=%s hit=%s" % (r.get("h1"), r.get("src"),
                               any("源码新增XYZ" in (b or "") for b in raws)))

# A5 cycle 按钮全循环：写作→源码→分屏→写作
win.cycle_mode()
wait(500)
check("A5a cycle 写作→源码", win._mode == "src")
win.cycle_mode()
wait_dual_loaded()
wait(2800)
check("A5b cycle 源码→分屏（双视图就绪）",
      win._mode == "dual" and win._dual and win._view_src is not None)
win.cycle_mode()
wait(1100)
check("A5c cycle 分屏→写作", win._mode == "edit" and not win._dual)

# ================= B 源码模式细节 =================
note("===== B 源码模式细节 =====")
win._set_mode("src")
wait(800)
r = jj(V, "(function(){return JSON.stringify({wrap:!!document.querySelector('.src-wrap'),"
          "gutter:!!document.querySelector('.src-gutter'),"
          "hl:!!document.querySelector('.src-hl'),"
          "glines:document.querySelectorAll('.src-gutter span,.src-gutter div').length})})()")
check("B1 源码层结构（wrap/gutter/高亮垫层）",
      r.get("wrap") and r.get("gutter") and r.get("hl"),
      json.dumps(r, ensure_ascii=False))
gl = r.get("glines") or 0
check("B2 行号数量 = 源码行数（含块间空行 %d）" % N_LINES, gl == N_LINES,
      "glines=%d expect=%d" % (gl, N_LINES))

r = jj(V, "(function(){var el=document.querySelector('#editor .raw-edit.t-src'),"
          "hl=document.querySelector('.src-hl');"
          "if(!el||!hl)return JSON.stringify({e:1});"
          "el.scrollLeft=300;el.dispatchEvent(new Event('scroll'));"
          "return JSON.stringify({sl:el.scrollLeft,hl:hl.scrollLeft})})()")
check("B3 长行横向滚动：高亮垫层 scrollLeft 跟随",
      (not r.get("e")) and (r.get("sl") or 0) > 0 and r.get("sl") == r.get("hl"),
      json.dumps(r, ensure_ascii=False))

src_type_end(V, "撤销观察串ABC", 1000)
md_before = (jj(V, "window.collect()").get("md") or "")
js_view(V, "window.cmd ? window.cmd('undo') : 'nocmd'")
wait(600)
md_after = (jj(V, "window.collect()").get("md") or "")
note("B4 源码模式 undo 观察：undo前尾14=%r undo后尾14=%r（记录现状，不判缺陷）"
     % (md_before[-14:], md_after[-14:]))

# ================= C 双屏内容与滚动同步 =================
note("===== C 双屏内容与滚动同步 =====")
win._set_mode("edit")
wait(600)
setdoc(DOC_BLOCKS)
wait(800)
win._set_mode("dual")
wait_dual_loaded()
wait(3000)
L = win._view_src
R = win._view_prev
r = poll(L)
check("C1 进入分屏：左侧源码态（pollSrcScroll 可解析）", r.get("idx") is not None,
      json.dumps(r, ensure_ascii=False))
check("C1b 右侧预览锁 __previewLock",
      js_view(R, "String(window.__previewLock===true)") == "true")

md0 = js_view(R, "JSON.stringify(window.__lastPreviewMd||'')") or ""
js_view(R, "(function(){var b=document.querySelector('#editor h1');"
           "if(b)b.focus();document.execCommand('insertText',false,'预览侧输入不应生效');return 'ok'})()")
wait(400)
md1 = js_view(R, "JSON.stringify(window.__lastPreviewMd||'')") or ""
r2 = jj(R, "(function(){return JSON.stringify({raw:document.querySelectorAll('#editor .raw-edit').length,"
           "chg:EDX})})()".replace("EDX", "document.getElementById('editor').textContent.indexOf('预览侧输入不应生效')>=0"))
check("C2 预览侧只读（输入不生效、不进编辑态）",
      md0 == md1 and (r2.get("raw") == 0) and (r2.get("chg") is False),
      json.dumps(r2, ensure_ascii=False))

src_type_end(L, " 双屏左侧新增QWE789", 300)
wait(1500)
got = js_view(R, "JSON.stringify((window.__lastPreviewMd||'').indexOf('QWE789')>=0)")
check("C3 左侧编辑→右侧预览更新（700ms 轮询链路）", got == "true", "right_has=%s" % got)

# C4 滚动映射：块 20 置顶 → 预览跟随（此时光标在文末，不在视口 → 走滚动映射）
src_goto_block(L, 20)
wait(900)
pt = prev_top(R)
check("C4 拉动源码滚动条→预览跟随（块20±2）",
      pt.get("top") is not None and abs(pt["top"] - 20) <= 2,
      json.dumps(pt, ensure_ascii=False))

# C5 回顶部
js_view(L, "window.scrollTo(0,0)")
wait(900)
pt = prev_top(R)
check("C5 源码回顶→预览回顶（scrollY<120）",
      pt.get("y") is not None and pt["y"] < 120, json.dumps(pt, ensure_ascii=False))

# C6 拉到底
js_view(L, "window.scrollTo(0,document.documentElement.scrollHeight)")
wait(900)
pt = prev_top(R)
check("C6 源码到底→预览接近底部",
      pt.get("h") and (pt.get("y") or 0) + 900 >= pt["h"],
      json.dumps(pt, ensure_ascii=False))

# C7 快速连续滚动 → 收敛到最终位置
for k in (12, 25, 33):
    src_goto_block(L, k)
    wait(70)
wait(1100)
pt = prev_top(R)
check("C7 快速连续滚动→预览收敛到最终块（33±2）",
      pt.get("top") is not None and abs(pt["top"] - 33) <= 2,
      json.dumps(pt, ensure_ascii=False))

# C8 光标可见 → 光标优先（编辑跟随）：光标块30置于视口60%处
r = src_caret_block(L, 30, 0.6)
wait(1000)
pt = prev_top(R)
check("C8 光标可见时预览跟随光标（≥28，非视口顶块≈26）",
      pt.get("top") is not None and pt["top"] >= 28,
      "caret=%s prev=%s" % (json.dumps(r, ensure_ascii=False), json.dumps(pt, ensure_ascii=False)))

# C9 反向：拉预览滚动条 → 源码不动（单向同步现状）
ly0 = js_view(L, "String(Math.round(window.scrollY))")
js_view(R, "window.scrollTo(0,window.scrollY+600)")
wait(900)
ly1 = js_view(L, "String(Math.round(window.scrollY))")
check("C9 拉动预览滚动条→源码不动（单向同步现状）", ly0 is not None and ly0 == ly1,
      "before=%s after=%s" % (ly0, ly1))

# C10 底部编辑：预览内容更新且滚动位置不被重置
ry0 = (prev_top(R).get("y") or 0)
src_type_end(L, " 尾部追加ABC", 200)
wait(1500)
r = jj(R, "(function(){return JSON.stringify({has:(window.__lastPreviewMd||'').indexOf('尾部追加ABC')>=0,"
          "y:Math.round(window.scrollY)})})()")
check("C10 底部编辑→预览更新且不重置滚动",
      r.get("has") is True and (r.get("y") or 0) > max(100, ry0 // 2),
      json.dumps(r, ensure_ascii=False))

# D2 前移：大纲在分屏下取自左侧（此时左侧仍是 41 块文档）
ol = jj(L, "window.getOutline()")
olv = ol.get("_v") if "_v" in ol else ol
if isinstance(olv, dict):
    olv = olv.get("outline") or olv
check("D2 分屏左侧视图大纲完整（≥21 个标题）",
      isinstance(olv, list) and len(olv) >= N_HEADINGS,
      "outline=%s" % (len(olv) if isinstance(olv, list) else json.dumps(olv, ensure_ascii=False)[:60]))

# C11 单块文档：pollSrcScroll / scrollPreviewToBlock 不异常
js_view(L, "window.setMarkdown('# 单块文档');window.setSourceMode(true)")
wait(1400)
r = poll(L)
check("C11 单块文档 pollSrcScroll 正常（idx=0）", r.get("idx") == 0,
      json.dumps(r, ensure_ascii=False))
r = js_view(R, "(function(){window.scrollPreviewToBlock(0,0.5);return 'ok'})()")
check("C11b scrollPreviewToBlock(0,…) 不异常", r == "ok")

# ================= D 一致性 =================
note("===== D 一致性 =====")
z0 = win._view.zoomFactor()
z1 = win._view_src.zoomFactor() if win._view_src else -1
z2 = win._view_prev.zoomFactor() if win._view_prev else -1
check("D1 三视图缩放一致", z0 == z1 == z2 == win._zoom,
      "edit=%s src=%s prev=%s zoom=%s" % (z0, z1, z2, win._zoom))

win._set_mode("edit")
wait(1100)
r = jj(V, "window.__raw()")
raws = r.get("raw") or []
check("D3 退出分屏：左栏编辑全部保留到写作视图",
      any("QWE789" in (b or "") for b in raws) and any("尾部追加ABC" in (b or "") for b in raws),
      "blocks=%d" % len(raws))

note("========== 汇总 ==========")
log("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE")
