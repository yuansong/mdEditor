# -*- coding: utf-8 -*-
"""主窗口：多文档标签、三视图（写作/源码/分屏）、文件操作与导出。"""
import base64
import binascii
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

from PySide6.QtCore import QEvent, QTimer, QUrl, QSize, Qt, QSettings, QMimeData
from PySide6.QtGui import QAction, QActionGroup, QColor, QGuiApplication, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QSplitter, QStackedWidget, QTabBar, QToolBar,
    QToolButton, QVBoxLayout, QWidget,
)
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

import exporters
from config import APP_NAME, APP_VERSION, BUILTIN_TEMPLATES, DEMO_MD, DRAFT_DIR, FILE_LIST_DEFAULT_DIR, HERE, LOG_DIR, MD_EXTS, MMD_LEGACY, MMD_THEME_LABELS, MODES, TEMPLATE_FILE, TPL_FILE_VERSION, TPL_MAX_BYTES, TPL_NAME_MAX, UPDATE_URL, USER_DATA_DIR, js

# 斜杠（/）菜单可配置项：一级菜单 id 集与默认顺序 / 默认项 / 二级默认下标
# v3.30.3：按用户要求移除「上标 / 下标」（supsub）一级项；^x^ / ~x~ 语法仍可输入
# v3.31.3：footnote / deflist 合并为 refs「脚注与定义」（旧配置 id 由 merge 自动插回）
# v3.32（P1-1）：新增 tpl「模板」一级项（内置 6 个场景模板，插入即写）
SLASH_IDS = ("heading", "list", "table", "code", "hr", "quote", "image", "chart",
             "refs", "tpl", "math")
SLASH_ORDER_DEFAULT = ["heading", "list", "table", "code", "hr", "quote", "image", "chart",
                       "refs", "tpl", "math"]
SLASH_SUB_DEFAULTS = {"heading": 2, "list": 1, "chart": 0, "math": 0,
                      "refs": 0, "tpl": 0}  # 标题默认H3 / 列表默认有序 / 图表默认流程图 / 公式默认上标


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

# v3.32（P0-5）：模块级日志器（main.setup_logging 已装配滚动文件输出）。
_log = logging.getLogger("mdEditor.app")


# ================= v3.35（TPL-D）「设为模板文件」名称规则 =================
def normalize_template_name(name, max_len=None):
    """归一化模板名称：空白折叠 → 去首尾 → 按显示上限截断；不可用时返回空串。

    名称会显示在 / 菜单「模板」二级与悬浮栏模板菜单里，过长会撑破菜单宽度，
    故与内核 window.setCustomTemplates 的截断规则同源（同为 TPL_NAME_MAX 个码点）——
    这样「管理对话框里看到的名字」与「菜单里看到的名字」永远一致，
    不会出现只在菜单被静默截断的错位。
    """
    limit = TPL_NAME_MAX if max_len is None else max(1, int(max_len))
    s = re.sub(r"[\s\u200b\u200c\u200d\ufeff]+", " ", str(name or "")).strip()
    return s[:limit]


def normalize_template_icon(ic):
    """v3.36（TPL-E）模板菜单图标：去空白 + 按码点截断到 4（容纳组合式 emoji）。

    空串 = 无图标，内核渲染时回退为 ⭐（自建模板保持旧观感）。
    """
    s = str(ic or "").strip()
    return "".join(list(s)[:4]) if s else ""


