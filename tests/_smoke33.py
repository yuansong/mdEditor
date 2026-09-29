# -*- coding: utf-8 -*-
"""v3.31 系统测试补充批次：边界条件与异常场景（smoke32 未覆盖项）。
覆盖：空文档、H7 标题、超长单行、CRLF、Unicode、XSS 注入、表格特殊内容、
reorderSections/gotoMatch/gotoHeading 异常输入、懒渲染 LAZY_MIN 边界、
懒状态下大纲/查找/导出、多标签内容隔离、主题/缩放/打字机持久化、
自动保存 + 手动保存版本快照、collect 字段、DiffDialog 空输入与超长、命令面板。
输出：tests/_smoke33.txt
"""
import json
import os
import shutil
import sys
import tempfile

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke33.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


app = QApplication(sys.argv)
from mainwindow import MainWindow
from dialogs import DiffDialog

win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(400)


def num(code):
    r = js(code)
    try:
        return int(float(r))
    except (TypeError, ValueError):
        return -1


# 保存设置初值，结束时还原
_t0 = win._settings.value("theme", "light")
_z0 = float(win._settings.value("zoom", 1.0) or 1.0)
_tw0 = win._settings.value("typewriter", False)

wait(3000)
js("window.setSlashMenuConfig(null)")

# ================= 1. 空文档与极端输入 =================
setmd("")
r = json.loads(js("JSON.stringify(window.getOutline())") or "[]")
check("E1 空文档 getOutline = []", r == [], str(r))
check("E1 空文档 foldAllHeadings 不崩", js("window.foldAllHeadings(true); 'ok'") == "ok", js("window.foldAllHeadings(false); 'ok'"))
html = js("window.getExportHTML()")
check("E1 空文档 getExportHTML 返回 HTML 字符串", isinstance(html, str) and "<" in (html or ""), str(type(html)))
d = json.loads(js("window.findAll('任意词', false, true, 500)") or "{}")
check("E1 空文档 findAll 计数 0", d.get("count") == 0, str(d)[:80])

# H7：v3.31.1（BUG-2）按 6 级封顶 —— `####### ` 不再解析为标题，按正文段落处理
setmd("####### 七级标题测试")
ol = json.loads(js("JSON.stringify(window.getOutline())") or "[]")
check("E2 H7 不进入大纲（getOutline 仅 h1~h6）", len(ol) == 0, str(ol))
md_now = js("window.getMarkdown()") or ""
check("E2 H7 原文保留", md_now.startswith("#######"), md_now[:30])
check("E2 H7 按段落处理（b-p，无 h6 元素——BUG-2 已修复）",
      num("document.querySelectorAll('#editor .blk.b-p').length") == 1 and
      num("document.querySelectorAll('#editor .blk h6').length") == 0,
      "p=%d,h6=%d" % (num("document.querySelectorAll('#editor .blk.b-p').length"),
                      num("document.querySelectorAll('#editor .blk h6').length")))

# 超长单行（6 万字符）+ findAll 上限封顶
big_line = "字" * 60000
setmd(big_line)
md_now = js("window.getMarkdown()") or ""
check("E3 6 万字符单行往返无损", len(md_now) == 60000, f"len={len(md_now)}")
d = json.loads(js("window.findAll('字', false, true, 500)") or "{}")
check("E3 findAll 计数达上限封顶（=500）", d.get("count") == 500 and len(d.get("matches") or []) == 500,
      f"count={d.get('count')}")
setmd(("针" * 2 + "，") * 40)   # 80 处命中（每单元 2 针 × 40）
d = json.loads(js("window.findAll('针', false, true, 500)") or "{}")
check("E3 精确计数 80（不封顶场景）", d.get("count") == 80, f"count={d.get('count')}")

# CRLF / Unicode / emoji 往返
setmd("甲\r\n\r\n乙")
md_now = (js("window.getMarkdown()") or "").replace("\r", "")
check("E4 CRLF 输入往返为 LF", md_now == "甲\n\n乙", repr(md_now[:20]))
uni = "标题 🎉 ≤ 中文「引号」“智能”\n\n正文 ‎含零宽与 emoji 🙂"
setmd(uni)
md_now = js("window.getMarkdown()") or ""
check("E4 Unicode/emoji/零宽字符往返保留",
      ("🎉" in md_now) and ("「引号」" in md_now) and ("🙂" in md_now), md_now[:50])

# XSS 注入：脚本不得执行、不得注入 DOM，原文保留
setmd('<script>window.__xss=1</script>\n\n正常段落')
check("E5 script 不执行", js("typeof window.__xss") == "undefined", js("typeof window.__xss"))
check("E5 DOM 无 script 元素", js("document.querySelector('#editor script') ? 'yes' : 'no'") == "no",
      js("document.querySelector('#editor script') ? 'yes' : 'no'"))
check("E5 原文保留", "<script" in (js("window.getMarkdown()") or ""), (js("window.getMarkdown()") or "")[:60])

