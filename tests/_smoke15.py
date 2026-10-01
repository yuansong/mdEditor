# -*- coding: utf-8 -*-
"""v3.8 测试：全局主题换肤 / 大纲 3 级折叠 / Mermaid 图表 / 系统设置 /
中文标准按钮 / 自动保存与缩放。"""
import json
import sys
import time

sys.path.insert(0, r"E:\WorkBuddy\md-editor\src")
import os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke15.txt")

results = []

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QEventLoop, QTimer, QSettings, QTranslator

app = QApplication.instance() or QApplication([])
# v3.29：大纲级别被其他用例 / 残留会话改动会污染「h3 默认折叠」断言（QSettings 跨运行持久化）
QSettings("WorkBuddy", "WorkBuddyMarkdown").setValue("outlineLevel", 3)
import main as appmain
appmain._load_translators(app)   # 与 main.py 相同的翻译加载逻辑
from mainwindow import MainWindow

t0 = time.perf_counter()
win = MainWindow()
win.show()


def js(code):
    box = {}
    loop = QEventLoop()

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(10000, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box.get("r")


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def check(name, cond, detail=""):
    results.append(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))


def open_slash(max_try=3):
    """打开斜杠菜单：Esc 清理 -> 派发空块 mousedown + '/' 键 -> 轮询直到菜单真正展开。

    直接派发 '/' 后立刻操作菜单会偶发失败（编辑器还没渲染出空块），
    这里轮询 #slashmenu.show 直到就绪，避免时序抖动导致的假 FAIL。
    """
    for _ in range(max_try):
        js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
           "var el=document.querySelector('#editor .blk');if(!el) return 'NOBLK';"
           "el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
           "var t=document.querySelector('#editor .raw-edit')||el;"
           "t.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true}));return 't'})()")
        wait(400)
        if js("document.getElementById('slashmenu').classList.contains('show')") is True:
            return True
    return False


for _ in range(120):
    if win._vstate["edit"]["loaded"]:
        break
    wait(250)
startup_ms = int((time.perf_counter() - t0) * 1000)
check("edit view loaded", win._vstate["edit"]["loaded"], f"{startup_ms}ms")

# ---------- 1) 全局主题换肤：六套主题 ----------
# QSS 检查用 Qt 调色板背景色（styles.PALETTES[*].bg）
QSS_BG = {"light": "#ffffff", "azure": "#f3f8fd", "sepia": "#f8f2e4",
          "dark": "#1e2227", "night": "#17181b", "panda": "#26292c"}
for tid, bgv in QSS_BG.items():
    win.apply_theme(tid)
    wait(250)
    r = js("(function(){return document.body.dataset.theme || 'light'})()")
    expect = "light" if tid == "light" else tid
    check(f"theme {tid}: web data-theme", r == expect, r)
    qss = app.styleSheet()
    check(f"theme {tid}: app QSS applied", f"background: {bgv}" in qss, "")
    sbqss = win._sidebar.styleSheet()
    check(f"theme {tid}: sidebar QSS applied", f"background: {bgv}" in sbqss, "")
    act = win._theme_acts.get(tid)
    check(f"theme {tid}: 视图菜单主题项已移除(统一在系统设置)", act is None, act)
saved_theme = QSettings("WorkBuddy", "WorkBuddyMarkdown").value("theme")
check("theme persisted", saved_theme == "panda", saved_theme)

# 未知主题回退浅色
r = js("window.setTheme('unknown'); document.body.dataset.theme || 'light'")
check("unknown theme falls back to light", r == "light", r)

# ---------- 2) 大纲：默认展开 3 级，4 级以上折叠 ----------
win.apply_theme("light")
js("window.setMarkdown('# 一级\\n\\n## 二级\\n\\n### 三级\\n\\n#### 四级\\n\\n##### 五级\\n\\n正文')")
wait(2500)  # 等待轮询 collect -> set_outline
tree = win._sidebar.outline
def collect_items(item, out):
    for k in range(item.childCount()):
        c = item.child(k)
        out.append(c)
        collect_items(c, out)
all_items = []
for t in range(tree.topLevelItemCount()):
    top = tree.topLevelItem(t)
    all_items.append(top)
    collect_items(top, all_items)
