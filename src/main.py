# -*- coding: utf-8 -*-
"""mdEditor — Typora 风格所见即所得 Markdown 编辑器（Windows）。

模块结构：
- config.py      应用常量 / 演示文档 / 模式定义
- styles.py      多主题 QSS 样式体系（六套主题调色板）
- icons.py       统一线性图标（QPainter 矢量绘制）
- dialogs.py     查找替换 / 快捷键设置 / 系统设置对话框
- sidebar.py     左侧边栏（文件列表 + 大纲树）
- mainwindow.py  主窗口
- main.py        程序入口（本文件）

基于 PySide6 / QtWebEngine：
- 块级「所见即所得」编辑（光标所在块显示原始语法，其余块实时渲染）
- 多文件标签页编辑、双栏模式（左源码 / 右预览）
- VS Code 式左侧竖向工具栏、斜杠菜单 / 行菜单 / 块菜单 / 表格工具栏
- 数学公式（KaTeX 离线渲染）、Mermaid 图表（流程图/时序图/类图/状态图/E-R 图等）
- 六套主题全局换肤、导出 HTML / PDF、自动保存、拖拽打开
"""
import os
import sys

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from config import APP_NAME
from mainwindow import MainWindow
from styles import app_qss


def _app_icon_path():
    """v3.26：应用图标路径（开发态取 src/，打包态取 _MEIPASS 根目录）。"""
    name = "mdeditor.ico"
    if getattr(sys, "frozen", False):
        p = os.path.join(sys._MEIPASS, name)
        if os.path.exists(p):
            return p
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    return p if os.path.exists(p) else ""


def _load_translators(app):
    """加载 Qt 官方简体中文翻译：QMessageBox / QFileDialog / QInputDialog
    等标准按钮由此变为中文（保存 / 取消 / 确定等）。"""
    base = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    candidates = [base]
    if getattr(sys, "frozen", False):  # PyInstaller 打包后
        candidates.append(os.path.join(sys._MEIPASS, "translations"))
    for tr in ("qt_zh_CN.qm", "qtbase_zh_CN.qm"):
        for folder in candidates:
            path = os.path.join(folder, tr)
            if os.path.exists(path):
                translator = QTranslator(app)
                if translator.load(path):
                    app.installTranslator(translator)
                    break


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("WorkBuddy")
    icon_path = _app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))  # 标题栏 / 任务栏统一图标
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    _load_translators(app)
    app.setStyleSheet(app_qss("light"))
    win = MainWindow()
    win.show()
    # 支持命令行传入文件（新开标签页）
    for arg in sys.argv[1:]:
        if os.path.exists(arg) and arg.lower().endswith((".md", ".markdown", ".mdown", ".txt")):
            win._load_path(arg)
            break
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
