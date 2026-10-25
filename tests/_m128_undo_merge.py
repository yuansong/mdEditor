# -*- coding: utf-8 -*-
"""_m128_undo_merge.py — v3.38 批次之十专项探针
A组 UNDO-1：源码态退出清双栈（旧缺陷：源码改写被旧 redo 条目静默覆盖）
B组 OBS-F1：wrapSelection 相邻同标记壳合并（**已加粗**和普通 → **已加粗和普通**）
轻量驱动：直接加载 editor.html（同 m110 套路），不走 MainWindow。
"""
import sys, json
from PySide6.QtCore import QUrl, QTimer, QEventLoop
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

APP = QApplication.instance() or QApplication(sys.argv)
view = QWebEngineView()
view.resize(1280, 900)
loop = QEventLoop()
view.loadFinished.connect(lambda ok: QTimer.singleShot(2800, loop.quit) if ok else None)
view.load(QUrl(("file:///" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "editor.html"))))
loop.exec()

_results = []
def check(name, ok, detail=""):
    _results.append((name, bool(ok), str(detail)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  | " + str(detail)))

def js(code):
    out = []
    lp = QEventLoop()
    def cb(res):
        out.append(res); lp.quit()
    view.page().runJavaScript(code, 0, cb)
    lp.exec()
    return out[0] if out else None

def setmd(md): js("window.setMarkdown(%s);" % json.dumps(md, ensure_ascii=False))
def getmd(): return js("window.getMarkdown();")
def wait(ms):
    w = QEventLoop(); QTimer.singleShot(ms, w.quit); w.exec()

js(r"""
window.__setSel = function(idx, a, b){
  var blk = document.querySelectorAll('#editor .blk')[idx]; if (!blk) return 'NOBLK';
  var host = blk.querySelector('[contenteditable="true"]') || blk;
  var w = document.createTreeWalker(host, NodeFilter.SHOW_TEXT, null);
  var nodes = [], n, total = 0;
  while ((n = w.nextNode())) { nodes.push([n, total]); total += n.nodeValue.length; }
  if (b > total) b = total; if (a > b) a = b; if (a < 0) a = 0;
  function loc(off){
    for (var i = nodes.length - 1; i >= 0; i--)
      if (off >= nodes[i][1]) return [nodes[i][0], off - nodes[i][1]];
    return null;
  }
  var s = loc(a), e = loc(b);
  if (!s || !e) return 'NOPOS';
  var rg = document.createRange();
  rg.setStart(s[0], s[1]); rg.setEnd(e[0], e[1]);
  var sel = getSelection(); sel.removeAllRanges(); sel.addRange(rg);
  return 'SEL:' + rg.toString();
};
window.__leak = function(){
  var bad = [];
  var blocks = document.querySelectorAll('#editor .blk');
  for (var i = 0; i < blocks.length; i++){
    var b = blocks[i];
    if (b.querySelector('pre, textarea, .raw-edit')) continue;
    var w = document.createTreeWalker(b, NodeFilter.SHOW_TEXT, null);
    var n;
    while ((n = w.nextNode())) {
      var v = n.nodeValue || '';
      var m = v.match(/(\*\*|==|~~|<u>|<\/u>)/g);
      if (m) bad.push(i + ':' + v.slice(0, 24));
    }
  }
  return JSON.stringify(bad);
};
""")

def fmt_case(name, raw, a, b, act, expect, leak_check=True):
    setmd(raw)
    wait(450)
    js("__enterEditAt(0,0)")
    wait(120)
    r = js("__setSel(0,%d,%d)" % (a, b))
    if not str(r).startswith("SEL"):
        check(name, False, "setSel=%s" % r); return
    js("__applyFloat('%s')" % act)
    wait(450)
    md = getmd()
    ok = (md == expect)
    # 渲染洁净度：applyFloat 在编辑态执行后块不回渲染态，__leak 会把原文文本
    # 误报为泄漏 —— 把结果重新灌入（渲染态）后再查才有意义
    leak = "[]"
    if ok and leak_check:
        setmd(md); wait(450)
        leak = js("__leak()")
    check(name, ok and leak == "[]", "got=%r leak=%s dbg=%s fmt=%s" % (
        md, leak, js("JSON.stringify(window.__wrapDbg||null)"),
        js("JSON.stringify(window.__fmtDbg||null)")))

print("========== A组 UNDO-1 源码态退出清双栈 ==========")
setmd("第一版正文")
wait(550)
js("__enterEditAt(0,0)"); wait(150)
js("__setSel(0,0,2)"); js("__applyFloat('bold')"); wait(550)
s1 = getmd()
check("A0 前置：加粗产生第二个撤销态", s1 == "**第一**版正文", repr(s1))
js("window.cmd('undo');"); wait(500)
s2 = getmd()
check("A1 源码态之前 undo 正常回退", s2 == "第一版正文", repr(s2))
js("window.setSourceMode(true);"); wait(250)
r = js("(function(){var el=document.querySelector('.raw-edit');if(!el)return 'NOEL';"
       "el.textContent='源码改写版';el.dispatchEvent(new Event('input',{bubbles:true}));return 'ok';})()")
check("A2a 源码态注入改写", r == "ok", str(r))
js("window.setSourceMode(false);"); wait(500)
s3 = getmd()
check("A2 源码改写落回生效", s3 == "源码改写版", repr(s3))
js("window.cmd('redo');"); wait(500)
s4 = getmd()
check("A3 修复点：redo 不再覆盖源码改写（redoStack 已清空）", s4 == "源码改写版", repr(s4))
js("window.cmd('undo');"); wait(500)
s5 = getmd()
check("A4 undoStack 同口径清空：undo 不回退", s5 == "源码改写版", repr(s5))

# 对照：setMarkdown 双栈口径下 undo 正常
setmd("对照文本")
wait(550)
js("__enterEditAt(0,0)"); wait(150)
js("__setSel(0,0,2)"); js("__applyFloat('bold')"); wait(550)
js("window.cmd('undo');"); wait(500)
s6 = getmd()
check("A5 对照：setMarkdown 口径下 undo 正常", s6 == "对照文本", repr(s6))

print("========== B组 OBS-F1 相邻同标记壳合并 ==========")
fmt_case("B1 左侧闭合壳并入：**已加粗**和普通 +bold(和普通)",
         "**已加粗**和普通", 7, 10, "bold", "**已加粗和普通**")
fmt_case("B2 左右双壳并入：**已加粗**和**丙** +bold(和)",
         "**已加粗**和**丙**", 7, 8, "bold", "**已加粗和丙**")
fmt_case("B3 右侧开口壳并入：普通**和乙** +bold(普通)",
         "普通**和乙**", 0, 2, "bold", "**普通和乙**")
fmt_case("B4 双壳全并入：**甲**乙**丙** +bold(乙)",
         "**甲**乙**丙**", 5, 6, "bold", "**甲乙丙**")
fmt_case("B5 粗斜长游程不并入（OBS-F1b 既有 5 游程缺口，只验 md）：***甲***和普通 +bold(和普通)",
         "***甲***和普通", 7, 10, "bold", "***甲*****和普通**", leak_check=False)
fmt_case("B6 斜体同规则：*斜*和普通 +italic(和普通)",
         "*斜*和普通", 3, 6, "italic", "*斜和普通*")
fmt_case("B7 无相邻壳回归：普通词 +bold",
         "普通词", 0, 3, "bold", "**普通词**")
fmt_case("B8 toggle 不受影响：**甲** +bold(甲) 取消格式",
         "**甲**", 2, 3, "bold", "甲")

# B9 分段加粗链式整并相邻壳（丁在原文中本就是裸文本，不在壳内）
setmd("**甲**乙**丙**丁**戊**")
wait(450)
i = js("(function(){var t=window.getMarkdown();return t.indexOf('乙');})()")
js("__enterEditAt(0,0)"); wait(120)
js("__setSel(0,%d,%d)" % (int(i), int(i) + 1))
js("__applyFloat('bold')"); wait(450)
md = getmd()
check("B9 分段加粗链式整并相邻壳", md == "**甲乙丙**丁**戊**", repr(md))

print("========== 汇总 ==========")
npass = sum(1 for _, ok, _ in _results if ok)
nfail = len(_results) - npass
print("PASS=%d FAIL=%d" % (npass, nfail))
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m128.txt")
with open(OUT, "w", encoding="utf-8") as f:
    for name, ok, detail in _results:
        f.write(("PASS " if ok else "FAIL ") + name + ("" if ok else "  | " + detail) + "\n")
    f.write("PASS=%d FAIL=%d\n" % (npass, nfail))