check("outline has 5 headings", len(all_items) == 5, len(all_items))
lvl_map = [(it.text(0).strip()[:2], it.data(0, __import__('PySide6').QtCore.Qt.UserRole)) for it in all_items]
h1, h2, h3, h4, h5 = all_items
check("outline h1/h2 expanded", h1.isExpanded() and h2.isExpanded(),
      [h1.isExpanded(), h2.isExpanded()])
check("outline h3 collapsed by default", not h3.isExpanded(), h3.isExpanded())
check("outline h4 nested under h3", h4.parent() is h3, "")
check("outline h5 nested under h4", h5.parent() is h4, "")
h3.setExpanded(True)   # 模拟手动展开
check("outline h3 manual expand works", h3.isExpanded(), "")
h3.setExpanded(False)

# ---------- 3) Mermaid 图表渲染 ----------
js("window.setMarkdown('```mermaid\\nflowchart TD\\n  A[开始] --> B[结束]\\n```')")
# 首次渲染需初始化 mermaid 引擎（慢机上耗时较长），轮询等待 svg 出现
d = {}
for _ in range(40):
    wait(500)
    r = js("(function(){var m=document.querySelector('.mermaidblock');"
           "return JSON.stringify({has:m?true:false, svg:m?!!m.querySelector('svg'):false,"
           "err:m?!!m.querySelector('.mmd-err'):false})})()")
    d = json.loads(r or "{}")
    if d.get("svg") or d.get("err"):
        break
wait(300)
check("mermaid render done", True, json.dumps(d))
check("mermaid block exists", d.get("has") is True, d)
check("mermaid svg rendered", d.get("svg") is True, d)
check("mermaid no error", d.get("err") is False, d)
# 语法错误 -> 显示错误提示
js("window.setMarkdown('```mermaid\\nflowchart TD\\n  A[ --> \\n```')")
wait(1200)
r = js("(function(){var m=document.querySelector('.mermaidblock');"
       "return m ? !!m.querySelector('.mmd-err') : 'NOBLOCK'})()")
check("mermaid syntax error shown", r is True, r)
# 主题切换后图表仍在
js("window.setMarkdown('```mermaid\\nflowchart TD\\n  A[开始] --> B[结束]\\n```')")
wait(1200)
js("window.setTheme('dark')")
wait(800)
r = js("(function(){var m=document.querySelector('.mermaidblock');"
       "return JSON.stringify({t:document.body.dataset.theme,svg:m?!!m.querySelector('svg'):false})})()")
d = json.loads(r or "{}")
check("mermaid survives theme switch", d.get("t") == "dark" and d.get("svg") is True, r)
js("window.setTheme('light')")
# 双击进入编辑
# v3.16+ 图表源码框是 textarea.mmd-src（内容在 .value，且不含围栏本身），单击即打开
r = js("(function(){var m=document.querySelector('#editor .mermaidblock');"
       "if(!m) return 'NO_CHART';"
       "m.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
       "var ta=document.querySelector('#editor textarea.mmd-src');"
       "return ta ? (ta.value||'') : 'NO_EDIT'})()")
check("mermaid 单击打开源码编辑框", (r or "").startswith("flowchart TD"), r)
wait(300)
js("window.setMarkdown('')")

# ---------- 4) 斜杠菜单：图表二级项 ----------
check("图表：斜杠菜单已打开", open_slash() is True, "")
# 悬停「图表」父项 -> 二级展开（v3.19：斜杠菜单二级不显示父菜单名）
r = js("(function(){var m=document.getElementById('slashmenu');"
       "var it=[].filter.call(m.querySelectorAll('.si'),function(x){return x.textContent.indexOf('图表')!==-1})[0];"
       "if(!it) return 'NO_ITEM';"
       "it.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return 'ok'})()")
wait(400)
r = js("(function(){var s=document.getElementById('submenu');"
       "if(!s.classList.contains('show')) return 'NOT_OPEN';"
       "return JSON.stringify([].map.call(s.querySelectorAll('.si .lb'),function(x){return x.textContent}))})()")
try:
    lbs = json.loads(r or "[]")
except Exception:
    lbs = r
