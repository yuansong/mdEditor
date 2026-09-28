# -*- coding: utf-8 -*-
"""v3.32（#5/#7/#8）sidebar.py 补丁：目录树 + 大纲拖拽调序 + 分节字数。幂等，每处恰好命中 1 次。"""
import io
import sys

P = r"E:\WorkBuddy\md-editor\src\sidebar.py"
src = io.open(P, encoding="utf-8").read()

EDITS = []


def rep(old, new, n=1):
    EDITS.append((old, new, n))


# ---- 1) imports（顺带补上 _on_file_menu 一直在用的 QMenu —— 原先缺失属潜在 NameError）----
rep("""from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
    QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)""", """from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QButtonGroup, QCheckBox, QComboBox,
    QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPushButton, QSizePolicy,
    QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)""")

# ---- 2) 目录树跳过清单 ----
rep("""SEARCH_SKIP_DIRS = {".git", ".svn", "node_modules", "__pycache__", ".idea", ".vscode"}""",
    """SEARCH_SKIP_DIRS = {".git", ".svn", "node_modules", "__pycache__", ".idea", ".vscode"}
# v3.31（#5）：目录树跳过的目录（在搜索跳过清单上补上编辑器自身的历史目录）
TREE_SKIP_DIRS = SEARCH_SKIP_DIRS | {".mdeditor-history"}""")

# ---- 3) OutlineTree 类（同级拖拽调序）----
rep("""class Sidebar(QWidget):
    \"\"\"Typora 风格左侧边栏：文件列表（一级目录）/ 大纲 两个标签页。\"\"\"""",
    '''class OutlineTree(QTreeWidget):
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
    """Typora 风格左侧边栏：文件列表（一级目录）/ 大纲 / 文件目录树 三个标签页。"""''')

# ---- 4) 标签页常量 ----
rep("    TAB_FILES, TAB_OUTLINE = 0, 1",
    "    TAB_FILES, TAB_OUTLINE, TAB_TREE = 0, 1, 2   # v3.31（#5）：新增「目录」页")

# ---- 5) 顶部标签加「目录」按钮 ----
rep("""        self.btn_files = QToolButton(tabcap, text="文件")
        self.btn_outline = QToolButton(tabcap, text="大纲")
        for b in (self.btn_files, self.btn_outline):""",
    """        self.btn_files = QToolButton(tabcap, text="文件")
        self.btn_outline = QToolButton(tabcap, text="大纲")
        self.btn_tree = QToolButton(tabcap, text="目录")
        for b in (self.btn_files, self.btn_outline, self.btn_tree):""")

# ---- 6) 按钮组注册 ----
rep("""        self._tabs.addButton(self.btn_files)
        self._tabs.addButton(self.btn_outline)
        self.btn_files.setChecked(True)
        self.btn_files.clicked.connect(lambda: self.select_tab(self.TAB_FILES))
        self.btn_outline.clicked.connect(lambda: self.select_tab(self.TAB_OUTLINE))""",
    """        self._tabs.addButton(self.btn_files)
        self._tabs.addButton(self.btn_outline)
        self._tabs.addButton(self.btn_tree)
        self.btn_files.setChecked(True)
        self.btn_files.clicked.connect(lambda: self.select_tab(self.TAB_FILES))
        self.btn_outline.clicked.connect(lambda: self.select_tab(self.TAB_OUTLINE))
        self.btn_tree.clicked.connect(lambda: self.select_tab(self.TAB_TREE))""")

