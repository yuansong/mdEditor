# -*- coding: utf-8 -*-
"""PS01-MAC 统一工具栏 + 无边框窗口支持 —— v3.41.0（UISTYLE-2，用户拍板方案 A）。

设计稿：docs/ui-redesign/主界面效果图-PS01-MAC.html
- 统一工具栏（52px）：红绿灯 + ☰ 菜单条开关 + 胶囊菜单条（5 菜单）+ 工具钮
  + 居中文档标题 + 右端视图状态区（由 mainwindow._vsz_corner 反_parent进来）；
- 无边框窗口：不改 Qt 窗口 flags（避免 re-show 闪烁 / 兼容坑），而是在
  MainWindow.nativeEvent 里拦截 WM_NCCALCSIZE（去掉系统标题栏、最大化时
  四周内缩一个隐形边框宽）与 WM_NCHITTEST（HTCAPTION 拖拽 + 八向缩放边），
  系统原生缩放 / Aero Snap 贴边 / 最小化动画全部保留。

本模块只含 UI 与命中测试辅助；窗口形态开关由 mainwindow._apply_mac_chrome 驱动。
"""

import ctypes
import platform

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QSizePolicy, QToolButton, QVBoxLayout,
    QWidget,
)

# v3.47（P0 跨平台）：本模块含 Win32 无边框窗口逻辑，仅在 Windows 激活；
# 非 Windows 下所有 Win32 调用降级为空操作，保证模块可安全导入。
_IS_WIN = (platform.system() == "Windows")

from icons import (
    icon_find, icon_history, icon_new, icon_open, icon_redo, icon_save,
    icon_settings, icon_sidepanel, icon_undo,
)

# ── Win32 常量 ──
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
HTCLIENT = 1
HTCAPTION = 2
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT = 10, 11, 12, 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17
SM_CXSIZEFRAME = 32
SM_CXPADDEDBORDER = 92
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_FRAMECHANGED = 0x0001, 0x0002, 0x0004, 0x0010


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
                ("wParam", ctypes.c_void_p), ("lParam", ctypes.c_void_p),
                ("time", ctypes.c_uint), ("pt", POINT)]


if _IS_WIN:
    _user32 = ctypes.windll.user32
else:
    _user32 = None


def frame_thickness():
    """隐形缩放边宽（Win10/11 通常 8px）；非 Windows 返回 0。"""
    if not _IS_WIN or _user32 is None:
        return 0
    return _user32.GetSystemMetrics(SM_CXSIZEFRAME) + _user32.GetSystemMetrics(SM_CXPADDEDBORDER)


def force_frame_recalc(hwnd):
    """窗口形态标记变化后强制重算非客户区（不闪烁）；非 Windows 空操作。"""
    if not _IS_WIN or _user32 is None:
        return
    _user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                         SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)


def handle_native_event(w, message_param, win):
    """MainWindow.nativeEvent 分发器。返回 (handled, result) 或 None（不处理）。

    非 Windows 或窗口未启用无边框形态时直接透传（None），保证 macOS / Linux
    走系统原生窗口（含原生标题栏 / 拖拽 / 缩放）。"""
    if not _IS_WIN or not getattr(w, "_mac_frame_on", False):
        return None
    msg = MSG.from_address(int(message_param))
    if msg.message == WM_NCCALCSIZE and msg.wParam:
        # wParam=TRUE：返回 0 = 整窗皆客户区（去掉系统标题栏与边框内缩）
        if _user32.IsZoomed(msg.hwnd):
            t = frame_thickness()
            rgrc = ctypes.cast(int(msg.lParam), ctypes.POINTER(RECT)).contents
            rgrc.left += t
            rgrc.top += t
            rgrc.right -= t
            rgrc.bottom -= t
        return (True, 0)
    if msg.message == WM_NCHITTEST:
        # lParam = y<<16 | x（屏幕坐标，多显示器下每半字可为负 → 按有符号 16 位取）
        lp = int(msg.lParam) or 0
        x = ctypes.c_short(lp & 0xFFFF).value
        y = ctypes.c_short((lp >> 16) & 0xFFFF).value
        return (True, _hit_test(win, x, y))
    return None


