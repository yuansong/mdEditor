# -*- coding: utf-8 -*-
"""v3.29 探针 J：源码模式语法高亮 + 双栏同步滚动。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29j.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def note(tag, extra):
    out.append(f"NOTE | {tag} | {extra}")
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


def js_view(view, code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_view(view, code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


wait(2500)

# ================= A. 源码模式语法高亮（单栏源码） =================
MD_A = ("# 高亮标题\n\n这是 **加粗文字** 和 `行内代码` 以及 [链接](https://example.com)。\n\n"
        "> 引用一行\n\n- 列表项一\n- 列表项二\n\n```python\nprint(\"hi\")\n```\n\n正文段落。")
js(f"window.setMarkdown({json.dumps(MD_A)})")
wait(600)
win._set_mode("src")
wait(900)

d = json.loads(js("""
(function(){var hl=document.querySelector('.src-hl');var se=document.querySelector('.raw-edit.t-src');
if(!hl||!se)return JSON.stringify({err:'nohl'});
return JSON.stringify({
  spans:hl.querySelectorAll('span').length,
  h:[].some.call(hl.querySelectorAll('.h-h'),function(x){return x.textContent==='高亮标题'}),
  b:hl.querySelectorAll('.h-b').length>0,
  code:hl.querySelectorAll('.h-code').length>0,
  link:hl.querySelectorAll('.h-link').length>0,
  quote:hl.querySelectorAll('.h-quote').length>0,
  list:hl.querySelectorAll('.h-list').length>0,
  fence:hl.querySelectorAll('.h-fence').length>0,
  codec:hl.querySelectorAll('.h-codec').length>0,
  color:getComputedStyle(se).color,
  caret:getComputedStyle(se).caretColor
})})()""") or "{}")
note("A hl", str(d))
check("高亮垫层存在且分类命中", d.get("spans", 0) >= 8 and d.get("h") and d.get("b")
      and d.get("code") and d.get("link") and d.get("quote") and d.get("list")
      and d.get("fence") and d.get("codec"), str(d))
check("编辑层文字透明 / 光标可见",
      d.get("color") == "rgba(0, 0, 0, 0)" and d.get("caret") not in (None, "rgba(0, 0, 0, 0)", "auto"), str(d))

# A2: 编辑后高亮实时刷新（直接改 textContent + 派发 input）
r = js("""
(function(){var s=document.querySelector('.raw-edit.t-src');if(!s)return 'nosrc';
s.textContent=s.textContent+'\\n## 探针新标题';
s.dispatchEvent(new InputEvent('input',{bubbles:true}));return 'ok'})()""")
wait(600)
d = json.loads(js("""
(function(){var hl=document.querySelector('.src-hl');if(!hl)return JSON.stringify({err:'nohl'});
return JSON.stringify({
  newh:[].some.call(hl.querySelectorAll('.h-h'),function(x){return x.textContent==='探针新标题'}),
  gutter:document.querySelectorAll('.src-gutter .ln').length,
  md:(window.getMarkdown()||'').slice(-10)})})()""") or "{}")
note("A2 refresh", str(d))
check("输入后高亮实时更新", d.get("newh") is True, str(d))
check("行号同步更新", d.get("gutter", 0) == 15, str(d))
check("srcText 回写正确", str(d.get("md", "")).endswith("探针新标题"), str(d))

# A3: 退出源码模式高亮层清理
js("window.setSourceMode(false)")
wait(700)
d = json.loads(js("(function(){var ar=JSON.parse(window.__raw());"
                  "return JSON.stringify({hl:!!document.querySelector('.src-hl'),"
                  "r0:ar.raw[0]||''})})()") or "{}")
check("退出源码后垫层清理", d.get("hl") is False and str(d.get("r0", "")).startswith("# 高亮标题"), str(d))

# ================= B. 双栏同步滚动 =================
blocks = []
for i in range(40):
    blocks.append(f"# 标题 {i}")
    blocks.append(f"段落 {i} " + "同步滚动验证内容。" * 8)
MD_B = "\n\n".join(blocks)
win._set_mode("dual")
wait(3500)
win._push_text(MD_B)
wait(1500)

# B1: 源码视图滚动 → 预览跟随
js_view(win._view_src, "window.scrollTo(0, 2400)")
wait(900)
d = json.loads(js_view(win._view_src, "window.pollSrcScroll()") or "{}")
note("B poll", str(d))
check("pollSrcScroll 返回块序号", d.get("idx") is not None, str(d))
prev_y = js_view(win._view_prev, "window.scrollY")
note("B prevY", str(prev_y))
check("预览视图已跟随滚动", float(prev_y or 0) > 300, str(prev_y))
top = float(js_view(win._view_prev,
                    f"(function(){{var b=document.querySelectorAll('#editor .blk')[{d.get('idx', 0)}];"
                    f"return b?b.getBoundingClientRect().top:-999}})()") or -999)
note("B blockTop", str(top))
check("预览对应块在视口内", -300 <= top <= 1200, str(top))

# B2: 光标定位段落（gotoHeadingSrc 放光标到块 35）→ 预览优先跟光标
js_view(win._view_src, "window.gotoHeadingSrc(35)")
wait(900)
d = json.loads(js_view(win._view_src, "window.pollSrcScroll()") or "{}")
note("B2 poll", str(d))
check("光标块上报", d.get("cv") is True and d.get("cidx") == 35, str(d))
top = float(js_view(win._view_prev,
                    "(function(){var b=document.querySelectorAll('#editor .blk')[35];"
                    "return b?b.getBoundingClientRect().top:-999})()") or -999)
note("B2 blockTop", str(top))
check("预览定位到光标段落（块顶≈8vh 垫高）", 0 <= top <= 220, str(top))

out.append("DONE")
flush()
print("done")