# ---- 7) 大纲改用 OutlineTree + 目录树面板构建 ----
rep("""        # 大纲：树形结构，默认展开到 3 级，更深层级默认折叠（可手动展开）
        self.outline = QTreeWidget(self)
        self.outline.setHeaderHidden(True)
        self.outline.setIndentation(18)   # v3.26：缩进加大，容纳加粗展开箭头
        self.outline.setExpandsOnDoubleClick(True)
        self.outline.setVerticalScrollMode(QTreeWidget.ScrollPerPixel)
        self.outline.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.outline.itemClicked.connect(self._on_outline_clicked)""",
    """        # 大纲：树形结构，默认展开到 3 级，更深层级默认折叠（可手动展开）
        # v3.31（#7）：OutlineTree 支持同级拖拽调序（整段移动章节）
        self.outline = OutlineTree(self, self)
        self.outline.setHeaderHidden(True)
        self.outline.setIndentation(18)   # v3.26：缩进加大，容纳加粗展开箭头
        self.outline.setExpandsOnDoubleClick(True)
        self.outline.setVerticalScrollMode(QTreeWidget.ScrollPerPixel)
        self.outline.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.outline.setDragDropMode(QAbstractItemView.InternalMove)
        self.outline.itemClicked.connect(self._on_outline_clicked)

        # v3.31（#5）：树形文件目录（懒加载子目录 / 右键管理 / 当前文档加粗）
        self.tree_root_lbl = QPushButton(self)
        self.tree_root_lbl.setObjectName("fileHeader")
        self.tree_root_lbl.setCursor(Qt.PointingHandCursor)
        self.tree_root_lbl.setText("📁 （未选择目录）")
        self.tree_root_lbl.setToolTip("双击选择根目录；右键可恢复跟随当前文档")
        self.tree_root_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tree_root_lbl.installEventFilter(self)
        self.tree_root_lbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_root_lbl.customContextMenuRequested.connect(self._on_tree_root_menu)
        self.tree_refresh = QToolButton(self)
        self.tree_refresh.setText("⟳")
        self.tree_refresh.setToolTip("刷新目录树")
        self.tree_refresh.setCursor(Qt.PointingHandCursor)
        self.tree_refresh.clicked.connect(self.tree_reload)
        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setVerticalScrollMode(QTreeWidget.ScrollPerPixel)
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree.itemExpanded.connect(self._on_tree_expand)
        self.tree.itemDoubleClicked.connect(self._on_tree_dbl)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_menu)
        self.tree_panel = QWidget(self)
        tp_lay = QVBoxLayout(self.tree_panel)
        tp_lay.setContentsMargins(0, 0, 0, 0)
        tp_lay.setSpacing(2)
        tp_row = QHBoxLayout()
        tp_row.setContentsMargins(0, 0, 0, 0)
        tp_row.setSpacing(2)
        tp_row.addWidget(self.tree_root_lbl, 1)
        tp_row.addWidget(self.tree_refresh)
        tp_lay.addLayout(tp_row)
        tp_lay.addWidget(self.tree, 1)""")

# ---- 8) stack 挂第三页 + 根目录持久化 ----
rep("""        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.file_panel)
        self.stack.addWidget(self.outline)
        lay.addWidget(self.stack, 1)

        # 初始进入「此电脑」层
        self._refresh_files()
        self._update_file_header()""",
    """        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.file_panel)
        self.stack.addWidget(self.outline)
        self.stack.addWidget(self.tree_panel)
        lay.addWidget(self.stack, 1)

        # 初始进入「此电脑」层
        self._refresh_files()
        self._update_file_header()
        # v3.31（#5）：目录树根目录 —— 上次使用的根（无则跟随当前文档目录）
        self._tree_root = None
        _saved_root = win._settings.value("treeRoot", "") or ""
        if os.path.isdir(_saved_root):
            self._tree_root = _saved_root
        self.tree_reload()""")

# ---- 9) 展开箭头配色同步目录树 ----
rep("""        self.outline.setStyleSheet("\\n".join(qss))""",
    """        self.outline.setStyleSheet("\\n".join(qss))
        if getattr(self, "tree", None) is not None:
            self.tree.setStyleSheet("\\n".join(qss))   # v3.31（#5）：目录树箭头同色""")

