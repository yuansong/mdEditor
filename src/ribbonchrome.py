# -*- coding: utf-8 -*-
"""RIBBON-12（v3.44.26）：PS01-RIBBON 按钮体系优化（Office 功能区界面统一）。

按 docs/ui-redesign/04_主界面效果图-PS01-RIBBON.html（#t-light 基准令牌）还原
Office 功能区「蓝色命令按钮」（严格对齐设计稿 .gbig / .gsm）：
  · 主命令按钮（_CmdButton / #gcmd）：竖排卡片（固定高 50px、最小宽 52px），
    图标在上（19px 蓝底方块）+ 文字在下（11px/600），图标与文字整体垂直居中；
  · 全部命令图标统一为单色几何/符号字形（accent 蓝、17px，对齐 #gcmdIco）：
    彻底移除彩色 emoji，保证图标大小与颜色一致，整体观感协调。
  · 「剪贴板」组（RIBBON-12）随「文档 / 编辑历史」等同改为 50px 大钮（图标上、文字下竖排），
    全功能区统一大钮竖排风格；小命令按钮（#gsel）仅保留为通用工厂，不再用于功能区主组。
  · 外观页三组（界面风格 / 主题 / 代码风格）统一为「图标 + 精简名称」的 50px 大钮，
    并全部固定宽度（LOOK_BTN_W），避免文字长短造成控件宽窄不一。
   · 全功能区所有组均为「单行横排」：组内按钮不换行、不竖排堆叠，严禁 3 行及以上。
   · 悬停 = 浅蓝底 + 蓝边；选中/勾选 = 更实浅蓝底 + 深蓝粗字（#gcmd）/ 同左（#gsel），文字始终深色可读、去除图标纯色块。

窗口形态与装配逻辑（标题栏/页签行/折叠/与 mac 形态互斥）沿用 RIBBON-1，本批次仅重构
按钮视觉与组内布局。本模块只建 UI；安装/卸载由 mainwindow._apply_ribbon_chrome 驱动。

v3.44.27（RIBBON-13）：① 命令钮与功能区内容高度锁定 Fixed（min==max==设计值），
彻底消除重启后真实环境偶发「按钮异常拉高」；② 页签行右端新增图钉式「固定 / 收拢」双态
切换钮（颜色 + 文案 + 提示明确反映状态）——固定=始终展开，收拢=仅留页签行、点页签临时
展开、点文档自动收起（焦点离开功能区进入编辑区即自动收拢）。
"""
from i18n import T  # v3.49.1（FIX-T）：国际化取词 T() 此前缺失导入

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QFont
from PySide6.QtWidgets import (
    QFrame, QLabel, QMenu, QSizePolicy, QStackedWidget, QToolButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
)

# ---- 设计令牌（#t-light 基准；深色主题经 apply_palette 以 chrome_bar 等覆盖） ----
TC = dict(
    accent="#2b579a", accent2="#103f91", ribbon="#ffffff", ribbonbg="#eef0f3",
    line="#d9dce1", line2="#c9cdd4", tx="#1f2328", tx2="#5f6672", tx3="#8a919c",
    hlbg="#e8f0fe", win="#ffffff", closehover="#e81123", statussep="rgba(255,255,255,.25)",
    # 命令按钮专用：选中态改为浅蓝高对比（深蓝文字可读），去除图标纯色块
    cmd_bg="#ffffff", cmd_border="#dde1e7", cmd_hover_bg="#eaf1fc",
    cmd_hover_border="#2b579a",
    cmd_sel_bg="#cfe2fb", cmd_sel_border="#2b579a", cmd_sel_tx="#103f91",
    sel_border="#e1e5ec", sel_hover_bg="#eaf1fc",
)

TITLE_H = 32
TABS_H = 34
BODY_MINH = 86           # 设计稿 .ribbon min-height:86px（大钮50 + 组标题~16 + 上下内距10）

CMD_W_MIN = 52          # 大命令按钮最小宽度（对齐 .gbig width:52px，长标签按内容增长）
CMD_H = 50              # 大命令按钮统一高度（竖排图标+文字，对齐 .gbig height:50px）
GSM_H = 24              # 小命令按钮高度（对齐 .gsm height:24px）
SEL_W = 72              # 小命令按钮最小宽度（横排图文按内容增长；图标钮 30px）
LOOK_BTN_W = 62        # 外观页大钮统一固定宽度（图标 + 精简名，避免文字长短导致宽窄不一）


