# -*- coding: utf-8 -*-
"""主窗口：多文档标签、三视图（写作/源码/分屏）、文件操作与导出。"""
import base64
import binascii
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from PySide6.QtCore import QEvent, QTimer, QUrl, QSize, Qt, QSettings, QMimeData
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QMenu, QMessageBox, QSplitter, QStackedWidget, QTabBar, QToolBar,
    QToolButton, QVBoxLayout, QWidget,
)
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

import exporters
from config import APP_NAME, DEMO_MD, HERE, MD_EXTS, MODES, js

# 斜杠（/）菜单可配置项：一级菜单 id 集与默认顺序 / 默认项 / 二级默认下标
# v3.30.3：按用户要求移除「上标 / 下标」（supsub）一级项；^x^ / ~x~ 语法仍可输入
SLASH_IDS = ("heading", "list", "table", "code", "hr", "quote", "image", "chart",
             "footnote", "deflist", "math")
SLASH_ORDER_DEFAULT = ["heading", "list", "table", "code", "hr", "quote", "image", "chart",
                       "footnote", "deflist", "math"]
SLASH_SUB_DEFAULTS = {"heading": 2, "list": 1, "chart": 0, "math": 0,
                      "footnote": 0}  # 标题默认H3 / 列表默认有序 / 图表默认流程图 / 公式默认上标


def merge_slash_order(saved):
    """把「已保存的菜单顺序」与最新默认顺序合并。

    新版本新增的一级菜单项按其**默认相对位置**插到相邻项旁边，而不是一律追加到末尾 ——
    否则「公式固定在最后」这类刻意设计会被后来的新项挤掉，用户排好的第一项也会被冲掉。
    传入完整默认顺序时结果与传入值完全一致（幂等）。
    """
    ids = [x for x in (saved or []) if x in SLASH_IDS]
    for x in SLASH_ORDER_DEFAULT:
        if x in ids:
            continue
        i = SLASH_ORDER_DEFAULT.index(x)
        prev = next((y for y in reversed(SLASH_ORDER_DEFAULT[:i]) if y in ids), None)
        nxt = next((y for y in SLASH_ORDER_DEFAULT[i + 1:] if y in ids), None)
        if prev is not None:
            ids.insert(ids.index(prev) + 1, x)
        elif nxt is not None:
            ids.insert(ids.index(nxt), x)
        else:
            ids.append(x)
    return ids


# 可插入的图片扩展名与对应 MIME（data URL 用）
IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
IMG_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp"}
# 反向映射：剪贴板图片的 MIME → 扩展名（落盘时用）
MIME_EXT = {v: k for k, v in IMG_MIME.items()}
MIME_EXT["image/jpg"] = ".jpg"
# 内嵌图片（data URL）在 Markdown 中的形态：![alt](data:image/png;base64,xxxx)
IMG_DATA_RE = re.compile(
    r"!\[([^\]]*)\]\(\s*(data:image/([A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+))\s*\)")
from dialogs import (
    CommandPaletteDialog, FindDialog, HistoryDialog, InsertImageDialog,
    SettingsDialog, ShortcutDialog,
)
from icons import (
    MODE_ICONS, icon_find, icon_new, icon_open, icon_redo, icon_save,
    icon_settings, icon_undo,
)
from sidebar import Sidebar
import styles


