# -*- coding: utf-8 -*-
"""m129：v3.38 TAB-7 / TAB-8 / TAB-9 / TAB-10
A组 TAB-7 固定标签：pin 切换 / 📌 前缀 / 排左（含拖动后强制）/ 关闭守卫 / 批量关闭跳过
B组 TAB-10 在终端中打开：菜单项 + subprocess 调用参数（cwd=文件所在目录）
C组 TAB-9 标签溢出下拉：按钮存在 / 窄窗启用 / 下拉列出全部标签 / 点击切换
D组 TAB-8 Ctrl+Tab MRU 快切面板：MRU 顺序 / 面板条目 / 提交切换 / 关闭惰性剔除
"""
import os, sys, tempfile

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, "E:/WorkBuddy/md-editor/src")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, Qt

app = QApplication(sys.argv)
import mainwindow as MW
from mainwindow import MainWindow


# ---------------- 菜单替身（同 m126）----------------
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

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m129.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  | " + str(detail)))


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def reset_docs(paths):
    win._switching = False
    win._pending_switch = -1
    win._docs = []
    while win._tabbar.count():
        win._tabbar.removeTab(0)
    win._cur = -1
    win._closed_stack = []
    win._dirty = False
    win._mru = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            win._add_doc(path=p, text=f.read())
    wait(400)


def paths():
    return [d.get("path") for d in win._docs]


def tabs():
    return [win._tabbar.tabText(i) for i in range(win._tabbar.count())]


def menu_of(idx):
    FakeMenu.last = None
    r = win._tabbar.tabRect(idx)
    win._on_tab_menu(r.center())
    m = FakeMenu.last
    return {a.text(): a for a in m.acts}, m


tmp = tempfile.mkdtemp(prefix="m129_")
FILES = []
for _n, _body in (("a.md", "# 文档a\n\n正文A\n"), ("b.md", "# 文档b\n\n正文B\n"),
                  ("c.md", "# 文档c\n\n正文C\n"), ("d.md", "# 文档d\n\n正文D\n")):
    _p = os.path.join(tmp, _n)
    with open(_p, "w", encoding="utf-8") as _f:
        _f.write(_body)
    FILES.append(_p)

win = MainWindow()
_sa_backup = win._settings.value("startupAction")
_lf_backup = win._settings.value("lastFile")
_sz0 = win.size()

win.show()
wait(2600)

# ---------- A TAB-7 固定标签 ----------
reset_docs(FILES)
check("A0 基线：4 标签，顺序 a/b/c/d", paths() == FILES, str(paths()))
win._toggle_pin(0)
wait(200)
check("A1 pin 后 doc0.pinned=True", win._docs[0].get("pinned") is True, "")
check("A2 标签文本带 📌 前缀", "📌" in win._tabbar.tabText(0), win._tabbar.tabText(0))
check("A3 未固定顺序不变", paths() == FILES, str(paths()))
win._toggle_pin(3)     # 固定最后一个 → 与已固定的 a.md 一起排前（稳定：a,d,b,c）
wait(200)
check("A4 固定末位标签后排入固定组（a,d,b,c）",
      paths() == [FILES[0], FILES[3], FILES[1], FILES[2]], str(paths()))
check("A5 固定后当前文档仍是 d.md",
      win._docs[win._cur].get("path") == FILES[3], "cur=%s" % win._cur)
check("A6 两个 📌 前缀都在前两签",
      all("📌" in win._tabbar.tabText(i) for i in (0, 1)), str(tabs()))
# 关闭守卫（此刻 a 与 d 都已固定）
n0 = win._tabbar.count()
win._close_tab(0)      # a.md 已固定
wait(300)
check("A7 固定标签 Ctrl+W / 关闭按钮路径被守卫（数量不变）",
      win._tabbar.count() == n0 and FILES[0] in paths(), str(paths()))
mids, _ = menu_of(0)
check("A8 固定标签右键「关闭」置灰", mids["关闭\tCtrl+W"].isEnabled() is False, "")
check("A9 右键「固定 / 取消固定标签」勾选态为真",
      mids["固定 / 取消固定标签"].isChecked() is True, "")
# 批量关闭跳过固定
win._toggle_pin(0)     # 取消固定 d → 全部未固定
wait(200)
win._toggle_pin(0)     # 重新固定 a.md（当前在第 0 位）
wait(200)
reset_docs(FILES)
win._toggle_pin(0)     # 固定 a.md
wait(200)
mids, _ = menu_of(2)   # 在 c.md 上右键「关闭其它所有」→ 只关 b/d（a 固定跳过）
wait(400)
mids["关闭其它所有"].fire()
wait(600)
check("A10 关闭其它所有跳过固定项（剩 a.md + c.md）",
      sorted(paths()) == sorted([FILES[0], FILES[2]]), str(paths()))
# 关闭所有未修改跳过固定
reset_docs(FILES)
win._toggle_pin(0)     # a.md 固定
wait(200)
win._close_unmodified()
wait(600)
check("A11 关闭所有未修改跳过固定项（a.md 保留）",
      paths() == [FILES[0]], str(paths()))
# 拖动后强制排左
reset_docs(FILES)
win._toggle_pin(2)     # 固定 c.md → 顺序 [c,a,b,d]
wait(200)
win._on_tab_moved(0, 3)   # 模拟把固定标签拖到末位
wait(200)
check("A12 拖动固定标签后被强制排回最前",
      paths()[0] == FILES[2] and win._docs[0].get("pinned") is True, str(paths()))
check("A13 排左后无越界：_cur 合法且与 currentIndex 一致",
      0 <= win._cur < len(win._docs) and win._cur == win._tabbar.currentIndex(),
      "cur=%s" % win._cur)

