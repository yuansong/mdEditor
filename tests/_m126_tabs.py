# -*- coding: utf-8 -*-
"""m126：v3.38 TAB-1 ~ TAB-6 —— 标签页「选中 / 关闭 / 批量关闭 / 复制路径 / 重开 / 切换 / 全部保存」

用户原话：请检查「选中标签页并支持关闭 notepad」是否真的已实现；若确认未实现，请在现有
标签页组件的架构与代码风格下补全该功能，保持与现有实现一致。
设计依据：docs/archive/标签页右键菜单方案-批量关闭与复制路径-v3.38.md

本探针只走 Qt 侧（不依赖 JS 回包）：
  · 右键菜单用 FakeMenu 替身捕获结构（exec 不阻塞）
  · 「选中态」以 _cur / _tabbar.currentIndex() / _docs 三者一致为准
  · 「关闭」校验 标签数、_cur 落点、path 不串位、_closed_stack 记录
"""
import os, sys, tempfile, shutil

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, "E:/WorkBuddy/md-editor/src")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, QEvent, Qt
from PySide6.QtGui import QMouseEvent

app = QApplication(sys.argv)
import mainwindow as MW
from mainwindow import MainWindow


# ---------------- 菜单替身 ----------------
class FakeAct:
    def __init__(self, text):
        self._text = text
        self._enabled = True
        self._checked = False
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
        if not isinstance(v, bool):
            raise TypeError("QAction.setChecked expects bool, got %r" % (v,))
        self._checked = bool(v)

    def isChecked(self):
        return self._checked

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
        self.seps += 1

    def exec(self, pos=None):
        return None


MW.QMenu = FakeMenu

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m126.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def reset_docs(paths):
    """把标签环境复位成给定文件集（全 Python 侧操作，不等 JS）。"""
    win._switching = False
    win._pending_switch = -1
    win._docs = []
    while win._tabbar.count():
        win._tabbar.removeTab(0)
    win._cur = -1
    win._closed_stack = []
    win._dirty = False
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            win._add_doc(path=p, text=f.read())
    wait(400)


def paths():
    return [d.get("path") for d in win._docs]


def tabs():
    return [win._tabbar.tabText(i) for i in range(win._tabbar.count())]


def names():
    """标签文本去掉前缀脏标记 / 固定标记后的文件名部分。"""
    return [t.replace("•", "").replace("📌", "").strip() for t in tabs()]


def open_menu(idx):
    """在指定标签上触发右键菜单（FakeMenu 捕获结构）。"""
    FakeMenu.last = None
    r = win._tabbar.tabRect(idx)
    win._on_tab_menu(r.center())
    return FakeMenu.last


def menu_of(idx):
    m = open_menu(idx)
    return {a.text(): a for a in m.acts}, m


tmp = tempfile.mkdtemp(prefix="m126_")
FILES = []
for _n, _body in (("a.md", "# 文档a\n\n正文A\n"), ("b.md", "# 文档b\n\n正文B\n"),
                  ("c.md", "# 文档c\n\n正文C\n")):
    _p = os.path.join(tmp, _n)
    with open(_p, "w", encoding="utf-8") as _f:
        _f.write(_body)
    FILES.append(_p)

win = MainWindow()
_sa_backup = win._settings.value("startupAction")
_lf_backup = win._settings.value("lastFile")

win.show()
wait(2600)

# ---------- A 选中态基线 ----------
reset_docs(FILES)
check("A1 三个文件 → 三个标签", win._tabbar.count() == 3, str(win._tabbar.count()))
check("A2 选中态三源一致（_cur == currentIndex == 末位）",
      win._cur == 2 and win._tabbar.currentIndex() == 2, "cur=%s idx=%s" % (win._cur, win._tabbar.currentIndex()))
check("A3 标签文本为文件名", names() == ["a.md", "b.md", "c.md"], str(tabs()))
check("A4 数据层与标签层同长（无幽灵文档）", len(win._docs) == win._tabbar.count(), "")

# ---------- B 右键菜单：结构 / 右键即选中 / 置灰 ----------
mids, _m = menu_of(1)
wait(500)          # 右键即选中是异步切换（getMarkdown 回包后才落 _cur）
_expect = ["固定 / 取消固定标签", "关闭\tCtrl+W", "关闭其它所有", "关闭左侧所有", "关闭右侧所有",
           "关闭所有未修改", "关闭所有标签页", "在资源管理器中显示", "在终端中打开",
           "复制文件名", "复制文件路径", "复制所在目录"]
check("B1 菜单项齐备（11 项，TAB-7 固定 + TAB-10 终端）",
      [a.text() for a in _m.acts] == _expect, str([a.text() for a in _m.acts]))