# ---------------------------------------------------------------- 小控件工厂
def _tbtn(text, tip, font_px, color, parent=None):
    """通用无边框文字钮（QAT / 窗口钮共用骨架）。"""
    b = QToolButton(parent)
    b.setText(text)
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setAutoRaise(True)
    b.setFont(QFont("Segoe UI Emoji", font_px) if any(ord(c) > 0x2FFF for c in text)
              else QFont("Segoe UI", font_px))
    b.setStyleSheet(
        "QToolButton{background:transparent;border:none;border-radius:3px;"
        "padding:0;color:%s;}" % color)
    return b


# ---------------------------------------------------------------- 主命令按钮
class _CmdButton(QFrame):
    """大命令按钮（#gcmd，对齐设计稿 .gbig：图标在上、文字在下，固定高 50px）。"""

    clicked = Signal()

    def __init__(self, icon, label, sub, parent=None):
        super().__init__(parent)
        self._p = dict(T)
        self.setObjectName("gcmd")
        self._checked = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(CMD_W_MIN)
        self.setFixedHeight(CMD_H)
        # v3.44.27(REQ3)：垂直尺寸策略锁定 Fixed，杜绝 HiDPI / 时序差异下被布局拉伸导致异常拉高
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        v = QVBoxLayout(self)
        v.setContentsMargins(3, 5, 3, 5)
        v.setSpacing(3)
        v.setAlignment(Qt.AlignCenter)

        if icon:
            self._ico = QLabel(icon, self)
            self._ico.setObjectName("gcmdIco")
            self._ico.setFixedSize(19, 19)
            self._ico.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self._ico.setAlignment(Qt.AlignCenter)
            self._ico.setStyleSheet(
                "background:transparent;font-size:17px;color:%s;"
                "font-family:'Segoe UI Symbol','Segoe UI','Microsoft YaHei';"
                % self._p["accent"])
            v.addWidget(self._ico)

        lab = QLabel(label, self)
        lab.setObjectName("gcmdLab")
        lab.setAlignment(Qt.AlignCenter)
        lab.setWordWrap(True)
        v.addWidget(lab)
        self._lab = lab

        self._paint(False)

    # ---- 视觉状态 ----
    def _paint(self, hover):
        # 三态统一为「浅色家族」：默认白底 / 悬停浅蓝 / 选中更实浅蓝+深蓝粗字，文字始终可读。
        # 注意：标签自身 setStyleSheet 优先级高于父级选择器——颜色/字重必须直接写到标签上，
        #       否则父级 QLabel#gcmdLab{color:...} 会被标签原有 color 覆盖（选中态曾因此仍是黑字）。
        # OFFICE-THEME：全部取色改走 self._p（随主题调色板），切换主题后重绘即生效。
        if self._checked:
            bg, bd = self._p["cmd_sel_bg"], self._p["cmd_sel_border"]
            lab_c, lab_w = self._p["cmd_sel_tx"], 700
        elif hover:
            bg, bd = self._p["cmd_hover_bg"], self._p["cmd_hover_border"]
            lab_c, lab_w = self._p["accent"], 600
        else:
            bg, bd = self._p["cmd_bg"], self._p["cmd_border"]
            lab_c, lab_w = self._p["tx"], 600
        self.setStyleSheet(
            "QFrame#gcmd{background:%s;border:1px solid %s;border-radius:4px;}" % (bg, bd))
        if getattr(self, "_ico", None) is not None:
            self._ico.setStyleSheet(
                "background:transparent;font-size:17px;color:%s;"
                "font-family:'Segoe UI Symbol','Segoe UI','Microsoft YaHei';"
                % self._p["accent"])
        if getattr(self, "_lab", None) is not None:
            self._lab.setStyleSheet(
                "font-size:11px;font-weight:%d;color:%s;background:transparent;"
                % (lab_w, lab_c))

    def apply_palette(self, p):
        """v3.44.28（OFFICE-THEME）：大命令钮随主题重绘（apply_palette 由 RibbonBody 统一调用）。"""
        self._p.update(p or {})
        self._paint(False)

    def isChecked(self):
        return self._checked

    def set_checked(self, v):
        if self._checked != v:
            self._checked = v
            self._paint(False)

    # 兼容 sync_display / sync_look 的 setChecked 调用（QFrame 无原生 setChecked）
    setChecked = set_checked

    def click(self):
        self.clicked.emit()

    def enterEvent(self, e):
        self._paint(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._paint(False)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


# ---------------------------------------------------------------- 小命令按钮（对齐 .gsm）
def _gsel_qss(p, has_text):
    """小命令钮（#gsel）QSS：随主题调色板取色（v3.44.28 OFFICE-THEME 统一驱动）。"""
    return (
        "QToolButton#gsel{background:%s;border:1px solid %s;border-radius:4px;"
        "color:%s;font-size:12px;padding:0 7px;text-align:%s;}"
        "QToolButton#gsel:hover{background:%s;border:1px solid %s;}"
        "QToolButton#gsel:checked{background:%s;border:1px solid %s;"
        "color:%s;font-weight:700;}"
        % (p["cmd_bg"], p["sel_border"], p["tx"],
           ("center" if not has_text else "left"),
           p["sel_hover_bg"], p["cmd_hover_border"],
           p["cmd_sel_bg"], p["cmd_sel_border"], p["cmd_sel_tx"]))


def _mk_small_btn(text, tip, slot, icon, checkable, parent):
    """通用小命令钮（#gsel，高 24px、横排图文，对齐设计稿 .gsm）。"""
    b = QToolButton(parent)
    b.setObjectName("gsel")
    if icon and text:
        b.setText("%s %s" % (icon, text))
    elif icon:
        b.setText(icon)
    else:
        b.setText(text)
    b.setCheckable(checkable)
    b.setFixedHeight(GSM_H)
    b.setMinimumWidth(30 if not text else SEL_W)
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setFont(QFont("Microsoft YaHei", 12))
    b.setProperty("has_text", bool(text))
    b.setStyleSheet(_gsel_qss(T, bool(text)))
    b.clicked.connect(slot)
    return b


class _SmallCol(QWidget):
    """设计稿 .gcol：竖向堆叠的小命令钮（gap 2px）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 宽度按内容收敛（Maximum），避免小钮被横向拉伸到整条功能区
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0,0, 0)
        v.setSpacing(2)

    def add_small(self, text, tip, slot, checkable=False, icon=""):
        b = _mk_small_btn(text, tip, slot, icon, checkable, self)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.layout().addWidget(b)
        return b


# ---------------------------------------------------------------- 组内布局
class _Group(QFrame):
    """功能区组：组标题 + 横向单行（大命令钮 / 小命令钮列 / 小命令钮行）。"""

    def __init__(self, caption, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        cap = QLabel(caption, self)
        cap.setObjectName("ribCap")
        cap.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        cap.setStyleSheet(
            "font-size:11px;font-weight:600;color:#8a919c;"
            "padding:0 2px;letter-spacing:.3px;")
        v.addWidget(cap)
        self.row = QWidget(self)
        self._hl = QHBoxLayout(self.row)
        self._hl.setContentsMargins(0, 0, 0, 0)
        self._hl.setSpacing(5)
        v.addWidget(self.row, 1)

    # ---- 大命令按钮（竖排 / 50px，对齐 .gbig） ----
    def add_big(self, text, tip, slot, icon="", sub=""):
        b = _CmdButton(icon, text, sub, self.row)
        b.setToolTip(tip)
        b.clicked.connect(slot)
        self._hl.addWidget(b)
        return b

    # ---- 小命令按钮列（竖向 .gcol，对齐 .gsm 串） ----
    def add_small_col(self):
        col = _SmallCol(self.row)
        self._hl.addWidget(col)
        return col

    # ---- 小命令按钮（横排 / 24px，对齐 .gsm；用于剪贴板图标行等） ----
    def add_small_inline(self, text, tip, slot, icon="", checkable=False):
        b = _mk_small_btn(text, tip, slot, icon, checkable, self.row)
        self._hl.addWidget(b)
        return b


class _VSep(QFrame):
    """组间竖分隔线。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(1)
        self.setStyleSheet("background:%s;" % TC["line2"])


# ---------------------------------------------------------------- 标题栏
class RibbonTitleBar(QFrame):
    """① 32px Office 蓝标题栏：QAT + logo + 标题 + 窗口钮。"""

    def __init__(self, win):
        super().__init__(win)
        self._p = dict(T)  # OFFICE-THEME：构造期即持有调色板，hover/logo 风格统一随主题
        self.setObjectName("ribbonTitle")
        self.setFixedHeight(TITLE_H)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 0, 0, 0)
        h.setSpacing(1)

        # QAT 快速访问工具栏（恒驻：保存/撤销/重做 + ▾ 自定义入口）
        self.qat_save = _tbtn("✓", "保存 (Ctrl+S)", 12, "#fff", self)
        self.qat_undo = _tbtn("↶", "撤销 (Ctrl+Z)", 12, "#fff", self)
        self.qat_redo = _tbtn("↷", "重做 (Ctrl+Y)", 12, "#fff", self)
        for i, b in enumerate((self.qat_save, self.qat_undo, self.qat_redo)):
            b.setFixedSize(22, 22)
            h.addWidget(b)
            if i < 2:
                h.addSpacing(0)
        sep = QFrame(self)
        sep.setFixedSize(1, 14)
        sep.setStyleSheet("background:rgba(255,255,255,.35);")
        h.addWidget(sep)
        h.addSpacing(4)
        self.qat_more = _tbtn("▾", "快速访问工具栏（固定：保存 / 撤销 / 重做）", 9, "#fff", self)
        self.qat_more.setFixedSize(22, 22)
        h.addWidget(self.qat_more)
        h.addSpacing(8)

        # logo + 标题
        self.logo = QLabel("M", self)
        self.logo.setObjectName("ribLogo")
        self.logo.setFixedSize(16, 16)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet(
            "background:#fff;color:%s;border-radius:3px;"
            "font-size:10px;font-weight:700;" % self._p["accent"])
        h.addWidget(self.logo)
        h.addSpacing(7)
        self.title = QLabel("mdEditor", self)
        self.title.setObjectName("ribTitle")
        self.title.setStyleSheet(
            "color:#fff;font-size:12px;font-weight:600;background:transparent;")
        h.addWidget(self.title)
        h.addStretch(1)

        # 窗口钮 ─ □ ✕
        self.btn_min = _tbtn("─", "最小化", 11, "#fff", self)
        self.btn_max = _tbtn("□", "最大化 / 还原", 10, "#fff", self)
        self.btn_close = _tbtn("✕", "关闭", 11, "#fff", self)
        for name, b in (("min", self.btn_min), ("max", self.btn_max), ("close", self.btn_close)):
            b.setFixedSize(44, TITLE_H - 1)
            b.setObjectName("ribWinBtn_" + name)
        self.btn_min.clicked.connect(win.showMinimized)
        self.btn_max.clicked.connect(lambda: win._mac_toggle_max())
        self.btn_close.clicked.connect(win.close)
        h.addWidget(self.btn_min)
        h.addWidget(self.btn_max)
        h.addWidget(self.btn_close)
        self._apply_hover_qss()

    def _apply_hover_qss(self):
        self.setStyleSheet(
            "QFrame#ribbonTitle{background:%s;}" % self._p["accent"]
            + "".join(
                "QToolButton#ribWinBtn_%s{background:transparent;border:none;color:#fff;}"
                "QToolButton#ribWinBtn_%s:hover{background:rgba(255,255,255,.15);}"
                % (n, n) for n in ("min", "max"))
            + "QToolButton#ribWinBtn_close{background:transparent;border:none;color:#fff;}"
              "QToolButton#ribWinBtn_close:hover{background:%s;color:#fff;}" % self._p["closehover"]
            + "QToolButton{font-family:'Segoe UI','Microsoft YaHei';}"
              "QToolButton#ribWinBtn_min,QToolButton#ribWinBtn_max{font-size:11px;}"
              "QToolButton#ribWinBtn_close{font-size:11px;}")

    def set_doc_title(self, text):
        self.title.setText("mdEditor — " + text if text else "mdEditor")

    def apply_palette(self, p):
        """深浅主题适配：chrome_bar 为主底色，logo / 窗口钮 / 关闭悬停随主题重绘。

        v3.44.28（OFFICE-THEME）：此前仅替换标题栏底色，页签行与功能区内容区读取
        写死的模块级 T 字典，导致 Office 风格切换主题后颜色割裂；现统一由 merge_palette
        合并后的主题调色板驱动，整条 Office 控件随主题协调。"""
        self._p = dict(T)
        self._p.update(p or {})
        if getattr(self, "logo", None) is not None:
            self.logo.setStyleSheet(
                "background:#fff;color:%s;border-radius:3px;font-size:10px;"
                "font-weight:700;" % self._p["accent"])
        self._apply_hover_qss()