def unique_template_name(name, existing, max_len=None):
    """重名自动编号（同名模板在菜单里无法区分）："周报" → "周报 2" → "周报 3"…

    编号后仍须满足显示上限，故先给序号留位再截断基名（否则 30 字满名加序号会
    被截回原名，陷入永远重名）。
    """
    limit = TPL_NAME_MAX if max_len is None else max(1, int(max_len))
    used = {str(n or "") for n in (existing or [])}
    if name not in used:
        return name
    for k in range(2, 1000):
        suf = " %d" % k
        cand = name[:max(1, limit - len(suf))] + suf
        if cand not in used:
            return cand
    return name


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
        # v3.32.2（TPL-C）：用户自定义模板（/ 菜单「模板」二级 + 悬浮栏 📄 共用）
        self._custom_templates = self._load_custom_templates()
        self._pending_toc = None
        self._pending_goto = None
        self._pending_tries = 0

        # ---- 多文档 ----
        self._docs = []          # [{"path": str|None, "content": str|None, "dirty": bool}]
        self._cur = -1
        self._switching = False
        self._pending_switch = -1
        # v3.38（TAB-3）：已关闭标签栈（Ctrl+Alt+T 逐个回溯，浏览器语义）
        self._closed_stack = []
        # v3.38（TAB-B）：多选标签（N++ 对标）—— Ctrl+单击增减 / Shift+单击区间，
        # 集合存标签索引；任何切换 / 批量关闭后清空重建。
        self._tab_multi = set()
        self._multi_anchor = -1
        # v3.38（TAB-8）：最近使用顺序（MRU，存 doc 字典引用；切换时前插、关闭时惰性剔除）
        self._mru = []

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

        # v3.38（OUT-5）：启动行为默认值（设置页可改，QSettings 持久化）
        self._startup_action = "blank"
        self._startup_folder = ""
        # v3.38（FLP-1）：文件列表默认打开路径（config 默认值 + QSettings 覆盖）
        self._file_list_default_dir = str(
            self._settings.value("files/defaultDir", FILE_LIST_DEFAULT_DIR) or "")

        self._init_ui()
        self._init_menu_toolbar()
        self.apply_theme(self._theme, persist=False)

        # 初始文档：v3.38（OUT-5）「启动时」设置 —— blank=欢迎页（默认，行为不变）/
        # lastFile=恢复上次打开的文件 / lastFileSide=恢复上次文件与侧栏位置 /
        # folder=打开指定文件夹（仅侧栏定位，不打开文档）
        _sa = str(self._settings.value("startupAction", self._startup_action) or "blank")
        _lf = str(self._settings.value("lastFile", "") or "")
        if _sa in ("lastFile", "lastFileSide") and _lf and os.path.isfile(_lf):
            self._add_doc(path=_lf, text=self._read_file(_lf))
            self._add_recent(_lf)
        else:
            self._add_doc(path=None, text=DEMO_MD)
            if _sa == "folder":
                _sf = str(self._settings.value("startupFolder", "") or "")
                if _sf and os.path.isdir(_sf):
                    self._sidebar.set_root(_sf)
        if _sa == "lastFileSide" and self.file_path:
            _sd = str(self._settings.value("lastSidebarDir", "") or "")
            if _sd and os.path.isdir(_sd):
                self._sidebar.set_root(_sd)   # 侧栏位置恢复（优先于文件目录）

        # v3.38（FLP-1）：文件列表默认打开路径 —— 上次访问目录（优先）→ 默认路径 → 根层。
        # 只在「启动时 = 打开欢迎页」（默认档）接管：lastFile / lastFileSide / folder 三档
        # 已各自决定侧栏位置（OUT-5），再覆盖会与既有语义打架。
        if _sa == "blank":
            self._sidebar.restore_initial_dir()

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
        # v3.38（TAB-1）：标签右键菜单（Notepad++ 对标）—— 右键先选中该标签再弹菜单
        self._tabbar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tabbar.customContextMenuRequested.connect(self._on_tab_menu)
        # v3.38（TAB-5）：中键点击标签即关闭 / 双击空白处新建标签（N++ / 浏览器对标）
        self._tabbar.installEventFilter(self)
        tab_wrap = QWidget(self)
        tab_wrap.setObjectName("tabstrip")
        tl = QHBoxLayout(tab_wrap)
        tl.setContentsMargins(8, 0, 0, 0)
        tl.addWidget(self._tabbar)
        # v3.38（TAB-9）：标签溢出下拉（N++ / VS Code 对标）—— 列出全部标签带
        # • 未保存 / 📌 固定标记，点击切换；仅在总宽超出可视宽度时启用
        self._btn_tb_more = QToolButton(tab_wrap)
        self._btn_tb_more.setObjectName("tbMore")
        self._btn_tb_more.setText("»")
        self._btn_tb_more.setAutoRaise(True)
        self._btn_tb_more.setFixedWidth(24)
        self._btn_tb_more.setCursor(Qt.PointingHandCursor)
        self._btn_tb_more.clicked.connect(self._show_tb_more_menu)
        self._btn_tb_more.setEnabled(False)
        tl.addWidget(self._btn_tb_more)
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

        # v3.38（SYN-3）：预览 → 源码反向同步的循环防护 / 变更检测状态
        self._sync_ts_src2prev = 0.0   # 最近一次程序性滚动预览（源码同步所致）的时刻
        self._sync_ts_prev2src = 0.0   # 最近一次用户滚动预览触发反向同步的时刻
        self._last_src_pair = None     # 上次发给预览的 (块号, frac)——无变化不重发
        self._last_prev_pair = None    # 上次从预览收到并转发的 (块号, frac)

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

        # v3.38（TB-1）：工具栏可被隐藏（右键菜单 / 视图菜单 / 快捷键），而隐藏后原本
        # 没有任何恢复入口 —— 连工具栏顶部的侧栏开关 « 也一起消失，等同死局。
        # 这里在窗口左侧边缘常驻一个「»」展开按钮，只在工具栏隐藏时显形、始终置顶可点。
        self._btn_tb_show = QToolButton(self)
        self._btn_tb_show.setObjectName("tbExpand")
        self._btn_tb_show.setText("»")
        self._btn_tb_show.setToolTip("展开工具栏（视图 → 显示 / 隐藏工具栏，或 Ctrl+Shift+B）")
        self._btn_tb_show.setCursor(Qt.PointingHandCursor)
        self._btn_tb_show.setAutoRaise(True)
        self._btn_tb_show.setFixedSize(20, 58)
        self._btn_tb_show.clicked.connect(lambda: self.set_toolbar_visible(True))
        self._btn_tb_show.hide()
        self._btn_tb_show.raise_()

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
        # v3.38（TB-1）：工具栏被隐藏（右键菜单 / 视图菜单 / 快捷键）→ 同步边缘展开按钮。
        # 注意只同步 UI、不写 QSettings：窗口关闭 / 隐藏时 Qt 也会给子控件发 HideToParent，
        # 若在此落盘会把「关闭程序」误记成「用户隐藏了工具栏」。
        tb.visibilityChanged.connect(lambda _v=False: self._sync_toolbar_state(persist=False))

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
        # v3.38（TAB-6）：多文档批量保存（只保存「有路径且已修改」的标签，未命名不批量弹窗）
        self._reg_act("文件", "全部保存", "Ctrl+Alt+S", self.save_all, menu=m_file)
        self._reg_act("文件", "关闭标签页", "Ctrl+W", lambda: self._close_tab(self._cur), menu=m_file)
        # v3.38（TAB-B）：走 _close_all_tabs（跳过固定标签 + 未保存汇总确认 + 状态栏反馈）
        self._reg_act("文件", "关闭所有标签", None,
                      self._close_all_tabs, menu=m_file)
        # v3.38（TAB-3）：重新打开刚关闭的标签（可连按逐个回溯）。
        # 浏览器习惯是 Ctrl+Shift+T，但该组合在本工程已属「插入表格」（v3.31 起），
        # 故改用 Ctrl+Alt+T，避免抢键。
        self._reg_act("文件", "重新打开关闭的标签", "Ctrl+Alt+T", self._reopen_closed_tab, menu=m_file)
        m_file.addSeparator()
        self._reg_act("文件", "导出 HTML…", None, self.export_html, menu=m_file)
        self._reg_act("文件", "导出 PDF…（含书签）", None, self.export_pdf, menu=m_file)
        self._reg_act("文件", "导出 Word (docx)…", None, self.export_docx, menu=m_file)
        self._reg_act("文件", "导出 EPUB…", None, self.export_epub, menu=m_file)
        self._reg_act("文件", "迁移内嵌图片为文件…", None, self.migrate_embedded_images, menu=m_file)
        m_file.addSeparator()
        # P1-6 / P1-7：版本历史（v3.25：「资源管理器显示 / 外部程序打开」移入侧栏文件列表右键）
        self._reg_act("文件", "历史版本…", "Ctrl+Shift+H", self.show_history, menu=m_file)
        # v3.32（P0-3）：命令面板同款「立即留档」在文件菜单也可见，主动打点
        self._reg_act("文件", "立即留档（版本快照）", None, self.manual_snapshot, menu=m_file)
        # v3.32（P0-7）：本地唯一副本的最低成本容灾出口
        self._reg_act("文件", "归档整个工作区…", None, self.archive_workspace, menu=m_file)
        # v3.32（P1-2②）：「复制为 HTML」是中文用户最高频交付动作，从编辑菜单提级
        a = QAction("复制为 HTML（公众号 / Word 富文本）", self)
        a.triggered.connect(self.copy_as_html)
        m_file.addAction(a)
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
        # v3.32（P1-2②）：「复制为 HTML」已提级到文件菜单（此处不再重复）
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
        # v3.38（TB-1）：主工具栏显示 / 隐藏（隐藏时左侧边缘常驻展开按钮，杜绝「无法恢复」）
        # v3.38（TAB-3）：默认快捷键由 TB-1 初版的 Ctrl+Shift+T 改为 Ctrl+Shift+B ——
        # Ctrl+Shift+T 早已被「插入表格」（格式命令，v3.31 起）占用，不能再抢。
        self._act_toolbar = self._reg_act("视图", "显示 / 隐藏工具栏", "Ctrl+Shift+B",
                                          self.toggle_toolbar, menu=m_view, checkable=True)
        self._act_toolbar.setChecked(True)
        self._reg_act("视图", "文件列表", "Ctrl+Shift+E", lambda: self._show_sidebar_tab(0), menu=m_view)
        self._reg_act("视图", "大纲", "Ctrl+Shift+O", lambda: self._show_sidebar_tab(1), menu=m_view)
        # v3.38（TAB-4）：上一 / 下一标签页（Ctrl+PgUp / Ctrl+PgDn，N++ 与 VS Code 同款）
        self._reg_act("视图", "上一个标签页", "Ctrl+PgUp", lambda: self._cycle_tab(-1), menu=m_view)
        self._reg_act("视图", "下一个标签页", "Ctrl+PgDown", lambda: self._cycle_tab(1), menu=m_view)
        # v3.38（TAB-8）：Ctrl+Tab MRU 快切面板（松开 Ctrl 或回车确认，Esc 取消）
        self._reg_act("视图", "标签快切面板", "Ctrl+Tab", self._open_tab_switcher, menu=m_view)
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
        self._reg_act("视图", "全屏", "F11", self.toggle_fullscreen, menu=m_view)
        # v3.34（MMD-11）：图表主题入口从视图菜单移到「设置 → 系统设置 → 外观」，
        # 与界面主题 / 字号同处一页集中配置；切换逻辑仍走 _set_mmd_theme
        self._theme_acts = {}

        # ---- 设置 ----
        m_set = self.menuBar().addMenu("设置(&S)")
        self._reg_act("设置", "系统设置…", None, self.show_settings, menu=m_set)
        self._reg_act("设置", "快捷键设置…", None, self.show_shortcut_settings, menu=m_set)

        # ---- 帮助（始终放最后）----
        m_help = self.menuBar().addMenu("帮助(&H)")
        # v3.38（HELP-1）：使用手册（只读渲染视图，滚动浏览全功能参考指南）
        self._reg_act("帮助", "使用手册", "F12", self._show_manual, menu=m_help)
        self._reg_act("帮助", "快捷键一览", "F1", self._show_shortcuts, menu=m_help)
        # v3.32（P0-6①）：检查更新（version.json 只提示不强升）
        self._reg_act("帮助", "检查更新…", None, self.check_update, menu=m_help)
        # v3.32（P0-5②）：复制诊断信息（版本 / 系统 / 依赖 / 最近日志）
        self._reg_act("帮助", "复制诊断信息", None, self.copy_diagnostics, menu=m_help)
        self._reg_act("帮助", "关于", None, self._about, menu=m_help)

        # v3.38（TB-1）：恢复上次的工具栏可见性（隐藏 → 同步显形边缘展开按钮）
        self.set_toolbar_visible(
            self._settings.value("ui/toolbarVisible", True, type=bool), toast=False)

    # ---- v3.38（TB-1）：工具栏展开按钮的摆放与右键菜单 ----
    def _place_tb_expand_btn(self):
        """把边缘展开按钮摆到左侧工具栏原本的顶部位置（菜单栏下方）。"""
        b = getattr(self, "_btn_tb_show", None)
        if b is None:
            return
        top = self.menuBar().height() if self.menuBar() is not None else 0
        b.move(2, top + 18)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_tb_expand_btn()
        self._update_tb_more()   # v3.38（TAB-9）：窗口缩放重算标签溢出态

    def createPopupMenu(self):
        """工具栏 / 菜单栏右键菜单：只给「显示 / 隐藏工具栏」一项。

        复用视图菜单同一个 QAction，避免出现两套互不同步的开关（默认实现只给
        QToolBar 自带的 toggleViewAction，取消勾选后即无法找回）。
        """
        m = QMenu(self)
        act = getattr(self, "_act_toolbar", None)
        if act is not None:
            m.addAction(act)
        return m

    def _set_mmd_theme(self, val):
        """v3.30.19（MMD-7）/ v3.34（MMD-11）：全局图表主题切换。

        持久化 QSettings.mmdTheme 并下发全部已加载视图；旧版原生主题值
        （default/dark/forest/neutral）先归一化到新主题，保证升级无感。
        设置面板下拉与图表块右键子菜单共用本方法，两处状态天然一致。"""
        val = MMD_LEGACY.get(val, val) or ""
        self._settings.setValue("mmdTheme", val)
        self._js_all(f"window.setMmdTheme({js(val)})")
        lbl = MMD_THEME_LABELS.get(val, "")
        self.show_status(f"图表主题：{lbl or val}" if val else "图表主题已更新（跟随界面主题）")

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
        # v3.30.19（MMD-7）/ v3.34（MMD-11）：图表主题随视图加载同步（空 = 跟随界面主题；
        # 旧版值归一化到新主题）
        _mmd0 = self._settings.value('mmdTheme', '') or ''
        self._js_view(view, f"window.setMmdTheme({js(MMD_LEGACY.get(_mmd0, _mmd0))})")
        # v3.31.2（#8/#9）：段首缩进 / 标题 1 居中随视图加载下发
        self._js_view(view, f"window.setParaIndent({int(getattr(self, '_para_indent', 0))})")
        self._js_view(view,
                      f"window.setH1Center({str(bool(getattr(self, '_h1_center', False))).lower()})")
        self._js_view(view, f"window.setSlashMenuConfig({js(json.dumps(self._slash_cfg()))})")
        # v3.32.2（TPL-C）：自定义模板随视图加载下发
        self._js_view(view, f"window.setCustomTemplates({self._custom_templates_js()})")
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
        if not msg:
            return
        # v3.34（MMD-11）：图表主题命令通道 —— 图表块右键子菜单切换后由编辑器侧
        # 推来「##mmdtheme:<id>」，此处落 QSettings 并广播全部视图（RPC 复用 toast 槽）
        if msg.startswith("##mmdtheme:"):
            self._set_mmd_theme(msg[len("##mmdtheme:"):])
            return
        # v3.38（QUO-11）：引用操作一次性提示 —— 编辑器侧首次在引用内按键时
        # 推来 ##quotetip，此处落 QSettings（每台机器只提示一次）
        if msg == "##quotetip":
            if not self._settings.value("quoteTipShown", False, type=bool):
                self._settings.setValue("quoteTipShown", True)
                self.show_status("提示：连续两次回车退出引用；Tab 嵌套 / Shift+Tab 减少嵌套")
            return
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

        v3.38（SYN-3）：同时轮询预览视图，用户滚动预览时反向带动源码。
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
        self._js_view(self._view_prev,
                      "window.pollPrevScroll ? window.pollPrevScroll() : null",
                      self._on_prev_scroll)

    def _on_src_scroll(self, res):
        try:
            data = json.loads(res) if isinstance(res, str) else res
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict) or data.get("idx") is None:
            return
        # v3.38（SYN-3）：用户刚滚动过预览 → 反向同步优先，源码侧暂时让权，
        # 否则光标锁定（cv）会把预览拉回光标段落、抵消用户的预览滚动。
        if time.monotonic() - self._sync_ts_prev2src < 1.2:
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
        pair = (idx, round(frac, 2))
        if pair == self._last_src_pair:   # 无变化不重发（防程序性滚动再触反向）
            return
        self._last_src_pair = pair
        self._sync_ts_src2prev = time.monotonic()
        self._js_view(self._view_prev, f"window.scrollPreviewToBlock({idx},{frac})")

    def _on_prev_scroll(self, res):
        """v3.38（SYN-3）：预览滚动 → 反向带动源码视图。"""
        try:
            data = json.loads(res) if isinstance(res, str) else res
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict) or data.get("idx") is None:
            return
        now = time.monotonic()
        # 这是源码同步程序性设置的滚动位置 → 不回传，切断回环
        if now - self._sync_ts_src2prev < 0.6:
            return
        try:
            idx = int(data["idx"])
            frac = max(0.0, min(1.0, float(data.get("frac", 0))))
        except (TypeError, ValueError, KeyError):
            return
        pair = (idx, round(frac, 2))
        if pair == self._last_prev_pair:  # 预览没动（或仍是上次位置）不重发
            return
        # v3.38（SYN-3）：与上次正向发给预览的目标同块且 frac 微差 → 是正向
        # 程序性落点（两侧参照残余偏差），不反向，杜绝正反向互相追逐
        if (self._last_src_pair is not None and idx == self._last_src_pair[0]
                and abs(frac - self._last_src_pair[1]) < 0.12):
            self._last_prev_pair = pair
            return
        self._last_prev_pair = pair
        self._sync_ts_prev2src = now
        self._js_view(self._view_src, f"window.scrollSrcToBlock({idx},{frac})")

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
            # v3.37（TBL-F3）：blkmenu 块级能力收录进命令面板 ——「想得起就搜得到」；
            # 目标块由 window.__blkCmd 解析（对象选中态优先，否则光标所在块）
            {"group": "编辑", "name": "表格标注…", "seq": "",
             "enabled": True, "run": js_cmd('window.__blkCmd && window.__blkCmd("cap")', "表格标注")},
            {"group": "编辑", "name": "表格还原尺寸", "seq": "",
             "enabled": True, "run": js_cmd('window.__blkCmd && window.__blkCmd("resetsize")', "表格还原尺寸")},
            {"group": "编辑", "name": "复制当前块", "seq": "",
             "enabled": True, "run": js_cmd('window.__blkCmd && window.__blkCmd("dup")', "复制当前块")},
            {"group": "文件", "name": "历史版本", "seq": "Ctrl+Shift+H",
             "enabled": True, "run": self.show_history},
            {"group": "文件", "name": "立即留档（版本快照）", "seq": "",
             "enabled": True, "run": self.manual_snapshot},
            {"group": "文件", "name": "归档整个工作区…", "seq": "",
             "enabled": True, "run": self.archive_workspace},
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

    def manual_snapshot(self):
        """v3.32（P0-3）：「立即留档」—— 不等写盘节流，把当前内容直接存一份
        快照（与自动快照不同：内容相同也保留，用户主动打点应有痕迹）。"""
        if not self.file_path:
            self.show_status("未命名文档暂不支持版本快照 · 保存到文件后可用")
            return

        def cb(md):
            if md is None:
                return
            d = self._history_dir(self.file_path)
            if not d:
                return
            try:
                os.makedirs(d, exist_ok=True)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                fp = os.path.join(d, f"{stamp}.md")
                n = 1
                while os.path.exists(fp):
                    fp = os.path.join(d, f"{stamp}-{n}.md")
                    n += 1
                out = md if md.endswith("\n") else md + "\n"
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(out)
            except OSError as e:
                QMessageBox.warning(self, "留档失败", str(e))
                return
            self.show_status(f"已留档 · {os.path.basename(fp)}")

        self._js_active("window.getMarkdown()", cb)

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
        if self._dual and self._view_src is not None:
            # v3.38（OUT-6）：分屏下双视图同时下发（原只发激活视图，预览侧要等 1~2s poll 收敛）
            self._js_view(self._view_src, f"window.reorderSections({js(payload)})")
            self._js_view(self._view_prev, f"window.reorderSections({js(payload)})")
        else:
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
        （00011_我的图片.png —— 编号自动生成，重名再由 _unique_name 兜底）
        v3.31.3（IMG-11）：名称里已带 5 位编号前缀（如「转相对路径」弹框的
        默认名经二次编号）时先剥掉，杜绝 00001_00001_图片.png 双重编号。"""
        assets = self._assets_dir_for(self.file_path) if self.file_path else None
        count = 0
        if assets and os.path.isdir(assets):
            count = len([n for n in os.listdir(assets)
                         if os.path.isfile(os.path.join(assets, n))])
        stem = os.path.splitext(name)[0] or name      # 名称里带了扩展名则剥掉
        stem = re.sub(r"^\d{5}_", "", stem)           # v3.31.3：剥已有编号前缀
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
        elif act == "imgReplace":
            self._img_replace(idx, str(req.get("mode") or "assets"))   # v3.38

    def _img_replace(self, idx, mode):
        """v3.38（图片报告 §四#9）：右键「替换图片」—— 选图后按当前存储形态替换 src。"""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "替换图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg);;所有文件 (*)")
        if not path:
            return
        name = os.path.basename(path)
        new_src = None
        if mode == "assets":
            new_src = self._save_image_to_assets(src_path=path, filename=name)
        if not new_src:
            try:
                with open(path, "rb") as f:
                    raw = f.read()
            except OSError as e:
                self.show_status(f"替换图片失败：{e}")
                return
            mime = IMG_MIME.get(os.path.splitext(name)[1].lower() or ".png", "image/png")
            new_src = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        self._js_active(f"window.__doImgReplace({int(idx)}, {js(new_src)})")
        self.show_status(f"已替换图片 · {name}")

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
        """相对路径 → 内嵌：读文件转 data URL 写回。
        v3.31.3（IMG-12）：写回成功后删除 assets 里的原文件（避免留下
        不再被引用的孤儿文件）；删除失败（占用 / 只读）仅提示、不影响转换。"""
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
        removed = ""
        try:
            # 安全守卫：只删当前文档 assets 目录内的文件（绝对路径引用的
            # 外部图片不删 —— 那可能是用户其它场景仍在用的源文件）
            assets = self._assets_dir_for(self.file_path) if self.file_path else None
            in_assets = bool(assets) and os.path.normcase(os.path.dirname(os.path.abspath(fp))) == \
                os.path.normcase(os.path.abspath(assets))
            if in_assets:
                os.remove(fp)
                removed = "，原文件已删除"
            else:
                removed = "（图片在 assets 目录外，原文件保留）"
        except OSError as e:
            removed = f"，原文件删除失败（{e}），请手动清理"
        self.show_status(f"图片已转为内嵌 data URL{removed}")

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
        if data.get("border"):
            self._theme_border = str(data.get("border"))   # v3.38（HR-8②）
        if data.get("outline") is not None:
            self._outline_cache = data.get("outline") or []
            self._sidebar.set_outline(data.get("outline"))
        if data.get("pick"):
            self._js_active("window.__wantPick = false")
            self._pick_local_image()
        md = data.get("md")
        dirty = bool(data.get("dirty"))
        # v3.38（TAB-1）：JS 的 dirty 是「自上次 collect 以来有改动」的**边沿**信号
        # （editor.html 读取即清零），只能用来「置脏」；清脏只由保存 / 关闭负责，
        # 否则停止敲键 0.7s 后 • 标记就会消失。per-doc 落盘见 _docs[i]["dirty"]。
        if 0 <= self._cur < len(self._docs):
            _doc = self._docs[self._cur]
            if dirty:
                _doc["dirty"] = True
            self._dirty = bool(_doc.get("dirty"))
        else:
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
        # v3.32（P0-1）：未命名文档影子草稿 —— 10 秒节流写入 %APPDATA%/mdEditor/drafts/，
        # 崩溃 / 断电后启动可恢复；内容清空即删草稿；保存到路径后由 save_file_as 收走。
        if 0 <= self._cur < len(self._docs):
            doc = self._docs[self._cur]
            if not doc.get("path") and md is not None:
                if md.strip():
                    if dirty:
                        self._save_draft(doc, md)
                elif doc.get("draft"):
                    self._remove_draft(doc)
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
            # v3.38（TAB-1）：改读 per-doc dirty —— 顺带修掉「非当前标签不显示 •」
            mark = " • " if doc.get("dirty") else "  "
            # v3.38（TAB-7）：固定标签加 📌 前缀（N++ / 浏览器对标，强提示 + 排左）
            if doc.get("pinned"):
                mark = "📌 " + mark.lstrip()
            self._tabbar.setTabText(i, f"{mark}{name}")
        self._update_tb_more()   # v3.38（TAB-9）：标签溢出态随文本变化重算
        self._update_multi_highlight()   # v3.38（TAB-B）：多选高亮随重建恢复

    # ---- TAB-B：多选标签高亮 ----
    def _update_multi_highlight(self):
        """多选标签着主题强调色；未选中的恢复默认文字色（QColor() = 清除覆盖）。"""
        self._tab_multi = {i for i in self._tab_multi if 0 <= i < len(self._docs)}
        col = QColor(styles.palette(self._theme)["accent"]) if self._tab_multi else None
        for i in range(self._tabbar.count()):
            self._tabbar.setTabTextColor(i, col if (col and i in self._tab_multi)
                                         else QColor())

    # ---- TAB-7：固定标签（Pin）----
    def _toggle_pin(self, idx):
        """固定 / 取消固定：固定标签不可关闭、批量关闭跳过、强制排在未固定之前。"""
        if not (0 <= idx < len(self._docs)):
            return
        doc = self._docs[idx]
        doc["pinned"] = not doc.get("pinned")
        name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
        self.show_status(f"已{'固定' if doc['pinned'] else '取消固定'} · {name}")
        self._enforce_pin_order()
        self._refresh_tab_texts()

    def _enforce_pin_order(self):
        """把固定标签稳定地排到未固定标签之前（必要时重建标签条，保持当前文档）。"""
        order = sorted(range(len(self._docs)),
                       key=lambda i: not self._docs[i].get("pinned"))   # 稳定排序
        if order == list(range(len(self._docs))):
            return
        old_cur = self._cur
        self._docs = [self._docs[i] for i in order]
        self._tabbar.blockSignals(True)
        while self._tabbar.count():
            self._tabbar.removeTab(0)
        for _ in self._docs:
            self._tabbar.addTab("")
        self._tabbar.blockSignals(False)
        if 0 <= old_cur < len(self._docs):
            self._cur = order.index(old_cur)
            self._tabbar.setCurrentIndex(self._cur)

    # ---- TAB-9：标签溢出下拉（N++ / VS Code 对标）----
    def _update_tb_more(self):
        """标签总宽超出标签栏可视宽度时启用 » 下拉按钮。"""
        if not hasattr(self, "_btn_tb_more"):
            return
        tb = self._tabbar
        overflow = (tb.count() > 1 and tb.sizeHint().width() > tb.width() + 2)
        self._btn_tb_more.setEnabled(overflow)
        self._btn_tb_more.setToolTip("所有标签页" if overflow else "所有标签页（无溢出）")

    def _show_tb_more_menu(self):
        m = QMenu(self)
        for i, doc in enumerate(self._docs):
            name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
            text = ("📌 " if doc.get("pinned") else "") + ("• " if doc.get("dirty") else "") + name
            a = m.addAction(("● " if i == self._cur else "    ") + text)
            a.triggered.connect(lambda _c=False, k=i: self._tabbar.setCurrentIndex(k))
        m.exec(self._btn_tb_more.mapToGlobal(
            self._btn_tb_more.rect().bottomLeft()))

    def _update_title(self):
        name = os.path.basename(self.file_path) if self.file_path else "未命名"
        star = " •" if self._dirty else ""
        self.setWindowTitle(f"{name}{star} — {APP_NAME}")

    # ================= 多文档标签 =================
    def _add_doc(self, path=None, text=None):
        # v3.38（TAB-1）：per-doc dirty —— 每个标签自带修改标记（切走再切回不丢）
        self._docs.append({"path": path, "content": text, "dirty": False})
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
        # v3.38（TAB-B）：普通切换即放弃多选（Ctrl/Shift 路径在 eventFilter 已消费事件）
        if self._tab_multi:
            self._tab_multi.clear()
            self._multi_anchor = -1
            self._update_multi_highlight()
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
        # v3.38（TAB-1）：切走前把当前文档的修改标记存回 doc（旧实现直接丢弃，
        # 切走再切回 • 就没了，「关闭所有未修改」也无从判断）
        if 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["dirty"] = bool(self._dirty)
        if self._cur >= 0 and self._cur < len(self._docs) and md is not None:
            self._docs[self._cur]["content"] = md
        target = self._pending_switch
        self._switching = False
        if target < 0 or target >= len(self._docs):
            return
        self._cur = target
        doc = self._docs[target]
        # v3.38（TAB-8）：切换完成 → 该文档移到 MRU 最前
        self._mru = [doc] + [x for x in self._mru if x is not doc]
        self.file_path = doc.get("path")
        text = doc.get("content")
        if text is None:
            text = self._read_file(self.file_path) if self.file_path else ""
            doc["content"] = text
        self._last_preview_md = None
        self._push_doc_dir()   # 图片相对路径随文档目录变化（先于正文下发）
        self._push_text(text)
        self._dirty = bool(doc.get("dirty"))   # v3.38（TAB-1）：恢复该文档自己的修改标记
        self._update_title()
        self._refresh_tab_texts()
        if self.file_path:
            self._sidebar.set_root(self.file_path)
            self._status.setText(f"已打开 · {self.file_path}")
        else:
            self._sidebar.clear_current_file()   # v3.38（OUT-3）：清除残留的文件上下文与高亮
            self.show_status("未命名文档")
        self._remember_last_session()   # v3.38（OUT-5）
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
        # v3.38（TAB-7）：拖动后固定标签仍须排在未固定之前
        self._enforce_pin_order()

    def _close_tab(self, idx):
        if idx < 0 or idx >= len(self._docs) or self._switching:
            return
        doc = self._docs[idx]
        # v3.38（TAB-7）：固定标签不可关闭（关闭按钮 / Ctrl+W / 菜单统一入口守卫）
        if doc.get("pinned"):
            name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
            self.show_status(f"标签已固定，请先取消固定再关闭 · {name}")
            return

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
                elif btn == QMessageBox.Discard:
                    self._remove_draft(doc)   # v3.32（P0-1）：明确丢弃 → 草稿一并删除
            self._drop_doc(idx)   # v3.38（TAB-3）：关闭即压入回溯栈（Ctrl+Shift+T 可恢复）
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
            do_close(self._capture_current_md())
        else:
            do_close()

    # ============ 标签页：选中 / 关闭 / 批量 / 复制路径（v3.38 TAB-1~TAB-6） ============
    # 设计依据：docs/archive/标签页右键菜单方案-批量关闭与复制路径-v3.38.md
    CLOSED_STACK_MAX = 10

    def _capture_current_md(self):
        """同步取回当前视图的实时 Markdown 并回写当前 doc。

        批量关闭 / 关闭前判定「未命名非空」都要用实时内容——doc["content"] 只在
        切换与保存时才回写，停在编辑器里敲的字还留在 WebEngine 侧。
        """
        from PySide6.QtCore import QEventLoop
        box = {}
        loop = QEventLoop()

        def cb(md):
            box["md"] = md
            loop.quit()

        self._js_active("window.getMarkdown()", cb)
        loop.exec()
        md = box.get("md")
        if md is not None and 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["content"] = md
        return md

    def _doc_text(self, idx):
        """第 idx 个文档的 Markdown。

        当前文档取**实时内容**（编辑器里的字还没回写 doc）；其余文档直接取缓存 ——
        切走时 `_on_switch_capture` 已把实时内容写回，缓存即最新，无需再切视图取回
        （切视图取回有「页面还没渲染完就开始读」的竞态，反而会读到上一个文档的内容）。
        """
        if idx == self._cur:
            md = self._capture_current_md()
            if md is not None:
                return md
        return self._docs[idx].get("content") or ""

    def _drop_doc(self, idx, remember=True):
        """移除第 idx 个文档（缓存 + 标签），按需压入「重新打开」回溯栈。"""
        doc = self._docs.pop(idx)
        self._tabbar.removeTab(idx)
        if remember:
            self._closed_stack.append(dict(doc))
            del self._closed_stack[:-self.CLOSED_STACK_MAX]
        return doc

    def _unnamed_nonempty(self, idx):
        """未命名且非空 —— 沿用 _close_tab 的确认口径。"""
        doc = self._docs[idx]
        if doc.get("path") is not None:
            return False
        if idx == self._cur:
            return bool(self._dirty or (doc.get("content") or "").strip())
        return bool((doc.get("content") or "").strip())

    def _save_doc_as_sync(self, idx):
        """给指定标签弹「另存为」并**同步**落盘（批量流程用，避免异步写入与切标签交错）。"""
        doc = self._docs[idx]
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Markdown 文件", self._dlg_start("save", doc.get("path") or "未命名.md"),
            "Markdown 文件 (*.md);;所有文件 (*.*)")
        if not path:
            return False
        path = os.path.abspath(path)
        md = self._doc_text(idx)
        text = md if md.endswith("\n") else md + "\n"
        try:
            self.snapshot_history(path, text)
            self._write_text(path, text)
        except OSError as e:
            QMessageBox.critical(self, "保存失败", f"{path}\n{e}")
            return False
        self._remember_dir("save", path)
        doc["path"] = path
        doc["content"] = md
        doc["dirty"] = False
        if idx == self._cur:
            self.file_path = path
            self._dirty = False
            self._push_doc_dir()
        self._remove_draft(doc)                  # v3.32（P0-1）：有路径后草稿收走
        self._remember_last_session()            # v3.38（OUT-5）
        self._refresh_tab_texts()
        self._update_title()
        return True

    def _perform_batch_close(self, idxs, discard_unnamed=False):
        """倒序移除给定索引集合，随后修正 _cur / 选中态 / 正文（索引不漂移）。"""
        self._clear_tab_multi()   # v3.38（TAB-B）：关闭后索引漂移，多选集作废
        idxset = {i for i in idxs if 0 <= i < len(self._docs)}
        if not idxset:
            return 0
        old_cur = self._cur
        cur_closed = old_cur in idxset
        closed = 0
        for i in sorted(idxset, reverse=True):
            if discard_unnamed and self._docs[i].get("path") is None:
                self._remove_draft(self._docs[i])   # 明确丢弃 → 草稿一并删除
            self._drop_doc(i)
            closed += 1
        if not self._docs:
            self._cur = -1
            self.file_path = None
            self._switching = False
            self._dirty = False
            self._add_doc(path=None, text="")        # 沿用「空栈自动补空白页」
            self._update_title()
            self._refresh_tab_texts()
            return closed
        if cur_closed:
            # 当前文档被关掉：置 -1 后走激活路径，让 _on_tab_clicked 从缓存装载正文
            # （否则会被 idx == self._cur 的短路守卫挡掉）
            self._cur = -1
            self._switching = False
            new_idx = min(max(old_cur - sum(1 for i in idxset if i < old_cur), 0),
                          len(self._docs) - 1)
            self._tabbar.setCurrentIndex(new_idx)
            self._on_tab_clicked(new_idx)
        else:
            # 当前文档保留：只同步索引漂移，**不要**从 doc["content"] 重载
            # （当前文档的缓存可能滞后于编辑器，重载会吞掉正在输入的内容）
            self._cur = old_cur - sum(1 for i in idxset if i < old_cur)
            self._tabbar.blockSignals(True)
            self._tabbar.setCurrentIndex(self._cur)
            self._tabbar.blockSignals(False)
        self._refresh_tab_texts()
        self._update_title()
        return closed

    def _batch_close(self, idxs, ask=True):
        """批量关闭确认链（Notepad++ 对标）：

        未保存文档（含**已命名但 dirty** 的）→ 一次汇总确认
        「全部保存 / 全部不保存 / 取消」→ 倒序执行，任一保存被取消则整批中止。
        """
        if self._switching:
            return 0
        idxs = sorted({i for i in idxs if 0 <= i < len(self._docs)})
        if not idxs:
            return 0
        if self._cur in idxs:
            self._capture_current_md()               # 实时内容回写，保证判定与保存内容正确
            self._docs[self._cur]["dirty"] = bool(self._dirty)   # 当前文档脏标记取实时
        need_unnamed = [i for i in idxs if self._unnamed_nonempty(i)]
        # v3.38（TAB-B）：已命名未保存的文档**必须**进确认（旧版只确认未命名，
        # 有路径的 dirty 文档会被静默关闭丢内容）
        need_named = [i for i in idxs if self._docs[i].get("path") is not None
                      and self._docs[i].get("dirty")]
        need = need_unnamed + need_named
        discard = not need
        if need and ask:
            box = QMessageBox(self)
            box.setWindowTitle("批量关闭")
            box.setIcon(QMessageBox.Question)
            names = []
            for i in need[:8]:
                nm = os.path.basename(self._docs[i]["path"]) \
                    if self._docs[i].get("path") else "未命名"
                names.append(f"    {nm}")
            if len(need) > 8:
                names.append(f"    …等共 {len(need)} 个")
            box.setText(f"要关闭的 {len(idxs)} 个标签页中，{len(need)} 个文档未保存，"
                        f"是否保存后关闭？\n" + "\n".join(names))
            b_save = box.addButton("全部保存", QMessageBox.AcceptRole)
            b_skip = box.addButton("全部不保存", QMessageBox.DestructiveRole)
            box.addButton("取消", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not b_save and box.clickedButton() is not b_skip:
                return 0
            if box.clickedButton() is b_save:
                for i in sorted(need_unnamed, reverse=True):
                    if not self._save_doc_as_sync(i):
                        return 0                     # 用户取消 → 整批中止，不动任何标签
                for i in sorted(need_named, reverse=True):
                    if not self._save_named_doc_sync(i):
                        return 0
            else:
                discard = True
        return self._perform_batch_close(idxs, discard_unnamed=discard)

    def _save_named_doc_sync(self, idx):
        """v3.38（TAB-B）：已命名文档同步落盘（批量「全部保存」用）。"""
        doc = self._docs[idx]
        if doc.get("path") is None:
            return False
        md = self._doc_text(idx)
        if md is None:
            return False
        text = md if md.endswith("\n") else md + "\n"
        try:
            self.snapshot_history(doc["path"], text)
            self._write_text(doc["path"], text)
        except OSError as e:
            QMessageBox.critical(self, "保存失败", f"{doc['path']}\n{e}")
            return False
        self._remember_dir("save", doc["path"])
        doc["content"] = md
        doc["dirty"] = False
        if idx == self._cur:
            self._dirty = False
        self._refresh_tab_texts()
        return True

    def _clear_tab_multi(self):
        self._tab_multi.clear()
        self._multi_anchor = -1
        self._update_multi_highlight()

    def _close_all_tabs(self):
        """v3.38（TAB-B）：关闭所有标签页（固定标签跳过，全固定则提示）。"""
        if 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["dirty"] = bool(self._dirty)
        idxs = [i for i in range(len(self._docs)) if not self._docs[i].get("pinned")]
        if not idxs:
            self.show_status("没有可关闭的标签页（固定标签需先取消固定）")
            return
        n = self._batch_close(idxs)
        if n:
            self.show_status(f"已关闭 {n} 个标签页")

    def _close_unmodified(self):
        """关闭所有未修改的标签（右键菜单项）；固定标签跳过（TAB-7 语义：不许自动关）。"""
        if 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["dirty"] = bool(self._dirty)   # 实时脏标记优先
        idxs = [i for i in range(len(self._docs))
                if not self._docs[i].get("dirty") and not self._docs[i].get("pinned")]
        if not idxs:
            self.show_status("没有未修改的标签页")
            return
        n = self._batch_close(idxs)
        if n:
            self.show_status(f"已关闭 {n} 个未修改的标签页")

    def _open_terminal(self, path):
        """v3.38（TAB-10）：在文件所在目录打开 PowerShell。"""
        d = os.path.dirname(path or "") or None
        try:
            subprocess.Popen("start powershell", shell=True, cwd=d)
            self.show_status(f"已打开终端 · {d or '当前目录'}")
        except OSError as e:
            QMessageBox.warning(self, "打开终端失败", str(e))

    def _when_idle(self, fn):
        """等切换锁释放后再执行（右键即选中的异步窗口期保护）。"""
        if self._switching:
            QTimer.singleShot(20, lambda: self._when_idle(fn))
            return
        fn()

    def _on_tab_menu(self, pos):
        """标签右键菜单（对标 Notepad++）：先选中被点标签，再弹菜单。"""
        idx = self._tabbar.tabAt(pos)
        if idx < 0:
            idx = self._cur
        if not (0 <= idx < len(self._docs)):
            return
        # v3.38（TAB-B）：多选感知 —— 右键命中选中集 → 选中与当前标签都保持不动
        #（N++ 语义：对选中集操作）；右键在选中集外 → 放弃多选走普通路径
        multi = {i for i in self._tab_multi if 0 <= i < len(self._docs)} \
            if idx in self._tab_multi else set()
        if self._tab_multi and not multi:
            self._tab_multi.clear()
            self._multi_anchor = -1
            self._update_multi_highlight()
        if not multi and idx != self._cur:
            self._tabbar.setCurrentIndex(idx)        # 右键即选中
        doc = self._docs[idx]
        has_path = doc.get("path") is not None
        # v3.38（TAB-B 修正）：_add_doc 的文档没有 pinned 键 → get 返回 None，
        # setChecked(None) 会 TypeError 令整个右键菜单弹不出来，必须转 bool
        pinned = bool(doc.get("pinned"))
        last = len(self._docs) - 1
        m = QMenu(self)
        # v3.38（TAB-B）：多选生效 → 首位给「关闭选中标签页」+「取消多选」（N++ 对标）
        if multi:
            a = m.addAction(f"关闭选中的 {len(multi)} 个标签页")
            a.triggered.connect(lambda: self._when_idle(
                lambda: self._batch_close(sorted(multi))))
            a = m.addAction("取消多选")
            a.triggered.connect(self._clear_tab_multi)
            m.addSeparator()
        # v3.38（TAB-7）：固定 / 取消固定（Notepad++ 对标第一项）
        a = m.addAction("固定 / 取消固定标签")
        a.setCheckable(True)
        a.setChecked(pinned)
        a.triggered.connect(lambda: self._when_idle(lambda: self._toggle_pin(idx)))
        a = m.addAction("关闭\tCtrl+W")
        a.setEnabled(not pinned)             # TAB-7：固定标签不可直接关闭
        a.triggered.connect(lambda: self._when_idle(lambda: self._close_tab(idx)))
        a = m.addAction("关闭其它所有")
        a.triggered.connect(lambda: self._when_idle(lambda: self._batch_close(
            [i for i in range(len(self._docs)) if i != idx and not self._docs[i].get("pinned")])))
        a = m.addAction("关闭左侧所有")
        a.setEnabled(any(not self._docs[i].get("pinned") for i in range(idx)))
        a.triggered.connect(lambda: self._when_idle(lambda: self._batch_close(
            [i for i in range(idx) if not self._docs[i].get("pinned")])))
        a = m.addAction("关闭右侧所有")
        a.setEnabled(any(not self._docs[i].get("pinned") for i in range(idx + 1, len(self._docs))))
        a.triggered.connect(lambda: self._when_idle(
            lambda: self._batch_close(
                [i for i in range(idx + 1, len(self._docs)) if not self._docs[i].get("pinned")])))
        a = m.addAction("关闭所有未修改")
        a.triggered.connect(lambda: self._when_idle(self._close_unmodified))
        a = m.addAction("关闭所有标签页")
        a.triggered.connect(lambda: self._when_idle(self._close_all_tabs))
        m.addSeparator()
        a = m.addAction("在资源管理器中显示")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self.show_in_explorer(doc.get("path")))
        # v3.38（TAB-10）：在终端中打开（文件所在目录起 PowerShell）
        a = m.addAction("在终端中打开")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self._open_terminal(doc.get("path")))
        m.addSeparator()
        a = m.addAction("复制文件名")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self._copy_to_clip(os.path.basename(doc.get("path") or ""), "文件名"))
        a = m.addAction("复制文件路径")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self._copy_to_clip(doc.get("path") or "", "文件路径"))
        a = m.addAction("复制所在目录")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self._copy_to_clip(os.path.dirname(doc.get("path") or ""), "所在目录"))
        m.exec(self._tabbar.mapToGlobal(pos))

    def _copy_to_clip(self, text, what):
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.show_status(f"已复制{what}：{text}")

    # ---- TAB-3：重新打开关闭的标签 ----
    def _reopen_closed_tab(self):
        if not self._closed_stack:
            self.show_status("没有可重新打开的标签页")
            return
        doc = self._closed_stack.pop()
        idx = self._add_doc(path=doc.get("path"), text=doc.get("content"))
        self._docs[idx]["dirty"] = bool(doc.get("dirty"))
        self._refresh_tab_texts()
        name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
        self.show_status(f"已重新打开 · {name}")

    # ---- TAB-4：上一个 / 下一个标签 ----
    def _cycle_tab(self, step):
        n = len(self._docs)
        if n < 2:
            return
        self._tabbar.setCurrentIndex((self._cur + step) % n)

    # ---- TAB-8：Ctrl+Tab MRU 快切面板 ----
    class _TabSwitcher(QDialog):
        """无边框快切浮层：按 MRU 列出标签，Ctrl+Tab / Ctrl+Shift+Tab 移动选区，
        松开 Ctrl（或回车）确认，Esc 取消。"""

        def __init__(self, win, entries, sel):
            super().__init__(win, Qt.Dialog | Qt.FramelessWindowHint)
            self.setWindowTitle("切换标签页")
            self._win = win
            self._entries = entries          # [(idx, 文本), ...]
            self._sel = sel
            self._result_idx = -1
            lay = QVBoxLayout(self)
            lay.setContentsMargins(10, 10, 10, 10)
            self._list = QLabel(self)
            self._list.setTextFormat(Qt.RichText)
            lay.addWidget(self._list)
            self._render()

        def _render(self):
            rows = []
            for k, (idx, text) in enumerate(self._entries):
                cur = "▶ " if k == self._sel else "&nbsp;&nbsp;&nbsp;"
                rows.append(f"<div style='padding:2px 6px;{'' if k != self._sel else 'background:#3d6db5;color:#fff;border-radius:3px;'}'>"
                            f"{cur}{text}</div>")
            self._list.setText("".join(rows))

        def keyPressEvent(self, ev):
            k, mods = ev.key(), ev.modifiers()
            if k in (Qt.Key_Tab, Qt.Key_Backtab) and mods & Qt.ControlModifier:
                d = 1 if k == Qt.Key_Tab else -1
                n = len(self._entries)
                self._sel = (self._sel + d) % n
                self._render()
                ev.accept()
                return
            if k in (Qt.Key_Return, Qt.Key_Enter):
                self.accept()
                ev.accept()
                return
            if k == Qt.Key_Escape:
                self.reject()
                ev.accept()
                return
            super().keyPressEvent(ev)

        def keyReleaseEvent(self, ev):
            # 松开 Ctrl = 确认（VS Code 语义）
            if ev.key() == Qt.Key_Control:
                self.accept()
                ev.accept()
                return
            super().keyReleaseEvent(ev)

        def run(self):
            self.exec()
            return self._entries[self._sel][0] if self.result() else -1

    def _open_tab_switcher(self):
        self._mru = [d for d in self._mru
                     if any(d is x for x in self._docs)]   # 惰性剔除已关闭
        if len(self._docs) < 2:
            self.show_status("只有一个标签页")
            return
        # MRU 序优先，缺项（从未切过的标签）按标签条顺序补尾
        order = [self._docs.index(d) if any(d is x for x in self._docs) else -1
                 for d in self._mru]
        order = [i for i in order if i >= 0]
        order += [i for i in range(len(self._docs)) if i not in order]
        entries = []
        for i in order:
            doc = self._docs[i]
            name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
            if doc.get("dirty"):
                name = "● " + name
            if doc.get("pinned"):
                name = "📌 " + name
            entries.append((i, name))
        sel = 1 if len(entries) > 1 else 0
        idx = self._TabSwitcher(self, entries, sel).run()
        if 0 <= idx < len(self._docs) and idx != self._cur:
            self._tabbar.setCurrentIndex(idx)

    # ---- TAB-6：全部保存 ----
    def save_all(self) -> bool:
        """批量保存「有路径且已修改」的文档；未命名文档不批量弹窗，仅在提示里计数。"""
        n = 0
        skipped = 0
        for i, doc in enumerate(list(self._docs)):
            if not doc.get("dirty"):
                continue
            if not doc.get("path"):
                skipped += 1
                continue
            md = self._doc_text(i)
            if md is None:
                continue
            text = md if md.endswith("\n") else md + "\n"
            try:
                self.snapshot_history(doc["path"], text)
                self._write_text(doc["path"], text)
            except OSError as e:
                QMessageBox.critical(self, "保存失败", f"{doc['path']}\n{e}")
                continue
            doc["content"] = md
            doc["dirty"] = False
            if i == self._cur:
                self._dirty = False
            n += 1
        if 0 <= self._cur < len(self._docs):
            self._dirty = bool(self._docs[self._cur].get("dirty"))
        self._refresh_tab_texts()
        self._update_title()
        msg = f"已保存 {n} 个文档" if n else "没有需要保存的修改"
        if skipped:
            msg += f"（{skipped} 个未命名文档请单独另存）"
        self.show_status(msg)
        return n > 0

    # ---- TAB-5：标签栏鼠标手势见文件末尾 eventFilter（QMainWindow 只能有一个
    #      eventFilter 定义，末位定义生效 —— 早期在此处另写一份会被静默遮蔽）----

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

    # ================= v3.32（P0-1）未命名文档影子草稿 =================
    def _save_draft(self, doc, md):
        """未命名文档内容暂存为影子草稿（10 秒节流）。有路径的文档不走此路径。"""
        if os.environ.get("MDEDITOR_SKIP_DRAFT"):
            return   # 测试进程禁用（_runner.py 统一设置），避免污染用户草稿目录
        try:
            os.makedirs(DRAFT_DIR, exist_ok=True)
        except OSError:
            return
        fp = doc.get("draft")
        if not fp:
            fp = os.path.join(DRAFT_DIR, "draft-%s-%d.md"
                              % (time.strftime("%Y%m%d-%H%M%S"), abs(id(doc)) % 100000))
            doc["draft"] = fp
        now = time.time()
        if now - doc.get("draft_ts", 0) < 10:
            return
        try:
            out = md if md.endswith("\n") else md + "\n"
            with open(fp, "w", encoding="utf-8") as f:
                f.write(out)
        except OSError:
            return
        doc["draft_ts"] = now
        self.show_status("草稿已自动暂存（未命名文档，崩溃可恢复）")

    def _remove_draft(self, doc):
        """草稿收走 / 清空时删除对应草稿文件。"""
        fp = doc.pop("draft", None)
        doc.pop("draft_ts", None)
        if fp:
            try:
                if os.path.exists(fp):
                    os.remove(fp)
            except Exception as e:   # noqa: BLE001 — 删除失败不影响主流程
                _log.debug("草稿删除失败: %s (%s)", fp, e)

    def check_draft_recovery(self):
        """v3.32（P0-1）：启动时检测孤儿草稿（上次会话未保存的未命名文档），
        弹窗展示预览与时间，问是否恢复；选择忽略则标记 .dismissed 不再打扰。"""
        if os.environ.get("MDEDITOR_SKIP_DRAFT") or not os.path.isdir(DRAFT_DIR):
            return
        drafts = []
        for name in os.listdir(DRAFT_DIR):
            if not name.endswith(".md"):
                continue
            fp = os.path.join(DRAFT_DIR, name)
            try:
                if os.path.getsize(fp) > 0:
                    drafts.append((fp, os.path.getmtime(fp)))
            except OSError:
                continue
        if not drafts:
            return
        drafts.sort(key=lambda x: x[1], reverse=True)
        try:
            with open(drafts[0][0], "r", encoding="utf-8", errors="replace") as f:
                head = f.read(200)
        except OSError:
            return
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(drafts[0][1]))
        detail = "\n".join(
            "· %s（%s）" % (os.path.basename(fp),
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt)))
            for fp, mt in drafts)
        btn = QMessageBox.question(
            self, "发现未恢复内容",
            f"检测到 {len(drafts)} 份未命名文档的自动暂存草稿，"
            f"可能是上次异常退出遗留。\n\n"
            f"最近一份预览（{when}）：\n「{head}」\n\n"
            f"是否恢复到编辑器？\n\n{detail}",
            QMessageBox.Yes | QMessageBox.No)
        if btn != QMessageBox.Yes:
            for fp, _mt in drafts:      # 忽略：改名归档，不再提示也不丢失
                try:
                    os.replace(fp, fp + ".dismissed")
                except OSError:
                    pass
            return
        for fp, _mt in drafts:
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            idx = self._add_doc(path=None, text=text)
            if 0 <= idx < len(self._docs):
                self._docs[idx]["draft"] = fp       # 草稿跟随文档继续更新，保存后收走
        self.show_status("已恢复草稿内容 · 保存到文件后自动清理")

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
        self._remember_last_session()   # v3.38（OUT-5）

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
        if 0 <= self._cur < len(self._docs):
            self._remove_draft(self._docs[self._cur])   # v3.32（P0-1）：有路径后草稿收走
        self._remember_last_session()   # v3.38（OUT-5）
        self.save_file()
        return True

    # ================= 导出 =================
    def _export_selfcheck(self, md, kinds):
        """v3.32（P0-4③ / P1-10①）：导出前"交付自检"——扫描文档里会降级 /
        需联网的元素，弹窗明示后果；返回 True 继续、False 取消。
        kinds: 'docx'|'epub'（块级公式降源码、图表位图化）或 'html'|'pdf'。"""
        if not md:
            return True
        math_n = len(re.findall(r"^```math\s*$", md, flags=re.M))
        mmd_n = len(re.findall(r"^```mermaid\s*$", md, flags=re.M))
        img_n = len(re.findall(r"!\[[^\]]*\]\((?:https?:)?//", md)) \
            + len(re.findall(r"<img[^>]*\ssrc=[\"'](?:https?:)?//", md))
        lines = []
        if kinds in ("docx", "epub") and math_n:
            lines.append(f"· {math_n} 处块级公式：导出后将保留 LaTeX 源码并加标注（暂不渲染）")
        if kinds in ("docx", "epub") and mmd_n:
            lines.append(f"· {mmd_n} 张 Mermaid 图表：将以已渲染的位图嵌入（不可再编辑）")
        if img_n:
            lines.append(f"· {img_n} 张网络图片：需联网才能显示（本地图片不受影响）")
        if not lines:
            return True
        ret = QMessageBox.question(
            self, "导出前自检",
            "本文档包含以下导出时需要注意的元素：\n\n" + "\n".join(lines)
            + "\n\n是否继续导出？",
            QMessageBox.Yes | QMessageBox.No)
        return ret == QMessageBox.Yes

    def _export_selfcheck_remote(self, n):
        """v3.32（P0-4③）：仅网络图片的自检（HTML / PDF 导出路径）。"""
        ret = QMessageBox.question(
            self, "导出前自检",
            f"本文档包含 {n} 张网络图片（http/https），查看时需联网加载；"
            "本地图片与公式 / 图表已内嵌，离线可用。\n\n是否继续导出？",
            QMessageBox.Yes | QMessageBox.No)
        return ret == QMessageBox.Yes

    def _export_done(self, label, path):
        """v3.32（P1-2①）：导出完成的收尾动作——打开该文件 / 打开所在文件夹。"""
        box = QMessageBox(self)
        box.setWindowTitle("导出完成")
        box.setText(f"已导出 {label}：\n{path}")
        b_open = box.addButton("打开该文件", QMessageBox.YesRole)
        b_dir = box.addButton("打开所在文件夹", QMessageBox.ActionRole)
        box.addButton("完成", QMessageBox.NoRole)
        box.exec()
        clicked = box.clickedButton()
        try:
            if clicked is b_open:
                os.startfile(path)                     # noqa: S606
            elif clicked is b_dir:
                os.startfile(os.path.dirname(path) or ".")   # noqa: S606
        except OSError:
            self.show_status("无法打开：系统缺少关联程序")
        return

    def archive_workspace(self):
        """v3.32（P0-7）：把当前工作区（当前文档所在目录或侧栏根目录）
        打包为带时间戳的 zip —— 含全部 .md / assets / .mdeditor-history，
        作为"本地唯一副本"的最低成本容灾出口。"""
        root = ""
        for cand in (self._doc_dir(), getattr(self._sidebar, "_cur_dir", "")):
            if cand and os.path.isdir(cand):
                root = os.path.abspath(cand)
                break
        if not root:
            QMessageBox.information(
                self, "归档工作区",
                "当前没有已保存的文档或已打开的文件夹，没有可归档的工作区。")
            return
        default = os.path.join(os.path.dirname(root) or root,
                               "%s-workspace-%s.zip"
                               % (os.path.basename(root), time.strftime("%Y%m%d-%H%M%S")))
        path, _ = QFileDialog.getSaveFileName(
            self, "归档整个工作区", default, "压缩包 (*.zip)")
        if not path:
            return
        n_file = 0
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [d for d in dirnames
                                   if d not in ("__pycache__", "$RECYCLE.BIN")]
                    for name in filenames:
                        fp = os.path.join(dirpath, name)
                        if os.path.abspath(fp) == os.path.abspath(path):
                            continue        # 归档包自身落在工作区内时跳过
                        try:
                            zf.write(fp, os.path.relpath(fp, root))
                            n_file += 1
                        except OSError:
                            continue
        except (OSError, zipfile.BadZipFile) as e:
            QMessageBox.warning(self, "归档失败", str(e))
            return
        self.show_status(f"已归档工作区 · {n_file} 个文件 → {path}")
        QMessageBox.information(
            self, "归档完成",
            f"已归档 {n_file} 个文件（含历史快照与图片资产）：\n{path}\n\n"
            "建议定期归档并复制到另一块磁盘 / 网盘，避免单点丢失。")

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
            # v3.32（P0-4③）：网络图片需查看端联网，先明示（本地图片已内嵌）
            remote = len(re.findall(r"<img[^>]*\ssrc=[\"'](?:https?:)?//", html))
            if remote and not self._export_selfcheck_remote(remote):
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
            self._export_done("HTML", path)
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
            self._export_done("PDF", path)
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
            # v3.32（P0-4③/P1-10①）：导出前"交付自检"——明示降级项再让用户决定
            if not self._export_selfcheck(md, kind):
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
            ok, msg = exporters.write_epub(
                md, path, base_dir, title, mmd_png=mmd_png,
                border_color=getattr(self, "_theme_border", "") or "#ddd")   # v3.38（HR-8②）
        self.show_status(msg)
        if not ok:
            QMessageBox.warning(self, f"导出 {label} 失败", msg)
        else:
            self._export_done(label, path)

    def export_docx(self):
        self._export_document("docx")

    def export_epub(self):
        self._export_document("epub")

    # ================= 杂项 =================
    def check_update(self):
        """v3.32（P0-6①）：检查更新 —— 拉取 version.json（{"version","url"}），
        只提示不强升；URL 可在 QSettings.updateUrl 覆盖，留空提示未配置。"""
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
        from PySide6.QtCore import QUrl as _QUrl
        url = str(self._settings.value("updateUrl", "") or "") or UPDATE_URL
        if not url:
            QMessageBox.information(
                self, "检查更新",
                f"当前版本 v{APP_VERSION}。\n\n尚未配置更新源（updateUrl）。\n"
                "发布新版本时请到下载页获取最新安装包。")
            return
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "检查更新", "更新源地址无效（须为 http/https）。")
            return
        self.show_status("正在检查更新…")
        nam = QNetworkAccessManager(self)

        def _done(reply):
            reply.deleteLater()
            if reply.error() != QNetworkReply.NoError:
                QMessageBox.warning(
                    self, "检查更新",
                    f"无法连接更新源：\n{reply.errorString()}\n\n"
                    f"当前版本 v{APP_VERSION}。请检查网络后重试，或直接到下载页查看。")
                return
            try:
                info = json.loads(bytes(reply.readAll()).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                QMessageBox.warning(self, "检查更新", "更新源返回内容不是有效的 version.json。")
                return
            remote = str(info.get("version") or "").strip()
            if not remote:
                QMessageBox.warning(self, "检查更新", "version.json 中缺少 version 字段。")
                return
            if self._ver_ge(remote, APP_VERSION):
                QMessageBox.information(self, "检查更新",
                                        f"已是最新版本（v{APP_VERSION}）。")
                return
            btn = QMessageBox.question(
                self, "发现新版本",
                f"当前版本 v{APP_VERSION}\n最新版本 v{remote}\n"
                f"{info.get('note') or ''}\n\n是否前往下载页？",
                QMessageBox.Yes | QMessageBox.No)
            if btn == QMessageBox.Yes and info.get("url"):
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(_QUrl(str(info["url"])))

        nam.finished.connect(_done)
        nam.get(QNetworkRequest(_QUrl(url)))

    @staticmethod
    def _ver_ge(a, b):
        """版本号比较：a >= b（按 . 分段数值比较，长度不齐补 0）。"""
        pa = [int(x) for x in re.findall(r"\d+", a)] or [0]
        pb = [int(x) for x in re.findall(r"\d+", b)] or [0]
        n = max(len(pa), len(pb))
        pa += [0] * (n - len(pa))
        pb += [0] * (n - len(pb))
        return pa >= pb

    def copy_diagnostics(self):
        """v3.32（P0-5②）：把版本 / 系统 / 依赖 / 最近日志拼成诊断文本复制到剪贴板，
        用户报障时一次给全信息。"""
        import platform
        import PySide6
        pandoc = self._pandoc_exe()
        lines = [
            f"版本: mdEditor v{APP_VERSION}",
            f"系统: {platform.platform()}",
            f"Python: {platform.python_version()}　PySide6: {PySide6.__version__}",
            f"主题: {self._theme}　自动保存: {'开' if self._autosave else '关'}",
            f"pandoc: {pandoc or '未检测到（导出 Word/EPUB 将用内置转换）'}",
        ]
        try:
            log_fp = os.path.join(LOG_DIR, "mdEditor.log")
            with open(log_fp, "r", encoding="utf-8", errors="replace") as f:
                tail = [ln.rstrip() for ln in f.readlines()[-50:]]
            lines.append("--- 最近日志（50 行）---")
            lines.extend(tail or ["（日志为空）"])
        except OSError:
            lines.append("（日志文件不可读）")
        QApplication.clipboard().setText("\n".join(lines))
        self.show_status("诊断信息已复制到剪贴板，可粘贴给开发者")

    def _about(self):
        """v3.29d（UX #29）：关于页显示版本号，并提供「查看更新日志」入口。"""
        ret = QMessageBox.question(
            self, "关于",
            f"<b>{APP_NAME}</b>　<span style='color:#888;'>v{APP_VERSION}</span><br>"
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

    # ---- v3.38（HELP-1）：使用手册 ----
    def _manual_md(self):
        """读取使用手册 Markdown（开发态 src/，打包态 _internal/）。"""
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "使用手册.md")
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return "# 使用手册\n\n手册文件缺失：" + p

    def _show_manual(self):
        """使用手册：独立非模态窗口，用编辑器内核只读渲染（滚动浏览）。"""
        if getattr(self, "_manual_dlg", None) is None:
            dlg = QDialog(self)
            dlg.setWindowTitle(f"使用手册 · {APP_NAME}")
            dlg.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
            dlg.resize(960, 720)
            v = QWebEngineView(dlg)
            v.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            lay = QHBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(v)
            dlg._view = v
            dlg._ready = False

            def _fill(ok):
                if not ok:
                    return
                self._js_view(v, f"window.setTheme({js(self._theme)})")
                v.setZoomFactor(self._zoom)
                self._js_view(v, "window.setPreviewMode(true)")
                self._js_view(v, f"window.setPreviewContent({js(self._manual_md())})")
                dlg._ready = True

            v.loadFinished.connect(_fill)
            v.load(QUrl.fromLocalFile(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor.html")))
            self._manual_dlg = dlg
        self._manual_dlg.show()
        self._manual_dlg.raise_()
        self._manual_dlg.activateWindow()
        self.show_status("已打开使用手册（滚动浏览，Esc 关闭）")

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
        # v3.31.3（QUO-6）：引用块 / 代码块常用按键说明（含退出方式）
        # v3.38（QUO-11）：按键说明对齐《引用模块交互规范-v3.37》
        rows.append("<p style='margin:10px 0 4px;'><b>引用块常用按键</b></p>"
                    "<div style='margin:2px 0 2px 12px;'>回车 —— 延续引用（自动补 &gt; 前缀）</div>"
                    "<div style='margin:2px 0 2px 12px;'>末行空行再按回车 —— 引用保留，其后新建空段落</div>"
                    "<div style='margin:2px 0 2px 12px;'>Tab / Shift+Tab —— 嵌套加 / 减一级</div>"
                    "<div style='margin:2px 0 2px 12px;'>行首退格 —— 逐级降级；顶层行仅当前行脱离引用</div>"
                    "<div style='margin:2px 0 2px 12px;'>Esc —— 失焦退出编辑（内容不动）；Ctrl+Enter —— 跳出引用</div>"
                    "<p style='margin:10px 0 4px;'><b>代码块常用按键</b></p>"
                    "<div style='margin:2px 0 2px 12px;'>Tab / Shift+Tab —— 插入 2 空格缩进 / 反缩进（跨行选区批量处理）</div>"
                    # v3.38（CODE-9/10/11/12/13）：按键与入口说明对齐《代码块模块交互规范-v3.37》
                    "<div style='margin:2px 0 2px 12px;'>Esc 或 Ctrl+Enter —— 退出编辑跳到下一块；已是末块则在其后新建空段落</div>"
                    "<div style='margin:2px 0 2px 12px;'>复制：悬停代码块 → 顶栏 ⧉ 复制全部代码（或右键语言栏）</div>"
                    "<div style='margin:2px 0 2px 12px;'>顶栏「风格」弹层：4 种风格 + 行数显示 + 自动换行开关</div>"
                    "<div style='margin:2px 0 2px 12px;'>长代码（&gt;20 行）顶栏 ▾ 可折叠；⛶ 全屏编辑（Esc 退出全屏）</div>"
                    "<div style='margin:2px 0 2px 12px;'>顶栏「命令」/ 空块命令条：按语言插入安装依赖、构建、运行、测试、格式化命令</div>"
                    "<div style='margin:2px 0 2px 12px;'>代码区右键 —— 复制代码 / 复制（选区）/ 粘贴 / 删除块</div>"
                    # v3.38（HR-11）：分割线使用指引（正向用法 + 慎用约束）
                    "<p style='margin:10px 0 4px;'><b>分割线（hr）使用指引</b></p>"
                    "<div style='margin:2px 0 2px 12px;'>插入：空行输入 / → 分割线；点击选中（Delete / Backspace 删除，Esc 取消）</div>"
                    "<div style='margin:2px 0 2px 12px;'>↑ / ↓ 键跨过分割线时自动建立选中态，可直接键盘删除</div>"
                    "<div style='margin:2px 0 2px 12px;'>用途：章节级内容分隔（把文章切成章节）</div>"
                    "<div style='margin:2px 0 2px 12px;'>慎用：不要连续使用或用分割线替代标题 / 留白 —— 过度分割会产生视觉噪音（Material Design 建议）</div>")
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

    # ---- 主工具栏 显示 / 隐藏（v3.38 TB-1）----
    def set_toolbar_visible(self, vis, toast=True):
        """显示 / 隐藏左侧主工具栏；隐藏时左侧边缘常驻「»」展开按钮。"""
        vis = bool(vis)
        self._tool_tb.setVisible(vis)
        # 注意：窗口尚未 show() 时 isVisible() 恒为 False（Qt 语义），**不能**拿它当
        # 「用户意图」落盘 —— 否则每次启动都会把 ui/toolbarVisible 写成 False，下次
        # 启动工具栏就凭空消失（TB-1 的症状换个马甲复发）。故显式把 vis 传下去。
        self._sync_toolbar_state(toast=toast and not vis, vis=vis)

    def toggle_toolbar(self, checked=True):
        """视图菜单 / 右键菜单 / 快捷键入口（checkable 动作带新勾选态）。"""
        self.set_toolbar_visible(bool(checked))

    def _sync_toolbar_state(self, toast=False, persist=True, vis=None):
        """按工具栏可见性同步展开按钮 / 菜单勾选 / 持久化，并给出恢复提示。

        vis=None → 取控件真实可见性（visibilityChanged 路径，此时窗口已 show，可信）；
        显式传入 → 以调用方意图为准（启动初始化阶段 isVisible() 不可信）。
        """
        vis = self._tool_tb.isVisible() if vis is None else bool(vis)
        btn = getattr(self, "_btn_tb_show", None)
        if btn is not None:
            btn.setVisible(not vis)
            if not vis:
                self._place_tb_expand_btn()
                btn.raise_()
        act = getattr(self, "_act_toolbar", None)
        if act is not None and act.isChecked() != vis:
            act.setChecked(vis)
        if persist:
            self._settings.setValue("ui/toolbarVisible", vis)
        if toast and not vis:
            self.show_status("工具栏已隐藏：点击左侧边缘的 » 或按 Ctrl+Shift+B 可重新展开")

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
        # v3.38（TB-1）：左侧边缘「展开工具栏」按钮随主题换色（仅工具栏隐藏时可见）
        if getattr(self, "_btn_tb_show", None) is not None:
            p = styles.palette(name)
            self._btn_tb_show.setStyleSheet(
                "QToolButton#tbExpand {{ background: {bg}; border: 1px solid {bd};"
                " border-radius: 9px; color: {ac}; font-size: 15px; font-weight: 800;"
                " padding: 0; }}"
                "QToolButton#tbExpand:hover {{ background: {acs}; color: {ac}; }}".format(
                    bg=p["bg_soft"], bd=p["border"], ac=p["accent"], acs=p["accent_soft"]))
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

    def set_startup_action(self, mode):
        """v3.38（OUT-5）：启动时行为（blank=欢迎页 / lastFile=恢复上次文件 /
        lastFileSide=恢复上次文件与侧栏位置 / folder=打开指定文件夹），下次启动生效。"""
        mode = str(mode or "blank")
        if mode not in ("blank", "lastFile", "lastFileSide", "folder"):
            mode = "blank"
        self._startup_action = mode
        self._settings.setValue("startupAction", mode)

    def set_startup_folder(self, path):
        """v3.38（OUT-5）：『打开指定文件夹』使用的目录路径。"""
        self._startup_folder = str(path or "")
        self._settings.setValue("startupFolder", self._startup_folder)

    def last_sidebar_dir(self):
        """v3.38（FLP-1）：上次访问的侧栏目录（无则空串）。"""
        return str(self._settings.value("lastSidebarDir", "") or "")

    def file_list_default_dir(self):
        """v3.38（FLP-1）：文件列表「默认打开路径」的**原始配置值**（未解析，空 = 未配置）。

        字段：QSettings `files/defaultDir`；默认值 = `config.FILE_LIST_DEFAULT_DIR`（""）。
        """
        return str(self._settings.value("files/defaultDir", FILE_LIST_DEFAULT_DIR) or "")

    def set_file_list_default_dir(self, text):
        """v3.38（FLP-1）：设置文件列表默认打开路径（留空 = 不启用），并即时定位一次。"""
        self._file_list_default_dir = str(text or "").strip()
        self._settings.setValue("files/defaultDir", self._file_list_default_dir)
        self._sidebar.apply_default_dir(toast=True)

    def _remember_last_session(self):
        """v3.38（OUT-5）：记录最近文档与侧栏目录，供「启动时」恢复上次会话。"""
        try:
            if self.file_path and os.path.isfile(self.file_path):
                self._settings.setValue("lastFile", self.file_path)
            sdir = self._sidebar.current_dir()
            if sdir and os.path.isdir(sdir):
                self._settings.setValue("lastSidebarDir", sdir)
        except Exception:      # noqa: BLE001
            pass

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

    # ================= v3.32.2（TPL-C）自定义模板 =================
    # v3.36（TPL-E）：模板体系统一 —— 内置模板也落 templates.json，与自建模板
    # 同等管理（/ 菜单「模板」二级的内容即这份列表）
    def _tpl_entry(self, name, content, ic=""):
        """构造一条模板记录（ic 为空时不写该键，保持与旧数据的字典形态一致）。"""
        it = {"name": name, "content": content}
        ic = normalize_template_icon(ic)
        if ic:
            it["ic"] = ic
        return it

    def _templates_from_data(self, data):
        """templates.json 内容 → (模板列表, 结构版本号)。

        v2 = {"v": 2, "templates": [...]}；v1 = 早期纯数组 [{name, content}]；
        0 = 缺失 / 损坏（按首次运行处理）。
        """
        if isinstance(data, dict):
            raw = data.get("templates")
            try:
                ver = int(data.get("v", 0) or 0)
            except (TypeError, ValueError):
                ver = 0
        elif isinstance(data, list):
            raw, ver = data, 1
        else:
            raw, ver = [], 0
        items = []
        for t in raw or []:
            if not isinstance(t, dict):
                continue
            name = normalize_template_name(t.get("name", ""))
            content = str(t.get("content", ""))
            if name and content.strip():
                items.append(self._tpl_entry(name, content, t.get("ic", "")))
        return items, ver

    def _merge_builtin_templates(self, items):
        """并入内置模板：同名保留用户版本（位置不动），缺失的按内置顺序补在末尾。"""
        have = set(t.get("name") for t in items or [])
        out = [dict(t) for t in items or []]
        for b in BUILTIN_TEMPLATES:
            if b["name"] in have:
                continue
            out.append(self._tpl_entry(b["name"], b["content"], b.get("ic", "")))
        return out

    def _reorder_builtin_templates(self, items):
        """v3.38（TPL-F）：内置模板重排到默认顺序（自建模板保持相对顺序排其后）。

        仅在结构版本 < 3 的一次性迁移中执行 —— 此后用户在设置页调整的顺序
        落在 templates.json（ver=3）里，不会再被改动。"""
        rank = {b["name"]: i for i, b in enumerate(BUILTIN_TEMPLATES)}
        bi = sorted((t for t in items if t.get("name") in rank),
                    key=lambda t: rank[t["name"]])
        us = [t for t in items if t.get("name") not in rank]
        return bi + us

    def _write_template_file(self, templates):
        """按 v2 结构写盘（"v" 同时是「内置模板已并入」的迁移标记）。"""
        try:
            os.makedirs(USER_DATA_DIR, exist_ok=True)
            with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"v": TPL_FILE_VERSION, "templates": templates}, f,
                          ensure_ascii=False, indent=2)
            return True
        except OSError as e:
            self.show_status(f"模板保存失败：{e}")
            return False

    def _load_custom_templates(self):
        """读取模板列表（templates.json）。

        v3.36（TPL-E）：内置模板并入统一列表 ——
          · 文件缺失 / 损坏 → 以内置模板初始化（首次运行）；
          · 旧格式（v1 纯数组）→ 合并缺失的内置模板后写回 v2（一次性迁移，
            用户既有模板保持原顺序，内置补在末尾）；
          · v2 → v3：内置模板重排为默认顺序（TPL-F，一次性迁移；自建模板
            保持相对顺序排其后），写回 v3；
          · 已是 v3 → 原样返回。
        名称统一过 normalize_template_name —— 手改过 json 或历史遗留的超长名称
        在这里被收回到显示上限，菜单与列表展示始终一致。
        """
        data = None
        try:
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = None
        items, ver = self._templates_from_data(data)
        if ver >= TPL_FILE_VERSION:
            return items
        merged = self._merge_builtin_templates(items)
        merged = self._reorder_builtin_templates(merged)   # v3.38（TPL-F）
        self._write_template_file(merged)
        return merged

    def _custom_templates_js(self):
        """模板列表序列化为下发参数（json 字符串字面量）。"""
        return js(json.dumps(self._custom_templates, ensure_ascii=False))

    def _sync_custom_templates(self, view=None):
        """把自定义模板下发给编辑器（缺省 = 当前活跃视图）。"""
        code = f"window.setCustomTemplates({self._custom_templates_js()})"
        if view is not None:
            self._js_view(view, code)
        else:
            self._js_active(code)

    def save_custom_templates(self, templates):
        """保存模板列表（模板设置页 / 设为模板文件共用）：写盘并即时下发。

        返回 True 表示已写盘并下发；False 表示写盘失败（调用方可据此决定是否再提示）。
        """
        cleaned, seen = [], set()
        for t in templates or []:
            name = normalize_template_name((t or {}).get("name", ""))
            content = str((t or {}).get("content", ""))
            if name and content.strip() and name not in seen:
                seen.add(name)
                cleaned.append(self._tpl_entry(name, content, (t or {}).get("ic", "")))
        self._custom_templates = cleaned
        if not self._write_template_file(cleaned):
            return False
        self._sync_custom_templates()
        self.show_status(f"模板已保存（{len(cleaned)} 个）")
        return True

    def make_template_from_file(self, path):
        """v3.35（TPL-D）：把文件列表里的某个文档收编为自定义模板。

        流程：读磁盘内容（体积 / 空内容 / 编码兜底）→ 弹输入框填名称（输入层硬限
        TPL_NAME_MAX 字）→ 归一化 + 重名自动编号 → 追加到列表末尾（= 菜单末尾）
        → 写 templates.json 并即时下发编辑器。
        """
        p = str(path or "")
        try:
            size = os.path.getsize(p)
        except OSError as e:
            QMessageBox.warning(self, "设为模板", f"无法读取该文件：{e}")
            return
        if size > TPL_MAX_BYTES:
            QMessageBox.warning(
                self, "设为模板",
                f"文件过大（{size / 1024:.0f} KB）。\n"
                f"模板内容上限为 {TPL_MAX_BYTES // 1024} KB，请先精简后再试。")
            return
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            QMessageBox.warning(self, "设为模板", f"无法读取该文件：{e}")
            return
        if not content.strip():
            QMessageBox.warning(self, "设为模板", "该文件内容为空，无法作为模板。")
            return

        base = os.path.splitext(os.path.basename(p))[0]
        default = normalize_template_name(base) or "新模板"
        label = f"模板名称（最多 {TPL_NAME_MAX} 字，将显示在 / 菜单与悬浮模板菜单中）："
        if (os.path.abspath(p) == os.path.abspath(self.file_path or "")
                and getattr(self, "_dirty", False)):
            label += "\n注意：该文件有未保存的修改，模板内容取磁盘上的版本（可先 Ctrl+S）。"
        dlg = QInputDialog(self)
        dlg.setWindowTitle("设为模板")
        dlg.setLabelText(label)
        dlg.setTextValue(default)
        le = dlg.findChild(QLineEdit)
        if le is not None:
            le.setMaxLength(TPL_NAME_MAX)   # 输入层硬限：手动输入 / 粘贴超长都会被截住
            le.selectAll()
        if dlg.exec() != QDialog.Accepted:
            return

        name = normalize_template_name(dlg.textValue())
        if not name:
            self.show_status("模板名称为空，未创建")
            return
        renamed = unique_template_name(name, [t.get("name") for t in self._custom_templates])
        self._custom_templates.append({"name": renamed, "content": content})
        if self.save_custom_templates(self._custom_templates):
            self.show_status(f"已设为模板：{renamed}" + ("（名称重复，已自动编号）" if renamed != name else ""))
        else:
            self._custom_templates.pop()   # 落盘失败：撤销内存追加，避免与磁盘不一致

    def open_template_manager(self):
        """打开「系统设置 → 模板」页。

        v3.36（TPL-E）：模板管理从独立对话框提升为设置面板的一级页（与外观 /
        编辑器 / 通用同级），这里保留入口便于侧栏 / 菜单 / 命令面板复用。
        """
        self.show_settings("模板")

    def show_settings(self, page=None):
        """打开系统设置；page 给定时定位到该页（如 "模板"）。"""
        if not hasattr(self, "_set_dlg"):
            self._set_dlg = SettingsDialog(self)
        if page:
            self._set_dlg.select_page(page)
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

    def jump_to_heading(self, index, text=None):
        """v3.38（OUT-4）：text = 大纲缓存标题文本，JS 侧先校验再跳（过期自动重查）。"""
        suffix = f", {js(text)}" if text else ""
        if self._dual and self._view_src is not None:
            self._js_view(self._view_src, f"window.gotoHeadingSrc({index}{suffix})")
            self._js_view(self._view_prev, f"window.gotoHeading({index}{suffix})")
        else:
            self._js_view(self._view, f"window.gotoHeading({index}{suffix})")

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
        # v3.38（TAB-5）：标签栏鼠标手势 —— 中键点击标签即关闭 / 双击标签即关闭 /
        # 双击空白处新建标签（Notepad++ 与浏览器对标）
        if obj is self._tabbar:
            if ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.MiddleButton:
                i = self._tabbar.tabAt(ev.position().toPoint())
                if i >= 0:
                    self._close_tab(i)
                    return True
            elif (ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton
                  and ev.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                # v3.38（TAB-B）：Ctrl+单击增减选中 / Shift+单击区间选中（消费事件
                # 阻止 QTabBar 内部切标签；固定标签不参与多选）
                i = self._tabbar.tabAt(ev.position().toPoint())
                if i >= 0 and not self._docs[i].get("pinned"):
                    if ev.modifiers() & Qt.ControlModifier:
                        if i in self._tab_multi:
                            self._tab_multi.discard(i)   # 取消选中：锚点保持不变
                        else:
                            self._tab_multi.add(i)
                            self._multi_anchor = i
                    else:   # Shift：锚点（上次 Ctrl 单击，缺省当前标签）到本标签的区间
                        a = self._multi_anchor if self._multi_anchor >= 0 else self._cur
                        lo, hi = sorted((a, i))
                        self._tab_multi = {k for k in range(lo, hi + 1)
                                           if not self._docs[k].get("pinned")}
                    self._update_multi_highlight()
                    self.show_status(
                        f"已选中 {len(self._tab_multi)} 个标签页（Ctrl+单击增减，Shift+单击区间，右键可批量关闭）")
                return True
            elif (ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton):
                # 普通左键单击：清多选（正常切标签路径不受影响）。
                # 注意右键**不能**在这里清 —— 右键命中选中集时要保持多选弹批量关闭菜单
                if self._tab_multi:
                    self._tab_multi.clear()
                    self._multi_anchor = -1
                    self._update_multi_highlight()
            elif ev.type() == QEvent.MouseButtonDblClick:
                i = self._tabbar.tabAt(ev.position().toPoint())
                if i >= 0:
                    self._close_tab(i)
                else:
                    self.new_file()
                return True
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
            self._remember_last_session()   # v3.38（OUT-5）
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
        if btn == QMessageBox.Discard and 0 <= self._cur < len(self._docs):
            self._remove_draft(self._docs[self._cur])   # v3.32（P0-1）：明确丢弃 → 删草稿
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
        self._remember_last_session()   # v3.38（OUT-5）
        self._quitting = True
        e.accept()