check("B2 菜单含 2 条分隔线（关闭组 / 文件组）", _m.seps == 2, str(_m.seps))
check("B3 右键即选中（右键第 2 个标签后 _cur 变为 1）", win._cur == 1, "cur=%s" % win._cur)
check("B4 有路径 → 复制三项均可点",
      mids["复制文件名"].isEnabled() and mids["复制文件路径"].isEnabled()
      and mids["复制所在目录"].isEnabled(), "")
_m0 = menu_of(0)[1]
_d0 = {a.text(): a for a in _m0.acts}
check("B5 首标签「关闭左侧所有」置灰", _d0["关闭左侧所有"].isEnabled() is False, "")
check("B6 首标签「关闭右侧所有」可点", _d0["关闭右侧所有"].isEnabled() is True, "")
_m2 = menu_of(2)[1]
_d2 = {a.text(): a for a in _m2.acts}
check("B7 末标签「关闭右侧所有」置灰", _d2["关闭右侧所有"].isEnabled() is False, "")
check("B8 末标签「关闭左侧所有」可点", _d2["关闭左侧所有"].isEnabled() is True, "")
check("B9 「在资源管理器中显示」有路径时可点（收编 show_in_explorer）",
      _d2["在资源管理器中显示"].isEnabled() is True, "")

# ---------- C 未命名文档：复制项置灰 ----------
reset_docs(FILES)
_uidx = win._add_doc(path=None, text="")
wait(300)
_mu = menu_of(_uidx)[1]
_du = {a.text(): a for a in _mu.acts}
check("C1 未命名标签：复制文件名置灰", _du["复制文件名"].isEnabled() is False, "")
check("C2 未命名标签：复制文件路径置灰", _du["复制文件路径"].isEnabled() is False, "")
check("C3 未命名标签：复制所在目录置灰", _du["复制所在目录"].isEnabled() is False, "")
check("C4 未命名标签：仍在资源管理器中显示置灰",
      _du["在资源管理器中显示"].isEnabled() is False, "")

# ---------- D 关闭当前（中间）标签 ----------
reset_docs(FILES)
win._tabbar.setCurrentIndex(1)
wait(450)
win._close_tab(1)
wait(450)
check("D1 关闭当前标签后标签数 -1", win._tabbar.count() == 2, str(win._tabbar.count()))
check("D2 数据层同步收缩", len(win._docs) == 2, str(len(win._docs)))
check("D3 选中态仍在合法范围且三源一致",
      win._cur == win._tabbar.currentIndex() and 0 <= win._cur < 2,
      "cur=%s idx=%s" % (win._cur, win._tabbar.currentIndex()))
check("D4 关闭后剩余 path 不串位（a.md + c.md）",
      paths() == [FILES[0], FILES[2]], str(paths()))
check("D5 关闭的文档进入回溯栈（可 Ctrl+Alt+T 恢复）",
      len(win._closed_stack) == 1 and win._closed_stack[-1].get("path") == FILES[1],
      str(win._closed_stack))

# ---------- E 关闭非当前标签：当前文档不受影响 ----------
reset_docs(FILES)
win._close_tab(0)
wait(450)
check("E1 关闭左侧非当前标签后仍指向 c.md",
      win._cur == 1 and win._docs[win._cur]["path"] == FILES[2],
      "cur=%s paths=%s" % (win._cur, paths()))
check("E2 当前文档内容未被重载（缓存仍在）",
      "文档c" in (win._docs[win._cur].get("content") or ""),
      str(win._docs[win._cur].get("content"))[:40])

# ---------- F 批量关闭：其它所有 / 左 / 右 ----------
reset_docs(FILES)
win._tabbar.setCurrentIndex(1)
wait(450)
n = win._batch_close([0, 2], ask=False)
wait(450)
check("F1 「关闭其它所有」返回关闭数 2", n == 2, str(n))
check("F2 只剩目标标签且 path 为 b.md",
      win._tabbar.count() == 1 and paths() == [FILES[1]], str(paths()))
check("F3 当前索引归位到 0", win._cur == 0 and win._tabbar.currentIndex() == 0,
      "cur=%s idx=%s" % (win._cur, win._tabbar.currentIndex()))
check("F4 保留文档内容正确（未串成被关掉的兄弟文档）",
      "文档b" in (win._docs[0].get("content") or ""),
      str(win._docs[0].get("content"))[:40])

reset_docs(FILES)
win._tabbar.setCurrentIndex(2)
wait(450)
n = win._batch_close([0, 1], ask=False)
wait(450)
check("F5 「关闭左侧所有」：剩 1 个且为 c.md",
      n == 2 and paths() == [FILES[2]] and win._cur == 0, "n=%s paths=%s cur=%s" % (n, paths(), win._cur))

