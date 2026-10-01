# -*- coding: utf-8 -*-
"""左侧边栏：文件列表（此电脑 / 逐级浏览）+ 大纲 两个标签页。

v3.24：跨文件全局搜索抽为独立面板类 GlobalSearchPanel，
内嵌到「查找 / 替换」对话框的「全局搜索」页签，侧栏不再承载搜索面板。"""
import json
import os
import re
import tempfile

from PySide6.QtCore import QEvent, Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QButtonGroup, QCheckBox, QComboBox,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPushButton, QSizePolicy,
    QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from styles import SIDEBAR_QSS

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

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("sidebar")
        self.setFixedWidth(252)
        self.setStyleSheet(SIDEBAR_QSS)
        self._outline_sig = None
        self._outline_level = 3      # 大纲展开显示级别（1~6，系统设置可改）
        self._outline_words = False  # v3.31.2（#3）：分节字数后缀开关（默认关）
        self._last_headings = None   # 最近一次大纲数据（级别切换时复用重建）
        self._file_mode = "current"  # 文件列表显示模式：current=跟随当前文档 / blank=空白项

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(4)

        # ---- 顶部标签（文件 / 大纲，均分宽度）----
        tabcap = QWidget(self)
        tabcap.setObjectName("tabcap")
        tab_row = QHBoxLayout(tabcap)
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(2)
        self.btn_files = QToolButton(tabcap, text="文件")
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
        cap_row.setContentsMargins(10, 6, 10, 2)
        cap_row.addWidget(tabcap)
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
        self.file_list.itemDoubleClicked.connect(self._on_file_dbl)
        # v3.25：右键菜单 —— 在资源管理器中显示 / 用外部程序打开（原「文件」菜单项迁入）
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_file_menu)

        self.file_panel = QWidget(self)
        fp_lay = QVBoxLayout(self.file_panel)
        fp_lay.setContentsMargins(0, 0, 0, 0)
        fp_lay.setSpacing(2)
        fp_lay.addWidget(self.file_header)
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

        # v3.31.2：树形「目录」页已移除（与文件页重合，管理操作迁文件页右键）
        # 全局搜索面板（v3.24 起移入「查找」对话框的「全局搜索」页签）：
        # 面板构造与检索逻辑见 GlobalSearchPanel，侧栏只保留文件 / 大纲两个标签页。
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.file_panel)
        self.stack.addWidget(self.outline)
        lay.addWidget(self.stack, 1)

        # 初始进入「此电脑」层
        self._refresh_files()
        self._update_file_header()
        # v3.26：加粗放大的展开/收拢箭头（颜色随主题）
        self.set_tree_arrows(getattr(win, "_theme", "light"))

    # ---- v3.26：大纲树展开/收拢箭头 ----
    def set_tree_arrows(self, theme_id="light"):
        """用运行时绘制的 chevron 折线箭头替换 QTreeWidget 默认的细小分支箭头。

        v3.31.3（#21 美化）：实心三角 → 细线 chevron（› / ˅，2.2px 圆头折线，
        VS Code 风格），16×16 px；颜色取主题次级文字色，选中行箭头换主题强调色
        （:selected 变体）。换肤时由 mainwindow.apply_theme 再次调用。"""
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
            """kind: closed=右向 ›（收拢）/ open=下向 ˅（展开）。
            细线 chevron：圆头折线，居中绘制在 16×16 画布。"""
            pm = QPixmap(16, 16)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            pen = QPen(color, 2.2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            if kind == "closed":
                pts = [QPointF(6.0, 3.5), QPointF(11.0, 8.0), QPointF(6.0, 12.5)]
            else:
                pts = [QPointF(3.5, 6.0), QPointF(8.0, 11.0), QPointF(12.5, 6.0)]
            p.drawPolyline(QPolygonF(pts))
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

    # ---- 行为 ----
    def eventFilter(self, obj, ev):
        if obj is self.file_header and ev.type() == QEvent.MouseButtonDblClick:
            self.go_up()
            return True
        return super().eventFilter(obj, ev)

    def _on_file_dbl(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        kind, p = data
        if kind == "dir":
            self._cur_dir = p
            self._refresh_files()
            self._update_file_header()
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
                menu.addAction("刷新", self._refresh_files)
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
        for n in dirs:
            p = os.path.join(self._cur_dir, n)
            it = QListWidgetItem("📁 " + n)
            it.setData(Qt.UserRole, ("dir", p))
            it.setToolTip(p)
            self.file_list.addItem(it)
        for n in files:
            p = os.path.join(self._cur_dir, n)
            it = QListWidgetItem("📄 " + n)
            it.setData(Qt.UserRole, ("file", p))
            it.setToolTip(p)
            self.file_list.addItem(it)
        # 高亮当前文件
        if self._cur_file:
            for row in range(self.file_list.count()):
                d = self.file_list.item(row).data(Qt.UserRole)
                if d and d[1] == self._cur_file:
                    self.file_list.setCurrentRow(row)
                    break
        self._apply_file_filter()   # v3.29d（UX #6）：刷新后保持过滤词生效

    def _apply_file_filter(self):
        """v3.29d（UX #6）：按过滤框关键词隐藏不匹配的条目（输入即筛）。"""
        if not hasattr(self, "file_filter"):
            return
        q = self.file_filter.text().strip().lower()
        for row in range(self.file_list.count()):
            it = self.file_list.item(row)
            d = it.data(Qt.UserRole)
            name = (d[1] if d else it.text()) or ""
            it.setHidden(bool(q) and q not in os.path.basename(name).lower())

    def _update_file_header(self):
        # 顶部始终显示当前所在文件夹（Typora 风格），双击逐级返回
        if self._file_mode == "blank":
            self.file_header.setText("空白")
            self.file_header.setToolTip("文件列表已设置为空白项\n（可在 系统设置→通用 修改）")
            return
        if self._cur_dir is None:
            self.file_header.setText("💻 此电脑")
            self.file_header.setToolTip("我的电脑（顶层）\n列表为所有盘符")
        else:
            base = os.path.basename(self._cur_dir.rstrip("/\\")) or self._cur_dir
            self.file_header.setText("📁 " + base)
            self.file_header.setToolTip(self._cur_dir + "\n双击返回上一级目录")

    def _on_outline_clicked(self, item, _col=0):
        self._win.jump_to_heading(item.data(0, Qt.UserRole))

    # ================= v3.32.2（OUT-2）大纲右键：展开 / 折叠子节点 =================
    def _on_outline_menu(self, pos):
        """大纲节点右键菜单：展开 / 折叠子节点（递归作用于全部嵌套子级，
        不影响其他分支）；无子节点时不弹菜单。"""
        item = self.outline.itemAt(pos)
        if item is None or item.childCount() == 0:
            return
        self.outline.setCurrentItem(item)
        menu = QMenu(self)
        act_exp = menu.addAction("展开子节点")
        act_col = menu.addAction("折叠子节点")
        act = menu.exec(self.outline.viewport().mapToGlobal(pos))
        if act is act_exp:
            self._set_children_expanded(item, True)
        elif act is act_col:
            self._set_children_expanded(item, False)

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
        # 内容未变化时跳过重建，避免闪烁与点击丢失
        # v3.31（#8）：签名不含分节字数 —— 字数变化原地更新后缀，不重建树（不抢点击）
        sig = json.dumps([[h.get("index"), h.get("level"), h.get("text")]
                          for h in (headings or [])], ensure_ascii=False)
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
        for h in headings or []:
            real = int(h["level"])
            it = QTreeWidgetItem([h["text"]])
            it.setData(0, Qt.UserRole, h["index"])
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
