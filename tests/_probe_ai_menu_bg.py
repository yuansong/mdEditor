# -*- coding: utf-8 -*-
"""离屏渲染设置对话框各页，定位 AI 菜单页背景色差异（v3.48.39 视觉排查）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, QSettings

import dialogs
from PySide6.QtWidgets import QWidget


class _TP(QWidget):
    """安全空页替身（避免离屏下 TemplatePage/AIConnectionForm 等组件崩溃）。"""
    def __init__(self, win, parent=None):
        super().__init__(parent)


def _safe_page(self):
    return QWidget(self)


# 隔离：仅保留真实 AI 菜单页，其余页面与 TemplatePage 替换为安全空页，
# 规避离屏环境下某些组件初始化导致的段错误。
for _nm in ("_page_general", "_page_editor_fmt", "_page_ai_connection"):
    setattr(dialogs.SettingsDialog, _nm, _safe_page)
dialogs.TemplatePage = _TP


class _Dummy:
    """缺失属性占位：可调用（供信号 connect）、为假值（供 `x or []`）、可空迭代。"""
    def __call__(self, *a, **k):
        return None
    def __bool__(self):
        return False
    def __iter__(self):
        return iter([])
    def __getattr__(self, n):
        return _Dummy()


class _Win(QWidget):
    """最小替身：SettingsDialog 构造只读 _theme/_settings 与若干 getattr 默认属性，
    其余缺失属性返回 _Dummy（可调用 / 假值 / 可空迭代），render 阶段不触发交互回调。"""
    _theme = os.environ.get("PROBE_THEME", "light")
    _settings = QSettings("mdEditorProbe", "probe")

    def __getattr__(self, n):
        return _Dummy()


def main():
    app = QApplication(sys.argv)
    win = _Win()
    dlg = dialogs.SettingsDialog(win)
    dlg.resize(700, 520)

    def shot(idx, path):
        dlg.pages.setCurrentIndex(idx)
        dlg.resize(660, 460)   # 模拟真实默认窗口尺寸（不按内容撑大）
        sz = dlg.size()
        pix = QPixmap(sz)
        pix.fill(QColor("white"))
        dlg.render(pix)
        pix.save(path)
        print("SAVED", path, sz.width(), sz.height())

    base = os.path.dirname(__file__)
    print("CONSTRUCTED dialog ok")
    # 渲染真实页：写作与输入（含斜杠菜单列表 themeList）+ AI 菜单页
    theme = os.environ.get("PROBE_THEME", "light")
    shot(2, os.path.join(base, "_probe_slash_%s.png" % theme))
    shot(4, os.path.join(base, "_probe_aimenu_%s.png" % theme))
    print("DONE")


if __name__ == "__main__":
    main()