reset_docs(FILES)
win._tabbar.setCurrentIndex(0)
wait(450)
n = win._batch_close([1, 2], ask=False)
wait(450)
check("F6 「关闭右侧所有」：剩 1 个且为 a.md，当前索引不变",
      n == 2 and paths() == [FILES[0]] and win._cur == 0, "n=%s paths=%s cur=%s" % (n, paths(), win._cur))

# ---------- G 全部关闭 → 自动补空白页 ----------
reset_docs(FILES)
n = win._batch_close([0, 1, 2], ask=False)
wait(450)
check("G1 全部关闭后自动补一个空白页", win._tabbar.count() == 1 and len(win._docs) == 1,
      str(win._tabbar.count()))
check("G2 空白页为未命名且 file_path 清空",
      win._docs[0].get("path") is None and win.file_path is None,
      "path=%s fp=%s" % (win._docs[0].get("path"), win.file_path))
check("G3 空白页为当前页", win._cur == 0, str(win._cur))
check("G4 三个文档全部进回溯栈", len(win._closed_stack) == 3, str(len(win._closed_stack)))

# ---------- H 关闭所有未修改（per-doc dirty）----------
reset_docs(FILES)
win._tabbar.setCurrentIndex(0)
wait(450)
win._docs[0]["dirty"] = True      # 当前文档（实时标记）
win._docs[1]["dirty"] = False     # 未修改 → 应被关闭
win._docs[2]["dirty"] = True
win._dirty = True
win._close_unmodified()
wait(450)
check("H1 只关闭未修改的那一个", win._tabbar.count() == 2, str(win._tabbar.count()))
check("H2 剩余为 a.md 与 c.md（b.md 被关）", paths() == [FILES[0], FILES[2]], str(paths()))
check("H3 关闭后当前文档仍是 a.md 且脏标记保留",
      win._cur == 0 and win._docs[0].get("dirty") is True and win._dirty is True,
      "cur=%s dirty=%s" % (win._cur, win._docs[0].get("dirty")))
check("H4 标签 • 标记随 per-doc dirty 显示（两个保留文档都是脏的）",
      "•" in win._tabbar.tabText(0) and "•" in win._tabbar.tabText(1),
      str(tabs()))

# ---------- I per-doc dirty 切走切回不丢 ----------
reset_docs(FILES)
win._tabbar.setCurrentIndex(0)
wait(450)
win._dirty = True
win._docs[0]["dirty"] = True
win._tabbar.setCurrentIndex(2)
wait(500)
check("I1 切走后原标签 • 仍在（旧实现会丢）", "•" in win._tabbar.tabText(0), str(tabs()))
win._tabbar.setCurrentIndex(0)
wait(500)
check("I2 切回后当前文档脏标记恢复", win._dirty is True, "dirty=%s" % win._dirty)

# ---------- J 复制三项 ----------
reset_docs(FILES)
_dj, _mj = menu_of(0)
_dj["复制文件名"].fire()
check("J1 复制文件名落剪贴板", QApplication.clipboard().text() == "a.md",
      QApplication.clipboard().text())
_dj2 = menu_of(1)[0]
_dj2["复制文件路径"].fire()
check("J2 复制文件路径为完整路径", QApplication.clipboard().text() == FILES[1],
      QApplication.clipboard().text())
_dj3 = menu_of(2)[0]
_dj3["复制所在目录"].fire()
check("J3 复制所在目录为纯目录", QApplication.clipboard().text() == os.path.dirname(FILES[2]),
      QApplication.clipboard().text())

# ---------- K 重新打开关闭的标签（TAB-3）----------
reset_docs(FILES)
win._close_tab(1)
wait(450)
check("K1 关闭后 2 个标签", win._tabbar.count() == 2, str(win._tabbar.count()))
win._reopen_closed_tab()
wait(500)
check("K2 重开后 3 个标签且新标签为 b.md",
      win._tabbar.count() == 3 and win._docs[-1].get("path") == FILES[1],
      str(paths()))
check("K3 重开的文档内容完整", "文档b" in (win._docs[-1].get("content") or ""),
      str(win._docs[-1].get("content"))[:40])
check("K4 栈已消费（长度归零）", len(win._closed_stack) == 0, str(len(win._closed_stack)))
win._reopen_closed_tab()
wait(200)
check("K5 栈空时再点不崩、标签数不变", win._tabbar.count() == 3, str(win._tabbar.count()))

# ---------- L 上一个 / 下一个标签（TAB-4）----------
reset_docs(FILES)
check("L1 起始在末位", win._cur == 2, str(win._cur))
win._cycle_tab(1)
wait(500)
check("L2 下一个标签回绕到首位", win._cur == 0, str(win._cur))
win._cycle_tab(-1)
wait(500)
check("L3 上一个标签回绕到末位", win._cur == 2, str(win._cur))