# 表格特殊内容：转义管道 + 裸表头（v3.31.1 BUG-1 已修复）
setmd("列A\\|B | 列C\n| --- | --- |\n| 1 | 2 |")
check("BUG-1(已修复) 转义管道+裸表头渲染为 1 张表格",
      num("document.querySelectorAll('#editor table').length") == 1,
      str(num("document.querySelectorAll('#editor table').length")))
check("BUG-1(已修复) 往返结构不劣化（单表格块，分隔行保留）",
      num("document.querySelectorAll('#editor table').length") == 1 and
      "| --- | --- |" in (js("window.getMarkdown()") or ""),
      (js("window.getMarkdown()") or "")[:60])
check("E6 转义管道往返保留", "\\|" in (js("window.getMarkdown()") or ""), (js("window.getMarkdown()") or "")[:40])
# GFM 混合管道风格：裸表头 + 裸分隔行 + 裸数据行
setmd("甲 | 乙\n--- | ---\n1 | 2")
check("BUG-1(已修复) GFM 裸管道表格渲染为 1 张表格",
      num("document.querySelectorAll('#editor table').length") == 1,
      str(num("document.querySelectorAll('#editor table').length")))
check("BUG-1(已修复) 裸管道表格往返保真",
      "甲 | 乙" in (js("window.getMarkdown()") or "") and "--- | ---" in (js("window.getMarkdown()") or ""),
      (js("window.getMarkdown()") or "")[:40])

# 合并单元格 HTML 表格：存储升级为 HTML
setmd('<table><tr><th colspan="2">跨列头</th></tr><tr><td>a</td><td>b</td></tr></table>')
check("E6 合并表格存储升级 HTML", "<table" in (js("window.getMarkdown()") or ""), (js("window.getMarkdown()") or "")[:60])
check("E6 合并表格 DOM 渲染", num("document.querySelectorAll('#editor table').length") == 1, "dom")

# 脚注 / 定义列表往返
setmd("正文[^1]\n\n[^1]: 注释内容\n\n术语\n: 定义内容")
md_now = js("window.getMarkdown()") or ""
check("E6 脚注往返", "[^1]" in md_now and "[^1]: 注释内容" in md_now, md_now[:60])
check("E6 定义列表往返", "术语" in md_now and ": 定义内容" in md_now, md_now[-40:])

# collect 字段完整性
c = json.loads(js("window.collect()") or "{}")
check("E7 collect 字段齐全（md/dirty/stats/outline/pick/img/req）",
      all(k in c for k in ("md", "dirty", "stats", "outline", "pick", "img", "req")), str(list(c.keys())))
check("E7 collect.stats 非空（有正文字数）", bool(c.get("stats")), str(c.get("stats"))[:80])

# ================= 2. API 异常输入 =================
setmd("# A\n\n段落1\n\n段落2")
for name, arg in (("空数组", "[]"), ("非数组", '"abc"'), ("坏 JSON", "{{"),
                  ("单区间", json.dumps(json.dumps([[0, 2]]))),
                  ("重复区间", json.dumps(json.dumps([[0, 2], [0, 2]])))):
    r = js(f"window.reorderSections({json.dumps(arg)})")
    check(f"E8 reorderSections {name} → invalid", r == "invalid", str(r))
r = js("window.gotoMatch(99999); 'ok'")
check("E8 gotoMatch 越界不崩", r == "ok", str(r))
r = js("window.gotoHeading(999); 'ok'")
check("E8 gotoHeading 越界不崩", r == "ok", str(r))

# 缩放超界钳制
win.set_zoom(2.5)
z = float(win._settings.value("zoom", 1.0) or 1.0)
check("E8 set_zoom(2.5) 钳制到 1.6", abs(z - 1.6) < 0.01, f"zoom={z}")
win.set_zoom(0.5)
z = float(win._settings.value("zoom", 1.0) or 1.0)
check("E8 set_zoom(0.5) 钳制到 0.8", abs(z - 0.8) < 0.01, f"zoom={z}")
win.set_zoom(_z0)

# ================= 3. 懒渲染边界（LAZY_MIN=400） =================
def blocks(n):
    return "\n\n".join(f"段落{i}" for i in range(n))

setmd(blocks(400))
wait(600)
check("E9 恰 400 块启用懒渲染（≥ 阈值）", num("window.__lazyCount()") > 0, f"lazy={num('window.__lazyCount()')}")
setmd(blocks(399))
wait(600)
check("E9 399 块不启用懒渲染（全量）", num("window.__lazyCount()") == 0, f"lazy={num('window.__lazyCount()')}")

# 懒状态下大纲 / 查找 / 导出不受影响
parts = ["# H0"]
for i in range(1, 401):
    parts.append(f"段落{i}")
    if i in (100, 200, 300, 400):
        parts.append(f"# H{i // 100}")
