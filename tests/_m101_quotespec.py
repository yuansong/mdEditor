# -*- coding: utf-8 -*-
"""m101 引用（blockquote）操作规范实证：退出路径 / 双重回车 / Backspace / 方向键 / 引用内标题

用户要求（2026-10-01）：系统梳理引用模块操作规范——
 1) 退出方式全列举 + 缺口
 2) 连续两次回车行为异常的实证与根因
 3) 引用内标题的处理定义（自动降级）
 4) 完整操作清单（规范输出）
衔接：_m90~_m93（BQ-1/2/3、E1-E5）、QUO-3/4/5/6 已修项
版本：src v3.37（2026-10-01 07:16:32，687450B，sha16 6A7F52911B83A044）
结果：tests/_m101.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m101.txt")
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


def setmd(md, ms=750):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)
    st = qstate()
    if st.get("nobq") and "> " in md:
        # 首次未生效（页面竞态）重试一次
        js("window.setMarkdown(" + json.dumps(md) + ")")
        wait(ms)


def qstate():
    return jj("(function(){var bq=document.querySelector('#editor blockquote');"
              "if(!bq)return JSON.stringify({nobq:1});"
              "var blk=bq.closest('.blk');"
              "var rw={};try{rw=JSON.parse(window.__raw()||'{}')}catch(e){}"
              "return JSON.stringify({isRaw:blk?blk.classList.contains('raw-edit'):null,"
              "cls:blk?blk.className:'',raw:rw.raw||[],"
              "editIdx:rw.editIdx,"
              "qblk:bq.querySelectorAll('.qblk').length,"
              "qh:!!bq.querySelector('.qblk h1, .qblk h2, .qblk h3'),"
              "hEditable:(function(){var h=bq.querySelector('.qblk h1, .qblk h2, .qblk h3');"
              "return h?h.getAttribute('contenteditable'):null})(),"
              "txt:(bq.textContent||'').slice(0,60),"
              "ae:document.activeElement?document.activeElement.tagName:''})})()")


def q_caret_end():
    """光标置于 blockquote 内容最末（含空末行 / 尾部哨兵之后）"""
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(200)


def q_caret_start():
    """光标置于 blockquote 首行行首（第一个非 qblk 文本节点起点）"""
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var w=document.createTreeWalker(bq,NodeFilter.SHOW_TEXT,null);var n;"
       "while(n=w.nextNode()){if(n.closest&&n.closest('.qblk'))continue;"
       "if(n.nodeValue.length===0)continue;"
       "var rg=document.createRange();rg.setStart(n,0);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'}"
       "return 'no-text'})()")
    wait(200)


def key_on_quote(key, ms=430, ctrl=False):
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var ev=new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,ctrlKey:" + ("true" if ctrl else "false") + "});"
       "bq.dispatchEvent(ev);return 'ok'})()")
    wait(ms)


note("========== A 组：双重回车（渲染态，行尾连按） ==========")
# 等待页面 JS 完成加载（_m101 首跑教训：过早调 window.setMarkdown 报 not a function）
wait(2800)
note("boot hooks=%s" % js("JSON.stringify({sm:typeof window.setMarkdown,rw:typeof window.__raw})"))
setmd("> 引文甲行\n\n段落乙")
st0 = qstate()
check("A0 引用渲染态就绪", st0.get("isRaw") is False and st0.get("cls", "").find("b-quote") >= 0,
      "inf=%s" % json.dumps(st0, ensure_ascii=False)[:160])

q_caret_end()
key_on_quote("Enter")
st1 = qstate()
check("A1 第一次回车：引用内新增空行（仍渲染态）",
      st1.get("isRaw") is False and
      st1.get("raw", [""])[0].count("\n") == 1,   # v3.38 甄别：raw 含后续段落块，块数不作断言
      "inf=%s" % json.dumps(st1, ensure_ascii=False)[:200])

q_caret_end()
key_on_quote("Enter")
st2 = qstate()
note("A2 第二次回车实际落点：isRaw=%s raw=%s" % (st2.get("isRaw"), json.dumps(st2.get("raw"), ensure_ascii=False)))
check("A2[规范] 第二次回车应退出引用→其后新建空段落且引用保持渲染",
      # v3.38（QUO-8 落地）：raw = [引用, 新空段落, 原后续块]
      st2.get("isRaw") is False and len(st2.get("raw", [])) == 3 and
      str(st2.get("raw", ["", ""])[0]).startswith(">") and str(st2.get("raw", ["", ""])[1]) == "",
      "inf=%s" % json.dumps(st2, ensure_ascii=False)[:200])

note("========== B 组：Backspace 退出/降级行为 ==========")
setmd("> 引文乙行")
q_caret_start()
key_on_quote("Backspace")
stb1 = qstate()
note("B1 单行引用行首退格实际：isRaw=%s raw=%s" % (stb1.get("isRaw"), json.dumps(stb1.get("raw"), ensure_ascii=False)))
_b1raw = json.loads(js("JSON.stringify((JSON.parse(window.__raw()||'{}')).raw||[])") or "[]")
check("B1[规范] 单行引用行首退格→整块转段落（源码态）",
      # v3.38 甄别：转段落后引用元素消失（qstate 读不到），改读 __raw
      len(_b1raw) >= 1 and _b1raw[0] == "引文乙行",
      "inf=%s" % json.dumps(stb1, ensure_ascii=False)[:200])

setmd("> 引文丙行\n>")
q_caret_end()
key_on_quote("Backspace")
stb2 = qstate()
note("B2 末尾空行退格实际：isRaw=%s raw=%s" % (stb2.get("isRaw"), json.dumps(stb2.get("raw"), ensure_ascii=False)))
check("B2[规范] 末尾空行退格应仅删空行、引用保留",
      len(stb2.get("raw", [])) == 1 and str(stb2.get("raw", [""])[0]).startswith(">") and
      "引文丙行" in str(stb2.get("raw", [""])[0]),
      "inf=%s" % json.dumps(stb2, ensure_ascii=False)[:200])

setmd(">> 深层行\n\n段落乙")
q_caret_start()
key_on_quote("Backspace")
stb3 = qstate()
_b3raw = str((stb3.get("raw") or [""])[0])
check("B3[QUO-3] 两层嵌套行首退格→退一级（仍渲染引用）",
      stb3.get("isRaw") is False and _b3raw == "> 深层行",
      "inf=%s" % json.dumps(stb3, ensure_ascii=False)[:200])

note("========== C 组：方向键跳出 / Esc / 点击外部 ==========")
setmd("> 引文丁行\n\n段落乙")
q_caret_end()
key_on_quote("ArrowDown")
stc1 = qstate()
note("C1 ArrowDown 实际：isRaw=%s raw=%s ae=%s" % (stc1.get("isRaw"), json.dumps(stc1.get("raw"), ensure_ascii=False), stc1.get("ae")))
check("C1[规范] 末尾按 ArrowDown→光标跳出引用（引用保持渲染态）",
      stc1.get("isRaw") is False and len(stc1.get("raw", [])) == 2,
      "inf=%s" % json.dumps(stc1, ensure_ascii=False)[:200])

setmd("> 引文戊行\n\n段落乙")
q_caret_end()
key_on_quote("Escape", ms=250)
stc2 = qstate()
note("C2 Escape 实际：isRaw=%s raw=%s（当前无 Esc 处理）" % (stc2.get("isRaw"), json.dumps(stc2.get("raw"), ensure_ascii=False)))

setmd("> 引文己行\n\n段落乙")
q_caret_end()
js("(function(){var blks=document.querySelectorAll('#editor .blk');"
   "var tgt=blks[blks.length-1];"
   "tgt.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(380)
stc3 = qstate()
_c3raw = str((stc3.get("raw") or ["", ""])[0])
check("C3[规范] 点击引用外→引用保持渲染态且 raw 不变",
      stc3.get("isRaw") is False and _c3raw == "> 引文己行",
      "inf=%s" % json.dumps(stc3, ensure_ascii=False)[:200])

note("========== D 组：引用内标题（降级目标行为） ==========")
setmd("> # 标题行\n> 正文行")
std1 = qstate()
note("D1 现状：raw=%s qblk=%d qh=%s hEditable=%s" % (
    json.dumps(std1.get("raw"), ensure_ascii=False), std1.get("qblk", -1),
    std1.get("qh"), std1.get("hEditable")))
check("D1[规范 v3.38 QUO-10] 引用内标题按字面文本行渲染（无 .qblk 富块）",
      std1.get("qblk", 0) == 0 and "# 标题行" in str(std1.get("txt", "")),
      "inf=%s" % json.dumps(std1, ensure_ascii=False)[:200])

setmd("> 正文行\n> # 粘贴来的标题\n> 尾行")
std2 = qstate()
note("D2 多行含标题引用现状：qblk=%d qh=%s raw 不漂移=%s" % (
    std2.get("qblk", -1), std2.get("qh"),
    json.dumps(std2.get("raw"), ensure_ascii=False)))

note("========== E 组：引用含内嵌代码块（qblk）时的回车 ==========")
setmd("> 前行文字\n> ```\n> code_here\n> ```\n> 后行文字")
ste0 = qstate()
note("E0 引用内代码块渲染：qblk=%d isRaw=%s raw=%s" % (
    ste0.get("qblk", -1), ste0.get("isRaw"), json.dumps(ste0.get("raw"), ensure_ascii=False)))
q_caret_end()
key_on_quote("Enter")
ste1 = qstate()
note("E1 qblk 引用行尾回车实际：isRaw=%s raw=%s" % (ste1.get("isRaw"), json.dumps(ste1.get("raw"), ensure_ascii=False)))

note("========== 汇总 ==========")
log("SUMMARY total=%d fail=%d" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABNORMAL " + a)
print("DONE total=%d fail=%d" % (TOTAL[0], FAIL[0]))
