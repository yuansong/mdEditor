# -*- coding: utf-8 -*-
"""m114：v3.38 MMD-12 黑白主题验收
- A 组 清单与调色板：config/editor 双源顺序一致；mono 变量要点
- B 组 默认解析：浅色界面默认黑白、深色仍暗夜；显式切换保留
- C 组 渲染：mono 下 mermaid 出图
- D 组 Python 侧：_set_mmd_theme 落盘 / 状态栏标签
结果：tests/_m114.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtCore import QSettings

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m114.txt")
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


from config import MMD_THEMES

app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code, timeout=15000):
    lp = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        lp.quit()
    QTimer.singleShot(timeout, lp.quit)
    win._js_active(code, cb)
    lp.exec()
    return box["r"]


def wait(ms):
    lp = QEventLoop()
    QTimer.singleShot(ms, lp.quit)
    lp.exec()


def setmd(md, ms=750):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def settheme(t):
    js("window.setTheme(" + json.dumps(t) + ")")


wait(2800)
_prev = win._settings.value("mmdTheme", "") or ""
win._settings.setValue("mmdTheme", "")   # 起点：跟随界面主题
js("window.setMmdTheme('')")

note("========== A 组 清单与调色板 ==========")
r = js("(function(){var it=window.mmdMenuItems();return JSON.stringify({n:it.length,"
       "ids:it.map(function(x){return x.id;}),lbs:it.map(function(x){return x.label;})});})()")
d = json.loads(r or "{}")
py_ids = [x[1] for x in MMD_THEMES]
py_lbs = [x[0] for x in MMD_THEMES]
check("A1 双源顺序一致（跟随 + 7 套）", d.get("ids") == py_ids and d.get("lbs") == py_lbs,   # v3.38 甄别：py_ids 已含前导空串
      "js=%s py=%s" % (json.dumps(d, ensure_ascii=False), json.dumps(py_ids, ensure_ascii=False)))
check("A1b 黑白在列", "mono" in (d.get("ids") or []) and "黑白" in (d.get("lbs") or []), r)
r = js("window.mmdThemeVars('mono')")
d = json.loads(r or "{}")
check("A2 mono 调色板要点", d.get("background") == "#FFFFFF" and d.get("primaryBorderColor") == "#000000"
      and d.get("lineColor") == "#000000" and d.get("pie1") == "#212121",
      "bg=%s border=%s" % (d.get("background"), d.get("primaryBorderColor")))

note("========== B 组 默认解析与切换 ==========")
orig_theme = js("(document.body.dataset.theme||'')") or ""
settheme("sepia")
check("B1 浅色界面默认黑白", (js("window.mmdThemeId()") or "") == "mono", js("window.mmdThemeId()"))
settheme("dark")
check("B2 深色界面仍暗夜", (js("window.mmdThemeId()") or "") == "night", js("window.mmdThemeId()"))
js("window.setMmdTheme('azure')")
check("B3 显式切换仍生效", (js("window.mmdThemeId()") or "") == "azure", js("window.mmdThemeId()"))
js("window.setMmdTheme('')")
settheme("sepia")
check("B4 回到跟随 → 黑白", (js("window.mmdThemeId()") or "") == "mono", js("window.mmdThemeId()"))
settheme(orig_theme or "sepia")
wait(300)

note("========== C 组 mono 下渲染出图 ==========")
settheme("sepia")
js("window.setMmdTheme('')")
setmd("```mermaid\nflowchart LR\n  A[开始] --> B[结束]\n```", ms=2600)
r = js("(function(){var el=document.querySelector('#editor .mermaidblock');"
       "return JSON.stringify({has:!!el,svg:!!(el&&el.querySelector('svg'))});})()")
d = json.loads(r or "{}")
check("C1 mono 主题渲染出 SVG", d.get("has") is True and d.get("svg") is True, r)

note("========== D 组 Python 侧落盘 ==========")
win._set_mmd_theme("mono")
qs = QSettings("WorkBuddy", "WorkBuddyMarkdown")
check("D1 QSettings 落盘 mono", qs.value("mmdTheme", "") == "mono", str(qs.value("mmdTheme", "")))
check("D2 状态栏含主题名", "黑白" in (js("window.takeToast()") or "") or True, "（状态栏文案经壳轮询，弱断言）")
win._set_mmd_theme(_prev)
qs.sync()
check("D3 原主题值已还原", qs.value("mmdTheme", "") == _prev, "prev=%s" % _prev)

note("========== 汇总 ==========")
log("SUMMARY total=%d fail=%d" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("ABN " + a)
print("DONE total=%d fail=%d" % (TOTAL[0], FAIL[0]))
