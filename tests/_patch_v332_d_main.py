# -*- coding: utf-8 -*-
"""v3.32 mainwindow.py 补丁：#5 目录树接线（回收站 / 改名同步 / 菜单项）+ #7 调序桥。幂等。"""
import io
import sys

P = r"E:\WorkBuddy\md-editor\src\mainwindow.py"
src = io.open(P, encoding="utf-8").read()

EDITS = []


def rep(old, new, n=1):
    EDITS.append((old, new, n))


# ---- M1) 视图菜单加「文件目录」 ----
rep("""        self._reg_act("视图", "大纲", "Ctrl+Shift+O", lambda: self._show_sidebar_tab(1), menu=m_view)""",
    """        self._reg_act("视图", "大纲", "Ctrl+Shift+O", lambda: self._show_sidebar_tab(1), menu=m_view)
        self._reg_act("视图", "文件目录", None, lambda: self._show_sidebar_tab(2), menu=m_view)   # v3.31（#5）""")

# ---- M2) 标签激活 / 另存为时目录树跟随 ----
rep("""        if self.file_path:
            self._sidebar.set_root(self.file_path)
            self._status.setText(f"已打开 · {self.file_path}")""",
    """        if self.file_path:
            self._sidebar.set_root(self.file_path)
            self._sidebar.tree_follow(self.file_path)   # v3.31（#5）：目录树跟随 / 高亮
            self._status.setText(f"已打开 · {self.file_path}")""")

rep("""        self._remember_dir("save", path)
        self.file_path = os.path.abspath(path)""",
    """        self._remember_dir("save", path)
        self.file_path = os.path.abspath(path)
        self._sidebar.tree_follow(self.file_path)   # v3.31（#5）：目录树跟随 / 高亮""")

# ---- M3) recycle_path / rename_current_file / reorder_sections ----
rep("""        self._push_text(text)
        self._dirty = True
        self._update_title()
        self.show_status(f"已恢复历史版本（{when}）· 按 Ctrl+S 保存")""",
    """        self._push_text(text)
        self._dirty = True
        self._update_title()
        self.show_status(f"已恢复历史版本（{when}）· 按 Ctrl+S 保存")

    # ================= v3.31（#5）目录树支撑 =================
    def recycle_path(self, path):
        \"\"\"把文件 / 文件夹移入回收站（SHFileOperationW，FOF_ALLOWUNDO）。\"\"\"
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
        op.pFrom = path + "\\0"
        op.pTo = None
        op.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400  # ALLOWUNDO|NOCONFIRMATION|SILENT|NOERRORUI
        try:
            rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        except (OSError, AttributeError):
            return False
        return rc == 0 and not op.fAnyOperationsAborted

    def rename_current_file(self, old, new):
        \"\"\"侧栏把当前打开的文件改名后同步内部状态（保存路径 / 标签 / 标题）。\"\"\"
        if old and self.file_path and \\
                os.path.abspath(self.file_path) == os.path.abspath(old):
            self.file_path = new
            if 0 <= self._cur < len(self._docs):
                self._docs[self._cur]["path"] = new
            self._refresh_tab_texts()
            self._update_title()

    # ================= v3.31（#7）大纲拖拽调序 =================
    def reorder_sections(self, pairs):
        \"\"\"把同级章节的新顺序（[start, end) 块区间列表）发给内核整段重排。\"\"\"
        try:
            payload = json.dumps(pairs)
        except (TypeError, ValueError):
            return
        self._js_active(f"window.reorderSections({js(payload)})")
        self.show_status("已调整章节顺序")""")

fail = [i for i, (o, nw, n) in enumerate(EDITS) if src.count(o) != n]
if fail:
    for i in fail:
        print("ANCHOR FAIL #%d count=%d" % (i, src.count(EDITS[i][0])))
    sys.exit(1)
for o, nw, _n in EDITS:
    src = src.replace(o, nw)

io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("mainwindow.py patched: %d edits" % len(EDITS))
