# -*- coding: utf-8 -*-
"""对话框组件：查找 / 替换、快捷键设置、系统设置、命令面板、版本历史。"""
import difflib
import json
import logging
import os
import re
from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QTextCursor, QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFrame, QGroupBox, QScrollArea, QHeaderView, QSizePolicy,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QKeySequenceEdit, QRadioButton, QSlider, QSplitter, QSpinBox,
    QStackedWidget, QTabWidget, QTextBrowser, QTextEdit, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from config import BUILTIN_TEMPLATES, CODE_STYLES, FMTLOG_DIR, MMD_LEGACY, MMD_THEMES, TPL_NAME_MAX, js
from sidebar import GlobalSearchPanel
from styles import THEMES, palette
import uistyles
from diffmerge import (TwoPaneMergeMixin, build_hunks, build_rows,
                       build_sent_rows, esc_html)
from ai_connection import AIConnectionForm


# 斜杠（/）菜单可配置项（与 editor.html 中 SLASH_DEFS 对应）
# v3.30.3：移除「上标 / 下标」（supsub）一级项
# v3.31.3：footnote / deflist 合并为 refs「脚注与定义」
# v3.32（P1-1）：新增 tpl「模板」一级项
MENU_ITEMS = [("heading", "标题"), ("list", "列表"), ("table", "表格"), ("code", "代码块"),
              ("hr", "分割线"), ("quote", "引用"), ("image", "图片"), ("chart", "图表"),
              ("refs", "脚注与定义"), ("tpl", "模板"),
              ("math", "公式")]
SUB_HEADING = ["标题 1", "标题 2", "标题 3", "标题 4", "标题 5", "标题 6"]  # v3.31.1 移除标题7
SUB_LIST = ["无序列表", "有序列表", "待办事项"]
SUB_CHART = ["流程图", "时序图", "类图", "状态图", "E-R 图", "甘特图", "饼图"]
# v3.36（TPL-E）：SUB_TPL（内置模板名硬编码清单）已删除 —— 模板清单由
# templates.json 承载（config.BUILTIN_TEMPLATES 为初始内容），不再静态枚举
SUB_MATH = ["上标", "下标", "分式", "根式", "求和", "积分", "极限", "导数", "偏导数", "向量",
            "向量箭头", "矩阵", "希腊字母", "无穷", "约等于", "垂直", "平行", "因为所以",
            "属于", "并集交集", "加减", "乘", "度数", "圆周率"]


class _ThemedDialog(QDialog):
    """随主窗口主题换肤的对话框基类。"""

    def _apply_theme_qss(self, theme_id):
        # v3.39.15（UISTYLE-1）：对话框 QSS 走风格感知管线（当前主题 + 界面风格覆盖）
        self.setStyleSheet(uistyles.dialog_qss(theme_id))


