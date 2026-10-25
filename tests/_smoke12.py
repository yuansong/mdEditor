# -*- coding: utf-8 -*-
"""v3.5 测试：模块化拆分 / 精简工具栏 / 菜单结构 / 快捷键 / 新 cmd（h1-h3,p,hr,math）。"""
import json
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke12.txt")

results = []

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication.instance() or QApplication([])
from mainwindow import MainWindow  # 模块化导入验证

win = MainWindow()
win.show()


def js(code):
    box = {}
    loop = QEventLoop()

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(10000, loop.quit)  # 超时保护，避免死等
    win._js_active(code, cb)
    loop.exec()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"JS [{code[:60]}] -> {str(box.get('r'))[:80]}\n")
    return box.get("r")


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def check(name, cond, detail=""):
    results.append(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))


wait(6000)

# ---------- 1) 工具栏精简 ----------
tb = win._tool_tb
tips = [a.toolTip() for a in tb.actions() if a.toolTip()]
check("toolbar has 7 actions", len(tips) == 7, tips)  # v3.24：新建/打开/保存/撤销/重做/查找/系统设置 + 模式按钮（全局搜索按钮已并入查找对话框）
check("toolbar has undo/redo, no bold/italic buttons",
      any("撤销" in t for t in tips) and any("重做" in t for t in tips) and
      all("加粗" not in t and "斜体" not in t for t in tips), tips)
check("mode button has icon", not win._btn_mode.icon().isNull())
check("mode button tooltip mentions cycle", "循环切换" in win._btn_mode.toolTip(), win._btn_mode.toolTip())

# ---------- 2) 菜单结构 ----------
menus = [m.text().replace("&", "") for m in win.menuBar().actions()]
check("menu order F/E/V/S/H", menus == ["文件(F)", "编辑(E)", "视图(V)", "设置(S)", "帮助(H)"], menus)
titles = {}
for m in win.menuBar().actions():
    acts = [a.text().replace("&", "") for a in m.menu().actions()]
    titles[m.text().replace("&", "")] = acts
check("no standalone find menu", not any("查找(" in t for t in menus), menus)
check("find merged into edit", "查找…" in titles.get("编辑(E)", []), titles.get("编辑(E)"))
check("format menu removed, settings added",
      "格式(O)" not in titles and "快捷键设置…" in titles.get("设置(S)", []), list(titles))
check("help is last", menus[-1].startswith("帮助"), menus)

# ---------- 3) 快捷键（含隐藏的格式类动作） ----------
sc = {name: (a.shortcut().toString() if a.shortcut().toString() else None)
      for name, a in win._shortcut_acts.items()}
check("bold Ctrl+B", sc.get("加粗") == "Ctrl+B", sc.get("加粗"))
check("h1 Ctrl+1", sc.get("标题 1") == "Ctrl+1", sc.get("标题 1"))
check("h2 Ctrl+2", sc.get("标题 2") == "Ctrl+2")
check("body Ctrl+0", sc.get("正文") == "Ctrl+0", sc.get("正文"))
check("strike Ctrl+Shift+X", sc.get("删除线") == "Ctrl+Shift+X", sc.get("删除线"))
check("quote Ctrl+Shift+Q", sc.get("引用") == "Ctrl+Shift+Q", sc.get("引用"))
check("exit Ctrl+Q", sc.get("退出") == "Ctrl+Q", sc.get("退出"))
check("find Ctrl+F", sc.get("查找…") == "Ctrl+F", sc.get("查找…"))
check("replace Ctrl+H", sc.get("替换…") == "Ctrl+H", sc.get("替换…"))
check("goto Ctrl+G", sc.get("转到行…") == "Ctrl+G", sc.get("转到行…"))
check("shortcut defs cover groups", len(win._shortcut_defs) >= 5 and
      all(len(items) > 0 for _g, items in win._shortcut_defs),
      [(g, len(items)) for g, items in win._shortcut_defs])

# ---------- 4) 视图菜单：三模式单选 ----------
view_acts = titles.get("视图(V)", [])
check("view has three modes", all(x in view_acts for x in ["写作模式", "源码模式", "分屏模式"]), view_acts)
check("mode radio exclusive", win._mode_group.actions()[0].isChecked() and
      not win._mode_group.actions()[1].isChecked())

with open(LOG, "a", encoding="utf-8") as f:
    f.write("== progress: UI checks done, entering JS tests ==\n")

# ---------- 5) 新 cmd：h1/h2/h3/p/hr/math ----------
js("window.setMarkdown('待设置的标题文字')")
wait(800)
win._fmt("h2")
wait(500)
r = js("window.getMarkdown()")
check("cmd h2", (r or "").startswith("## "), (r or "")[:40])
win._fmt("h3")
wait(500)
r = js("window.getMarkdown()")
check("cmd h3 replaces h2", (r or "").startswith("### 待"), (r or "")[:40])
win._fmt("p")
wait(500)
r = js("window.getMarkdown()")
check("cmd p strips heading", (r or "").startswith("待设置"), (r or "")[:40])
win._fmt("hr")
wait(500)
r = js("window.getMarkdown()")
check("cmd hr inserts ---", "---" in (r or ""), (r or "")[:60])
win._fmt("math")
wait(500)
r = js("window.getMarkdown()")
check("cmd math inserts block", "```math" in (r or ""), (r or "")[:60])
# 公式块渲染（KaTeX 回归）
js("window.setMarkdown('```math\\nx^2 + y^2 = z^2\\n```')")
wait(1200)
r = js("document.querySelectorAll('.mathblock .katex').length")
check("math block renders", r == 1, r)

# ---------- 6) 模式切换 ----------
win._set_mode("dual")
wait(2000)
check("dual mode stack", win._stack.currentIndex() == 1 and win._dual is True)
check("mode button updated", "分屏模式" in win._btn_mode.toolTip(), win._btn_mode.toolTip())
check("mode menu synced", win._mode_acts["dual"].isChecked())
win._set_mode("edit")
wait(1500)
check("back to edit", win._stack.currentIndex() == 0 and win._dual is False)
r = js("window.getMarkdown()")
check("edit view content preserved", r is not None, (r or "")[:40])
win._set_mode("src")
wait(800)
r = js("(function(){var s=document.querySelector('.t-src');return s? 'SRC_ON':'SRC_OFF'})()")
check("src mode on same view", r == "SRC_ON", r)
win._set_mode("edit")
wait(800)

# ---------- 7) 图标模块 ----------
import icons
for fn in (icons.icon_new, icons.icon_open, icons.icon_save, icons.icon_find,
           icons.icon_write, icons.icon_code, icons.icon_split):
    ic = fn(40)
    check("icon " + fn.__name__ + " ok", not ic.isNull())

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
import os
os._exit(0)  # 强制退出，避免未保存弹窗阻塞测试进程