check("chart submenu opens", isinstance(lbs, list), r)
if isinstance(lbs, list):
    for name in ("流程图", "时序图", "类图", "状态图", "E-R 图", "甘特图", "饼图"):
        check(f"chart submenu has {name}", name in lbs, lbs)
# 选择流程图 -> 插入 mermaid 块
r = js("(function(){var s=document.getElementById('submenu');"
       "var it=[].filter.call(s.querySelectorAll('.si'),function(x){return x.textContent.indexOf('流程图')!==-1})[0];"
       "if(!it) return 'NO';"
       "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return 'ok'})()")
wait(500)
r = js("window.getMarkdown()")
check("slash insert flowchart", (r or "").startswith("```mermaid"), (r or "")[:30])
# v3.10：插入图表后应立即渲染；v3.11：焦点自动落到下方空段落可继续编辑
d = {}
for _ in range(40):
    wait(500)
    r = js("(function(){var m=document.querySelector('.mermaidblock');"
           "var ed=document.querySelector('.raw-edit');"
           "return JSON.stringify({has:m?true:false, svg:m?!!m.querySelector('svg'):false,"
           "editEmpty:ed?ed.textContent==='':null,"
           "chartInEdit:ed?(ed.textContent.indexOf('```mermaid')===0):false})})()")
    d = json.loads(r or "{}")
    if d.get("svg") or d.get("has") is False:
        break
check("insert chart renders immediately", d.get("svg") is True, d)
check("chart block not left in raw-edit", d.get("chartInEdit") is False, d)
check("focus on editable block after chart", d.get("editEmpty") is True, d)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 'e'})()")
js("window.setMarkdown('')")

# ---------- 4b) Ctrl+/ 唤起菜单：默认选中标题并展开二级（默认标题 3） ----------
js("window.setMarkdown('')")
wait(500)
r = js("window.openBlockMenu()")
check("ctrl+/ returns slash", r == "slash", r)
wait(400)
r = js("(function(){var sm=document.getElementById('slashmenu');"
       "var s=document.getElementById('submenu');"
       "var act=sm.querySelector('.si.act .lb');"
       "var cap=s.querySelector('.cap');"
       "var subact=s.querySelector('.si.act .lb');"
       "return JSON.stringify({open:sm.classList.contains('show'),"
       "first:act?act.textContent:null,"
       "subopen:s.classList.contains('show'),"
       "cap:cap?cap.textContent:null,"
       "subact:subact?subact.textContent:null})})()")
d = json.loads(r or "{}")
check("ctrl+/ opens insert menu", d.get("open") is True, d)
check("ctrl+/ default selects 标题", d.get("first") == "标题", d)
# v3.19：斜杠菜单的二级不显示父菜单名（块菜单的二级仍显示「标题」）
check("ctrl+/ opens 标题 submenu", d.get("subopen") is True and not (d.get("cap") or ""), d)
check("ctrl+/ submenu defaults 标题 3", d.get("subact") == "标题 3", d)
# 回车直接应用标题 3
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return 'e'})()")
wait(400)
r = js("window.getMarkdown()")
check("ctrl+/ Enter applies 标题 3", (r or "").startswith("### "), (r or "")[:20])
# 非空块：Ctrl+/ 打开块菜单并默认展开标题二级
js("window.setMarkdown('普通文字')")
wait(600)
r = js("window.openBlockMenu()")
check("ctrl+/ non-empty returns ok", r == "ok", r)
wait(400)
r = js("(function(){var s=document.getElementById('submenu');"
       "var cap=s.querySelector('.cap');"
       "var subact=s.querySelector('.si.act .lb');"
       "return JSON.stringify({subopen:s.classList.contains('show'),"
       "cap:cap?cap.textContent:null, subact:subact?subact.textContent:null})})()")
d = json.loads(r or "{}")
check("ctrl+/ block menu opens 标题 sub", d.get("subopen") is True and d.get("cap") == "标题", d)
check("ctrl+/ block menu sub defaults 标题 3", d.get("subact") == "标题 3", d)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 'e'})()")
js("window.setMarkdown('')")

