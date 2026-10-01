# -*- coding: utf-8 -*-
"""把 docs/图表主题预览-v3.34.html 用 QtWebEngine 离屏渲染成 PNG，供人工观感确认。"""
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "..", "docs", "图表主题预览-v3.34.html")
OUT = os.path.join(HERE, "_mmd_theme_preview.png")

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

app = QApplication(sys.argv)
view = QWebEngineView()
view.resize(1240, 1500)
view.show()


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


loaded = {"ok": False}
view.loadFinished.connect(lambda ok: loaded.update(ok=ok))
view.load(QUrl.fromLocalFile(os.path.abspath(HTML)))
wait(4000)
print("loaded:", loaded["ok"])
wait(1200)
pix = view.grab()
pix.save(OUT, "PNG")
print("png:", os.path.exists(OUT), os.path.getsize(OUT) if os.path.exists(OUT) else 0)
# 滚动到页面底部截第二张（深色主题区）
view.page().runJavaScript("window.scrollTo(0, document.body.scrollHeight)", lambda v: None)
wait(1500)
OUT2 = os.path.join(HERE, "_mmd_theme_preview_bottom.png")
pix2 = view.grab()
pix2.save(OUT2, "PNG")
print("png2:", os.path.exists(OUT2), os.path.getsize(OUT2) if os.path.exists(OUT2) else 0)