# ---------------------------------------------------------------- 页签行
class RibbonTabsRow(QFrame):
    """② 34px 功能区页签行：文件蓝钮 + 四页签 + 右端视图状态区/帮助/折叠。"""

    tab_selected = Signal(str)

    def __init__(self, win):
        super().__init__(win)
        self._p = dict(T)  # OFFICE-THEME：构造期即持有调色板，避免 apply_palette 前访问 self._p 崩溃
        self._pinned = True  # 默认固定（与 pinbtn 初始文案「固定」一致），供 apply_palette 首调 set_pin_state 使用
        self.setObjectName("ribbonTabs")
        self.setFixedHeight(TABS_H)
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 0, 6, 0)
        h.setSpacing(2)

        # 文件蓝钮：弹出既有「文件」QMenu（同源不复制）
        self.filebtn = QToolButton(self)
        self.filebtn.setObjectName("ribFileBtn")
        self.filebtn.setText(T("文件", "File"))
        self.filebtn.setFont(QFont("Microsoft YaHei", 9))
        self.filebtn.setCursor(Qt.PointingHandCursor)
        self.filebtn.setStyleSheet(
            "QToolButton#ribFileBtn{background:%s;color:#fff;font-weight:600;"
            "border:none;border-radius:3px;padding:4px 16px 5px;margin-bottom:3px;}"
            % self._p["accent"])
        self.filebtn.clicked.connect(self._pop_file_menu)
        h.addWidget(self.filebtn)
        h.addSpacing(4)

        # 四页签
        self.tabs = {}
        for i, (pid, label) in enumerate((("home", "开始"), ("view", "视图"),
                                          ("look", "外观"), ("tools", "工具"))):
            b = QToolButton(self)
            b.setObjectName("ribTab")
            b.setText(label)
            b.setCheckable(True)
            b.setFont(QFont("Microsoft YaHei", 9))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=pid: self.select_tab(k))
            b.setStyleSheet(
                "QToolButton#ribTab{background:transparent;border:1px solid transparent;"
                "border-bottom:none;border-radius:3px 3px 0 0;color:%s;padding:6px 14px 7px;}"
                "QToolButton#ribTab:hover{background:%s;}"
                "QToolButton#ribTab:checked{background:%s;border-color:%s;"
                "color:%s;font-weight:600;padding-bottom:8px;}"
                % (TC["tx"], TC["hlbg"], TC["ribbonbg"], TC["line2"], TC["accent"]))
            h.addWidget(b)
            self.tabs[pid] = b

        # 右端：视图状态区（反_parent 自菜单栏 corner）+ ? 帮助 + 图钉（固定/收拢）+ ▴ 折叠
        h.addStretch(1)
        self.right_zone = QWidget(self)
        rh = QHBoxLayout(self.right_zone)
        rh.setContentsMargins(0, 4, 0, 4)
        rh.setSpacing(4)
        rh.addWidget(win._vsz_corner)
        self.helpbtn = _tbtn("?", "帮助：手册 F12 / 关于（快捷键见使用手册第 10 章）", 12, self._p["accent"], self)
        self.helpbtn.setFixedSize(26, 26)
        self.helpbtn.clicked.connect(self._pop_help_menu)
        rh.addWidget(self.helpbtn)
        # v3.44.27(REQ1)：图钉式「固定 / 收拢」双态切换钮（状态明确可感知）
        self.pinbtn = _tbtn("固定", "功能区固定 / 收拢切换", 11, TC["accent"], self)
        self.pinbtn.setFixedSize(46, 26)
        # v3.44.31 FIX: do NOT connect here. pinbtn.clicked is connected once in
        # mainwindow.py at RibbonTabsRow instantiation; a 2nd connect double-fires
        # _toggle_ribbon_pin, flipping _ribbon_pinned twice (net no-op) => button dead.
        rh.addWidget(self.pinbtn)
        h.addWidget(self.right_zone)

    # ---- 弹出菜单 ----
    def _pop_file_menu(self):
        m = None
        for act in self.window().menuBar().actions():
            if str(act.text()).startswith("文件"):
                m = act.menu()
                break
        if m is not None:
            m.exec(self.filebtn.mapToGlobal(self.filebtn.rect().bottomLeft()))

    def _pop_help_menu(self):
        acts = self.window()._shortcut_acts
        m = QMenu(self)
        for name in ("使用手册", "关于"):
            a = acts.get(name)
            if a is not None:
                m.addAction(a)
        m.exec(self.helpbtn.mapToGlobal(self.helpbtn.rect().bottomLeft()))

    # ---- 页签 ----
    def select_tab(self, pid):
        for k, b in self.tabs.items():
            b.setChecked(k == pid)
        self.tab_selected.emit(pid)

    def current_tab(self):
        for k, b in self.tabs.items():
            if b.isChecked():
                return k
        return "home"

    def set_pin_state(self, pinned):
        """v3.44.27(REQ1)：把固定 / 收拢状态明确反映到图钉钮（颜色 + 文案 + 提示）。"""
        self._pinned = pinned
        if pinned:
            self.pinbtn.setText(T("固定", "Pin"))
            self.pinbtn.setToolTip(
                "功能区已固定（始终展开）。点击切换为「自动收拢」")
            self.pinbtn.setStyleSheet(
                "QToolButton{background:transparent;border:1px solid %s;"
                "border-radius:3px;color:%s;font-weight:700;}"
                "QToolButton:hover{background:%s;}"
                % (self._p["accent"], self._p["accent2"], self._p["hlbg"]))
        else:
            self.pinbtn.setText(T("收拢", "Collapse"))
            self.pinbtn.setToolTip(
                "功能区自动收拢（点页签临时展开，点文档自动收起）。"
                "点击切换为「固定」")
            self.pinbtn.setStyleSheet(
                "QToolButton{background:transparent;border:1px solid %s;"
                "border-radius:3px;color:%s;}"
                "QToolButton:hover{background:%s;}"
                % (self._p["line2"], self._p["tx2"], self._p["hlbg"]))

    def apply_palette(self, p):
        """v3.44.28（OFFICE-THEME）：页签行随主题重绘（页签 / 帮助 / 图钉 + 行底）。"""
        self._p = dict(T)
        self._p.update(p or {})
        self.setStyleSheet("background:%s;" % self._p["ribbonbg"])
        for b in self.tabs.values():
            b.setStyleSheet(
                "QToolButton#ribTab{background:transparent;border:1px solid transparent;"
                "border-bottom:none;border-radius:3px 3px 0 0;color:%s;padding:6px 14px 7px;}"
                "QToolButton#ribTab:hover{background:%s;}"
                "QToolButton#ribTab:checked{background:%s;border-color:%s;"
                "color:%s;font-weight:600;padding-bottom:8px;}"
                % (self._p["tx"], self._p["hlbg"], self._p["ribbonbg"],
                   self._p["line2"], self._p["accent"]))
        self.helpbtn.setStyleSheet(
            "QToolButton{background:transparent;border:none;border-radius:3px;"
            "padding:0;color:%s;}" % self._p["accent"])
        # v3.44.30（THEME-SYNC）：文件蓝钮背景随主题 accent 重绘（此前写死 TC["accent2"] 蓝，切主题不变）
        self.filebtn.setStyleSheet(
            "QToolButton#ribFileBtn{background:%s;color:#fff;font-weight:600;"
            "border:none;border-radius:3px;padding:4px 16px 5px;margin-bottom:3px;}"
            % self._p["accent"])
        self.set_pin_state(self._pinned)


