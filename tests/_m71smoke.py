# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m71_smoke.txt")
with open(LOG, "w", encoding="utf-8") as f:
    f.write("start\n")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
with open(LOG, "a", encoding="utf-8") as f:
    f.write("qt imported\n")
app = QApplication(sys.argv)
with open(LOG, "a", encoding="utf-8") as f:
    f.write("app ok\n")
from mainwindow import MainWindow
with open(LOG, "a", encoding="utf-8") as f:
    f.write("mainwindow imported\n")
win = MainWindow()
win.show()
with open(LOG, "a", encoding="utf-8") as f:
    f.write("win shown\n")