class FindDialog(_ThemedDialog):
    """查找面板（v3.27 统一重设计：全局搜索 + 当前文件查找合一）。

    借鉴 VS Code / IntelliJ / Obsidian 的查找面板：
    · 顶部「当前文件 | 全局搜索」分段切换（替代下拉框，状态一目了然）；
    · 匹配计数以胶囊形式内嵌在搜索框右侧（VS Code 式），不再单独占一行；
    · 全局模式：范围 + 文件数 / 命中数合并为一行状态栏，下方结果树按文件分组；
    · 替换行仅在「当前文件」+ 替换模式显示（Ctrl+H 入口）；
    · 搜索词历史：↑ / ↓ 回溯本次会话输入过的关键词（Notepad++ / VS Code 惯例）；
    · 搜索默认支持正则表达式（写法无效时自动回退普通文本搜索）；
    · 「?」按钮弹出常用正则写法，点击即填入搜索框。

    兼容说明：scope_box 保留为隐藏 QComboBox 作为状态源（分段按钮驱动它），
    SCOPE_GLOBAL / SCOPE_FILE 常量与 show_replace / show_global / focus_find 不变。"""

    SCOPE_GLOBAL, SCOPE_FILE = 0, 1

    # 常用正则写法（帮助菜单，点击自动填入搜索框）
    REGEX_PRESETS = [
        ("数字（一段）", r"\d+"),
        ("英文单词", r"[A-Za-z]+"),
        ("中文汉字", r"[\u4e00-\u9fa5]+"),
        ("网址 URL", r"https?://[^\s)]+"),
        ("电子邮箱", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        ("日期（2026-01-02）", r"\d{4}-\d{2}-\d{2}"),
        ("时间（12:34）", r"\d{1,2}:\d{2}"),
        ("Markdown 链接", r"\[([^\]]+)\]\(([^)]+)\)"),
    ]

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("findDlg")
        self.setWindowTitle("查找 / 替换")
        self.setModal(False)
        # v3.48.18（FIND-UI）：560 宽时行 1 只剩 151px 给输入框 → 文字被裁剪。
        # 提升到 680x460 起步，并允许用户拉大（结果树随之变宽）。
        self.setMinimumSize(680, 460)
        self.resize(760, 540)
        self._apply_theme_qss(getattr(win, "_theme", "light"))
        self._replace_mode = False
        self._history = []          # 搜索词历史（会话内）
        self._hist_pos = -1

        # ---- 范围状态源：隐藏下拉框（入口焦点语义用，测试兼容）----
        self.scope_box = QComboBox(self)
        self.scope_box.addItem("全局搜索", "global")
        self.scope_box.addItem("当前文件", "file")
        self.scope_box.setVisible(False)
        self.scope_box.currentIndexChanged.connect(self._on_scope)

        # ---- 搜索框 + 计数胶囊 + 正则帮助 ----
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("搜索内容（支持正则，如 \\d+、https?://…）")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.installEventFilter(self)
        # v3.48.18（FIND-UI）：输入框保底宽度，保证长关键词 / 长占位提示可读；
        # 单行 QLineEdit 超长时内部水平滚动，不再挤压其它控件。
        self.find_edit.setMinimumWidth(240)

        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("countLbl")
        # v3.29b：提示行独立于搜索框行（初始隐藏），位于搜索框之下、结果列表之上
        self.count_lbl.setVisible(False)
        # v3.48.18（FIND-UI）：胶囊尺寸贴合文字 —— 旧版默认 Expanding，
        # 空文本时 QSS 背景仍铺满整行，形成一条无意义蓝色色带。
        self.count_lbl.setSizePolicy(QSizePolicy.Maximum,
                                     QSizePolicy.Preferred)

        self.help_btn = QToolButton(self)
        self.help_btn.setObjectName("helpBtn")
        self.help_btn.setText("?")
        self.help_btn.setToolTip("常用正则表达式写法")
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.clicked.connect(self._show_regex_help)

        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("替换为…")
        self.replace_edit.setClearButtonEnabled(True)

        b_prev = QPushButton("上一个")
        b_find = QPushButton("下一个")
        b_find.setDefault(True)
        b_rep = QPushButton("替换")
        b_all = QPushButton("全部替换")
        # v3.29：全局搜索改为常显按钮（与当前文件查找同页，不再二选一切换）
        b_global = QPushButton("全局搜索")
        b_global.setObjectName("scopeBtn")
        b_global.setToolTip("在当前文件夹的全部文档中搜索（结果见下方列表）")
        b_global.clicked.connect(self._run_global)

        # ---- 行 1：搜索框 + 帮助 + 当前文件导航 + 全局搜索 ----
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self.find_edit, 1)
        row1.addWidget(self.help_btn)
        row1.addWidget(b_prev)
        row1.addWidget(b_find)
        row1.addWidget(b_global)

        # ---- 行 2：替换（仅替换模式显示，作用于当前文件）----
        self.replace_row = QWidget(self)
        row2 = QHBoxLayout(self.replace_row)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)
        lbl2 = QLabel("替换")
        lbl2.setMinimumWidth(28)
        row2.addWidget(lbl2)
        row2.addWidget(self.replace_edit, 1)
        row2.addWidget(b_rep)
        row2.addWidget(b_all)

        # ---- 全局搜索结果区（复用 GlobalSearchPanel，隐藏其自带输入行）----
        self.search_panel = GlobalSearchPanel(win, self)
        self.search_panel.search_edit.setVisible(False)
        self.search_panel.search_btn.setVisible(False)
        # v3.48.18（FIND-UI）：「语义搜索」移出主行 —— 主行 6 个控件会把输入框
        # 压到 151px。改由下方「选项行」承载（见 opt_row）。
        if not getattr(win, "_sem_enabled", False):
            self.search_panel.search_sem.setChecked(False)
            self.search_panel.search_sem.setEnabled(False)
            self.search_panel.search_sem.setToolTip(
                "本地语义搜索未启用：系统设置 → 通用 → 本地语义搜索")

        # ---- 状态行：范围在左、统计在右（v3.29：与当前文件查找同页常显）----
        status_row = QHBoxLayout()
        status_row.setContentsMargins(2, 0, 2, 0)
        status_row.setSpacing(8)
        status_row.addWidget(self.search_panel.search_scope, 1)
        # v3.48.18（FIND-UI）：信息标签给足宽度并按内容需要换行，
        # 旧版 120px 下「输入关键词后回车开始搜索」被折成两行且下沿被裁。
        self.search_panel.search_info.setMinimumWidth(200)
        status_row.addWidget(self.search_panel.search_info, 0)

        # ---- v3.48.18（FIND-UI）选项行：扩展名筛选 + 仅文件名 + 语义搜索 ----
        opt_row = QHBoxLayout()
        opt_row.setContentsMargins(0, 0, 0, 0)
        opt_row.setSpacing(8)
        opt_row.addWidget(QLabel("范围"))
        opt_row.addWidget(self.search_panel.search_ext, 0)
        opt_row.addWidget(self.search_panel.search_nameonly, 0)
        opt_row.addWidget(self.search_panel.search_sem, 0)
        opt_row.addStretch(1)

        # 计数胶囊左对齐 + 右侧留白（不再整行铺色）
        count_row = QHBoxLayout()
        count_row.setContentsMargins(0, 0, 0, 0)
        count_row.setSpacing(0)
        count_row.addWidget(self.count_lbl, 0)
        count_row.addStretch(1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        lay.addLayout(row1)
        lay.addWidget(self.replace_row)
        lay.addLayout(opt_row)
        # v3.29b：「未找到匹配内容 / 共 N 处匹配」提示行 —— 搜索框之下、结果列表之上
        lay.addLayout(count_row)
        lay.addLayout(status_row)
        lay.addWidget(self.search_panel.search_tree, 1)

        # v3.31（#19）：当前文件命中列表点击跳转
        # （GlobalSearchPanel 自己的 itemClicked 处理器对未知标签直接忽略，互不冲突）
        self.search_panel.search_tree.itemClicked.connect(self._on_cfile_click)
        self.find_edit.returnPressed.connect(lambda: self._run("findNext"))
        b_find.clicked.connect(lambda: self._run("findNext"))
        b_prev.clicked.connect(lambda: self._run("findPrev"))
        b_rep.clicked.connect(lambda: self._run("replaceOne"))
        b_all.clicked.connect(lambda: self._run("replaceAll"))
        self.setTabOrder(self.find_edit, b_prev)
        self.setTabOrder(b_prev, b_find)
        self.setTabOrder(b_find, self.replace_edit)
        self._on_scope()

    # ---- 范围切换（v3.29：两半常显，仅保留焦点 / 状态语义） ----
    def _set_scope(self, idx):
        if self.scope_box.currentIndex() != idx:
            self.scope_box.setCurrentIndex(idx)
        else:
            self._on_scope()

    def _on_scope(self):
        glob = self.scope_box.currentData() == "global"
        # v3.29：当前文件查找与全局搜索同页常显 —— 不再互斥隐藏
        self.replace_row.setVisible(self._replace_mode)
        # v3.48.18（FIND-UI）：无文本不显示 —— 空胶囊会被 QSS 画成一条色带
        self.count_lbl.setVisible(bool(str(self.count_lbl.text()).strip()))
        self.search_panel.search_scope.setVisible(True)
        self.search_panel.search_info.setVisible(True)
        self.search_panel.search_ext.setVisible(True)
        self.search_panel.search_tree.setVisible(True)
        self.setWindowTitle("查找 / 替换" if self._replace_mode else "查找")
        if not glob:
            self.find_edit.setFocus()
        # v3.48.18（FIND-UI）：不再 adjustSize() —— 它会把窗口压到 sizeHint，
        # 首行被推到窗口上边缘之外（实测顶部文字被裁）。尺寸由 minimumSize 保证。
        if not self.isVisible():
            self.resize(max(self.width(), 760), max(self.height(), 540))

    # ---- 搜索词历史（↑ / ↓ 回溯）----
    def _remember(self, q):
        q = str(q or "").strip()
        if not q:
            return
        if q in self._history:
            self._history.remove(q)
        self._history.insert(0, q)
        self._history = self._history[:30]

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent as _QE
        if obj is self.find_edit and ev.type() == _QE.Type.KeyPress:
            if ev.key() == Qt.Key_Up and self._history:
                self._hist_pos = min(self._hist_pos + 1, len(self._history) - 1)
                self.find_edit.setText(self._history[self._hist_pos])
                return True
            if ev.key() == Qt.Key_Down and self._history:
                self._hist_pos = max(self._hist_pos - 1, -1)
                self.find_edit.setText("" if self._hist_pos < 0 else self._history[self._hist_pos])
                return True
        return super().eventFilter(obj, ev)

    def _show_regex_help(self):
        menu = QMenu(self)
        for label, pat in self.REGEX_PRESETS:
            act = menu.addAction(f"{label}　{pat}")
            act.setData(pat)
        act = menu.exec_(self.help_btn.mapToGlobal(self.help_btn.rect().bottomLeft()))
        if act is not None:
            self.find_edit.insert(str(act.data()))
            self.find_edit.setFocus()

    def show_replace(self, on):
        self._replace_mode = on
        if on and self.scope_box.currentData() == "global":
            # 替换仅作用于当前文件 → Ctrl+H 入口自动切到「当前文件」
            self.scope_box.setCurrentIndex(self.SCOPE_FILE)
        self._on_scope()

    def show_global(self):
        """切到「全局搜索」范围并聚焦输入框（Ctrl+Shift+F 入口）。"""
        self.scope_box.setCurrentIndex(self.SCOPE_GLOBAL)
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        if self.height() < 420:
            self.resize(max(self.width(), 560), 460)

    def focus_find(self):
        self.scope_box.setCurrentIndex(self.SCOPE_FILE)
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def _run(self, action):
        """当前文件查找 / 替换；Ctrl+Shift+F 入口（scope=global）时回车同时刷新全局结果。"""
        self._remember(self.find_edit.text())
        q = self.find_edit.text()
        if not q:
            self.count_lbl.setVisible(False)   # 清空搜索词 → 撤下结果提示行
        if self.scope_box.currentData() == "global":
            self.search_panel.run_with_query(q)
        # 默认正则、不区分大小写（正则无效时编辑器内自动回退普通文本）
        self._win._js_active(
            f"window.find({js(action)}, {js(q)}, false, true, {js(self.replace_edit.text())})",
            self._on_result)
        # v3.31（#18/#19）：当前文件全部命中 → 编辑器内高亮 + 结果列表（点击跳转）。
        # 全局搜索范围不注入（结果树由 GlobalSearchPanel 负责）；清空关键词撤高亮。
        if self.scope_box.currentData() == "global":
            return
        if not q:
            self._win._js_active("window.findClearHits()", None)
            self.search_panel.search_tree.clear()
        else:
            self._win._js_active(
                f"window.findAll({js(q)}, false, true, 500)", self._on_findall)

    def _run_global(self):
        """v3.29：常显「全局搜索」按钮 —— 只刷新全局结果，不动当前文件光标。"""
        self._remember(self.find_edit.text())
        self.search_panel.run_with_query(self.find_edit.text())

    def _on_findall(self, res):
        """v3.31（#18）：当前文件全部命中列表（复用结果树区域展示）。"""
        try:
            data = json.loads(res) if isinstance(res, str) else (res or {})
        except (TypeError, ValueError):
            data = {}
        tree = self.search_panel.search_tree
        tree.clear()
        ms = data.get("matches") or []
        n = int(data.get("count") or 0)
        if not ms:
            tree.addTopLevelItem(QTreeWidgetItem(["当前文件：无匹配"]))
            return
        cap = "（已达上限，仅显示前 500 处）" if n >= 500 else ""
        top = QTreeWidgetItem([f"当前文件 · {n} 处匹配{cap}　（点击跳转）"])
        f = top.font(0)
        f.setBold(True)
        top.setFont(0, f)
        tree.addTopLevelItem(top)
        for k, m in enumerate(ms):
            ch = QTreeWidgetItem([f"{k + 1}. {m.get('prev', '')}"])
            ch.setToolTip(0, m.get("prev", ""))
            ch.setData(0, Qt.UserRole, ("cfile", int(m.get("i", 0)), int(m.get("off", 0))))
            top.addChild(ch)
        tree.expandAll()
        self.search_panel.fit_tree_width()   # v3.48.18（FIND-UI）

    def _on_cfile_click(self, item, _col=0):
        data = item.data(0, Qt.UserRole)
        if not data or data[0] != "cfile":
            return
        self._win._js_active(f"window.gotoMatch({data[1]}, {data[2]})", None)

    def _clear_hits(self):
        try:
            if getattr(self, "_win", None) is not None:
                self._win._js_active("window.findClearHits()", None)
        except Exception:      # noqa: BLE001
            pass

    def closeEvent(self, ev):
        """v3.31（#18）：关闭 / 隐藏查找面板时撤下编辑器内全部命中高亮。"""
        self._clear_hits()
        self.search_panel.stop_sem_worker()
        super().closeEvent(ev)

    def hideEvent(self, ev):
        if not self.isVisible():
            self._clear_hits()
        super().hideEvent(ev)

    def _on_result(self, res):
        try:
            data = json.loads(res) if isinstance(res, str) else (res or {})
        except (TypeError, ValueError):
            data = {}
        n = data.get("count", 0)
        # v3.29b：结果提示独立成行（warn 态高亮「未找到」），位于搜索框与结果之间
        if n == 0:
            self.count_lbl.setText("未找到匹配内容")
            self.count_lbl.setProperty("warn", True)
            self._win._status.setText("未找到匹配内容")
        else:
            self.count_lbl.setText(f"共 {n} 处匹配")
            self.count_lbl.setProperty("warn", False)
            self._win._status.setText(f"共 {n} 处匹配")
        self.count_lbl.setVisible(bool(str(n).strip()) and n >= 0)
        st = self.count_lbl.style()
        st.unpolish(self.count_lbl)
        st.polish(self.count_lbl)


class ShortcutDialog(_ThemedDialog):
    """快捷键设置：按分组展示全部动作，选中后录制新快捷键，即时生效并持久化。"""

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("shortcutDlg")
        self.setWindowTitle("快捷键设置")
        self.setModal(False)
        self.resize(420, 520)
        self._apply_theme_qss(getattr(win, "_theme", "light"))

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["功能", "快捷键"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(False)
        self.tree.header().setStretchLastSection(False)
        self.tree.setColumnWidth(0, 220)

        self.key_edit = QKeySequenceEdit(self)
        self.key_edit.setClearButtonEnabled(True)

        hint = QLabel("选中功能后录制快捷键，松开即生效并保存；Esc / 单键将被忽略。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        b_reset = QPushButton("恢复全部默认")
        b_close = QPushButton("关闭")
        b_close.setDefault(True)

        btns = QHBoxLayout()
        btns.addWidget(b_reset)
        btns.addStretch(1)
        btns.addWidget(b_close)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(self.tree, 1)
        lay.addWidget(self.key_edit)
        lay.addWidget(hint)
        lay.addLayout(btns)

        self._loading = False
        self._load_items()
        self.tree.currentItemChanged.connect(self._on_select)
        self.key_edit.keySequenceChanged.connect(self._on_edit)
        b_reset.clicked.connect(self._reset_all)
        b_close.clicked.connect(self.accept)

    def _load_items(self):
        self._loading = True
        self.tree.clear()
        self._group_items = []
        for group, items in self._win.shortcut_groups():
            gitem = QTreeWidgetItem([group, ""])
            gitem.setFlags(Qt.ItemIsEnabled)  # 分组标题不可选
            f = gitem.font(0)
            f.setBold(True)
            gitem.setFont(0, f)
            gitem.setForeground(0, Qt.gray)
            self.tree.addTopLevelItem(gitem)
            self._group_items.append(gitem)
            for name in items:
                act = self._win._shortcut_acts.get(name)
                if act is None:
                    continue
                it = QTreeWidgetItem([name, act.shortcut().toString(QKeySequence.NativeText)])
                it.setData(0, Qt.UserRole, name)
                gitem.addChild(it)
        self.tree.expandAll()
        self._loading = False

    def _on_select(self, cur, _prev):
        if self._loading or cur is None:
            return
        name = cur.data(0, Qt.UserRole)
        if not name:
            return
        act = self._win._shortcut_acts.get(name)
        if act:
            self.key_edit.setKeySequence(act.shortcut())

    def _on_edit(self, seq):
        cur = self.tree.currentItem()
        if self._loading or cur is None or not cur.data(0, Qt.UserRole):
            return
        name = cur.data(0, Qt.UserRole)
        # v3.29d（B12/UX #25）：自定义快捷键冲突检测 —— 与其他动作绑同一组合键时
        # 提示并要求先处理，避免两个动作抢同一快捷键后行为不可预期
        if seq and not seq.isEmpty():
            clash = []
            for other, act2 in self._win._shortcut_acts.items():
                if other != name and act2 is not None and \
                        act2.shortcut().toString(QKeySequence.PortableText) == \
                        seq.toString(QKeySequence.PortableText):
                    clash.append(other)
            if clash:
                QMessageBox.warning(
                    self, "快捷键冲突",
                    f"「{seq.toString(QKeySequence.NativeText)}」已被以下动作使用：\n"
                    f"{ '、'.join(clash) }\n\n"
                    "请先修改或清空对方的快捷键，再来设置本动作。")
                act = self._win._shortcut_acts.get(name)
                self.key_edit.setKeySequence(act.shortcut() if act else QKeySequence())
                return
        self._win.apply_shortcut(name, seq)
        cur.setText(1, seq.toString(QKeySequence.NativeText))

    def _reset_all(self):
        self._loading = True
        for name, default in self._win.all_shortcuts():
            self._win.apply_shortcut(name, QKeySequence(default))
        self._load_items()
        self._loading = False
        if self.tree.currentItem():
            self._on_select(self.tree.currentItem(), None)

    def showEvent(self, ev):
        super().showEvent(ev)
        self._load_items()


class SettingsDialog(_ThemedDialog):
    """系统设置：Typedown 式左侧导航（通用 / 编辑器 / 写作与输入 / 模板），设置即时生效。

    v3.43.0（LOOK-1）：原「外观」页整体迁出到顶栏「外观(&A)」一级菜单 ——
    主题 / 界面风格 / 图表风格 / 代码风格四项在菜单里即时切换，设置中心不再
    重复提供同一功能（避免「同一配置两处入口、状态互相打架」）。
    编辑区字号缩放不属于外观四项的范畴，下放到「编辑器 → 编辑区显示」保留；
    v3.43.1（SET-4）：「界面风格管理…」菜单项移除（管理对话框无就地新增能力），
    命令面板（Ctrl+Shift+P）保留该命令兜底。

    v3.43.1（SET-3P）：三页拆四页压高度 —— 「通用」提到「编辑器」上方；
    从两页各抽一组组框组成新页「写作与输入」（编辑器←段落与标题 / 斜杠(/)菜单，
    通用←写作模式 / 输入辅助）。组框是移动不是复制（同一配置只留一处入口），
    控件仍挂 SettingsDialog 属性，showEvent 同步与回调逻辑不受影响。
    """

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("settingsDlg")
        self.setWindowTitle("系统设置")
        self.setModal(False)
        self.resize(660, 460)
        self._apply_theme_qss(getattr(win, "_theme", "light"))

        # ---- 左侧导航 ----
        self.nav = QListWidget(self)
        self.nav.setObjectName("navList")
        self.nav.setFixedWidth(150)
        # v3.29：「写作与历史」已并入「通用」页；「编辑器」页含图片 / 代码块 / 斜杠菜单
        # v3.36（TPL-E）：模板管理提升为一级页「模板」
        # v3.43.0（LOOK-1）：「外观」页迁出至顶栏「外观(&A)」菜单，此处不再保留
        # v3.43.1（SET-3P）：导航顺序 = 通用 / 编辑器 / 写作与输入 / 模板
        # v3.47.2（SoloMD 对标）：新增「AI 连接」页（默认连接参数配置入口）
        # v3.48.36（AI-MENUS）：新增「AI 菜单」页（两处「AI优化」菜单自定义）
        for name in ("通用", "编辑器", "写作与输入", "模板", "AI 菜单", "AI 连接"):
            QListWidgetItem(name, self.nav)
        self.nav.setCurrentRow(0)

        # ---- 右侧页面 ----
        self.pages = QStackedWidget(self)
        self.pages.addWidget(self._page_general())
        self.pages.addWidget(self._page_editor_fmt())
        self.pages.addWidget(self._page_writing())
        self.pages.addWidget(TemplatePage(win, self))
        self.pages.addWidget(self._page_ai_menus())
        self.pages.addWidget(self._page_ai_connection())
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)

        b_close = QPushButton("关闭")
        b_close.setDefault(True)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(b_close)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.nav)
        body = QVBoxLayout()
        body.setContentsMargins(24, 18, 24, 14)
        body.setSpacing(12)
        body.addWidget(self.pages, 1)
        body.addLayout(btns)
        wrap = QWidget(self)
        wrap.setLayout(body)
        lay.addWidget(wrap, 1)
        b_close.clicked.connect(self.accept)

    def select_page(self, name):
        """按页名定位左侧导航（v3.36：供「设置 → 模板」直达入口使用）。"""
        for i in range(self.nav.count()):
            if self.nav.item(i).text() == name:
                self.nav.setCurrentRow(i)
                return True
        return False

    # ================= 外观 =================
    # v3.43.0（LOOK-1）：原「外观」页已整体迁出到顶栏「外观(&A)」一级菜单
    # （界面风格 / 主题 / 图表风格 / 代码风格 四项），设置中心不再重复提供。
    # 编辑区字号缩放不属外观四项，下放到「编辑器 → 编辑区显示」继续保留。

    def _on_zoom(self, v):
        self.zoom_lbl.setText(f"{v}%")
        self._win.set_zoom(v / 100.0)

    # ================= 编辑器 =================
    def _sec(self, text):
        """v3.26：设置页分组标题（加粗小节头）。"""
        lbl = QLabel(text)
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _group(self, title):
        """v3.29b：设置页组框（分组容器）——同类设置项归拢到一个 QGroupBox。"""
        gb = QGroupBox(title, self)
        v = QVBoxLayout(gb)
        v.setContentsMargins(12, 6, 12, 8)
        v.setSpacing(6)
        return gb, v

    def _page_editor_fmt(self):
        """v3.29：「编辑器」页 —— 图片 / 代码块。
        v3.29b：各组设置归入组框（QGroupBox）。
        v3.43.1（SET-3P）：「段落与标题」「斜杠(/)菜单」移入「写作与输入」页，
        本页只留呈现类配置（编辑区显示 / 图片存储 / 代码块外观 / 格式化日志）。"""
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("编辑器")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        # ---- v3.43.0（LOOK-1）：编辑区显示（原「外观」页的编辑区字号缩放迁入） ----
        #      字号只影响编辑区内容呈现，不属于外观四项的皮肤范畴，故落在编辑器页。
        gb_view, gview = self._group("编辑区显示")
        zrow = QHBoxLayout()
        zrow.addWidget(QLabel("编辑区字号缩放"))
        self.zoom_slider = QSlider(Qt.Horizontal, page)
        self.zoom_slider.setRange(80, 160)
        self.zoom_slider.setValue(int(round(getattr(self._win, "_zoom", 1.0) * 100)))
        self.zoom_lbl = QLabel(f"{self.zoom_slider.value()}%")
        self.zoom_lbl.setMinimumWidth(44)
        self.zoom_slider.valueChanged.connect(self._on_zoom)
        zrow.addWidget(self.zoom_slider, 1)
        zrow.addWidget(self.zoom_lbl)
        gview.addLayout(zrow)
        zoom_hint = QLabel("· 只缩放编辑区显示字号，不影响导出的 Markdown 与 HTML\n"
                           "· Ctrl+= / Ctrl+- 可快速缩放，点击状态栏百分比格重置 100%")
        zoom_hint.setObjectName("pageHint")
        zoom_hint.setWordWrap(True)
        gview.addWidget(zoom_hint)
        lay.addWidget(gb_view)

        # ---- v3.43.1（SET-3P）：「段落与标题」移入「写作与输入」页 ----

        # ---- 图片存储（组框；v3.29c：描述信息直接作为组框标题） ----
        gb_img, gimg = self._group("图片存储")
        gimg.addWidget(QLabel("图片存放方式"))
        self.image_mode_box = QComboBox(page)
        self.image_mode_box.addItem("相对路径：保存到「文档名.assets」文件夹（推荐）", "assets")
        self.image_mode_box.addItem("内嵌 data URL：图片写进文档本身", "embed")
        _im = "embed" if getattr(self._win, "_image_mode", "assets") == "embed" else "assets"
        _iidx = self.image_mode_box.findData(_im)
        self.image_mode_box.setCurrentIndex(_iidx if _iidx >= 0 else 0)
        self.image_mode_box.currentIndexChanged.connect(self._on_image_mode)
        gimg.addWidget(self.image_mode_box)

        img_hint = QLabel(
            "· 相对路径：图片另存为独立文件，Markdown 只记录路径，文档小、可被其它工具复用\n"
            "· 内嵌 data URL：图片写入 Markdown 本身，单文件自包含但文档会明显变大\n"
            "· 尚未保存的文档只能内嵌；「文件 → 迁移内嵌图片为文件…」可给老文档瘦身")
        img_hint.setObjectName("pageHint")
        img_hint.setWordWrap(True)
        gimg.addWidget(img_hint)
        lay.addWidget(gb_img)

        # ---- 代码块外观（组框） ----
        gb_code, gcode = self._group("代码块外观")
        gcode.addWidget(QLabel("默认语言（插入代码块时预选，可输入自定义值）"))
        self.lang_box = QComboBox(page)
        self.lang_box.setEditable(True)
        _LANGS = ["C", "C++", "C#", "Java", "Python", "JavaScript", "TypeScript", "Go",
                  "Rust", "SQL", "Bash", "PowerShell", "HTML", "CSS", "JSON", "YAML",
                  "Markdown", "MATLAB", "R", "Swift", "Kotlin", "PHP", "Ruby", "Plain Text"]
        self.lang_box.addItems(_LANGS)
        cur_lang = str(getattr(self._win, "_code_lang", "C") or "C")
        if cur_lang in _LANGS:
            self.lang_box.setCurrentText(cur_lang)
        else:
            self.lang_box.setEditText(cur_lang)
        self.lang_box.currentTextChanged.connect(self._on_code_lang)
        gcode.addWidget(self.lang_box)

        # ---- v3.25 代码块行号 ----
        # v3.43.0（LOOK-1）：「代码风格」下拉已迁至「外观(&A) → 代码风格」，
        # 此处不再重复提供（同一配置只保留一处入口，避免两处状态打架）。
        crow = QHBoxLayout()
        self.code_lnum_box = QCheckBox("代码块显示行号", page)
        self.code_lnum_box.setChecked(bool(getattr(self._win, "_code_lnum", True)))
        self.code_lnum_box.toggled.connect(self._on_code_lnum)
        crow.addWidget(self.code_lnum_box)
        crow.addStretch(1)
        gcode.addLayout(crow)
        code_hint = QLabel("· 新插入 / 重新渲染的代码块使用以上默认配置\n"
                           "· 代码块顶部语言栏的「风格」按钮可对单个代码块临时切换\n"
                           "· 全局默认代码风格在「外观 → 代码风格」切换（经典 / 深色 / 护眼 / 极简）")
        code_hint.setObjectName("pageHint")
        code_hint.setWordWrap(True)
        gcode.addWidget(code_hint)
        lay.addWidget(gb_code)

        # ---- v3.39.8（FMT-LOG）：格式化操作日志（组框） ----
        gb_flog, gflog = self._group("格式化操作日志")
        self.fmt_log_box = QCheckBox(
            "记录格式化操作日志（时间 / 动作 / 源码片段，用于问题复现与排查）", page)
        self.fmt_log_box.setChecked(bool(getattr(self._win, "_fmt_log", False)))
        self.fmt_log_box.toggled.connect(self._win.set_fmt_log)
        gflog.addWidget(self.fmt_log_box)
        flog_hint = QLabel("· 日志写入 %APPDATA%\\mdEditor\\fmtlog\\，帮助菜单 →「格式化操作日志」可查看 / 导出\n"
                           "· 关闭后立即停止记录（即时生效，已写入的文件保留）")
        flog_hint.setObjectName("pageHint")
        flog_hint.setWordWrap(True)
        gflog.addWidget(flog_hint)
        lay.addWidget(gb_flog)

        # ---- v3.43.1（SET-3P）：「斜杠（/）菜单」移入「写作与输入」页 ----

        lay.addStretch(1)
        return page

    # ---- 斜杠菜单设置 ----
    def _fill_menu_list(self, order):
        by_id = dict(MENU_ITEMS)
        ids = [x for x in (order or []) if x in by_id]
        # 新版本新增的一级项：按 MENU_ITEMS（= 编辑器默认顺序）的相对位置插入，
        # 而不是一律追加到末尾，保证列表里展示的顺序与实际生效顺序一致。
        for i, (mid, _name) in enumerate(MENU_ITEMS):
            if mid in ids:
                continue
            prev = next((m for m, _n in reversed(MENU_ITEMS[:i]) if m in ids), None)
            nxt = next((m for m, _n in MENU_ITEMS[i + 1:] if m in ids), None)
            if prev is not None:
                ids.insert(ids.index(prev) + 1, mid)
            elif nxt is not None:
                ids.insert(ids.index(nxt), mid)
            else:
                ids.append(mid)
        self.menu_list.clear()
        for mid in ids:
            it = QListWidgetItem(by_id[mid], self.menu_list)
            it.setData(Qt.UserRole, mid)

    def _fill_def_box(self, def_id=None):
        def_id = def_id or str(getattr(self._win, "_slash_def", "heading") or "heading")
        self.menu_def_box.blockSignals(True)
        self.menu_def_box.clear()
        for k in range(self.menu_list.count()):
            it = self.menu_list.item(k)
            self.menu_def_box.addItem(it.text(), it.data(Qt.UserRole))
        idx = self.menu_def_box.findData(def_id)
        self.menu_def_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.menu_def_box.blockSignals(False)

    def _menu_move(self, delta):
        row = self.menu_list.currentRow()
        if row < 0:
            row = 0
            self.menu_list.setCurrentRow(0)
        it = self.menu_list.takeItem(row)
        if not it:
            return
        self.menu_list.insertItem(max(0, min(self.menu_list.count(), row + delta)), it)
        self.menu_list.setCurrentItem(it)
        self._fill_def_box()
        self._push_menu_cfg()

    # ---- v3.36（TPL-E）：模板管理入口已移至「模板」一级页（TemplatePage） ----

    def _push_menu_cfg(self):
        order = [self.menu_list.item(k).data(Qt.UserRole) for k in range(self.menu_list.count())]
        self._win.set_slash_menu_config(order, self.menu_def_box.currentData(), {
            "heading": self.sub_heading_box.currentIndex(),
            "list": self.sub_list_box.currentIndex(),
            "chart": self.sub_chart_box.currentIndex(),
            "math": self.sub_math_box.currentIndex(),
        })

    def _on_code_lang(self, text):
        if str(getattr(self._win, "_code_lang", "C")) != text:
            self._win.set_code_lang(text)

    def _on_para_indent(self, _idx):
        """v3.31.2（#8）：段首缩进格数。"""
        n = self.para_indent_box.currentData()
        if n is not None and int(n) != int(getattr(self._win, "_para_indent", 0)):
            self._win.set_para_indent(int(n))

    def _on_code_lnum(self, on):
        """v3.25：代码块行号开关。"""
        if bool(on) != bool(getattr(self._win, "_code_lnum", True)):
            self._win.set_code_prefs(lnum=bool(on))

    def _on_code_style(self, _idx):
        """v3.25：默认代码风格。"""
        sid = self.code_style_box.currentData()
        if sid and sid != str(getattr(self._win, "_code_style", "classic")):
            self._win.set_code_prefs(style=sid)

    def _on_image_mode(self, _idx):
        mode = self.image_mode_box.currentData()
        if mode and mode != getattr(self._win, "_image_mode", "assets"):
            self._win.set_image_mode(mode)

    def _on_typewriter(self, on):
        if bool(getattr(self._win, "_typewriter", False)) != on:
            self._win.toggle_typewriter()

    def _on_focus(self, on):
        if bool(getattr(self._win, "_focus", False)) != on:
            self._win.toggle_focus()

    def _on_autopair(self, on):
        if bool(getattr(self._win, "_auto_pair", True)) != on:
            self._win.set_auto_pair(on)

    def _on_emoji(self, on):
        if bool(getattr(self._win, "_emoji", True)) != on:
            self._win.set_emoji_complete(on)

    def _on_history_keep(self, n):
        if int(getattr(self._win, "_history_keep", 5) or 5) != int(n):
            self._win.set_history_keep(int(n))

    # ---- 通用页：侧栏显示设置 ----
    def _on_outline_level(self, _idx):
        lvl = self.outline_level_box.currentData()
        if lvl is not None and int(lvl) != int(getattr(self._win, "_outline_level", 3)):
            self._win.set_outline_level(int(lvl))

    def _on_startup_action(self, _i):
        self._win.set_startup_action(self.startup_box.currentData())
        self._sync_startup_dir_visible()

    def _on_startup_dir(self):
        # v3.44：folder 档与全局默认位置共用 files/defaultDir（去重 startupFolder）
        self._win.set_file_list_default_dir(self.startup_dir_edit.text().strip())
        self._sync_startup_dir_visible()

    def _browse_startup_dir(self):
        cur = self.startup_dir_edit.text().strip()
        d = QFileDialog.getExistingDirectory(
            self, "选择启动时打开的文件夹", cur or os.path.expanduser("~"))
        if d:
            self.startup_dir_edit.setText(d)
            self._on_startup_dir()

    def _sync_startup_dir_visible(self):
        # 仅「打开指定文件夹」档显示目录输入
        show = self.startup_box.currentData() == "folder"
        self.startup_dir_row.setVisible(show)

    def _on_save_mode(self, _i):
        self._win.set_autosave_interval(int(self.save_mode_box.currentData() or 0))

    def _sync_save_mode_enabled(self):
        # 关闭自动保存时禁用「保存时机」
        self.save_mode_box.setEnabled(self.autosave_box.isChecked())

    def _on_file_mode(self, _idx):
        mode = self.file_mode_box.currentData()
        if mode and mode != getattr(self._win, "_file_list_mode", "current"):
            self._win.set_file_list_mode(mode)

    def _on_recent_max(self, n):
        self._win.set_recent_max(int(n))

    def _on_pandoc_path(self):
        self._win.set_pandoc_path(self.pandoc_edit.text())

    # ---- v3.48.12（SEM-4）：本地语义搜索 ----
    def _sync_sem_info(self):
        """同步索引状态文案（建页 / showEvent 刷新）。"""
        try:
            st = self._win.sem_index_stats()
        except Exception:
            st = {}
        if not st or not st.get("db"):
            self.sem_info.setText("索引尚未建立（首次语义搜索时自动创建）")
            return
        size_mb = st.get("size", 0) / 1048576.0
        txt = (f"索引：{st.get('files', 0)} 个文件 · {st.get('chunks', 0)} 个段落块"
               f" · {size_mb:.1f} MB")
        if st.get("updated"):
            txt += f" · 更新于 {st['updated']}"
        self.sem_info.setText(txt + f"\n位置：{st.get('db', '')}")

    def _on_sem_rebuild(self):
        self._win.sem_rebuild_index()
        self._sync_sem_info()

    def _on_external_editor(self):
        self._win.set_external_editor(self.extedit_edit.text())

    # ================= 通用 =================
    def _page_general(self):
        """v3.43.1（SET-3P）：「通用」页提到导航首位；「写作模式」「输入辅助」
        移入「写作与输入」页。v3.44（FILE-UX）：原「文件与启动」大组框拆为
        「保存 / 启动 / 文件列表」三个语义组框，本页现含 保存 / 启动 / 文件列表 /
        大纲 / 导出 / 版本历史。v3.44.1：移除通用页冗余说明/提示文案（sd_hint /
        fm_hint / 底部 note 全删，ol_hint 压一行，导出/版本历史标签去括号说明），
        进一步压低总高度；控件与交互逻辑不变。"""
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        title = QLabel("通用")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        # ================= 保存（组框；v3.44 从「文件与启动」拆出） =================
        gb_save, gsave = self._group("保存")
        self.autosave_box = QCheckBox("自动保存（编辑后自动写入文件）", page)
        self.autosave_box.setChecked(bool(getattr(self._win, "_autosave", True)))
        self.autosave_box.toggled.connect(self._win.set_autosave)
        self.autosave_box.toggled.connect(self._sync_save_mode_enabled)
        gsave.addWidget(self.autosave_box)

        # ---- v3.44（AUTOSAVE-INT）：保存时机（实时 / 30 秒 / 5 分钟） ----
        srow = QHBoxLayout()
        srow.addWidget(QLabel("保存时机"))
        self.save_mode_box = QComboBox(page)
        self.save_mode_box.addItem("实时（每次改动即写盘）", 0)
        self.save_mode_box.addItem("每 30 秒", 30)
        self.save_mode_box.addItem("每 5 分钟", 300)
        _si_int = int(getattr(self._win, "_autosave_interval", 0) or 0)
        _si_idx = self.save_mode_box.findData(_si_int)
        self.save_mode_box.setCurrentIndex(_si_idx if _si_idx >= 0 else 0)
        self.save_mode_box.currentIndexChanged.connect(self._on_save_mode)
        srow.addWidget(self.save_mode_box, 1)
        gsave.addLayout(srow)
        self._sync_save_mode_enabled()
        lay.addWidget(gb_save)

        # ================= 启动（组框；v3.44 从「文件与启动」拆出） =================
        gb_start, gstart = self._group("启动")
        arow = QHBoxLayout()
        arow.addWidget(QLabel("启动时"))
        self.startup_box = QComboBox(page)
        self.startup_box.addItem("打开欢迎页", "blank")
        self.startup_box.addItem("恢复上次打开的文件", "lastFile")
        self.startup_box.addItem("恢复上次会话（多标签 + 位置，默认）", "session")
        self.startup_box.addItem("打开指定文件夹", "folder")
        _sa = str(getattr(self._win, "_startup_action", "session") or "session")
        if _sa == "lastFileSide":
            # v3.44：旧「恢复上次文件与侧栏位置」升级为完整会话恢复（兼容旧值）
            _sa = "session"
        _si = self.startup_box.findData(_sa)
        self.startup_box.setCurrentIndex(_si if _si >= 0 else 0)
        self.startup_box.currentIndexChanged.connect(self._on_startup_action)
        arow.addWidget(self.startup_box, 1)
        gstart.addLayout(arow)

        # 「打开指定文件夹」档：定位到「默认打开位置」（与文件列表组共用 files/defaultDir，去重）
        self.startup_dir_row = QWidget(page)
        drow = QHBoxLayout(self.startup_dir_row)
        drow.setContentsMargins(0, 0, 0, 0)
        drow.addWidget(QLabel("启动时打开的文件夹"))
        self.startup_dir_edit = QLineEdit(page)
        self.startup_dir_edit.setPlaceholderText("留空 = 不定位")
        self.startup_dir_edit.setText(str(getattr(self._win, "_file_list_default_dir", "") or ""))
        self.startup_dir_edit.editingFinished.connect(self._on_startup_dir)
        drow.addWidget(self.startup_dir_edit, 1)
        b_dir = QPushButton("浏览…")
        b_dir.clicked.connect(self._browse_startup_dir)
        drow.addWidget(b_dir)
        gstart.addWidget(self.startup_dir_row)

        self._sync_startup_dir_visible()
        lay.addWidget(gb_start)

        # ================= 文件列表（组框；v3.44 从「文件与启动」拆出） =================
        gb_fl, gfl = self._group("文件列表")
        # ---- 未打开文件时的显示模式 ----
        lrow = QHBoxLayout()
        lrow.addWidget(QLabel("未打开文件时显示"))
        self.file_mode_box = QComboBox(page)
        self.file_mode_box.addItem("上次编辑的文档（预览）", "current")
        self.file_mode_box.addItem("始终空白", "blank")
        _fm = "blank" if getattr(self._win, "_file_list_mode", "current") == "blank" else "current"
        idx = self.file_mode_box.findData(_fm)
        self.file_mode_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.file_mode_box.currentIndexChanged.connect(self._on_file_mode)
        lrow.addWidget(self.file_mode_box, 1)
        gfl.addLayout(lrow)

        # ---- v3.44（RECENT-MAX）：最近文件保留条数 ----
        rrow = QHBoxLayout()
        rrow.addWidget(QLabel("最近文件保留"))
        self.recent_max_box = QSpinBox(page)
        self.recent_max_box.setRange(0, 50)
        self.recent_max_box.setSuffix(" 条")
        self.recent_max_box.setValue(int(getattr(self._win, "_recent_max", 10) or 10))
        self.recent_max_box.valueChanged.connect(self._on_recent_max)
        rrow.addWidget(self.recent_max_box, 1)
        gfl.addLayout(rrow)
        rm_hint = QLabel("· 0 = 不保留最近文件（菜单项隐藏）")
        rm_hint.setObjectName("pageHint")
        rm_hint.setWordWrap(True)
        gfl.addWidget(rm_hint)
        lay.addWidget(gb_fl)

        # ================= 本地语义搜索（v3.48.12 SEM-4） =================
        gb_sem, gsem = self._group("本地语义搜索")
        self.sem_box = QCheckBox("启用本地语义搜索（查找 → 全局搜索 → 语义搜索）", page)
        self.sem_box.setChecked(bool(getattr(self._win, "_sem_enabled", False)))
        self.sem_box.toggled.connect(self._win.set_semantic_search)
        gsem.addWidget(self.sem_box)
        self.sem_info = QLabel(page)
        self.sem_info.setObjectName("pageHint")
        self.sem_info.setWordWrap(True)
        gsem.addWidget(self.sem_info)
        self._sync_sem_info()
        srow_sem = QHBoxLayout()
        self.sem_rebuild_btn = QPushButton("重建索引", page)
        self.sem_rebuild_btn.setToolTip("清空当前索引；下次语义搜索时按目录内容自动重建")
        self.sem_rebuild_btn.clicked.connect(self._on_sem_rebuild)
        srow_sem.addWidget(self.sem_rebuild_btn)
        srow_sem.addStretch(1)
        gsem.addLayout(srow_sem)
        sem_hint = QLabel("· 纯本地计算（TF-IDF 向量 + 同义词扩展），文档内容不外传\n"
                          "· 索引位于 %APPDATA%\\mdEditor\\semindex，不在项目目录、不入 Git\n"
                          "· 索引随文档改动自动增量更新；关闭后全局搜索按普通全文检索")
        sem_hint.setObjectName("pageHint")
        sem_hint.setWordWrap(True)
        gsem.addWidget(sem_hint)
        lay.addWidget(gb_sem)

        # ---- v3.43.0（LOOK-1）：大纲（原散落在「文件与启动」组里，按语义独立成组） ----
        gb_ol, gol = self._group("大纲")
        orow = QHBoxLayout()
        orow.addWidget(QLabel("显示级别（超过该级别的标题默认折叠）"))
        self.outline_level_box = QComboBox(page)
        for n in range(1, 7):
            self.outline_level_box.addItem(f"{n} 级", n)
        self.outline_level_box.setCurrentIndex(
            max(0, int(getattr(self._win, "_outline_level", 3)) - 1))
        self.outline_level_box.currentIndexChanged.connect(self._on_outline_level)
        orow.addWidget(self.outline_level_box, 1)
        gol.addLayout(orow)

        self.outline_words_box = QCheckBox("显示分节字数（标题后追加「· N 字」）", page)
        self.outline_words_box.setChecked(bool(getattr(self._win, "_outline_words", False)))
        self.outline_words_box.toggled.connect(self._win.set_outline_words)
        gol.addWidget(self.outline_words_box)

        ol_hint = QLabel("支持拖拽整段调序；右键可跳转 / 复制标题 / 展开折叠 / 移到首尾")
        ol_hint.setObjectName("pageHint")
        ol_hint.setWordWrap(True)
        gol.addWidget(ol_hint)
        lay.addWidget(gb_ol)

        # ---- 导出（组框） ----
        gb_exp, gexp = self._group("导出")
        gexp.addWidget(QLabel("Pandoc 路径"))
        self.pandoc_edit = QLineEdit(page)
        self.pandoc_edit.setPlaceholderText("留空 = 自动探测；未安装 pandoc 时使用内置转换")
        self.pandoc_edit.setText(str(getattr(self._win, "_pandoc_path", "") or ""))
        self.pandoc_edit.editingFinished.connect(self._on_pandoc_path)
        gexp.addWidget(self.pandoc_edit)

        # ---- P1-7 外部编辑器路径（可选）----
        gexp.addWidget(QLabel("外部编辑器"))
        self.extedit_edit = QLineEdit(page)
        self.extedit_edit.setPlaceholderText("留空 = 系统默认关联程序（可填 Notepad++ / VS Code 等可执行文件）")
        self.extedit_edit.setText(str(getattr(self._win, "_external_editor", "") or ""))
        self.extedit_edit.editingFinished.connect(self._on_external_editor)
        gexp.addWidget(self.extedit_edit)
        lay.addWidget(gb_exp)

        # ---- v3.43.1（SET-3P）：「写作模式」「输入辅助」移入「写作与输入」页 ----

        # ---- v3.29：版本历史（P1-6 历史版本保留份数；组框化）----
        gb_hist, ghist = self._group("版本历史")
        histrow = QHBoxLayout()
        histrow.addWidget(QLabel("历史版本保留份数"))
        self.history_keep_box = QSpinBox(page)
        # v3.43.1：默认 5 份、上限 100 份（原 20 / 200）
        self.history_keep_box.setRange(1, 100)
        self.history_keep_box.setSuffix(" 份")
        self.history_keep_box.setValue(int(getattr(self._win, "_history_keep", 5) or 5))
        self.history_keep_box.valueChanged.connect(self._on_history_keep)
        histrow.addWidget(self.history_keep_box, 1)
        ghist.addLayout(histrow)
        lay.addWidget(gb_hist)

        lay.addStretch(1)
        return page

    # ================= 写作与输入 =================
    def _page_writing(self):
        """v3.43.1（SET-3P）：新页「写作与输入」—— 从「编辑器」页移入
        段落与标题 / 斜杠(/)菜单，从「通用」页移入 写作模式 / 输入辅助，
        把打字体验相关配置集中到一页（组框是移动不是复制，回调与同步逻辑不变）。
        注意：本页须在 _page_general / _page_editor_fmt 之后构建（__init__ 已保证顺序），
        控件属性挂 SettingsDialog（self），showEvent 同步逻辑跨页依然可用。"""
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("写作与输入")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        # ---- 段落与标题（v3.43.1 自「编辑器」页移入；v3.31.2 组框化） ----
        gb_para, gpara = self._group("段落与标题")
        prow = QHBoxLayout()
        prow.addWidget(QLabel("段首缩进（每段首行空出的格数）"))
        self.para_indent_box = QComboBox(page)
        for _pn in range(0, 5):
            self.para_indent_box.addItem(f"{_pn} 格" if _pn else "无（0 格）", _pn)
        _pi = int(getattr(self._win, "_para_indent", 0) or 0)
        _piidx = self.para_indent_box.findData(_pi)
        self.para_indent_box.setCurrentIndex(_piidx if _piidx >= 0 else 0)
        self.para_indent_box.currentIndexChanged.connect(self._on_para_indent)
        prow.addWidget(self.para_indent_box, 1)
        gpara.addLayout(prow)

        self.h1_center_box = QCheckBox("标题 1 始终居中显示（导出跟随；单个标题可用格式栏按钮单独切换）", page)
        self.h1_center_box.setChecked(bool(getattr(self._win, "_h1_center", False)))
        self.h1_center_box.toggled.connect(self._win.set_h1_center)
        gpara.addWidget(self.h1_center_box)

        para_hint = QLabel("· 段首缩进仅作用于段落首行（列表 / 引用 / 表格不受影响），导出 HTML 同步生效\n"
                           "· 标题 1 居中为全局默认；格式栏「⇔」按钮可对单个标题 1 覆盖（优先级更高）")
        para_hint.setObjectName("pageHint")
        para_hint.setWordWrap(True)
        gpara.addWidget(para_hint)
        lay.addWidget(gb_para)

        # ---- 写作模式（v3.43.1 自「通用」页移入；v3.29 并入，组框化） ----
        gb_write, gwrite = self._group("写作模式")
        self.typewriter_box = QCheckBox("打字机模式（光标所在行始终居中）", page)
        self.typewriter_box.setChecked(bool(getattr(self._win, "_typewriter", False)))
        self.typewriter_box.toggled.connect(self._on_typewriter)
        gwrite.addWidget(self.typewriter_box)

        self.focus_box = QCheckBox("专注模式（淡化非当前段落）", page)
        self.focus_box.setChecked(bool(getattr(self._win, "_focus", False)))
        self.focus_box.toggled.connect(self._on_focus)
        gwrite.addWidget(self.focus_box)
        lay.addWidget(gb_write)

        # ---- 输入辅助（v3.43.1 自「通用」页移入；P1-1 / P1-8 输入增强，组框化） ----
        gb_input, ginput = self._group("输入辅助")
        self.autopair_box = QCheckBox("自动配对括号 / 引号（选中文字可直接用符号包裹）", page)
        self.autopair_box.setChecked(bool(getattr(self._win, "_auto_pair", True)))
        self.autopair_box.toggled.connect(self._on_autopair)
        ginput.addWidget(self.autopair_box)

        self.emoji_box = QCheckBox("Emoji 自动补全（正文输入「:」+ 名称弹出候选）", page)
        self.emoji_box.setChecked(bool(getattr(self._win, "_emoji", True)))
        self.emoji_box.toggled.connect(self._on_emoji)
        ginput.addWidget(self.emoji_box)
        lay.addWidget(gb_input)

        # ---- 斜杠（/）菜单（v3.43.1 自「编辑器」页移入；组框） ----
        gb_menu, gmenu = self._group("斜杠（/）菜单")
        gmenu.addWidget(QLabel("用上移 / 下移调整一级菜单优先级顺序"))
        mrow = QHBoxLayout()
        self.menu_list = QListWidget(page)
        self.menu_list.setObjectName("themeList")
        self.menu_list.setFixedHeight(148)
        self._fill_menu_list(getattr(self._win, "_slash_order", None))
        mbtns = QVBoxLayout()
        b_up = QPushButton("上移")
        b_down = QPushButton("下移")
        mbtns.addWidget(b_up)
        mbtns.addWidget(b_down)
        mbtns.addStretch(1)
        mrow.addWidget(self.menu_list, 1)
        mrow.addLayout(mbtns)
        gmenu.addLayout(mrow)

        frow = QHBoxLayout()
        frow.addWidget(QLabel("一级菜单默认选项"))
        self.menu_def_box = QComboBox(page)
        self._fill_def_box()
        frow.addWidget(self.menu_def_box, 1)
        gmenu.addLayout(frow)

        srow1 = QHBoxLayout()
        srow1.addWidget(QLabel("标题默认"))
        self.sub_heading_box = QComboBox(page)
        self.sub_heading_box.addItems(SUB_HEADING)
        srow1.addWidget(self.sub_heading_box, 1)
        srow1.addWidget(QLabel("列表默认"))
        self.sub_list_box = QComboBox(page)
        self.sub_list_box.addItems(SUB_LIST)
        srow1.addWidget(self.sub_list_box, 1)
        gmenu.addLayout(srow1)

        srow2 = QHBoxLayout()
        srow2.addWidget(QLabel("图表默认"))
        self.sub_chart_box = QComboBox(page)
        self.sub_chart_box.addItems(SUB_CHART)
        srow2.addWidget(self.sub_chart_box, 1)
        srow2.addWidget(QLabel("公式默认"))
        self.sub_math_box = QComboBox(page)
        self.sub_math_box.addItems(SUB_MATH)
        srow2.addWidget(self.sub_math_box, 1)
        gmenu.addLayout(srow2)

        subs = getattr(self._win, "_slash_sub", {}) or {}
        for box, key in ((self.sub_heading_box, "heading"), (self.sub_list_box, "list"),
                         (self.sub_chart_box, "chart"), (self.sub_math_box, "math")):
            box.blockSignals(True)
            box.setCurrentIndex(max(0, int(subs.get(key, 0))))
            box.blockSignals(False)

        b_up.clicked.connect(lambda: self._menu_move(-1))
        b_down.clicked.connect(lambda: self._menu_move(1))
        self.menu_def_box.currentIndexChanged.connect(lambda _: self._push_menu_cfg())
        self.sub_heading_box.currentIndexChanged.connect(lambda _: self._push_menu_cfg())
        self.sub_list_box.currentIndexChanged.connect(lambda _: self._push_menu_cfg())
        self.sub_chart_box.currentIndexChanged.connect(lambda _: self._push_menu_cfg())
        self.sub_math_box.currentIndexChanged.connect(lambda _: self._push_menu_cfg())

        # v3.36（TPL-E）：原「自定义模板（⭐，插入文档即用）→ 管理…」入口已提升为
        # 独立的「模板」一级页；斜杠菜单组内不再重复入口

        lay.addWidget(gb_menu)

        lay.addStretch(1)
        return page

    # v3.47.2（SoloMD 对标）：「AI 连接」页 —— 默认连接参数配置入口

    # ================= v3.48.36（AI-MENUS）：AI 菜单 =================
    def _page_ai_menus(self):
        """「AI 菜单」页：框选文字右键 / 整篇文章右键两处「AI优化」的菜单项
        名称与提示词自定义。改动即时落盘（右键菜单每次构建时实时读取）。"""
        from ai_pane import ai_menu_items
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("AI 菜单")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        info = QLabel("自定义两处「AI优化」菜单的菜单项名称与提示词。"
                      "提示词留空表示使用内置提示词（翻译会按内容语种自动定向）。设置即时生效。")
        info.setWordWrap(True)
        info.setObjectName("pageTitle")
        info.setStyleSheet("font-size:11.5px; font-weight:400;")
        lay.addWidget(info)

        self._ai_menu_data = {}
        self._ai_menu_lists = {}
        for scope, cap in (("ctx", "框选文字后 · 右键「AI优化」"),
                           ("doc", "选中文章后 · 文件列表 / 标签右键「AI优化」")):
            gb, v = self._group(cap)
            lst = QListWidget(self)
            lst.setObjectName("aiMenuList")
            lst.setMinimumHeight(96)
            lst.itemDoubleClicked.connect(lambda _it, s=scope: self._ai_menu_edit(s))
            v.addWidget(lst)
            row = QHBoxLayout()
            for text, cb in (("添加…", lambda _c=False, sc=scope: self._ai_menu_add(sc)),
                             ("编辑…", lambda _c=False, sc=scope: self._ai_menu_edit(sc)),
                             ("删除", lambda _c=False, sc=scope: self._ai_menu_del(sc)),
                             ("上移", lambda _c=False, sc=scope: self._ai_menu_move(sc, -1)),
                             ("下移", lambda _c=False, sc=scope: self._ai_menu_move(sc, 1)),
                             ("恢复默认", lambda _c=False, sc=scope: self._ai_menu_reset(sc))):
                btn = QPushButton(text)
                btn.clicked.connect(cb)
                row.addWidget(btn)
            row.addStretch(1)
            v.addLayout(row)
            lay.addWidget(gb)
            self._ai_menu_lists[scope] = lst
            self._ai_menu_data[scope] = ai_menu_items(self._win._settings, scope)
            self._ai_menu_repaint(scope)

        lay.addStretch(1)
        scr = QScrollArea(self)
        scr.setWidget(page)
        scr.setWidgetResizable(True)
        scr.setFrameShape(QFrame.NoFrame)
        return scr

    def _ai_menu_repaint(self, scope):
        lst = self._ai_menu_lists[scope]
        cur = lst.currentRow()
        lst.clear()
        for it in self._ai_menu_data[scope]:
            tag = "内置提示词" if not it.get("prompt") else "自定义提示词"
            QListWidgetItem("%s（%s）" % (it["label"], tag), lst)
        n = lst.count()
        lst.setCurrentRow(cur if 0 <= cur < n else (n - 1 if n else -1))

    def _ai_menu_save(self, scope):
        from ai_pane import save_ai_menu_items
        save_ai_menu_items(self._win._settings, scope, self._ai_menu_data[scope])
        self._ai_menu_repaint(scope)

    def _ai_menu_cur(self, scope):
        lst = self._ai_menu_lists[scope]
        row = lst.currentRow()
        items = self._ai_menu_data[scope]
        if not (0 <= row < len(items)):
            QMessageBox.information(self, "提示", "请先在列表中选择一个菜单项。")
            return None, None
        return row, items[row]

    def _ai_menu_add(self, scope):
        res = self._ai_menu_prompt_dlg("添加菜单项")
        if res is None:
            return
        label, prompt = res
        items = self._ai_menu_data[scope]
        row = max(0, self._ai_menu_lists[scope].currentRow())
        items.insert(row + 1 if row >= 0 else len(items),
                     {"key": "c#" + label, "label": label, "prompt": prompt})
        self._ai_menu_save(scope)

    def _ai_menu_edit(self, scope):
        row, it = self._ai_menu_cur(scope)
        if row is None:
            return
        # v3.48.37（MENU-PREFILL）：内置项点开即带出内置提示词（不必自己写）；
        # 若用户原样保存，则仍按「留空 = 内置」落盘 —— 翻译的动态语种提示词
        # 因此不会被写死成单一方向。
        from ai_pane import builtin_prompt_for
        saved_prompt = it.get("prompt", "")
        prefill = saved_prompt or builtin_prompt_for(it.get("key", ""))
        res = self._ai_menu_prompt_dlg("编辑菜单项", it.get("label", ""), prefill)
        if res is None:
            return
        label, prompt = res
        it["label"] = label
        it["prompt"] = "" if (not saved_prompt and prompt == prefill) else prompt
        if it["key"].startswith("c#"):
            it["key"] = "c#" + label      # 自定义项的 key 跟随名称
        self._ai_menu_save(scope)

    def _ai_menu_del(self, scope):
        row, it = self._ai_menu_cur(scope)
        if row is None:
            return
        self._ai_menu_data[scope].pop(row)
        self._ai_menu_save(scope)

    def _ai_menu_move(self, scope, delta):
        row, it = self._ai_menu_cur(scope)
        if row is None:
            return
        items = self._ai_menu_data[scope]
        j = row + delta
        if not (0 <= j < len(items)):
            return
        items[row], items[j] = items[j], items[row]
        self._ai_menu_save(scope)
        self._ai_menu_lists[scope].setCurrentRow(j)

    def _ai_menu_reset(self, scope):
        from ai_pane import _builtin_menu_items
        if QMessageBox.question(
                self, "恢复默认", "恢复该菜单为内置菜单项？自定义项将被清除。"
        ) != QMessageBox.Yes:
            return
        self._ai_menu_data[scope] = _builtin_menu_items(scope)
        self._ai_menu_save(scope)

    def _ai_menu_prompt_dlg(self, title, label0="", prompt0=""):
        """菜单项编辑小对话框：返回 (label, prompt)；取消返回 None。"""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setModal(True)
        dlg.resize(420, 300)
        v = QVBoxLayout(dlg)
        form = QHBoxLayout()
        form.addWidget(QLabel("菜单名称"))
        ed_label = QLineEdit(label0)
        form.addWidget(ed_label, 1)
        v.addLayout(form)
        v.addWidget(QLabel("提示词（内置项已预填内置提示词，保持原样即继续使用内置；"
                           "自定义提示词请写明「只输出结果文本本身，不要附加解释」）"))
        ed_prompt = QPlainTextEdit(prompt0)
        ed_prompt.setPlaceholderText("例如：请把下面的文本改写成 FAQs 问答对，"
                                     "每条以「Q: / A:」开头，不要附加解释。")
        v.addWidget(ed_prompt, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)

        def _accept():
            if not ed_label.text().strip():
                QMessageBox.information(self, "提示", "菜单名称不能为空。")
                return
            dlg.accept()

        bb.accepted.disconnect()
        bb.accepted.connect(_accept)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        if not ok:
            return None
        return ed_label.text().strip(), ed_prompt.toPlainText().strip()

    def _page_ai_connection(self):
        """复用 ai_connection.AIConnectionForm：与独立连接面板共享同一份
        QSettings + 凭据存储，因此「设置里填的默认连接」即「主面板连接设置
        按钮打开的面板」所用数据。connection_changed 触发主面板状态条刷新。"""
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        form = AIConnectionForm(self._win._settings, self)
        form.connection_changed.connect(self._win._refresh_ai_status)
        lay.addWidget(form, 1)
        return page

    def showEvent(self, ev):
        super().showEvent(ev)
        # 打开时同步主窗口当前状态
        self._apply_theme_qss(getattr(self._win, "_theme", "light"))
        # v3.43.0：主题 / 界面风格 / 图表风格 / 代码风格已迁至「外观(&A)」菜单，
        # 设置中心不再同步这些项（唯一数据源 = QSettings，菜单展开时回写勾选）。
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(int(round(getattr(self._win, "_zoom", 1.0) * 100)))
        self.zoom_slider.blockSignals(False)
        self.zoom_lbl.setText(f"{self.zoom_slider.value()}%")
        self.autosave_box.blockSignals(True)
        self.autosave_box.setChecked(bool(getattr(self._win, "_autosave", True)))
        self.autosave_box.blockSignals(False)
        # v3.44（AUTOSAVE-INT）：保存时机同步 + 启用态跟随自动保存开关
        self.save_mode_box.blockSignals(True)
        _si_int = int(getattr(self._win, "_autosave_interval", 0) or 0)
        _si_idx = self.save_mode_box.findData(_si_int)
        self.save_mode_box.setCurrentIndex(_si_idx if _si_idx >= 0 else 0)
        self.save_mode_box.blockSignals(False)
        self._sync_save_mode_enabled()
        # 启动行为 + 指定文件夹（含旧 lastFileSide → session 兼容）
        _sa = str(getattr(self._win, "_startup_action", "session") or "session")
        if _sa == "lastFileSide":
            _sa = "session"
        self.startup_box.blockSignals(True)
        _sidx = self.startup_box.findData(_sa)
        self.startup_box.setCurrentIndex(_sidx if _sidx >= 0 else 0)
        self.startup_box.blockSignals(False)
        self.startup_dir_edit.blockSignals(True)
        self.startup_dir_edit.setText(str(getattr(self._win, "_file_list_default_dir", "") or ""))
        self.startup_dir_edit.blockSignals(False)
        self._sync_startup_dir_visible()
        # 最近文件保留条数
        self.recent_max_box.blockSignals(True)
        self.recent_max_box.setValue(int(getattr(self._win, "_recent_max", 10) or 10))
        self.recent_max_box.blockSignals(False)
        # P1-1 / P1-8 输入增强开关
        self.autopair_box.blockSignals(True)
        self.autopair_box.setChecked(bool(getattr(self._win, "_auto_pair", True)))
        self.autopair_box.blockSignals(False)
        self.emoji_box.blockSignals(True)
        self.emoji_box.setChecked(bool(getattr(self._win, "_emoji", True)))
        self.emoji_box.blockSignals(False)
        # 大纲级别 / 文件列表模式：与主窗口当前配置同步
        self.outline_level_box.blockSignals(True)
        self.outline_level_box.setCurrentIndex(
            max(0, int(getattr(self._win, "_outline_level", 3)) - 1))
        self.outline_level_box.blockSignals(False)
        _fm = "blank" if getattr(self._win, "_file_list_mode", "current") == "blank" else "current"
        self.file_mode_box.blockSignals(True)
        _fidx = self.file_mode_box.findData(_fm)
        self.file_mode_box.setCurrentIndex(_fidx if _fidx >= 0 else 0)
        self.file_mode_box.blockSignals(False)
        self.lang_box.blockSignals(True)
        cur_lang = str(getattr(self._win, "_code_lang", "C") or "C")
        self.lang_box.setCurrentText(cur_lang)
        self.lang_box.blockSignals(False)
        # 图片存放方式 / pandoc 路径：与主窗口当前配置同步
        _im = "embed" if getattr(self._win, "_image_mode", "assets") == "embed" else "assets"
        self.image_mode_box.blockSignals(True)
        _iidx = self.image_mode_box.findData(_im)
        self.image_mode_box.setCurrentIndex(_iidx if _iidx >= 0 else 0)
        self.image_mode_box.blockSignals(False)
        self.pandoc_edit.blockSignals(True)
        self.pandoc_edit.setText(str(getattr(self._win, "_pandoc_path", "") or ""))
        self.pandoc_edit.blockSignals(False)
        # v3.48.12（SEM-4）：语义搜索开关与索引状态同步
        self.sem_box.blockSignals(True)
        self.sem_box.setChecked(bool(getattr(self._win, "_sem_enabled", False)))
        self.sem_box.blockSignals(False)
        self._sync_sem_info()
        # P1-6 / P1-7：历史保留份数、外部编辑器路径同步
        self.history_keep_box.blockSignals(True)
        self.history_keep_box.setValue(int(getattr(self._win, "_history_keep", 5) or 5))
        self.history_keep_box.blockSignals(False)
        self.extedit_edit.blockSignals(True)
        self.extedit_edit.setText(str(getattr(self._win, "_external_editor", "") or ""))
        self.extedit_edit.blockSignals(False)
        # 斜杠菜单：与主窗口当前配置同步
        self._fill_menu_list(getattr(self._win, "_slash_order", None))
        self._fill_def_box()
        subs = getattr(self._win, "_slash_sub", {}) or {}
        for box, key in ((self.sub_heading_box, "heading"), (self.sub_list_box, "list"),
                         (self.sub_chart_box, "chart"), (self.sub_math_box, "math")):
            box.blockSignals(True)
            box.setCurrentIndex(max(0, int(subs.get(key, 0))))
            box.blockSignals(False)


# =========================================================================
# P1-3 命令面板（Ctrl+Shift+P）
# =========================================================================
# 中文命令名 → 拼音首字母（用于搜索加速；未收录的字直接跳过，不影响功能）
_PY_GROUPS = {
    "a": "安按爱",
    "b": "本版标表闭边板帮布笔",
    "c": "存查粗菜除侧藏插",
    "d": "打导单代动大对叠",
    "f": "分复符附",
    "g": "关格公割管",
    "h": "含换行回",
    "j": "件夹近辑剪加机键结继",
    "k": "开块快",
    "l": "历览列",
    "m": "命面码",
    "n": "内嵌",
    "p": "片屏配",
    "q": "迁切全签确",
    "r": "入日",
    "s": "书搜数视示史式删设索",
    "t": "退图贴替题统体",
    "w": "文为外",
    "x": "新销选线写显学系",
    "y": "页移引用源于隐",
    "z": "最作转在注助制正自展折资置专重做完",
}
_PY_INITIAL = {}


def _build_py_initial():
    if _PY_INITIAL:
        return
    for letter, chars in _PY_GROUPS.items():
        for ch in chars:
            _PY_INITIAL.setdefault(ch, letter)


def pinyin_initials(text):
    """取字符串中每个汉字的拼音首字母（未收录字跳过）。"""
    _build_py_initial()
    out = []
    for ch in str(text or ""):
        ini = _PY_INITIAL.get(ch)
        if ini:
            out.append(ini)
    return "".join(out)


class StyleManagerDialog(_ThemedDialog):
    """v3.43.0（LOOK-1）：界面风格管理（承接原设置中心「外观」页的风格组）。

    「外观(&A) → 界面风格」子菜单只列设计稿定义的 6 套（名称纯净），
    而风格注册表是可增删的（内置 10 套 + 用户自建）。本对话框保留完整的
    查看 / 应用 / 刷新 / 打开风格文件夹 / 删除能力，避免迁移丢功能。
    """

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("styleMgrDlg")
        self.setWindowTitle("界面风格管理")
        self.setModal(False)
        self.resize(560, 380)
        self._apply_theme_qss(getattr(win, "_theme", "light"))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        title = QLabel("界面风格")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        hint = QLabel("「外观 → 界面风格」菜单列出设计稿定义的 6 套；这里显示全部已安装风格"
                      "（含用户自建）。把风格 JSON 拖进风格文件夹后点「刷新」即可新增。")
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        row = QHBoxLayout()
        self.list_w = QListWidget(self)
        self.list_w.setObjectName("themeList")
        row.addWidget(self.list_w, 1)
        btns = QVBoxLayout()
        self.b_apply = QPushButton("应用", self)
        self.b_refresh = QPushButton("刷新", self)
        self.b_dir = QPushButton("风格文件夹…", self)
        self.b_del = QPushButton("删除所选", self)
        for b in (self.b_apply, self.b_refresh, self.b_dir, self.b_del):
            btns.addWidget(b)
        btns.addStretch(1)
        row.addLayout(btns)
        lay.addLayout(row, 1)

        self.info = QLabel("")
        self.info.setObjectName("pageHint")
        self.info.setWordWrap(True)
        self.info.setMinimumHeight(56)
        lay.addWidget(self.info)

        bb = QHBoxLayout()
        bb.addStretch(1)
        b_close = QPushButton("关闭", self)
        b_close.setDefault(True)
        bb.addWidget(b_close)
        lay.addLayout(bb)

        self.b_apply.clicked.connect(self._apply)
        self.b_refresh.clicked.connect(self.reload)
        self.b_dir.clicked.connect(self._open_dir)
        self.b_del.clicked.connect(self._del)
        b_close.clicked.connect(self.accept)
        self.list_w.itemSelectionChanged.connect(self._show_info)
        self.list_w.itemDoubleClicked.connect(lambda _i: self._apply())
        self.reload()

    # ---- 列表 ----
    def reload(self):
        """重扫风格目录；保持当前激活风格选中。"""
        cur = uistyles.active()
        self.list_w.clear()
        hit = None
        for s in uistyles.list_styles():
            in_menu = any(sid == s["id"] for sid, _n in uistyles.MENU_STYLES)
            mark = "（默认）" if s["id"] == uistyles.DEFAULT_ID else ""
            tag = "· 菜单" if in_menu else "· 仅管理"
            it = QListWidgetItem(f"{s['name']}{mark}　{tag}", self.list_w)
            it.setData(Qt.UserRole, s["id"])
            it.setToolTip(s["desc"])
            if s["id"] == cur:
                hit = it
        if hit is not None:
            self.list_w.setCurrentItem(hit)
        self.b_del.setEnabled(False)
        self._show_info()

    def _cur_id(self):
        it = self.list_w.currentItem()
        return it.data(Qt.UserRole) if it is not None else ""

    def _show_info(self):
        sid = self._cur_id()
        s = uistyles.get_style(sid) if sid else None
        if s is None:
            self.info.setText("")
            self.b_apply.setEnabled(False)
            self.b_del.setEnabled(False)
            return
        self.b_apply.setEnabled(True)
        self.b_del.setEnabled(sid != uistyles.DEFAULT_ID)
        in_menu = any(x == sid for x, _n in uistyles.MENU_STYLES)
        self.info.setText(
            f"ID：{s['id']}　{'内置' if not s.get('_user') else '用户'}　"
            f"{'在「外观 → 界面风格」菜单中' if in_menu else '不在菜单中（仅此处可应用）'}\n"
            f"{s['desc']}")

    def _apply(self):
        sid = self._cur_id()
        if sid:
            self._win.set_uistyle(sid)
            self.reload()

    def _open_dir(self):
        import subprocess
        d = uistyles.user_style_dir()
        try:
            subprocess.Popen(["explorer", d])
        except Exception:
            self._win.show_status(f"风格目录：{d}")

    def _del(self):
        sid = self._cur_id()
        if not sid or sid == uistyles.DEFAULT_ID:
            return
        s = uistyles.get_style(sid)
        r = QMessageBox.question(
            self, "删除风格",
            f"确定删除风格「{s['name'] if s else sid}」吗？\n\n"
            "将删除其风格文件；若为当前激活风格，会自动回退到默认风格。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        ok, msg = uistyles.remove_style(sid)
        if not ok:
            QMessageBox.warning(self, "删除风格", msg)
        elif sid == uistyles.active():
            self._win.set_uistyle(uistyles.DEFAULT_ID)
        self.reload()
        self._win.show_status(msg)


class InsertImageDialog(_ThemedDialog):
    """v3.29 插入图片统一面板（唯一入口，不再有编辑器内第二层面板）。

    · 本地文件：浏览按钮或直接粘贴完整路径；「存储方式」二选一单选
      （相对路径存储 / 内嵌式存储），默认跟随系统设置；
    · 网络 URL：粘贴 http(s) 地址直接插入，不做本地存储；
    · 存储名称不再在插入时指定 —— 插入后单击图片，在对象条「修改存储文件名」里
      修改（仅相对路径存储的图片支持，内嵌 / 网络图片不显示该功能）；
      插入时默认用文件名（assets 模式自动加 5 位编号前缀）。"""

    def __init__(self, win, src_path=""):
        super().__init__(win)
        self._win = win
        self._src = src_path or ""
        self.setObjectName("imgInsertDlg")
        self.setWindowTitle("插入图片")
        self.setModal(True)
        self.resize(500, 170)
        self._apply_theme_qss(getattr(win, "_theme", "light"))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(8)

        # ---- 图片文件 / URL ----
        lay.addWidget(QLabel("图片文件或网络地址"))
        prow = QHBoxLayout()
        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText("选择 / 粘贴本地图片完整路径，或 https:// 图片地址…")
        self.path_edit.setText(self._src)
        browse = QPushButton("浏览…", self)
        browse.setObjectName("imgBrowse")
        prow.addWidget(self.path_edit, 1)
        prow.addWidget(browse)
        lay.addLayout(prow)

        # ---- 存储方式：二选一单选（默认跟随系统设置） ----
        # 系统设置 = 相对路径存储 → 默认选中「相对路径存储」；= 内嵌存储 → 默认「内嵌式存储」。
        # 未保存文档选了相对路径时，插入会自动降级为内嵌并提示。
        srow = QHBoxLayout()
        slbl = QLabel("存储方式", self)
        self.rb_assets = QRadioButton("相对路径存储", self)
        self.rb_embed = QRadioButton("内嵌式存储", self)
        if str(getattr(win, "_image_mode", "embed")) == "assets":
            self.rb_assets.setChecked(True)
        else:
            self.rb_embed.setChecked(True)
        self.rb_assets.toggled.connect(self._update_preview)
        self.rb_embed.toggled.connect(self._update_preview)
        srow.addWidget(slbl)
        srow.addWidget(self.rb_assets)
        srow.addWidget(self.rb_embed)
        srow.addStretch(1)
        lay.addLayout(srow)

        hint = QLabel("存储名称在插入后单击图片指定（本地存储图 →「修改存储文件名」）", self)
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.preview = QLabel("", self)
        self.preview.setObjectName("pageHint")
        lay.addWidget(self.preview)

        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("插入", self)
        ok.setObjectName("primaryBtn")
        ok.setDefault(True)
        cancel = QPushButton("取消", self)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)

        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        browse.clicked.connect(self._browse)
        self.path_edit.textChanged.connect(self._on_path_changed)
        self._update_preview()

    # ---- 文件路径 / URL ----
    def is_url(self):
        return bool(re.match(r"^(https?|data):", str(self._src or ""), re.I))

    def _cur_stem(self, src=None):
        src = src or self._src
        if self.is_url():
            base = src.split("#")[0].split("?")[0].rstrip("/")
            k = max(base.rfind("/"), base.rfind("\\"))
            return base[k + 1:] if k >= 0 else "图片"
        return os.path.splitext(os.path.basename(src))[0] or "图片"

    def _browse(self):
        # v3.29d（B7）：记忆上次选择图片的目录（挂到主窗口，跨对话框有效）
        start = ""
        w = self.parent()
        if w is not None and hasattr(w, "_dlg_dir"):
            start = w._dlg_dir("image")
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", start,
            "图片 (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;所有文件 (*)")
        if path:
            if w is not None and hasattr(w, "_remember_dir"):
                w._remember_dir("image", path)
            self.path_edit.setText(path)

    def _on_path_changed(self, text):
        p = text.strip()
        if re.match(r"^(https?|data):", p, re.I):
            self._src = p
        elif p and os.path.isfile(p):
            self._src = p
        else:
            self._src = ""
        self._update_preview()

    def src_path(self):
        return self._src

    def accept(self):
        if not self._src:
            self.preview.setText("请先选择图片文件或粘贴图片地址（当前为空 / 路径不存在）")
            return
        super().accept()

    def _update_preview(self):
        if self.is_url():
            self.preview.setText("网络图片将以 URL 形式直接插入文档（不做本地存储）")
        elif self._src:
            if self.rb_assets.isChecked():
                self.preview.setText(
                    f"将复制到「文档名.assets」文件夹，默认名称：{self._cur_stem()}"
                    "（插入后单击图片 →「修改存储文件名」可修改）")
            else:
                self.preview.setText(
                    f"将以 data URL 内嵌进文档，默认说明文字：{self._cur_stem()}")
        else:
            self.preview.setText("")

    def mode(self):
        """「相对路径存储」= assets；「内嵌式存储」= embed。"""
        return "assets" if self.rb_assets.isChecked() else "embed"