# ---------------------------------------------------------------- 功能区内容
class RibbonBody(QStackedWidget):
    """③ 四页功能区（组间竖线 + 组标题）。动作复用 MainWindow._shortcut_acts。"""

    def __init__(self, win):
        super().__init__(win)
        self._p = dict(T)
        self.setObjectName("ribbonBody")
        # v3.44.27(REQ3)：min == max == 设计稿高度，硬性锁死功能区内容高度，
        # 彻底消除重启后在真实 HiDPI / 字体时序下偶发被拉伸「特别高」的异常。
        self.setMinimumHeight(BODY_MINH)
        self.setMaximumHeight(BODY_MINH)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._win = win
        self._mode_btns = {}
        self._disp_btns = {}
        self._style_btns = {}
        self._theme_btns = {}
        self._code_btns = {}
        self._build_home()
        self._build_view()
        self._build_look()
        self._build_tools()

    # ---- 动作快捷方式 ----
    def _act(self, name):
        a = self._win._shortcut_acts.get(name)
        return (lambda _=False: a.trigger()) if a is not None else (lambda *_: None)

    def _page(self):
        w = QWidget(self)
        h = QHBoxLayout(w)
        h.setContentsMargins(10, 6, 10, 4)
        h.setSpacing(0)
        h.setAlignment(Qt.AlignLeft)
        return w, h

    def _group(self, h, caption):
        if h.count():
            h.addWidget(_VSep(self))
        g = _Group(caption, self)
        h.addWidget(g)
        return g

    # ---- 开始 ----
    def _build_home(self):
        w, h = self._page()
        g = self._group(h, "文档")
        g.add_big("新建", "新建文档 (Ctrl+N)", self._act("新建"), "✚", "Ctrl+N")
        g.add_big("打开", "打开文件 (Ctrl+O)", self._act("打开…"), "▣", "Ctrl+O")
        g.add_big("保存", "保存当前文档 (Ctrl+S)", self._act("保存"), "✓", "Ctrl+S")
        g = self._group(h, "编辑历史")
        g.add_big("撤销", "撤销 (Ctrl+Z)", self._act("撤销"), "↶", "Ctrl+Z")
        g.add_big("重做", "重做 (Ctrl+Y)", self._act("重做"), "↷", "Ctrl+Y")
        g = self._group(h, "查找导航")
        g.add_big("查找替换", "查找 / 替换 (Ctrl+F / Ctrl+H)",
                  self._act("查找…"), "◎", "Ctrl+F")
        g.add_big("全局搜索", "在文件夹中搜索 (Ctrl+Shift+F)",
                  self._act("在文件夹中搜索…"), "◍")
        g.add_big("转到行", "转到指定行 (Ctrl+G)", self._act("转到行…"), "→")
        g = self._group(h, "块与命令")
        g.add_big("块菜单", "块级操作菜单 (Ctrl+/)", self._act("块菜单"), "☰", "Ctrl+/")
        g.add_big("命令面板", "命令面板 (Ctrl+Shift+P)", self._act("命令面板…"), "⌘", "Ctrl+Shift+P")
        g = self._group(h, "剪贴板")
        from PySide6.QtWebEngineCore import QWebEnginePage
        # RIBBON-12：剪贴板组改为 50px 大钮（图标上、文字下竖排），与「文档」等组风格统一；
        # 图标统一为单色字形（accent 蓝），✂/⧉/▤/☑ 均为单色几何字形，彻底去彩色 emoji。
        for glyph, label, tip, pa in (("✂", "剪切", "剪切 (Ctrl+X)", QWebEnginePage.Cut),
                                       ("⧉", "复制", "复制 (Ctrl+C)", QWebEnginePage.Copy),
                                       ("▤", "粘贴", "粘贴 (Ctrl+V)", QWebEnginePage.Paste),
                                       ("☑", "全选", "全选 (Ctrl+A)", QWebEnginePage.SelectAll)):
            g.add_big(label, tip, (lambda _=False, x=pa: self._win._page_action(x)),
                      icon=glyph)
        h.addStretch(1)
        self.addWidget(w)

    # ---- 视图 ----
    def _build_view(self):
        w, h = self._page()
        g = self._group(h, "模式（单击直切）")
        for mid, glyph, label in (("edit", "✎", "写作"), ("src", "<>", "源码"), ("dual", "▥", "分屏")):
            b = g.add_big(label, "%s模式（单击直切）" % label,
                          (lambda _=False, m=mid: self._win._set_mode(m)), glyph)
            self._mode_btns[mid] = b
        g = self._group(h, "沉浸")
        g.add_big("专注", "专注模式（隐藏干扰）", self._act("专注模式"), "◉")
        g.add_big("打字机", "打字机模式", self._act("打字机模式"), "≡")
        g.add_big("全屏", "全屏 (F11)", self._act("全屏"), "⛶")
        g = self._group(h, "显示与缩放")
        for text, name, ico in (("侧边栏", "显示 / 隐藏侧边栏", "▤"),
                                 ("工具栏", "显示 / 隐藏工具栏", "▦"),
                                 ("状态栏", "显示 / 隐藏状态栏", "▭")):
            b = g.add_big(text, name,
                          (lambda _=False, n=name: self._toggle_disp(n)), icon=ico)
            self._disp_btns[name] = b
        for label, tip, name, ico in (("放大", "放大 (Ctrl+=)", "放大", "⊕"),
                                       ("缩小", "缩小 (Ctrl+-)", "缩小", "⊖"),
                                       ("重置缩放", "重置缩放", "重置缩放", "⟲")):
            g.add_big(label, tip, self._act(name), icon=ico)
        g = self._group(h, "标签导航")
        for label, tip, name, ico in (("上一标签", "上一标签页 (Ctrl+PgUp)", "上一标签页", "◀"),
                                       ("下一标签", "下一标签页 (Ctrl+PgDown)", "下一标签页", "▶"),
                                       ("标签快切", "标签快切面板 (Ctrl+Tab)", "标签快切面板", "▦")):
            g.add_big(label, tip, self._act(name), icon=ico)
        h.addStretch(1)
        self.addWidget(w)

    # ---- 外观 ----
    def _build_look(self):
        w, h = self._page()
        # RIBBON-11：外观页统一为「图标 + 精简名称」的 50px 大钮，并固定同宽，
        # 解决纯文字、长短不一导致控件宽窄参差的问题；完整名称保留在 tooltip。
        # 界面风格（单击即切，✓ 当前）——每次展开刷新勾选
        g = self._group(h, "界面风格（单击即切）")
        from uistyles import MENU_STYLES
        style_ico = {"ps01": "▤", "mac": "◐", "code": "<>",
                     "ribbon": "▦", "notion": "▭", "zen": "○"}
        style_short = {"ps01": "现代", "mac": "macOS", "code": "VS Code",
                       "ribbon": "Office", "notion": "Notion", "zen": "极简"}
        for sid, label in MENU_STYLES:
            b = g.add_big(style_short.get(sid, label),
                          "切换界面风格：%s" % label,
                          (lambda _=False, s=sid: self._win.set_uistyle(s)),
                          icon=style_ico.get(sid, "▤"))
            b.setFixedWidth(LOOK_BTN_W)
            self._style_btns[sid] = b
        # 主题
        g2 = self._group(h, "主题（即时生效）")
        import styles as _styles
        theme_ico = {"light": "☼", "azure": "☁", "sepia": "◑",
                     "dark": "●", "night": "☾", "panda": "◓"}
        theme_short = {"light": "浅色", "azure": "青空", "sepia": "护眼",
                       "dark": "深色", "night": "墨夜", "panda": "熊猫"}
        for t in _styles.THEMES:
            b = g2.add_big(theme_short.get(t["id"], t["label"]),
                           "切换主题：%s" % t["label"],
                           (lambda _=False, tid=t["id"]: self._win.apply_theme(tid)),
                           icon=theme_ico.get(t["id"], "◐"))
            b.setFixedWidth(LOOK_BTN_W)
            self._theme_btns[t["id"]] = b
        # 代码风格
        g3 = self._group(h, "代码风格（代码块）")
        from config import CODE_STYLES
        code_ico = {"classic": "</>", "dark": "●", "eye": "◑", "mini": "○"}
        for sid, slabel in CODE_STYLES:
            b = g3.add_big(slabel, "切换代码风格：%s" % slabel,
                           (lambda _=False, s=sid: self._win.set_code_prefs(style=s)),
                           icon=code_ico.get(sid, "</>"))
            b.setFixedWidth(LOOK_BTN_W)
            self._code_btns[sid] = b
        h.addStretch(1)
        self.addWidget(w)

    # ---- 工具 ----
    def _build_tools(self):
        w, h = self._page()
        g = self._group(h, "版本容灾")
        g.add_big("历史版本", "历史版本 (Ctrl+Shift+H)", self._act("历史版本…"), "↺", "Ctrl+Shift+H")
        g.add_big("立即留档", "立即留档（版本快照）", self._act("立即留档（版本快照）"), "❖")
        g = self._group(h, "批量工具")
        g.add_big("迁移图片", "迁移内嵌图片为文件", self._act("迁移内嵌图片为文件…"), "▦")
        g.add_big("归档工作区", "归档整个工作区", self._act("归档整个工作区…"), "⊟")
        g = self._group(h, "设置")
        g.add_big("系统设置", "系统设置 (Ctrl+,)", self._act("系统设置…"), "⚙", "Ctrl+,")
        g.add_big("快捷键设置", "快捷键设置", self._act("快捷键设置…"), "⌨")
        h.addStretch(1)
        self.addWidget(w)

    # ---- 状态同步 ----
    def _toggle_disp(self, name):
        self._win._shortcut_acts.get(name) and self._win._shortcut_acts[name].trigger()
        self.sync_display()

    def sync_mode(self, mid):
        """模式大钮勾选态（mainwindow._update_mode_button 调用）。"""
        for m, b in self._mode_btns.items():
            b.set_checked(m == mid)

    def sync_display(self):
        """显示三开关勾选态跟随实际可见性。"""
        w = self._win
        vis = {"显示 / 隐藏侧边栏": w._sidebar.isVisible(),
               "显示 / 隐藏工具栏": w._tool_tb.isVisible(),
               "显示 / 隐藏状态栏": w.statusBar().isVisible()}
        for name, b in self._disp_btns.items():
            b.setChecked(vis.get(name, True))

    def sync_look(self):
        """外观页 ✓ 勾选态（页签切入时刷新）。"""
        for sid, b in self._style_btns.items():
            b.setChecked(sid == self._win._uistyle)
        for tid, b in self._theme_btns.items():
            b.setChecked(tid == self._win._theme)
        for sid, b in self._code_btns.items():
            b.setChecked(sid == self._win._code_style)

    def apply_palette(self, p):
        """v3.44.28（OFFICE-THEME）：功能区内容区随主题重绘。

        重绘：自身底色 + 所有大命令钮（_CmdButton）/ 小命令钮（#gsel）/
        组间分隔（#ribVSep）/ 组标题（#ribCap），确保切换主题后整条 Office
        控件配色协调、与标题栏 / 页签行 / 编辑器一致。"""
        self._p = dict(T)
        self._p.update(p or {})
        self.setStyleSheet("background:%s;" % self._p["bg"])
        for b in self.findChildren(_CmdButton):
            b.apply_palette(self._p)
        for b in self.findChildren(QToolButton):
            if b.objectName() == "gsel":
                b.setStyleSheet(_gsel_qss(self._p, bool(b.property("has_text"))))
        for v in self.findChildren(QFrame):
            if v.objectName() == "ribVSep":
                v.setStyleSheet("background:%s;" % self._p["line2"])
        for c in self.findChildren(QLabel):
            if c.objectName() == "ribCap":
                c.setStyleSheet(
                    "font-size:11px;font-weight:600;color:%s;padding:0 2px;"
                    "letter-spacing:.3px;" % self._p["tx3"])
