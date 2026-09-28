# -*- coding: utf-8 -*-
"""v3.23 设置界面补入口：版本历史保留份数 + 外部编辑器路径（原本只能改配置文件）。

每处替换都要求「恰好命中 1 次」，否则全部放弃、不写任何文件。
运行一次即可，之后可删除本脚本。
"""
import io
import os

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")

EDITS = {}

EDITS["dialogs.py"] = [
    (
        "    QListWidgetItem, QPlainTextEdit, QPushButton, QKeySequenceEdit, QSlider,\n"
        "    QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,\n",
        "    QListWidgetItem, QPlainTextEdit, QPushButton, QKeySequenceEdit, QSlider,\n"
        "    QSpinBox, QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,\n",
    ),
    (
        '        self.emoji_box.toggled.connect(self._on_emoji)\n'
        '        lay.addWidget(self.emoji_box)\n',
        '        self.emoji_box.toggled.connect(self._on_emoji)\n'
        '        lay.addWidget(self.emoji_box)\n'
        '\n'
        '        # ---- P1-6 版本历史保留份数 ----\n'
        '        histrow = QHBoxLayout()\n'
        '        histrow.addWidget(QLabel("历史版本保留份数（保存前留档，超出自动清理）"))\n'
        '        self.history_keep_box = QSpinBox(page)\n'
        '        self.history_keep_box.setRange(1, 200)\n'
        '        self.history_keep_box.setSuffix(" 份")\n'
        '        self.history_keep_box.setValue(int(getattr(self._win, "_history_keep", 20) or 20))\n'
        '        self.history_keep_box.valueChanged.connect(self._on_history_keep)\n'
        '        histrow.addWidget(self.history_keep_box, 1)\n'
        '        lay.addLayout(histrow)\n',
    ),
    (
        '    def _on_emoji(self, on):\n'
        '        if bool(getattr(self._win, "_emoji", True)) != on:\n'
        '            self._win.set_emoji_complete(on)\n',
        '    def _on_emoji(self, on):\n'
        '        if bool(getattr(self._win, "_emoji", True)) != on:\n'
        '            self._win.set_emoji_complete(on)\n'
        '\n'
        '    def _on_history_keep(self, n):\n'
        '        if int(getattr(self._win, "_history_keep", 20) or 20) != int(n):\n'
        '            self._win.set_history_keep(int(n))\n',
    ),
    (
        "        self.pandoc_edit.editingFinished.connect(self._on_pandoc_path)\n"
        "        lay.addWidget(self.pandoc_edit)\n",
        "        self.pandoc_edit.editingFinished.connect(self._on_pandoc_path)\n"
        "        lay.addWidget(self.pandoc_edit)\n"
        "\n"
        "        # ---- P1-7 外部编辑器路径（可选）----\n"
        '        lay.addWidget(QLabel("外部编辑器（「文件 → 用外部程序打开」使用；留空 = 系统默认程序）"))\n'
        "        self.extedit_edit = QLineEdit(page)\n"
        '        self.extedit_edit.setPlaceholderText("留空 = 系统默认关联程序（可填 Notepad++ / VS Code 等可执行文件）")\n'
        '        self.extedit_edit.setText(str(getattr(self._win, "_external_editor", "") or ""))\n'
        "        self.extedit_edit.editingFinished.connect(self._on_external_editor)\n"
        "        lay.addWidget(self.extedit_edit)\n",
    ),
    (
        "    def _on_pandoc_path(self):\n"
        "        self._win.set_pandoc_path(self.pandoc_edit.text())\n",
        "    def _on_pandoc_path(self):\n"
        "        self._win.set_pandoc_path(self.pandoc_edit.text())\n"
        "\n"
        "    def _on_external_editor(self):\n"
        "        self._win.set_external_editor(self.extedit_edit.text())\n",
    ),
    (
        '        self.pandoc_edit.blockSignals(True)\n'
        '        self.pandoc_edit.setText(str(getattr(self._win, "_pandoc_path", "") or ""))\n'
        '        self.pandoc_edit.blockSignals(False)\n',
        '        self.pandoc_edit.blockSignals(True)\n'
        '        self.pandoc_edit.setText(str(getattr(self._win, "_pandoc_path", "") or ""))\n'
        '        self.pandoc_edit.blockSignals(False)\n'
        '        # P1-6 / P1-7：历史保留份数、外部编辑器路径同步\n'
        '        self.history_keep_box.blockSignals(True)\n'
        '        self.history_keep_box.setValue(int(getattr(self._win, "_history_keep", 20) or 20))\n'
        '        self.history_keep_box.blockSignals(False)\n'
        '        self.extedit_edit.blockSignals(True)\n'
        '        self.extedit_edit.setText(str(getattr(self._win, "_external_editor", "") or ""))\n'
        '        self.extedit_edit.blockSignals(False)\n',
    ),
]

EDITS["mainwindow.py"] = [
    (
        '    def set_emoji_complete(self, on):\n'
        '        """Emoji 短代码自动补全开关。"""\n'
        '        self._emoji = bool(on)\n'
        '        self._settings.setValue("emojiComplete", bool(on))\n'
        '        self._js_active(f"window.setMode({{emoji: {str(bool(on)).lower()}}})")\n'
        '        self._status.setText("Emoji 补全：开" if on else "Emoji 补全：关")\n',
        '    def set_emoji_complete(self, on):\n'
        '        """Emoji 短代码自动补全开关。"""\n'
        '        self._emoji = bool(on)\n'
        '        self._settings.setValue("emojiComplete", bool(on))\n'
        '        self._js_active(f"window.setMode({{emoji: {str(bool(on)).lower()}}})")\n'
        '        self._status.setText("Emoji 补全：开" if on else "Emoji 补全：关")\n'
        '\n'
        '    def set_history_keep(self, n):\n'
        '        """历史版本保留份数（1~200，系统设置→编辑器）。"""\n'
        '        try:\n'
        '            n = max(1, min(200, int(n)))\n'
        '        except (TypeError, ValueError):\n'
        '            return\n'
        '        self._history_keep = n\n'
        '        self._settings.setValue("historyKeep", n)\n'
        '        self._status.setText(f"历史版本保留 {n} 份")\n'
        '\n'
        '    def set_external_editor(self, path):\n'
        '        """外部编辑器可执行文件路径（留空 = 系统默认关联程序，系统设置→通用）。"""\n'
        '        self._external_editor = str(path or "").strip()\n'
        '        self._settings.setValue("externalEditor", self._external_editor)\n'
        '        self._status.setText("外部编辑器：" + (self._external_editor or "系统默认程序"))\n',
    ),
]


def main():
    planned = []
    for name, edits in EDITS.items():
        path = os.path.join(root, name)
        with io.open(path, "r", encoding="utf-8") as f:
            text = f.read()
        for old, new in edits:
            n = text.count(old)
            if n != 1:
                raise SystemExit("ABORT %s: 命中 %d 次（应为 1）\n---\n%s" % (name, n, old[:200]))
            text = text.replace(old, new, 1)
        planned.append((path, text))
    for path, text in planned:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print("patched", os.path.basename(path))
    print("ALL PATCHED")


if __name__ == "__main__":
    main()
