# -*- coding: utf-8 -*-
"""左侧边栏：文件列表（此电脑 / 逐级浏览）+ 大纲 两个标签页。

v3.24：跨文件全局搜索抽为独立面板类 GlobalSearchPanel，
内嵌到「查找 / 替换」对话框的「全局搜索」页签，侧栏不再承载搜索面板。"""
import json
import os
import re
import tempfile

from PySide6.QtCore import QEvent, QSize, QStandardPaths, Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QButtonGroup, QCheckBox, QComboBox,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPushButton, QSizePolicy,
    QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from config import DRAFT_DIR, FILE_LIST_DEFAULT_DIR, HERE
from styles import SIDEBAR_QSS
from icons import icon_file, icon_folder, icon_up

# 跨文件搜索上限（避免在超大目录上卡死界面）
SEARCH_MAX_FILES = 1500
SEARCH_MAX_SIZE = 1_500_000     # 单文件最大字节数
SEARCH_MAX_HITS = 400           # 最多展示的命中条数
SEARCH_SKIP_DIRS = {".git", ".svn", "node_modules", "__pycache__", ".idea", ".vscode"}
# v3.31（#5）：目录树跳过的目录（在搜索跳过清单上补上编辑器自身的历史目录）
TREE_SKIP_DIRS = SEARCH_SKIP_DIRS | {".mdeditor-history"}