class EditorPage(QWebEnginePage):
    """自定义页面：把 JS alert / confirm / prompt 换成中文原生对话框。"""

    def javaScriptPrompt(self, origin, msg, default):
        from PySide6.QtWidgets import QInputDialog
        parent = self.parent() if isinstance(self.parent(), QWidget) else None
        text, ok = QInputDialog.getText(parent, "输入", str(msg), text=str(default or ""))
        return ok, text

    def javaScriptAlert(self, origin, msg):
        QMessageBox.information(self.parent() if isinstance(self.parent(), QWidget) else None,
                                "提示", str(msg))

    def javaScriptConfirm(self, origin, msg):
        btn = QMessageBox.question(self.parent() if isinstance(self.parent(), QWidget) else None,
                                   "确认", str(msg),
                                   QMessageBox.Ok | QMessageBox.Cancel)
        return btn == QMessageBox.Ok


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1240, 830)
        self.file_path = None
        self._dirty = False
        self._pdf_view = None
        self._pdf_path = None
        self._quitting = False

        self._settings = QSettings("WorkBuddy", "WorkBuddyMarkdown")
        # ---- 主题 / 外观（启动即恢复上次选择）----
        self._theme = self._settings.value("theme", "light")
        if self._theme not in styles.THEME_IDS:
            self._theme = "light"
        self._zoom = float(self._settings.value("zoom", 1.0) or 1.0)
        self._autosave = self._settings.value("autosave", True, type=bool)
        # 代码块默认语言（插入代码块时预选，可在 系统设置→编辑器 修改）
        self._code_lang = str(self._settings.value("codeLang", "C") or "C")
        # v3.25 代码块行号 / 代码风格（系统设置→编辑器 可改；代码栏「风格」按钮可临时切换）
        self._code_lnum = str(self._settings.value("codeLineNum", "1")) not in ("0", "false")
        self._code_style = str(self._settings.value("codeStyle", "classic") or "classic")
        # 打字机 / 专注模式（视图菜单或系统设置开关，持久化，重启保持）
        self._typewriter = self._settings.value("typewriter", False, type=bool)
        self._focus = self._settings.value("focus", False, type=bool)
        # P1-1 自动配对 / P1-8 Emoji 补全（默认开，系统设置→编辑器可关）
        self._auto_pair = self._settings.value("autoPair", True, type=bool)
        self._emoji = self._settings.value("emojiComplete", True, type=bool)
        # P1-6 版本历史保留份数
        try:
            self._history_keep = max(1, min(200, int(self._settings.value("historyKeep", 20))))
        except (TypeError, ValueError):
            self._history_keep = 20
        # 斜杠（/）菜单配置（系统设置→编辑器 可改）
        raw_order = str(self._settings.value("slashMenuOrder", "") or "")
        saved_order = [x for x in raw_order.split(",") if x in SLASH_IDS]
        self._slash_order = merge_slash_order(saved_order)
        saved_def = str(self._settings.value("slashMenuDef", "heading") or "heading")
        self._slash_def = saved_def if saved_def in self._slash_order else self._slash_order[0]
        def _sub_int(key, dft):
            try:
                return max(0, int(self._settings.value(key, dft)))
            except (TypeError, ValueError):
                return dft
        self._slash_sub = {
            "heading": _sub_int("slashSubHeading", SLASH_SUB_DEFAULTS["heading"]),
            "list": _sub_int("slashSubList", SLASH_SUB_DEFAULTS["list"]),
            "chart": _sub_int("slashSubChart", SLASH_SUB_DEFAULTS["chart"]),
            "math": _sub_int("slashSubMath", SLASH_SUB_DEFAULTS["math"]),
        }
        # 大纲显示级别（1~6，默认 3）与文件列表显示模式（current=当前 / blank=空白项）
        try:
            self._outline_level = max(1, min(6, int(self._settings.value("outlineLevel", 3))))
        except (TypeError, ValueError):
            self._outline_level = 3
        _flm = str(self._settings.value("fileListMode", "current") or "current")
        self._file_list_mode = "blank" if _flm == "blank" else "current"
        # v3.31.2（#3）：大纲分节字数后缀显示开关（默认关）
        self._outline_words = self._settings.value("outlineWords", False, type=bool)
        # v3.31.2（#8）：段落首行缩进格数（0~4，默认 0）
        try:
            self._para_indent = max(0, min(4, int(self._settings.value("paraIndent", 0))))
        except (TypeError, ValueError):
            self._para_indent = 0
        # v3.31.2（#9）：标题 1 全局居中（默认关）
        self._h1_center = self._settings.value("h1Center", False, type=bool)
        # 图片存放方式：assets=落盘到「文档名.assets/」并插入相对路径（推荐）
        #              embed =内嵌 data URL（图片写入 Markdown 本身）
        _imgm = str(self._settings.value("imageMode", "assets") or "assets")
        self._image_mode = "embed" if _imgm == "embed" else "assets"
        # 外部 pandoc 路径（导出 docx / EPUB 时优先使用；留空则自动探测 PATH）
        self._pandoc_path = str(self._settings.value("pandocPath", "") or "")
        # P1-7 外部编辑器可执行文件（留空 = 用系统默认关联程序打开）
        self._external_editor = str(self._settings.value("externalEditor", "") or "")
        # 统计详情缓存（状态栏点击查看）与搜索结果跳转等待状态
        self._stats = {}
        self._outline_cache = []    # 最近一次大纲（导出 PDF 时生成书签）
        self._pending_toc = None
        self._pending_goto = None
        self._pending_tries = 0

        # ---- 多文档 ----
        self._docs = []          # [{"path": str|None, "content": str|None}]
        self._cur = -1
        self._switching = False
        self._pending_switch = -1

        # ---- 模式（edit=写作 / src=源码 / dual=分屏）----
        self._mode = "edit"
        self._dual = False
        self._last_preview_md = None

        # ---- 每个视图的加载状态 ----
        # role -> {"loaded": bool, "pending": str, "src": bool, "preview": bool}
        self._vstate = {
            "edit": {"loaded": False, "pending": DEMO_MD, "src": False, "preview": False},
            "src": {"loaded": False, "pending": "", "src": True, "preview": False},
            "prev": {"loaded": False, "pending": "", "src": False, "preview": True},
        }

        self._init_ui()
        self._init_menu_toolbar()
        self.apply_theme(self._theme, persist=False)

        # 初始文档：欢迎页
        self._add_doc(path=None, text=DEMO_MD)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(700)

        # v3.29 双栏同步滚动：独立轻量定时器，非双栏时空转开销可忽略
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._poll_sync_scroll)
        self._sync_timer.start(160)

        self._update_title()

    # ================= UI =================
    def _init_ui(self):
        self._view = QWebEngineView(self)       # WYSIWYG 编辑视图
        # 分屏用的源码 / 预览视图惰性创建（见 _ensure_dual_views）：
        # 每个视图都要加载 editor.html + KaTeX，启动只加载当前需要的 1 个可明显提速
        self._view_src = None
        self._view_prev = None
        self._dual_split = None

        # 自定义页面：JS prompt / alert / confirm 使用中文对话框
        self._view.setPage(EditorPage(self._view))
        # file:// 页面默认禁止加载远程资源（README 徽章图等显示不出来），放开
        _v = self._view
        _v.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        _v.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        _v.loadFinished.connect(lambda ok: self._on_loaded(ok, "edit"))
        _v.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), "editor.html")))
        # Typora 式中文右键菜单（替代 Chromium 默认英文菜单）
        _v.setContextMenuPolicy(Qt.CustomContextMenu)
        _v.customContextMenuRequested.connect(
            lambda pos: self._show_ctx_menu(self._view, pos))

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._view)        # 0 单栏 WYSIWYG（1 = 双栏，惰性添加）

        # 多文件标签页
        self._tabbar = QTabBar(self)
        self._tabbar.setTabsClosable(True)
        self._tabbar.setMovable(True)
        self._tabbar.setExpanding(False)
        self._tabbar.setDrawBase(False)
        self._tabbar.setCursor(Qt.PointingHandCursor)
        self._tabbar.currentChanged.connect(self._on_tab_clicked)
        self._tabbar.tabCloseRequested.connect(self._close_tab)
        self._tabbar.tabMoved.connect(self._on_tab_moved)
        tab_wrap = QWidget(self)
        tab_wrap.setObjectName("tabstrip")
        tl = QHBoxLayout(tab_wrap)
        tl.setContentsMargins(8, 0, 0, 0)
        tl.addWidget(self._tabbar)
        tl.addStretch(1)

        right = QWidget(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(tab_wrap)
        rl.addWidget(self._stack, 1)

        self._sidebar = Sidebar(self)
        # 应用持久化的侧栏设置：大纲显示级别 / 分节字数开关 / 文件列表显示模式
        self._sidebar.set_outline_level(self._outline_level)
        self._sidebar.set_outline_words(self._outline_words)
        self._sidebar.set_file_mode(self._file_list_mode)
        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)
        split.addWidget(self._sidebar)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setHandleWidth(1)
        self.setCentralWidget(split)
        self.setAcceptDrops(True)

        self._status = QLabel("就绪")
        self.statusBar().addWidget(self._status)
        # v3.29d（B3）：临时提示独立区域（右侧、3 秒自动还原），不再覆盖左侧常驻信息
        self._toast = QLabel("")
        self._toast.setStyleSheet("color: #0052d9; padding-right: 12px;")
        self.statusBar().addPermanentWidget(self._toast)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast.setText(""))
        # v3.29d（UX #26）：状态栏常驻「⌘ 命令」入口，提高命令面板发现率
        self._cmd_entry = QLabel("⌘ 命令")
        self._cmd_entry.setToolTip("打开命令面板（Ctrl+Shift+P）")
        self._cmd_entry.setCursor(Qt.PointingHandCursor)
        self._cmd_entry.setStyleSheet("color: #0052d9; padding: 0 8px;")
        self._cmd_entry.mousePressEvent = lambda _e: self.show_command_palette()
        self.statusBar().addPermanentWidget(self._cmd_entry)
        self._count = QLabel("字数 0 · 约 0 分钟")
        self._count.setCursor(Qt.PointingHandCursor)
        self._count.setToolTip("字数统计（中文按字 / 英文按词）· 点击查看详情")
        self._count.installEventFilter(self)
        self.statusBar().addPermanentWidget(self._count)
        self._pos = QLabel("行 1 · 列 1")
        self._pos.setToolTip("光标所在行 / 列（Ctrl+G 可跳转到指定行）")
        self.statusBar().addPermanentWidget(self._pos)
        # v3.30.10（HP-1）：状态栏「当前块」——光标进入任何块即显示类型 / 标题级别，
        # 零遮挡确认「选中的标题是几级」（数据随 getCaretLineCol 轮询通道返回）
        self._blktype = QLabel("")
        self._blktype.setStyleSheet("color: #6b7280; padding-right: 4px;")
        self.statusBar().addPermanentWidget(self._blktype)

    def _ensure_dual_views(self):
        """首次进入分屏时才创建源码 / 预览视图并加载编辑器页面（启动提速）。"""
        if self._view_src is not None:
            return
        self._view_src = QWebEngineView(self)
        self._view_prev = QWebEngineView(self)
        for role, v in (("src", self._view_src), ("prev", self._view_prev)):
            v.setPage(EditorPage(v))
            v.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            v.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            v.loadFinished.connect(lambda ok, r=role: self._on_loaded(ok, r))
            v.setContextMenuPolicy(Qt.CustomContextMenu)
            v.customContextMenuRequested.connect(
                lambda pos, view=v: self._show_ctx_menu(view, pos))
            v.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), "editor.html")))

        self._dual_split = QSplitter(Qt.Horizontal, self)
        self._dual_split.setChildrenCollapsible(False)
        self._dual_split.addWidget(self._view_src)
        self._dual_split.addWidget(self._view_prev)
        self._dual_split.setStretchFactor(0, 1)
        self._dual_split.setStretchFactor(1, 1)
        self._dual_split.setHandleWidth(1)
        self._stack.addWidget(self._dual_split)  # index 1

    # ================= 工具栏 + 菜单 =================
    def _init_menu_toolbar(self):
        # ---- 左侧竖向工具栏：只保留文件级高频操作，统一线性图标 ----
        tb = QToolBar("主工具栏", self)
        tb.setObjectName("sideTB")
        tb.setMovable(False)
        tb.setOrientation(Qt.Vertical)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.LeftToolBarArea, tb)
        self._tool_tb = tb

        def tb_act(icon, tooltip, slot):
            a = QAction(self)
            a.setIcon(icon)
            a.setToolTip(tooltip)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        # 顶部：侧边栏开关（« 收起 / » 展开，Typora 同款侧栏位置）
        self._btn_side = QToolButton(tb)
        self._btn_side.setAutoRaise(True)
        self._btn_side.setText("«")
        self._btn_side.setToolTip("收起侧边栏 (Ctrl+Shift+L)")
        self._btn_side.setCursor(Qt.PointingHandCursor)
        # v3.26：收拢/展开符号加大加粗，保证可见性（用户反馈原字体太小）。
        # 用按钮级 QSS 覆盖（全局 QSS 的 px 字号会压过 QFont，pointSize 方式无效）
        self._btn_side.setStyleSheet("font-size: 17px; font-weight: 800; padding: 0 6px;")
        self._btn_side.clicked.connect(self.toggle_sidebar)
        tb.addWidget(self._btn_side)
        tb.addSeparator()

        tb_act(icon_new(), "新建 (Ctrl+N)", self.new_file)
        tb_act(icon_open(), "打开 (Ctrl+O)", lambda: self.open_file(None))
        tb_act(icon_save(), "保存 (Ctrl+S)", self.save_file)
        tb.addSeparator()
        # 撤销 / 重做：快捷键仍由编辑菜单注册，这里只放图标按钮
        tb_act(icon_undo(), "撤销 (Ctrl+Z)", lambda: self._js_active('window.cmd("undo")'))
        tb_act(icon_redo(), "重做 (Ctrl+Y)", lambda: self._js_active('window.cmd("redo")'))
        tb.addSeparator()
        tb_act(icon_find(), "查找 / 替换 (Ctrl+F)", lambda: self.show_find(False))
        tb.addSeparator()
        # 模式切换按钮：单击循环 写作 → 源码 → 分屏 → 写作
        self._btn_mode = QToolButton(tb)
        self._btn_mode.setAutoRaise(True)
        self._btn_mode.setIconSize(QSize(20, 20))
        self._btn_mode.setCursor(Qt.PointingHandCursor)
        self._btn_mode.clicked.connect(self.cycle_mode)
        tb.addWidget(self._btn_mode)
        self._update_mode_button()
        # 系统设置入口（左侧工具栏底部齿轮按钮）
        tb.addSeparator()
        tb_act(icon_settings(), "系统设置", self.show_settings)

        self._shortcut_acts = {}   # 动作名 -> QAction（设置->快捷键设置 可配置）
        self._shortcut_defs = []   # [(分组, [(动作名, 默认快捷键), ...]), ...]

        # ---- 文件菜单 ----
        m_file = self.menuBar().addMenu("文件(&F)")
        self._reg_act("文件", "新建", "Ctrl+N", self.new_file, menu=m_file)
        self._reg_act("文件", "打开…", "Ctrl+O", lambda: self.open_file(None), menu=m_file)
        self._reg_act("文件", "打开文件夹…", None, self.open_folder, menu=m_file)
        m_recent = self._recent_menu = m_file.addMenu("最近文件")
        m_recent.aboutToShow.connect(self._rebuild_recent_menu)
        m_file.addSeparator()
        self._reg_act("文件", "保存", "Ctrl+S", self.save_file, menu=m_file)
        self._reg_act("文件", "另存为…", "Ctrl+Shift+S", self.save_file_as, menu=m_file)
        self._reg_act("文件", "关闭标签页", "Ctrl+W", lambda: self._close_tab(self._cur), menu=m_file)
        m_file.addSeparator()
        self._reg_act("文件", "导出 HTML…", None, self.export_html, menu=m_file)
        self._reg_act("文件", "导出 PDF…（含书签）", None, self.export_pdf, menu=m_file)
        self._reg_act("文件", "导出 Word (docx)…", None, self.export_docx, menu=m_file)
        self._reg_act("文件", "导出 EPUB…", None, self.export_epub, menu=m_file)
        self._reg_act("文件", "迁移内嵌图片为文件…", None, self.migrate_embedded_images, menu=m_file)
        m_file.addSeparator()
        # P1-6 / P1-7：版本历史（v3.25：「资源管理器显示 / 外部程序打开」移入侧栏文件列表右键）
        self._reg_act("文件", "历史版本…", "Ctrl+Shift+H", self.show_history, menu=m_file)
        m_file.addSeparator()
        self._reg_act("文件", "退出", "Ctrl+Q", self.close, menu=m_file)

        # ---- 编辑菜单（剪贴板操作由 Web 内核原生处理，不注册全局快捷键）----
        m_edit = self.menuBar().addMenu("编辑(&E)")
        self._reg_act("编辑", "撤销", "Ctrl+Z", lambda: self._js_active('window.cmd("undo")'), menu=m_edit)
        self._reg_act("编辑", "重做", "Ctrl+Y", lambda: self._js_active('window.cmd("redo")'), menu=m_edit)
        m_edit.addSeparator()
        for label, act_name in (("剪切", QWebEnginePage.Cut), ("复制", QWebEnginePage.Copy),
                                ("粘贴", QWebEnginePage.Paste)):
            a = QAction(label, self)
            a.triggered.connect(lambda _=False, x=act_name: self._page_action(x))
            m_edit.addAction(a)
        a = QAction("全选", self)
        a.triggered.connect(lambda: self._page_action(QWebEnginePage.SelectAll))
        m_edit.addAction(a)
        # v3.29d（UX #34）：复制为 HTML —— 粘进微信 / Word 等保留格式
        a = QAction("复制为 HTML", self)
        a.triggered.connect(self.copy_as_html)
        m_edit.addAction(a)
        m_edit.addSeparator()
        self._reg_act("编辑", "查找…", "Ctrl+F", lambda: self.show_find(False), menu=m_edit)
        self._reg_act("编辑", "替换…", "Ctrl+H", lambda: self.show_find(True), menu=m_edit)
        self._reg_act("编辑", "转到行…", "Ctrl+G", self.goto_line, menu=m_edit)
        self._reg_act("编辑", "在文件夹中搜索…", "Ctrl+Shift+F", self.show_search,
                      menu=m_edit)  # v3.24：打开「查找」对话框的「全局搜索」页签
        # Ctrl+/ 唤起块菜单（空块时等价于 "/" 插入菜单）
        self._reg_act("编辑", "块菜单", "Ctrl+/",
                      lambda: self._js_active("window.openBlockMenu ? window.openBlockMenu() : null"),
                      menu=m_edit)
        m_edit.addSeparator()
        # P1-3 命令面板
        self._reg_act("编辑", "命令面板…", "Ctrl+Shift+P", self.show_command_palette, menu=m_edit)

        # ---- 格式命令：不再单设菜单（行菜单 / 斜杠菜单 / 快捷键已覆盖），
        #      仍注册为隐藏动作，使快捷键生效并可在"设置->快捷键设置"中修改 ----
        for _name, _seq, _cmd in (
            ("加粗", "Ctrl+B", "bold"), ("斜体", "Ctrl+I", "italic"),
            ("删除线", "Ctrl+Shift+X", "strike"), ("行内代码", "Ctrl+E", "code"),
            ("标题 1", "Ctrl+1", "h1"), ("标题 2", "Ctrl+2", "h2"),
            ("标题 3", "Ctrl+3", "h3"), ("正文", "Ctrl+0", "p"),
            ("引用", "Ctrl+Shift+Q", "quote"),
            ("插入表格", "Ctrl+Shift+T", "table"), ("插入代码块", "Ctrl+Shift+K", "fence"),
            ("插入数学公式", "Ctrl+Shift+M", "math"), ("插入分割线", "Ctrl+Shift+-", "hr"),
        ):
            self._reg_act("格式", _name, _seq, lambda _=False, c=_cmd: self._fmt(c))

        # ---- 视图菜单 ----
        m_view = self.menuBar().addMenu("视图(&V)")
        # 三种模式：互斥单选（与左侧工具栏按钮联动）
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_acts = {}
        _mode_seq = {"edit": None, "src": None, "dual": "Ctrl+Shift+D"}
        # （Ctrl+/ 已分配给「块菜单」，源码模式经左侧模式按钮或菜单切换）
        for mode_id, _icon, label, _desc in MODES:
            act = self._reg_act("视图", label, _mode_seq[mode_id],
                                lambda _=False, m=mode_id: self._set_mode(m),
                                menu=m_view, checkable=True)
            self._mode_group.addAction(act)
            self._mode_acts[mode_id] = act
        self._mode_acts["edit"].setChecked(True)
        m_view.addSeparator()
        self._act_sidebar = self._reg_act("视图", "显示 / 隐藏侧边栏", "Ctrl+Shift+L",
                                          self.toggle_sidebar, menu=m_view, checkable=True)
        self._act_sidebar.setChecked(True)
        self._reg_act("视图", "文件列表", "Ctrl+Shift+E", lambda: self._show_sidebar_tab(0), menu=m_view)
        self._reg_act("视图", "大纲", "Ctrl+Shift+O", lambda: self._show_sidebar_tab(1), menu=m_view)
        m_view.addSeparator()
        self._act_typewriter = self._reg_act("视图", "打字机模式", None,
                                             self.toggle_typewriter, menu=m_view, checkable=True)
        self._act_focus = self._reg_act("视图", "专注模式", None,
                                        self.toggle_focus, menu=m_view, checkable=True)
        # 启动时恢复上次持久化的模式勾选状态（模式本身随页面加载 setMode 下发）
        self._act_typewriter.setChecked(self._typewriter)
        self._act_focus.setChecked(self._focus)
        m_view.addSeparator()
        # P1-2 标题折叠
        self._reg_act("视图", "折叠全部标题", "Ctrl+Shift+[",
                      lambda: self.fold_all_headings(True), menu=m_view)
        self._reg_act("视图", "展开全部标题", "Ctrl+Shift+]",
                      lambda: self.fold_all_headings(False), menu=m_view)
        m_view.addSeparator()
        # v3.30.19（MMD-7）：全局图表主题（mermaid 主题；「跟随界面」= 空 = 自动）
        m_mmd = m_view.addMenu("图表主题")
        self._mmd_group = QActionGroup(self)
        self._mmd_group.setExclusive(True)
        for label, val in (("跟随界面主题", ""), ("默认（浅色）", "default"),
                           ("深色", "dark"), ("森林", "forest"), ("中性", "neutral")):
            a = QAction(label, self)
            a.setCheckable(True)
            a.setChecked((self._settings.value("mmdTheme", "") or "") == val)
            a.triggered.connect(lambda _c=False, v=val: self._set_mmd_theme(v))
            self._mmd_group.addAction(a)
            m_mmd.addAction(a)
        m_view.addSeparator()
        self._reg_act("视图", "全屏", "F11", self.toggle_fullscreen, menu=m_view)
        # 主题入口统一收口到「设置 → 系统设置」（原视图→主题子菜单已取消）
        self._theme_acts = {}

        # ---- 设置 ----
        m_set = self.menuBar().addMenu("设置(&S)")
        self._reg_act("设置", "系统设置…", None, self.show_settings, menu=m_set)
        self._reg_act("设置", "快捷键设置…", None, self.show_shortcut_settings, menu=m_set)

        # ---- 帮助（始终放最后）----
        m_help = self.menuBar().addMenu("帮助(&H)")
        self._reg_act("帮助", "快捷键一览", "F1", self._show_shortcuts, menu=m_help)
        self._reg_act("帮助", "关于", None, self._about, menu=m_help)

    def _set_mmd_theme(self, val):
        """v3.30.19（MMD-7）：全局图表主题切换（持久化 + 下发全部已加载视图）。"""
        self._settings.setValue("mmdTheme", val)
        self._js_all(f"window.setMmdTheme({js(val)})")
        self.show_status("图表主题已更新" + ("" if val else "（跟随界面主题）"))

    def _js_all(self, code):
        """对全部已加载的编辑器视图执行 JS。"""
        for role, view in (("edit", self._view), ("src", getattr(self, "_view_src", None)),
                           ("prev", getattr(self, "_view_prev", None))):
            st = self._vstate.get(role)
            if view is not None and st and st.get("loaded"):
                self._js_view(view, code)

    def _reg_act(self, group, name, seq, slot, menu=None, checkable=False):
        """创建动作并纳入快捷键管理体系（设置 -> 快捷键设置 可查看 / 修改）。

        seq 为 None 表示无默认快捷键（动作仍登记在案）；已有用户自定义值时优先使用。
        """
        act = QAction(name, self)
        if checkable:
            act.setCheckable(True)
        act.triggered.connect(slot)
        if seq:
            saved = self._settings.value(f"shortcut/{name}")
            act.setShortcut(QKeySequence(saved if isinstance(saved, str) and saved else seq))
            act.setShortcutContext(Qt.ApplicationShortcut)
        if menu is not None:
            menu.addAction(act)
        else:
            self.addAction(act)   # 不进菜单也要加入窗口，快捷键才能全局生效
        self._shortcut_acts[name] = act
        for g, items in self._shortcut_defs:
            if g == group:
                items.append((name, seq))
                break
        else:
            self._shortcut_defs.append((group, [(name, seq)]))
        return act

    def shortcut_groups(self):
        """给快捷键设置对话框：[(分组, [动作名, ...]), ...]"""
        return [(g, [n for n, _ in items]) for g, items in self._shortcut_defs]

    def all_shortcuts(self):
        """给快捷键设置对话框：[(动作名, 默认快捷键), ...]（无默认为 None）"""
        out = []
        for _g, items in self._shortcut_defs:
            out.extend(items)
        return out

    def apply_shortcut(self, name, seq):
        """应用并持久化某个动作的快捷键（seq 为空序列表示清除）。"""
        act = self._shortcut_acts.get(name)
        if act is None:
            return
        act.setShortcut(seq)
        if isinstance(seq, QKeySequence) and not seq.isEmpty():
            self._settings.setValue(f"shortcut/{name}",
                                    seq.toString(QKeySequence.PortableText))
        else:
            self._settings.remove(f"shortcut/{name}")

    def show_shortcut_settings(self):
        if not hasattr(self, "_sc_dlg"):
            self._sc_dlg = ShortcutDialog(self)
        self._sc_dlg.show()
        self._sc_dlg.raise_()

    # ================= JS bridge =================
    def _js_view(self, view, code, callback=None):
        if callback is None:
            view.page().runJavaScript(code)
        else:
            view.page().runJavaScript(code, callback)

    def _active_role(self):
        return "src" if self._dual else "edit"

    def _active_view(self):
        return self._view_src if self._dual else self._view

    def _js_active(self, code, callback=None):
        self._js_view(self._active_view(), code, callback)

    def _doc_dir(self):
        """当前文档所在目录（绝对路径）；未保存文档返回空串。"""
        if self.file_path:
            return os.path.dirname(os.path.abspath(self.file_path))
        return ""

    def _push_doc_dir(self):
        """文档目录 / 图片模式变化后同步到全部视图（切换文档、另存为后调用）。

        只推给已加载完成的视图：页面尚未注入 editor.html 时调用会报
        “window.setDocDir is not a function”，加载完成后 _on_loaded 会自行补齐。
        """
        code_dir = js(self._doc_dir())
        code_mode = js(self._image_mode)
        for role, v in (("edit", self._view), ("src", self._view_src), ("prev", self._view_prev)):
            if v is not None and self._vstate.get(role, {}).get("loaded"):
                self._js_view(v, f"window.setDocDir({code_dir})")
                self._js_view(v, f"window.setImageMode({code_mode})")

    def _page_action(self, name):
        """对活动视图的渲染页面执行剪切 / 复制 / 粘贴 / 全选。"""
        self._active_view().page().triggerAction(name)

    def _fmt(self, cmd):
        """把格式命令派发到当前编辑视图。"""
        self._js_active(f'window.cmd("{cmd}")')

    def _on_loaded(self, ok, role):
        if not ok:
            return
        st = self._vstate[role]
        st["loaded"] = True
        view = {"edit": self._view, "src": self._view_src, "prev": self._view_prev}[role]
        text = st["pending"] if st["pending"] is not None else ""
        # 图片相对路径解析依赖文档目录与图片模式，必须在 setMarkdown 之前下发
        self._js_view(view, f"window.setDocDir({js(self._doc_dir())})")
        self._js_view(view, f"window.setImageMode({js(self._image_mode)})")
        self._js_view(view, f"window.setMarkdown({js(text)})")
        if st["src"]:
            self._js_view(view, "window.setSourceMode(true)")
        if st["preview"]:
            self._js_view(view, "window.setPreviewMode(true)")
            self._js_view(view, f"window.setPreviewContent({js(text)})")
        st["pending"] = ""
        # 主题 / 缩放 / 写作辅助随视图加载同步（含惰性创建的分屏视图）
        self._js_view(view, f"window.setTheme({js(self._theme)})")
        view.setZoomFactor(self._zoom)
        self._js_view(view,
                      f"window.setMode({{typewriter: {str(bool(getattr(self, '_typewriter', False))).lower()}, "
                      f"focus: {str(bool(getattr(self, '_focus', False))).lower()}, "
                      f"autoPair: {str(bool(getattr(self, '_auto_pair', True))).lower()}, "
                      f"emoji: {str(bool(getattr(self, '_emoji', True))).lower()}}})")
        self._js_view(view, f"window.setDefaultCodeLang({js(self._code_lang)})")
        self._js_view(view, f"window.setCodePrefs({{lnum: {str(self._code_lnum).lower()}, "
                            f"style: {js(self._code_style)}}})")
        # v3.30.19（MMD-7）：全局图表主题随视图加载同步（空 = 跟随界面主题）
        self._js_view(view, f"window.setMmdTheme({js(self._settings.value('mmdTheme', '') or '')})")
        # v3.31.2（#8/#9）：段首缩进 / 标题 1 居中随视图加载下发
        self._js_view(view, f"window.setParaIndent({int(getattr(self, '_para_indent', 0))})")
        self._js_view(view,
                      f"window.setH1Center({str(bool(getattr(self, '_h1_center', False))).lower()})")
        self._js_view(view, f"window.setSlashMenuConfig({js(json.dumps(self._slash_cfg()))})")
        self._install_drop_filter()

    def _push_text(self, text):
        """把文本推送到当前模式的编辑视图（含双栏两侧）。"""
        if self._dual:
            st = self._vstate["src"]
            if st["loaded"]:
                self._js_view(self._view_src, f"window.setMarkdown({js(text)})")
                self._js_view(self._view_src, "window.setSourceMode(true)")
            else:
                st["pending"] = text
            stp = self._vstate["prev"]
            if stp["loaded"]:
                self._js_view(self._view_prev, "window.setPreviewMode(true)")
                self._js_view(self._view_prev, f"window.setPreviewContent({js(text)})")
            else:
                stp["pending"] = text
        else:
            st = self._vstate["edit"]
            if st["loaded"]:
                self._js_view(self._view, f"window.setMarkdown({js(text)})")
            else:
                st["pending"] = text

    # ================= 轮询同步 =================
    def show_status(self, msg, timeout_ms=3000):
        """v3.29d（B3）：临时提示走状态栏右侧独立区域，超时自动还原；
        「已保存 / 自动保存 / 已打开」等常驻信息仍走左侧 _status，二者互不覆盖。"""
        self._toast.setText(str(msg or ""))
        self._toast_timer.start(timeout_ms)

    def _poll(self):
        if self._cur < 0:
            return
        self._js_active("window.collect ? window.collect() : null", self._on_collect)
        self._js_active("window.getCaretLineCol ? window.getCaretLineCol() : null",
                        self._on_caret)
        # v3.29d（S2/C1）：取走编辑器侧的轻量提示（删除可撤销 / 模式提示等）
        self._js_active("window.takeToast ? window.takeToast() : null", self._on_toast)

    def _on_toast(self, res):
        msg = res if isinstance(res, str) else None
        if msg:
            self.show_status(msg)

    def _on_caret(self, res):
        try:
            data = json.loads(res) if isinstance(res, str) else res
        except (TypeError, ValueError):
            return
        if isinstance(data, dict) and data.get("line"):
            self._pos.setText(f"行 {int(data['line'])} · 列 {int(data.get('col', 1))}")
            # v3.30.10（HP-1）：当前块类型（标题 N / 表格 / 图表 / 公式 / 引用…）
            self._blktype.setText(data.get("type") or "")
        elif isinstance(data, dict) and data.get("imgsel"):
            # v3.30.17：选中图片 → 状态栏显示存储方式 / 存储文件名；取消选中 → 清空
            self._blktype.setText(data.get("type") or "")

    def _poll_sync_scroll(self):
        """v3.29 双栏同步滚动：源码视图滚动位置 / 光标段落 → 预览视图。

        非双栏直接返回；两侧页面都加载完成后才发查询，避免 JS 未注入报错。"""
        if not self._dual or self._view_src is None or self._view_prev is None:
            return
        st = self._vstate.get("src", {})
        stp = self._vstate.get("prev", {})
        if not (st.get("loaded") and stp.get("loaded")):
            return
        self._js_view(self._view_src,
                      "window.pollSrcScroll ? window.pollSrcScroll() : null",
                      self._on_src_scroll)

    def _on_src_scroll(self, res):
        try:
            data = json.loads(res) if isinstance(res, str) else res
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict) or data.get("idx") is None:
            return
        # 光标在源码视口内可见 → 预览优先定位到光标所在段落（编辑跟随）
        if data.get("cv") and data.get("cidx") is not None:
            idx, frac = data["cidx"], data.get("cfrac", 0)
        else:  # 否则按两侧滚动位置映射（滚动跟随）
            idx, frac = data["idx"], data.get("frac", 0)
        try:
            idx = int(idx)
            frac = max(0.0, min(1.0, float(frac)))
        except (TypeError, ValueError):
            return
        self._js_view(self._view_prev, f"window.scrollPreviewToBlock({idx},{frac})")

    def goto_line(self):
        n, ok = QInputDialog.getInt(self, "转到行", "行号：", 1, 1, 1_000_000)
        if ok:
            self._js_active(f"window.gotoLine({n})")

    def _show_stats_detail(self):
        """状态栏点击 → 字数 / 字符 / 段落 / 阅读时长详情。"""
        s = self._stats or {}
        if not s:
            QMessageBox.information(self, "统计", "暂无统计数据。")
            return
        g = lambda k: int(s.get(k, 0) or 0)  # noqa: E731
        QMessageBox.information(
            self, "统计详情",
            f"<b>字数</b>：{g('chars'):,}"
            f"　<span style='color:#888;'>（中文字符 {g('cjk'):,} ＋ 英文单词 {g('words'):,}）</span><br>"
            f"<b>字符数</b>（不含空白）：{g('raw'):,}<br>"
            f"<b>数字</b>：{g('digits'):,}　<b>标点</b>：{g('punct'):,}<br>"
            f"<b>段落</b>：{g('paragraphs'):,}　<b>行数</b>：{g('lines'):,}<br>"
            f"<b>阅读时长</b>：约 {g('readMin')} 分钟"
            "<br><br><span style='color:#888;'>统计口径：中文按字计、英文按词计；"
            "代码块不计入字数。</span>")

    # ================= P1-3 命令面板 =================
    def copy_as_html(self):
        """v3.29d（UX #34）：把整篇文档导出为带格式 HTML 并复制进剪贴板，
        粘贴到微信 / Word / 邮件时保留标题、加粗、表格等格式。"""
        def cb(html):
            if not html:
                return
            md = QMimeData()
            md.setHtml(html)
            md.setText(html)
            QApplication.clipboard().setMimeData(md)
            self.show_status("已复制为 HTML · 粘贴到微信 / Word 可保留格式")
        self._js_active("window.getExportHTML()", cb)

    def extra_commands(self):
        """命令面板里的补充命令（不在菜单 / 快捷键体系中的编辑器命令）。"""
        def js_cmd(code, tip):
            return lambda: self._js_active(code)

        def theme_cmd(tid):
            return lambda: self.apply_theme(tid)

        rows = [
            {"group": "视图", "name": "折叠全部标题", "seq": "Ctrl+Shift+[",
             "enabled": True, "run": lambda: self.fold_all_headings(True)},
            {"group": "视图", "name": "展开全部标题", "seq": "Ctrl+Shift+]",
             "enabled": True, "run": lambda: self.fold_all_headings(False)},
            {"group": "编辑", "name": "插入脚注引用", "seq": "",
             "enabled": True, "run": js_cmd('window.cmd && window.cmd("footnote")', "脚注")},
            {"group": "编辑", "name": "插入定义列表", "seq": "",
             "enabled": True, "run": js_cmd('window.cmd && window.cmd("deflist")', "定义列表")},
            {"group": "文件", "name": "历史版本", "seq": "Ctrl+Shift+H",
             "enabled": True, "run": self.show_history},
        ]
        for t in styles.THEMES:
            rows.append({"group": "外观", "name": f"切换主题：{t['label']}", "seq": "",
                         "enabled": True, "run": theme_cmd(t["id"])})
        for m_id, _icon, label, _desc in MODES:
            rows.append({"group": "视图", "name": f"切换到{label}", "seq": "",
                         "enabled": True, "run": (lambda m=m_id: self._set_mode(m))})
        return rows

    def show_command_palette(self):
        """打开命令面板（Ctrl+Shift+P）。v3.25：面板停靠在菜单栏下方顶端。"""
        if not hasattr(self, "_cmd_dlg"):
            self._cmd_dlg = CommandPaletteDialog(self)
        dlg = self._cmd_dlg
        dlg._apply_theme_qss(self._theme)
        dlg.show()
        # v3.25：show 后显式停靠到菜单栏下方居中（Qt 默认会把对话框居中覆盖掉 showEvent 里的定位）
        geo = self.geometry()
        menu_h = self.menuBar().height() if self.menuBar() else 0
        dlg.move(geo.x() + max(8, (geo.width() - dlg.width()) // 2), geo.y() + menu_h + 10)
        dlg.raise_()
        dlg.activateWindow()

    # ================= P1-6 版本历史 =================
    def _history_dir(self, path):
        """历史快照目录：<文档目录>/.mdeditor-history/<文档名>/"""
        if not path:
            return ""
        base = os.path.splitext(os.path.basename(os.path.abspath(path)))[0] or "untitled"
        return os.path.join(os.path.dirname(os.path.abspath(path)),
                            ".mdeditor-history", base)

    def list_history(self, path):
        """返回 [(快照文件, mtime)]，按时间倒序。"""
        d = self._history_dir(path)
        if not d or not os.path.isdir(d):
            return []
        out = []
        for name in os.listdir(d):
            if not name.lower().endswith(".md"):
                continue
            fp = os.path.join(d, name)
            try:
                out.append((fp, os.path.getmtime(fp)))
            except OSError:
                continue
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    def snapshot_history(self, path, text):
        """保存前把上一版内容留档（内容与磁盘一致时跳过，避免无意义快照）。"""
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                old = f.read()
        except OSError:
            return None
        if text is not None and old == text:
            return None
        d = self._history_dir(path)
        if not d:
            return None
        try:
            os.makedirs(d, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            fp = os.path.join(d, f"{stamp}.md")
            n = 1
            while os.path.exists(fp):
                fp = os.path.join(d, f"{stamp}-{n}.md")
                n += 1
            with open(fp, "w", encoding="utf-8") as f:
                f.write(old)
        except OSError:
            return None
        # 只保留最近 N 份
        items = self.list_history(path)
        for fp_old, _mt in items[self._history_keep:]:
            try:
                os.remove(fp_old)
            except OSError:
                pass
        return fp

    def show_history(self):
        """打开历史版本对话框（文件菜单 / Ctrl+Shift+H）。"""
        if not hasattr(self, "_hist_dlg"):
            self._hist_dlg = HistoryDialog(self)
        self._hist_dlg._apply_theme_qss(self._theme)
        self._hist_dlg.show_for(self.file_path)

    def restore_history(self, snap_path, mtime=None):
        """把某个历史快照内容恢复到当前编辑区（未保存状态）。"""
        try:
            with open(snap_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            QMessageBox.critical(self, "恢复失败", str(e))
            return
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)) if mtime else "历史版本"
        if QMessageBox.question(
                self, "恢复历史版本",
                f"确定用 {when} 的内容替换当前编辑区吗？\n\n"
                "（当前内容不会被删除：恢复后处于未保存状态，可撤销 / 不保存直接关闭）",
                QMessageBox.Ok | QMessageBox.Cancel) != QMessageBox.Ok:
            return
        self._push_text(text)
        self._dirty = True
        self._update_title()
        self.show_status(f"已恢复历史版本（{when}）· 按 Ctrl+S 保存")

    # ================= 侧栏文件管理支撑（回收站删除 / 重命名同步） =================
    def recycle_path(self, path):
        """把文件 / 文件夹移入回收站（SHFileOperationW，FOF_ALLOWUNDO）。"""
        import ctypes
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return False

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
                        ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                        ("fFlags", ctypes.c_ushort),
                        ("fAnyOperationsAborted", ctypes.c_int),
                        ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", ctypes.c_wchar_p)]

        op = SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = 3                    # FO_DELETE
        op.pFrom = path + "\0"
        op.pTo = None
        op.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400  # ALLOWUNDO|NOCONFIRMATION|SILENT|NOERRORUI
        try:
            rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        except (OSError, AttributeError):
            return False
        return rc == 0 and not op.fAnyOperationsAborted

    def rename_current_file(self, old, new):
        """侧栏把当前打开的文件改名后同步内部状态（保存路径 / 标签 / 标题）。"""
        if old and self.file_path and \
                os.path.abspath(self.file_path) == os.path.abspath(old):
            self.file_path = new
            if 0 <= self._cur < len(self._docs):
                self._docs[self._cur]["path"] = new
            self._refresh_tab_texts()
            self._update_title()

    # ================= v3.31（#7）大纲拖拽调序 =================
    def reorder_sections(self, pairs):
        """把同级章节的新顺序（[start, end) 块区间列表）发给内核整段重排。"""
        try:
            payload = json.dumps(pairs)
        except (TypeError, ValueError):
            return
        self._js_active(f"window.reorderSections({js(payload)})")
        self.show_status("已调整章节顺序")

    # ================= P1-7 外部打开 =================
    def show_in_explorer(self, path=None):
        """在资源管理器中定位当前文档（无文档时打开所在目录）。"""
        target = path or self.file_path
        if not target:
            QMessageBox.information(self, "在资源管理器中显示", "当前文档尚未保存到文件。")
            return
        target = os.path.abspath(target)
        try:
            if os.path.exists(target):
                subprocess.Popen(["explorer", "/select,", target])
            else:
                d = os.path.dirname(target)
                subprocess.Popen(["explorer", d if d else "."])
        except OSError as e:
            QMessageBox.critical(self, "打开失败", str(e))

    def open_external(self, path=None):
        """用系统默认程序打开指定文件（缺省 = 当前文档；
        可用系统设置里的外部编辑器路径覆盖）。v3.25：支持侧栏文件列表右键调用。"""
        target = path or self.file_path
        if not target:
            QMessageBox.information(self, "用外部程序打开", "当前文档尚未保存到文件。")
            return
        target = os.path.abspath(target)
        if not os.path.exists(target):
            QMessageBox.information(self, "用外部程序打开", f"文件不存在：{target}")
            return
        cmd = str(getattr(self, "_external_editor", "") or "").strip()
        try:
            if cmd:
                subprocess.Popen([cmd, target])
            else:
                os.startfile(target)     # noqa: S606 — Windows 默认关联程序
            self.show_status(f"已用外部程序打开 · {target}")
        except OSError as e:
            QMessageBox.critical(self, "打开失败", str(e))

    # ================= P1-2 折叠 =================
    def fold_all_headings(self, close):
        """折叠 / 展开全部标题（视图菜单、命令面板）。"""
        self._js_active(
            f"window.foldAllHeadings ? window.foldAllHeadings({str(bool(close)).lower()}) : 0",
            lambda n: self.show_status(
                ("已折叠 " if close else "已展开 ") + f"{int(n or 0)} 个标题"))

    # ================= P1-1 / P1-8 输入增强 =================
    def set_auto_pair(self, on):
        """自动配对括号 / 引号开关。"""
        self._auto_pair = bool(on)
        self._settings.setValue("autoPair", bool(on))
        self._js_active(f"window.setMode({{autoPair: {str(bool(on)).lower()}}})")
        self.show_status("自动配对：开" if on else "自动配对：关")

    def set_emoji_complete(self, on):
        """Emoji 短代码自动补全开关。"""
        self._emoji = bool(on)
        self._settings.setValue("emojiComplete", bool(on))
        self._js_active(f"window.setMode({{emoji: {str(bool(on)).lower()}}})")
        self.show_status("Emoji 补全：开" if on else "Emoji 补全：关")

    def set_history_keep(self, n):
        """历史版本保留份数（1~200，系统设置→编辑器）。"""
        try:
            n = max(1, min(200, int(n)))
        except (TypeError, ValueError):
            return
        self._history_keep = n
        self._settings.setValue("historyKeep", n)
        self.show_status(f"历史版本保留 {n} 份")

    def set_external_editor(self, path):
        """外部编辑器可执行文件路径（留空 = 系统默认关联程序，系统设置→通用）。"""
        self._external_editor = str(path or "").strip()
        self._settings.setValue("externalEditor", self._external_editor)
        self.show_status("外部编辑器：" + (self._external_editor or "系统默认程序"))

    # ================= 跨文件搜索 =================
    def show_search(self):
        """打开「查找」对话框的「全局搜索」页签（Ctrl+Shift+F / 编辑菜单）。

        v3.24：全局搜索不再单独占用工具栏按钮 / 侧栏面板，与查找整合为一个对话框，
        「查找」「全局搜索」各占一个页签，可随时切换。"""
        self.show_find(False)
        self._find_dlg.show_global()

    def search_root(self):
        """搜索根目录：当前文档所在目录 → 侧栏当前目录 → 用户主目录。"""
        if self.file_path:
            return os.path.dirname(os.path.abspath(self.file_path))
        cur = getattr(self._sidebar, "_cur_dir", None)
        if cur and os.path.isdir(cur):
            return cur
        return os.path.expanduser("~")

    def open_file_at(self, path, line):
        """打开文件并跳转到指定行（搜索结果点击）。"""
        if not path or not os.path.exists(path):
            self.show_status(f"文件不存在：{path}")
            return
        self._pending_goto = (os.path.abspath(path), max(1, int(line)))
        self._pending_tries = 0
        self.open_file(path)
        QTimer.singleShot(500, self._flush_pending_goto)

    def _flush_pending_goto(self):
        """等待文档真正加载进视图后再跳行（跨标签 / 首次打开都要等）。"""
        pg = self._pending_goto
        if not pg:
            return
        path, line = pg
        loaded = (self.file_path and os.path.abspath(self.file_path) == path
                  and self._vstate[self._active_role()]["loaded"])
        if loaded:
            self._pending_goto = None
            self._js_active(f"window.gotoLine({line})")
            self.show_status(f"已跳转到 {os.path.basename(path)} 第 {line} 行")
            return
        self._pending_tries += 1
        if self._pending_tries < 12:
            QTimer.singleShot(300, self._flush_pending_goto)
        else:
            self._pending_goto = None

    # ================= 图片插入（落盘相对路径 / 内嵌 data URL 双模式） =================
    def _pick_local_image(self):
        """斜杠菜单 / 编辑器「图片」→ v3.27 唯一插入面板（不再有编辑器内第二层弹窗）。

        「本地相对路径存储」勾选框默认跟随系统设置预勾选，用户可在面板内改；
        存储名称插入后单击图片「修改存储文件名」指定。
        面板里输入 http(s) 地址则按网络图片直接插入。"""
        dlg = InsertImageDialog(self)
        if not dlg.exec():
            return
        src = dlg.src_path()
        if not src:
            return
        if dlg.is_url():
            name = dlg._cur_stem() or "图片"
            self._js_active(f"window.insertImageMarkdown({js(src)}, {js(name)})")
            self.show_status(f"已插入网络图片 · {src[:60]}")
            return
        self._insert_image_file(src, mode=dlg.mode())

    def _numbered_asset_name(self, name, ext):
        """v3.25：默认存储名 = 「assets 现有文件数 + 1」5 位编号 _ 名称。
        （00011_我的图片.png —— 编号自动生成，重名再由 _unique_name 兜底）"""
        assets = self._assets_dir_for(self.file_path) if self.file_path else None
        count = 0
        if assets and os.path.isdir(assets):
            count = len([n for n in os.listdir(assets)
                         if os.path.isfile(os.path.join(assets, n))])
        stem = os.path.splitext(name)[0] or name      # 名称里带了扩展名则剥掉
        return f"{count + 1:05d}_{stem}{ext or '.png'}"

    def _insert_image_file(self, path, mode=None, name=None):
        """插入本地图片：assets 模式落盘为相对路径，embed 模式内嵌 data URL。

        v3.25：mode / name 来自插入对话框（缺省取系统设置里的图片存放方式）。"""
        name = name or os.path.splitext(os.path.basename(path))[0] or "图片"
        mode = mode or self._image_mode
        rel = None
        if mode == "assets":
            fname = self._numbered_asset_name(name, os.path.splitext(path)[1].lower())
            try:
                rel = self._save_image_to_assets(path, filename=fname)
            except OSError as e:
                self.show_status(f"图片落盘失败，已改为内嵌：{e}")
                rel = None
            else:
                if rel is None:
                    self._status_prefer_assets()
        if rel:
            self._js_active(f"window.insertImageMarkdown({js(rel)}, {js(name)})")
            self.show_status(f"已插入图片（相对路径）· {rel}")
            return
        try:
            ext = os.path.splitext(path)[1].lower()
            mime = IMG_MIME.get(ext, "image/png")
            with open(path, "rb") as f:
                raw = f.read()
            # v3.29d（B8/UX #35）：内嵌超过 1MB 的大图给出提示（建议相对路径存储）
            if len(raw) > 1024 * 1024:
                self.show_status(
                    f"提示：内嵌图片 {os.path.basename(path)} 约 {len(raw) // 1024 // 1024 + 1} MB，"
                    "可能拖慢文档加载；建议改用相对路径（assets）存储", 6000)
            b64 = base64.b64encode(raw).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"
            self._js_active(f"window.insertImageMarkdown({js(data_url)}, {js(name)})")
            self.show_status(f"已插入图片（内嵌）· {os.path.basename(path)}")
        except OSError as e:
            self.show_status(f"插入图片失败：{e}")

    def _status_prefer_assets(self):
        self.show_status("当前文档尚未保存，图片已改为内嵌；保存后插入的图片会自动落到 assets 目录")

    # ---- 落盘：<文档名>.assets/ 目录 ----
    @staticmethod
    def _assets_dir_for(doc_path):
        """图片资源目录：与文档同级的「<文档名>.assets/」（Typora 风格）。"""
        base = os.path.splitext(os.path.basename(doc_path))[0] or "文档"
        return os.path.join(os.path.dirname(os.path.abspath(doc_path)), base + ".assets")

    @staticmethod
    def _unique_name(directory, filename):
        """重名自动追加 -1、-2 …（与 Typora 行为一致）。"""
        stem, ext = os.path.splitext(filename)
        cand, k = filename, 1
        while os.path.exists(os.path.join(directory, cand)):
            cand = f"{stem}-{k}{ext}"
            k += 1
        return cand

    def _save_image_to_assets(self, src_path=None, data=None, filename=None):
        """把图片写入「<文档名>.assets/」，返回写进 Markdown 的相对路径（正斜杠）。

        未保存文档（无路径）时返回 None，由调用方回退为内嵌 data URL。
        """
        if not self.file_path:
            return None
        assets = self._assets_dir_for(self.file_path)
        fname = filename or os.path.basename(src_path)
        # 源文件已在目标目录内：直接复用，避免复制出 -1 副本
        if src_path:
            try:
                if os.path.normcase(os.path.dirname(os.path.abspath(src_path))) == \
                        os.path.normcase(assets):
                    return f"{os.path.basename(assets)}/{os.path.basename(src_path)}"
            except (OSError, ValueError):
                pass
        os.makedirs(assets, exist_ok=True)
        dest_name = self._unique_name(assets, fname)
        dest = os.path.join(assets, dest_name)
        if data is not None:
            with open(dest, "wb") as f:
                f.write(data)
        else:
            shutil.copy2(src_path, dest)
        return f"{os.path.basename(assets)}/{dest_name}"

    def _handle_pasted_image(self, info):
        """剪贴板 / 截图粘贴的图片：assets 模式落盘，否则内嵌。"""
        if not isinstance(info, dict):
            return
        url = str(info.get("url") or "")
        name = str(info.get("name") or "粘贴图片")
        if not url.startswith("data:"):
            return
        rel = None
        if self._image_mode == "assets":
            m = re.match(r"data:([^;,]+);base64,(.*)$", url, re.S)
            if m:
                ext = MIME_EXT.get(m.group(1).lower(), ".png")
                stem = os.path.splitext(name)[0] or "图片"
                try:
                    rel = self._save_image_to_assets(
                        data=base64.b64decode(m.group(2)), filename=stem + ext)
                except (OSError, ValueError, binascii.Error):
                    rel = None
                if rel is None and not self.file_path:
                    self._status_prefer_assets()
        if rel:
            self._js_active(f"window.insertImageMarkdown({js(rel)}, {js(name)})")
            self.show_status(f"已粘贴图片（相对路径）· {rel}")
        else:
            # v3.29d（B8）：大图内嵌提示（粘贴网络图 / 未保存文档回退内嵌时）
            m2 = re.match(r"^data:image/[^;]+;base64,", url or "")
            if m2 and len(url) > 1024 * 1365:   # base64 后约 >1MB 原始数据
                self.show_status("提示：粘贴的内嵌图片超过 1MB，可能拖慢文档加载；"
                                 "建议保存文档后改用相对路径（assets）存储", 6000)
            self._js_active(f"window.insertImageMarkdown({js(url)}, {js(name)})")
            self.show_status("已粘贴图片（内嵌 data URL）")

    def set_image_mode(self, mode):
        """设置图片存放方式：assets=落盘相对路径（推荐）/ embed=内嵌 data URL。"""
        mode = "embed" if str(mode) == "embed" else "assets"
        self._image_mode = mode
        self._settings.setValue("imageMode", mode)
        self._push_doc_dir()
        self.show_status("图片存放方式：" + (
            "相对路径（保存到「文档名.assets」文件夹）" if mode == "assets"
            else "内嵌 data URL（图片写入文档本身）"))

    # ---- v3.25 图片存储操作：重命名 / 内嵌 ↔ 相对路径（编辑器悬浮按钮发起） ----
    def _handle_img_req(self, req):
        """处理编辑器 collect 轮询带出的图片操作请求，完成后回调 imgReqDone。"""
        if not isinstance(req, dict):
            return
        act = str(req.get("act") or "")
        idx = req.get("idx")
        src = str(req.get("src") or "")
        if act == "imgRename":
            self._img_rename(idx, src, str(req.get("name") or "").strip())
        elif act == "imgToEmbed":
            self._img_to_embed(idx, src)
        elif act == "imgToAssets":
            self._img_to_assets(idx, src)
        elif act == "imgCopy":
            self._img_copy(idx, src)

    def _img_bytes(self, src):
        """v3.30.16：把图片块的 src 取成字节（本地文件 / data URL / 网络图）。"""
        m = re.match(r"^data:([^;,]+);base64,(.*)$", src, re.S)
        if m:
            try:
                return base64.b64decode(m.group(2))
            except (ValueError, binascii.Error):
                return None
        if re.match(r"^https?:", src, re.I):
            try:
                import urllib.request
                with urllib.request.urlopen(src, timeout=15) as resp:
                    return resp.read()
            except Exception:      # noqa: BLE001
                return None
        fp = self._img_local_path(src)
        if not fp or not os.path.isfile(fp):
            return None
        try:
            with open(fp, "rb") as f:
                return f.read()
        except OSError:
            return None

    def _img_copy(self, idx, src):
        """v3.30.16：右键「复制图片」—— 以位图形式写入系统剪贴板，
        可直接粘贴到微信 / Word / 画图等。不改文档、不入撤销历史。"""
        data = self._img_bytes(src)
        if not data:
            self.show_status("复制图片失败：取不到图片数据（本地文件缺失 / 网络图下载失败）")
            return
        img = QImage()
        if not img.loadFromData(data):
            self.show_status("复制图片失败：无法识别的图片格式")
            return
        QGuiApplication.clipboard().setImage(img)
        self.show_status(f"图片已复制到剪贴板（{img.width()}×{img.height()}）")

    def _img_local_path(self, src):
        """把图片块的 src 解析成本地文件绝对路径；非本地文件返回 None。"""
        if not src or re.match(r"^(data:|https?:)", src, re.I):
            return None
        if re.match(r"^[A-Za-z]:[\\/]", src):
            return os.path.normpath(src)
        if not self.file_path:
            return None
        rel = src.replace("\\", "/").lstrip("/")
        try:
            rel = urllib.parse.unquote(rel)
        except Exception:      # noqa: BLE001
            pass
        return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(self.file_path)), rel))

    def _img_ask_name(self, title, default_stem):
        """弹框让用户指定存储名称（默认带 5 位自动编号前缀，可连编号一起改）。"""
        fname = self._numbered_asset_name(default_stem, "")   # 借用编号逻辑（不带扩展名）
        text, ok = QInputDialog.getText(self, title, "存储名称（含编号前缀，可修改）：", text=fname)
        if not ok or not text.strip():
            return None
        text = text.strip()
        if not re.match(r'^[^\\/:*?"<>|]+$', text):
            QMessageBox.information(self, title, "名称包含非法字符（不能含 \\ / : * ? \" < > |）。")
            return None
        return text

    def _img_rename(self, idx, src, name):
        """重命名 assets 里的图片文件（连编号一起改），并更新 Markdown 里的路径。"""
        if not name:
            return
        old = self._img_local_path(src)
        if not old or not os.path.isfile(old):
            self.show_status("重命名失败：只支持本地 assets 中的图片（内嵌 / 网络图片无文件名）")
            return
        directory = os.path.dirname(old)
        ext = os.path.splitext(old)[1] or ".png"
        stem = name if os.path.splitext(name)[1] else name + ext
        if not os.path.splitext(stem)[1]:
            stem += ext
        new_name = self._unique_name(directory, stem)
        try:
            os.rename(old, os.path.join(directory, new_name))
        except OSError as e:
            self.show_status(f"重命名失败：{e}")
            return
        new_rel = f"{os.path.basename(directory)}/{new_name}"
        self._js_active(f"window.imgReqDone && window.imgReqDone({int(idx)}, {js(new_rel)})")
        self.show_status(f"图片已重命名 · {new_name}")

    def _img_to_embed(self, idx, src):
        """相对路径 → 内嵌：读文件转 data URL 写回（assets 文件保留不删）。"""
        fp = self._img_local_path(src)
        if not fp or not os.path.isfile(fp):
            self.show_status("转为内嵌失败：找不到图片文件")
            return
        ext = os.path.splitext(fp)[1].lower()
        mime = IMG_MIME.get(ext, "image/png")
        try:
            with open(fp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except OSError as e:
            self.show_status(f"转为内嵌失败：{e}")
            return
        data_url = f"data:{mime};base64,{b64}"
        self._js_active(f"window.imgReqDone && window.imgReqDone({int(idx)}, {js(data_url)})")
        self.show_status("图片已转为内嵌 data URL（原文件保留在 assets 目录）")

    def _img_to_assets(self, idx, src):
        """内嵌 data URL / 网络图片 / 本地文件 → 相对路径落盘（弹框指定名称）。"""
        data = None
        default_stem = "图片"
        m = re.match(r"^data:([^;,]+);base64,(.*)$", src, re.S)
        if m:
            ext = MIME_EXT.get(m.group(1).lower(), ".png")
            try:
                data = base64.b64decode(m.group(2))
            except (ValueError, binascii.Error):
                self.show_status("转为相对路径失败：内嵌数据解码错误")
                return
            default_stem = "图片" + ext
            name = self._img_ask_name("转为相对路径", os.path.splitext(default_stem)[0])
        elif re.match(r"^https?:", src, re.I):
            name = self._img_ask_name("下载网络图片", "图片")
            if name is None:
                return
            try:
                import urllib.request
                with urllib.request.urlopen(src, timeout=15) as resp:
                    raw = resp.read()
                ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                ext = MIME_EXT.get(ctype, ".png")
                data = raw
            except Exception as e:      # noqa: BLE001 — 网络 / 超时 / 解码错误统一提示
                self.show_status(f"网络图片下载失败，已保持原样：{e}")
                return
        else:
            fp = self._img_local_path(src)
            if not fp or not os.path.isfile(fp):
                self.show_status("转为相对路径失败：找不到图片文件")
                return
            default_stem = os.path.splitext(os.path.basename(fp))[0] or "图片"
            name = self._img_ask_name("转为相对路径", default_stem)
            if name is None:
                return
            try:
                with open(fp, "rb") as f:
                    data = f.read()
                ext = os.path.splitext(fp)[1].lower() or ".png"
            except OSError as e:
                self.show_status(f"转为相对路径失败：{e}")
                return
        if name is None:
            return
        if not self.file_path:
            self.show_status("请先把文档保存到文件，再转为相对路径（需要确定 assets 目录）")
            return
        uext = os.path.splitext(name)[1].lower()
        if uext:                        # 用户在名称里自带了扩展名
            ext, stem = uext, os.path.splitext(name)[0]
        else:
            stem = name
        fname = self._numbered_asset_name(stem, ext or ".png")
        try:
            rel = self._save_image_to_assets(data=data, filename=fname)
        except OSError as e:
            self.show_status(f"图片落盘失败：{e}")
            return
        if not rel:
            self.show_status("请先把文档保存到文件，再转为相对路径")
            return
        self._js_active(f"window.imgReqDone && window.imgReqDone({int(idx)}, {js(rel)})")
        self.show_status(f"图片已转为相对路径 · {rel}")

    # ---- 迁移：把文档里已有的内嵌图片抽出成文件 ----
    def migrate_embedded_images(self):
        """把当前文档中内嵌的 data URL 图片写入 assets 目录并替换为相对路径。"""
        if not self.file_path:
            QMessageBox.information(
                self, "迁移内嵌图片",
                "请先把文档保存到文件，再执行迁移（需要据此确定 assets 目录位置）。")
            return

        def cb(md):
            if not md:
                return
            new_md, count, failed = self._extract_embedded_images(md)
            if count == 0:
                QMessageBox.information(self, "迁移内嵌图片",
                                        "本文档没有内嵌的 data URL 图片，无需迁移。")
                return
            assets = os.path.basename(self._assets_dir_for(self.file_path))
            btn = QMessageBox.question(
                self, "迁移内嵌图片",
                f"检测到 {count} 张内嵌图片。\n\n"
                f"将把它们写入 「{assets}」文件夹，并把文档中的路径替换为相对路径，\n"
                f"文档体积会显著变小（相对路径图片也可被其它编辑器复用）。\n\n"
                f"是否继续？",
                QMessageBox.Ok | QMessageBox.Cancel)
            if btn != QMessageBox.Ok:
                return
            try:
                out = new_md if new_md.endswith("\n") else new_md + "\n"
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(out)
            except OSError as e:
                QMessageBox.critical(self, "迁移失败", str(e))
                return
            if 0 <= self._cur < len(self._docs):
                self._docs[self._cur]["content"] = out
            self._dirty = False
            self._js_active(f"window.setMarkdown({js(new_md)})")
            self._push_doc_dir()
            msg = f"已迁移 {count} 张内嵌图片到 {assets}"
            if failed:
                msg += f"（{failed} 张解码失败已保留原样）"
            self.show_status(msg + "，请按 Ctrl+S 确认保存")

        self._js_active("window.getMarkdown()", cb)

    def _extract_embedded_images(self, md):
        """把 md 中的 data URL 图片落盘，返回 (新文本, 成功数, 失败数)。"""
        ok = [0]
        bad = [0]

        def repl(m):
            alt, _url, subtype, b64 = m.group(1), m.group(2), m.group(3), m.group(4)
            ext = "." + subtype.lower().replace("jpeg", "jpg").replace("svg+xml", "svg")
            stem = (alt or "image").strip() or "image"
            stem = re.sub(r'[\\/:*?"<>|\s]+', "_", stem)[:40] or "image"
            try:
                raw = base64.b64decode(re.sub(r"\s+", "", b64))
                rel = self._save_image_to_assets(data=raw, filename=stem + ext)
            except (OSError, ValueError, binascii.Error):
                rel = None
            if not rel:
                bad[0] += 1
                return m.group(0)
            ok[0] += 1
            return f"![{alt}]({rel})"

        return IMG_DATA_RE.sub(repl, md), ok[0], bad[0]

    def _on_collect(self, res):
        if not res:
            return
        try:
            data = json.loads(res)
        except (TypeError, ValueError):
            return
        if data.get("stats"):
            s = data["stats"]
            self._stats = dict(s) if isinstance(s, dict) else {}
            n = int(self._stats.get("chars", 0) or 0)
            self._count.setText(f"字数 {n:,} · 约 {int(self._stats.get('readMin', 0) or 0)} 分钟")
        if data.get("img"):
            self._handle_pasted_image(data.get("img"))
        if data.get("req"):
            self._handle_img_req(data.get("req"))
        if data.get("outline") is not None:
            self._outline_cache = data.get("outline") or []
            self._sidebar.set_outline(data.get("outline"))
        if data.get("pick"):
            self._js_active("window.__wantPick = false")
            self._pick_local_image()
        md = data.get("md")
        dirty = bool(data.get("dirty"))
        self._dirty = dirty
        if self._autosave and 0 <= self._cur < len(self._docs):
            doc = self._docs[self._cur]
            if dirty and doc.get("path"):
                # 自动保存（保证文件以单个换行结尾）
                try:
                    out = md or ""
                    if out and not out.endswith("\n"):
                        out += "\n"
                    # v3.29d（B1）：写盘前先把上一版留档到版本历史 —— 此前自动保存
                    # 直接写盘，磁盘内容永远等于新内容，之后手动保存的快照被去重
                    # 跳过，默认配置下版本历史形同虚设。加 60 秒节流控制 IO 频率。
                    last = getattr(self, "_snap_ts", {})
                    now = time.time()
                    if now - last.get(doc["path"], 0) >= 60:
                        self.snapshot_history(doc["path"], out)
                        last[doc["path"]] = now
                        self._snap_ts = last
                    self._write_text(doc["path"], out)   # v3.29d（B2）：按原编码写盘
                    self.show_status(f"已自动保存 · {doc['path']}")
                except OSError as e:
                    self._status.setText(f"自动保存失败：{e}")
        # 双栏：同步到预览
        if self._dual and md is not None and md != self._last_preview_md:
            self._last_preview_md = md
            stp = self._vstate["prev"]
            if stp["loaded"]:
                self._js_view(self._view_prev, f"window.setPreviewContent({js(md)})")
        self._refresh_tab_texts()
        self._update_title()

    def _refresh_tab_texts(self):
        for i, doc in enumerate(self._docs):
            name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
            mark = " • " if (i == self._cur and self._dirty) else "  "
            self._tabbar.setTabText(i, f"{mark}{name}")

    def _update_title(self):
        name = os.path.basename(self.file_path) if self.file_path else "未命名"
        star = " •" if self._dirty else ""
        self.setWindowTitle(f"{name}{star} — {APP_NAME}")

    # ================= 多文档标签 =================
    def _add_doc(self, path=None, text=None):
        self._docs.append({"path": path, "content": text})
        idx = len(self._docs) - 1
        self._tabbar.addTab("未命名" if not path else os.path.basename(path))
        self._tabbar.setCurrentIndex(idx)  # 触发 _on_tab_clicked -> 激活
        return idx

    def _on_tab_clicked(self, idx):
        # 信号同时来自 addTab / setCurrentIndex / 用户点击
        if idx < 0 or idx >= len(self._docs):
            return
        if self._switching:
            return
        if idx == self._cur:
            return
        # 编辑视图尚未加载完成时无法取回内容，直接同步激活
        if not self._vstate[self._active_role()]["loaded"]:
            self._pending_switch = idx
            self._on_switch_capture(None)
            return
        # 切换前先把当前内容存入缓存
        self._pending_switch = idx
        self._switching = True
        self._js_active("window.getMarkdown()", self._on_switch_capture)

    def _on_switch_capture(self, md):
        if self._cur >= 0 and self._cur < len(self._docs) and md is not None:
            self._docs[self._cur]["content"] = md
        target = self._pending_switch
        self._switching = False
        if target < 0 or target >= len(self._docs):
            return
        self._cur = target
        doc = self._docs[target]
        self.file_path = doc.get("path")
        text = doc.get("content")
        if text is None:
            text = self._read_file(self.file_path) if self.file_path else ""
            doc["content"] = text
        self._last_preview_md = None
        self._push_doc_dir()   # 图片相对路径随文档目录变化（先于正文下发）
        self._push_text(text)
        self._dirty = False
        self._update_title()
        self._refresh_tab_texts()
        if self.file_path:
            self._sidebar.set_root(self.file_path)
            self._status.setText(f"已打开 · {self.file_path}")
        else:
            self.show_status("未命名文档")
        # 期间用户又点了其他标签 -> 继续处理最新请求
        if self._tabbar.currentIndex() != self._cur:
            QTimer.singleShot(0, lambda: self._on_tab_clicked(self._tabbar.currentIndex()))

    def _on_tab_moved(self, frm, to):
        doc = self._docs.pop(frm)
        self._docs.insert(to, doc)
        if self._cur == frm:
            self._cur = to
        elif frm < self._cur <= to:
            self._cur -= 1
        elif to <= self._cur < frm:
            self._cur += 1

    def _close_tab(self, idx):
        if idx < 0 or idx >= len(self._docs) or self._switching:
            return
        doc = self._docs[idx]

        def do_close(cached_md=None):
            if cached_md is not None:
                doc["content"] = cached_md
            # 未命名且非空 -> 提示保存
            if doc.get("path") is None and (doc.get("content") or "").strip():
                btn = QMessageBox.question(
                    self, "关闭未命名文档",
                    "该文档尚未保存到文件，关闭将丢失内容。是否保存？",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                if btn == QMessageBox.Cancel:
                    return
                if btn == QMessageBox.Save:
                    self._cur = idx
                    self.file_path = None
                    if not self.save_file_as():
                        return
                    doc["path"] = self.file_path
            self._docs.pop(idx)
            self._tabbar.removeTab(idx)
            if not self._docs:
                self._cur = -1
                self.file_path = None
                self._add_doc(path=None, text="")
                return
            if idx == self._cur:
                self._cur = -1
                new_idx = min(idx, len(self._docs) - 1)
                self._tabbar.setCurrentIndex(new_idx)
                self._on_tab_clicked(new_idx)
            else:
                if idx < self._cur:
                    self._cur -= 1
            self._refresh_tab_texts()
            self._update_title()

        if idx == self._cur:
            from PySide6.QtCore import QEventLoop
            loop_res = {}
            loop = QEventLoop()

            def cb(md):
                loop_res["md"] = md
                loop.quit()

            self._js_active("window.getMarkdown()", cb)
            loop.exec()
            do_close(loop_res.get("md"))
        else:
            do_close()

    # ================= 文件操作 =================
    @staticmethod
    def _detect_encoding(path):
        """v3.29d（B2）：探测文件编码（BOM / UTF-8 / GBK），供按原编码写回。"""
        try:
            with open(path, "rb") as f:
                raw = f.read(65536)
        except OSError:
            return "utf-8"
        if raw.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass
        try:
            raw.decode("gbk")
            return "gbk"
        except UnicodeDecodeError:
            return "utf-8"

    @staticmethod
    def _read_file(path):
        """读文件：BOM → UTF-8 → GBK 自动回退，避免中文乱码/打不开。"""
        with open(path, "rb") as f:
            raw = f.read()
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig", errors="replace")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            pass
        try:
            return raw.decode("gbk")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")

    def _write_text(self, path, text):
        """v3.29d（B2）：按打开时识别的原编码写盘 —— GBK 文件保存后仍是 GBK、
        带 BOM 的 UTF-8 保留 BOM，不再一律静默转码成 UTF-8（导出文件除外）。"""
        enc = getattr(self, "_enc_map", {}).get(path, "utf-8")
        if enc not in ("utf-8", "utf-8-sig", "gbk"):
            enc = "utf-8"
        with open(path, "w", encoding=enc) as f:
            f.write(text)

    def new_file(self):
        self._add_doc(path=None, text="")

    def open_folder(self):
        """打开文件夹：左侧文件栏定位并显示该文件夹的一级内容。"""
        d = QFileDialog.getExistingDirectory(self, "打开文件夹", "")
        if not d:
            return
        self._sidebar.setVisible(True)
        self._update_side_btn()
        self._sidebar.select_tab(Sidebar.TAB_FILES)
        self._sidebar.set_root(d)
        self.show_status(f"已打开文件夹：{d}")

    def open_file(self, path=None):
        # QAction.triggered 会把 checked(bool) 作为第一个参数传入，
        # 必须把非字符串的 path 归一化为 None，否则打开对话框永远不会弹出
        if not isinstance(path, str) or not path:
            path = None
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "打开 Markdown 文件", self._dlg_dir("open"),
                "Markdown 文件 (*.md *.markdown *.mdown *.txt);;所有文件 (*.*)")
            if not path:
                return
            self._remember_dir("open", path)
        if not os.path.exists(path):
            QMessageBox.warning(self, "打开失败", f"文件不存在：\n{path}")
            return
        self._load_path(path)

    def _load_path(self, path):
        """打开文件：已在标签页中则切换，否则新开标签。"""
        path = os.path.abspath(path)
        for i, doc in enumerate(self._docs):
            if doc.get("path") == path:
                self._tabbar.setCurrentIndex(i)
                self._on_tab_clicked(i)
                return
        text = self._read_file(path)
        self._add_doc(path=path, text=text)
        self._add_recent(path)

    def save_file(self) -> bool:
        if not self.file_path:
            return self.save_file_as()

        def cb(md):
            if md is None:
                return
            try:
                if md and not md.endswith("\n"):
                    md += "\n"
                # P1-6：写入前把上一版留档（内容相同则不产生快照）
                self.snapshot_history(self.file_path, md)
                self._write_text(self.file_path, md)   # v3.29d（B2）：按原编码写盘
                self._dirty = False
                if 0 <= self._cur < len(self._docs):
                    self._docs[self._cur]["content"] = md
                self._update_title()
                self._refresh_tab_texts()
                self.show_status(f"已保存 · {self.file_path}")
            except OSError as e:
                QMessageBox.critical(self, "保存失败", str(e))

        self._js_active("window.getMarkdown()", cb)
        return True

    def save_file_as(self) -> bool:
        # v3.29d（B7）：对话框记忆上次保存目录
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Markdown 文件",
            self._dlg_start("save", self.file_path or "未命名.md"),
            "Markdown 文件 (*.md);;所有文件 (*.*)")
        if not path:
            return False
        self._remember_dir("save", path)
        self.file_path = os.path.abspath(path)
        if 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["path"] = self.file_path
            self._refresh_tab_texts()
        self._push_doc_dir()
        self.save_file()
        return True

    # ================= 导出 =================
    # v3.29d（B7/UX #28）：按用途记忆文件对话框的上次目录（导出 / 另存 / 打开）
    def _dlg_dir(self, key):
        return getattr(self, "_dir_map", {}).get(key, "")

    def _dlg_start(self, key, fallback=""):
        d = self._dlg_dir(key)
        if d and os.path.isdir(d):
            return os.path.join(d, os.path.basename(fallback or " "))
        return fallback

    def _remember_dir(self, key, path):
        if not hasattr(self, "_dir_map"):
            self._dir_map = {}
        d = os.path.dirname(os.path.abspath(str(path)))
        if os.path.isdir(d):
            self._dir_map[key] = d

    def export_html(self):
        def cb(html):
            if not html:
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "导出 HTML",
                self._dlg_start("html",
                    os.path.splitext(self.file_path or "未命名")[0] + ".html"),
                "HTML 文件 (*.html)")
            if not path:
                return
            self._remember_dir("html", path)
            # v3.30.11（MATH-1）：内嵌本地 katex.min.css（字体转 data URI），
            # 导出 HTML 断网可用，不再依赖 CDN
            html = self._inline_katex_css(html)
            # v3.30.18（IMG-2）：本地相对路径图片内嵌为 data URI ——
            # 单文件 HTML 发给别人不再裂图（默认内嵌；失败图片保留原样）
            html, n_img = self._embed_local_images(html)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.show_status(f"已导出 HTML · {path}"
                             + (f"（内嵌 {n_img} 张图片）" if n_img else ""))
        self._js_active("window.getExportHTML()", cb)

    def _embed_local_images(self, html):
        """v3.30.18（IMG-2）：把导出 HTML 里的本地图片内嵌为 base64 data URI。

        - data: / http(s): 已自包含或远程，不动；
        - file:/// 绝对 URL 与相对路径都按本地文件解析（相对路径相对文档目录）；
        - 文件缺失时保留原样（与既有「找不到则跳过」原则一致）。
        返回 (html, 内嵌张数)。"""
        if not html:
            return html, 0
        import urllib.parse
        doc_dir = os.path.dirname(self.file_path) if self.file_path else ""
        count = 0

        def _repl(m):
            nonlocal count
            src = m.group(1)
            if src.startswith(("data:", "http://", "https://")):
                return m.group(0)
            path = src
            if path.lower().startswith("file:///"):
                path = urllib.parse.unquote(path[len("file:///"):])
            elif path.lower().startswith("file:"):
                path = urllib.parse.unquote(path[5:])
                path = path.lstrip("/") if os.path.isabs(path.lstrip("/")) else path
            if not os.path.isabs(path):
                if not doc_dir:
                    return m.group(0)      # 未保存文档无法解析相对路径
                path = os.path.join(doc_dir, path.replace("/", os.sep))
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
            except OSError:
                return m.group(0)
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "gif": "image/gif", "webp": "image/webp",
                    "svg": "image/svg+xml", "bmp": "image/bmp"}.get(ext, "image/png")
            count += 1
            return m.group(0).replace(src, "data:" + mime + ";base64," + b64)

        html = re.sub(r'<img[^>]*\ssrc="([^"]+)"', _repl, html)
        return html, count

    def _inline_katex_css(self, html):
        """v3.30.11（MATH-1）：把 editor 侧留下的 __KATEX_CSS__ 占位替换为本地
        katex.min.css —— 字体文件转 base64 data URI（仅保留 woff2，woff/ttf 分支
        去掉），导出单文件离线可用。无占位（文档无公式）或 css 缺失时原样返回。
        结果缓存：字体 base64 转换约几百 KB，同一会话只算一次。"""
        if not html or "__KATEX_CSS__" not in html:
            return html
        css = getattr(self, "_katex_css_cache", None)
        if css is None:
            css = ""
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "katex")
            css_path = os.path.join(base, "katex.min.css")
            try:
                with open(css_path, "r", encoding="utf-8") as f:
                    css = f.read()
                fonts_dir = os.path.join(base, "fonts")
                # woff / ttf 分支直接去掉（现代浏览器均支持 woff2）
                css = re.sub(
                    r",?url\(\"?fonts/[^)]+?\.(?:woff|ttf)\"?\)\s*format\(\"(?:woff|truetype)\"\)",
                    "", css)

                def _font_uri(m):
                    # m.group(1) 形如 "fonts/KaTeX_AMS-Regular.woff2"，取basename
                    # 拼进字体目录（避免二次拼接 fonts/ 导致路径不存在）
                    fp = os.path.join(fonts_dir, os.path.basename(m.group(1)))
                    try:
                        with open(fp, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("ascii")
                    except OSError:
                        return m.group(0)
                    return 'url(data:font/woff2;base64,' + b64 + ') format("woff2")'

                css = re.sub(r"url\(\"?(fonts/[^)]+?\.woff2)\"?\)", _font_uri, css)
            except OSError:
                css = ""
            self._katex_css_cache = css
        if not css:
            # css 缺失（异常安装）：去掉整个占位 style，避免留下字面标记
            return html.replace('<style>__KATEX_CSS__</style>\n', "").replace(
                "<style>__KATEX_CSS__</style>", "")
        return html.replace("__KATEX_CSS__", css)

    def export_pdf(self):
        def cb(html):
            if not html:
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "导出 PDF",
                self._dlg_start("pdf",
                    os.path.splitext(self.file_path or "未命名")[0] + ".pdf"),
                "PDF 文件 (*.pdf)")
            if not path:
                return
            self._remember_dir("pdf", path)
            self._pdf_path = path
            # 先取出标题大纲，PDF 生成后用于写入书签
            self._pending_toc = list(getattr(self, "_outline_cache", []) or [])
            self._pdf_view = QWebEngineView(self)  # 隐藏的导出视图
            self._pdf_view.hide()
            v = self._pdf_view
            v.setPage(EditorPage(v))
            v.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            v.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            # v3.30.11（MATH-1）：PDF 渲染同样走离线内嵌 css（公式静态化后零依赖）
            html = self._inline_katex_css(html)
            base = QUrl.fromLocalFile(
                (os.path.dirname(self.file_path) if self.file_path else os.path.expanduser("~")) + "/")
            v.loadFinished.connect(self._print_pdf)
            v.setHtml(html, base)
        self._js_active("window.getExportHTML()", cb)

    def _print_pdf(self, ok):
        if not ok or not self._pdf_view:
            return
        page = self._pdf_view.page()
        page.pdfPrintingFinished.connect(self._pdf_done)
        page.printToPdf(self._pdf_path)

    def _pdf_done(self, path, ok):
        if not ok:
            self.show_status("导出 PDF 失败")
        else:
            n, msg = exporters.add_pdf_bookmarks(path, getattr(self, "_pending_toc", None))
            self.show_status(f"已导出 PDF · {path}" + (f"（{msg}）" if n else f"（{msg}）"))
        self._pending_toc = None
        if self._pdf_view:
            self._pdf_view.deleteLater()
            self._pdf_view = None

    # ---- Word / EPUB ----
    def _pandoc_exe(self):
        return exporters.find_pandoc(getattr(self, "_pandoc_path", ""))

    def set_pandoc_path(self, path):
        """设置外部 pandoc 路径（留空 = 自动探测 PATH）。"""
        self._pandoc_path = str(path or "").strip()
        self._settings.setValue("pandocPath", self._pandoc_path)
        found = self._pandoc_exe()
        self.show_status(f"pandoc 路径已保存：{found}" if found
                             else "pandoc 路径已保存（当前未探测到 pandoc，将使用内置导出）")

    def _export_document(self, kind):
        """kind: 'docx' | 'epub'。优先 pandoc，未安装则回退内置实现。"""
        label = "Word (docx)" if kind == "docx" else "EPUB"
        ext = ".docx" if kind == "docx" else ".epub"
        filt = "Word 文档 (*.docx)" if kind == "docx" else "EPUB 电子书 (*.epub)"

        def cb(md):
            if md is None:
                return
            # v3.29d（B6/UX #33）：pandoc 未安装时导出前先预警（每会话只提示一次），
            # 说明降级影响并给出安装指引，不再静默回退内置转换
            pandoc = self._pandoc_exe()
            if not pandoc and not getattr(self, "_pandoc_warned", False):
                self._pandoc_warned = True
                ret = QMessageBox.question(
                    self, "未检测到 pandoc",
                    "未检测到 pandoc，将使用内置转换导出：\n"
                    "· 公式与图表会降级为「源码 + 标注」形式\n"
                    "· 标题 / 表格 / 图片等其余内容正常导出\n\n"
                    "如需完整的公式 / 图表导出效果，可到 pandoc 官网"
                    "（pandoc.org）下载安装，并在 系统设置 → 通用 中配置路径。\n\n"
                    "是否继续使用内置转换导出？",
                    QMessageBox.Yes | QMessageBox.No)
                if ret != QMessageBox.Yes:
                    return
            path, _ = QFileDialog.getSaveFileName(
                self, f"导出 {label}",
                self._dlg_start(kind,
                    os.path.splitext(self.file_path or "未命名")[0] + ext), filt)
            if not path:
                return
            self._remember_dir(kind, path)
            base_dir = self._doc_dir()
            title = os.path.splitext(os.path.basename(self.file_path or "未命名"))[0]
            if pandoc:
                ok, msg = exporters.pandoc_convert(pandoc, md, path, kind, base_dir)
                self.show_status(msg)
                if not ok:
                    QMessageBox.warning(self, f"导出 {label} 失败", msg)
                return
            # v3.30.19（MMD-2）：内置导出前先把已渲染图表位图化（SVG→PNG）
            self._export_with_mmd(kind, label, md, path, base_dir, title)

        self._js_active("window.getMarkdown()", cb)

    def _export_with_mmd(self, kind, label, md, path, base_dir, title):
        """v3.30.19（MMD-2）：让编辑器把已渲染 SVG 转 PNG，收齐后执行内置导出。"""
        def start(total):
            if not total:
                self._export_now(kind, label, md, path, base_dir, title, {})
                return
            self._mmd_export = {"total": int(total), "t0": time.time()}
            self._mmd_poll(kind, label, md, path, base_dir, title)
        self._js_active("window.__mmdExportStart ? window.__mmdExportStart() : 0", start)

    def _mmd_poll(self, kind, label, md, path, base_dir, title):
        def got(state):
            st = state or {}
            done = int(st.get("done", 0) or 0)
            total = int(st.get("total", 0) or 0)
            if done >= total or time.time() - self._mmd_export["t0"] > 12:
                mmd_png = {}
                for it in st.get("items", []):
                    src = str(it.get("src") or "")
                    data = str(it.get("data") or "")
                    if not src or not data or src in mmd_png:
                        continue
                    try:
                        fd, tmp = tempfile.mkstemp(suffix=".png")
                        with os.fdopen(fd, "wb") as f:
                            f.write(base64.b64decode(data.split(",", 1)[-1]))
                        mmd_png[src] = tmp
                    except Exception as e3:
                        _log.debug("图表 PNG 落盘失败: %s", e3)
                self._export_now(kind, label, md, path, base_dir, title, mmd_png)
                return
            QTimer.singleShot(300, lambda: self._mmd_poll(kind, label, md, path, base_dir, title))
        self._js_active("window.__mmdExportState || null", got)

    def _export_now(self, kind, label, md, path, base_dir, title, mmd_png):
        if kind == "docx":
            ok, msg = exporters.write_docx(md, path, base_dir, title, mmd_png=mmd_png)
        else:
            ok, msg = exporters.write_epub(md, path, base_dir, title, mmd_png=mmd_png)
        self.show_status(msg)
        if not ok:
            QMessageBox.warning(self, f"导出 {label} 失败", msg)

    def export_docx(self):
        self._export_document("docx")

    def export_epub(self):
        self._export_document("epub")

    # ================= 杂项 =================
    def _about(self):
        """v3.29d（UX #29）：关于页显示版本号，并提供「查看更新日志」入口。"""
        ret = QMessageBox.question(
            self, "关于",
            f"<b>{APP_NAME}</b>　<span style='color:#888;'>v3.30</span><br>"
            "Typora 风格的所见即所得 Markdown 编辑器<br>"
            "支持多文件标签页、双栏（源码 / 预览）模式、数学公式<br>"
            "基于 Python + PySide6 (QtWebEngine) 构建。<br><br>"
            "是否查看更新日志（CHANGELOG.md）？",
            QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        log_md = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "CHANGELOG.md")
        if not os.path.exists(log_md):
            log_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md")
        if os.path.exists(log_md):
            try:
                os.startfile(log_md)     # noqa: S606 — 系统默认程序打开
            except OSError:
                self.show_status("无法打开更新日志")
        else:
            self.show_status("未找到 CHANGELOG.md")

    def _show_shortcuts(self):
        """快捷键一览：从快捷键管理体系动态生成（含用户自定义值）。"""
        rows = []
        for group, items in self._shortcut_defs:
            rows.append(f"<p style='margin:10px 0 4px;'><b>{group}</b></p>")
            for name, _default in items:
                act = self._shortcut_acts.get(name)
                key = act.shortcut().toString(QKeySequence.NativeText) if act else ""
                rows.append(
                    f"<div style='margin:2px 0 2px 12px;'>{name} — "
                    f"<code style='background:#f2f3f5;padding:1px 6px;border-radius:4px;'>{key}</code>"
                    f"</div>")
        rows.append("<p style='margin:10px 0 2px; color:#6b7280;'>"
                    "在「设置 → 快捷键设置」中可修改以上快捷键。编辑器内操作："
                    "空行输入 / 唤起插入菜单（也可点块手柄或 Ctrl+/）· 选中文字浮现行菜单 · "
                    "悬停块左侧 ⠿ 块菜单（空块直接唤起插入菜单）· "
                    "Ctrl+Enter 跳出代码块/引用。</p>")
        QMessageBox.information(self, "快捷键一览", "".join(rows))

    # ---- 最近文件 ----
    def _add_recent(self, path):
        lst = self._settings.value("recentFiles", []) or []
        if isinstance(lst, str):
            lst = [lst]
        path = os.path.abspath(path)
        if path in lst:
            lst.remove(path)
        lst.insert(0, path)
        self._settings.setValue("recentFiles", lst[:10])

    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        lst = self._settings.value("recentFiles", []) or []
        if isinstance(lst, str):
            lst = [lst]
        if not lst:
            self._recent_menu.addAction("(空)").setEnabled(False)
            return
        for p in lst:
            act = self._recent_menu.addAction(p)
            act.triggered.connect(lambda _=False, f=p: self.open_file(f))
        self._recent_menu.addSeparator()
        clr = self._recent_menu.addAction("清空最近文件")
        clr.triggered.connect(lambda: self._settings.setValue("recentFiles", []))

    # ---- 侧边栏 ----
    def toggle_sidebar(self):
        self._sidebar.setVisible(not self._sidebar.isVisible())
        self._update_side_btn()

    def _update_side_btn(self):
        """左侧工具栏顶部开关：侧栏可见时显示 «（收起），隐藏时显示 »（展开）。"""
        vis = self._sidebar.isVisible()
        self._btn_side.setText("«" if vis else "»")
        self._btn_side.setToolTip(
            ("收起" if vis else "展开") + "侧边栏 (Ctrl+Shift+L)")
        if getattr(self, "_act_sidebar", None) is not None:
            self._act_sidebar.setChecked(vis)

    def _show_sidebar_tab(self, tab):
        self._sidebar.setVisible(True)
        self._update_side_btn()
        self._sidebar.select_tab(tab)

    # ---- 模式切换（写作 / 源码 / 分屏）----
    def _mode_label(self):
        for m in MODES:
            if m[0] == self._mode:
                return m[2], m[3]
        return "写作模式", ""

    def _update_mode_button(self):
        name, desc = self._mode_label()
        icon_name = next(m[1] for m in MODES if m[0] == self._mode)
        self._btn_mode.setIcon(MODE_ICONS[icon_name](20))
        self._btn_mode.setToolTip(
            f"当前模式：{name}\n{desc}\n"
            "单击循环切换：写作 → 源码 → 分屏")
        # 菜单里的模式单选同步勾选状态
        act = getattr(self, "_mode_acts", {}).get(self._mode)
        if act and not act.isChecked():
            act.setChecked(True)

    def cycle_mode(self):
        order = [m[0] for m in MODES]
        nxt = order[(order.index(self._mode) + 1) % len(order)]
        self._set_mode(nxt)

    def _set_mode(self, mode):
        """统一的三态模式切换，保留各视图内容不丢失。"""
        if mode not in ("edit", "src", "dual") or mode == self._mode:
            return
        if mode == "dual":
            # 首次进入分屏：此时才创建源码/预览视图（启动提速）
            self._ensure_dual_views()

            # 进入分屏：把写作视图内容推到 源码 + 预览
            def apply(md):
                text = md if md is not None else ""
                self._mode = mode
                self._dual = True
                self._last_preview_md = None
                self._push_text(text)
                self._stack.setCurrentIndex(1)
                self._update_mode_button()
                self.show_status("分屏模式：左侧源码编辑 · 右侧实时预览")
            self._js_view(self._view, "window.getMarkdown()", apply)
            return
        # 回到单栏（写作 或 源码）
        src_on = "true" if mode == "src" else "false"

        def apply_back(md):
            text = md if md is not None else ""
            self._stack.setCurrentIndex(0)
            self._last_preview_md = None
            st = self._vstate["edit"]
            if st["loaded"]:
                self._js_view(self._view, f"window.setMarkdown({js(text)})")
                self._js_view(self._view, f"window.setSourceMode({src_on})")
            else:
                st["pending"] = text
            self._mode = mode
            self._dual = False
            self._update_mode_button()
            name, _ = self._mode_label()
            self.show_status(name)

        if self._mode == "dual":
            self._js_view(self._view_src, "window.getMarkdown()", apply_back)
        else:
            # 写作 <-> 源码：同一视图，直接开关源码态
            st = self._vstate["edit"]
            if st["loaded"]:
                self._js_view(self._view, f"window.setSourceMode({src_on})")
            self._mode = mode
            self._update_mode_button()
            name, _ = self._mode_label()
            self.show_status(name)

    def toggle_typewriter(self):
        self._typewriter = not getattr(self, "_typewriter", False)
        self._settings.setValue("typewriter", bool(self._typewriter))
        self._act_typewriter.setChecked(self._typewriter)
        self._js_active(
            f"window.setMode({{typewriter: {str(self._typewriter).lower()}}})")
        self.show_status("打字机模式：开" if self._typewriter else "打字机模式：关")

    def toggle_focus(self):
        self._focus = not getattr(self, "_focus", False)
        self._settings.setValue("focus", bool(self._focus))
        self._act_focus.setChecked(self._focus)
        self._js_active(f"window.setMode({{focus: {str(self._focus).lower()}}})")
        self.show_status("专注模式：开" if self._focus else "专注模式：关")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def set_theme(self, name):
        """兼容旧调用：等价于 apply_theme。"""
        self.apply_theme(name)

    def apply_theme(self, name, persist=True):
        """全局换肤：Qt 界面（菜单/工具栏/状态栏/对话框/侧栏）+ 编辑器网页视图。"""
        if name not in styles.THEME_IDS:
            name = "light"
        self._theme = name
        # 1) Qt 层：全局 QSS + 侧栏 + 已打开的对话框
        QApplication.instance().setStyleSheet(styles.app_qss(name))
        self._sidebar.setStyleSheet(styles.sidebar_qss(name))
        if hasattr(self._sidebar, "set_tree_arrows"):
            self._sidebar.set_tree_arrows(name)   # v3.26：展开/收拢箭头随主题换色
        for dlg_attr in ("_find_dlg", "_sc_dlg", "_set_dlg", "_cmd_dlg", "_hist_dlg"):
            dlg = getattr(self, dlg_attr, None)
            if dlg is not None:
                dlg._apply_theme_qss(name)
        # 2) Web 层：所有已加载的编辑器视图
        views = {"edit": self._view, "src": self._view_src, "prev": self._view_prev}
        for role, view in views.items():
            if view is not None and self._vstate[role]["loaded"]:
                self._js_view(view, f"window.setTheme({js(name)})")
        # 3) 菜单勾选状态
        for tid, act in self._theme_acts.items():
            act.setChecked(tid == name)
        if persist:
            self._settings.setValue("theme", name)
        self.show_status(f"主题：{styles.theme_label(name)}")

    def set_zoom(self, factor):
        """编辑区字号缩放（对所有视图生效并持久化）。"""
        self._zoom = max(0.8, min(1.6, float(factor)))
        views = (self._view, self._view_src, self._view_prev)
        for v in views:
            if v is not None:
                v.setZoomFactor(self._zoom)
        self._settings.setValue("zoom", self._zoom)
        self.show_status(f"编辑区缩放：{int(round(self._zoom * 100))}%")

    def set_autosave(self, on):
        self._autosave = bool(on)
        self._settings.setValue("autosave", self._autosave)
        self.show_status("自动保存：开" if self._autosave else "自动保存：关")

    def set_code_lang(self, lang):
        """设置代码块默认语言（插入代码块时预选），即时下发到编辑器并持久化。"""
        lang = str(lang or "C").strip() or "C"
        self._code_lang = lang
        self._settings.setValue("codeLang", lang)
        self._js_active(f"window.setDefaultCodeLang({js(lang)})")
        self.show_status(f"代码块默认语言：{lang}")

    def set_code_prefs(self, lnum=None, style=None):
        """v3.25：设置代码块行号显示 / 默认代码风格，即时下发并持久化。

        新插入 / 重新渲染的代码块默认取此配置；代码栏「风格」按钮可对单个
        代码块临时切换（会话内生效，不写入 Markdown）。"""
        if lnum is not None:
            self._code_lnum = bool(lnum)
            self._settings.setValue("codeLineNum", "1" if lnum else "0")
        if style:
            self._code_style = str(style)
            self._settings.setValue("codeStyle", self._code_style)
        self._js_active(
            f"window.setCodePrefs({{lnum: {str(self._code_lnum).lower()}, "
            f"style: {js(self._code_style)}}})")
        self.show_status(
            f"代码块：行号{'开' if self._code_lnum else '关'} · "
            f"风格 {self._code_style}")

    # ================= 侧栏显示设置 =================
    def set_outline_level(self, level):
        """设置大纲显示级别（1~6，默认 3），持久化并立即重建大纲。"""
        try:
            level = max(1, min(6, int(level)))
        except (TypeError, ValueError):
            return
        self._outline_level = level
        self._settings.setValue("outlineLevel", level)
        self._sidebar.set_outline_level(level)
        self.show_status(f"大纲显示级别：{level} 级")

    def set_outline_words(self, on):
        """v3.31.2（#3）：大纲分节字数后缀显示开关，持久化并原地刷新后缀。"""
        self._outline_words = bool(on)
        self._settings.setValue("outlineWords", self._outline_words)
        self._sidebar.set_outline_words(self._outline_words)
        self.show_status("大纲分节字数：" + ("已显示" if self._outline_words else "已隐藏"))

    def set_para_indent(self, n):
        """v3.31.2（#8）：段落首行缩进格数（0~4），持久化并全视图即时生效。"""
        try:
            n = max(0, min(4, int(n)))
        except (TypeError, ValueError):
            return
        self._para_indent = n
        self._settings.setValue("paraIndent", n)
        for v in (self._view, self._view_src, self._view_prev):
            if v is not None:
                self._js_view(v, f"window.setParaIndent({n})")
        self.show_status(f"段首缩进：{n} 格" if n else "段首缩进：无")

    def set_h1_center(self, on):
        """v3.31.2（#9）：标题 1 全局居中，持久化并全视图即时生效。"""
        self._h1_center = bool(on)
        self._settings.setValue("h1Center", self._h1_center)
        s = str(self._h1_center).lower()
        for v in (self._view, self._view_src, self._view_prev):
            if v is not None:
                self._js_view(v, f"window.setH1Center({s})")
        self.show_status("标题 1 居中：" + ("开" if self._h1_center else "关"))

    def set_file_list_mode(self, mode):
        """设置文件列表显示模式：current=跟随当前文档（默认）/ blank=空白项。"""
        mode = "blank" if str(mode) == "blank" else "current"
        if mode == getattr(self, "_file_list_mode", "current") and \
                self._sidebar._file_mode == mode:
            return
        self._file_list_mode = mode
        self._settings.setValue("fileListMode", mode)
        self._sidebar.set_file_mode(mode)
        self.show_status("文件列表：空白项" if mode == "blank" else "文件列表：跟随当前文档")

    # ================= 斜杠（/）菜单配置 =================
    def _slash_cfg(self):
        """把当前菜单配置整理为下发给编辑器的 dict。"""
        order = [x for x in self._slash_order if x in SLASH_IDS] or list(SLASH_ORDER_DEFAULT)
        return {"order": order, "def": self._slash_def, "sub": dict(self._slash_sub)}

    def set_slash_menu_config(self, order, def_id, sub):
        """设置斜杠菜单：一级顺序 / 默认项 / 二级默认项，即时生效并持久化。"""
        # 缺省项按默认相对位置补齐（持久化完整顺序），不覆盖用户排序
        ids = merge_slash_order(order)
        self._slash_order = ids
        self._slash_def = def_id if def_id in ids else ids[0]
        cleaned = {}
        for key, dft in SLASH_SUB_DEFAULTS.items():
            try:
                cleaned[key] = max(0, int(sub.get(key, dft)))
            except (TypeError, ValueError):
                cleaned[key] = dft
        self._slash_sub = cleaned
        self._settings.setValue("slashMenuOrder", ",".join(ids))
        self._settings.setValue("slashMenuDef", self._slash_def)
        self._settings.setValue("slashSubHeading", cleaned["heading"])
        self._settings.setValue("slashSubList", cleaned["list"])
        self._settings.setValue("slashSubChart", cleaned["chart"])
        self._settings.setValue("slashSubMath", cleaned["math"])
        self._js_active(f"window.setSlashMenuConfig({js(json.dumps(self._slash_cfg()))})")
        self.show_status("斜杠菜单设置已保存")

    def show_settings(self):
        if not hasattr(self, "_set_dlg"):
            self._set_dlg = SettingsDialog(self)
        self._set_dlg.show()
        self._set_dlg.raise_()

    # ---- 查找替换 ----
    def show_find(self, with_replace):
        if not hasattr(self, "_find_dlg"):
            self._find_dlg = FindDialog(self)
        self._find_dlg.show_replace(with_replace)
        self._find_dlg.show()
        self._find_dlg.raise_()
        self._find_dlg.focus_find()

    def jump_to_heading(self, index):
        if self._dual and self._view_src is not None:
            self._js_view(self._view_src, f"window.gotoHeadingSrc({index})")
            self._js_view(self._view_prev, f"window.gotoHeading({index})")
        else:
            self._js_view(self._view, f"window.gotoHeading({index})")

    # ================= 拖拽 =================
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        # v3.30.10（IMG-1）：拖入多图时全部插入（原先只插第一张就 break），
        # 并给数量提示；拖入 .md 仍只打开第一个
        img_cnt = 0
        opened = False
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if not opened and p.lower().endswith(MD_EXTS):
                self.open_file(p)
                opened = True
                continue
            if p.lower().endswith(IMG_EXTS):
                self._insert_image_file(p)
                img_cnt += 1
        if img_cnt > 1:
            self.show_status(f"已插入 {img_cnt} 张图片")

    # QWebEngineView 的渲染子控件会吞掉 drop 事件，需要事件过滤器
    def _install_drop_filter(self):
        for v in (self._view, self._view_src, self._view_prev):
            if v is None:
                continue
            fp = v.focusProxy()
            if fp:
                fp.installEventFilter(self)
            v.setAcceptDrops(True)

    def eventFilter(self, obj, ev):
        # 状态栏「字数」点击 → 统计详情
        if obj is getattr(self, "_count", None) and ev.type() == QEvent.MouseButtonPress:
            self._show_stats_detail()
            return True
        if ev.type() == QEvent.DragEnter and ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            return True
        if ev.type() in (QEvent.DragMove, QEvent.DragLeave):
            return True
        if ev.type() == QEvent.Drop:
            opened = False
            for url in ev.mimeData().urls():
                p = url.toLocalFile()
                if p.lower().endswith(MD_EXTS):
                    self.open_file(p)
                    opened = True
                    break
                if p.lower().endswith(IMG_EXTS):
                    self._insert_image_file(p)
                    opened = True
                    break
            if opened:
                return True
        return super().eventFilter(obj, ev)

    # ================= 右键菜单 =================
    def _show_ctx_menu(self, view, pos):
        """Typora 式中文右键菜单（预览侧只读，无剪切/粘贴）。"""
        page = view.page()
        readonly = view is self._view_prev
        menu = QMenu(self)
        if not readonly:
            menu.addAction("撤销", lambda: page.triggerAction(QWebEnginePage.Undo))
            menu.addAction("重做", lambda: page.triggerAction(QWebEnginePage.Redo))
            menu.addSeparator()
            menu.addAction("剪切", lambda: page.triggerAction(QWebEnginePage.Cut))
        menu.addAction("复制", lambda: page.triggerAction(QWebEnginePage.Copy))
        if not readonly:
            menu.addAction("粘贴", lambda: page.triggerAction(QWebEnginePage.Paste))
        menu.addSeparator()
        menu.addAction("全选", lambda: page.triggerAction(QWebEnginePage.SelectAll))
        menu.exec(view.mapToGlobal(pos))

    # ================= 退出 =================
    def closeEvent(self, e):
        if self._quitting:
            e.accept()
            return
        # 自动保存机制下，有路径的文档内容已实时落盘；未命名文档询问保存
        need_ask = False
        if self._cur >= 0 and self._cur < len(self._docs):
            cur_doc = self._docs[self._cur]
            if not cur_doc.get("path") and (cur_doc.get("content") or "").strip():
                need_ask = True
        if not need_ask:
            self._quitting = True
            e.accept()
            return
        btn = QMessageBox.question(
            self, "未保存的更改",
            "当前未命名文档尚未保存到文件，退出前是否保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if btn == QMessageBox.Cancel:
            e.ignore()
            return
        if btn == QMessageBox.Save:
            from PySide6.QtCore import QEventLoop
            res = {}
            loop = QEventLoop()

            def cb(md):
                res["md"] = md
                loop.quit()

            self._js_active("window.getMarkdown()", cb)
            loop.exec()
            md = res.get("md")
            if md is not None:
                if not self.file_path:
                    path, _ = QFileDialog.getSaveFileName(
                        self, "保存 Markdown 文件",
                        self._dlg_start("save", "未命名.md"), "Markdown 文件 (*.md)")
                    if not path:
                        e.ignore()
                        return
                    self._remember_dir("save", path)
                    self.file_path = os.path.abspath(path)
                self._write_text(self.file_path, md)   # v3.29d（B2）
        self._quitting = True
        e.accept()
