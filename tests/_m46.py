# -*- coding: utf-8 -*-
"""v3.30.6 探针：标题行内格式脏标记修复 + 源码模式单行显示。
H) 标题渲染态：先 ~~删除线~~ 再 ==高亮== → raw 应为 # ~~==文字==~~（两侧不多出 ==）；
   逆序 mark→strike、同标记 toggle 取消、普通段落对照同样验证。
S) 源码模式：每条源码行恒单行显示（white-space:pre + 横向滚动 + 垫层同步），
   长行不再折行（折行曾导致行号/高亮层错位而无法编辑）。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m46.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def jj(code):
    r = js(code)
    try: return json.loads(r or "{}")
    except Exception: return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


wait(2500)

# 选中第 i 块渲染内容的全部文本（页面脚本 ED 不在全局作用域 → 用 DOM 查询）
SEL_BLK = ("(function(i){try{var b=document.querySelectorAll('#editor .blk')[i];"
           "if(!b)return 'noblk';"
           "var tn=null;(function w(n){if(tn)return;if(n.nodeType===3&&n.nodeValue.trim())tn=n;"
           "for(var k=0;k<n.childNodes.length;k++)w(n.childNodes[k])})(b);"
           "if(!tn)return 'notext';"
           "var r=document.createRange();r.selectNodeContents(tn.nodeType===3?tn.parentNode:tn);"
           "var s=getSelection();s.removeAllRanges();s.addRange(r);return 'sel'}"
           "catch(e){return 'ERR:'+e.message}})")

# ---------- H1: 标题 strike → mark ----------
js("window.setMarkdown('# 标题内容')")
wait(700)
r = js(SEL_BLK + "(0)")
check("H1-0 选中标题渲染文本", r == "sel", str(r))
js("window.__applyFloat('strike')")
wait(500)
r0 = raw()[0]
check("H1-1 标题应用删除线 → # ~~标题内容~~", r0 == "# ~~标题内容~~", r0)
r = js(SEL_BLK + "(0)")
check("H1-2 重建后重选标题文本", r == "sel", str(r))
js("window.__applyFloat('mark')")
wait(500)
r0 = raw()[0]
check("H1-3 再应用高亮 → # ~~==标题内容==~~（两侧不多出 ==）",
      r0 == "# ~~==标题内容==~~", r0)

# ---------- H2: 高亮 toggle 取消 → 删除线 toggle 取消 ----------
r = js(SEL_BLK + "(0)")
js("window.__applyFloat('mark')")
wait(500)
r0 = raw()[0]
check("H2-1 高亮 toggle 取消 → # ~~标题内容~~", r0 == "# ~~标题内容~~", r0)
r = js(SEL_BLK + "(0)")
js("window.__applyFloat('strike')")
wait(500)
r0 = raw()[0]
check("H2-2 删除线 toggle 取消 → # 标题内容", r0 == "# 标题内容", r0)

# ---------- H3: 逆序 mark → strike ----------
r = js(SEL_BLK + "(0)")
js("window.__applyFloat('mark')")
wait(500)
r = js(SEL_BLK + "(0)")
js("window.__applyFloat('strike')")
wait(500)
r0 = raw()[0]
check("H3 逆序 mark→strike → # ==~~标题内容~~==",
      r0 == "# ==~~标题内容~~==", r0)

# ---------- H4: 普通段落对照（strike → mark）----------
js("window.setMarkdown('正文文字')")
wait(700)
r = js(SEL_BLK + "(0)")
js("window.__applyFloat('strike')")
wait(500)
r = js(SEL_BLK + "(0)")
js("window.__applyFloat('mark')")
wait(500)
r0 = raw()[0]
check("H4 段落 strike→mark → ~~==正文文字==~~",
      r0 == "~~==正文文字==~~", r0)

# ---------- S: 源码模式单行显示 ----------
js("window.setMarkdown('# 标\\n\\n正文段')")
wait(700)
js("window.setSourceMode(true)")
wait(600)
d = jj("(function(){try{"
       "var e=document.querySelector('.raw-edit.t-src');"
       "var h=document.querySelector('.src-hl');if(!e)return 'nosrc';"
       "e.textContent='短';var cs=getComputedStyle(e),hs=getComputedStyle(h);"
       "var hShort=e.getBoundingClientRect().height;"
       "e.textContent='长'.repeat(4000);"
       "var hLong=e.getBoundingClientRect().height;"
       "h.textContent='长'.repeat(4000);"   # 垫层同步内容，横向才可滚
       "e.scrollLeft=80;e.dispatchEvent(new Event('scroll'));"
       "return JSON.stringify({wsE:cs.whiteSpace,wsH:hs.whiteSpace,"
       "hShort:Math.round(hShort),hLong:Math.round(hLong),"
       "scrollable:e.scrollWidth>e.clientWidth,sync:h.scrollLeft})"
       "}catch(err){return 'ERR:'+err.message}})()")
check("S1 编辑层 / 垫层 white-space 均为 pre（不折行）",
      d.get("wsE") == "pre" and d.get("wsH") == "pre", json.dumps(d, ensure_ascii=False))
check("S2 4000 字长行与短行同高（恒单行，不折行）",
      d.get("hShort") == d.get("hLong") and (d.get("hLong") or 0) > 0,
      f"hShort={d.get('hShort')} hLong={d.get('hLong')}")
check("S3 长行横向可滚动且垫层 scrollLeft 同步",
      d.get("scrollable") is True and d.get("sync") == 80, json.dumps(d, ensure_ascii=False))
js("window.setSourceMode(false)")
wait(500)
r = raw()
check("S4 退出源码模式 → 原文按块恢复", len(r) == 2 and r[0] == "# 标" and r[1] == "正文段",
      json.dumps(r, ensure_ascii=False))

out.append("DONE")
flush()
print("done")