def _hit_test(win, gx, gy):
    """无边框命中测试：八向缩放边 + 标题栏 HTCAPTION（交互子控件除外）。"""
    pos = win.mapFromGlobal(QPoint(gx, gy))
    w, h = win.width(), win.height()
    if win.isFullScreen():
        return HTCLIENT
    t = frame_thickness()
    if not win.isMaximized():
        on_l = pos.x() < t
        on_r = pos.x() >= w - t
        on_t = pos.y() < t
        on_b = pos.y() >= h - t
        if on_t and on_l:
            return HTTOPLEFT
        if on_t and on_r:
            return HTTOPRIGHT
        if on_b and on_l:
            return HTBOTTOMLEFT
        if on_b and on_r:
            return HTBOTTOMRIGHT
        if on_l:
            return HTLEFT
        if on_r:
            return HTRIGHT
        if on_t:
            return HTTOP
        if on_b:
            return HTBOTTOM
    # 标题栏拖拽区：位于统一工具栏行内、且命中的是背景 / 标题文字（非交互控件）
    if pos.y() < _titlebar_height(win):
        child = win.childAt(pos)
        if child is not None:
            name = child.objectName()
            if name in ("macTitleBar", "macTitle", "macLights", "macMenuStrip",
                        "ribbonTitle"):
                return HTCAPTION
    return HTCLIENT


def _titlebar_height(win):
    # v3.44.12（RIBBON-1）：命中白名单泛化——mac / ribbon 两种自绘标题栏共用无边框机制
    for attr in ("_mac_title", "_ribbon_bar"):
        tb = getattr(win, attr, None)
        if tb is not None and tb.isVisible():
            return tb.height()
    return 0


