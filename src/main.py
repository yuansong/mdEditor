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

v3.32 新增：
- 滚动日志（%APPDATA%/mdEditor/logs/，P0-5）
- 单实例互斥：二次启动把文件参数转发给已运行实例（P0-2）
- 草稿恢复：启动时检测未命名文档的影子草稿（P0-1，恢复逻辑在 MainWindow）
"""
import json
import logging
import logging.handlers
import os
import sys
import traceback

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtGui import QFont, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from config import APP_NAME, APP_VERSION, LOG_DIR
from mainwindow import MainWindow
from styles import app_qss

# 单实例服务名（QLocalServer 的管道名；Windows 下即命名管道）
# v3.35：可经 MDEDITOR_SINGLETON_KEY 覆盖 —— 供自动化在「已有实例在跑」时
# 仍能确定性启动新实例做启动自检（与 MDEDITOR_SKIP_DRAFT 同类的测试隔离开关）。
_SINGLETON_KEY = os.environ.get("MDEDITOR_SINGLETON_KEY") \
    or "WorkBuddyMarkdown.SingleInstance.v1"


def setup_logging():
    """v3.32（P0-5）：本地滚动日志。INFO 起步，文件 512KB × 3 份轮转，
    供「帮助 → 复制诊断信息」取最近日志，也便于用户报障时拿证据。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "mdEditor.log"),
        maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    logging.getLogger("mdEditor").setLevel(logging.INFO)

    def _hook(tp, val, tb):
        logging.getLogger("mdEditor.crash").critical(
            "未捕获异常：%s", "".join(traceback.format_exception(tp, val, tb)))
        sys.__excepthook__(tp, val, tb)

    sys.excepthook = _hook
    logging.getLogger("mdEditor.app").info(
        "mdEditor %s 启动（Python %s / %s）",
        APP_VERSION, sys.version.split()[0], sys.platform)


def _forward_to_running(paths):
    """已有实例在运行时，把文件路径转发过去并退出（返回 True）。
    转发内容 = UTF-8 JSON 数组；首个实例 newConnection 里解析。"""
    sock = QLocalSocket()
    sock.connectToServer(_SINGLETON_KEY)
    if not sock.waitForConnected(300):
        return False
    payload = json.dumps(paths, ensure_ascii=False).encode("utf-8")
    sock.write(payload)
    sock.flush()
    ok = sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    logging.getLogger("mdEditor.app").info("已转发参数给运行中实例：%s", paths)
    return ok


def _start_singleton_server(win):
    """首实例：监听管道，收到路径即在已有窗口中新开标签并前置窗口（P0-2②）。"""
    QLocalServer.removeServer(_SINGLETON_KEY)   # 清理异常退出残留

    def _on_conn():
        while True:
            conn = _server.nextPendingConnection()
            if conn is None:
                return

            def _read(c=conn):
                buf = bytes(c.readAll())
                try:
                    paths = json.loads(buf.decode("utf-8")) if buf else []
                except (ValueError, UnicodeDecodeError):
                    paths = []
                for p in paths if isinstance(paths, list) else []:
                    if isinstance(p, str) and os.path.exists(p) and \
                            p.lower().endswith((".md", ".markdown", ".mdown", ".txt")):
                        win._load_path(os.path.abspath(p))
                if paths:
                    win.showNormal()
                    win.raise_()
                    win.activateWindow()
                c.disconnectFromServer()

            conn.readyRead.connect(_read)

    _server = QLocalServer()
    _server.newConnection.connect(_on_conn)
    if not _server.listen(_SINGLETON_KEY):
        logging.getLogger("mdEditor.app").warning(
            "单实例监听失败：%s", _server.errorString())


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

    # 命令行文件参数（在单实例转发 / 本实例打开两处使用）
    file_args = [a for a in sys.argv[1:]
                 if os.path.exists(a) and a.lower().endswith(
                     (".md", ".markdown", ".mdown", ".txt"))]

    setup_logging()

    # v3.32（P0-2）：单实例。已有实例 → 转发文件参数后退出；
    # 转发失败（如管道半死）则照常以第二实例启动，宁可双开也不拒绝使用。
    if _forward_to_running(file_args):
        sys.exit(0)

    win = MainWindow()
    _start_singleton_server(win)
    win.show()
    for arg in file_args[:1]:
        win._load_path(arg)
    # v3.32（P0-1）：启动时检测孤儿草稿并询问恢复（窗口就绪后执行）
    win.check_draft_recovery()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
