# -*- coding: utf-8 -*-
"""隔离验证：QImage.loadFromData + QClipboard.setImage 在本环境是否可用。"""
import base64, os, sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication, QImage

PNG1 = ("data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")
raw = base64.b64decode(PNG1.split(",", 1)[1])

app = QApplication(sys.argv)
img = QImage()
ok = img.loadFromData(raw)
print("loadFromData ok=%s size=%sx%s" % (ok, img.width(), img.height()))
cb = QGuiApplication.clipboard()
cb.setImage(img)
im = cb.image()
print("clipboard image isNull=%s size=%sx%s" % (im.isNull(), im.width(), im.height()))
print("mime hasImage=%s" % cb.mimeData().hasImage())
os._exit(0)
