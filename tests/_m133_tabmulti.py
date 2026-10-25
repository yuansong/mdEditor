# -*- coding: utf-8 -*-
"""m133 —— v3.38（TAB-B）Notepad++ 风格多选批量关闭 +（HELP-1）使用手册验收

A 组：Ctrl/Shift 多选与高亮、固定标签排除、普通单击清除
B 组：多选右键菜单（关闭选中的 N 个标签页 / 取消多选）、右键保持多选（回归点：
      eventFilter 误把右键当普通单击清多选的缺陷）、关闭所有标签页菜单项
C 组：批量关闭行为（选中集关闭 / 全关 / 固定跳过）
D 组：汇总确认对话框（全部保存 / 全部不保存 / 取消，含已命名 dirty 文档）
E 组：使用手册（帮助菜单项、窗口、只读渲染内容）
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from PySide6.QtCore import QEvent, QEventLoop, QTimer, Qt
from PySide6.QtGui import QMouseEvent

import mainwindow as MW
from mainwindow import MainWindow
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m133.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))
    with open(os.path.join(os.path.dirname(OUT), "_m133_mark.log"), "a", encoding="utf-8") as _mf:
        _mf.write(("PASS " if cond else "FAIL ") + name + " | " + str(detail)[:60] + "\n")


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


# ---------- QMessageBox 打桩（捕获批量确认对话框） ----------
class FakeBtn:
    def __init__(self, text):
        self._text = text


class FakeBox:
    last = None
    click_next = None          # 测试注入：exec 后 clickedButton 返回该按钮
    # QMessageBox 类常量（产品代码 box.setIcon(QMessageBox.Question) 会取用）
    Question = 4
    Information = 1
    Warning = 2
    Critical = 3
    Save = 0
    Discard = 8
    Cancel = 4194304
    AcceptRole = 0
    DestructiveRole = 2
    RejectRole = 3

    def __init__(self, parent=None):
        self.btns = []          # [(text, role, obj)]
        self._text = ""
        self._title = ""
        FakeBox.last = self

    def setWindowTitle(self, t):
        self._title = t

    def setIcon(self, icon):
        pass

    def setText(self, t):
        self._text = t

    def addButton(self, text, role):
        b = FakeBtn(text)
        self.btns.append((text, role, b))
        return b

    def exec(self):
        return 0

    def clickedButton(self):
        # 必须返回 addButton 创建的**同一实例**（产品代码用 is 比较）
        want = FakeBox.click_next
        for text, _role, obj in self.btns:
            if text == want:
                return obj
        return self.btns[-1][2] if self.btns else FakeBtn("取消")


_box_backup = MW.QMessageBox
MW.QMessageBox = FakeBox


class FakeAct:
    def __init__(self, text):
        self._text = text
        self._enabled = True
        self._cbs = []

    def text(self):
        return self._text

    def setEnabled(self, v):
        self._enabled = bool(v)

    def isEnabled(self):
        return self._enabled

    def setCheckable(self, v):
        pass

    def setChecked(self, v):
        # 严格镜像真实 QAction：非 bool 直接抛 TypeError（防 setChecked(None) 类缺陷逃逸）
        if not isinstance(v, bool):
            raise TypeError("QAction.setChecked expects bool, got %r" % (v,))
        self._checked = bool(v)

    @property
    def triggered(self):
        return self

    def connect(self, fn):
        self._cbs.append(fn)

    def fire(self):
        for f in list(self._cbs):
            f()


class FakeMenu:
    last = None

    def __init__(self, parent=None):
        self.acts = []
        self.seps = 0
        FakeMenu.last = self

    def addAction(self, text):
        a = FakeAct(text)
        self.acts.append(a)
        return a

    def addSeparator(self):
        self.seps += 0 if False else 1

    def exec(self, pos=None):
        return None


MW.QMenu = FakeMenu

# ---------- 环境 ----------
app = QApplication(sys.argv)   # 必须先建 QApplication，否则 MainWindow 直接硬崩
win = MainWindow()
win.show()
wait(2600)

tmp = tempfile.mkdtemp(prefix="m133_")
FILES = []
for _n, _body in (("a.md", "# 文档a\n\n正文A\n"), ("b.md", "# 文档b\n\n正文B\n"),
                  ("c.md", "# 文档c\n\n正文C\n"), ("d.md", "# 文档d\n\n正文D\n")):
    _p = os.path.join(tmp, _n)
    with open(_p, "w", encoding="utf-8") as _f:
        _f.write(_body)
    FILES.append(_p)


def reset_docs(paths):
    win._switching = False
    win._pending_switch = -1
    win._docs = []
    while win._tabbar.count():
        win._tabbar.removeTab(0)
    win._cur = -1
    win._closed_stack = []
    win._dirty = False
    win._clear_tab_multi()
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            win._add_doc(path=p, text=f.read())
    wait(300)


def paths():
    return [os.path.basename(d.get("path") or "") for d in win._docs]


def press(i, button=Qt.LeftButton, mods=Qt.NoModifier):
    """向标签栏 eventFilter 直接派发鼠标按下事件（不走 QTabBar 内部逻辑）。"""
    c = win._tabbar.tabRect(i).center()
    ev = QMouseEvent(QEvent.MouseButtonPress, c, win._tabbar.mapToGlobal(c),
                     button, button, mods)
    return win.eventFilter(win._tabbar, ev)


def selected_color(i):
    c = win._tabbar.tabTextColor(i)
    return c.isValid()


# ---------- A 多选与高亮 ----------
check("MARK A 多选与高亮 begin", True, "")
reset_docs(FILES)
press(1, Qt.LeftButton, Qt.ControlModifier)
wait(120)
check("A1 Ctrl+单击标签1 → 选中 {1}", win._tab_multi == {1}, str(win._tab_multi))
check("A2 标签1 着强调色（文字色生效）", selected_color(1), "")
press(3, Qt.LeftButton, Qt.ControlModifier)
wait(120)
check("A3 Ctrl+单击标签3 → {1,3}", win._tab_multi == {1, 3}, str(win._tab_multi))
press(1, Qt.LeftButton, Qt.ControlModifier)
wait(120)
check("A4 再次 Ctrl+单击标签1 → 取消 {3}", win._tab_multi == {3}, str(win._tab_multi))
win._tab_multi.add(1)
press(0, Qt.LeftButton, Qt.ShiftModifier)
wait(120)
check("A5 Shift+单击标签0 → 锚点3区间 {0,1,2,3}",
      win._tab_multi == {0, 1, 2, 3}, str(win._tab_multi))
# 固定标签不参与
win._toggle_pin(0)
wait(150)
win._tab_multi.clear()
press(0, Qt.LeftButton, Qt.ControlModifier)
wait(120)
check("A6 固定标签 Ctrl+单击不入选", 0 not in win._tab_multi, str(win._tab_multi))
press(2, Qt.LeftButton, Qt.ControlModifier)
wait(120)
n_before = win._cur
press(3, Qt.LeftButton)     # 普通单击 → 切换 + 清多选
wait(500)
check("A7 普通单击清多选并切换", win._tab_multi == set() and win._cur == 3,
      "multi=%s cur=%s" % (win._tab_multi, win._cur))

# ---------- B 多选右键菜单 ----------
check("MARK B 多选右键菜单 begin", True, "")
reset_docs(FILES)
press(1, Qt.LeftButton, Qt.ControlModifier)
press(2, Qt.LeftButton, Qt.ControlModifier)
wait(120)


def open_menu(idx):
    FakeMenu.last = None
    win._on_tab_menu(win._tabbar.tabRect(idx).center())
    return FakeMenu.last


m = open_menu(2)            # 右键命中选中集
texts = [a.text() for a in m.acts]
check("B1 右键选中集 → 菜单首项「关闭选中的 2 个标签页」",
      texts and texts[0].startswith("关闭选中的 2 个标签页"), str(texts))
check("B2 菜单含「取消多选」", "取消多选" in texts, str(texts))
check("B3 右键命中选中集后多选保持（右键不清多选，回归点）",
      win._tab_multi == {1, 2}, str(win._tab_multi))
m2 = open_menu(0)           # 右键选中集外 → 清多选、普通菜单
texts2 = [a.text() for a in m2.acts]
check("B4 右键选中集外 → 清多选且菜单无「关闭选中」项",
      win._tab_multi == set() and not any(t.startswith("关闭选中的") for t in texts2),
      "multi=%s texts=%s" % (win._tab_multi, texts2))
check("B5 普通菜单含「关闭所有标签页」", "关闭所有标签页" in texts2, str(texts2))
check("B6 普通菜单含四项批量关闭 + 关闭所有未修改",
      all(t in texts2 for t in ("关闭其它所有", "关闭左侧所有", "关闭右侧所有",
                                "关闭所有未修改")), str(texts2))

# ---------- C 批量关闭行为 ----------
check("MARK C 批量关闭行为 begin", True, "")
reset_docs(FILES)
win._tab_multi = {1, 3}
win._batch_close(sorted(win._tab_multi))
wait(400)
check("C1 关闭选中 {1,3} → 剩 a/c", paths() == ["a.md", "c.md"], str(paths()))
win._close_all_tabs()
wait(500)
check("C2 关闭所有 → 空栈自动补空白页",
      len(win._docs) == 1 and win._docs[0].get("path") is None, str(paths()))
reset_docs(FILES)
win._toggle_pin(1)
wait(150)
FakeBox.click_next = None
win._close_all_tabs()
wait(500)
check("C3 关闭所有跳过固定标签", paths() == ["b.md"], str(paths()))
win._toggle_pin(1)
wait(120)

# ---------- D 汇总确认对话框 ----------
check("MARK D 汇总确认对话框 begin", True, "")
reset_docs(FILES)
win._docs[1]["dirty"] = True          # b.md 已命名但未保存（非当前标签，脏标记不被实时覆盖）
win._docs[1]["content"] = "# 文档b改\n\n新正文B\n"
FakeBox.last = None
FakeBox.click_next = "取消"
n0 = win._tabbar.count()
win._batch_close([0, 1, 2, 3])
wait(300)
check("D1 汇总确认框弹出", FakeBox.last is not None, "")
check("D2 三键文案 = 全部保存/全部不保存/取消",
      [t for t, _r, _o in FakeBox.last.btns] == ["全部保存", "全部不保存", "取消"],
      str(FakeBox.last.btns))
check("D3 取消 → 整批不动", win._tabbar.count() == n0, str(win._tabbar.count()))
FakeBox.click_next = "全部不保存"
win._batch_close([0, 1, 2, 3])
wait(300)
check("D4 全部不保存 → 全关且文件原样",
      len(win._docs) == 1 and win._docs[0].get("path") is None, "")
with open(FILES[1], "r", encoding="utf-8") as f:
    _b = f.read()
check("D5 b.md 磁盘内容未被改写", "文档b" in _b, _b[:20])
reset_docs(FILES)
win._docs[1]["dirty"] = True
win._docs[1]["content"] = "# 文档b改\n\n新正文B\n"
FakeBox.click_next = "全部保存"
win._batch_close([0, 1, 2, 3])
wait(400)
with open(FILES[1], "r", encoding="utf-8") as f:
    _b2 = f.read()
check("D6 全部保存 → 已命名 dirty 文档落盘新内容", "文档b改" in _b2, _b2[:20])
check("D7 保存后整批关闭", len(win._docs) == 1 and win._docs[0].get("path") is None, "")
reset_docs(FILES)
FakeBox.last = None
FakeBox.click_next = None
win._batch_close([0])                 # 全部已保存 → 不弹框
wait(300)
check("D8 无未保存 → 不弹确认直接关（关 1 剩 3）",
      FakeBox.last is None and win._tabbar.count() == 3, str(win._tabbar.count()))

# ---------- E 使用手册 ----------
check("MARK E 使用手册 begin", True, "")
acts = win._shortcut_acts
check("E1 帮助菜单注册「使用手册」动作", "使用手册" in acts, str(list(acts.keys())))
md = win._manual_md()
check("E2 手册内容完整（>3000 字符且含关键章节）",
      len(md) > 3000 and "标签页系统" in md and "多选与批量关闭" in md
      and "快捷键速查" in md, "len=%d" % len(md))
win._show_manual()
wait(1600)
dlg = getattr(win, "_manual_dlg", None)
check("E3 手册窗口打开且可见", isinstance(dlg, QDialog) and dlg.isVisible(), "")
try:
    _lock = win._js_view(dlg._view, "window.__previewLock === true || document.body !== null")
    _md_len = None
    _holder = {}

    def _cb(res):
        _holder["v"] = res

    from PySide6.QtCore import QEventLoop as _EL
    _lp = _EL()

    def _cb2(res):
        _holder["v"] = res
        _lp.quit()

    dlg._view.page().runJavaScript("window.getMarkdown ? window.getMarkdown().length : -1",
                                   0, _cb2)
    _lp.exec()
    _md_len = _holder.get("v")
except Exception as e:                                      # noqa: BLE001
    _md_len = "ERR:%s" % e
check("E4 手册视图装载了完整 Markdown（getMarkdown 长度>3000）",
      isinstance(_md_len, (int, float)) and _md_len > 3000, str(_md_len))
dlg.close()

# ---------- 收尾：复位 QSettings 防污染 ----------
win._clear_tab_multi()
FakeBox.click_next = None
MW.QMessageBox = _box_backup

print("========== 汇总 ==========")
npass = sum(1 for s, _n, _d in _log if s == "PASS")
nfail = len(_log) - npass
print("PASS=%d FAIL=%d" % (npass, nfail))
with open(OUT, "w", encoding="utf-8") as f:
    for s, n, d in _log:
        line = "PASS %s" % n if s == "PASS" else "FAIL %s | %s" % (n, d)
        print(line)
        f.write(line + "\n")

app = QApplication.instance()
QTimer.singleShot(0, app.quit)
app.exec()