# ---------- M 全部保存（TAB-6）----------
# 说明：非当前标签取「切换时回写的缓存」，当前标签取**实时内容**。
# 这里把当前页切到 b.md，让 a/C 两个改动走缓存路径（Python 侧改 doc 即可）；
# 之后再单独验证「当前标签以实时内容为准」。
reset_docs(FILES)
win._tabbar.setCurrentIndex(1)
wait(500)
win._docs[0]["dirty"] = True
win._docs[0]["content"] = "# 改过的A\n\n新正文A\n"
win._docs[2]["dirty"] = True
win._docs[2]["content"] = "# 改过的C\n\n新正文C\n"
win._docs[1]["dirty"] = False
r = win.save_all()
wait(300)
with open(FILES[0], "r", encoding="utf-8") as f:
    _a = f.read()
with open(FILES[2], "r", encoding="utf-8") as f:
    _c = f.read()
with open(FILES[1], "r", encoding="utf-8") as f:
    _b = f.read()
check("M1 save_all 返回 True", r is True, str(r))
check("M2 a.md 已落盘新内容", "改过的A" in _a, _a[:30])
check("M3 c.md 已落盘新内容", "改过的C" in _c, _c[:30])
check("M4 未修改的 b.md 未被改写", "文档b" in _b, _b[:30])
check("M5 保存后脏标记清零",
      win._docs[0]["dirty"] is False and win._docs[2]["dirty"] is False, "")
check("M6 无改动时 save_all 返回 False 并提示",
      win.save_all() is False, "")
win._docs[1]["dirty"] = True
win._dirty = True
win.save_all()
wait(300)
with open(FILES[1], "r", encoding="utf-8") as f:
    _b2 = f.read()
check("M7 当前标签按实时内容落盘（未被 Python 侧缓存冒充）",
      "文档b" in _b2 and win._docs[1]["dirty"] is False, _b2[:30])

# ---------- N 快捷键注册（不与既有键冲突）----------
def seq_of(name):
    a = win._shortcut_acts.get(name)
    return a.shortcut().toString() if a is not None else "<missing>"


check("N1 重新打开关闭的标签 = Ctrl+Alt+T（避开「插入表格」的 Ctrl+Shift+T）",
      seq_of("重新打开关闭的标签") == "Ctrl+Alt+T", seq_of("重新打开关闭的标签"))
check("N2 全部保存 = Ctrl+Alt+S", seq_of("全部保存") == "Ctrl+Alt+S", seq_of("全部保存"))
check("N3 下一个标签页 = Ctrl+PgDown", "PgDown" in seq_of("下一个标签页"), seq_of("下一个标签页"))
check("N4 上一个标签页 = Ctrl+PgUp", "PgUp" in seq_of("上一个标签页"), seq_of("上一个标签页"))
check("N5 插入表格仍为 Ctrl+Shift+T（未被抢键）",
      seq_of("插入表格") == "Ctrl+Shift+T", seq_of("插入表格"))
check("N6 工具栏开关已改 Ctrl+Shift+B（让开 Ctrl+Shift+T）",
      seq_of("显示 / 隐藏工具栏") == "Ctrl+Shift+B", seq_of("显示 / 隐藏工具栏"))
_alldef = [n for _g, items in win._shortcut_defs for n, _s in items]
_seqs = [seq_of(n) for n in _alldef if seq_of(n)]
check("N7 全表快捷键无重复", len(_seqs) == len(set(_seqs)),
      str([s for s in _seqs if _seqs.count(s) > 1]))

# ---------- O 中键点击标签即关闭（TAB-5）----------
reset_docs(FILES)
_center = win._tabbar.tabRect(1).center()
_ev = QMouseEvent(QEvent.MouseButtonPress, _center, win._tabbar.mapToGlobal(_center),
                  Qt.MiddleButton, Qt.MiddleButton, Qt.NoModifier)
_handled = win.eventFilter(win._tabbar, _ev)
wait(450)
check("O1 中键事件被接管（返回 True）", _handled is True, str(_handled))
check("O2 中键关闭了 b.md", paths() == [FILES[0], FILES[2]], str(paths()))

# ---------- 收尾：复位会话设置，避免污染其它探针 ----------
if _sa_backup is None:
    win._settings.remove("startupAction")
else:
    win._settings.setValue("startupAction", _sa_backup)
if _lf_backup is None:
    win._settings.remove("lastFile")
else:
    win._settings.setValue("lastFile", _lf_backup)
win._settings.sync()

shutil.rmtree(tmp, ignore_errors=True)

with open(OUT, "w", encoding="utf-8") as f:
    for s_, name, detail in _log:
        f.write("%s %s%s\n" % (s_, name, (" | " + detail) if detail and s_ == "FAIL" else ""))
print("done")
