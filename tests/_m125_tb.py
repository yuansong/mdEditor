# -*- coding: utf-8 -*-
"""m125：v3.38 TB-1 —— 主工具栏隐藏（折叠）后的「展开」入口验收

用户报告：某个工具栏折叠起来后没有「展开」按钮，用户无法再展开工具栏。
根因：左侧竖向主工具栏可被隐藏（工具栏/菜单栏右键 → 取消勾选「主工具栏」），
隐藏后窗口内不再有任何恢复入口 —— 连工具栏顶部的侧栏开关 « 也一并消失。
修复：① 视图菜单新增「显示 / 隐藏工具栏」（可勾选，Ctrl+Shift+T）
     ② 工具栏隐藏时，窗口左侧边缘常驻一个「»」展开按钮（置顶可点）
     ③ 右键菜单 createPopupMenu 复用同一 QAction，避免两套互不同步的开关
     ④ 可见性持久化 ui/toolbarVisible，重启保持。
"""
import os, sys

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, "E:/WorkBuddy/md-editor/src")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication(sys.argv)
from mainwindow import MainWindow

win = MainWindow()
win.show()

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m125.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def state():
    tb = win._tool_tb
    b = win._btn_tb_show
    act = getattr(win, "_act_toolbar", None)
    return {
        "tbVis": tb.isVisible(),
        "btnVis": b.isVisible(),
        "btnText": b.text(),
        "btnTip": b.toolTip(),
        "btnPos": (b.x(), b.y()),
        "btnSize": (b.width(), b.height()),
        "actExists": act is not None,
        "actChecked": (act.isChecked() if act is not None else None),
        "actCheckable": (act.isCheckable() if act is not None else None),
        "actSeq": (act.shortcut().toString() if act is not None else ""),
        "saved": win._settings.value("ui/toolbarVisible", True, type=bool),
    }


wait(2600)

# ---------- A 初始态：工具栏可见，边缘按钮不出现 ----------
s0 = state()
check("A1 主工具栏初始可见", s0["tbVis"] is True, str(s0))
check("A2 工具栏可见时边缘展开按钮隐藏（不干扰编辑区）", s0["btnVis"] is False, str(s0))
check("A3 视图菜单存在「显示 / 隐藏工具栏」且可勾选",
      s0["actExists"] and s0["actCheckable"] is True, str(s0))
check("A4 菜单项初始为勾选态（与工具栏可见性一致）", s0["actChecked"] is True, str(s0))
check("A5 菜单项带默认快捷键 Ctrl+Shift+T", "Ctrl+Shift+T" in s0["actSeq"], s0["actSeq"])

# ---------- B 隐藏工具栏（模拟用户走菜单 / 右键取消勾选）----------
win._act_toolbar.trigger()      # checkable：trigger 会翻转勾选并回调 toggle_toolbar
wait(200)
s1 = state()
check("B1 工具栏被隐藏", s1["tbVis"] is False, str(s1))
check("B2 隐藏后**出现展开按钮**（用户报告的核心缺陷）", s1["btnVis"] is True, str(s1))
check("B3 展开按钮文案为 »", s1["btnText"] == "»", s1["btnText"])
check("B4 展开按钮 tooltip 明示用途与替代入口",
      "展开" in s1["btnTip"] and "Ctrl+Shift+T" in s1["btnTip"], s1["btnTip"])
check("B5 展开按钮贴在窗口左边缘（x<30）", s1["btnPos"][0] < 30, str(s1["btnPos"]))
check("B6 展开按钮位于菜单栏下方（不被菜单栏遮挡）",
      s1["btnPos"][1] >= win.menuBar().height(), str(s1["btnPos"]))
check("B7 菜单勾选态同步为未勾选", s1["actChecked"] is False, str(s1))
check("B8 隐藏状态已持久化", s1["saved"] is False, str(s1["saved"]))

# ---------- C 点击展开按钮 → 工具栏恢复 ----------
win._btn_tb_show.click()
wait(200)
s2 = state()
check("C1 点展开按钮后工具栏恢复显示", s2["tbVis"] is True, str(s2))
check("C2 恢复后展开按钮自动隐藏", s2["btnVis"] is False, str(s2))
check("C3 恢复后菜单勾选同步回 True", s2["actChecked"] is True, str(s2))
check("C4 恢复状态已持久化", s2["saved"] is True, str(s2["saved"]))

# ---------- D 快捷键路径（Ctrl+Shift+T）----------
act = win._act_toolbar
act.setChecked(True)
win.set_toolbar_visible(True)
wait(150)
try:
    from PySide6.QtGui import QKeySequence
    act.setShortcut(QKeySequence("Ctrl+Shift+T"))
    win.addAction(act)
    # 直接触发动作（等价于快捷键命中），验证 checkable 语义不会反向
    act.trigger()
    wait(200)
    s3 = state()
    check("D1 快捷键路径可隐藏工具栏", s3["tbVis"] is False, str(s3))
    check("D2 快捷键隐藏后同样出现展开按钮", s3["btnVis"] is True, str(s3))
    act.trigger()
    wait(200)
    s4 = state()
    check("D3 再次触发恢复工具栏", s4["tbVis"] is True, str(s4))
    check("D4 恢复后展开按钮隐藏", s4["btnVis"] is False, str(s4))
except Exception as e:                                   # pragma: no cover
    check("D1 快捷键路径可隐藏工具栏", False, "EXC %s" % e)

# ---------- E 右键菜单（createPopupMenu）可用且同源 ----------
try:
    pm = win.createPopupMenu()
    acts = pm.actions()
    check("E1 右键菜单非空（工具栏被隐藏后仍可就地恢复）", len(acts) >= 1, str([a.text() for a in acts]))
    check("E2 右键菜单复用视图菜单同一 action（状态同源）",
          any(a is win._act_toolbar for a in acts), str([a.text() for a in acts]))
except Exception as e:                                   # pragma: no cover
    check("E1 右键菜单非空（工具栏被隐藏后仍可就地恢复）", False, "EXC %s" % e)

# ---------- F 窗口缩放后展开按钮仍就位 ----------
win.set_toolbar_visible(False)
wait(150)
win.resize(1000, 700)
wait(250)
s5 = state()
check("F1 缩放后展开按钮仍可见", s5["btnVis"] is True, str(s5))
check("F2 缩放后按钮仍在窗口可视范围内",
      0 <= s5["btnPos"][0] < 40 and 0 <= s5["btnPos"][1] < win.height(), str(s5["btnPos"]))

# ---------- 收尾：复位为可见，避免污染其它探针 ----------
win.set_toolbar_visible(True)
wait(150)
s6 = state()
check("Z1 收尾复位：工具栏可见", s6["tbVis"] is True, str(s6))
check("Z2 收尾复位：持久化写回 True", s6["saved"] is True, str(s6["saved"]))

with open(OUT, "w", encoding="utf-8") as f:
    for s_, name, detail in _log:
        f.write("%s %s%s\n" % (s_, name, (" | " + detail) if detail and s_ == "FAIL" else ""))
print("done")
