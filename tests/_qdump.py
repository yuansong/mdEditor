# -*- coding: utf-8 -*-
"""Dump mdEditor QSettings values (read-only)."""
import os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

app = QApplication(sys.argv)
s = QSettings("WorkBuddy", "WorkBuddyMarkdown")
out = []
for k in sorted(s.allKeys()):
    out.append("%s = %s" % (k, s.value(k)))
print("\n".join(out))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_qdump.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))
