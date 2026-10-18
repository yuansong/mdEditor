# -*- coding: utf-8 -*-
"""m113：v3.38 QUO 批次验收（对齐《引用模块交互规范-v3.37.md》）
- A 组 QUO-8 / E1：末行空行回车 → 引用保留渲染态 + 其后新建空段落
- B 组 QUO-9 / E2：末尾空行退格 → 仅删空行、引用保留
- C 组 QUO-9 / E3：多行顶层行首退格 → 仅当前行脱离；单行整块转段落（回归）
- D 组 QUO-10：引用内标题渲染统一按字面文本行（无 .qblk h）
- E 组 QUO-11：末行空行 data-ph 占位；E5 Esc 失焦；##quotetip 一次性提示
结果：tests/_m113.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtCore import QSettings

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m113.txt")
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
    lp = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        lp.quit()
    QTimer.singleShot(timeout, lp.quit)
    win._js_active(code, cb)
    lp.exec()
    return box["r"]


def wait(ms):
    lp = QEventLoop()
    QTimer.singleShot(ms, lp.quit)
    lp.exec()


def setmd(md, ms=750):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def state_now():
    r = js("(function(){var rw={};try{rw=JSON.parse(window.__raw()||'{}')}catch(e){}"
           "var bs=document.querySelectorAll('#editor .blk');var arr=[];"
           "for(var k=0;k<bs.length&&k<6;k++)arr.push({cls:bs[k].className,"
           "txt:(bs[k].textContent||'').slice(0,40)});"
           "var bq=document.querySelector('#editor blockquote');"
           "return JSON.stringify({raw:rw.raw||[],editIdx:rw.editIdx,blks:arr,"
           "ph:bq?bq.getAttribute('data-ph'):null,"
           "qblk:!!(bq&&bq.querySelector('.qblk'))})})()")
    try:
        return json.loads(r or "{}")
    except Exception:
        return {}


def caret_end():
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var rg=document.createRange();rg.selectNodeContents(bq);rg.collapse(false);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(200)


def caret_line_start(n):
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var w=document.createTreeWalker(bq,NodeFilter.SHOW_TEXT,null);"
       "var pos=0,tn=null,to=0,m;"
       "while(m=w.nextNode()){if(m.closest&&m.closest('.qblk'))continue;"
       "var v=m.nodeValue;for(var k=0;k<v.length;k++){"
       "if(pos===" + str(n) + "){tn=m;to=k;break;} pos+=v[k]==='\\n'?1:1;}"
       "if(tn)break;}"
       "if(!tn)return 'no-pos';"
       "var rg=document.createRange();rg.setStart(tn,to);rg.collapse(true);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
    wait(200)


def key_on_quote(key, ms=430, shift=False):
    js("(function(){var bq=document.querySelector('#editor blockquote');"
       "if(!bq)return 'no-bq';bq.focus();"
       "var ev=new KeyboardEvent('keydown',{key:" + json.dumps(key) +
       ",bubbles:true,cancelable:true,shiftKey:" + ("true" if shift else "false") + "});"
       "bq.dispatchEvent(ev);return 'ok'})()")
    wait(ms)


wait(2800)

note("========== A 组 QUO-8 / E1 双回车落点 ==========")
note("A1 引文 + 后续段落：双回车后引用保留、新建空段落")
setmd("> 引文甲行\n\n段落乙")
caret_end()
key_on_quote("Enter")     # 新增空行
caret_end()
key_on_quote("Enter")     # 空行回车 → 退出
wait(300)
st = state_now()
note("  A1 raw=%s" % json.dumps(st.get("raw"), ensure_ascii=False))
check("A1 引用保留且带原文", (st.get("raw") or [""])[0] == "> 引文甲行",
      json.dumps(st.get("raw"), ensure_ascii=False))
check("A1b 其后新建空段落", len(st.get("raw") or []) >= 3 and (st.get("raw") or ["", "?"])[1] == "",
      json.dumps(st.get("raw"), ensure_ascii=False))
blks = st.get("blks") or []
check("A1c 引用未切源码态", bool(blks) and "raw-edit" not in (blks[0].get("cls") or ""),
      json.dumps(blks[0] if blks else {}, ensure_ascii=False))
check("A1d 光标落新段落", st.get("editIdx") == 1,
      "editIdx=%s" % st.get("editIdx"))

note("A2 独立引用：双回车后引用 + 空段落")
setmd("> 独行")
caret_end()
key_on_quote("Enter")
caret_end()
key_on_quote("Enter")
wait(300)
st = state_now()
check("A2 独立引用双回车", (st.get("raw") or [""])[0] == "> 独行" and len(st.get("raw") or []) >= 2
      and (st.get("raw") or ["", "?"])[1] == "",
      json.dumps(st.get("raw"), ensure_ascii=False))

note("========== B 组 QUO-9 / E2 末尾空行退格 ==========")
note("B1 末尾空行退格：仅删空行，引用保留")
setmd("> 引文丙行\n>")
caret_end()
key_on_quote("Backspace")
wait(300)
st = state_now()
note("  B1 raw=%s" % json.dumps(st.get("raw"), ensure_ascii=False))
check("B1 引用保留为单行", (st.get("raw") or [""])[0] == "> 引文丙行",
      json.dumps(st.get("raw"), ensure_ascii=False))
blks = st.get("blks") or []
check("B1b 未切源码态（非整块拍平）", bool(blks) and "raw-edit" not in (blks[0].get("cls") or ""),
      json.dumps(blks[0] if blks else {}, ensure_ascii=False))

note("B2 空引用退格 → 转空段落")
setmd(">")
caret_end()
key_on_quote("Backspace")
wait(300)
st = state_now()
check("B2 空引用转空段落", (st.get("raw") or ["?"])[0] == "",
      json.dumps(st.get("raw"), ensure_ascii=False))

note("========== C 组 QUO-9 / E3 行首退格 ==========")
note("C1 多行首行退格：仅首行脱离")
setmd("> 行一\n> 行二\n\n段落乙")
caret_line_start(0)
key_on_quote("Backspace")
wait(300)
st = state_now()
note("  C1 raw=%s" % json.dumps(st.get("raw"), ensure_ascii=False))
rawc = st.get("raw") or []
check("C1 首行脱离为段落", len(rawc) >= 2 and rawc[0] == "行一" and rawc[1] == "> 行二",
      json.dumps(rawc, ensure_ascii=False))
check("C1b 其余行保持引用", bool(st.get("blks")) and "b-quote" in (st["blks"][1].get("cls") or ""),
      json.dumps(st.get("blks", [])[:2], ensure_ascii=False))

note("C2 中间行退格：引用切开")
setmd("> 行甲\n> 行乙\n> 行丙")
caret_line_start(3)   # 行乙行首（行甲=2 字符 + \n → 偏移 3）
key_on_quote("Backspace")
wait(300)
st = state_now()
note("  C2 raw=%s" % json.dumps(st.get("raw"), ensure_ascii=False))
rawc = st.get("raw") or []
check("C2 引用切开中段脱离", rawc and rawc[0] == "> 行甲" and rawc[1] == "行乙" and rawc[2] == "> 行丙",
      json.dumps(rawc, ensure_ascii=False))

note("C3 单行引用退格：整块转段落（回归）")
setmd("> 独行\n\n段落乙")
caret_line_start(0)
key_on_quote("Backspace")
wait(300)
st = state_now()
check("C3 单行整块转段落", (st.get("raw") or ["?"])[0] == "独行",
      json.dumps(st.get("raw"), ensure_ascii=False))

note("========== D 组 QUO-10 标题按字面文本行 ==========")
setmd("> 正文行\n> # 粘贴来的标题\n> 尾行")
wait(400)
st = state_now()
check("D1 中部标题无 .qblk", st.get("qblk") is False, "qblk=%s" % st.get("qblk"))
check("D1b 标题按字面文本", "# 粘贴来的标题" in json.dumps(st.get("blks"), ensure_ascii=False),
      json.dumps(st.get("blks"), ensure_ascii=False)[:160])
setmd("> # 标题行\n> 正文")
wait(400)
st = state_now()
check("D2 首行标题同样按字面", st.get("qblk") is False and "# 标题行" in json.dumps(st.get("blks"), ensure_ascii=False),
      json.dumps(st.get("blks"), ensure_ascii=False)[:160])
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "editor.html"),
           "r", encoding="utf-8").read()
check("D3 粘贴剥 # 规则在位", "#{1,6}[ \\t]+" in src.replace("\\t", "\t") or "#{1,6}" in src, "")

note("========== E 组 QUO-11 提示与可发现性 ==========")
note("E1 末行空行 data-ph 占位")
setmd("> 文字\n>")
wait(400)
st = state_now()
# v3.38（QUO-12）：提示文案明确化
check("E1 空末行显示占位", st.get("ph") == "空行上回车退出引用 · Tab 加一层 / Shift+Tab 减一层",
      "ph=%s" % st.get("ph"))
setmd("> 文字")
wait(400)
st = state_now()
check("E1b 非空末行无占位", st.get("ph") is None, "ph=%s" % st.get("ph"))

note("E2 Esc 失焦（内容不动）")
setmd("> 引文癸行\n\n段落乙")
caret_end()
js("(function(){var bq=document.querySelector('#editor blockquote');bq.focus();"
   "var ev=new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true});"
   "bq.dispatchEvent(ev);return 'ok'})()")
wait(300)
st = state_now()
check("E2 Esc 内容不动", (st.get("raw") or ["?"])[0] == "> 引文癸行",
      json.dumps(st.get("raw"), ensure_ascii=False))
check("E2b Esc 后失焦", st.get("blks") and "raw-edit" not in (st["blks"][0].get("cls") or ""),
      json.dumps(st.get("blks", [{}])[0] if st.get("blks") else {}, ensure_ascii=False))

note("E3 首次按键推 ##quotetip（Python 侧 QSettings 只提示一次）")
setmd("> 引文子行")
caret_end()
js("window.__quoTipReset ? window.__quoTipReset() : ''; window.takeToast()")   # 复位会话标志 + 清残留
tst = js("(function(){var bq=document.querySelector('#editor blockquote');"
         "if(!bq)return 'no-bq';bq.focus();"
         "bq.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));"
         "return window.takeToast()})()") or ""   # v3.38 甄别：同帧派发+读取，避开壳轮询竞态
wait(300)
check("E3 通道推 ##quotetip", tst == "##quotetip", "toast=%s" % tst)
win._on_toast("##quotetip")
qs = QSettings("WorkBuddy", "WorkBuddyMarkdown")
check("E3b QSettings 记已读", qs.value("quoteTipShown", False, type=bool) is True, "")
win._on_toast("##quotetip")
qs.remove("quoteTipShown")   # 恢复：真实用户仍可收到首次提示
note("  E3 已清理 quoteTipShown")

note("========== 汇总 ==========")
log("SUMMARY total=%d fail=%d" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABN " + a)
print("DONE total=%d fail=%d" % (TOTAL[0], FAIL[0]))