lazy_doc = "\n\n".join(parts)
setmd(lazy_doc)
wait(800)
ol = json.loads(js("JSON.stringify(window.getOutline())") or "[]")
check("E9 懒状态下大纲完整（5 个标题）", len(ol) == 5, str([h.get("text") for h in ol]))
check("E9 懒状态下分节 end 正确（H0 节止于 index 101）", ol and ol[0].get("end") == 101, str(ol[:1]))
d = json.loads(js("window.findAll('段落', false, true, 500)") or "{}")
check("E9 懒状态下 findAll 计数 400", d.get("count") == 400, f"count={d.get('count')}")
html = js("window.getExportHTML()") or ""
check("E9 导出自动 flush（无残留懒块）", num("window.__lazyCount()") == 0, f"lazy={num('window.__lazyCount()')}")
check("E9 导出 HTML 含末块内容与样式", ("段落399" in html) and ("<style" in html), f"len={len(html)}")
md_now = (js("window.getMarkdown()") or "").replace("\r", "")
check("E9 懒渲染往返内容无损", md_now == lazy_doc.replace("\r", ""), "md ok")

# ================= 4. GUI 层：多标签 / 主题 / 打字机 =================
n0 = len(win._docs)
setmd("TAB0内容甲")
win.new_file()
wait(800)
setmd("TAB1内容乙")
win.new_file()
wait(800)
check("G1 新建两个标签（+2）", len(win._docs) == n0 + 2, f"docs={len(win._docs)}")
win._tabbar.setCurrentIndex(n0)
wait(1200)
md_now = js("window.getMarkdown()") or ""
check("G1 切到新建标签 1（内容 TAB1）", "TAB1内容乙" in md_now, md_now[:30])
win._tabbar.setCurrentIndex(n0 + 1)
wait(1200)
md_now = js("window.getMarkdown()") or ""
check("G1 切到新建标签 2（空）", md_now == "", md_now[:30])
win._tabbar.setCurrentIndex(0)
wait(1200)
md_now = js("window.getMarkdown()") or ""
check("G1 切回初始标签 0（内容 TAB0）", "TAB0内容甲" in md_now, md_now[:30])
# 关闭中间标签
win._close_tab(n0 + 1)
wait(600)
check("G1 关闭中间标签后数量 -1", len(win._docs) == n0 + 1, f"docs={len(win._docs)}")

# 主题切换与持久化
win.apply_theme("dark")
check("G2 主题切换 dark 生效并持久化",
      win._theme == "dark" and win._settings.value("theme", "") == "dark", win._theme)
win.apply_theme("非法主题名")
check("G2 非法主题名回退 light", win._theme == "light", win._theme)
win.apply_theme(_t0 if _t0 in ("light", "azure", "sepia", "dark", "night", "panda") else "light")

# 打字机模式开关与持久化
win.toggle_typewriter()
wait(200)
tw1 = win._settings.value("typewriter", False)
check("G3 打字机开关持久化（值翻转）", str(tw1).lower() != str(_tw0).lower(), f"{_tw0} -> {tw1}")
win.toggle_typewriter()
wait(200)

# ================= 5. 手动保存版本快照（自动保存真实键入路径已由 _m33b 探针验证 PASS；
#                          程序化 setMarkdown 不置 dirty 属预期行为，不在此重复） =================
tmp = tempfile.mkdtemp(prefix="mded_s33_")
doc_path = os.path.join(tmp, "快照文档.md")
with open(doc_path, "w", encoding="utf-8") as f:
    f.write("v1 原始内容")
win.open_file(doc_path)
wait(1500)
setmd("v2 修改后内容\n\n新段落")
win.save_file()
wait(1500)
with open(doc_path, "r", encoding="utf-8") as f:
    disk = f.read()
check("S1 手动保存落盘（含结尾换行）", disk.startswith("v2 修改后内容") and disk.endswith("\n"), repr(disk[-12:]))
hist_dir = os.path.join(tmp, ".mdeditor-history", "快照文档")   # _history_dir 用 splitext 去扩展名
snaps = []
if os.path.isdir(hist_dir):
    snaps = [x for x in os.listdir(hist_dir) if x.endswith(".md")]
check("S1 手动保存把上一版留档为版本快照（待确认项#2 验证）", len(snaps) >= 1, str(snaps))

# ================= 6. DiffDialog 边界 + 命令面板 =================
diff = DiffDialog(win)
diff.show_diff("空对空", "", "", "A", "B")
check("D1 空对空提示内容一致", "内容一致" in diff.stat_lbl.text(), diff.stat_lbl.text())
old = "\n".join(f"旧{i}" for i in range(5000))
new = "\n".join(f"新{i}" for i in range(5000))
try:
    diff.show_diff("超长", old, new, "A", "B")
    ok = True
except Exception as e:
    ok = False
check("D1 5000 行 diff 不崩且渲染非空", ok and len(diff.view.toPlainText()) > 0,
      f"len={len(diff.view.toPlainText())}")
diff.close()
win.show_command_palette()
wait(400)
dlg = getattr(win, "_cmd_dlg", None)
check("D2 命令面板可打开", dlg is not None and dlg.isVisible(), str(dlg))
if dlg is not None:
    dlg.close()

# ================= 收尾 =================
try:
    diff.deleteLater()
except Exception:
    pass
shutil.rmtree(tmp, ignore_errors=True)
win._settings.setValue("zoom", _z0)
win._settings.setValue("typewriter", _tw0)
setmd("")
check("收尾：编辑区清空", js("window.getMarkdown()") == "", "done")
flush()
print("SMOKE33 DONE")
