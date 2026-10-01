# -*- coding: utf-8 -*-
"""v3.34 图表主题重设计（MMD-11）功能探针。

覆盖：
  T1 主题清单（跟随界面 + 六套自定义，顺序与 Python config.MMD_THEMES 一致）
  T2 setMmdTheme / getMmdTheme / 旧版值映射（default/dark/forest/neutral）
  T3 跟随界面解析（浅色→晴空、深色→暗夜）
  T4 mermaid 初始化走 base + themeVariables（含主题切换后变量重载）
  T5 图表块右键菜单「图表主题」二级子菜单（8 项、当前项 ✓、黑白可选）
  T6 选择后本地即时生效 + ##mmdtheme: 命令通道 → QSettings 持久化
  T7 设置面板下拉与右键菜单状态双向一致
  T8 视图菜单不再含「图表主题」；设置对话框入口存在
  T9 旧版 QSettings 值经 _set_mmd_theme 归一化
输出：tests/_m99.txt
"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m99.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


app = QApplication(sys.argv)
from mainwindow import MainWindow
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


wait(3000)
js("window.setSlashMenuConfig(null)")
win._settings.setValue("mmdTheme", "")   # 起点：跟随界面主题

# ---------- T1 主题清单 ----------
r = js("(function(){var it=window.mmdMenuItems();return JSON.stringify({n:it.length,"
       "ids:it.map(function(x){return x.id;}),lbs:it.map(function(x){return x.label;})});})()")
d = json.loads(r or "{}")
check("T1 主题清单 8 项（跟随 + 7 套自定义）", d.get("n") == 8, r)   # v3.38（MMD-12）+黑白
check("T1 主题 id 顺序与 Python 一致",
      d.get("ids") == ["", "azure", "mint", "sepia", "graphite", "night", "ember", "mono"], r)
check("T1 主题中文标签", d.get("lbs") == ["跟随界面主题", "晴空", "薄荷", "暖沙", "石墨", "暗夜", "琥珀", "黑白"], r)

# ---------- T2 set/get + 旧值映射 ----------
js("window.setMmdTheme('night')")
check("T2 setMmdTheme('night') 生效",
      (js("window.getMmdTheme()") or "") == "night" and (js("window.mmdThemeId()") or "") == "night",
      js("window.getMmdTheme()"))
js("window.setMmdTheme('forest')")
check("T2 旧值 forest → mint（无缝过渡）", (js("window.getMmdTheme()") or "") == "mint",
      js("window.getMmdTheme()"))
js("window.setMmdTheme('neutral')")
check("T2 旧值 neutral → graphite", (js("window.getMmdTheme()") or "") == "graphite",
      js("window.getMmdTheme()"))
js("window.setMmdTheme('')")
check("T2 setMmdTheme('') 回到跟随界面", (js("window.getMmdTheme()") or "") == "",
      js("window.getMmdTheme()"))

# ---------- T3 跟随界面解析 ----------
orig = js("(document.body.dataset.theme||'')") or ""
js("window.setTheme('dark')")
check("T3 深色界面 → 暗夜", (js("window.mmdThemeId()") or "") == "night", js("window.mmdThemeId()"))
js("window.setTheme('panda')")
check("T3 panda 界面 → 暗夜", (js("window.mmdThemeId()") or "") == "night", js("window.mmdThemeId()"))
js("window.setTheme('sepia')")
check("T3 浅色界面 → 黑白", (js("window.mmdThemeId()") or "") == "mono", js("window.mmdThemeId()"))   # v3.38（MMD-12）默认改黑白
js(f"window.setTheme({json.dumps(orig)})")
wait(300)

# ---------- T4 mermaid base + themeVariables ----------
setmd("```mermaid\nflowchart LR\n  A[开始] --> B[结束]\n```")
wait(2600)
r = js("(function(){var el=document.querySelector('#editor .mermaidblock');"
       "return JSON.stringify({has:!!el, svg:!!(el&&el.querySelector('svg'))});})()")
d = json.loads(r or "{}")
check("T4 图表块渲染出 SVG", d.get("has") is True and d.get("svg") is True, r)

r = js("(function(){try{var c=window.mermaid.mermaidAPI.getSiteConfig();var v=c.themeVariables||{};"
       "return JSON.stringify({theme:c.theme,pv:v.primaryColor,fz:v.fontSize});}"
       "catch(e){return 'ERR:'+e.message;}})()")
d = json.loads(r) if (r or "").startswith("{") else {}
check("T4 初始化走 theme=base（自定义主题）", d.get("theme") == "base", r)
check("T4 跟随界面时注入黑白变量", d.get("pv") == "#FFFFFF", r)   # v3.38（MMD-12）
check("T4 统一字号 15px", d.get("fz") == "15px", r)

js("window.setMmdTheme('night')")
wait(1200)
r = js("(function(){try{var c=window.mermaid.mermaidAPI.getSiteConfig();var v=c.themeVariables||{};"
       "return JSON.stringify({pv:v.primaryColor,tc:v.textColor});}"
       "catch(e){return 'ERR:'+e.message;}})()")
d = json.loads(r) if (r or "").startswith("{") else {}
check("T4 切换暗夜后变量重载并重渲染",
      d.get("pv") == "#1E293B" and d.get("tc") == "#E2E8F0"
      and js("!!document.querySelector('#editor .mermaidblock svg')") is True, r)
js("window.setMmdTheme('')")
wait(600)

# ---------- T5 右键「图表主题」子菜单 ----------
r = js("(function(){var el=document.querySelector('#editor .mermaidblock');if(!el)return 'NOEL';"
       "el.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,"
       "clientX:260,clientY:260}));return 'OK';})()")
wait(400)
r = js("(function(){var bm=document.getElementById('blkmenu');"
       "return JSON.stringify({cap:(bm.querySelector('.cap')||{}).textContent||'',"
       "item:!!bm.querySelector('.mi[data-act=\"mmd-theme-sub\"]'),n:bm.querySelectorAll('.mi').length});})()")
d = json.loads(r or "{}")
check("T5 图表块右键菜单含「图表主题」项",
      d.get("item") is True and "图表块" in (d.get("cap") or ""), r)

js("(function(){var mi=document.querySelector('#blkmenu .mi[data-act=\"mmd-theme-sub\"]');"
   "mi.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true}));return 'OK';})()")
wait(400)
r = js("(function(){var si=document.querySelectorAll('#submenu .si');var mark='';"
       "for(var i=0;i<si.length;i++){var t=si[i].textContent;if(t.indexOf('\\u2713')!==-1)mark=t;}"
       "return JSON.stringify({n:si.length,mark:mark});})()")
d = json.loads(r or "{}")
check("T5 二级子菜单 8 项", d.get("n") == 8, r)   # v3.38（MMD-12）+黑白
check("T5 当前项带 ✓（跟随界面主题）", "跟随界面" in (d.get("mark") or ""), r)

# 点选「琥珀」→ 即时生效 + 命令通道
r = js("(function(){var si=document.querySelectorAll('#submenu .si');"
       "for(var i=0;i<si.length;i++){if(si[i].textContent.indexOf('琥珀')!==-1){"
       "si[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'OK';}}"
       "return 'NOITEM';})()")
wait(500)
check("T5 点选琥珀 → 本地即时生效", (js("window.getMmdTheme()") or "") == "ember",
      f"{r} / {js('window.getMmdTheme()')}")

# ---------- T6 命令通道 → 持久化（探针钩住 _set_mmd_theme 观测回调） ----------
# 注：toast 槽每秒被 _poll 取走一次，直接 takeToast 读取存在竞态；
# 改为观测命令通道的终点（_set_mmd_theme 被调用 + QSettings 落盘 + 状态栏文案）
seen = []
_orig_set = win._set_mmd_theme


def _spy_set(v):
    seen.append(v)
    return _orig_set(v)


win._set_mmd_theme = _spy_set
js("(function(){var el=document.querySelector('#editor .mermaidblock');"
   "el.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:260,clientY:260}));"
   "var mi=document.querySelector('#blkmenu .mi[data-act=\"mmd-theme-sub\"]');"
   "mi.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true}));return 'OK';})()")
wait(400)
js("(function(){var si=document.querySelectorAll('#submenu .si');"
   "for(var i=0;i<si.length;i++){if(si[i].textContent.indexOf('石墨')!==-1){"
   "si[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'OK';}}"
   "return 'NOITEM';})()")
wait(1800)   # 等 _poll 取走命令
check("T6 ##mmdtheme: 命令抵达 Qt（_set_mmd_theme('graphite')）",
      bool(seen) and seen[-1] == "graphite", repr(seen))
check("T6 QSettings 已落盘 graphite",
      (win._settings.value("mmdTheme", "") or "") == "graphite",
      repr(win._settings.value("mmdTheme", "")))
check("T6 状态栏显示主题名且不泄露原始命令",
      "石墨" in win._toast.text() and "##mmdtheme" not in win._toast.text(), win._toast.text())
win._set_mmd_theme = _orig_set

# ---------- T7 设置面板 ↔ 右键菜单 双向一致 ----------
from dialogs import SettingsDialog
dlg = SettingsDialog(win)
dlg.show()
wait(300)
check("T7 设置面板下拉 8 项", dlg.mmd_box.count() == 8, str(dlg.mmd_box.count()))   # v3.38（MMD-12）
check("T7 设置面板回读右键所选（graphite）", (dlg.mmd_box.currentData() or "") == "graphite",
      repr(dlg.mmd_box.currentData()))
idx = [dlg.mmd_box.itemData(i) for i in range(dlg.mmd_box.count())].index("sepia")
dlg.mmd_box.setCurrentIndex(idx)
wait(600)
check("T7 设置面板改选 → 编辑器生效", (js("window.getMmdTheme()") or "") == "sepia",
      js("window.getMmdTheme()"))
check("T7 设置面板改选 → QSettings 同步",
      (win._settings.value("mmdTheme", "") or "") == "sepia",
      repr(win._settings.value("mmdTheme", "")))
r = json.loads(js("(function(){return JSON.stringify({pv:(window.mermaid&&window.mermaid.mermaidAPI?"
                  "window.mermaid.mermaidAPI.getSiteConfig().themeVariables.primaryColor:'')||''});})()") or "{}")
check("T7 设置面板改选 → 图表变量随动（暖沙）", r.get("pv") == "#F5EBDD", json.dumps(r))
dlg.close()
wait(300)

# 右键菜单侧回读设置面板所选
js("(function(){var el=document.querySelector('#editor .mermaidblock');"
   "el.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:260,clientY:260}));"
   "var mi=document.querySelector('#blkmenu .mi[data-act=\"mmd-theme-sub\"]');"
   "mi.dispatchEvent(new MouseEvent('mouseover',{bubbles:true,cancelable:true}));return 'OK';})()")
wait(500)
r = js("(function(){var si=document.querySelectorAll('#submenu .si');var mark='';"
       "for(var i=0;i<si.length;i++){var t=si[i].textContent;if(t.indexOf('\\u2713')!==-1)mark=t;}"
       "return JSON.stringify({mark:mark});})()")
d = json.loads(r or "{}")
check("T7 右键子菜单回读设置面板所选（暖沙 ✓）", "暖沙" in (d.get("mark") or ""), r)
js("hidePops ? hidePops() : 0")

# ---------- T8 入口迁移 ----------
menus = {a.text(): a for a in win.menuBar().actions()}
view_txts = [a.text() for a in menus["视图(&V)"].menu().actions()] if "视图(&V)" in menus else []
check("T8 视图菜单已无「图表主题」", "图表主题" not in view_txts, json.dumps(view_txts, ensure_ascii=False)[:200])
check("T8 视图菜单其余项保留（全屏）", "全屏" in view_txts, json.dumps(view_txts, ensure_ascii=False)[:200])

# ---------- T9 旧值归一化（Python 侧） ----------
win._settings.setValue("mmdTheme", "forest")
win._set_mmd_theme("forest")
wait(500)
check("T9 _set_mmd_theme 归一化旧值 forest→mint",
      (win._settings.value("mmdTheme", "") or "") == "mint"
      and (js("window.getMmdTheme()") or "") == "mint",
      f"{win._settings.value('mmdTheme', '')} / {js('window.getMmdTheme()')}")
check("T9 状态栏提示含新主题名", "薄荷" in win._toast.text(), win._toast.text())

# 复原
win._set_mmd_theme("")
wait(400)

flush()
log = f"RESULT PASS={sum(1 for x in results if x.startswith('PASS'))} " \
      f"FAIL={sum(1 for x in results if x.startswith('FAIL'))}"
results.append(log)
flush()
print(log)
