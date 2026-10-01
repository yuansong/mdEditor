# -*- coding: utf-8 -*-
"""对话框组件：查找 / 替换、快捷键设置、系统设置、命令面板、版本历史。"""
import difflib
import json
import logging
import os
import re
from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
    QKeySequenceEdit, QRadioButton, QSlider, QSpinBox, QStackedWidget, QTabWidget,
    QTextBrowser, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from config import BUILTIN_TEMPLATES, MMD_LEGACY, MMD_THEMES, TPL_NAME_MAX, js
from sidebar import GlobalSearchPanel
from styles import THEMES, dialog_qss, palette

# 斜杠（/）菜单可配置项（与 editor.html 中 SLASH_DEFS 对应）
# v3.30.3：移除「上标 / 下标」（supsub）一级项
# v3.31.3：footnote / deflist 合并为 refs「脚注与定义」
# v3.32（P1-1）：新增 tpl「模板」一级项
MENU_ITEMS = [("heading", "标题"), ("list", "列表"), ("table", "表格"), ("code", "代码块"),
              ("hr", "分隔线"), ("quote", "引用"), ("image", "图片"), ("chart", "图表"),
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
        self.setStyleSheet(dialog_qss(theme_id))


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
        self.setMinimumWidth(560)
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

        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("countLbl")
        # v3.29b：提示行独立于搜索框行（初始隐藏），位于搜索框之下、结果列表之上
        self.count_lbl.setVisible(False)

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

        # ---- 状态行：范围在左、统计在右（v3.29：与当前文件查找同页常显）----
        status_row = QHBoxLayout()
        status_row.setContentsMargins(2, 0, 2, 0)
        status_row.setSpacing(8)
        status_row.addWidget(self.search_panel.search_scope, 1)
        status_row.addWidget(self.search_panel.search_info, 0)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        lay.addLayout(row1)
        lay.addWidget(self.replace_row)
        # v3.29b：「未找到匹配内容 / 共 N 处匹配」提示行 —— 搜索框之下、结果列表之上
        lay.addWidget(self.count_lbl)
        lay.addLayout(status_row)
        lay.addWidget(self.search_panel.search_ext)
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
        self.count_lbl.setVisible(True)
        self.search_panel.search_scope.setVisible(True)
        self.search_panel.search_info.setVisible(True)
        self.search_panel.search_ext.setVisible(True)
        self.search_panel.search_tree.setVisible(True)
        self.setWindowTitle("查找 / 替换" if self._replace_mode else "查找")
        if not glob:
            self.find_edit.setFocus()
        self.adjustSize()

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
        self.adjustSize()

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
        self.count_lbl.setVisible(True)
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
    """系统设置：Typedown 式左侧导航（外观 / 编辑器 / 通用），设置即时生效。"""

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
        # v3.36（TPL-E）：模板管理提升为一级页「模板」（与外观 / 编辑器 / 通用同级）
        for name in ("外观", "编辑器", "通用", "模板"):
            QListWidgetItem(name, self.nav)
        self.nav.setCurrentRow(0)

        # ---- 右侧页面 ----
        self.pages = QStackedWidget(self)
        self.pages.addWidget(self._page_appearance())
        self.pages.addWidget(self._page_editor_fmt())
        self.pages.addWidget(self._page_general())
        self.pages.addWidget(TemplatePage(win, self))
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
    def _page_appearance(self):
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("外观")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        hint = QLabel("选择主题（即时生效，自动记住）；拖动滑块调整编辑区显示字号；下方可另选图表主题。")
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        lay.addWidget(QLabel("主题"))
        self.theme_list = QListWidget(page)
        self.theme_list.setObjectName("themeList")
        for t in THEMES:
            QListWidgetItem(f"●  {t['label']}", self.theme_list)
        cur = getattr(self._win, "_theme", "light")
        ids = [t["id"] for t in THEMES]
        self.theme_list.setCurrentRow(ids.index(cur) if cur in ids else 0)
        self.theme_list.itemClicked.connect(self._on_theme_clicked)
        lay.addWidget(self.theme_list, 1)

        lay.addWidget(QLabel("编辑区字号缩放"))
        zrow = QHBoxLayout()
        self.zoom_slider = QSlider(Qt.Horizontal, page)
        self.zoom_slider.setRange(80, 160)
        self.zoom_slider.setValue(int(round(getattr(self._win, "_zoom", 1.0) * 100)))
        self.zoom_lbl = QLabel(f"{self.zoom_slider.value()}%")
        self.zoom_lbl.setMinimumWidth(44)
        self.zoom_slider.valueChanged.connect(self._on_zoom)
        zrow.addWidget(self.zoom_slider, 1)
        zrow.addWidget(self.zoom_lbl)
        lay.addLayout(zrow)

        # v3.34（MMD-11）：图表（mermaid）主题 —— 原「视图 → 图表主题」菜单移入此处，
        # 与界面主题同页集中配置；与图表块右键「图表主题」子菜单共用 QSettings.mmdTheme
        lay.addWidget(QLabel("图表主题"))
        self.mmd_box = QComboBox(page)
        for label, val in MMD_THEMES:
            self.mmd_box.addItem(label, val)
        _cur_mmd = MMD_LEGACY.get(self._win._settings.value("mmdTheme", "") or "",
                                  self._win._settings.value("mmdTheme", "") or "")
        _ids = [v for _l, v in MMD_THEMES]
        self.mmd_box.setCurrentIndex(_ids.index(_cur_mmd) if _cur_mmd in _ids else 0)
        self.mmd_box.currentIndexChanged.connect(self._on_mmd_theme)
        lay.addWidget(self.mmd_box)
        mmd_hint = QLabel("图表主题对所有 mermaid 图表即时生效（含右键图表块直接切换）；"
                          "「跟随界面主题」会随深 / 浅色界面自动切换。")
        mmd_hint.setObjectName("pageHint")
        mmd_hint.setWordWrap(True)
        lay.addWidget(mmd_hint)
        return page

    def _on_mmd_theme(self, _idx=0):
        self._win._set_mmd_theme(self.mmd_box.currentData() or "")

    def _on_theme_clicked(self, item):
        t = THEMES[self.theme_list.row(item)]
        self._win.apply_theme(t["id"])

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
        v.setContentsMargins(14, 8, 14, 12)
        v.setSpacing(8)
        return gb, v

    def _page_editor_fmt(self):
        """v3.29：「编辑器」页 —— 图片 / 代码块 / 斜杠菜单（原编辑器页后半部分）。
        v3.29b：三组设置各归入一个组框（QGroupBox）。"""
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("编辑器")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        # ---- v3.31.2（#8/#9）：段落与标题（组框） ----
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

        # ---- v3.25 代码块行号 / 代码风格 ----
        crow = QHBoxLayout()
        self.code_lnum_box = QCheckBox("代码块显示行号", page)
        self.code_lnum_box.setChecked(bool(getattr(self._win, "_code_lnum", True)))
        self.code_lnum_box.toggled.connect(self._on_code_lnum)
        crow.addWidget(self.code_lnum_box)
        crow.addWidget(QLabel("代码风格"))
        self.code_style_box = QComboBox(page)
        for _sid, _slabel in (("classic", "经典"), ("dark", "深色"),
                              ("eye", "护眼"), ("mini", "极简")):
            self.code_style_box.addItem(_slabel, _sid)
        _cidx = self.code_style_box.findData(str(getattr(self._win, "_code_style", "classic")))
        self.code_style_box.setCurrentIndex(_cidx if _cidx >= 0 else 0)
        self.code_style_box.currentIndexChanged.connect(self._on_code_style)
        crow.addWidget(self.code_style_box, 1)
        gcode.addLayout(crow)
        code_hint = QLabel("· 新插入 / 重新渲染的代码块使用以上默认配置\n"
                           "· 代码块顶部语言栏的「风格」按钮可对单个代码块临时切换")
        code_hint.setObjectName("pageHint")
        code_hint.setWordWrap(True)
        gcode.addWidget(code_hint)
        lay.addWidget(gb_code)

        # ---- 斜杠（/）菜单（组框） ----
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
        if int(getattr(self._win, "_history_keep", 20) or 20) != int(n):
            self._win.set_history_keep(int(n))

    # ---- 通用页：侧栏显示设置 ----
    def _on_outline_level(self, _idx):
        lvl = self.outline_level_box.currentData()
        if lvl is not None and int(lvl) != int(getattr(self._win, "_outline_level", 3)):
            self._win.set_outline_level(int(lvl))

    def _on_file_mode(self, _idx):
        mode = self.file_mode_box.currentData()
        if mode and mode != getattr(self._win, "_file_list_mode", "current"):
            self._win.set_file_list_mode(mode)

    def _on_pandoc_path(self):
        self._win.set_pandoc_path(self.pandoc_edit.text())

    def _on_external_editor(self):
        self._win.set_external_editor(self.extedit_edit.text())

    # ================= 通用 =================
    def _page_general(self):
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("通用")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        # ---- 文件与启动（组框；组框标题即分类描述） ----
        gb_file, gfile = self._group("文件与启动")
        self.autosave_box = QCheckBox("自动保存（编辑后自动写入文件）", page)
        self.autosave_box.setChecked(bool(getattr(self._win, "_autosave", True)))
        self.autosave_box.toggled.connect(self._win.set_autosave)
        gfile.addWidget(self.autosave_box)

        # ---- 大纲显示级别 ----
        orow = QHBoxLayout()
        orow.addWidget(QLabel("大纲显示级别（超过该级别的标题默认折叠）"))
        self.outline_level_box = QComboBox(page)
        for n in range(1, 7):
            self.outline_level_box.addItem(f"{n} 级", n)
        self.outline_level_box.setCurrentIndex(
            max(0, int(getattr(self._win, "_outline_level", 3)) - 1))
        self.outline_level_box.currentIndexChanged.connect(self._on_outline_level)
        orow.addWidget(self.outline_level_box, 1)
        gfile.addLayout(orow)

        # ---- v3.31.2（#3）：大纲分节字数后缀开关 ----
        self.outline_words_box = QCheckBox("大纲显示分节字数（标题后追加「· N 字」）", page)
        self.outline_words_box.setChecked(bool(getattr(self._win, "_outline_words", False)))
        self.outline_words_box.toggled.connect(self._win.set_outline_words)
        gfile.addWidget(self.outline_words_box)

        # ---- 文件列表显示模式（v3.26 语义澄清：指未选择文件 / 文件夹时的初始状态）----
        lrow = QHBoxLayout()
        lrow.addWidget(QLabel("启动时文件列表"))
        self.file_mode_box = QComboBox(page)
        self.file_mode_box.addItem("跟随当前文档（未打开文档时显示空白）", "current")
        self.file_mode_box.addItem("始终空白（不自动显示内容）", "blank")
        _fm = "blank" if getattr(self._win, "_file_list_mode", "current") == "blank" else "current"
        idx = self.file_mode_box.findData(_fm)
        self.file_mode_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.file_mode_box.currentIndexChanged.connect(self._on_file_mode)
        lrow.addWidget(self.file_mode_box, 1)
        gfile.addLayout(lrow)
        fm_hint = QLabel("· 指尚未选择文件 / 文件夹时的显示状态\n"
                         "· 打开或选择了文件夹后，文件列表始终按该文件夹现有策略显示")
        fm_hint.setObjectName("pageHint")
        fm_hint.setWordWrap(True)
        gfile.addWidget(fm_hint)
        lay.addWidget(gb_file)

        # ---- 导出（组框） ----
        gb_exp, gexp = self._group("导出")
        gexp.addWidget(QLabel("Pandoc 路径（导出 Word / EPUB 时优先使用；留空 = 自动探测 PATH）"))
        self.pandoc_edit = QLineEdit(page)
        self.pandoc_edit.setPlaceholderText("留空 = 自动探测；未安装 pandoc 时使用内置转换")
        self.pandoc_edit.setText(str(getattr(self._win, "_pandoc_path", "") or ""))
        self.pandoc_edit.editingFinished.connect(self._on_pandoc_path)
        gexp.addWidget(self.pandoc_edit)

        # ---- P1-7 外部编辑器路径（可选）----
        gexp.addWidget(QLabel("外部编辑器（侧栏文件列表右键「用外部程序打开」使用；留空 = 系统默认程序）"))
        self.extedit_edit = QLineEdit(page)
        self.extedit_edit.setPlaceholderText("留空 = 系统默认关联程序（可填 Notepad++ / VS Code 等可执行文件）")
        self.extedit_edit.setText(str(getattr(self._win, "_external_editor", "") or ""))
        self.extedit_edit.editingFinished.connect(self._on_external_editor)
        gexp.addWidget(self.extedit_edit)
        lay.addWidget(gb_exp)

        # ---- v3.29：写作模式（原「写作与历史」页并入；组框化） ----
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

        # ---- v3.29：输入辅助（P1-1 / P1-8 输入增强；组框化）----
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

        # ---- v3.29：版本历史（P1-6 历史版本保留份数；组框化）----
        gb_hist, ghist = self._group("版本历史")
        histrow = QHBoxLayout()
        histrow.addWidget(QLabel("历史版本保留份数（保存前留档，超出自动清理）"))
        self.history_keep_box = QSpinBox(page)
        self.history_keep_box.setRange(1, 200)
        self.history_keep_box.setSuffix(" 份")
        self.history_keep_box.setValue(int(getattr(self._win, "_history_keep", 20) or 20))
        self.history_keep_box.valueChanged.connect(self._on_history_keep)
        histrow.addWidget(self.history_keep_box, 1)
        ghist.addLayout(histrow)
        lay.addWidget(gb_hist)

        note = QLabel(
            "· 主题、字号与快捷键设置已自动保存，重启后保持\n"
            "· 文档通过左侧「文件」列表浏览，拖拽 .md 文件到窗口即可打开\n"
            "· 未安装 pandoc 也能导出 Word / EPUB（内置转换，公式与图表降级为源码）")
        note.setObjectName("pageHint")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch(1)
        return page

    def showEvent(self, ev):
        super().showEvent(ev)
        # 打开时同步主窗口当前状态
        self._apply_theme_qss(getattr(self._win, "_theme", "light"))
        ids = [t["id"] for t in THEMES]
        cur = getattr(self._win, "_theme", "light")
        self.theme_list.blockSignals(True)
        self.theme_list.setCurrentRow(ids.index(cur) if cur in ids else 0)
        self.theme_list.blockSignals(False)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(int(round(getattr(self._win, "_zoom", 1.0) * 100)))
        self.zoom_slider.blockSignals(False)
        self.zoom_lbl.setText(f"{self.zoom_slider.value()}%")
        self.autosave_box.blockSignals(True)
        self.autosave_box.setChecked(bool(getattr(self._win, "_autosave", True)))
        self.autosave_box.blockSignals(False)
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
        # P1-6 / P1-7：历史保留份数、外部编辑器路径同步
        self.history_keep_box.blockSignals(True)
        self.history_keep_box.setValue(int(getattr(self._win, "_history_keep", 20) or 20))
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
            self.hint.setText("输入关键词（汉字 / 拼音首字母 / 快捷键）筛选命令 · Esc 关闭")
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
    """v3.31（#27）：版本差异对比视图（行级差异高亮，随主题配色）。

    用 difflib.SequenceMatcher 逐行比对，新增行 / 删除行分别着色，
    上下文行淡色；QTextBrowser 展示静态 HTML，零外部依赖。"""

    MAX_ROWS = 4000   # 超长差异截断，避免 HTML 过大卡界面

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("diffDlg")
        self.setWindowTitle("版本对比")
        self.setModal(False)
        self.resize(860, 560)
        self._apply_theme_qss(getattr(win, "_theme", "light"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(8)
        self.title_lbl = QLabel("", self)
        self.title_lbl.setObjectName("pageTitle")
        lay.addWidget(self.title_lbl)
        self.stat_lbl = QLabel("", self)
        self.stat_lbl.setObjectName("pageHint")
        lay.addWidget(self.stat_lbl)
        self.view = QTextBrowser(self)
        self.view.setOpenExternalLinks(False)
        lay.addWidget(self.view, 1)
        brow = QHBoxLayout()
        brow.addStretch(1)
        b_close = QPushButton("关闭", self)
        b_close.clicked.connect(self.close)
        brow.addWidget(b_close)
        lay.addLayout(brow)

    def show_diff(self, title, old_text, new_text, old_label, new_label):
        self.title_lbl.setText(title)
        theme = getattr(self._win, "_theme", "light")
        dark = theme in ("dark", "night", "panda")
        c_add = "#1e3b2a" if dark else "#e2f6e9"
        c_del = "#3f2222" if dark else "#fde8e8"
        try:
            c_ctx = palette(theme).get("text_muted", "#6b7280")
        except Exception:      # noqa: BLE001
            c_ctx = "#6b7280"
        old_lines = str(old_text or "").split("\n")
        new_lines = str(new_text or "").split("\n")
        sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        add = dele = same = 0
        rows = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for ln in old_lines[i1:i2]:
                    rows.append(("ctx", ln))
                same += i2 - i1
            else:
                for ln in old_lines[i1:i2]:
                    rows.append(("del", ln))
                dele += i2 - i1
                for ln in new_lines[j1:j2]:
                    rows.append(("add", ln))
                add += j2 - j1
        if add == 0 and dele == 0:
            self.stat_lbl.setText("两个版本内容一致。")
            self.view.setPlainText("")
        else:
            self.stat_lbl.setText(
                f"新增 {add} 行 · 删除 {dele} 行 · 相同 {same} 行　（{old_label} → {new_label}）")
            parts = ['<div style="font-family: Consolas, monospace; font-size: 12px; line-height: 1.5;">']
            for kind, ln in rows[:self.MAX_ROWS]:
                escd = (ln.replace("&", "&amp;").replace("<", "&lt;")
                          .replace(">", "&gt;").replace(" ", "&nbsp;") or "&nbsp;")
                if kind == "add":
                    parts.append(f'<div style="background:{c_add};">{escd}</div>')
                elif kind == "del":
                    parts.append(f'<div style="background:{c_del};">{escd}</div>')
                else:
                    parts.append(f'<div style="color:{c_ctx};">{escd}</div>')
            if len(rows) > self.MAX_ROWS:
                parts.append(f'<div style="color:{c_ctx};">… 其余 {len(rows) - self.MAX_ROWS} 行省略</div>')
            parts.append("</div>")
            self.view.setHtml("".join(parts))
        self.show()
        self.raise_()
        self.activateWindow()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._apply_theme_qss(getattr(self._win, "_theme", "light"))


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
        row.addWidget(self.listw, 0)
        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("（选择左侧快照查看内容）")
        row.addWidget(self.preview, 1)
        lay.addLayout(row, 1)

        brow = QHBoxLayout()
        brow.addStretch(1)
        # v3.31（#27）：版本差异对比
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
        else:
            self.b_restore.setEnabled(True)
            self.b_folder.setEnabled(True)
            self.b_diff_cur.setEnabled(True)
            self.b_diff_prev.setEnabled(len(self._items) >= 2)
            for fp, mt in self._items:
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    size = 0
                self.listw.addItem(QListWidgetItem(
                    f"{datetime.fromtimestamp(mt).strftime('%Y-%m-%d %H:%M:%S')}    {size} 字节"))
            self.listw.setCurrentRow(0)
        self.listw.blockSignals(False)
        self._on_pick(self.listw.currentRow())
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