# ---- 10) select_tab 三页 ----
rep("""    def select_tab(self, tab):
        \"\"\"切换侧栏标签页（文件 / 大纲）。\"\"\"
        self.btn_files.setChecked(tab == self.TAB_FILES)
        self.btn_outline.setChecked(tab == self.TAB_OUTLINE)
        self.stack.setCurrentIndex(tab)""",
    """    def select_tab(self, tab):
        \"\"\"切换侧栏标签页（文件 / 大纲 / 目录）。\"\"\"
        self.btn_files.setChecked(tab == self.TAB_FILES)
        self.btn_outline.setChecked(tab == self.TAB_OUTLINE)
        self.btn_tree.setChecked(tab == self.TAB_TREE)
        self.stack.setCurrentIndex(tab)""")

# ---- 11) eventFilter：根标签双击选根目录 ----
rep("""    def eventFilter(self, obj, ev):
        if obj is self.file_header and ev.type() == QEvent.MouseButtonDblClick:
            self.go_up()
            return True
        return super().eventFilter(obj, ev)""",
    """    def eventFilter(self, obj, ev):
        if obj is self.file_header and ev.type() == QEvent.MouseButtonDblClick:
            self.go_up()
            return True
        # v3.31（#5）：目录树根标签双击 = 选择新的根目录
        if obj is self.tree_root_lbl and ev.type() == QEvent.MouseButtonDblClick:
            d = QFileDialog.getExistingDirectory(
                self, "选择目录树根文件夹", self.tree_root() or "")
            if d:
                self.set_tree_root(d)
            return True
        return super().eventFilter(obj, ev)""")

# ---- 12) set_outline：签名剔除字数 + 节点字典 ----
rep("""        sig = json.dumps(headings or [], ensure_ascii=False)""",
    """        # v3.31（#8）：签名不含分节字数 —— 字数变化原地更新后缀，不重建树（不抢点击）
        sig = json.dumps([[h.get("index"), h.get("level"), h.get("text")]
                          for h in (headings or [])], ensure_ascii=False)""")

rep("""        self.outline.blockSignals(True)
        self.outline.clear()
        last = {}   # 实际层级 -> 最近一个该层级条目""",
    """        self.outline.blockSignals(True)
        self.outline.clear()
        self._outline_items = {}   # v3.31（#8）：标题块序号 -> 树节点
        last = {}   # 实际层级 -> 最近一个该层级条目""")

rep("""            it = QTreeWidgetItem([h["text"]])
            it.setData(0, Qt.UserRole, h["index"])
            it.setToolTip(0, h["text"])""",
    """            it = QTreeWidgetItem([h["text"]])
            it.setData(0, Qt.UserRole, h["index"])
            it.setToolTip(0, h["text"])
            self._outline_items[h["index"]] = it   # v3.31（#8）：字数后缀原地更新用""")

rep("""        self.outline.blockSignals(False)
        # 恢复选中项（按标题块序号匹配）""",
    """        self.outline.blockSignals(False)
        self._update_outline_words(headings or [])   # v3.31（#8）：分节字数后缀
        # 恢复选中项（按标题块序号匹配）""")

fail = [i for i, (o, nw, n) in enumerate(EDITS) if src.count(o) != n]
if fail:
    for i in fail:
        print("ANCHOR FAIL #%d count=%d" % (i, src.count(EDITS[i][0])))
    sys.exit(1)
for o, nw, _n in EDITS:
    src = src.replace(o, nw)