# ---------- B TAB-10 在终端中打开 ----------
reset_docs(FILES)
_popen_args = []
_orig_popen = MW.subprocess.Popen
MW.subprocess.Popen = lambda cmd, shell=False, cwd=None: _popen_args.append((cmd, cwd)) or type("P", (), {"pid": 0})()
try:
    mids, _ = menu_of(1)
    check("B1 菜单含「在终端中打开」且有路径时可点",
          "在终端中打开" in mids and mids["在终端中打开"].isEnabled() is True, "")
    mids["在终端中打开"].fire()
    wait(300)
    check("B2 调用 start powershell 且 cwd=文件所在目录",
          len(_popen_args) == 1 and _popen_args[0][0] == "start powershell"
          and os.path.dirname(FILES[1]) == _popen_args[0][1], str(_popen_args))
    # 未命名 → 置灰
    _uidx = win._add_doc(path=None, text="")
    wait(300)
    mids, _ = menu_of(_uidx)
    check("B3 未命名标签「在终端中打开」置灰",
          mids["在终端中打开"].isEnabled() is False, "")
finally:
    MW.subprocess.Popen = _orig_popen

# ---------- C TAB-9 标签溢出下拉 ----------
reset_docs(FILES[:3])
check("C1 溢出按钮存在（objectName tbMore）", hasattr(win, "_btn_tb_more"), "")
check("C2 宽窗 + 3 标签 → 按钮禁用（未溢出）",
      win._btn_tb_more.isEnabled() is False, str(win.size()))
# 收窄窗口制造溢出
win.resize(360, 640)
wait(400)
win._update_tb_more()
_state = win._btn_tb_more.isEnabled()
win.resize(_sz0.width(), _sz0.height())
wait(300)
win._update_tb_more()
_state2 = win._btn_tb_more.isEnabled()
check("C3 窄窗启用 / 复宽禁用（溢出态随宽度翻转）",
      _state is True and _state2 is False, "narrow=%s wide=%s" % (_state, _state2))
# 下拉列出全部标签并切换
FakeMenu.last = None
win._show_tb_more_menu()
_m = FakeMenu.last
check("C4 下拉列出全部 3 个标签",
      _m is not None and len(_m.acts) == 3,
      str([a.text() for a in _m.acts]) if _m else "NO_MENU")
check("C5 当前标签带 ● 标记", "●" in _m.acts[0].text() or "●" in _m.acts[1].text()
      or "●" in _m.acts[2].text(), str([a.text() for a in _m.acts]))
_m.acts[2].fire()
wait(450)
check("C6 点击下拉项切换到第 3 个标签",
      win._cur == 2 and win._docs[win._cur]["path"] == FILES[2], "cur=%s" % win._cur)

# ---------- D TAB-8 Ctrl+Tab MRU 快切面板 ----------
reset_docs(FILES[:3])
# 构造 MRU：切到 b → 切到 c → 切到 a
for k in (1, 2, 0):
    win._tabbar.setCurrentIndex(k)
    wait(480)
check("D1 MRU 顺序与切换历史一致（a 最新，b 最旧）",
      [win._docs.index(d) if any(d is x for x in win._docs) else -1 for d in win._mru] == [0, 2, 1],
      str([win._docs.index(d) if any(d is x for x in win._docs) else -1 for d in win._mru]))
# 捕获面板输入（替身 _TabSwitcher，避免 exec 阻塞）
_captures = {}


class FakeSwitcher:
    def __init__(self, win_, entries, sel):
        _captures["entries"] = entries
        _captures["sel"] = sel

    def run(self):
        return _captures["entries"][_captures["sel"]][0]


MW.MainWindow._TabSwitcher = FakeSwitcher
win._open_tab_switcher()
wait(450)
check("D2 面板条目按 MRU 排序（a/b/c）",
      [t for _, t in _captures["entries"]] == ["a.md", "c.md", "b.md"],
      str(_captures["entries"]))
check("D3 默认选中第 2 项（最近使用的上一个）", _captures["sel"] == 1, str(_captures["sel"]))
check("D4 确认后切换到 c.md",
      win._docs[win._cur]["path"] == FILES[2], "cur=%s paths=%s" % (win._cur, paths()))
# 关闭惰性剔除
reset_docs(FILES[:3])
for k in (1, 2):
    win._tabbar.setCurrentIndex(k)
    wait(480)
win._close_tab(2)     # 关闭 c.md（当前）
wait(450)
win._open_tab_switcher()
wait(300)
check("D5 已关闭标签从面板剔除（条目仅 a/b）",
      [t for _, t in _captures["entries"]] == ["b.md", "a.md"],
      str(_captures["entries"]))
# 单标签 → 提示不开面板
_captures.clear()
reset_docs(FILES[:1])
win._open_tab_switcher()
wait(300)
check("D6 只有一个标签时不弹面板", len(_captures.get("entries", [])) == 0,
      str(_captures.get("entries")))

# ---------- 收尾：复位 QSettings，防污染其它探针 ----------
win._settings.setValue("startupAction", _sa_backup)
win._settings.setValue("lastFile", _lf_backup)
win._settings.sync()

npass = sum(1 for s, _, _ in _log if s == "PASS")
nfail = sum(1 for s, _, _ in _log if s == "FAIL")
print("PASS=%d FAIL=%d" % (npass, nfail))
with open(OUT, "w", encoding="utf-8") as f:
    for s, name, detail in _log:
        f.write(f"{s} {name}" + (f"  | {detail}" if s == "FAIL" else "") + "\n")
    f.write("PASS=%d FAIL=%d\n" % (npass, nfail))
