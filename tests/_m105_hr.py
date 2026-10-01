# -*- coding: utf-8 -*-
"""m105 分割线（Divider / hr）组件系统排查

覆盖：渲染与语法变体、视觉规范计算值、插入入口、选中态与删除、键盘与边界、
      源码/深色模式、导出表现。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m105_hr.txt")
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


def rawlist():
    return jj("(function(){try{return JSON.parse(window.__raw()||'{}').raw||[]}catch(e){return []}})()")


def hrshape():
    """返回每块的类型/是否 hr/是否 hrsel"""
    return jj("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
              "return JSON.stringify({n:bs.length,shape:bs.map(function(b){"
              "var h=b.querySelector('hr');"
              "return (h?'HR':'--')+(h&&h.classList.contains('hrsel')?'*':'')+'|'+b.className"
              "+(b.classList.contains('raw-edit')?'|RAW':'')})})})()")


def hrcss():
    """首个 hr 的计算样式"""
    return jj("(function(){var h=document.querySelector('#editor hr');"
              "if(!h)return JSON.stringify({none:1});"
              "var c=getComputedStyle(h);var r=h.getBoundingClientRect();"
              "return JSON.stringify({btw:c.borderTopWidth,btc:c.borderTopColor,"
              "mt:c.marginTop,mb:c.marginBottom,w:Math.round(r.width),h:Math.round(r.height),"
              "disp:c.display,border:c.borderTopStyle})})()")


def click_hr(idx=0):
    """点击第 idx 个 hr 元素（mousedown + click）"""
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


note("========== A 组：语法变体渲染 ==========")
VARIANTS = [("三连字符", "---"), ("三连星号", "***"), ("三连下划线", "___"),
            ("四连字符", "----"), ("空格分隔", "- - -"), ("缩进三连", "   ---")]
for name, syn in VARIANTS:
    setmd("前段\n\n" + syn + "\n\n尾段")
    s = hrshape()
    ishr = any(x.startswith("HR") for x in s.get("shape", []))
    check("A[%s] `%s` 渲染为 hr" % (name, syn), ishr,
          "shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:200])

note("========== B 组：视觉规范计算值 ==========")
setmd("前段\n\n---\n\n尾段")
css = hrcss()
note("  css=%s" % json.dumps(css, ensure_ascii=False))
check("B1 线粗为 1px", css.get("btw") == "1px", "btw=%s" % css.get("btw"))
check("B2 线型为 solid", str(css.get("border")) == "solid", "border=%s" % css.get("border"))
check("B3 上下外边距 2em（32px @16px 根字号）",
      css.get("mt") == "32px" and css.get("mb") == "32px",
      "mt=%s mb=%s" % (css.get("mt"), css.get("mb")))
check("B4 颜色取自 --border 变量（浅色 #e9ecef → rgb(233,236,239)）",
      css.get("btc") == "rgb(233, 236, 239)", "btc=%s" % css.get("btc"))
w = css.get("w")
check("B5 横向铺满栏宽", isinstance(w, int) and w > 200, "w=%s" % w)

note("========== C 组：插入入口 ==========")
setmd("前段")
note("  C1 / 菜单项存在性：%s" %
     js("(function(){var m=window.__slashIds?String(window.__slashIds()):'n/a';return m})()"))
# C2：通过块插入动作（与 / 菜单同源的 applySlash 分支）
js("(function(){var f=window.__applyFloat;return 'has='+(typeof f)})()")
r0 = js("(function(){"
        "var b=document.querySelector('#editor .blk');if(!b)return 'noblk';"
        "b.focus&&b.focus();"
        "var rg=document.createRange();rg.selectNodeContents(b);rg.collapse(false);"
        "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
        "return 'sel'})()")
wait(300)
before = rawlist()
# 走 / 菜单触发链：模拟输入 /
js("(function(){var b=document.querySelector('#editor .blk');"
   "if(!b)return 'noblk';"
   "var ev=new InputEvent('beforeinput',{bubbles:true,inputType:'insertText',data:'/'});"
   "b.dispatchEvent(ev);return 'ok'})()")
wait(500)
slash = js("(function(){var p=document.getElementById('slash');"
           "if(!p)return 'noslash';"
           "var items=[].slice.call(p.querySelectorAll('[data-k],[data-id],.it,.item'));"
           "return JSON.stringify({show:p.classList.contains('show'),"
           "n:items.length,txt:items.map(function(i){return (i.textContent||'').slice(0,12)}).slice(0,20)})})()")
note("  slash=%s" % str(slash)[:400])
has_hr = "分割线" in str(slash) or "hr" in str(slash)
check("C2 / 菜单含「分割线」项", has_hr, "slash=%s" % str(slash)[:300])
js("(function(){var p=document.getElementById('slash');if(p)p.classList.remove('show')})()")

note("  C3 走 applySlash('hr') 直接插入")
setmd("前段")
r_ins = js("(function(){"
           "var b=document.querySelector('#editor .blk');if(!b)return 'noblk';"
           "b.setAttribute('contenteditable','plaintext-only');b.focus();"
           "var rg=document.createRange();rg.selectNodeContents(b);rg.collapse(false);"
           "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
           "return 'ok'})()")
wait(300)
note("  C3 前置=%s" % r_ins)
# 用 Ctrl+Shift+- 对应的 QAction 触发（主程序菜单）
act = None
for a in win.findChildren(__import__("PySide6.QtGui", fromlist=["QAction"]).QAction):
    if "分割线" in (a.text() or "") or "分割线" in (a.toolTip() or ""):
        act = a
        break
note("  C3 找到主程序动作：%s" % (act.text() if act else "None"))
if act:
    act.trigger()
    wait(700)
    rl = rawlist()
    note("  C3 插入后 raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])
    check("C3 插入动作产出 `---` 块", "---" in rl, "raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])
else:
    check("C3 插入动作产出 `---` 块", False, "未找到主程序分割线动作")

note("========== D 组：选中态与删除 ==========")
setmd("前段\n\n---\n\n尾段")
click_hr(0)
wait(400)
s = hrshape()
check("D1 点击分割线进入选中态（hrsel）",
      any(x.startswith("HR*") for x in s.get("shape", [])),
      "shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:200])

note("  D2 点击其它块取消选中")
js("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
   "var t=bs[bs.length-1];if(!t)return 'no';"
   "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
wait(400)
s = hrshape()
check("D2 点击其它位置取消选中",
      not any(x.startswith("HR*") for x in s.get("shape", [])),
      "shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:200])

note("  D3 Esc 取消选中（HR-4 注释声称支持）")
click_hr(0)
wait(400)
pre_esc = hrshape()
key("Escape")
wait(400)
post_esc = hrshape()
check("D3 Esc 取消分割线选中态",
      not any(x.startswith("HR*") for x in post_esc.get("shape", [])),
      "pre=%s post=%s" % (json.dumps(pre_esc.get("shape"), ensure_ascii=False)[:160],
                          json.dumps(post_esc.get("shape"), ensure_ascii=False)[:160]))

note("  D4 Delete 删除分割线")
click_hr(0)
wait(400)
key("Delete")
wait(600)
rl = rawlist()
check("D4 Delete 删除整条分割线", "---" not in rl, "raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])

note("  D5 Backspace 删除分割线")
setmd("前段\n\n---\n\n尾段")
click_hr(0)
wait(400)
key("Backspace")
wait(600)
rl = rawlist()
check("D5 Backspace 删除整条分割线", "---" not in rl, "raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])

note("  D6 删除后可撤销")
js("(function(){try{return String(typeof window.__undo)}catch(e){return 'n/a'}})()")
win._js_active("(function(){"
               "var t=document.querySelector('#editor');"
               "t.focus();return 'ok'})()", lambda r: None)
wait(300)
try:
    win.undo()
    wait(700)
    rl = rawlist()
    note("  D6 撤销后 raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])
    check("D6 删除后可撤销恢复", "---" in rl, "raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])
except Exception as ex:
    check("D6 删除后可撤销恢复", False, "undo 异常 %s" % ex)

note("========== E 组：键盘与边界 ==========")
note("  E1 文档末尾是分割线时的导航进入")
setmd("前段\n\n---")
js("window.setMarkdown(" + json.dumps("前段\n\n---") + ")")
wait(700)
js("(function(){var f=window.__goToBlock||window.goToBlock;"
   "if(typeof f!=='function')return 'nofn';"
   "f(1,'end');return 'ok'})()")
wait(600)
s = hrshape()
note("  E1 shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:240])
rl = rawlist()
note("  E1 raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])
check("E1 末尾分割线导航不切入源码态", s.get("shape") and "RAW" not in s["shape"][-1],
      "shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:240])

note("  E2 空段 Backspace 删除上方分割线（HR-3）")
setmd("前段\n\n---\n\n")
js("window.setMarkdown(" + json.dumps("前段\n\n---\n\n") + ")")
wait(700)
last = js("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
          "return String(bs.length)})()")
note("  E2 块数=%s" % last)
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
rl = rawlist()
note("  E2 删后 raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])
check("E2 空段 Backspace 删除上方分割线", "---" not in rl,
      "raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])

note("  E3 单元格内禁止插入分割线（7078）")
setmd("| a | b |\n|---|---|\n| 1 | 2 |")
cellok = js("(function(){var td=document.querySelector('#editor td');"
            "if(!td)return 'notd';"
            "var f=window.__applySlash||window.applyBlockInsert||null;"
            "return 'td-ok'})()")
note("  E3 单元格探测=%s" % cellok)

note("  E4 连续多条分割线")
setmd("---\n\n---\n\n---")
s = hrshape()
nhr = len([x for x in s.get("shape", []) if x.startswith("HR")])
check("E4 连续三条分割线各自独立渲染", nhr == 3, "nhr=%s shape=%s" % (nhr, json.dumps(s.get("shape"), ensure_ascii=False)[:200]))

note("  E5 引用内分割线")
setmd("> 引文\n>\n> ---\n>\n> 后文")
s = hrshape()
rl = rawlist()
note("  E5 shape=%s raw=%s" % (json.dumps(s.get("shape"), ensure_ascii=False)[:200],
                               json.dumps(rl, ensure_ascii=False)[:200]))

note("========== F 组：模式与主题 ==========")
setmd("前段\n\n---\n\n尾段")
win._set_mode("src")
wait(1200)
s = hrshape()
note("  F1 源码模式 shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:240])
check("F1 源码模式下分割线不再渲染为 hr（呈源码文本）",
      not any(x.startswith("HR") for x in s.get("shape", [])),
      "shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:240])
win._set_mode("edit")
wait(1200)
rl = rawlist()
check("F2 模式往返后 raw 不漂移", rl == ["前段", "---", "尾段"],
      "raw=%s" % json.dumps(rl, ensure_ascii=False)[:200])

note("  F3 深色模式下 --border 生效")
js("document.body.setAttribute('data-theme','dark')")
wait(500)
css_d = hrcss()
note("  F3 dark css=%s" % json.dumps(css_d, ensure_ascii=False))
check("F3 深色模式分割线颜色随主题（#2e343b → rgb(46,52,59)）",
      css_d.get("btc") == "rgb(46, 52, 59)", "btc=%s" % css_d.get("btc"))
js("document.body.removeAttribute('data-theme')")
wait(400)

note("========== G 组：导出表现 ==========")
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
    import exporters
    b = exporters.parse_blocks("前段\n\n---\n\n尾段")
    kinds = [x.get("kind") for x in b]
    note("  G1 parse_blocks kinds=%s" % json.dumps(kinds, ensure_ascii=False))
    check("G1 导出解析识别 hr 块", "hr" in kinds, "kinds=%s" % json.dumps(kinds, ensure_ascii=False))
    csss = exporters._EPUB_CSS
    check("G2 导出样式表含 hr 规则", "hr{" in csss or "hr {" in csss,
          "含hr=%s" % ("hr" in csss))
    note("  G2 导出 hr 规则=%s" % [l for l in csss.split("\n") if l.strip().startswith("hr")])
    check("G3 导出 hr 颜色为硬编码 #ddd（不随编辑器主题）",
          "#ddd" in csss, "观察项：导出配色固定")
except Exception as ex:
    check("G1 导出解析识别 hr 块", False, "exporters 导入/调用异常 %s" % ex)

log("\n==== 合计 %d 项，FAIL %d ====" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABNORMAL " + a)
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
