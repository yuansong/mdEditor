# -*- coding: utf-8 -*-
"""v3.31.2 批次补丁 A：sidebar.py 删除树形目录方法区段，替换为文件页管理操作。
用法：python tests/_patch_v332_b.py  （幂等：标记行数 != 1 时拒绝执行）"""
import io, sys

P = r"E:\WorkBuddy\md-editor\src\sidebar.py"
MARK = "    # ================= v3.31（#5）树形文件目录 ================="

NEW = '''    # ================= v3.31.2 文件页管理操作（自「目录」页迁入） =================
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
                f.write("# " + os.path.splitext(name)[0] + "\\n\\n")
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
        if os.path.abspath(p) == os.path.abspath(self._cur_file or ""):
            self._cur_file = np
        self._refresh_files()

    def _file_delete(self, p):
        is_cur = p == getattr(self._win, "file_path", None)
        tip = ("\\n注意：这是当前正在编辑的文件，删除后请不要再保存该标签\\n"
               "（否则会以原内容重建同名文件）。") if is_cur else ""
        if QMessageBox.question(self, "删除确认",
                                f"确定把\\n{p}\\n移入回收站吗？{tip}",
                                QMessageBox.Ok | QMessageBox.Cancel) != QMessageBox.Ok:
            return
        if self._win.recycle_path(p):
            self._refresh_files()
            self._win.show_status("已移入回收站：" + p)
'''

with io.open(P, "r", encoding="utf-8") as f:
    src = f.read()
n = src.count(MARK)
if n != 1:
    sys.exit("ABORT: marker count=%d (expect 1)" % n)
head = src[:src.index(MARK)]
with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(head + NEW)
print("OK: tree section replaced,", len(NEW.splitlines()), "lines written")