class CommandPaletteDialog(_ThemedDialog):
    """命令面板：搜索并执行任意已注册命令（菜单动作 + 编辑器命令）。

    v3.25：改为 VSCode 风格 —— 无边框面板固定停靠在菜单栏下方顶端（不再悬浮居中），
    输入关键词（汉字 / 拼音首字母 / 快捷键）后才下拉显示候选，Esc 或失焦关闭。"""

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("cmdPalette")
        self.setWindowTitle("命令面板")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.resize(580, 440)
        self._apply_theme_qss(getattr(win, "_theme", "light"))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(8)
        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText("输入命令名称 / 拼音首字母 / 快捷键，回车执行…")
        self.edit.setClearButtonEnabled(True)
        self.edit.installEventFilter(self)
        lay.addWidget(self.edit)

        self.listw = QListWidget(self)
        self.listw.setObjectName("themeList")
        lay.addWidget(self.listw, 1)

        self.hint = QLabel("", self)
        self.hint.setObjectName("pageHint")
        lay.addWidget(self.hint)

        self._rows = []
        self.edit.textChanged.connect(self._refilter)
        self.edit.returnPressed.connect(self._run_current)
        self.listw.itemActivated.connect(lambda _i: self._run_current())
        self.listw.itemClicked.connect(lambda _i: self._run_current())

    # ---- 构建候选 ----
    def collect(self):
        win = self._win
        acts = getattr(win, "_shortcut_acts", {}) or {}
        rows = []
        for group, items in (getattr(win, "_shortcut_defs", []) or []):
            for name, _default in items:
                act = acts.get(name)
                if act is None:
                    continue
                rows.append({
                    "group": group, "name": name,
                    "seq": act.shortcut().toString(QKeySequence.PortableText),
                    "enabled": bool(act.isEnabled()),
                    "run": (lambda a=act: a.trigger()),
                })
        extra = getattr(win, "extra_commands", None)
        if callable(extra):
            try:
                rows.extend(extra() or [])
            except Exception as e:      # noqa: BLE001 — v3.29d（B9）：记录而非静默
                logging.getLogger("mdEditor.ui").debug("命令面板 extra 提供者失败: %s", e)
        return rows

    def refresh(self):
        self._rows = self.collect()
        self.edit.blockSignals(True)
        self.edit.setText("")
        self.edit.blockSignals(False)
        self.edit.setFocus()
        self._refilter("")

    def _score(self, row, q):
        """匹配打分：数值越小越靠前，-1 表示不匹配。"""
        name = str(row.get("name") or "")
        hay = name + " " + str(row.get("group") or "") + " " + str(row.get("seq") or "")
        low = hay.lower()
        nl = name.lower()
        if q in nl:
            return nl.index(q)
        if q in low:
            return 100 + low.index(q)
        ini = pinyin_initials(name).lower()
        if ini and q in ini:
            return 200 + ini.index(q)
        # v3.25：拼音首字母子序列匹配（「zd」→ 折(z)叠(d)…，字符可跳过中间字）
        if ini and len(q) >= 2:
            it_ = iter(ini)
            if all(c in it_ for c in q):
                return 250
        parts = [p for p in q.split() if p]
        if len(parts) > 1 and all((p in low or p in ini) for p in parts):
            return 300
        return -1

    def _refilter(self, text):
        q = str(text or "").strip().lower()
        rows = self._rows
        if not q:
            # v3.25：未输入时不显示候选列表（VSCode 风格，输入才下拉）
            self.listw.clear()
            self.listw.hide()
            # v3.44.29：空态提示只讲操作（↑↓/Enter/Esc），不再重复输入框占位文字，
            # 消除「输入命令…」与「输入以检索命令…」两行相似文案造成的重影。
            self.hint.setText("⌨ ↑ ↓ 选择 · Enter 执行 · Esc 关闭")
            return
        self.listw.show()
        if q:
            scored = []
            for r in rows:
                s = self._score(r, q)
                if s >= 0:
                    scored.append((s, r))
            scored.sort(key=lambda x: x[0])
            rows = [r for _s, r in scored]
        self.listw.clear()
        for r in rows[:200]:
            seq = str(r.get("seq") or "")
            label = f"{r['name']}    〔{r['group']}〕" + (f"    {seq}" if seq else "")
            it = QListWidgetItem(label, self.listw)
            it.setData(Qt.UserRole, r)
            if not r.get("enabled", True):
                it.setForeground(Qt.gray)
        if self.listw.count():
            self.listw.setCurrentRow(0)
        self.hint.setText(f"共 {len(rows)} 条 · ↑ ↓ 选择 · Enter 执行 · Esc 关闭")

    def _run_current(self):
        it = self.listw.currentItem()
        if it is None:
            return
        row = it.data(Qt.UserRole)
        if not row or not row.get("enabled", True):
            return
        self.accept()
        try:
            row["run"]()
        except Exception as e:      # noqa: BLE001 — 单个命令失败不影响面板（v3.29d：记录日志）
            logging.getLogger("mdEditor.ui").debug("命令面板命令执行失败: %s", e)

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == QEvent.Type.KeyPress:
            k = ev.key()
            if k in (Qt.Key_Down, Qt.Key_Up) and self.listw.count():
                row = self.listw.currentRow()
                row = row + 1 if k == Qt.Key_Down else row - 1
                self.listw.setCurrentRow(max(0, min(self.listw.count() - 1, row)))
                return True
            if k == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, ev)

    def showEvent(self, ev):
        super().showEvent(ev)
        self._apply_theme_qss(getattr(self._win, "_theme", "light"))
        # v3.25：面板固定停靠在主窗口菜单栏下方、水平居中（VSCode 风格）
        geo = self._win.geometry()
        menu_h = self._win.menuBar().height() if self._win.menuBar() else 0
        self.move(geo.x() + max(8, (geo.width() - self.width()) // 2),
                  geo.y() + menu_h + 10)
        self.refresh()


# =========================================================================
# P1-6 版本历史
# =========================================================================
class DiffDialog(_ThemedDialog):
    """v3.31（#27）：版本差异对比视图；v3.38（DIFF-1）：词级高亮 + 单栏/双栏切换。

    - 行级差异沿用 difflib.SequenceMatcher；replace 块内 del/add 行按顺序 1:1 配对，
      配对行再做字符级 SequenceMatcher，非 equal 段用 <span> 词级高亮（>300 字符护栏）；
    - 「单栏（unified，默认）| 双栏（split）」切换，QSettings `diff/layout` 跨会话记忆；
    - 双栏 = QSplitter 内双 QTextBrowser + 左右列头 + 同步滚动（防递归互连）；
    - 行流由 build_rows 公共构造，两模式从同一序列投影，内容恒一致；
    - 对齐近似：QTextBrowser 自动换行下长段两侧可能错位 1~2 视觉行（方案 §5 已声明接受）。
    QTextBrowser 展示静态 HTML，零外部依赖。"""

    MAX_ROWS = 4000   # 超长差异截断（双栏按行对截断，左右行数恒等）
    WORD_MAX = 300    # 词级 diff 字符护栏：超长行退整行着色

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("diffDlg")
        self.setWindowTitle("版本对比")
        self.setModal(False)
        self.resize(860, 560)
        self._apply_theme_qss(getattr(win, "_theme", "light"))
        self._rows = None        # build_rows 产物（切布局不重算 diff）
        self._colors = None
        self._widened = False    # 首次切双栏放宽窗口只做一次

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(8)
        self.title_lbl = QLabel("", self)
        self.title_lbl.setObjectName("pageTitle")
        lay.addWidget(self.title_lbl)
        self.stat_lbl = QLabel("", self)
        self.stat_lbl.setObjectName("pageHint")
        lay.addWidget(self.stat_lbl)

        # ---- v3.38（DIFF-1）：单栏 | 双栏 切换（默认单栏，QSettings 记忆） ----
        trow = QHBoxLayout()
        trow.addWidget(QLabel("视图"))
        self.layout_box = QComboBox(self)
        self.layout_box.addItem("单栏", "unified")
        self.layout_box.addItem("双栏", "split")
        _cur = str(self._win._settings.value("diff/layout", "unified") or "unified")
        _ci = self.layout_box.findData(_cur)
        self.layout_box.setCurrentIndex(_ci if _ci >= 0 else 0)
        self.layout_box.currentIndexChanged.connect(self._on_layout)
        trow.addWidget(self.layout_box, 1)
        trow.addStretch(1)
        lay.addLayout(trow)

        # 单栏视图（左栏浏览器同时复用为双栏左列，切布局只换容器可见性）
        self.view = QTextBrowser(self)
        self.view.setOpenExternalLinks(False)
        # 双栏：QSplitter + 左右列头 + 双浏览器
        self.split = QSplitter(Qt.Horizontal, self)
        self.lbl_l = QLabel("", self)
        self.lbl_r = QLabel("", self)
        pane_l = QWidget(self)
        vl = QVBoxLayout(pane_l)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(2)
        vl.addWidget(self.lbl_l)
        self.view_l = QTextBrowser(self)
        self.view_l.setOpenExternalLinks(False)
        vl.addWidget(self.view_l, 1)
        self.split.addWidget(pane_l)
        pane_r = QWidget(self)
        vr = QVBoxLayout(pane_r)
        vr.setContentsMargins(0, 0, 0, 0)
        vr.setSpacing(2)
        vr.addWidget(self.lbl_r)
        self.view_r = QTextBrowser(self)
        self.view_r.setOpenExternalLinks(False)
        vr.addWidget(self.view_r, 1)
        self.split.addWidget(pane_r)
        self.split.setSizes([1, 1])
        lay.addWidget(self.view, 1)
        lay.addWidget(self.split, 1)
        # v3.38（DIFF-1）：双栏同步滚动（blockSignals 防递归）
        self.view_l.verticalScrollBar().valueChanged.connect(self._sync_scroll_l)
        self.view_r.verticalScrollBar().valueChanged.connect(self._sync_scroll_r)

        brow = QHBoxLayout()
        brow.addStretch(1)
        b_close = QPushButton("关闭", self)
        b_close.clicked.connect(self.close)
        brow.addWidget(b_close)
        lay.addLayout(brow)
        self._on_layout(self.layout_box.currentIndex())   # 按记忆的布局初始化可见性

    # ---------- 同步滚动 ----------
    def _sync_scroll_l(self, v):
        sb = self.view_r.verticalScrollBar()
        sb.blockSignals(True)
        sb.setValue(v)
        sb.blockSignals(False)

    def _sync_scroll_r(self, v):
        sb = self.view_l.verticalScrollBar()
        sb.blockSignals(True)
        sb.setValue(v)
        sb.blockSignals(False)

    def _on_layout(self, _i):
        self._win._settings.setValue("diff/layout", self.layout_box.currentData())
        if self._rows is not None:
            self._render()

    # ---------- 转义（v3.48.25 热修：重构补丁误删 _esc，补回并统一委托
    # diffmerge.esc_html —— _render 十余处 self._esc 调用依赖本方法） ----------
    def _esc(self, s):
        return esc_html(s)

    # ---------- v3.38（DIFF-1）：词级配对（v3.48.25 MERGE-CORE 起算法由
    # 统一差异引擎 diffmerge 提供，与 MergeDialog / AIFragmentDialog 同一套） ----------
    def _pair_html(self, text, ops, color, side):
        """配对行按字符级 opcodes 生成词级高亮 HTML（side: "a"|"b"）；
        ops 为 None 时返回 None（退整行着色）。"""
        if not ops:
            return None
        out = []
        for tag, i1, i2, j1, j2 in ops:
            a, b = (j1, j2) if side == "b" else (i1, i2)
            seg = self._esc(text[a:b])
            out.append('<span style="background:%s;">%s</span>' % (color, seg)
                       if tag != "equal" else seg)
        return "".join(out)

    def _build_rows(self, old_lines, new_lines, c_wdel, c_wadd):
        """公共行流：行级差异与 replace 块 1:1 行配对由统一引擎
        diffmerge.build_hunks + build_rows 提供，本方法只做词级 HTML 投影
        与计数，保持 (kl, tl, hl, kr, tr, hr) 元组格式与返回值不变。"""
        # v3.48.31：历史版本对比按**原文行**显示（不按句号人工折行 ——
        # 用户实测要求）；精细化差异由 build_rows 内的 word_ops_deep 给出
        rows = build_rows(build_hunks(old_lines, new_lines))
        out = []
        add = dele = same = 0
        for r in rows:
            hl = self._pair_html(r["lt"], r["lw"], c_wdel, "a")
            hr = self._pair_html(r["rt"], r["lw"], c_wadd, "b")
            out.append((r["lk"], r["lt"], hl, r["rk"], r["rt"], hr))
            if r["lk"] == "ctx":
                same += 1
            elif r["lk"] == "del":
                dele += 1
            if r["rk"] == "add":
                add += 1
        return out, add, dele, same

    def show_diff(self, title, old_text, new_text, old_label, new_label):
        self.title_lbl.setText(title)
        theme = getattr(self._win, "_theme", "light")
        dark = theme in ("dark", "night", "panda")
        # v3.38（DIFF-1）：行底沿用两档；词级取更深一档（方案 §4 配色）
        c_add = "#1e3b2a" if dark else "#e2f6e9"
        c_del = "#3f2222" if dark else "#fde8e8"
        c_wadd = "#2a5c42" if dark else "#9FE1CB"
        c_wdel = "#5c2f2f" if dark else "#F5C4B3"
        try:
            c_ctx = palette(theme).get("text_muted", "#6b7280")
        except Exception:      # noqa: BLE001
            c_ctx = "#6b7280"
        self._colors = (dark, c_add, c_del, c_ctx, c_wadd, c_wdel)
        old_lines = str(old_text or "").split("\n")
        new_lines = str(new_text or "").split("\n")
        self._rows, add, dele, same = self._build_rows(
            old_lines, new_lines, c_wdel, c_wadd)
        self.lbl_l.setText(old_label)
        self.lbl_r.setText(new_label)
        if add == 0 and dele == 0:
            self.stat_lbl.setText("两个版本内容一致。")
            self.view.setPlainText("")
            self.view_l.setPlainText("")
            self.view_r.setPlainText("")
        else:
            self.stat_lbl.setText(
                f"新增 {add} 行 · 删除 {dele} 行 · 相同 {same} 行　（{old_label} → {new_label}）")
            self._render()
        self.show()
        self.raise_()
        self.activateWindow()

    def _render(self):
        """按当前布局渲染（切布局不重算 diff，直接复用缓存的行流）。"""
        dark, c_add, c_del, c_ctx, c_wadd, c_wdel = self._colors
        rows = self._rows
        c_sp = "#3a3f4b" if dark else "#d1d5db"
        if self.layout_box.currentData() == "split":
            self.view.setVisible(False)
            self.split.setVisible(True)
            if not self._widened:
                self._widened = True
                if self.width() < 1000:   # 仅首次切双栏且未手动放宽过
                    self.resize(1100, self.height())
            shown = rows[:self.MAX_ROWS]
            pl = ['<div style="font-family: Consolas, monospace; font-size: 12px; line-height: 1.5;">']
            pr = ['<div style="font-family: Consolas, monospace; font-size: 12px; line-height: 1.5;">']
            for kl, tl, hl, kr, tr, hr in shown:
                if kl == "spacer":
                    pl.append(f'<div style="border-top:1px dashed {c_sp};'
                              f'border-bottom:1px dashed {c_sp};color:{c_ctx};">&nbsp;</div>')
                elif kl == "del":
                    body = hl if hl else self._esc(tl)
                    st_l = '' if hl else f'background:{c_del};'
                    pl.append(f'<div style="{st_l}">{body}</div>')
                else:
                    pl.append(f'<div style="color:{c_ctx};">{self._esc(tl)}</div>')
                if kr == "spacer":
                    pr.append(f'<div style="border-top:1px dashed {c_sp};'
                              f'border-bottom:1px dashed {c_sp};color:{c_ctx};">&nbsp;</div>')
                elif kr == "add":
                    body = hr if hr else self._esc(tr)
                    st_r = '' if hr else f'background:{c_add};'
                    pr.append(f'<div style="{st_r}">{body}</div>')
                else:
                    pr.append(f'<div style="color:{c_ctx};">{self._esc(tr)}</div>')
            tail = f'<div style="color:{c_ctx};">… 其余 {len(rows) - self.MAX_ROWS} 行省略</div>'
            if len(rows) > self.MAX_ROWS:
                pl.append(tail)
                pr.append(tail)
            pl.append("</div>")
            pr.append("</div>")
            self.view_l.setHtml("".join(pl))
            self.view_r.setHtml("".join(pr))
        else:
            self.split.setVisible(False)
            self.view.setVisible(True)
            parts = ['<div style="font-family: Consolas, monospace; font-size: 12px; line-height: 1.5;">']
            for kl, tl, hl, kr, tr, hr in rows[:self.MAX_ROWS]:
                # v3.38 修复：单栏从行流投影时 replace 对两侧都要输出（旧版 del/add
                # 各占一行；投影只取左列会丢失 add 侧内容）
                if kl == "del" and kr == "add":
                    body = hl if hl else self._esc(tl)
                    st_d = '' if hl else f'background:{c_del};'
                    parts.append(f'<div style="{st_d}">{body}</div>')
                    body2 = hr if hr else self._esc(tr)
                    st_r2 = '' if hr else f'background:{c_add};'
                    parts.append(f'<div style="{st_r2}">{body2}</div>')
                    continue
                if kl == "spacer":
                    body2 = hr if hr else self._esc(tr)
                    st_r2 = '' if hr else f'background:{c_add};'
                    parts.append(f'<div style="{st_r2}">{body2}</div>')
                    continue
                if kr == "spacer":
                    body = hl if hl else self._esc(tl)
                    st_d = '' if hl else f'background:{c_del};'
                    parts.append(f'<div style="{st_d}">{body}</div>')
                    continue
                if kl == "add":
                    body = hl if hl else self._esc(tl)
                    st_a = '' if hl else f'background:{c_add};'
                    parts.append(f'<div style="{st_a}">{body}</div>')
                elif kl == "del":
                    body = hl if hl else self._esc(tl)
                    st_d = '' if hl else f'background:{c_del};'
                    parts.append(f'<div style="{st_d}">{body}</div>')
                else:
                    parts.append(f'<div style="color:{c_ctx};">{self._esc(tl)}</div>')
            if len(rows) > self.MAX_ROWS:
                parts.append(f'<div style="color:{c_ctx};">… 其余 {len(rows) - self.MAX_ROWS} 行省略</div>')
            parts.append("</div>")
            self.view.setHtml("".join(parts))

    def showEvent(self, ev):
        super().showEvent(ev)
        self._apply_theme_qss(getattr(self._win, "_theme", "light"))


class FmtLogDialog(_ThemedDialog):
    """v3.39.8（FMT-LOG）：格式化操作日志查看器。
    日志由编辑器内核记录（每次行内格式突变一条：序号/时间/动作/源码片段）、
    主窗口 collect 轮询差量落盘 %APPDATA%/mdEditor/fmtlog/fmt-YYYYMMDD.log
    （JSON Lines）。此处读全部日志文件，支持 刷新 / 复制 / 导出 / 清空。"""

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("fmtlogDlg")
        self.setWindowTitle("格式化操作日志")
        self.setModal(False)
        self.resize(860, 560)
        self._apply_theme_qss(getattr(win, "_theme", "light"))

        lay = QVBoxLayout(self)
        hint = QLabel("每次行内格式操作（包裹 / 取消 / 清除 / 码壳 toggle / 单元格格式）的"
                      "时间、动作与应用前后源码片段；按「对象 → 结果」序列可逐步复现问题。"
                      "随测试报告一并发送本日志可大幅加快定位。")
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setObjectName("logView")
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        f = self.text.font()
        f.setFamilies(["Consolas", "Courier New", "monospace"])
        self.text.setFont(f)
        lay.addWidget(self.text, 1)

        row = QHBoxLayout()
        b_refresh = QPushButton("刷新")
        b_copy = QPushButton("复制全部")
        b_export = QPushButton("导出为文本…")
        b_clear = QPushButton("清空日志文件…")
        b_close = QPushButton("关闭")
        b_close.setDefault(True)
        for b in (b_refresh, b_copy, b_export, b_clear):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)

        b_refresh.clicked.connect(self.load_log)
        b_copy.clicked.connect(self._copy_all)
        b_export.clicked.connect(self._export)
        b_clear.clicked.connect(self._clear_files)
        b_close.clicked.connect(self.accept)
        self.load_log()

    # ---- 数据 ----
    def _log_files(self):
        if not os.path.isdir(FMTLOG_DIR):
            return []
        out = []
        for name in sorted(os.listdir(FMTLOG_DIR)):
            if name.startswith("fmt-") and name.endswith(".log"):
                fp = os.path.join(FMTLOG_DIR, name)
                out.append(fp)
        return out

    def load_log(self):
        """读全部日志文件并格式化为可读文本（时间 序号 [动作](备注) 文档 / 对象 / 结果）。"""
        lines = []
        for fp in self._log_files():
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    raw_lines = f.read().splitlines()
            except OSError:
                continue
            for ln in raw_lines:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    e = json.loads(ln)
                except ValueError:
                    lines.append(ln)   # 非 JSON 行原样保留（容错）
                    continue
                head = f"#{e.get('n', '?')} {e.get('t', '')} [{e.get('act', '')}]"
                if e.get("note"):
                    head += f"({e['note']})"
                if e.get("doc"):
                    head += f" 文档:{e['doc']}"
                lines.append(head)
                if e.get("obj"):
                    lines.append(f"    对象: {e['obj']}")
                if e.get("res"):
                    lines.append(f"    结果: {e['res']}")
        self.text.setPlainText("\n".join(lines))

    def _plain_text(self):
        return self.text.toPlainText()

    # ---- 动作 ----
    def _copy_all(self):
        QApplication.clipboard().setText(self._plain_text())
        self._win.show_status("日志已复制到剪贴板")

    def _export(self):
        if not self._plain_text():
            self._win.show_status("日志为空，无可导出内容")
            return
        default = os.path.join(os.path.expanduser("~"), "Desktop",
                               "mdeditor-fmtlog-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".txt")
        path, _ = QFileDialog.getSaveFileName(self, "导出格式化操作日志", default,
                                              "文本文件 (*.txt);;全部文件 (*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._plain_text() + "\n")
            self._win.show_status(f"日志已导出：{path}")
        except OSError as e:
            QMessageBox.warning(self, "导出失败", f"写入文件失败：{e}")

    def _clear_files(self):
        files = self._log_files()
        if not files:
            self._win.show_status("暂无日志文件")
            return
        btn = QMessageBox.question(
            self, "清空日志文件",
            f"删除 {len(files)} 个日志文件（fmt-*.log）？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if btn != QMessageBox.Yes:
            return
        n = 0
        for fp in files:
            try:
                os.remove(fp)
                n += 1
            except OSError:
                continue
        self.load_log()
        self._win.show_status(f"已删除 {n} 个日志文件")


class HistoryDialog(_ThemedDialog):
    """版本历史：列出保存时留下的快照，可预览、对比并恢复。"""

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("historyDlg")
        self.setWindowTitle("历史版本")
        self.setModal(False)
        self.resize(780, 520)
        self._apply_theme_qss(getattr(win, "_theme", "light"))
        self._cur_file = None
        self._items = []      # [(path, mtime)]
        # v3.39.7（HIST-3）：勾选点击顺序队列（行号，旧→新）——
        # 勾选超过两项时保留最近两次点击的两项
        self._hist_clicks = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(8)
        self.title_lbl = QLabel("", self)
        self.title_lbl.setObjectName("pageTitle")
        lay.addWidget(self.title_lbl)
        self.hint = QLabel(
            "每次保存都会先把上一版内容留档到文档同目录的 .mdeditor-history 文件夹，只保留最近若干份。"
            "恢复会把所选内容写入当前编辑区（处于未保存状态，需再按 Ctrl+S 落盘）。", self)
        self.hint.setObjectName("pageHint")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        row = QHBoxLayout()
        self.listw = QListWidget(self)
        self.listw.setObjectName("themeList")
        self.listw.setMinimumWidth(240)
        self.listw.currentRowChanged.connect(self._on_pick)
        # v3.38（DIFF-2）：扩展选择 —— 单击仍是单选预览；Ctrl/Shift 可选两项互比
        self.listw.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listw.itemSelectionChanged.connect(self._on_sel_changed)
        self.listw.itemClicked.connect(self._on_item_clicked)   # v3.39.7（HIST-3）
        row.addWidget(self.listw, 0)
        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("（选择左侧快照查看内容）")
        row.addWidget(self.preview, 1)
        lay.addLayout(row, 1)

        brow = QHBoxLayout()
        brow.addStretch(1)
        # v3.31（#27）：版本差异对比；v3.38（DIFF-2）：任选两快照互比
        self.b_diff_two = QPushButton("对比所选两项", self)
        self.b_diff_two.setEnabled(False)
        self.b_diff_two.clicked.connect(self._diff_two)
        # v3.47.4（REQ3）：任选两快照合并（git/SVN 风格冲突标记）
        self.b_merge = QPushButton("合并所选两项", self)
        self.b_merge.setEnabled(False)
        self.b_merge.clicked.connect(self._merge_two)
        self.b_diff_prev = QPushButton("与上一版本对比", self)
        self.b_diff_prev.clicked.connect(self._diff_prev)
        self.b_diff_cur = QPushButton("与当前文档对比", self)
        self.b_diff_cur.clicked.connect(self._diff_current)
        self.b_restore = QPushButton("恢复此版本", self)
        self.b_restore.clicked.connect(self._restore)
        self.b_folder = QPushButton("在文件夹中显示", self)
        self.b_folder.clicked.connect(self._open_folder)
        b_close = QPushButton("关闭", self)
        b_close.clicked.connect(self.close)
        brow.addWidget(self.b_diff_two)
        brow.addWidget(self.b_merge)
        brow.addWidget(self.b_diff_prev)
        brow.addWidget(self.b_diff_cur)
        brow.addWidget(self.b_restore)
        brow.addWidget(self.b_folder)
        brow.addWidget(b_close)
        lay.addLayout(brow)

    def show_for(self, path):
        self._cur_file = path
        self.title_lbl.setText(
            f"历史版本 · {os.path.basename(path) if path else '（未保存文档）'}")
        try:
            self._items = self._win.list_history(path) if path else []
        except Exception:      # noqa: BLE001
            self._items = []
        self.listw.blockSignals(True)
        self.listw.clear()
        self.preview.setPlainText("")
        self._hist_clicks = []   # v3.39.7（HIST-3）：重建列表时点击顺序一并清空
        if not self._items:
            # v3.32（P0-3）：空态说明触发规则 —— 让用户知道"为什么没有快照"
            hint = "（未保存文档没有版本历史，保存后可用）" if not path else \
                "（本文档尚未产生快照 · 快照在保存 / 自动保存写盘时生成）"
            self.listw.addItem(QListWidgetItem(hint))
            self.listw.addItem(QListWidgetItem("提示：文件菜单 / 命令面板可「立即留档」手动打点"))
            self.b_restore.setEnabled(False)
            self.b_folder.setEnabled(False)
            self.b_diff_cur.setEnabled(False)
            self.b_diff_prev.setEnabled(False)
            self.b_diff_two.setEnabled(False)
            self.b_merge.setEnabled(False)
        else:
            for fp, mt in self._items:
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    size = 0
                self.listw.addItem(QListWidgetItem(
                    f"{datetime.fromtimestamp(mt).strftime('%Y-%m-%d %H:%M:%S')}    {size} 字节"))
            self.listw.setCurrentRow(0)
            # v3.38（HIST-1）：ExtendedSelection 下 setCurrentRow 不产生勾选，
            # 显式勾选首项，保持「打开即可预览 / 恢复」的旧可用性
            if self.listw.count() > 0:
                self.listw.item(0).setSelected(True)
        self.listw.blockSignals(False)
        self._on_pick(self.listw.currentRow())
        self._on_sel_changed()   # v3.38（HIST-1）：按钮状态统一由选择变化驱动
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_pick(self, row):
        if row < 0 or row >= len(self._items):
            return
        fp = self._items[row][0]
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                self.preview.setPlainText(f.read())
        except OSError as e:
            self.preview.setPlainText(f"（读取失败：{e}）")

    @staticmethod
    def _fmt_when(mtime):
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

    def _snap_text(self, row):
        if row < 0 or row >= len(self._items):
            return None
        try:
            with open(self._items[row][0], "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return None

    def _current_text(self):
        win = self._win
        if 0 <= getattr(win, "_cur", -1) < len(getattr(win, "_docs", [])):
            cached = win._docs[win._cur].get("content")
            if cached is not None:
                return cached   # 编辑区实时内容（含未保存修改）
        if win.file_path and os.path.isfile(win.file_path):
            try:
                with open(win.file_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except OSError:
                return ""
        return ""

    def _ensure_diff_dlg(self):
        if not hasattr(self, "_diff_dlg"):
            self._diff_dlg = DiffDialog(self._win)
        self._diff_dlg._apply_theme_qss(getattr(self._win, "_theme", "light"))
        return self._diff_dlg

    def _ensure_merge_dlg(self):
        if not hasattr(self, "_merge_dlg"):
            self._merge_dlg = MergeDialog(self._win)
        self._merge_dlg._apply_theme_qss(getattr(self._win, "_theme", "light"))
        return self._merge_dlg

    def _merge_two(self):
        """v3.47.4（REQ3）：任选两个快照合并 —— 按 mtime 旧→新作为 A/B，
        复用 MergeDialog（自动生成 git/SVN 风格冲突标记 + 可编辑合并结果）。"""
        sel = self.listw.selectedItems()
        if len(sel) != 2:
            return
        rows = sorted([self.listw.row(it) for it in sel],
                      key=lambda r: self._items[r][1])
        a = self._snap_text(rows[0])
        b = self._snap_text(rows[1])
        if a is None or b is None:
            return   # 快照在合并期间被清理：沿用现有静默返回模式
        name = os.path.basename(self._cur_file) if self._cur_file else "（未保存文档）"
        self._ensure_merge_dlg().show_merge(
            f"合并版本 · {name}", a, b,
            f"快照 {self._fmt_when(self._items[rows[0]][1])}",
            f"快照 {self._fmt_when(self._items[rows[1]][1])}")

    def _diff_current(self):
        """v3.31（#27）：所选快照 vs 当前编辑区内容。"""
        row = self.listw.currentRow()
        old = self._snap_text(row)
        if old is None:
            return
        name = os.path.basename(self._cur_file) if self._cur_file else "（未保存文档）"
        self._ensure_diff_dlg().show_diff(
            f"版本对比 · {name}", old, self._current_text(),
            f"快照 {self._fmt_when(self._items[row][1])}", "当前文档")

    def _on_item_clicked(self, item):
        """v3.39.7（HIST-3）：点击已有勾选但选择未变化的情形（如重复单击同一
        已勾选项）也把该行刷新为「最近点击」——只影响顺序队列，不动选择集。"""
        if item is None:
            return
        row = self.listw.row(item)
        if row < 0 or row >= len(self._items):
            return
        if row in self._hist_clicks:
            self._hist_clicks.remove(row)
        self._hist_clicks.append(row)

    def _on_sel_changed(self):
        """v3.38（HIST-1）：按勾选数量统一驱动四个按钮的启用 / 禁用。
        v3.39.7（HIST-3）：勾选数量约束改为「最近两次点击」——
        - 超过两项同时勾选时，自动取消较早点击的项，只保留**最近两次点击**
          的两项（点击顺序队列 _hist_clicks，旧→新）；
        - 取消部分勾选再重新勾选 / 重新点击同一版本：重新勾选视为最新一次
          点击，顺序随之刷新（取消即出队、勾选即入队）；
        - 少于两项：维持原行为（不干预选择）。
        按钮启用规则：
        - 恰选 1 项：启用「与上一版本对比」「与当前文档对比」「恢复此版本」，
          禁用「对比所选两项」；
        - 恰选 2 项：只启用「对比所选两项」，其余三个禁用（单选语义按钮
          对两项选择无意义）；
        - 0 项 / 超界：全部禁用。"""
        if not hasattr(self, "b_diff_two") or not self._items:
            return
        sel = self.listw.selectedItems()
        sel_rows = [self.listw.row(it) for it in sel]
        sel_set = set(sel_rows)
        # 刷新点击顺序队列：已取消的行出队；新勾选的行（按行号序）入队尾
        old_order = [r for r in self._hist_clicks if r in sel_set]
        added = [r for r in sorted(sel_set - set(old_order))]
        self._hist_clicks = old_order + added
        # 约束：最多同时勾选两项 —— 保留最近两次点击的两项
        if len(sel_rows) > 2:
            keep = set(self._hist_clicks[-2:])
            self.listw.blockSignals(True)
            for it in list(sel):
                if self.listw.row(it) not in keep:
                    it.setSelected(False)
            self.listw.blockSignals(False)
            self._hist_clicks = [r for r in self._hist_clicks if r in keep]
            sel = self.listw.selectedItems()
        n = len(sel)
        self.b_diff_two.setEnabled(n == 2)
        self.b_merge.setEnabled(n == 2)   # v3.47.4（REQ3）：恰选两项才可合并
        single = (n == 1)
        row = self.listw.currentRow()
        self.b_diff_cur.setEnabled(single)
        self.b_restore.setEnabled(single)
        # v3.44.9（HIST-SEL）：选中首项（最旧版本，row==0）无更早版本可对比，
        # 禁用「与上一版本对比」；否则（single 且 row>0）启用
        self.b_diff_prev.setEnabled(single and row > 0)

    def _diff_two(self):
        """v3.38（DIFF-2）：任选两个快照互比 —— 按 mtime 旧→新作为 old/new
        （复用 DiffDialog，自动获得词级高亮与单栏/双栏切换能力）。"""
        sel = self.listw.selectedItems()
        if len(sel) != 2:
            return
        rows = sorted([self.listw.row(it) for it in sel],
                      key=lambda r: self._items[r][1])
        old = self._snap_text(rows[0])
        new = self._snap_text(rows[1])
        if old is None or new is None:
            return   # 快照在对比期间被清理：沿用现有静默返回模式
        name = os.path.basename(self._cur_file) if self._cur_file else "（未保存文档）"
        self._ensure_diff_dlg().show_diff(
            f"版本对比 · {name}", old, new,
            f"快照 {self._fmt_when(self._items[rows[0]][1])}",
            f"快照 {self._fmt_when(self._items[rows[1]][1])}")

    def _diff_prev(self):
        """v3.31（#27）：所选快照 vs 更新一份的快照（列表按时间倒序，row-1 更新）。"""
        row = self.listw.currentRow()
        old = self._snap_text(row)
        newer = self._snap_text(row - 1)
        if old is None or newer is None:
            return
        name = os.path.basename(self._cur_file) if self._cur_file else "（未保存文档）"
        self._ensure_diff_dlg().show_diff(
            f"版本对比 · {name}", old, newer,
            f"快照 {self._fmt_when(self._items[row][1])}",
            f"快照 {self._fmt_when(self._items[row - 1][1])}")

    def _restore(self):
        row = self.listw.currentRow()
        if row < 0 or row >= len(self._items):
            return
        self._win.restore_history(self._items[row][0], self._items[row][1])

    def _open_folder(self):
        if self._cur_file:
            self._win.show_in_explorer(self._cur_file)

    def showEvent(self, ev):
        super().showEvent(ev)
        self._apply_theme_qss(getattr(self._win, "_theme", "light"))


class MergeDialog(_ThemedDialog, TwoPaneMergeMixin):
    """v3.48.25（MERGE-CORE 重构）：Beyond Compare 式三区域版本合并。

    差异计算 / 对比视图 / 选区合并全部由统一引擎 diffmerge 提供
    （与版本对比 DiffDialog、AI 片段替换 AIFragmentDialog 同一套实现）。
    v3.48.27 语义：仅对**有差异的文字**着色（左红右绿，相同文字无底色）；
    合并入口 —— 选中文字后双击或右键「合并所选内容」（按字符级对齐原位
    替换到下方结果框，可跨行、可反复叠加，其余不动）；右键「全部采用
    左 / 右」整行裁决。下方合并框默认即最新版本全文：仅冲突文字黄底
    （与对侧逐字比较，相同文字无底色），红/绿底=合并自左/右侧的内容
    （整行被完整合并为某侧时整行着该侧色）；左/右栏选中联动浅蓝高亮、
    三框滚动同步；可直接手动编辑，按行原位替换、不影响其余手工修改。点
    「应用到当前文档」以合并框当前文本整段替换目标段落。
    仅保留功能性按钮：应用到当前文档、另存为、关闭。"""

    mp_all_left_text = "全部采用左(A)"
    mp_all_right_text = "全部采用右(B)"

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("mergeDlg")
        self.setWindowTitle("合并版本")
        self.setModal(False)
        self.resize(980, 680)
        self._apply_theme_qss(getattr(win, "_theme", "light"))
        self.title_lbl = QLabel("", self)
        self.title_lbl.setObjectName("pageTitle")
        self._mp_build_ui(
            top_widgets=[self.title_lbl],
            result_hint=("合并结果（默认最新版本 · 可编辑）：仅差异文字有底色 ——"
                         " 黄=未合并的冲突文字（相同文字无底色），红=合并自左侧（快照），"
                         " 绿=合并自右侧（最新）。任意一框选中文字，另两框对应内容浅蓝"
                         " 高亮（无对应内容时高亮空白占位行）、三框滚动同步。选中后双击"
                         " 或右键「合并所选内容」仅合并所选；右键「选中采用（左/右）」把"
                         " 所选范围替换为另一侧对应内容；右键可「全部采用左 / 右」。"))
        self.stat_lbl = self.mp_stat      # 另存为等提示复用状态行
        self._a_label = ""
        self._b_label = ""

    def _mp_tail_buttons(self, brow):
        brow.addStretch(1)
        self.b_apply = QPushButton("应用到当前文档", self)
        self.b_save = QPushButton("另存为…", self)
        b_close = QPushButton("关闭", self)
        self.b_apply.clicked.connect(self._apply)
        self.b_save.clicked.connect(self._save)
        b_close.clicked.connect(self.close)
        for b in (self.b_apply, self.b_save, b_close):
            brow.addWidget(b)

    def eventFilter(self, obj, ev):
        handled = self._mp_event_filter(obj, ev)
        if handled is not None:
            return handled
        return super().eventFilter(obj, ev)

    def show_merge(self, title, a_text, b_text, a_label, b_label):
        self.title_lbl.setText(title)
        self._a_label, self._b_label = a_label, b_label
        self._mp_set_labels(a_label, b_label)
        self._mp_load(a_text, b_text,
                      theme=getattr(self._win, "_theme", "light"))
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------- 行为 ----------
    def _apply(self):
        text = self._mp_get_result_text()
        if self._win.apply_merged_text(text):
            self.close()

    def _save(self):
        text = self._mp_get_result_text()
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为合并结果", "",
            "Markdown 文件 (*.md);;文本文件 (*.txt);;所有文件 (*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text if text.endswith("\n") else text + "\n")
            self.stat_lbl.setText(f"已另存为：{os.path.basename(path)}")
        except OSError as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def showEvent(self, ev):
        super().showEvent(ev)
        self._apply_theme_qss(getattr(self._win, "_theme", "light"))


class TemplatePage(QWidget):
    """v3.36（TPL-E）：模板管理页（系统设置 → 模板，与外观 / 编辑器 / 通用同级）。

    统一管理全部模板（内置 + 自建）：左侧列表（顺序 = / 菜单「模板」二级的排列），
    右侧名称 + Markdown 内容编辑。「新建 / 删除 / 上移 / 下移 / 恢复内置」调整列表，
    改动即时写盘（templates.json）并下发编辑器 —— 文本类改动做 400ms 防抖，
    结构类改动立即落盘，不再需要「保存并生效」动作。
    删除不弹确认（项目约定：删除操作直接执行）。"""

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self._win = win
        self._templates = [dict(t) for t in getattr(win, "_custom_templates", []) or []]
        self._loading = False   # 程序性填充编辑框时抑制 _on_edited 回写
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save)
        self._build()
        self._fill_list(0 if self._templates else -1)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        title = QLabel("模板")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        hint = QLabel(
            "这里就是 / 菜单「模板」里的全部条目（内置 %d 个 + 你自建的），"
            "列表顺序即菜单顺序。内容为纯 Markdown，按空行分块插入；"
            "名称上限 %d 字（菜单里显示的就是它），同一名称只保留一个。\n"
            "改动即时生效并保存，关掉设置即已写盘。"
            % (len(BUILTIN_TEMPLATES), TPL_NAME_MAX), self)
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        body = QHBoxLayout()
        body.setSpacing(12)

        list_col = QVBoxLayout()
        list_col.addWidget(QLabel("模板列表", self))
        self.list_w = QListWidget(self)
        self.list_w.setObjectName("themeList")
        self.list_w.currentRowChanged.connect(self._on_row_changed)
        list_col.addWidget(self.list_w, 1)
        btn_row = QHBoxLayout()
        self.b_new = QPushButton("新建", self)
        self.b_del = QPushButton("删除", self)
        self.b_up = QPushButton("上移", self)
        self.b_down = QPushButton("下移", self)
        for b in (self.b_new, self.b_del, self.b_up, self.b_down):
            btn_row.addWidget(b)
        list_col.addLayout(btn_row)
        self.b_restore = QPushButton("恢复内置", self)
        self.b_restore.setToolTip(
            "把 %d 个内置模板按原始内容写回（同名覆盖、缺失追加），自建模板不受影响"
            % len(BUILTIN_TEMPLATES))
        list_col.addWidget(self.b_restore)
        body.addLayout(list_col, 1)

        edit_col = QVBoxLayout()
        edit_col.addWidget(QLabel("模板名称", self))
        self.name_edit = QLineEdit(self)
        self.name_edit.setMaxLength(TPL_NAME_MAX)   # v3.35：与菜单显示上限同源，输入层硬限
        self.name_edit.setPlaceholderText("（显示在菜单里的名字，必填，最多 %d 字）" % TPL_NAME_MAX)
        edit_col.addWidget(self.name_edit)
        edit_col.addWidget(QLabel("模板内容（Markdown，空行 = 插入时的分块边界）", self))
        self.content_edit = QPlainTextEdit(self)
        self.content_edit.setPlaceholderText("# 标题\n\n正文…")
        edit_col.addWidget(self.content_edit, 1)
        body.addLayout(edit_col, 2)
        lay.addLayout(body, 1)

        self.b_new.clicked.connect(self._on_new)
        self.b_del.clicked.connect(self._on_del)
        self.b_up.clicked.connect(lambda: self._on_move(-1))
        self.b_down.clicked.connect(lambda: self._on_move(1))
        self.b_restore.clicked.connect(self._on_restore)
        self.name_edit.textEdited.connect(self._on_edited)
        self.content_edit.textChanged.connect(self._on_edited)

    def showEvent(self, ev):
        """每次显示时回读 —— 模板可能被其它入口（侧栏「设为模板…」）改动过。"""
        super().showEvent(ev)
        self.reload()

    def reload(self):
        items = [dict(t) for t in getattr(self._win, "_custom_templates", []) or []]
        if items == self._templates:
            return
        self._templates = items
        self._fill_list(0 if items else -1)

    # ---- 列表与编辑框同步 ----
    def _label_of(self, t):
        """列表项显示文本：图标（若有）+ 名称。"""
        ic = str((t or {}).get("ic") or "").strip()
        return (ic + " " if ic else "") + str((t or {}).get("name") or "")

    def _fill_list(self, sel_row):
        """按 self._templates 重建列表并选中 sel_row（触发编辑框回填）。"""
        self._loading = True
        self.list_w.blockSignals(True)
        self.list_w.clear()
        for t in self._templates:
            it = QListWidgetItem(self._label_of(t))
            it.setToolTip(t["content"][:160])
            self.list_w.addItem(it)
        self.list_w.blockSignals(False)
        if 0 <= sel_row < self.list_w.count():
            self.list_w.setCurrentRow(sel_row)
        self._loading = False
        self._load_edit(self.list_w.currentRow())

    def _load_edit(self, row):
        self._loading = True
        if 0 <= row < len(self._templates):
            self.name_edit.setText(self._templates[row]["name"])
            self.content_edit.setPlainText(self._templates[row]["content"])
        else:
            self.name_edit.clear()
            self.content_edit.clear()
        self._loading = False

    def _on_row_changed(self, _row):
        if not self._loading:
            self._load_edit(self.list_w.currentRow())

    def _on_edited(self, *_):
        """编辑框输入实时回写当前模板（名称同步到列表项），并防抖落盘。"""
        if self._loading:
            return
        row = self.list_w.currentRow()
        if not (0 <= row < len(self._templates)):
            return
        name = self.name_edit.text().strip()
        if name:
            self._templates[row]["name"] = name
        self._templates[row]["content"] = self.content_edit.toPlainText()
        it = self.list_w.item(row)
        if it is not None and it.text() != self._label_of(self._templates[row]):
            it.setText(self._label_of(self._templates[row]))
        self._save_timer.start()   # 400ms 防抖：连续输入只在停笔后写一次盘

    # ---- 管理操作（结构类改动立即落盘） ----
    def _on_new(self):
        names = {t["name"] for t in self._templates}
        base, k = "新模板", 2
        name = base
        while name in names:
            name = f"{base}{k}"
            k += 1
        self._templates.append({"name": name, "content": f"# {name}\n\n"})
        self._fill_list(len(self._templates) - 1)
        self._save()
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _on_del(self):
        row = self.list_w.currentRow()
        if not (0 <= row < len(self._templates)):
            return
        del self._templates[row]
        self._fill_list(min(row, len(self._templates) - 1))
        self._save()

    def _on_move(self, delta):
        row = self.list_w.currentRow()
        new_row = row + delta
        if not (0 <= row < len(self._templates)) or not (0 <= new_row < len(self._templates)):
            return
        self._templates[row], self._templates[new_row] = \
            self._templates[new_row], self._templates[row]
        self._fill_list(new_row)
        self._save()

    def _on_restore(self):
        """恢复内置模板：同名覆盖为原始内容，缺失的追加到末尾（自建模板不动）。"""
        idx = dict((t["name"], k) for k, t in enumerate(self._templates))
        added = 0
        for b in BUILTIN_TEMPLATES:
            ent = {"name": b["name"], "content": b["content"], "ic": b.get("ic", "")}
            if b["name"] in idx:
                self._templates[idx[b["name"]]] = ent
            else:
                self._templates.append(ent)
                added += 1
        self._fill_list(0)
        self._save()
        self._win.show_status("内置模板已恢复（%d 个%s）"
                              % (len(BUILTIN_TEMPLATES), "，新增 %d 个" % added if added else ""))

    def _save(self):
        """写盘 + 下发编辑器（文本改动经防抖触发，结构改动直接调用）。"""
        self._save_timer.stop()
        items = [dict(t) for t in self._templates]
        self._win.save_custom_templates(items)
        saved = [dict(t) for t in getattr(self._win, "_custom_templates", []) or []]
        if len(saved) != len(items):
            # 归一化丢弃了无效项（空名 / 重名 / 空内容）—— 列表回读真实存盘结果
            self._templates = saved
            self._fill_list(min(self.list_w.currentRow(), len(saved) - 1))
