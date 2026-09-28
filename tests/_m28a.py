# -*- coding: utf-8 -*-
"""v3.29 探针：插入图片面板「存储方式」二选一单选，默认跟随系统设置。
1) 系统设置 = assets → 默认选中相对路径存储；2) = embed → 默认选中内嵌式存储；
3) mode() 返回 assets/embed；4) 单选切换联动预览文案。"""
import json
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m28a.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")


app = QApplication(sys.argv)
from mainwindow import MainWindow
from dialogs import InsertImageDialog

win = MainWindow()
win.show()

# 1) 系统设置 = assets（相对路径）→ 默认选中「相对路径存储」
win._image_mode = "assets"
d1 = InsertImageDialog(win)
check("系统设置=相对路径 → 默认选中相对路径存储",
      d1.rb_assets.isChecked() and (not d1.rb_embed.isChecked())
      and d1.mode() == "assets", d1.mode())
d1.rb_embed.setChecked(True)
check("切到内嵌式存储 → mode()=embed", d1.mode() == "embed", d1.mode())
d1.deleteLater()

# 2) 系统设置 = embed（内嵌）→ 默认选中「内嵌式存储」
win._image_mode = "embed"
d2 = InsertImageDialog(win)
check("系统设置=内嵌 → 默认选中内嵌式存储",
      d2.rb_embed.isChecked() and (not d2.rb_assets.isChecked())
      and d2.mode() == "embed", d2.mode())
d2.rb_assets.setChecked(True)
check("切到相对路径存储 → mode()=assets", d2.mode() == "assets", d2.mode())

# 3) 单选互斥：选中一个，另一个自动取消
check("单选互斥", d2.rb_assets.isChecked() and (not d2.rb_embed.isChecked()))

# 4) 预览文案随单选联动（填一个假本地路径，仅测文案分支）
d2.path_edit.blockSignals(True)
d2._src = "X:/fake/shot.png"
d2.path_edit.blockSignals(False)
d2.rb_embed.setChecked(True)
t_embed = d2.preview.text()
d2.rb_assets.setChecked(True)
t_assets = d2.preview.text()
check("预览文案随存储方式联动（内嵌=写进文档 / 相对路径=assets）",
      "data URL" in t_embed and "assets" in t_assets,
      f"embed[{t_embed[:20]}] assets[{t_assets[:20]}]")
d2.deleteLater()

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results) + "\n")
    p = sum(1 for r in results if r.startswith("PASS"))
    fl = sum(1 for r in results if r.startswith("FAIL"))
    f.write(f"DONE PASS={p} FAIL={fl}\n")
win.close()
app.processEvents()
