# -*- coding: utf-8 -*-
"""m119 NEST-1 交叉嵌套自愈 GUI 验收（v3.38）

用户报告：==<u>aswefasfdf==</u> 转标题后源码变 ### <u>==<u>aswefasfdf</u>==</u>，
== 与 <u> 交叉嵌套导致渲染字面化。根因：parseInline「区间内搜闭合」模型解析不了
交叉态。修复：setMarkdown / commitEdit / commitEditSilent 三处咽喉点挂 healBlockRaw
（token 级栈式重排 + 后继闭合符降序重开 + 紧邻残对剪枝 + 行内码掩码）。

验收组：
  N1-N4 载入自愈：段落 / 标题 / 级联 / 尾部残余 → 交叉态重排为合法嵌套
  N5-N6 合法内容与行内码：逐字节不动
  N7    自愈后渲染保真（mark>u 真元素、无字面 &lt;u&gt;）+ 交叉态上再套下划线不恶化
  N8    编辑态提交自愈（commitEdit 路径，dblclick 进入源码态改出交叉再提交）
结果：tests/_m119.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m119.txt")
out = []
FAIL = [0]
TOTAL = [0]


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


wait(2800)
js("window.__errs=[];window.onerror=function(m){window.__errs.push(String(m))};")

# ---------- N1 载入自愈：段落 ----------
setmd("==<u>aswefasfdf==</u>")
g = getraw()
check("N1a 段落交叉态载入自愈 raw", g and g[0] == "==<u>aswefasfdf</u>==",
      "raw=%s" % json.dumps(g, ensure_ascii=False))
r = jj("(function(){var p=document.querySelector('#editor p');"
       "return JSON.stringify({mark:!!(p&&p.querySelector('mark')),u:!!(p&&p.querySelector('u')),"
       "lit:p?p.innerHTML.indexOf('&lt;u')>=0:true})})()")
check("N1b 渲染为真 mark>u 元素（无字面标签）", r.get("mark") and r.get("u") and not r.get("lit"),
      "dom=%s" % json.dumps(r, ensure_ascii=False))

# ---------- N2 载入自愈：标题（用户原始复现） ----------
setmd("### ==<u>aswefasfdf==</u>")
g = getraw()
check("N2 标题交叉态自愈（用户复现）", g and g[0] == "### ==<u>aswefasfdf</u>==",
      "raw=%s" % json.dumps(g, ensure_ascii=False))
r = jj("(function(){var h=document.querySelector('#editor h3');"
       "return JSON.stringify({mark:!!(h&&h.querySelector('mark')),u:!!(h&&h.querySelector('u')),"
       "lit:h?h.innerHTML.indexOf('&lt;u')>=0:true})})()")
check("N2b 标题渲染无字面标签", r.get("mark") and r.get("u") and not r.get("lit"),
      "dom=%s" % json.dumps(r, ensure_ascii=False))

# ---------- N3 级联交叉 ----------
setmd("==<u>**x==</u>**")
g = getraw()
check("N3 级联交叉自愈", g and g[0] == "==<u>**x**</u>==",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

# ---------- N4 尾部残余 ----------
setmd("==<u>ab==cd</u>")
g = getraw()
check("N4 闭合后残余 → 拆段重排", g and g[0] == "==<u>ab</u>==<u>cd</u>",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

# ---------- N5 合法内容不动 ----------
setmd("==<u>x</u>==\n\n**a ~~b ==c== ~~**")
g = getraw()
check("N5 合法嵌套逐字节不动",
      g[:2] == ["==<u>x</u>==", "**a ~~b ==c== ~~**"],
      "raw=%s" % json.dumps(g, ensure_ascii=False))

# ---------- N6 行内码内交叉不动 ----------
setmd("前文\n\n`==<u>x==</u>`\n\n尾段")
g = getraw()
check("N6 行内码内交叉保持字面", g and g[1] == "`==<u>x==</u>`",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

# ---------- N7 自愈后渲染选区套下划线 → 不恶化 ----------
setmd("==<u>ab==cd</u>")
g = getraw()   # 已自愈为 ==<u>ab</u>==<u>cd</u>
r = js("(function(){var p=document.querySelector('#editor p');"
       "var rg=document.createRange();rg.selectNodeContents(p);"
       "var s2=getSelection();s2.removeAllRanges();s2.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
wait(300)
js("window.__applyFloat('underline')")
wait(500)
g = getraw()
# 全选含 == 边界，可能拒绝或成功包裹；断言：结果不得再出现交叉（可用单测思路粗检：无 '<u>' 紧跟 '==' 交叉模式）
r = jj("(function(){var p=document.querySelector('#editor p');"
       "return JSON.stringify({u:!!(p&&p.querySelector('u')),"
       "lit:p?p.innerHTML.indexOf('&lt;u')>=0:true,txt:p?p.textContent:''})})()")
check("N7 交叉态上再套格式：渲染无字面标签", r.get("u") and not r.get("lit"),
      "raw=%s dom=%s" % (json.dumps(g, ensure_ascii=False), json.dumps(r, ensure_ascii=False)))

# ---------- N8 编辑态提交自愈（commitEdit 路径） ----------
setmd("甲块\n\n乙块")
# 进编辑态入口是 ED 上的 mousedown（单击渲染块）→ enterEdit
js("(function(){var el=document.querySelectorAll('#editor .blk')[0];"
   "var rc=el.getBoundingClientRect();"
   "el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
   "clientX:rc.left+rc.width/2,clientY:rc.top+rc.height/2}));return 'ok'})()")
wait(400)
r = jj("(function(){var e=document.querySelector('#editor .raw-edit');"
       "if(!e)return JSON.stringify({ed:false});"
       "e.textContent='==<u>ab==cd</u>';"
       "e.dispatchEvent(new Event('input',{bubbles:true}));"
       "return JSON.stringify({ed:true})})()")
check("N8a 进入源码态并写入交叉文本", r.get("ed") is True, "r=%s" % json.dumps(r, ensure_ascii=False))
# 切到另一块触发 commitEdit（同样用 mousedown）
js("(function(){var els=document.querySelectorAll('#editor .blk');"
   "var t=els.length>1?els[1]:els[0];var rc=t.getBoundingClientRect();"
   "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,"
   "clientX:rc.left+rc.width/2,clientY:rc.top+rc.height/2}));return 'ok'})()")
wait(500)
g = getraw()
check("N8b commitEdit 提交时自愈", g and g[0] == "==<u>ab</u>==<u>cd</u>",
      "raw=%s" % json.dumps(g, ensure_ascii=False))

errs = js("JSON.stringify(window.__errs)")
check("Z0 全程无 JS 异常", errs in ("[]", "[]"), "errs=%s" % errs)

note("PASS=%d FAIL=%d" % (TOTAL[0] - FAIL[0], FAIL[0]))
