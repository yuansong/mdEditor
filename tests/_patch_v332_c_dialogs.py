# -*- coding: utf-8 -*-
"""v3.32 dialogs.py 补丁：#27 版本 diff 视图 + #18/#19 查找全部命中面板。幂等。"""
import io
import sys

P = r"E:\WorkBuddy\md-editor\src\dialogs.py"
src = io.open(P, encoding="utf-8").read()

EDITS = []


def rep(old, new, n=1):
    EDITS.append((old, new, n))


# ---- D1) difflib import ----
rep("""import json
import logging
import os
import re
from datetime import datetime""",
    """import difflib
import json
import logging
import os
import re
from datetime import datetime""")

# ---- D2) QTextBrowser import ----
rep("""    QKeySequenceEdit, QRadioButton, QSlider, QSpinBox, QStackedWidget, QTabWidget,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)""",
    """    QKeySequenceEdit, QRadioButton, QSlider, QSpinBox, QStackedWidget, QTabWidget,
    QTextBrowser, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)""")

# ---- D3) palette import ----
rep("from styles import THEMES, dialog_qss",
    "from styles import THEMES, dialog_qss, palette")

# ---- D4) DiffDialog 类 ----
rep("""class HistoryDialog(_ThemedDialog):
    \"\"\"版本历史：列出保存时留下的快照，可预览并恢复。\"\"\"""",
    '''class DiffDialog(_ThemedDialog):
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
        old_lines = str(old_text or "").split("\\n")
        new_lines = str(new_text or "").split("\\n")
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
    """版本历史：列出保存时留下的快照，可预览、对比并恢复。"""''')

# ---- D5) diff 按钮 ----
rep("""        brow = QHBoxLayout()
        brow.addStretch(1)
        self.b_restore = QPushButton("恢复此版本", self)""",
    """        brow = QHBoxLayout()
        brow.addStretch(1)
        # v3.31（#27）：版本差异对比
        self.b_diff_prev = QPushButton("与上一版本对比", self)
        self.b_diff_prev.clicked.connect(self._diff_prev)
        self.b_diff_cur = QPushButton("与当前文档对比", self)
        self.b_diff_cur.clicked.connect(self._diff_current)
        self.b_restore = QPushButton("恢复此版本", self)""")

rep("""        brow.addWidget(self.b_restore)
        brow.addWidget(self.b_folder)
        brow.addWidget(b_close)""",
    """        brow.addWidget(self.b_diff_prev)
        brow.addWidget(self.b_diff_cur)
        brow.addWidget(self.b_restore)
        brow.addWidget(self.b_folder)
        brow.addWidget(b_close)""")

rep("""        if not self._items:
            self.listw.addItem(QListWidgetItem("（暂无历史版本）"))
            self.b_restore.setEnabled(False)
            self.b_folder.setEnabled(False)
        else:
            self.b_restore.setEnabled(True)
            self.b_folder.setEnabled(True)""",
    """        if not self._items:
            self.listw.addItem(QListWidgetItem("（暂无历史版本）"))
            self.b_restore.setEnabled(False)
            self.b_folder.setEnabled(False)
            self.b_diff_cur.setEnabled(False)
            self.b_diff_prev.setEnabled(False)
        else:
            self.b_restore.setEnabled(True)
            self.b_folder.setEnabled(True)
            self.b_diff_cur.setEnabled(True)
            self.b_diff_prev.setEnabled(len(self._items) >= 2)""")

# ---- D6) diff 方法 ----
rep("""    def _restore(self):
        row = self.listw.currentRow()
        if row < 0 or row >= len(self._items):
            return
        self._win.restore_history(self._items[row][0], self._items[row][1])""",
    """    @staticmethod
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
        \"\"\"v3.31（#27）：所选快照 vs 当前编辑区内容。\"\"\"
        row = self.listw.currentRow()
        old = self._snap_text(row)
        if old is None:
            return
        name = os.path.basename(self._cur_file) if self._cur_file else "（未保存文档）"
        self._ensure_diff_dlg().show_diff(
            f"版本对比 · {name}", old, self._current_text(),
            f"快照 {self._fmt_when(self._items[row][1])}", "当前文档")

    def _diff_prev(self):
        \"\"\"v3.31（#27）：所选快照 vs 更新一份的快照（列表按时间倒序，row-1 更新）。\"\"\"
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
        self._win.restore_history(self._items[row][0], self._items[row][1])""")

# ---- D7) FindDialog：命中列表点击 + findAll 接线 ----
rep("""        self.find_edit.returnPressed.connect(lambda: self._run("findNext"))""",
    """        # v3.31（#19）：当前文件命中列表点击跳转
        # （GlobalSearchPanel 自己的 itemClicked 处理器对未知标签直接忽略，互不冲突）
        self.search_panel.search_tree.itemClicked.connect(self._on_cfile_click)
        self.find_edit.returnPressed.connect(lambda: self._run("findNext"))""")

rep("""        # 默认正则、不区分大小写（正则无效时编辑器内自动回退普通文本）
        self._win._js_active(
            f"window.find({js(action)}, {js(q)}, false, true, {js(self.replace_edit.text())})",
            self._on_result)""",
    """        # 默认正则、不区分大小写（正则无效时编辑器内自动回退普通文本）
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
                f"window.findAll({js(q)}, false, true, 500)", self._on_findall)""")

# ---- D8) _on_findall / _on_cfile_click / close-hide 清高亮 ----
rep("""    def _on_result(self, res):""",
    '''    def _on_findall(self, res):
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

    def _on_result(self, res):''')

fail = [i for i, (o, nw, n) in enumerate(EDITS) if src.count(o) != n]
if fail:
    for i in fail:
        print("ANCHOR FAIL #%d count=%d" % (i, src.count(EDITS[i][0])))
    sys.exit(1)
for o, nw, _n in EDITS:
    src = src.replace(o, nw)

io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("dialogs.py patched: %d edits" % len(EDITS))