# ---- 13) 文件末尾追加：字数更新 / 拖拽回调 / 目录树方法组 ----
src = src.rstrip("\n") + """

    # ================= v3.31（#8）大纲分节字数 =================
    def _update_outline_words(self, headings):
        \"\"\"分节字数后缀：原地 setText，不重建树（避免轮询闪烁 / 丢点击）。\"\"\"
        items = getattr(self, "_outline_items", None) or {}
        for h in headings:
            it = items.get(h.get("index"))
            if it is None:
                continue
            w = int(h.get("words") or 0)
            base = h.get("text") or ""
            suffix = f"　·　{w:,} 字" if w else ""
            if it.text(0) != base + suffix:
                it.setText(0, base + suffix)

    # ================= v3.31（#7）大纲拖拽调序 =================
    def _on_outline_dropped(self):
        \"\"\"拖放完成（OutlineTree.dropEvent 回调）：按新视觉顺序发整段重排请求。\"\"\"
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

    # ================= v3.31（#5）树形文件目录 =================
    def tree_root(self):
        return getattr(self, "_tree_root", None)

    def set_tree_root(self, path, persist=True):
        \"\"\"设置目录树根目录；persist=False 用于跟随当前文档（不写设置）。\"\"\"
        path = os.path.abspath(path) if path else None
        if path and not os.path.isdir(path):
            path = None
        self._tree_root = path
        if persist and path:
            self._win._settings.setValue("treeRoot", path)
        self.tree_reload()

    def tree_follow(self, doc_path):
        \"\"\"打开 / 切换文档时：未自选根目录则跟随文档目录；总是刷新当前文件高亮。\"\"\"
        root = getattr(self, "_tree_root", None)
        if doc_path and os.path.isfile(doc_path):
            if not root:
                self.set_tree_root(os.path.dirname(os.path.abspath(doc_path)),
                                   persist=False)
                return
        self.tree_highlight(doc_path)

    def tree_reload(self):
        if not hasattr(self, "tree"):
            return
        self.tree.blockSignals(True)
        self.tree.clear()
        root = getattr(self, "_tree_root", None)
        base = os.path.basename((root or "").rstrip("/\\\\")) or (root or "")
        self.tree_root_lbl.setText("📁 " + (base or "（未选择目录）"))
        self.tree_root_lbl.setToolTip(root or "双击选择根目录；右键可恢复跟随当前文档")
        if not root:
            empty = QTreeWidgetItem(["（双击上方选择根目录）"])
            empty.setFlags(Qt.ItemIsEnabled)
            self.tree.addTopLevelItem(empty)
            self.tree.blockSignals(False)
            return
        self._fill_dir(self.tree.invisibleRootItem(), root)
        self.tree.blockSignals(False)
        self.tree_highlight(getattr(self._win, "file_path", None))

    def _tree_children(self, d):
        try:
            names = os.listdir(d)
        except OSError:
            return [], []
        dirs = sorted(n for n in names
                      if not n.startswith(".") and n not in TREE_SKIP_DIRS
                      and not n.lower().endswith(".assets")
                      and os.path.isdir(os.path.join(d, n)))
        files = sorted(n for n in names
                       if os.path.isfile(os.path.join(d, n))
                       and n.lower().endswith(self.MD_EXTS))
        return dirs, files

    def _fill_dir(self, parent_item, d):
        parent_item.takeChildren()
        dirs, files = self._tree_children(d)
        for n in dirs:
            p = os.path.join(d, n)
            it = QTreeWidgetItem(["📁 " + n])
            it.setData(0, Qt.UserRole, ("dir", p))
            it.setToolTip(0, p)
            it.addChild(QTreeWidgetItem())   # 占位子节点：保证显示展开箭头（懒加载）
            it.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            parent_item.addChild(it)
        for n in files:
            p = os.path.join(d, n)
            it = QTreeWidgetItem(["📄 " + n])
            it.setData(0, Qt.UserRole, ("file", p))
            it.setToolTip(0, p)
            parent_item.addChild(it)
        if not dirs and not files:
            empty = QTreeWidgetItem(["（空文件夹）"])
            empty.setFlags(Qt.ItemIsEnabled)
            parent_item.addChild(empty)

    def _on_tree_expand(self, item):
        data = item.data(0, Qt.UserRole)
        if not data or data[0] != "dir":
            return
        if item.childCount() == 1 and item.child(0).data(0, Qt.UserRole) is None:
            self._fill_dir(item, data[1])   # 替换占位子节点（懒加载）
            self.tree_highlight(getattr(self._win, "file_path", None))

    def _on_tree_dbl(self, item, _col=0):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        if data[0] == "file":
            self._win.open_file(data[1])
        else:
            item.setExpanded(not item.isExpanded())

    def tree_highlight(self, doc_path):
        \"\"\"当前文档加粗（仅扫描已加载节点，不强行展开）。\"\"\"
        target = os.path.abspath(doc_path) if doc_path and os.path.isfile(doc_path) else None

        def walk(item):
            for k in range(item.childCount()):
                c = item.child(k)
                data = c.data(0, Qt.UserRole)
                hit = bool(target and data and data[0] == "file"
                           and os.path.abspath(data[1]) == target)
                f = c.font(0)
                if f.bold() != hit:
                    f.setBold(hit)
                    c.setFont(0, f)
                walk(c)

        walk(self.tree.invisibleRootItem())

    def _on_tree_root_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("刷新目录树", self.tree_reload)
        menu.addAction("跟随当前文档目录",
                       lambda: self.set_tree_root(
                           os.path.dirname(self._win.file_path)
                           if self._win.file_path else None, persist=False))
        menu.exec(self.tree_root_lbl.mapToGlobal(pos))

    def _on_tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        data = item.data(0, Qt.UserRole) if item is not None else None
        menu = QMenu(self)
        menu.addAction("刷新", self.tree_reload)
        cur_dir = None
        if data and data[0] == "dir":
            cur_dir = data[1]
        elif data and data[0] == "file":
            cur_dir = os.path.dirname(data[1])
        cur_dir = cur_dir or getattr(self, "_tree_root", None)
        if cur_dir:
            menu.addSeparator()
            menu.addAction("新建 Markdown 文件", lambda: self._tree_new_file(cur_dir))
            menu.addAction("新建文件夹", lambda: self._tree_new_dir(cur_dir))
        if item is not None and data:
            p = data[1]
            menu.addSeparator()
            if data[0] == "file":
                menu.addAction("打开", lambda: self._win.open_file(p))
                menu.addAction("用外部程序打开", lambda: self._win.open_external(p))
            menu.addAction("在资源管理器中显示", lambda: self._win.show_in_explorer(p))
            menu.addSeparator()
            menu.addAction("重命名", lambda: self._tree_rename(p))
            menu.addAction("删除（移入回收站）", lambda: self._tree_delete(p))
        menu.exec(self.tree.mapToGlobal(pos))

    def _tree_new_file(self, d):
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
                f.write("# " + os.path.splitext(name)[0] + "\\n\\n")
        except OSError as e:
            QMessageBox.critical(self, "新建文件", str(e))
            return
        self.tree_reload()
        self._win.open_file(p)

    def _tree_new_dir(self, d):
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
        self.tree_reload()

    def _tree_rename(self, p):
        base = os.path.basename(p)
        new, ok = QInputDialog.getText(self, "重命名", "新名称：", text=base)
        if not ok:
            return
        new = new.strip()
        if not new or new == base:
            return
        if any(ch in new for ch in '\\\\/:*?"<>|'):
            QMessageBox.warning(self, "重命名", "名称不能包含 \\\\/:*?\\"<>| 等字符。")
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
        self.tree_reload()

    def _tree_delete(self, p):
        is_cur = p == getattr(self._win, "file_path", None)
        tip = ("\\n注意：这是当前正在编辑的文件，删除后请不要再保存该标签\\n"
               "（否则会以原内容重建同名文件）。") if is_cur else ""
        if QMessageBox.question(self, "删除确认",
                                f"确定把\\n{p}\\n移入回收站吗？{tip}",
                                QMessageBox.Ok | QMessageBox.Cancel) != QMessageBox.Ok:
            return
        if self._win.recycle_path(p):
            self.tree_reload()
            self._win.show_status("已移入回收站：" + p)
"""

io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("sidebar.py patched: %d edits" % len(EDITS))
