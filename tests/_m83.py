# -*- coding: utf-8 -*-
"""m83：v3.31.2 功能批次探针（9 项改动点回归）
B1 h1 居中按钮 toggle + <h1 align="center"> 持久化 + 渲染/大纲/映射贯通
B2 浮动栏尾部「标题 1 · 已选 N 字」+ 居中按钮出现在清除格式之前
B3 双栏首进源码层守卫（rebuild 不再摧毁 src-wrap）
B4 行首空格可见（pre-wrap）
B5 段首缩进 setParaIndent
B6 标题 1 全局居中 setH1Center（渲染层 + 源码高亮层）
B7 tagForm 标题块行内格式映射（居中标题内加粗）
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

# 先复位本批涉及 QSettings（跨运行持久化）
try:
    from PySide6.QtCore import QSettings
    _qs = QSettings("WorkBuddy", "WorkBuddyMarkdown")
    for k in ("outlineWords", "paraIndent", "h1Center", "treeRoot"):
        _qs.remove(k)
    _qs.sync()
except Exception:
    pass

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m83.txt")
LINES = []
def log(s): LINES.append(str(s))
def check(name, cond, extra=""):
    LINES.append(("PASS | " if cond else "FAIL | ") + name + ("" if cond else " | " + str(extra)[:200]))

def js(win, code, timeout=8000):
    res = {"v": None, "done": False}
    def cb(r):
        res["v"] = r; res["done"] = True
    win._js_active(code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)
    return res["v"]

def jsv(win, view, code, timeout=8000):
    res = {"v": None, "done": False}
    def cb(r):
        res["v"] = r; res["done"] = True
    win._js_view(view, code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)
    return res["v"]

def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)

def setmd(win, md):
    js(win, "window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(500)

def md0(win):
    return js(win, "window.getMarkdown()") or ""

def sel_all_blk0(win):
    js(win, """(function(){var b=document.querySelectorAll('#editor .blk')[0];
if(!b)return 'no-blk';var rg=document.createRange();rg.selectNodeContents(b);
var s=window.getSelection();s.removeAllRanges();s.addRange(rg);
document.dispatchEvent(new Event('selectionchange'));return 'ok'})()""")
    wait(400)

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"): break
        wait(500)

    # ---------- B1: h1 居中按钮 ----------
    setmd(win, "# 标题甲")
    sel_all_blk0(win)
    js(win, "window.__applyFloat('h1center')"); wait(500)
    r = md0(win)
    check("B1.1 h1center 居中 → <h1 align=\"center\"> 存储形态",
          r == '<h1 align="center">标题甲</h1>', r)
    h = js(win, """(function(){var h=document.querySelector('#editor h1');
return h ? (h.getAttribute('align') || '') : 'no-h1'})()""")
    check("B1.2 渲染层 h1 带 align=center", h == "center", h)
    r = js(win, "JSON.stringify(window.getOutline().map(function(o){return o.text}))")
    check("B1.3 tagForm 标题的大纲文本已剥壳", json.loads(r or "[]") == ["标题甲"], r)
    js(win, "window.__applyFloat('h1center')"); wait(500)
    check("B1.4 再次点击还原 # 形式", md0(win) == "# 标题甲", md0(win))

    # ---------- B7: tagForm 内行内格式映射（居中态下加粗） ----------
    sel_all_blk0(win)
    js(win, "window.__applyFloat('h1center')"); wait(500)
    sel_all_blk0(win)
    js(win, "window.__applyFloat('bold')"); wait(500)
    check("B7.1 居中标题内加粗落位正确",
          md0(win) == '<h1 align="center">**标题甲**</h1>', md0(win))
    sel_all_blk0(win)
    js(win, "window.__applyFloat('bold')"); wait(500)
    check("B7.2 toggle 取消还原居中裸标题",
          md0(win) == '<h1 align="center">标题甲</h1>', md0(win))
    js(win, "window.__applyFloat('h1center')"); wait(500)   # 还原 # 形式
    check("B7.3 还原回 # 标题甲", md0(win) == "# 标题甲", md0(win))

    # ---------- B2: 浮动栏尾部标识 + 居中按钮位次 ----------
    setmd(win, "# 演示标题内容")
    sel_all_blk0(win)
    wait(500)
    fb = js(win, """(function(){var f=document.getElementById('floatbar');
if(!f||!f.classList.contains('show'))return 'no-fb';
var c=f.querySelector('.fbcnt');
var btns=[].slice.call(f.querySelectorAll('button')).map(function(b){return b.title||''});
return JSON.stringify({cnt:c?c.textContent:'', titles:btns})})()""")
    try:
        fbj = json.loads(fb or "{}")
    except Exception:
        fbj = {}
    check("B2.1 尾部显示「标题 1 · 已选 N 字」",
          (fbj.get("cnt") or "").startswith("标题 1 · 已选 "), fbj.get("cnt"))
    ti = fbj.get("titles") or []
    check("B2.2 居中按钮在清除格式之前",
          "标题居中" in ti and "清除格式" in ti and ti.index("标题居中") < ti.index("清除格式"),
          str(ti))
    # 普通段落：无标题标识、无居中按钮
    setmd(win, "普通段落文字")
    sel_all_blk0(win)
    wait(500)
    fb = js(win, """(function(){var f=document.getElementById('floatbar');
if(!f||!f.classList.contains('show'))return 'no-fb';
var c=f.querySelector('.fbcnt');
var btns=[].slice.call(f.querySelectorAll('button')).map(function(b){return b.title||''});
return JSON.stringify({cnt:c?c.textContent:'', titles:btns})})()""")
    try:
        fbj = json.loads(fb or "{}")
    except Exception:
        fbj = {}
    check("B2.3 段落尾部仍是「已选 N 字」（无标题标识）",
          (fbj.get("cnt") or "").startswith("已选 "), fbj.get("cnt"))
    check("B2.4 段落无居中按钮", "标题居中" not in (fbj.get("titles") or []), str(fbj.get("titles")))

    # ---------- B4: 行首空格可见 ----------
    setmd(win, "  缩进段落文字")
    r = js(win, """(function(){var b=document.querySelector('#editor .blk p');
if(!b)return 'no-p';
var cs=getComputedStyle(b);
return JSON.stringify({ws:cs.whiteSpace})})()""")
    try:
        rb = json.loads(r or "{}")
    except Exception:
        rb = {}
    check("B4.1 渲染段落 white-space:pre-wrap", rb.get("ws") == "pre-wrap", rb)
    check("B4.2 行首空格存储保留", md0(win) == "  缩进段落文字", md0(win))

    # ---------- B5: 段首缩进 ----------
    js(win, "window.setParaIndent(2)"); wait(300)
    r = js(win, """(function(){var b=document.querySelector('#editor .blk p');
return b ? getComputedStyle(b).textIndent : 'no-p'})()""")
    _ti_ok = (r == "2em") or (isinstance(r, str) and r.endswith("px") and float(r[:-2]) > 0)
    check("B5.1 setParaIndent(2) → text-indent 2em（计算值 2×字号）", _ti_ok, r)
    js(win, "window.setParaIndent(0)"); wait(300)
    r = js(win, """(function(){var b=document.querySelector('#editor .blk p');
return b ? getComputedStyle(b).textIndent : 'no-p'})()""")
    check("B5.2 setParaIndent(0) 复位", r in ("0px", "auto", "0em"), r)

    # ---------- B6: 标题 1 全局居中 ----------
    setmd(win, "# 一级标题\n\n正文段落")
    js(win, "window.setH1Center(true)"); wait(400)
    r = js(win, """(function(){var h=document.querySelector('#editor h1');
var p=document.querySelector('#editor .blk p');
return JSON.stringify({hc:h?getComputedStyle(h).textAlign:'', pc:p?getComputedStyle(p).textAlign:'', cls:document.body.classList.contains('h1-center')})})()""")
    try:
        rj = json.loads(r or "{}")
    except Exception:
        rj = {}
    check("B6.1 h1Center 开 → h1 居中、段落不受影响",
          rj.get("hc") == "center" and rj.get("pc") != "center" and rj.get("cls") is True, rj)
    # 源码模式：h1 行为块级居中容器
    js(win, "window.setSourceMode(true)"); wait(500)
    r = js(win, """(function(){var c=document.querySelector('.src-hl .h-h1c');
return c ? getComputedStyle(c).display + '|' + getComputedStyle(c).textAlign : 'no-h1c'})()""")
    check("B6.2 源码高亮层 h1 行居中（display:block + center）", r == "block|center", r)
    js(win, "window.setSourceMode(false)"); wait(500)
    js(win, "window.setH1Center(false)"); wait(300)
    r = js(win, """(function(){var h=document.querySelector('#editor h1');
return h ? getComputedStyle(h).textAlign : 'no-h1'})()""")
    check("B6.3 关闭后恢复向左", r != "center", r)

    # ---------- B3: 双栏首进源码层守卫 ----------
    win._set_mode("dual")
    wait(6000)   # 等待 src/prev 视图加载 + pending 推送
    ok = False
    extra = "no view"
    if win._view_src is not None:
        for _ in range(20):
            if jsv(win, win._view_src, "!!window.setMarkdown"): break
            wait(500)
        wait(1500)
        r = jsv(win, win._view_src, """(function(){
var wrap=!!document.querySelector('#editor .src-wrap');
var blocks=document.querySelectorAll('#editor > .blk').length;
return JSON.stringify({wrap:wrap, blocks:blocks, srcText:(window.getMarkdown()||'').slice(0,20)})})()""")
        try:
            rj = json.loads(r or "{}")
        except Exception:
            rj = {}
        ok = rj.get("wrap") is True and rj.get("blocks") == 0
        extra = rj
    check("B3.1 首进双栏：左栏为源码层（无渲染块残留）", ok, extra)
    win._set_mode("edit")
    wait(800)

    log("")
    log("TOTAL-BATCH DONE")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("DONE")

if __name__ == "__main__":
    main()