class MacTitleBar(QFrame):
    """PS01-MAC 统一工具栏。占位 QMainWindow 菜单栏行（置于 central widget 上方）。"""

    def __init__(self, win):
        super().__init__(win)
        self.setObjectName("macTitleBar")
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._win = win

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(8)

        # ── 红绿灯（12px 纯色圆点，设计稿口径：纯色无符号；悬停/按下仅微暗反馈）──
        lights = QFrame(self)
        lights.setObjectName("macLights")
        self._lights = lights
        ll = QHBoxLayout(lights)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        self._btn_close = self._light(lights, "ltR", "关闭", win.close)
        self._btn_min = self._light(lights, "ltY", "最小化", win.showMinimized)
        self._btn_max = self._light(lights, "ltG", "最大化 / 还原", win._mac_toggle_max)
        lay.addWidget(lights)
        lay.addSpacing(4)

        # ── ☰ 菜单条开关（胶囊菜单条默认隐藏，点击展开 / 收起）──
        self._btn_menu = QToolButton(self)
        self._btn_menu.setObjectName("macMenuBtn")
        self._btn_menu.setText("☰")
        self._btn_menu.setToolTip("菜单（文件 / 编辑 / 视图 / 工具 / 帮助）")
        self._btn_menu.setCursor(Qt.PointingHandCursor)
        self._btn_menu.setCheckable(True)
        self._btn_menu.setFixedSize(30, 30)
        self._btn_menu.toggled.connect(self._toggle_menustrip)
        lay.addWidget(self._btn_menu)

        # 胶囊菜单条：5 个 QToolButton 各挂 mainwindow 既有 QMenu（同源菜单）
        self._strip = QFrame(self)
        self._strip.setObjectName("macMenuStrip")
        self._strip.hide()
        sl = QHBoxLayout(self._strip)
        sl.setContentsMargins(6, 3, 6, 3)
        sl.setSpacing(2)
        self._menu_btns = {}
        for name, menu in win._mac_source_menus():
            b = QToolButton(self._strip)
            b.setText(name)
            b.setCursor(Qt.PointingHandCursor)
            b.setPopupMode(QToolButton.InstantPopup)
            b.setMenu(menu)
            sl.addWidget(b)
            self._menu_btns[name] = b
        lay.addWidget(self._strip)

        # ── 工具钮组（与左工具栏同源动作）──
        lay.addSpacing(2)
        sep = QFrame(self)
        sep.setObjectName("macTSep")
        sep.setFixedSize(1, 18)
        lay.addWidget(sep)

        def tb_btn(icon, tip, slot):
            b = QToolButton(self)
            b.setIcon(icon)
            b.setIconSize(QSize(16, 16))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoRaise(True)
            b.setFixedSize(30, 30)
            b.clicked.connect(slot)
            lay.addWidget(b)
            return b

        self._btn_side = tb_btn(icon_sidepanel(20), "侧边栏 (Ctrl+Shift+L)", win.toggle_sidebar)
        tb_btn(icon_new(), "新建 (Ctrl+N)", win.new_file)
        tb_btn(icon_open(), "打开 (Ctrl+O)", lambda: win.open_file(None))
        tb_btn(icon_save(), "保存 (Ctrl+S)", win.save_file)
        sep2 = QFrame(self)
        sep2.setObjectName("macTSep")
        sep2.setFixedSize(1, 18)
        lay.addWidget(sep2)
        tb_btn(icon_undo(), "撤销 (Ctrl+Z)", lambda: win._js_active('window.cmd("undo")'))
        tb_btn(icon_redo(), "重做 (Ctrl+Y)", lambda: win._js_active('window.cmd("redo")'))
        sep3 = QFrame(self)
        sep3.setObjectName("macTSep")
        sep3.setFixedSize(1, 18)
        lay.addWidget(sep3)
        tb_btn(icon_find(), "查找 / 替换 (Ctrl+F)", lambda: win.show_find(False))
        tb_btn(icon_history(), "历史版本 (Ctrl+Shift+H)", win.show_history)
        tb_btn(icon_settings(), "系统设置", win.show_settings)

        # ── 居中文档标题（绝对定位，与设计稿一致）──
        self._title = QLabel(self)
        self._title.setObjectName("macTitle")
        self._title.setText("未命名")

        # ── 右端视图状态区：反_parent mainwindow._vsz_corner（单一状态源不复制）──
        self._vsz = getattr(win, "_vsz_corner", None)
        self.relayout_vsz()

    def relayout_vsz(self):
        """把主窗口视图状态区装进标题栏右端（进出 mac 形态均可重复调用）。

        widget 被 setParent 反_parent 走时 QLayout 不会自动摘除条目，
        这里统一先清掉「弹性空白 + 旧 vsz 条目」再重装，避免条目堆积/空隙。"""
        lay = self.layout()
        for i in reversed(range(lay.count())):
            it = lay.itemAt(i)
            if it.widget() is None or it.widget() is self._vsz:
                lay.takeAt(i)
        if self._vsz is not None:
            lay.addStretch(1)
            lay.addWidget(self._vsz)
        else:
            lay.addStretch(1)

    def sync_side_icon(self, vis):
        """侧边栏开关图标双态（mainwindow._update_side_btn 转发）。"""
        self._btn_side.setIcon(icon_sidepanel(20, collapsed=not vis))

    # ── 红绿灯（v3.41.4：去掉 ✕/−/+ 符号，纯色圆点表示，回归设计稿口径）──
    def _light(self, parent, objname, tip, slot):
        b = QToolButton(parent)
        b.setObjectName(objname)
        b.setText("")           # 纯色无符号（提示靠 tooltip）
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(12, 12)
        b.clicked.connect(slot)
        parent.layout().addWidget(b)
        return b

    # ── 菜单条开关 ──
    def _toggle_menustrip(self, on):
        self._strip.setVisible(on)

    # ── 文档标题（mainwindow.setWindowTitle 覆写转发）──
    def set_doc_title(self, text):
        self._title.setText(text or "未命名")
        self._reposition_title()

    def _reposition_title(self):
        """标题绝对居中（设计稿 .tb-title left:50%）。"""
        t = self._title
        t.adjustSize()
        t.move(max(0, (self.width() - t.width()) // 2), (self.height() - t.height()) // 2)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reposition_title()

    def mouseDoubleClickEvent(self, e):
        # 空白处双击 = 最大化 / 还原（Windows 惯例）
        if e.button() == Qt.LeftButton and self.childAt(e.position().toPoint()) is self:
            self._win._mac_toggle_max()
        super().mouseDoubleClickEvent(e)

    def apply_palette(self, p):
        """随主题 / 风格调色（p = uistyles.merge_palette 结果）。"""
        self.setStyleSheet(f"""
            QFrame#macTitleBar {{
                /* v3.44.3（DESIGN01）：设计稿口径「Win11 Mica 云母底（无分隔线）」
                   ——纯色底、去渐变、去底部分隔线；与下方 chrome2 标签条以底色区分 */
                background: {p['bg']};
            }}
            QFrame#macTitleBar QToolButton {{ border: none; background: transparent;
                color: {p['text_muted']}; font-size: 13px; border-radius: 6px; }}
            QFrame#macTitleBar QToolButton:hover {{ background: {p['hover_bg']};
                color: {p['text']}; }}
            /* 红绿灯（v3.41.4：设计稿口径「纯色无符号」——始终纯色圆点，
               不显符号；仅按下时加深反馈。规则必须带 #macTitleBar 前缀以
               压过通用 hover 规则，且置于其后——v3.41.1 悬停灰点缺陷的修复点。
               注意：QSS 注释只能用 斜杠星 语法，# 行会被当 ID 选择器毁掉整段规则）*/
            QFrame#macTitleBar QToolButton#ltR, QFrame#macTitleBar QToolButton#ltY,
            QFrame#macTitleBar QToolButton#ltG {{
                border-radius: 6px; color: transparent; font-size: 9px; font-weight: 700; }}
            QFrame#macTitleBar QToolButton#ltR {{ background: #ff5f57; }}
            QFrame#macTitleBar QToolButton#ltY {{ background: #febc2e; }}
            QFrame#macTitleBar QToolButton#ltG {{ background: #28c840; }}
            QFrame#macTitleBar QToolButton#ltR:pressed {{ background: #d94943; }}
            QFrame#macTitleBar QToolButton#ltY:pressed {{ background: #d29a24; }}
            QFrame#macTitleBar QToolButton#ltG:pressed {{ background: #1fa533; }}
            QFrame#macMenuStrip {{ background: {p['menu_bg']};
                border: 1px solid {p['border']}; border-radius: 8px; }}
            QFrame#macMenuStrip QToolButton {{ border: none; border-radius: 5px;
                padding: 4px 10px; background: transparent; color: {p['text']}; }}
            QFrame#macMenuStrip QToolButton:hover {{ background: {p['menu_hover_bg']};
                color: {p['sel_text'] if p.get('sel_text') else p['accent']}; }}
            QToolButton#macMenuBtn {{ border: none; border-radius: 6px; font-size: 14px;
                color: {p['text_muted']}; }}
            QToolButton#macMenuBtn:hover {{ background: {p['hover_bg']};
                color: {p['text']}; }}
            QToolButton#macMenuBtn:checked {{ background: {p['accent_soft']};
                color: {p['accent']}; }}
            QFrame#macTSep {{ background: {p['sep']}; }}
            QLabel#macTitle {{ color: {p['text']}; font-size: 13px; font-weight: 600;
                background: transparent; }}
        """)