# ---------- 5) 系统设置对话框 ----------
win.show_settings()
wait(400)
check("settings dialog created", hasattr(win, "_set_dlg"), "")
dlg = win._set_dlg
check("settings nav 4 pages (v3.36 模板提升为一级页)", dlg.nav.count() == 4, dlg.nav.count())
check("settings pages 4", dlg.pages.count() == 4, dlg.pages.count())
# 切换到外观页并点击主题行
dlg.nav.setCurrentRow(0)
wait(200)
check("settings theme list rows", dlg.theme_list.count() == 6, dlg.theme_list.count())
dlg.theme_list.row(dlg.theme_list.item(2))  # sepia
dlg._on_theme_clicked(dlg.theme_list.item(2))
wait(300)
check("settings live theme apply", win._theme == "sepia", win._theme)
# 缩放
dlg._on_zoom(120)
wait(200)
check("settings zoom applied", abs(win._zoom - 1.2) < 0.01, win._zoom)
zf = win._view.zoomFactor()
check("web view zoom factor", abs(zf - 1.2) < 0.01, zf)
# 图片与格式页打字机联动（v3.29：写作模式开关移入通用页）
dlg.nav.setCurrentRow(2)
wait(200)
dlg.typewriter_box.setChecked(True)
wait(200)
check("settings typewriter sync", win._typewriter is True, win._typewriter)
dlg.typewriter_box.setChecked(False)
wait(200)
# 通用页自动保存（v3.29：三页布局，通用 = 第 3 行）
dlg.nav.setCurrentRow(2)
wait(200)
dlg.autosave_box.setChecked(False)
wait(200)
check("settings autosave off", win._autosave is False, win._autosave)
dlg.autosave_box.setChecked(True)
dlg.close()
win.set_zoom(1.0)
check("zoom restored", abs(win._zoom - 1.0) < 0.01, win._zoom)

# ---------- 6) 左侧工具栏系统设置按钮 ----------
tips = [a.toolTip() for a in win._tool_tb.actions()]
check("toolbar has settings", any("系统设置" in t for t in tips), tips)

# ---------- 7) 中文标准按钮（Qt 翻译） ----------
mb = QMessageBox()
mb.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel | QMessageBox.Save)
ok_btn = mb.button(QMessageBox.Ok)
cancel_btn = mb.button(QMessageBox.Cancel)
save_btn = mb.button(QMessageBox.Save)
check("Ok button is Chinese", ok_btn.text() in ("确定", "OK(&O)"), ok_btn.text())
check("Cancel button is Chinese", cancel_btn.text().startswith("取消"), cancel_btn.text())
check("Save button is Chinese", save_btn.text().startswith("保存"), save_btn.text())
n_trans = len([t for t in app.children() if isinstance(t, QTranslator)])
check("translators installed", n_trans >= 1, n_trans)

# ---------- 8) v3.23 新增设置项：历史版本保留份数 / 外部编辑器路径 ----------
_pst = QSettings("WorkBuddy", "WorkBuddyMarkdown")
dlg.history_keep_box.setValue(7)
wait(250)
check("settings 历史保留份数 -> win._history_keep", win._history_keep == 7, win._history_keep)
check("settings 历史保留份数 持久化", int(_pst.value("historyKeep", 0)) == 7, _pst.value("historyKeep", 0))
dlg.extedit_edit.setText("C:/Windows/notepad.exe")
dlg._on_external_editor()
wait(250)
check("settings 外部编辑器路径 -> win._external_editor",
      str(win._external_editor).lower().endswith("notepad.exe"), win._external_editor)
# 还原，避免污染后续用例
dlg.history_keep_box.setValue(20)
dlg.extedit_edit.setText("")
dlg._on_external_editor()
wait(200)
check("settings 历史保留份数 / 外部编辑器 已还原",
      win._history_keep == 20 and win._external_editor == "",
      (win._history_keep, win._external_editor))

# ---------- 9) 恢复设置环境 ----------
st = QSettings("WorkBuddy", "WorkBuddyMarkdown")
st.remove("historyKeep")
st.remove("externalEditor")
st.remove("theme")
st.remove("zoom")
st.remove("autosave")
results.append(f"INFO startup(construct->editable) = {startup_ms}ms")

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
import os
os._exit(0)
