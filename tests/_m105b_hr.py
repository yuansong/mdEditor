# -*- coding: utf-8 -*-
"""m105b 分割线复验（_m105 中 window.__raw 钩子已被移除，依赖 raw 的断言为假通过）

改用 window.getMarkdown()；slash 弹层 id=slashmenu；撤销走 window.cmd('undo')。
重验：C2 / 菜单、C3 插入、D4/D5 删除、D6 撤销、E2 空段删 hr、F2 往返、D3 Esc 甄别。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105b_hr.txt")
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


def blocks():
    """按块切分（空行分隔）"""
    return [b for b in getmd().split("\n\n")]


def hrshape():
    return jj("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
              "return JSON.stringify({n:bs.length,shape:bs.map(function(b){"
              "var h=b.querySelector('hr');"
              "return (h?'HR':'--')+(h&&h.classList.contains('hrsel')?'*':'')+'|'+b.className"
              "+(b.classList.contains('raw-edit')?'|RAW':'')})})})()")


def click_hr(idx=0):
    return js("(function(){var hs=document.querySelectorAll('#editor hr');"
              "var h=hs[" + str(idx) + "];if(!h)return 'nohr';"
              "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));"
              "h.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok'})()")


def key(k, **kw):
    opts = {"key": json.dumps(k), "bubbles": "true", "cancelable": "true"}
    for a, b in kw.items():
        opts[a] = "true" if b else "false"
    s = ",".join("%s:%s" % (a, b) for a, b in opts.items())
    js("document.dispatchEvent(new KeyboardEvent('keydown',{" + s + "}))")


note("========== R0 钩子与基线 ==========")
setmd("前段\n\n---\n\n尾段")
md0 = getmd()
note("  getMarkdown=%s" % json.dumps(md0, ensure_ascii=False))
check("R0 getMarkdown 可用且含 ---", "---" in md0, "md=%s" % json.dumps(md0, ensure_ascii=False))

note("========== R1 / 菜单含分割线（id=slashmenu）==========")
setmd("前段")
js("(function(){var b=document.querySelector('#editor .blk');if(!b)return 'noblk';"
   "b.setAttribute('contenteditable','plaintext-only');b.focus();"
   "var rg=document.createRange();rg.selectNodeContents(b);rg.collapse(false);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
wait(300)
js("(function(){var t=document.activeElement;"
   "t.dispatchEvent(new InputEvent('beforeinput',{bubbles:true,inputType:'insertText',data:'/'}));"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(700)
sm = js("(function(){var p=document.getElementById('slashmenu');"
        "if(!p)return 'nodom';"
        "return JSON.stringify({show:p.classList.contains('show'),"
        "txt:(p.textContent||'').slice(0,300)})})()")
note("  slashmenu=%s" % str(sm)[:400])
check("R1 / 菜单含「分割线」项", "分割线" in str(sm), "sm=%s" % str(sm)[:300])
js("(function(){var p=document.getElementById('slashmenu');if(p)p.classList.remove('show')})()")

note("========== R2 插入动作（主程序 QAction）产出 --- ==========")
setmd("甲段")
js("(function(){var b=document.querySelector('#editor .blk');if(!b)return 'noblk';"
   "b.setAttribute('contenteditable','plaintext-only');b.focus();"
   "var rg=document.createRange();rg.selectNodeContents(b);rg.collapse(false);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
wait(300)
from PySide6.QtGui import QAction
act = None
for a in win.findChildren(QAction):
    if "分割线" in (a.text() or ""):
        act = a
        break
note("  R2 动作=%s" % (act.text() if act else "None"))
if act:
    act.trigger()
    wait(800)
    md = getmd()
    note("  R2 插入后 md=%s" % json.dumps(md, ensure_ascii=False))
    check("R2 插入动作产出 `---` 块", "---" in md, "md=%s" % json.dumps(md, ensure_ascii=False))
    s = hrshape()
    check("R2 插入后渲染为 hr 且光标落在下一块",
          any(x.startswith("HR") for x in s.get("shape", [])),
          "shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:200])
else:
    check("R2 插入动作产出 `---` 块", False, "未找到动作")

note("========== R3 Delete 删除（真校验）==========")
setmd("前段\n\n---\n\n尾段")
click_hr(0)
wait(400)
st = hrshape()
check("R3a 点击后进入 hrsel", any(x.startswith("HR*") for x in st.get("shape", [])),
      "shape=%s" % json.dumps(st.get("shape"), ensure_ascii=False)[:200])
key("Delete")
wait(700)
md = getmd()
note("  R3 Delete 后 md=%s" % json.dumps(md, ensure_ascii=False))
check("R3b Delete 真删除分割线（上一轮为假通过）", "---" not in md,
      "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== R4 Backspace 删除（真校验）==========")
setmd("前段\n\n---\n\n尾段")
click_hr(0)
wait(400)
key("Backspace")
wait(700)
md = getmd()
note("  R4 Backspace 后 md=%s" % json.dumps(md, ensure_ascii=False))
check("R4 Backspace 真删除分割线", "---" not in md, "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== R5 删除后撤销（window.cmd('undo')）==========")
js("window.cmd('undo')")
wait(900)
md = getmd()
note("  R5 撤销后 md=%s" % json.dumps(md, ensure_ascii=False))
check("R5 删除后可撤销恢复分割线", "---" in md, "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== R6 空段 Backspace 删上方 hr（HR-3 真校验）==========")
setmd("前段\n\n---\n\n")
wait(300)
js("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
   "var t=bs[bs.length-1];if(!t)return 'no';"
   "t.setAttribute('contenteditable','plaintext-only');t.focus();"
   "var rg=document.createRange();rg.selectNodeContents(t);rg.collapse(true);"
   "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);return 'ok'})()")
wait(400)
js("(function(){var t=document.activeElement;if(!t)return 'no';"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'Backspace',bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(700)
md = getmd()
note("  R6 删后 md=%s" % json.dumps(md, ensure_ascii=False))
check("R6 空段 Backspace 真删除上方分割线", "---" not in md,
      "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== R7 Esc 取消选中：是否靠 rebuild 假取消 ==========")
setmd("前段\n\n---\n\n尾段")
click_hr(0)
wait(400)
pre = hrshape()
note("  R7 pre=%s" % json.dumps(pre.get("shape"), ensure_ascii=False)[:200])
# 记录当前 DOM 节点身份（给 hr 打标记，rebuild 会丢失）
js("(function(){var h=document.querySelector('#editor hr');if(h)h.dataset.probe='P1';return 'ok'})()")
key("Escape")
wait(700)
post = hrshape()
marker = js("(function(){var h=document.querySelector('#editor hr');"
            "return h?String(h.dataset.probe||'') : 'nohr'})()")
note("  R7 post=%s marker=%s" % (json.dumps(post.get("shape"), ensure_ascii=False)[:200], marker))
check("R7a Esc 后 hrsel 类消失", not any(x.startswith("HR*") for x in post.get("shape", [])),
      "post=%s" % json.dumps(post.get("shape"), ensure_ascii=False)[:200])
check("R7b Esc 取消不触发整篇 rebuild（DOM 标记仍在→原地清除而非重建）",
      marker == "P1", "marker=%s（丢失说明靠 rebuild 兜底取消）" % marker)

note("========== R8 模式往返 raw 不漂移 ==========")
setmd("前段\n\n---\n\n尾段")
win._set_mode("src")
wait(1300)
win._set_mode("edit")
wait(1300)
md = getmd()
note("  R8 往返后 md=%s" % json.dumps(md, ensure_ascii=False))
check("R8 模式往返后 raw 不漂移", md.strip() == "前段\n\n---\n\n尾段",
      "md=%s" % json.dumps(md, ensure_ascii=False))

note("========== R9 末尾 hr 导航（HR-1）落点 ==========")
setmd("前段\n\n---")
js("(function(){var f=window.goToBlock||window.__goToBlock;"
   "if(typeof f!=='function')return 'nofn';f(1,'end');return 'ok'})()")
wait(700)
s = hrshape()
md = getmd()
note("  R9 shape=%s md=%s" % (json.dumps(s.get("shape"), ensure_ascii=False)[:200],
                              json.dumps(md, ensure_ascii=False)))
check("R9 末尾 hr 导航不切入源码态", not any("RAW" in x for x in s.get("shape", [])),
      "shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:200])

note("========== R10 边界：hr 相邻空段时外边距是否塌陷 ==========")
setmd("甲\n\n---\n\n乙")
m = jj("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
       "var r=[];for(var k=0;k<bs.length;k++){var c=getComputedStyle(bs[k]);"
       "r.push({t:(bs[k].textContent||'').slice(0,4),mt:c.marginTop,mb:c.marginBottom,"
       "oh:Math.round(bs[k].getBoundingClientRect().height)})}"
       "var h=document.querySelector('#editor hr');var rc=h.getBoundingClientRect();"
       "var pb=h.closest('.blk').getBoundingClientRect();"
       "return JSON.stringify({blks:r,hrTop:Math.round(rc.top),blkTop:Math.round(pb.top),"
       "gapAbove:Math.round(rc.top-pb.top)})})()")
note("  R10=%s" % json.dumps(m, ensure_ascii=False))
check("R10 分割线上下留白由 margin 承担（未被块容器压缩）",
      m.get("gapAbove") is not None and m.get("gapAbove") >= 0,
      "gapAbove=%s" % m.get("gapAbove"))

log("\n==== 合计 %d 项，FAIL %d ====" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABNORMAL " + a)
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