class GlobalSearchPanel(QWidget):
    """跨文件全局搜索面板：在当前文件夹内检索关键词，点击命中跳转到对应文件行。

    v3.24 起由「查找 / 替换」对话框的「全局搜索」页签承载，
    不再占用侧栏标签页，也没有独立的工具栏按钮。"""

    MD_EXTS = (".md", ".markdown", ".mdown", ".txt")

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self._win = win
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("在当前文件夹内搜索（支持正则）…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_ext = QComboBox(self)
        self.search_ext.addItem("全部", "")
        self.search_ext.addItem("仅 .md", ".md")
        self.search_ext.addItem("仅 .txt", ".txt")
        self.search_btn = QPushButton("搜索", self)
        # v3.29d（UX #20）：「仅文件名」复选框 —— 只按文件名匹配，不搜正文
        self.search_nameonly = QCheckBox("仅文件名", self)
        self.search_nameonly.setToolTip("只按文件名搜索（不改文档内容检索）")
        self.search_scope = QLabel("", self)
        self.search_scope.setObjectName("searchScope")
        self.search_scope.setWordWrap(True)
        self.search_info = QLabel("输入关键词后回车开始搜索", self)
        self.search_info.setObjectName("searchInfo")
        self.search_info.setWordWrap(True)
        self.search_tree = QTreeWidget(self)
        self.search_tree.setHeaderHidden(True)
        self.search_tree.setIndentation(12)
        self.search_tree.setVerticalScrollMode(QTreeWidget.ScrollPerPixel)
        self.search_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.search_tree.itemClicked.connect(self._on_search_click)
        self.search_tree.itemActivated.connect(self._on_search_click)

        srow = QHBoxLayout()
        srow.setContentsMargins(0, 0, 0, 0)
        srow.setSpacing(4)
        srow.addWidget(self.search_ext, 1)
        srow.addWidget(self.search_nameonly)
        srow.addWidget(self.search_btn)
        # v3.26：区分大小写 / 正则复选框移除 —— 搜索默认支持正则（无效时回退普通文本）

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self.search_edit)
        lay.addLayout(srow)
        lay.addWidget(self.search_scope)
        lay.addWidget(self.search_info)
        lay.addWidget(self.search_tree, 1)

        self.search_edit.returnPressed.connect(self.run_search)
        self.search_btn.clicked.connect(self.run_search)

    def focus_input(self):
        """切到本页签时聚焦输入框并全选，便于直接输入关键词。"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def run_with_query(self, q):
        """v3.26：供查找对话框外部驱动 —— 用统一搜索框的关键词执行全局搜索。"""
        self.search_edit.setText(q)
        self.run_search()

    # ================= 跨文件搜索 =================
    @staticmethod
    def iter_files(root, ext_filter=""):
        """递归收集可搜索的文本文件（跳过隐藏目录 / 常见构建目录 / 资源目录）。"""
        count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".")
                           and d not in SEARCH_SKIP_DIRS
                           and not d.lower().endswith(".assets")]
            for name in sorted(filenames):
                if name.startswith("."):
                    continue
                low = name.lower()
                if ext_filter:
                    if not low.endswith(ext_filter):
                        continue
                elif not low.endswith(GlobalSearchPanel.MD_EXTS):
                    continue
                p = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(p) > SEARCH_MAX_SIZE:
                        continue
                except OSError:
                    continue
                count += 1
                if count > SEARCH_MAX_FILES:
                    return
                yield p

    @staticmethod
    def _read_text(path):
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            return None
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig", errors="replace")
        for enc in ("utf-8", "gbk"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def run_search(self):
        """在当前文件夹内跨文件搜索关键词。"""
        query = self.search_edit.text()
        if not query.strip():
            self.search_info.setText("请输入关键词")
            return
        root = self._win.search_root()
        flags = re.IGNORECASE
        pattern = query
        try:
            rx = re.compile(pattern, flags)
        except re.error:
            # v3.26：正则写法无效时回退为普通文本搜索（与编辑器内查找行为一致）
            rx = re.compile(re.escape(query), flags)

        self.search_tree.clear()
        name_only = self.search_nameonly.isChecked()   # v3.29d（UX #20）
        self.search_scope.setText(f"范围：{root}" + ("（仅文件名）" if name_only else ""))
        ext = self.search_ext.currentData() or ""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        hits, files, truncated = 0, 0, False
        groups = {}
        try:
            for path in self.iter_files(root, ext):
                # v3.29d（UX #20）：仅文件名模式 —— 命中文件名的直接列为结果，
                # 不读文件内容，速度更快
                if name_only:
                    if rx.search(os.path.basename(path)):
                        groups[path] = [(1, os.path.basename(path), 0)]
                        files += 1
                        hits += 1
                    continue
                text = self._read_text(path)
                if text is None or rx.search(text) is None:
                    continue
                files += 1
                for no, line in enumerate(text.split("\n"), 1):
                    if no > 200_000:
                        break
                    m = rx.search(line)
                    if not m:
                        continue
                    groups.setdefault(path, []).append((no, line, m.start()))
                    hits += 1
                    if hits >= SEARCH_MAX_HITS:
                        truncated = True
                        break
                if truncated:
                    break
        finally:
            QApplication.restoreOverrideCursor()

        if not groups:
            self.search_info.setText(f"未找到匹配「{query}」")
            return
        for path, rows in groups.items():
            top = QTreeWidgetItem([f"{os.path.basename(path)}  ({len(rows)})"])
            top.setToolTip(0, path)
            top.setData(0, Qt.UserRole, ("file", path))
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            top.setForeground(0, QBrush(QColor("#8a6d1f")))
            for no, line, col in rows[:60]:
                snippet = line.strip()
                if len(snippet) > 120:
                    snippet = snippet[:120] + "…"
                child = QTreeWidgetItem([f"{no}: {snippet}"])
                child.setToolTip(0, f"{path}:{no}")
                child.setData(0, Qt.UserRole, ("hit", path, no))
                top.addChild(child)
            if len(rows) > 60:
                more = QTreeWidgetItem([f"… 该文件还有 {len(rows) - 60} 处匹配"])
                more.setData(0, Qt.UserRole, ("more", path))
                top.addChild(more)
            self.search_tree.addTopLevelItem(top)
        self.search_tree.expandAll()
        msg = f"{len(groups)} 个文件 · {hits} 处匹配"
        if truncated:
            msg += f"（已达上限 {SEARCH_MAX_HITS}，请缩小范围或细化关键词）"
        self.search_info.setText(msg)

    def _on_search_click(self, item, _col=0):
        data = item.data(0, Qt.UserRole)
        if not data or data[0] != "hit":
            return
        self._win.open_file_at(data[1], data[2])


class OutlineTree(QTreeWidget):
    """v3.31（#7）：支持拖拽调序的大纲树。

    只允许同一父级（同级标题）之间上下移动，放下后回调
    Sidebar._on_outline_dropped 按新顺序整段移动对应章节。"""

    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self._owner = owner

    def dropEvent(self, e):
        src = self.currentItem()
        tgt = self.itemAt(e.position().toPoint())
        if src is None or tgt is None or src is tgt:
            e.ignore()
            return
        if src.parent() is not tgt.parent():   # 跨级 / 跨父级调序一律拒绝
            e.ignore()
            return
        if self.dropIndicatorPosition() not in (
                QAbstractItemView.AboveItem, QAbstractItemView.BelowItem):
            e.ignore()   # 只接受项间落点（落到项上 / 空白处的语义不明确）
            return
        super().dropEvent(e)
        self._owner._on_outline_dropped()


class Sidebar(QWidget):
    """Typora 风格左侧边栏：文件列表（一级目录）/ 大纲 两个标签页。

    v3.31.2（需求变更）：原「目录」树形页与「文件」页职责重合，整体移除；
    新建 / 新建文件夹 / 重命名 / 回收站删除等管理操作迁入「文件」页右键菜单。"""

    TAB_FILES, TAB_OUTLINE = 0, 1
    MD_EXTS = (".md", ".markdown", ".mdown", ".txt")
    # v3.39（FL-4）：非 md 灰显时隐藏的系统噪音文件（大小写不敏感）
    IGNORE_NAMES = {"desktop.ini", "thumbs.db", "$recycle.bin", "autorun.inf"}
    # v3.39（FL-6）：固定目录上限
    PIN_MAX = 8

    def sizeHint(self):
        """v3.39.14（UIUX-2）：钉死建议宽度=固定宽 224。

        QSplitter 初始槽位按 sizeHint() 分配（布局树算出约 370px），
        比固定宽多出的部分变成侧栏右侧的死白区；覆写后 splitter
        初始即按 224 分配，消除「侧栏与内容区间距过大」。"""
        return QSize(232, super().sizeHint().height())

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("sidebar")
        self.setFixedWidth(224)
        # v3.39.14（UIUX-2）：sizePolicy=Fixed —— 配合 sizeHint 覆写，
        # 修复 splitter 初始按布局树 sizeHint（约 370px）分配槽位、
        # 而控件实际只画 224px 导致的右侧死白区
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(SIDEBAR_QSS)
        self._outline_sig = None
        self._outline_level = 3      # 大纲展开显示级别（1~6，系统设置可改）
        self._outline_words = False  # v3.31.2（#3）：分节字数后缀开关（默认关）
        self._last_headings = None   # 最近一次大纲数据（级别切换时复用重建）
        self._file_mode = "current"  # 文件列表显示模式：current=跟随当前文档 / blank=空白项
        self._initial_restored = False  # v3.38（FLP-2）：启动/首次打开 tab 是否已定位过

        lay = QVBoxLayout(self)
        # v3.39.14（HEAD-1）：头行边距对齐——侧栏头行与主区页签条同高 42px、顶空 5px
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # ---- 顶部标签（文件 / 大纲，均分宽度）----
        tabcap = QWidget(self)
        tabcap.setObjectName("tabcap")
        tab_row = QHBoxLayout(tabcap)
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(2)
        self.btn_files = QToolButton(tabcap, text="文件列表")   # v3.44.3（DESIGN01）：设计稿页签名
        self.btn_outline = QToolButton(tabcap, text="大纲")
        for b in (self.btn_files, self.btn_outline):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tab_row.addWidget(b, 1)
        self._tabs = QButtonGroup(self)
        self._tabs.setExclusive(True)
        self._tabs.addButton(self.btn_files)
        self._tabs.addButton(self.btn_outline)
        self.btn_files.setChecked(True)
        self.btn_files.clicked.connect(lambda: self.select_tab(self.TAB_FILES))
        self.btn_outline.clicked.connect(lambda: self.select_tab(self.TAB_OUTLINE))
        cap_row = QHBoxLayout()
        # HEAD-1：左右 10px 与文件列表/大纲面板基准线一致；HEAD-2 行高 40 同步
        cap_row.setContentsMargins(10, 3, 10, 3)
        cap_row.addWidget(tabcap)
        # v3.43.0（OUT-LOOK）：页签行右侧工具钮（设计稿同款）——重建大纲 / 折叠·展开全部
        self.btn_ol_refresh = QToolButton(self)
        self.btn_ol_refresh.setText("⟳")
        self.btn_ol_refresh.setObjectName("olTool")
        self.btn_ol_refresh.setToolTip("重建大纲（按当前过滤与显示级别重新生成）")
        self.btn_ol_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_ol_refresh.setFixedSize(22, 22)
        self.btn_ol_refresh.clicked.connect(self.refresh_outline)
        self.btn_ol_fold = QToolButton(self)
        self.btn_ol_fold.setText("⌄")
        self.btn_ol_fold.setObjectName("olTool")
        self.btn_ol_fold.setToolTip("折叠全部 / 展开全部（大纲树）")
        self.btn_ol_fold.setCursor(Qt.PointingHandCursor)
        self.btn_ol_fold.setFixedSize(22, 22)
        self.btn_ol_fold.clicked.connect(self.toggle_outline_fold)
        cap_row.addWidget(self.btn_ol_refresh)
        cap_row.addWidget(self.btn_ol_fold)
        lay.addLayout(cap_row)

        # ---- 中部：文件列表（仅一级目录）/ 大纲 ----
        # 文件面板：顶部显示当前所在文件夹，双击逐级返回，最顶层为「此电脑」
        # 用 QPushButton 以支持 text-align:left（QToolButton 不支持，文字会居中）
        self.file_header = QPushButton(self)
        self.file_header.setObjectName("fileHeader")
        self.file_header.setCursor(Qt.PointingHandCursor)
        self.file_header.setText("此电脑")
        self.file_header.setToolTip("双击返回上一级目录")
        self.file_header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_header.installEventFilter(self)
        self._cur_dir = None      # None = 「此电脑」层（显示所有盘符）
        self._cur_file = None

        self.file_list = QListWidget(self)
        self.file_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.file_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.file_list.setIconSize(QSize(16, 16))
        self.file_list.itemDoubleClicked.connect(self._on_file_dbl)
        # v3.44.2（FILE-UX）：文件夹图标主题色（随 apply_theme 重填），文件用中性灰描边图标
        self._folder_accent = "#0052d9"
        # v3.39（FL-3）：列表键盘快捷键经事件过滤器处理（列表有焦点才生效）
        self.file_list.installEventFilter(self)
        # v3.25：右键菜单 —— 在资源管理器中显示 / 用外部程序打开（原「文件」菜单项迁入）
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_file_menu)

        # v3.39（FL-1）：面包屑路径条 —— 路径段按钮一键直达任意上级；
        # 双击面包屑 = 返回上一级（保留原 file_header 双击习惯）
        self.crumbs = QWidget(self)
        self.crumbs.setObjectName("crumbs")
        self._crumb_lay = QHBoxLayout(self.crumbs)
        self._crumb_lay.setContentsMargins(10, 2, 10, 2)
        self._crumb_lay.setSpacing(1)
        self.crumbs.setToolTip("双击返回上一级目录")
        self.crumbs.installEventFilter(self)
        # v3.44.5（DESIGN01）：面包屑首部「↑ 上级目录」按钮（设计稿 .crumb .up）
        self._crumb_up = QPushButton(self)
        self._crumb_up.setObjectName("crumbUp")
        self._crumb_up.setText("")
        self._crumb_up.setIcon(icon_up(16))
        self._crumb_up.setIconSize(QSize(16, 16))
        self._crumb_up.setCursor(Qt.PointingHandCursor)
        self._crumb_up.setFixedSize(22, 22)
        self._crumb_up.setToolTip("返回上一级目录")
        self._crumb_up.clicked.connect(self.go_up)
        self.file_panel = QWidget(self)
        fp_lay = QVBoxLayout(self.file_panel)
        fp_lay.setContentsMargins(0, 0, 0, 0)
        fp_lay.setSpacing(2)
        fp_lay.addWidget(self.file_header)
        fp_lay.addWidget(self.crumbs)
        fp_lay.addWidget(self.file_list, 1)

        # 大纲：树形结构，默认展开到 3 级，更深层级默认折叠（可手动展开）
        # v3.31（#7）：OutlineTree 支持同级拖拽调序（整段移动章节）
        self.outline = OutlineTree(self, self)
        self.outline.setHeaderHidden(True)
        self.outline.setIndentation(18)   # v3.26：缩进加大，容纳加粗展开箭头
        self.outline.setExpandsOnDoubleClick(True)
        self.outline.setVerticalScrollMode(QTreeWidget.ScrollPerPixel)
        self.outline.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.outline.setDragDropMode(QAbstractItemView.InternalMove)
        self.outline.itemClicked.connect(self._on_outline_clicked)
        # v3.32.2（OUT-2）：大纲右键 —— 展开 / 折叠子节点（递归全部嵌套子级）
        self.outline.setContextMenuPolicy(Qt.CustomContextMenu)
        self.outline.customContextMenuRequested.connect(self._on_outline_menu)

        # ---- v3.44.9（OUT-STRIP2）：大纲面板 = 纯标题树 ----
        #      移除顶部「全部 / H1 / H2 / H3」级别过滤 chip 行（v3.44.8），
        #      并移除底部「N 个标题」计数行（v3.44.9）；大纲仅显示标题树。
        self._outline_filter = 0      # 0=全部（内部逻辑保留，UI 不再暴露级别过滤）

        self.outline_panel = QWidget(self)
        op = QVBoxLayout(self.outline_panel)
        op.setContentsMargins(0, 0, 0, 0)
        op.setSpacing(0)
        op.addWidget(self.outline, 1)

        # v3.31.2：树形「目录」页已移除（与文件页重合，管理操作迁文件页右键）
        # 全局搜索面板（v3.24 起移入「查找」对话框的「全局搜索」页签）：
        # 面板构造与检索逻辑见 GlobalSearchPanel，侧栏只保留文件 / 大纲两个标签页。
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.file_panel)
        self.stack.addWidget(self.outline_panel)   # v3.43.0：大纲页 = 过滤条 + 树
        lay.addWidget(self.stack, 1)

        # 初始进入「此电脑」层
        self._refresh_files()
        self._update_file_header()
        # v3.26：加粗放大的展开/收拢箭头（颜色随主题）
        self.set_tree_arrows(getattr(win, "_theme", "light"))

    # ---- v3.26：大纲树展开/收拢箭头 ----
    def set_tree_arrows(self, theme_id="light"):
        """用运行时绘制的实心三角箭头替换 QTreeWidget 默认的细小分支箭头。

        v3.44.3（DESIGN01）：按需求改回「三角形」——收拢 = 右向实心 ▶，
        展开 = 下向实心 ▼，16×16 px；颜色取主题次级文字色，选中行箭头换
        主题强调色（:selected 变体）。换肤时由 mainwindow.apply_theme 再次调用。"""
        from styles import palette
        try:
            pal = palette(theme_id)
            col = QColor(pal["text_muted"])
            col_sel = QColor(pal.get("accent") or pal.get("text") or "#3b82f6")
        except Exception:
            col = QColor("#6b7280")
            col_sel = QColor("#3b82f6")
        cache = os.path.join(tempfile.gettempdir(), "mdEditor_arrows")
        os.makedirs(cache, exist_ok=True)

        def _draw(name, kind, color):
            """kind: closed=右向 ▶（收拢）/ open=下向 ▼（展开）。实心三角。"""
            pm = QPixmap(16, 16)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            if kind == "closed":
                pts = [QPointF(5.5, 3.5), QPointF(12.5, 8.0), QPointF(5.5, 12.5)]
            else:
                pts = [QPointF(3.5, 5.5), QPointF(12.5, 5.5), QPointF(8.0, 12.5)]
            p.drawPolygon(QPolygonF(pts))
            p.end()
            fp = os.path.join(cache, f"{name}_{theme_id}.png")
            pm.save(fp, "PNG")
            return fp

        qss = []
        for name, kind in (("closed", "closed"), ("open", "open")):
            sel = ":has-children:closed" if name == "closed" else ":open"
            for variant, color in (("", col), (":selected", col_sel)):
                fp = _draw(f"{name}{variant.replace(':', '_')}", kind, color)
                url = fp.replace("\\", "/")
                qss.append(
                    f"QTreeWidget::branch{sel}{variant} {{ image: url({url}); }}"
                )
        self.outline.setStyleSheet("\n".join(qss))
        # v3.43.0（OUT-LOOK）：大纲过滤 chip / 计数 / 页签行工具钮随主题调色
        try:
            import uistyles
            _pal = uistyles.merge_palette(theme_id)
        except Exception:
            _pal = {}
        self._apply_outline_chrome_qss(_pal)

    # ---- v3.44.2（FILE-UX）：文件列表文件夹图标随主题强调色 ----
    def set_folder_theme(self, theme_id="light"):
        """刷新文件夹图标颜色（= 当前主题 accent），并就地重着色已有目录项。

        由 mainwindow.apply_theme 在每个主题切换入口调用（与 set_tree_arrows 同源）。
        文件项图标为中性灰描边、不随主题变化，故无需重绘。"""
        from styles import palette
        try:
            self._folder_accent = palette(theme_id).get("accent") or "#0052d9"
        except Exception:
            self._folder_accent = "#0052d9"
        for i in range(self.file_list.count()):
            it = self.file_list.item(i)
            d = it.data(Qt.UserRole)
            if d and d[0] == "dir":
                it.setIcon(icon_folder(self._folder_accent))

    def _apply_outline_chrome_qss(self, pal):
        """v3.44.9：大纲工具钮（重建 / 折叠）随主题调色（底部计数行已移除）。

        关键修复：btn_ol_refresh/btn_ol_fold 是 #sidebar 内的 QToolButton，会被
        #sidebar QToolButton 规则套上 padding:5px 12px；而它们 setFixedSize(22,22)，
        12px 横向内边距使内容宽度为 22-24=-2px，⟳/⌄ 字形被裁掉 → 按钮呈空白方块
        （"未正常显示"根因）。此处显式 padding:2px + min-width/min-height 复位，
        给字形留出渲染空间。"""
        g = lambda k, d: (pal or {}).get(k, d)
        qss = (
            "QToolButton#olTool {{ border:none; background:transparent; color:{muted};"
            " font-size:14px; padding:2px; min-width:18px; min-height:18px;"
            " border-radius:4px; }}"
            "QToolButton#olTool:hover {{ background:{hov}; }}"
        ).format(hov=g("hover_bg", "#eef2f7"),
                 muted=g("text_muted", "#6b7280"))
        for b in (self.btn_ol_refresh, self.btn_ol_fold):
            b.setStyleSheet(qss)

    # ---- 行为 ----
    def eventFilter(self, obj, ev):
        if obj is self.file_header and ev.type() == QEvent.MouseButtonDblClick:
            self.go_up()
            return True
        if obj is self.crumbs and ev.type() == QEvent.MouseButtonDblClick:
            self.go_up()          # v3.39（FL-1）：双击面包屑返回上一级
            return True
        if obj is self.file_list and ev.type() == QEvent.KeyPress:
            if self._file_list_key(ev):   # v3.39（FL-3）
                return True
        return super().eventFilter(obj, ev)

    def _file_list_key(self, ev):
        """v3.39（FL-3）：文件列表键盘快捷键 —— F2 重命名 / Del 删除（走既有
        确认框）/ Enter 打开·进入（等价双击）/ F5 刷新。
        作用域：列表有焦点（事件过滤器天然保证）+ 当前项有效。"""
        key = ev.key()
        if key not in (Qt.Key_F2, Qt.Key_Delete, Qt.Key_Return, Qt.Key_Enter, Qt.Key_F5):
            return False
        if key == Qt.Key_F5:
            self._refresh_files()
            return True
        it = self.file_list.currentItem()
        row = self.file_list.currentRow()
        if row < 0 or it is None or self._file_mode == "blank":
            return True       # 无当前项：吞键防误落其它行为，但不动作
        data = it.data(Qt.UserRole)
        if not data:
            return False
        _kind, p = data
        if key == Qt.Key_F2:
            self._file_rename(p)
        elif key == Qt.Key_Delete:
            self._file_delete(p)
        else:
            self._on_file_dbl(it)
        return True

    def _on_file_dbl(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        kind, p = data
        if kind == "dir":
            self._cur_dir = p
            self._refresh_files()
            self._update_file_header()
        elif kind == "ext":                    # v3.39（FL-4）：非 md → 外部程序
            self._win.open_external(p)
        else:
            self._win.open_file(p)

    def _on_file_menu(self, pos):
        """v3.31.2：文件列表右键菜单（v3.25 两项 + v3.31.2 自「目录」页迁入的管理操作）。
        文件：打开 / 资源管理器 / 外部打开 / 设为模板（v3.35）/ 重命名 / 删除（回收站）；
        文件夹：进入 / 资源管理器 / 重命名 / 删除（回收站）；
        空白处：新建 Markdown 文件 / 新建文件夹（当前所在文件夹）。"""
        item = self.file_list.itemAt(pos)
        menu = QMenu(self)
        d = self._cur_dir if (self._cur_dir and os.path.isdir(self._cur_dir)) else None
        if item is None:
            # 空白处：管理操作作用于当前所在文件夹
            if d and self._file_mode != "blank":
                menu.addAction("新建 Markdown 文件", lambda: self._file_new_file(d))
                menu.addAction("新建文件夹", lambda: self._file_new_dir(d))
                menu.addSeparator()
                sort_menu = menu.addMenu("排序方式")   # v3.39（FL-5）
                for _label, _mode in (("名称升序", 0), ("名称降序", 1),
                                      ("修改时间 新→旧", 2)):
                    sort_menu.addAction(_label,
                                        lambda m=_mode: self._set_sort_mode(m))
                menu.addSeparator()
                menu.addAction("刷新", self._refresh_files)
            elif self._cur_dir is None and self._pinned_dirs():
                # v3.39（FL-6）：「此电脑」层空白右键 —— 清理失效固定项
                menu.addAction("清理失效的固定目录", self._clean_dead_pins)
            if menu.isEmpty():
                return
            menu.exec(self.file_list.mapToGlobal(pos))
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        kind, p = data
        if kind == "dir":
            menu.addAction("进入文件夹", lambda: self._on_file_dbl(item))
            # v3.39（FL-6）：固定 / 取消固定
            menu.addSeparator()
            if p in self._pinned_dirs():
                menu.addAction("取消固定", lambda: self._unpin_dir(p))
            else:
                menu.addAction("固定此目录", lambda: self._pin_dir(p))
        elif kind == "ext":                    # v3.39（FL-4）
            menu.addAction("用外部程序打开", lambda: self._win.open_external(p))
        else:
            menu.addAction("打开", lambda: self._win.open_file(p))
        menu.addAction("在资源管理器中显示", lambda: self._win.show_in_explorer(p))
        if kind == "file":
            menu.addAction("用外部程序打开", lambda: self._win.open_external(p))
            # v3.35（TPL-D）：把该文档收编为自定义模板（追加到 / 菜单与悬浮模板菜单）
            menu.addAction("设为模板…", lambda: self._win.make_template_from_file(p))
        menu.addSeparator()
        menu.addAction("重命名", lambda: self._file_rename(p))
        menu.addAction("删除（移入回收站）", lambda: self._file_delete(p))
        menu.exec(self.file_list.mapToGlobal(pos))

    def go_up(self):
        """双击文件头返回上一级目录；到达盘符根目录后再返回「此电脑」层。"""
        if self._file_mode == "blank" or self._cur_dir is None:
            return
        parent = os.path.dirname(self._cur_dir)
        if parent and parent != self._cur_dir and os.path.isdir(parent):
            self._cur_dir = parent
        else:
            self._cur_dir = None  # 盘符根目录 -> 此电脑
        self._cur_file = None
        self._refresh_files()
        self._update_file_header()

    @staticmethod
    def _drives():
        """Windows API 直接取盘符列表（瞬时返回）。

        之前用 os.path.exists 逐个探测 A~Z：在不存在 / 断开的盘符上
        每次探测可能阻塞数秒（网络驱动器超时），26 次累计拖慢启动约 1 分钟。"""
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetLogicalDriveStringsW(1024, buf)
        raw = ctypes.wstring_at(ctypes.addressof(buf), n)
        return [s for s in raw.split("\x00") if s]

    def _refresh_files(self):
        self.file_list.clear()
        if self._file_mode == "blank":
            return  # 空白项模式：不显示任何内容
        if self._cur_dir is None:
            # v3.39（FL-6）：固定目录分组置顶（双击直达；失效项灰显）
            pins = self._pinned_dirs()
            for p in pins:
                it = QListWidgetItem("📌 " + (os.path.basename(p.rstrip("/\\")) or p))
                it.setData(Qt.UserRole, ("dir", p))
                if self._dir_usable(p):
                    it.setToolTip(p)
                else:
                    it.setToolTip(p + "\n（目录已失效，可右键取消固定）")
                    it.setForeground(self._muted_color())
                self.file_list.addItem(it)
            if pins:
                sep = QListWidgetItem()
                sep.setFlags(Qt.NoItemFlags)
                self.file_list.addItem(sep)
            # 「此电脑」层：列出所有盘符
            for d in self._drives():
                it = QListWidgetItem("💽 " + d)
                it.setData(Qt.UserRole, ("dir", d))
                it.setToolTip(d)
                self.file_list.addItem(it)
            return
        if not os.path.isdir(self._cur_dir):
            return
        try:
            names = os.listdir(self._cur_dir)
        except OSError:
            names = []
        dirs = sorted(n for n in names
                      if not n.startswith(".") and os.path.isdir(os.path.join(self._cur_dir, n)))
        files = sorted(n for n in names
                       if os.path.isfile(os.path.join(self._cur_dir, n))
                       and n.lower().endswith(self.MD_EXTS))
        # v3.39（FL-4）：非 md 文件第三组（隐藏系统噪音；md 行为零变化）
        others = sorted(n for n in names
                        if os.path.isfile(os.path.join(self._cur_dir, n))
                        and not n.lower().endswith(self.MD_EXTS)
                        and not n.startswith(".") and n.lower() not in self.IGNORE_NAMES)
        # v3.39（FL-5）：排序方式（文件夹恒在文件前，沿用现哲学）
        mode = self._sort_mode()
        if mode == 1:
            files.reverse(); others.reverse()
        elif mode == 2:
            def _mtime(n):
                try:
                    return os.path.getmtime(os.path.join(self._cur_dir, n))
                except OSError:
                    return 0.0
            files.sort(key=_mtime, reverse=True)
            others.sort(key=_mtime, reverse=True)
        for n in dirs:
            p = os.path.join(self._cur_dir, n)
            it = QListWidgetItem(icon_folder(self._folder_accent), n)
            it.setData(Qt.UserRole, ("dir", p))
            it.setToolTip(p)
            self.file_list.addItem(it)
        for n in files:
            p = os.path.join(self._cur_dir, n)
            it = QListWidgetItem(icon_file(), n)
            it.setData(Qt.UserRole, ("file", p))
            it.setToolTip(p)
            self.file_list.addItem(it)
        for n in others:
            p = os.path.join(self._cur_dir, n)
            it = QListWidgetItem(icon_file(), n)
            it.setData(Qt.UserRole, ("ext", p))
            it.setToolTip(p + "\n（非 Markdown 文件，将用外部程序打开）")
            it.setForeground(self._muted_color())
            self.file_list.addItem(it)
        # 高亮当前文件
        if self._cur_file:
            for row in range(self.file_list.count()):
                d = self.file_list.item(row).data(Qt.UserRole)
                if d and d[1] == self._cur_file:
                    self.file_list.setCurrentRow(row)
                    break

    # ============ v3.39（FL-5）：排序方式 ============
    def _sort_mode(self):
        try:
            return int(self._win._settings.value("files/sortMode", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _set_sort_mode(self, mode):
        self._win._settings.setValue("files/sortMode", int(mode))
        self._refresh_files()

    # ============ v3.39（FL-6）：常用目录固定 Pin ============
    def _pinned_dirs(self):
        """QSettings `sidebar/pinnedDirs`（QSettings 单元素列表会退化为 str，需归一）。"""
        v = self._win._settings.value("sidebar/pinnedDirs", []) or []
        if isinstance(v, str):
            v = [v]
        return [x for x in v if x]

    def _pin_dir(self, p):
        pins = self._pinned_dirs()
        if p in pins:
            return
        if len(pins) >= self.PIN_MAX:
            self._win.show_status("固定目录最多 %d 个，请先取消固定再试" % self.PIN_MAX)
            return
        pins.append(p)
        self._win._settings.setValue("sidebar/pinnedDirs", pins)
        if self._cur_dir is None:
            self._refresh_files()

    def _unpin_dir(self, p):
        pins = [x for x in self._pinned_dirs() if x != p]
        self._win._settings.setValue("sidebar/pinnedDirs", pins)
        if self._cur_dir is None:
            self._refresh_files()

    def _clean_dead_pins(self):
        pins = [x for x in self._pinned_dirs() if self._dir_usable(x)]
        self._win._settings.setValue("sidebar/pinnedDirs", pins)
        if self._cur_dir is None:
            self._refresh_files()
        self._win.show_status("已清理失效的固定目录")

    def _muted_color(self):
        """主题禁用色（FL-4 灰显 / FL-6 失效固定项）。"""
        from styles import palette
        try:
            return QColor(palette(getattr(self._win, "_theme", "light"))["text_muted"])
        except Exception:      # noqa: BLE001 —— 主题键缺失时兜底
            return QColor("#6b7280")

    def _update_file_header(self):
        # v3.44.3（DESIGN01）：对齐设计稿侧栏结构 —— 不再显示「当前选中目录名」行
        # （设计稿只有 页签行 + 面包屑路径 + 列表），路径统一由面包屑承担；
        # 仅 blank 模式保留头行提示。双击面包屑返回上一级的习惯不变。
        if self._file_mode == "blank":
            self.file_header.setText("空白")
            self.file_header.setToolTip("文件列表已设置为空白项\n（可在 系统设置→通用 修改）")
            self.file_header.setVisible(True)
            self._rebuild_crumbs()   # v3.39（FL-1）：blank 模式隐藏面包屑
            return
        self.file_header.setVisible(False)
        if self._cur_dir is None:
            self.file_header.setToolTip("我的电脑（顶层）\n列表为所有盘符")
        else:
            self.file_header.setToolTip(self._cur_dir + "\n双击返回上一级目录")
        self._rebuild_crumbs()

    # ============ v3.39（FL-1）：面包屑路径条 ============
    def _rebuild_crumbs(self):
        """路径段按钮（此电脑 › 盘 › 目录…），点击段一键直达；中间溢出折叠为
        「…」（点击 = 返回上一级）。blank 模式整条隐藏。"""
        lay = self._crumb_lay
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None and w is not self._crumb_up:
                w.deleteLater()
        if self._file_mode == "blank":
            self.crumbs.setVisible(False)
            return
        self.crumbs.setVisible(True)
        # v3.44.6：顶层（此电脑层）无父级可回退，隐藏「↑上级」按钮，
        # 避免其以带边框小框形态出现在「此电脑」前方形成多余占位。
        if self._cur_dir is not None:
            lay.addWidget(self._crumb_up)

        def seg(text, tip, cb, cur=False):
            b = QToolButton(self.crumbs)
            b.setText(text)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoRaise(True)
            b.setStyleSheet("QToolButton{border:none;padding:1px 3px;}"
                            + ("font-weight:600;" if cur else ""))
            b.clicked.connect(cb)
            lay.addWidget(b)
            arrow = QLabel("›", self.crumbs)
            arrow.setStyleSheet("padding:0 1px;")
            lay.addWidget(arrow)

        if self._cur_dir is None:
            seg("此电脑", "我的电脑（顶层）", lambda: None, cur=True)
            lay.addStretch(1)
            return
        norm = self._cur_dir.rstrip("/\\")
        # 拆段：盘符段 + 逐级目录
        parts = []          # (显示名, 绝对路径)
        drive = os.path.splitdrive(norm)[0]
        if drive:
            rest = norm[len(drive):].lstrip("/\\")
            parts.append((drive + "\\", drive + "\\"))
            if rest:
                acc = drive + "\\"
                for segn in re.split(r"[\\/]", rest):
                    if segn:
                        acc = os.path.join(acc, segn)
                        parts.append((segn, acc))
        else:
            parts.append((norm or self._cur_dir, self._cur_dir))
        seg("此电脑", "我的电脑（顶层）", self._enter_this_pc)
        if len(parts) > 4:                       # 中间溢出折叠
            seg("…", "返回上一级", self.go_up)
            parts = parts[-3:]
        for i, (name, pth) in enumerate(parts):
            cur = i == len(parts) - 1
            seg(name, pth if not cur else pth + "\n（当前目录）",
                lambda pp=pth: self._enter_dir(pp), cur=cur)
        lay.addStretch(1)

    def _enter_this_pc(self):
        self._cur_dir = None
        self._cur_file = None
        self._refresh_files()
        self._update_file_header()

    def _enter_dir(self, p):
        if os.path.isdir(p):
            self._cur_dir = p
            self._refresh_files()
            self._update_file_header()

    def _on_outline_clicked(self, item, _col=0):
        # v3.38（OUT-4）：附带标题文本，JS 侧校验缓存 index 是否过期
        self._win.jump_to_heading(item.data(0, Qt.UserRole),
                                  item.data(0, Qt.UserRole + 1))

    # ================= 大纲右键（v3.43.0 扩为 6 项，对齐设计稿） =================
    def _on_outline_menu(self, pos):
        """大纲节点右键菜单：跳转到此处 / 复制标题文本 / 展开·折叠子节点 /
        移到开头 / 移到末尾。前四项为只读操作，后两项复用拖拽调序通道整段移动。"""
        item = self.outline.itemAt(pos)
        if item is None or item.isDisabled():   # 空态引导占位项不弹菜单
            return
        self.outline.setCurrentItem(item)
        menu = QMenu(self)
        act_jump = menu.addAction("跳转到此处")
        act_copy = menu.addAction("复制标题文本")
        menu.addSeparator()
        act_exp = menu.addAction("展开子节点")
        act_col = menu.addAction("折叠子节点")
        menu.addSeparator()
        act_top = menu.addAction("移到开头")
        act_end = menu.addAction("移到末尾")
        act = menu.exec(self.outline.viewport().mapToGlobal(pos))
        if act is act_jump:
            self._on_outline_clicked(item)
        elif act is act_copy:
            text = item.data(0, Qt.UserRole + 1) or item.text(0)
            QApplication.clipboard().setText(str(text))
            win = getattr(self, "_win", None)
            if win is not None and hasattr(win, "show_status"):
                win.show_status("已复制标题文本")
        elif act is act_exp:
            self._set_children_expanded(item, True)
        elif act is act_col:
            self._set_children_expanded(item, False)
        elif act is act_top:
            self._outline_move(item, True)
        elif act is act_end:
            self._outline_move(item, False)

    def _outline_move(self, item, to_start):
        """把节点移到同级开头 / 末尾，随后复用拖拽调序通道把整段写回文档。"""
        try:
            parent = item.parent()
            if parent is None:
                i = self.outline.indexOfTopLevelItem(item)
                if i < 0:
                    return
                self.outline.takeTopLevelItem(i)
                if to_start:
                    self.outline.insertTopLevelItem(0, item)
                else:
                    self.outline.addTopLevelItem(item)
            else:
                i = parent.indexOfChild(item)
                if i < 0:
                    return
                parent.takeChild(i)
                if to_start:
                    parent.insertChild(0, item)
                else:
                    parent.addChild(item)
        except Exception:
            return
        self.outline.setCurrentItem(item)
        self._on_outline_dropped()

    def _set_children_expanded(self, item, expanded):
        """递归设置 item 全部嵌套子级的展开态（不改动 item 自身）。"""
        for i in range(item.childCount()):
            ch = item.child(i)
            ch.setExpanded(expanded)
            if ch.childCount():
                self._set_children_expanded(ch, expanded)

    def select_tab(self, tab):
        """切换侧栏标签页（文件 / 大纲）。"""
        self.btn_files.setChecked(tab == self.TAB_FILES)
        self.btn_outline.setChecked(tab == self.TAB_OUTLINE)
        self.stack.setCurrentIndex(tab)

    def show_outline(self):
        self.select_tab(self.TAB_OUTLINE)
        self.setVisible(True)

    # ================= 跨文件搜索 =================
    # v3.24 起检索逻辑整体移入 GlobalSearchPanel（查找对话框「全局搜索」页签）。
    # 静态工具方法以别名保留，供旧引用兼容。
    iter_files = staticmethod(GlobalSearchPanel.iter_files)
    _read_text = staticmethod(GlobalSearchPanel._read_text)

    def set_root(self, path):
        """文件列表根目录跟随当前文档；顶部显示当前文件名。空白项模式下忽略。"""
        if self._file_mode == "blank":
            return
        if path and os.path.isfile(path):
            self._cur_file = path
            self._cur_dir = os.path.dirname(path) or self._cur_dir
        elif path and os.path.isdir(path):
            self._cur_dir = path
            self._cur_file = None
        self._refresh_files()
        self._update_file_header()

    def clear_current_file(self):
        """v3.38（OUT-3）：切到未命名文档时清除文件上下文 —— 保留浏览目录，
        清 _cur_file 并取消列表高亮，避免用户误以为仍处于旧文件。"""
        if self._file_mode == "blank":
            return
        self._cur_file = None
        self._refresh_files()
        self.file_list.setCurrentRow(-1)
        self._update_file_header()

    def current_dir(self):
        """v3.38（OUT-5）：当前浏览目录（会话恢复记录用）。"""
        return self._cur_dir

    # ============ v3.38（FLP-1）：文件列表「默认打开路径」 ============
    @staticmethod
    def _dir_usable(path):
        """可用性探针：存在 + 是目录 + 可枚举（覆盖无访问权限）。任何异常视为不可用。"""
        try:
            if not path or not os.path.isdir(path):
                return False
            os.listdir(path)
            return True
        except Exception:      # noqa: BLE001 —— OSError（权限）/ 设备名 / 超长路径
            return False

    def resolve_default_dir(self):
        """解析配置的「默认打开路径」→ 可用绝对目录，或 None（未配置 / 不可用）。

        字段：QSettings `files/defaultDir`（默认值 = config.FILE_LIST_DEFAULT_DIR = ""）
        取值规则：
          · 空 / 纯空白 → None（不启用）
          · `~` 开头 → 展开为用户主目录
          · 绝对路径 → 原样规范化
          · 相对路径 → 相对**应用目录 HERE** 解析（与启动时工作目录无关）
        安全回退：不存在 / 不是目录 / 无访问权限 → None，由调用方回退到根层；全程不报错。
        """
        try:
            raw = str(self._win.file_list_default_dir() or "").strip()
        except Exception:      # noqa: BLE001 —— 取配置失败视为未配置
            return None
        if not raw:
            return None
        try:
            p = os.path.expanduser(raw)
            if not os.path.isabs(p):
                p = os.path.join(HERE, p)
            p = os.path.abspath(p)
        except Exception:      # noqa: BLE001
            return None
        return p if self._dir_usable(p) else None

    def highlight_dir(self, path):
        """在当前层列表里高亮 path 对应条目；未命中则选中首项（保证列表有焦点）。

        本模型是 Typora 式**逐级浏览的单层列表**（没有懒加载目录树），「高亮目录节点」
        在本模型下等价于：目标目录本身出现在当前列表时选中它（如盘符层的 `D:\\`），
        否则定位到目标目录的内容层并把焦点落在首项。
        """
        if not path:
            return False
        try:
            target = os.path.normcase(os.path.abspath(path)).rstrip("\\/")
        except Exception:      # noqa: BLE001
            return False
        for row in range(self.file_list.count()):
            it = self.file_list.item(row)
            d = it.data(Qt.UserRole) if it is not None else None
            if not d:
                continue
            try:
                cand = os.path.normcase(os.path.abspath(d[1])).rstrip("\\/")
            except Exception:      # noqa: BLE001
                continue
            if cand == target:
                self.file_list.setCurrentRow(row)
                self.file_list.scrollToItem(it, QAbstractItemView.PositionAtCenter)
                return True
        if self.file_list.count():
            self.file_list.setCurrentRow(0)
        return False

    def apply_default_dir(self, toast=False):
        """按「默认打开路径」定位（设置页改完即时生效）。空 / 不可用 → 回退根层。"""
        if self._file_mode == "blank":
            return False
        target = self.resolve_default_dir()
        if not target:
            self._cur_dir = None
            self._cur_file = None
            self._refresh_files()
            self._update_file_header()
            if toast:
                self._win.show_status("文件列表默认路径为空或不可用，已回退到「此电脑」")
            return False
        self.set_root(target)
        self.highlight_dir(target)
        if toast:
            self._win.show_status(f"文件列表已定位到默认路径 · {target}")
        return True

    def restore_initial_dir(self, once=False):
        """初始化定位（FLP-2 优先级链，v3.38）：

        **上次成功打开文件目录 → 上次访问目录 → 配置默认路径 →
        系统文档目录 → 当前工作目录 → 根层**

        · `once=True`（首次打开文件列表 tab 的补定位）：已定位过则不再移动，
          避免打断用户后续浏览。
        · 与既有加载逻辑兼容：本模型没有懒加载目录树，`_refresh_files()` 只列
          **当前一层**，子目录被逐级进入时才 listdir —— 不会预展开子树、
          也不会在启动时做递归扫描（大目录不阻塞启动）。
        """
        if once and self._initial_restored:
            return False
        self._initial_restored = True
        if self._file_mode == "blank":
            return False
        # ① 最近一次成功打开文件的目录（FLP-2，QSettings files/lastOpenDir）
        try:
            lod = str(self._win.last_open_dir() or "")
        except Exception:      # noqa: BLE001
            lod = ""
        if lod and self._dir_usable(lod):
            self.set_root(os.path.abspath(lod))
            self.highlight_dir(lod)
            return True
        # ② 上次访问的侧栏目录（FLP-1 既有，QSettings lastSidebarDir）
        try:
            last = str(self._win.last_sidebar_dir() or "")
        except Exception:      # noqa: BLE001
            last = ""
        if last and self._dir_usable(last):
            self.set_root(os.path.abspath(last))
            self.highlight_dir(last)
            return True
        # ③ 配置的默认打开路径（FLP-1，系统设置可改）
        if self.apply_default_dir(toast=False):
            return True
        # ③½ v3.39.2（PATH-1）：首次启动（无任何记录）→ 临时文档（草稿）目录 ——
        # 应用自身的草稿保存处，比系统文档目录更贴近「打开上次工作区」的预期
        try:
            _draft = str(DRAFT_DIR or "")
            if _draft and not os.path.isdir(_draft):
                os.makedirs(_draft, exist_ok=True)
        except Exception:      # noqa: BLE001 —— 建目录失败按不可用处理
            _draft = ""
        if _draft and self._dir_usable(_draft):
            self.set_root(os.path.abspath(_draft))
            self.highlight_dir(_draft)
            return True
        # ④⑤ 系统级回退：文档目录 → 当前工作目录（FLP-2，全部不可用则落 ⑥）
        for cand in self._system_fallback_dirs():
            self.set_root(os.path.abspath(cand))
            self.highlight_dir(cand)
            return True
        # ⑥ 根层兜底
        self._cur_dir = None
        self._cur_file = None
        self._refresh_files()
        self._update_file_header()
        return False

    @staticmethod
    def _system_fallback_dirs():
        """FLP-2 系统级回退目录（按序取第一个可用项，可全空）：
        系统文档目录（QStandardPaths DocumentsLocation）→ 当前工作目录。"""
        out = []
        try:
            docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            if docs:
                out.append(docs)
        except Exception:      # noqa: BLE001
            pass
        try:
            out.append(os.getcwd())
        except Exception:      # noqa: BLE001
            pass
        return [p for p in out if Sidebar._dir_usable(p)]

    # 大纲默认展开层级：1~3 级直接可见，4 级及以下默认折叠（可手动展开）。
    # 级别可经 系统设置→通用 修改（OUTLINE_EXPAND_LEVEL 仅作默认值）
    OUTLINE_EXPAND_LEVEL = 3

    def set_outline_level(self, level):
        """设置大纲显示（默认展开）级别：1~6 级标题；切换后立即重建大纲树。"""
        try:
            level = int(level)
        except (TypeError, ValueError):
            return
        level = max(1, min(6, level))
        if level == self._outline_level:
            return
        self._outline_level = level
        # 强制重建（内容签名未变但展开级别变了）
        self._outline_sig = None
        self.set_outline(self._last_headings)

    def set_file_mode(self, mode):
        """设置文件列表显示模式：current=跟随当前文档（默认）/ blank=空白项。"""
        mode = "blank" if str(mode) == "blank" else "current"
        if mode == self._file_mode:
            return
        self._file_mode = mode
        if mode == "blank":
            self.file_list.clear()
            self._update_file_header()
        else:
            # 恢复跟随当前文档（无打开文件则回到「此电脑」层）
            fp = getattr(self._win, "file_path", None)
            if fp and os.path.isfile(fp):
                self._cur_file = fp
                self._cur_dir = os.path.dirname(fp) or self._cur_dir
            else:
                self._cur_file = None
            self._refresh_files()
            self._update_file_header()

    def set_outline(self, headings):
        """大纲树构建：h1~h{级别} 按层级展开；更深层级挂到最近的上级标题下并默认折叠。"""
        self._last_headings = headings
        # v3.43.0（OUT-LOOK）：级别过滤（0=全部；n=只看该级及其父级，保证祖先链不断层）
        flt = int(getattr(self, "_outline_filter", 0) or 0)
        # 内容未变化时跳过重建，避免闪烁与点击丢失
        # v3.31（#8）：签名不含分节字数 —— 字数变化原地更新后缀，不重建树（不抢点击）
        # v3.43.0：签名带上过滤级别 —— 切过滤必须重建
        sig = json.dumps([flt, [[h.get("index"), h.get("level"), h.get("text")]
                                for h in (headings or [])]], ensure_ascii=False)
        if sig == self._outline_sig:
            return
        self._outline_sig = sig
        cur_idx = None
        cur = self.outline.currentItem()
        if cur is not None:
            cur_idx = cur.data(0, Qt.UserRole)
        self.outline.blockSignals(True)
        self.outline.clear()
        self._outline_items = {}   # v3.31（#8）：标题块序号 -> 树节点
        last = {}   # 实际层级 -> 最近一个该层级条目
        shown = 0   # v3.43.0：过滤后可见标题数（底部计数）
        for h in headings or []:
            real = int(h["level"])
            if flt and real > flt:
                continue          # 过滤掉更深的层级（父级保留，层级链不断）
            shown += 1
            it = QTreeWidgetItem([h["text"]])
            it.setData(0, Qt.UserRole, h["index"])
            it.setData(0, Qt.UserRole + 1, h.get("text"))   # v3.38（OUT-4）：跳转校验用
            it.setToolTip(0, h["text"])
            self._outline_items[h["index"]] = it   # v3.31（#8）：字数后缀原地更新用
            if real > self._outline_level:
                it.setToolTip(0, h["text"] + f"\n（{real} 级标题，双击可展开/折叠）")
            # 挂到最近上级标题（h4 -> 最近的 h3；无 h3 时逐级向上找）
            parent = None
            for pl in range(real - 1, 0, -1):
                if pl in last:
                    parent = last[pl]
                    break
            if parent is None:
                self.outline.addTopLevelItem(it)
            else:
                parent.addChild(it)
            last[real] = it
            for deeper in [k for k in last if k > real]:
                del last[deeper]
            # 1~(级别-1) 级默认展开（保证第「级别」级可见）；该级别及更深默认折叠
            it.setExpanded(real < self._outline_level)
        # v3.44.9（OUT-STRIP2）：底部「N 个标题」计数行已移除；仅保留空态引导
        if not shown:
            ph = QTreeWidgetItem(["用 # 开始一行即可出现在大纲"])
            ph.setDisabled(True)
            ph.setToolTip(0, "任意一行以 # 开头即成为标题，会出现在这里")
            self.outline.addTopLevelItem(ph)
        self.outline.blockSignals(False)
        self._update_outline_words(headings or [])   # v3.31（#8）：分节字数后缀
        # 恢复选中项（按标题块序号匹配）
        if cur_idx is not None:
            def find(sel):
                for k in range(sel.childCount()):
                    c = sel.child(k)
                    if c.data(0, Qt.UserRole) == cur_idx:
                        return c
                    hit = find(c)
                    if hit is not None:
                        return hit
                return None
            for t in range(self.outline.topLevelItemCount()):
                top = self.outline.topLevelItem(t)
                if top.data(0, Qt.UserRole) == cur_idx:
                    self.outline.setCurrentItem(top)
                    break
                hit = find(top)
                if hit is not None:
                    self.outline.setCurrentItem(hit)
                    break

    # ================= v3.43.0（OUT-LOOK）大纲过滤 / 工具钮 =================
    def set_outline_filter(self, level):
        """设置级别过滤（0=全部 / 1~3=只看该级及其父级），立即按当前数据重建。
        v3.44.8（OUT-STRIP）：大纲 UI 不再暴露 H1/H2/H3 过滤 chip，仅保留内部逻辑。"""
        try:
            level = max(0, min(3, int(level)))
        except (TypeError, ValueError):
            return
        if level == getattr(self, "_outline_filter", 0):
            return
        self._outline_filter = level
        self._outline_sig = None      # 强制重建（签名含过滤级别）
        self.set_outline(self._last_headings)

    def refresh_outline(self):
        """重建大纲（按当前过滤与显示级别重新生成，不重新解析文档）。"""
        self._outline_sig = None
        self.set_outline(self._last_headings)
        win = getattr(self, "_win", None)
        if win is not None and hasattr(win, "show_status"):
            win.show_status("大纲已重建")

    def toggle_outline_fold(self):
        """折叠全部 / 展开全部（按当前是否还有展开节点自动取反）。"""
        tree = self.outline
        any_open = False
        stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        while stack:
            it = stack.pop()
            if it.isExpanded():
                any_open = True
                break
            stack.extend(it.child(i) for i in range(it.childCount()))
        if any_open:
            tree.collapseAll()
            self.btn_ol_fold.setText("⌃")
        else:
            tree.expandAll()
            self.btn_ol_fold.setText("⌄")

    # ================= v3.31（#8）大纲分节字数 =================
    def set_outline_words(self, on):
        """v3.31.2（#3）：分节字数后缀显示开关，切换后原地刷新（不重建树）。"""
        self._outline_words = bool(on)
        self._update_outline_words(self._last_headings or [])

    def _update_outline_words(self, headings):
        """分节字数后缀：原地 setText，不重建树（避免轮询闪烁 / 丢点击）。"""
        show = getattr(self, "_outline_words", False)
        items = getattr(self, "_outline_items", None) or {}
        for h in headings:
            it = items.get(h.get("index"))
            if it is None:
                continue
            base = h.get("text") or ""
            suffix = ""
            if show:
                w = int(h.get("words") or 0)
                suffix = f"　·　{w:,} 字" if w else ""
            if it.text(0) != base + suffix:
                it.setText(0, base + suffix)

    # ================= v3.31（#7）大纲拖拽调序 =================
    def _on_outline_dropped(self):
        """拖放完成（OutlineTree.dropEvent 回调）：按新视觉顺序发整段重排请求。"""
        cur = self.outline.currentItem()
        if cur is None:
            return
        parent = cur.parent()
        n = parent.childCount() if parent is not None else self.outline.topLevelItemCount()
        ends = {}
        for h in (self._last_headings or []):
            if h.get("end") is not None:
                ends[h.get("index")] = h["end"]
        pairs = []
        for i in range(n):
            it = parent.child(i) if parent is not None else self.outline.topLevelItem(i)
            idx = it.data(0, Qt.UserRole)
            if idx is None or idx not in ends:
                return   # 大纲缓存与树不一致（内容刚变化），放弃本次调序
            pairs.append([int(idx), int(ends[idx])])
        if len(pairs) >= 2:
            self._win.reorder_sections(pairs)

    # ================= v3.31.2 文件页管理操作（自「目录」页迁入） =================
    def _file_new_file(self, d):
        name, ok = QInputDialog.getText(self, "新建 Markdown 文件", "文件名：",
                                        text="未命名.md")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if not name.lower().endswith(self.MD_EXTS):
            name += ".md"
        p = os.path.join(d, name)
        if os.path.exists(p):
            QMessageBox.warning(self, "新建文件", "同名文件已存在。")
            return
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write("# " + os.path.splitext(name)[0] + "\n\n")
        except OSError as e:
            QMessageBox.critical(self, "新建文件", str(e))
            return
        self._refresh_files()
        self._win.open_file(p)

    def _file_new_dir(self, d):
        name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名：")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        p = os.path.join(d, name)
        if os.path.exists(p):
            QMessageBox.warning(self, "新建文件夹", "同名文件夹已存在。")
            return
        try:
            os.makedirs(p)
        except OSError as e:
            QMessageBox.critical(self, "新建文件夹", str(e))
            return
        self._refresh_files()

    def _file_rename(self, p):
        base = os.path.basename(p)
        new, ok = QInputDialog.getText(self, "重命名", "新名称：", text=base)
        if not ok:
            return
        new = new.strip()
        if not new or new == base:
            return
        if any(ch in new for ch in '\\/:*?"<>|'):
            QMessageBox.warning(self, "重命名", "名称不能包含 \\/:*?\"<>| 等字符。")
            return
        np = os.path.join(os.path.dirname(p), new)
        if os.path.exists(np):
            QMessageBox.warning(self, "重命名", "目标名称已存在。")
            return
        try:
            os.rename(p, np)
        except OSError as e:
            QMessageBox.critical(self, "重命名", str(e))
            return
        self._win.rename_current_file(p, np)
        if os.path.abspath(p) == os.path.abspath(self._cur_file or ""):
            self._cur_file = np
        self._refresh_files()

    def _file_delete(self, p):
        is_cur = p == getattr(self._win, "file_path", None)
        tip = ("\n注意：这是当前正在编辑的文件，删除后请不要再保存该标签\n"
               "（否则会以原内容重建同名文件）。") if is_cur else ""
        if QMessageBox.question(self, "删除确认",
                                f"确定把\n{p}\n移入回收站吗？{tip}",
                                QMessageBox.Ok | QMessageBox.Cancel) != QMessageBox.Ok:
            return
        if self._win.recycle_path(p):
            self._refresh_files()
            self._win.show_status("已移入回收站：" + p)
