# -*- coding: utf-8 -*-
"""v3.20 冒烟测试：大纲显示级别可设置（默认 3 级）/ 文件列表显示模式
（默认跟随当前文档，可指定空白项）。"""
import json
import os
import sys
import tempfile

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, Qt

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke24.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


app = QApplication(sys.argv)
from mainwindow import MainWindow

# 前置：还原持久化设置（清除上次运行残留）——必须与主窗口同一存储、且在窗口创建前
from PySide6.QtCore import QSettings
_st = QSettings("WorkBuddy", "WorkBuddyMarkdown")
_st.setValue("outlineLevel", 3)
_st.setValue("fileListMode", "current")
_st.sync()

win = MainWindow()
win.show()


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


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


MD = "# 一级 A\n\n## 二级 A1\n\n### 三级 A1a\n\n#### 四级 A1a-i\n\n##### 五级 A1a-i-1\n\n# 一级 B\n\n正文。"
wait(3000)  # 等页面就绪
js("window.setMarkdown(%r)" % MD)
wait(1800)  # 等主窗口轮询 collect() 刷新侧栏大纲


def outline_state():
    """收集大纲树：每项 (index, level估计, expanded)"""
    sb = win._sidebar

    def walk(item, depth, out):
        # v3.31（#8）：剥掉大纲项的分节字数后缀「　·　N 字」，按标题原文断言
        out.append({"idx": item.data(0, Qt.UserRole), "depth": depth,
                    "expanded": item.isExpanded(),
                    "text": item.text(0).split("　·　")[0]})
        for k in range(item.childCount()):
            walk(item.child(k), depth + 1, out)

    tops = []
    for t in range(sb.outline.topLevelItemCount()):
        walk(sb.outline.topLevelItem(t), 1, tops)
    return tops


# ---------- 1) 默认大纲显示级别 = 3 ----------
check("默认：win/sidebar 大纲级别均为 3",
      win._outline_level == 3 and win._sidebar._outline_level == 3,
      f"{win._outline_level}/{win._sidebar._outline_level}")
st = outline_state()
by_text = {d["text"]: d for d in st}
check("级别3：全部 6 个标题都在树中（深层折叠但可见）",
      len(st) == 6 and all(t in by_text for t in
                           ("一级 A", "二级 A1", "三级 A1a", "四级 A1a-i",
                            "五级 A1a-i-1", "一级 B")), f"n={len(st)}")
check("级别3：h1 展开 / h3 可见但折叠 / h4 挂在 h3 下（depth=4）",
      by_text["一级 A"]["expanded"] is True
      and by_text["三级 A1a"]["expanded"] is False
      and by_text["四级 A1a-i"]["depth"] == 4,
      json.dumps(st, ensure_ascii=False)[:300])

# ---------- 2) 切换级别 = 1：全部折叠但仍在树中 ----------
win.set_outline_level(1)
wait(600)
st = outline_state()
by_text = {d["text"]: d for d in st}
check("级别1：6 项仍在树中、全部折叠",
      len(st) == 6 and by_text["一级 A"]["expanded"] is False
      and by_text["二级 A1"]["expanded"] is False,
      json.dumps(st, ensure_ascii=False)[:300])
check("级别1：QSettings 已持久化 + 状态栏提示",
      str(win._settings.value("outlineLevel")) == "1"
      and "大纲显示级别：1" in win._toast.text(),
      win._toast.text())

# ---------- 3) 切换级别 = 5：h4 展开 / h5 折叠 ----------
win.set_outline_level(5)
wait(600)
st = outline_state()
by_text = {d["text"]: d for d in st}
check("级别5：h4 展开、h5 折叠",
      by_text["四级 A1a-i"]["expanded"] is True
      and by_text["五级 A1a-i-1"]["expanded"] is False,
      json.dumps(st, ensure_ascii=False)[:300])
win.set_outline_level(3)   # 复原默认
wait(600)

# ---------- 4) 设置对话框联动 ----------
from dialogs import SettingsDialog
dlg = SettingsDialog(win)
dlg.show()
wait(300)
ok_dlg = (dlg.outline_level_box.currentData() == 3
          and dlg.file_mode_box.currentData() == "current")
dlg.close()
check("设置对话框：大纲级别=3级、文件列表=当前的（与主窗口同步）", ok_dlg,
      f"lvl={dlg.outline_level_box.currentData()} fm={dlg.file_mode_box.currentData()}")

# ---------- 5) 文件列表空白项模式 ----------
tmpdir = tempfile.mkdtemp()
md1 = os.path.join(tmpdir, "a.md")
with open(md1, "w", encoding="utf-8") as f:
    f.write("# A\n\n内容")
win.file_path = md1
sb = win._sidebar
sb.set_root(md1)
wait(200)
n_before = sb.file_list.count()
check("current 模式：文件列表跟随当前文档目录（有内容）",
      n_before > 0 and sb._cur_dir == tmpdir and sb._file_mode == "current",
      f"n={n_before} mode={sb._file_mode} dir={sb._cur_dir}")

win.set_file_list_mode("blank")
wait(300)
check("blank 模式：列表清空 + 头部显示「空白」+ 不跟随文档",
      sb.file_list.count() == 0 and sb.file_header.text() == "空白"
      and sb._file_mode == "blank",
      f"n={sb.file_list.count()} header={sb.file_header.text()}")
sb.set_root(md1)   # blank 模式下应被忽略
wait(200)
check("blank 模式：set_root 被忽略（列表仍为空）", sb.file_list.count() == 0)
check("blank 模式：QSettings 已持久化",
      str(win._settings.value("fileListMode")) == "blank",
      str(win._settings.value("fileListMode")))

# ---------- 6) blank 持久化后，启动路径（MainWindow __init__ 同款调用）生效 ----------
from sidebar import Sidebar
sb2 = Sidebar(win)
sb2.set_outline_level(3)
sb2.set_file_mode("blank")   # 与 MainWindow.__init__ 中的启动调用一致
wait(300)
check("持久化：启动路径应用 blank 模式（列表为空 + 头部「空白」）",
      sb2.file_list.count() == 0 and sb2.file_header.text() == "空白"
      and sb2._file_mode == "blank",
      f"n={sb2.file_list.count()} h={sb2.file_header.text()}")
sb2.setParent(None)
sb2.deleteLater()

win.set_file_list_mode("current")
wait(300)
check("切回 current：恢复显示当前文档目录内容",
      win._sidebar.file_list.count() > 0
      and win._sidebar._cur_dir == tmpdir
      and str(win._settings.value("fileListMode")) == "current",
      f"n={win._sidebar.file_list.count()}")

# 复原（与主窗口同一存储）
win._settings.setValue("outlineLevel", 3)
win._settings.setValue("fileListMode", "current")
win._settings.sync()
_st.setValue("outlineLevel", 3)
_st.setValue("fileListMode", "current")
_st.sync()
results.append("INFO | 测试完成，QSettings 已复原 | ")
flush()
print("SMOKE24 DONE")
