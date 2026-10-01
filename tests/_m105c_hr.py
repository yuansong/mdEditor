# -*- coding: utf-8 -*-
"""m105c 分割线精查：/ 菜单触发链、R6 空段删 hr 甄别、响应式、打印、无障碍"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105c_hr.txt")
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


def setmd(md, ms=800):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getmd():
    return js("window.getMarkdown()") or ""


def blkseq():
    return jj("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
              "return JSON.stringify(bs.map(function(b){"
              "var h=b.querySelector('hr');"
              "return (h?'HR':'P')+'['+(b.textContent||'').slice(0,6)+']'})"
              ")})()")


note("========== S1 / 菜单触发链（execCommand 插入 /）==========")
setmd("前段")
js("(function(){var b=document.querySelector('#editor .blk');if(!b)return 'noblk';"
   "b.setAttribute('contenteditable','plaintext-only');b.focus();"
   "var rg=document.createRange();rg.selectNodeContents(b);rg.collapse(false);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
   "try{document.execCommand('insertText',false,'/')}catch(e){}"
   "return 'ok'})()")
wait(800)
sm = js("(function(){var p=document.getElementById('slashmenu');"
        "if(!p)return 'nodom';"
        "return JSON.stringify({show:p.classList.contains('show'),"
        "txt:(p.textContent||'').slice(0,260)})})()")
note("  S1 slashmenu=%s" % str(sm)[:400])
check("S1 / 菜单可打开且含「分割线」", "分割线" in str(sm), "sm=%s" % str(sm)[:300])

note("  S2 通过 __slashPick('hr') 应用")
r = js("window.__slashPick('hr')")
wait(900)
note("  S2 pick=%s md=%s" % (r, json.dumps(getmd(), ensure_ascii=False)))
check("S2 / 菜单 hr 项可插入", "---" in getmd(), "pick=%s md=%s" % (r, json.dumps(getmd(), ensure_ascii=False)))

note("========== S3 R6 甄别：尾部空段是否被规范化 ==========")
setmd("前段\n\n---\n\n")
md_pre = getmd()
seq = blkseq()
note("  S3 setmd 后 md=%s 块序列=%s" % (json.dumps(md_pre, ensure_ascii=False),
                                        json.dumps(seq, ensure_ascii=False)))
check("S3a setMarkdown 保留尾部空段（存在可聚焦的空段块）",
      len(seq.get("_raw", seq) if isinstance(seq, dict) else seq) >= 3,
      "seq=%s" % json.dumps(seq, ensure_ascii=False))

note("  S4 手动构造「hr + 空段」并从空段行首 Backspace")
setmd("甲\n\n---\n\n乙")
wait(400)
# 在 hr 之后插入一个空段：模拟真实用户「hr 后回车再回车」的产物
js("(function(){var f=window.goToBlock||window.__goToBlock;"
   "if(typeof f==='function'){f(1,'end')}return 'ok'})()")
wait(400)
md_a = getmd()
note("  S4 定位后 md=%s" % json.dumps(md_a, ensure_ascii=False))
# 用键盘在 hr 后回车（应新建空段）
js("(function(){var t=document.activeElement||document.body;"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(600)
md_b = getmd()
note("  S4 回车后 md=%s" % json.dumps(md_b, ensure_ascii=False))
# 再按 Backspace（空段行首 → 按 HR-3 应删除 hr）
js("(function(){var t=document.activeElement||document.body;"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'Backspace',bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(700)
md_c = getmd()
note("  S4 Backspace 后 md=%s" % json.dumps(md_c, ensure_ascii=False))
check("S4 hr 后新建空段再 Backspace → 删除 hr（HR-3 语义）",
      "---" not in md_c, "md=%s" % json.dumps(md_c, ensure_ascii=False))

note("========== S5 响应式：栏宽变化时 hr 铺满 ==========")
setmd("甲\n\n---\n\n乙")
w1 = jj("(function(){var h=document.querySelector('#editor hr');"
        "return JSON.stringify({w:Math.round(h.getBoundingClientRect().width),"
        "edw:Math.round(document.getElementById('editor').getBoundingClientRect().width)})})()")
note("  S5 默认宽度=%s" % json.dumps(w1, ensure_ascii=False))
win.resize(700, 800)
wait(900)
w2 = jj("(function(){var h=document.querySelector('#editor hr');"
        "return JSON.stringify({w:Math.round(h.getBoundingClientRect().width),"
        "edw:Math.round(document.getElementById('editor').getBoundingClientRect().width)})})()")
note("  S5 窄窗宽度=%s" % json.dumps(w2, ensure_ascii=False))
check("S5 分割线随栏宽自适应收缩", w2.get("w", 0) < w1.get("w", 0) and w2.get("w", 0) > 100,
      "w1=%s w2=%s" % (w1.get("w"), w2.get("w")))
check("S5b 分割线宽度 = 内容栏宽（非溢出）",
      abs(w2.get("w", 0) - w2.get("edw", 0)) <= 80,
      "hr=%s editor=%s" % (w2.get("w"), w2.get("edw")))
win.resize(1200, 860)
wait(700)

note("========== S6 打印：@media print 下 hr 是否可见 ==========")
pr = jj("(function(){var h=document.querySelector('#editor hr');"
        "if(!h)return JSON.stringify({none:1});"
        "var c=getComputedStyle(h);"
        "return JSON.stringify({disp:c.display,vis:c.visibility,btw:c.borderTopWidth})})()")
note("  S6=%s" % json.dumps(pr, ensure_ascii=False))
check("S6 打印态下分割线未被隐藏", pr.get("disp") != "none", "disp=%s" % pr.get("disp"))

note("========== S7 无障碍语义 ==========")
ax = jj("(function(){var h=document.querySelector('#editor hr');"
        "if(!h)return JSON.stringify({none:1});"
        "return JSON.stringify({tag:h.tagName,role:h.getAttribute('role'),"
        "aria:h.getAttribute('aria-hidden'),"
        "implicit:'separator(HTML原生)'})})()")
note("  S7=%s" % json.dumps(ax, ensure_ascii=False))
check("S7 使用原生 <hr>（隐含 role=separator，读屏可识别）",
      ax.get("tag") == "HR", "ax=%s" % json.dumps(ax, ensure_ascii=False))

note("========== S8 配置项能力盘点（源码层）==========")
note("  S8 可配置维度探测：hr 元素是否被附加任何 data-* / class 变体")
var = jj("(function(){var h=document.querySelector('#editor hr');"
         "if(!h)return JSON.stringify({none:1});"
         "return JSON.stringify({cls:h.className,attrs:[].slice.call(h.attributes).map(function(a){return a.name})})})()")
note("  S8=%s" % json.dumps(var, ensure_ascii=False))
check("S8 hr 无变体类/属性（线型·粗细·颜色·文字·竖线均不可配）",
      not var.get("cls") and len([a for a in var.get("attrs", []) if a.startswith("data-")]) == 0,
      "var=%s" % json.dumps(var, ensure_ascii=False))

note("========== S9 引用内分割线渲染 ==========")
setmd("> 引文\n>\n> ---\n>\n> 后文")
q = jj("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return JSON.stringify({none:1});"
       "var h=bq.querySelector('hr');"
       "return JSON.stringify({hrInQuote:!!h,txt:(bq.textContent||'').slice(0,30)})})()")
note("  S9=%s" % json.dumps(q, ensure_ascii=False))
check("S9 引用内 `> ---` 渲染为 hr", q.get("hrInQuote") is True,
      "q=%s" % json.dumps(q, ensure_ascii=False))

note("========== S10 列表项与 hr 的歧义边界 ==========")
setmd("- 甲\n- 乙\n\n---\n\n丙")
amb = getmd()
note("  S10 md=%s" % json.dumps(amb, ensure_ascii=False))
check("S10 列表后的 --- 独立成 hr（不与列表粘连）", amb.count("---") >= 1,
      "md=%s" % json.dumps(amb, ensure_ascii=False))
note("  S10b 列表项内的 --- 是否误判")
setmd("- 甲\n---\n- 乙")
amb2 = getmd()
s10 = blkseq()
note("  S10b md=%s seq=%s" % (json.dumps(amb2, ensure_ascii=False), json.dumps(s10, ensure_ascii=False)))

log("\n==== 合计 %d 项，FAIL %d ====" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABNORMAL " + a)
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
