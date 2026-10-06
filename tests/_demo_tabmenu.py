# -*- coding: utf-8 -*-
"""真实 GUI 演示：标签右键批量关闭菜单（dist66 = 源码同版）。
自动执行：右键标签 → 截图菜单；Ctrl+单击多选 → 截图高亮；
右键选中集 → 截图「关闭选中的 N 个标签页」并真实点击执行 → 截图关闭后状态。
全程使用真实 QMenu（非打桩），截图存 _demo/。
"""
import os
import sys
import tempfile

sys.path.insert(0, "E:/WorkBuddy/md-editor/src")

from PySide6.QtCore import QEvent, QEventLoop, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu

from mainwindow import MainWindow

OUT = "E:/WorkBuddy/md-editor/_demo"
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "demo_log.txt"), "w", encoding="utf-8")


def mark(s):
    LOG.write(s + "\n")
    LOG.flush()


app = QApplication(sys.argv)
win = None


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def shot(name):
    pm = app.primaryScreen().grabWindow(0)
    fp = os.path.join(OUT, name)
    pm.save(fp, "PNG")
    mark("shot saved: %s" % name)


def press(i, button=Qt.LeftButton, mods=Qt.NoModifier):
    c = win._tabbar.tabRect(i).center()
    ev = QMouseEvent(QEvent.MouseButtonPress, c, win._tabbar.mapToGlobal(c),
                     button, button, mods)
    return win.eventFilter(win._tabbar, ev)


def open_menu(idx, shotname, then_click=None):
    """真实弹出右键菜单，700ms 后截图（菜单在屏上），可选真实点击某菜单项。"""
    items = {}

    def during():
        m = QApplication.activePopupWidget()
        if isinstance(m, QMenu):
            items["texts"] = [a.text() for a in m.actions() if a.text()]
            shot(shotname)
            if then_click:
                for a in m.actions():
                    if a.text() == then_click:
                        a.triggered.emit()
                        mark("clicked menu item: %s" % then_click)
                        break
                else:
                    mark("MENU ITEM NOT FOUND: %s" % then_click)
            m.close()
        else:
            items["texts"] = None
            shot(shotname)
            mark("no popup menu visible!")

    QTimer.singleShot(700, during)
    win._on_tab_menu(win._tabbar.tabRect(idx).center())
    wait(250)
    return items.get("texts")


def main():
    global win
    win = MainWindow()
    win.show()
    win.activateWindow()
    win.raise_()
    wait(3200)

    # 准备 4 个文档
    tmp = tempfile.mkdtemp(prefix="demo_tabs_")
    files = []
    for n, body in (("甲-需求.md", "# 甲\n\n正文甲\n"),
                    ("乙-设计.md", "# 乙\n\n正文乙\n"),
                    ("丙-开发.md", "# 丙\n\n正文丙\n"),
                    ("丁-测试.md", "# 丁\n\n正文丁\n")):
        p = os.path.join(tmp, n)
        open(p, "w", encoding="utf-8").write(body)
        files.append(p)
    win._switching = False
    win._pending_switch = -1
    win._docs = []
    while win._tabbar.count():
        win._tabbar.removeTab(0)
    win._cur = -1
    win._closed_stack = []
    win._dirty = False
    win._clear_tab_multi()
    for p in files:
        win._add_doc(path=p, text=open(p, encoding="utf-8").read())
    wait(600)
    mark("tabs ready = %d" % win._tabbar.count())

    # 演示 1：右键「乙-设计」标签 → 全量批量关闭菜单截图
    items = open_menu(1, "demo1_右键批量菜单.png")
    mark("demo1 menu items = %s" % items)
    wait(300)

    # 演示 2：Ctrl+单击 乙、丙 → 多选高亮截图
    press(1, Qt.LeftButton, Qt.ControlModifier)
    press(2, Qt.LeftButton, Qt.ControlModifier)
    wait(200)
    mark("multi selected = %s" % sorted(win._tab_multi))
    shot("demo2_多选高亮.png")

    # 演示 3：右键选中的「丙」→ 菜单首位「关闭选中的 2 个标签页」→ 真实点击执行
    items = open_menu(2, "demo3_多选右键菜单.png", then_click="关闭选中的 2 个标签页")
    mark("demo3 menu items = %s" % items)
    wait(800)
    mark("after batch close: tabs = %d, names = %s" % (
        win._tabbar.count(),
        [os.path.basename(d.get("path") or "") for d in win._docs]))
    shot("demo4_批量关闭后.png")

    mark("DEMO OK")
    QTimer.singleShot(0, app.quit)


QTimer.singleShot(100, main)
app.exec()
LOG.close()
print("DEMO DONE")
