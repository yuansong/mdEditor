# -*- coding: utf-8 -*-
"""主窗口：多文档标签、三视图（写作/源码/分屏）、文件操作与导出。"""
import base64
import binascii
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
import sys

import openutil  # 跨平台打开文件 / 文件夹（封装 os.startfile / open / xdg-open）

from PySide6.QtCore import (QBuffer, QByteArray, QEvent, QIODevice, QTimer, QUrl,
                            QSize, Qt, QSettings, QMimeData, QObject)
from PySide6.QtGui import (QAction, QActionGroup, QBrush, QColor, QGuiApplication,
                           QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QProxyStyle, QPushButton, QDockWidget, QSplitter, QStackedWidget, QStyle, QTabBar,
    QToolBar, QToolButton, QVBoxLayout, QWidget, QComboBox, QDoubleSpinBox,
    QFormLayout, QCheckBox, QDialogButtonBox, QGroupBox, QGridLayout,
    QSpinBox,
)
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

import exporters
import bookmode   # v3.44.34（BOOK-1）：mdBook 书籍模式（纯函数解析 / 序列化）
import mdutil     # v3.45（BOOKLINK）：锚点派生 / 标题抽取（与导出同源）
import ai_pane    # v3.46（SoloMD P1）：AI 助手停靠面板（密钥经 secretstore 跨平台存储）
import ai_connection  # v3.47.2（SoloMD 对标）：独立 AI 连接面板 / 设置页「AI 连接」
import semsearch     # v3.48.12（SEM-2）：本地语义搜索（离线 TF-IDF + sqlite 索引）


def table_file_to_markdown(path):
    """读取 xlsx(首个工作表) 或 csv，返回 Markdown 表格字符串；无数据返回 ''。"""
    ext = os.path.splitext(path)[1].lower()
    rows = []
    if ext == ".csv":
        import csv
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.reader(f):
                rows.append(list(r))
    else:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        for r in ws.iter_rows(values_only=True):
            rows.append(list(r))
        wb.close()
    rows = [[("" if c is None else str(c)) for c in row] for row in rows]
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return ""
    ncol = max(len(row) for row in rows)

    def cell(v):
        return v.replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    lines = []
    lines.append("| " + " | ".join(cell(c) for c in rows[0]) + " |")
    lines.append("| " + " | ".join("---" for _ in range(ncol)) + " |")
    for row in rows[1:]:
        if len(row) < ncol:
            row = row + [""] * (ncol - len(row))
        lines.append("| " + " | ".join(cell(c) for c in row[:ncol]) + " |")
    return "\n".join(lines)


# v3.44.5（DESIGN01）：标签栏选中指示条 —— 设计稿 .tab.on::after 为 inset 10px 的
# 2px accent 短线；QSS 的 border-bottom 无法 inset，故在 paintEvent 中自绘。

# v3.44.8（TB-DWM）：Windows 原生标题栏沉浸式暗色同步（仅 win32 + 原生标题栏路径）。
# 原生标题栏由 DWM 绘制、不在 Qt 主题系统内，故单独随深色主题族切换亮/暗。
_DARK_THEMES = {"dark", "night", "panda"}


def _win_set_immersive_dark(hwnd, enabled):
    """通过 DwmSetWindowAttribute 切换原生标题栏亮/暗（仅 win32 生效）。"""
    try:
        import ctypes
        from ctypes import wintypes
        dwmapi = ctypes.windll.dwmapi
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        proto = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, wintypes.HWND, ctypes.c_int, ctypes.c_void_p, ctypes.c_int)
        DwmSetWindowAttribute = proto(("DwmSetWindowAttribute", dwmapi))
        value = ctypes.c_int(1 if enabled else 0)
        DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                             ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


class _TabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent = QColor("#0052d9")

    def set_accent(self, color):
        self._accent = QColor(color) if not isinstance(color, QColor) else color

    def paintEvent(self, event):
        super().paintEvent(event)
        i = self.currentIndex()
        if i < 0:
            return
        r = self.tabRect(i)
        x0 = r.left() + 10
        x1 = r.right() - 10
        if x1 <= x0:
            x0, x1 = r.left(), r.right()
        p = QPainter(self)
        p.fillRect(x0, r.bottom() - 1, x1 - x0, 2, self._accent)
from config import APP_NAME, APP_VERSION, BUILTIN_TEMPLATES, CODE_STYLES, DEMO_MD, DRAFT_DIR, FILE_LIST_DEFAULT_DIR, FMTLOG_DIR, HERE, LOG_DIR, MD_EXTS, MMD_LEGACY, MMD_THEMES, MMD_THEME_LABELS, MODES, TEMPLATE_FILE, TPL_FILE_VERSION, TPL_MAX_BYTES, TPL_NAME_MAX, UPDATE_URL, USER_DATA_DIR, js

# 斜杠（/）菜单可配置项：一级菜单 id 集与默认顺序 / 默认项 / 二级默认下标
# v3.30.3：按用户要求移除「上标 / 下标」（supsub）一级项；^x^ / ~x~ 语法仍可输入
# v3.31.3：footnote / deflist 合并为 refs「脚注与定义」（旧配置 id 由 merge 自动插回）
# v3.32（P1-1）：新增 tpl「模板」一级项（内置 6 个场景模板，插入即写）
SLASH_IDS = ("heading", "list", "table", "code", "hr", "quote", "image", "chart",
             "refs", "tpl", "math")
SLASH_ORDER_DEFAULT = ["heading", "list", "table", "code", "hr", "quote", "image", "chart",
                       "refs", "tpl", "math"]
SLASH_SUB_DEFAULTS = {"heading": 2, "list": 1, "chart": 0, "math": 0,
                      "refs": 0, "tpl": 0}  # 标题默认H3 / 列表默认有序 / 图表默认流程图 / 公式默认上标


def merge_slash_order(saved):
    """把「已保存的菜单顺序」与最新默认顺序合并。

    新版本新增的一级菜单项按其**默认相对位置**插到相邻项旁边，而不是一律追加到末尾 ——
    否则「公式固定在最后」这类刻意设计会被后来的新项挤掉，用户排好的第一项也会被冲掉。
    传入完整默认顺序时结果与传入值完全一致（幂等）。
    """
    ids = [x for x in (saved or []) if x in SLASH_IDS]
    for x in SLASH_ORDER_DEFAULT:
        if x in ids:
            continue
        i = SLASH_ORDER_DEFAULT.index(x)
        prev = next((y for y in reversed(SLASH_ORDER_DEFAULT[:i]) if y in ids), None)
        nxt = next((y for y in SLASH_ORDER_DEFAULT[i + 1:] if y in ids), None)
        if prev is not None:
            ids.insert(ids.index(prev) + 1, x)
        elif nxt is not None:
            ids.insert(ids.index(nxt), x)
        else:
            ids.append(x)
    return ids


# 可插入的图片扩展名与对应 MIME（data URL 用）
IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
IMG_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp"}
# 反向映射：剪贴板图片的 MIME → 扩展名（落盘时用）
MIME_EXT = {v: k for k, v in IMG_MIME.items()}
MIME_EXT["image/jpg"] = ".jpg"
# 内嵌图片（data URL）在 Markdown 中的形态：![alt](data:image/png;base64,xxxx)
IMG_DATA_RE = re.compile(
    r"!\[([^\]]*)\]\(\s*(data:image/([A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+))\s*\)")


# v3.48.30（IMG-EMBED）：换行拆断的内嵌图片行自动愈合 --------------------
_IMG_OPEN_RE = re.compile(
    r"^\s*!\[[^\]\n]*\]\(\s*(data:image/[A-Za-z0-9.+-]+;base64,)"
    r"[A-Za-z0-9+/=]*\s*$")
_B64_LINE_RE = re.compile(r"^\s*([A-Za-z0-9+/=\s]*?)\)\s*$")
_B64_ANY_RE = re.compile(r"^\s*[A-Za-z0-9+/=]*\s*$")


def heal_wrapped_images(text):
    """把被换行拆断的内嵌图片 data URL 并回单行。

    外部编辑器 / AI 输出常把长 base64 按 76 列换行写入 Markdown：
    `![alt](data:image/png;base64,xxx\nyyy\nzzz)`。拆断后该行不再匹配
    图片块正则（单行 `![..](..)`），编辑区永远显示 ![](...) 源码、图片
    不渲染、裁剪被拒（naturalWidth=0）。此处将「内嵌图开头行 + 纯 base64
    续行 + 以 ) 收尾」重联为一行并剥掉 base64 内部全部空白。
    仅在行首匹配内嵌图开头且无右括号时触发，正常文档零改动。"""
    lines = text.split("\n")
    if len(lines) < 2:
        return text
    out = []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        m = _IMG_OPEN_RE.match(ln)
        if m and not ln.rstrip().endswith(")"):
            parts = [ln.rstrip()]
            j = i + 1
            closed = False
            while j < n and (j - i) <= 4096:
                nxt = lines[j]
                if _B64_LINE_RE.match(nxt):
                    parts.append(nxt)
                    closed = True
                    j += 1
                    break
                if nxt.strip() and _B64_ANY_RE.match(nxt):
                    parts.append(nxt)
                    j += 1
                    continue
                break
            if closed:
                joined = "".join(parts)
                k = joined.index(";base64,") + len(";base64,")
                joined = joined[:k] + re.sub(r"\s+", "", joined[k:])
                out.append(joined)
                i = j
                continue
        out.append(ln)
        i += 1
    return "\n".join(out)
from dialogs import (
    CommandPaletteDialog, FindDialog, HistoryDialog, InsertImageDialog,
    SettingsDialog, ShortcutDialog, StyleManagerDialog,
)
from icons import (
    icon_ai, icon_find, icon_history, icon_nav_back, icon_nav_forward, icon_new, icon_open,
    icon_redo, icon_save, icon_settings, icon_sidepanel, icon_toolbar_expand, icon_undo,
)
from sidebar import Sidebar
import styles
import uistyles
import mactitlebar
import ribbonchrome
from i18n import T, get_lang, set_lang

# v3.32（P0-5）：模块级日志器（main.setup_logging 已装配滚动文件输出）。
_log = logging.getLogger("mdEditor.app")


# ================= v3.35（TPL-D）「设为模板文件」名称规则 =================
def normalize_template_name(name, max_len=None):
    """归一化模板名称：空白折叠 → 去首尾 → 按显示上限截断；不可用时返回空串。

    名称会显示在 / 菜单「模板」二级与悬浮栏模板菜单里，过长会撑破菜单宽度，
    故与内核 window.setCustomTemplates 的截断规则同源（同为 TPL_NAME_MAX 个码点）——
    这样「管理对话框里看到的名字」与「菜单里看到的名字」永远一致，
    不会出现只在菜单被静默截断的错位。
    """
    limit = TPL_NAME_MAX if max_len is None else max(1, int(max_len))
    s = re.sub(r"[\s\u200b\u200c\u200d\ufeff]+", " ", str(name or "")).strip()
    return s[:limit]


def normalize_template_icon(ic):
    """v3.36（TPL-E）模板菜单图标：去空白 + 按码点截断到 4（容纳组合式 emoji）。

    空串 = 无图标，内核渲染时回退为 ⭐（自建模板保持旧观感）。
    """
    s = str(ic or "").strip()
    return "".join(list(s)[:4]) if s else ""


def unique_template_name(name, existing, max_len=None):
    """重名自动编号（同名模板在菜单里无法区分）："周报" → "周报 2" → "周报 3"…

    编号后仍须满足显示上限，故先给序号留位再截断基名（否则 30 字满名加序号会
    被截回原名，陷入永远重名）。
    """
    limit = TPL_NAME_MAX if max_len is None else max(1, int(max_len))
    used = {str(n or "") for n in (existing or [])}
    if name not in used:
        return name
    for k in range(2, 1000):
        suf = " %d" % k
        cand = name[:max(1, limit - len(suf))] + suf
        if cand not in used:
            return cand
    return name


class EditorPage(QWebEnginePage):
    """自定义页面：把 JS alert / confirm / prompt 换成中文原生对话框；
    v3.45.3（LINK-NAV）：链接点击由内核 JS 拦截后经 __navQ 队列交主窗口，
    这里只保留「主帧误导航到外部目标」的灾难性兜底（拒跳转 + 转浏览器）。"""

    def __init__(self, parent=None, mw=None):
        super().__init__(parent)
        self._mw = mw

    def javaScriptPrompt(self, origin, msg, default):
        from PySide6.QtWidgets import QInputDialog
        parent = self.parent() if isinstance(self.parent(), QWidget) else None
        text, ok = QInputDialog.getText(parent, T("输入", "Input"), str(msg), text=str(default or ""))
        return ok, text

    def javaScriptAlert(self, origin, msg):
        QMessageBox.information(self.parent() if isinstance(self.parent(), QWidget) else None,
                                "提示", str(msg))

    def javaScriptConfirm(self, origin, msg):
        btn = QMessageBox.question(self.parent() if isinstance(self.parent(), QWidget) else None,
                                   "确认", str(msg),
                                   QMessageBox.Ok | QMessageBox.Cancel)
        return btn == QMessageBox.Ok

    def acceptNavigationRequest(self, url, navType, isMainFrame):
        # v3.45.3（LINK-NAV）：链接点击已全部由内核 JS 拦截（preventDefault）
        # 并经 __navQ 队列交主窗口处理，正常不会走到这里。旧 mdeditor://
        # 自定义协议桥接已废弃（Chromium 会静默丢弃该 scheme 的导航，
        # acceptNavigationRequest 根本不被调用，实测 PySide6 6.11）。
        # 兜底：主帧链接点击若导航到非本地目标，会整个替换编辑器页面
        # （灾难性），一律拒绝并改交系统浏览器打开。
        if (isMainFrame and url.scheme() not in ("file", "about", "data", "blob")
                and self._mw is not None):
            self._mw._open_external(url.toString())
            return False
        return super().acceptNavigationRequest(url, navType, isMainFrame)


# v3.48.34（PDF-LAYOUT）：PDF 导出设置对话框 —— 纸张 / 方向 / 四边独立边距 /
# 缩放 / 行间距 / 字体 / 字号，可保存为默认。v3.47.1 起逐步扩展。
class PdfExportDialog(QDialog):
    # 可选字体（含「跟随界面字体」占位）；中文环境优先常用字体
    FONTS = ["", "Microsoft YaHei", "SimSun", "SimHei", "KaiTi",
             "Arial", "Times New Roman", "Consolas", "Courier New"]

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle(T("PDF 导出设置", "PDF Export Settings"))
        self._settings = settings
        from bookexport import PAPER_SIZES, PDF_DEFAULT_OPTS, opts_from_settings
        o = opts_from_settings(settings)
        self._syncing = False

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # ---- 纸张 ----
        g_page = QGroupBox(T("纸张", "Paper"))
        f1 = QFormLayout(g_page)
        self._paper = QComboBox()
        for label, val in PAPER_SIZES:
            self._paper.addItem(label, val)
        idx = self._paper.findData(o["paper_size"])
        self._paper.setCurrentIndex(idx if idx >= 0 else 0)
        f1.addRow("纸张尺寸", self._paper)

        self._orient = QComboBox()
        self._orient.addItem(T("纵向", "Portrait"), "portrait")
        self._orient.addItem(T("横向", "Landscape"), "landscape")
        idx = self._orient.findData(o["orientation"])
        self._orient.setCurrentIndex(idx if idx >= 0 else 0)
        f1.addRow("方向", self._orient)
        lay.addWidget(g_page)

        # ---- 页边距（四边独立；勾选「四边一致」时联动）----
        g_m = QGroupBox(T("页边距", "Margins"))
        v = QVBoxLayout(g_m)
        self._uniform = QCheckBox(T("四边一致", "Uniform Margins"))
        self._uniform.setChecked(bool(o["margin_uniform"]))
        v.addWidget(self._uniform)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        self._margins = {}
        for i, (key, label) in enumerate((("top", "上"), ("right", "右"),
                                          ("bottom", "下"), ("left", "左"))):
            sp = QDoubleSpinBox()
            sp.setRange(0.0, 100.0)
            sp.setDecimals(1)
            sp.setSingleStep(1.0)
            sp.setSuffix(" mm")
            sp.setValue(float(o["margin_" + key + "_mm"]))
            sp.valueChanged.connect(self._on_margin_changed)
            self._margins[key] = sp
            row, col = divmod(i, 2)
            grid.addWidget(QLabel(label), row, col * 2)
            grid.addWidget(sp, row, col * 2 + 1)
        v.addLayout(grid)
        self._uniform.toggled.connect(self._sync_uniform)
        lay.addWidget(g_m)

        # ---- 排版 ----
        g_t = QGroupBox(T("排版", "Layout"))
        f3 = QFormLayout(g_t)
        self._scale = QSpinBox()
        self._scale.setRange(25, 400)
        self._scale.setSingleStep(5)
        self._scale.setSuffix(" %")
        self._scale.setToolTip(T("正文按比例缩放，页边距保持不变；100% 为原尺寸", "Scale body text proportionally; margins stay fixed; 100% = original size"))
        self._scale.setValue(int(o["scale_pct"]))
        f3.addRow("缩放", self._scale)

        self._line = QDoubleSpinBox()
        self._line.setRange(0.0, 4.0)
        self._line.setDecimals(2)
        self._line.setSingleStep(0.05)
        self._line.setSpecialValueText("跟随文档")
        self._line.setToolTip(T("行高倍数（× 字号）；「跟随文档」表示不调整", "Line-height multiplier (× font size); 'Follow Document' means no adjustment"))
        self._line.setValue(float(o["line_spacing"]))
        f3.addRow("行间距", self._line)

        self._font = QComboBox()
        self._font.addItem(T("（跟随界面字体）", "(Follow UI Font)"), "")
        for f in self.FONTS[1:]:
            self._font.addItem(f, f)
        idx = self._font.findData(o["font_family"])
        self._font.setCurrentIndex(idx if idx >= 0 else 0)
        f3.addRow("字体", self._font)

        self._size = QDoubleSpinBox()
        self._size.setRange(8, 24)
        self._size.setDecimals(1)
        self._size.setSuffix(" pt")
        self._size.setValue(float(o["font_size_pt"]))
        f3.addRow("字号", self._size)
        lay.addWidget(g_t)

        self._save = QCheckBox(T("保存为默认", "Save as Default"))
        lay.addWidget(self._save)

        # v3.48.38（PDF-DEF）：一键还原为内置最佳默认参数（不写盘，仅重置本对话框）
        hb = QHBoxLayout()
        self._reset = QPushButton(T("还原默认设置", "Restore Defaults"))
        self._reset.setToolTip(
            "将以上各项重置为程序内置的最佳导出默认值（行距 / 字体 / 字号 / 边距等）")
        self._reset.clicked.connect(self._reset_to_defaults)
        hb.addWidget(self._reset)
        hb.addStretch(1)
        lay.addLayout(hb)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._apply_uniform_state()

    # ---- 四边联动 ----
    def _apply_uniform_state(self):
        """四边一致时锁住「右 / 下 / 左」（值随「上」联动），避免误以为可独立输入。"""
        uni = self._uniform.isChecked()
        for key in ("right", "bottom", "left"):
            self._margins[key].setEnabled(not uni)

    def _sync_uniform(self, checked):
        if not checked:
            self._apply_uniform_state()
            return
        self._syncing = True
        top = self._margins["top"].value()
        for key in ("right", "bottom", "left"):
            self._margins[key].setValue(top)
        self._syncing = False
        self._apply_uniform_state()

    def _on_margin_changed(self, _val):
        if self._syncing or not self._uniform.isChecked():
            return
        src = self.sender()
        self._syncing = True
        for sp in self._margins.values():
            if sp is not src:
                sp.setValue(src.value())
        self._syncing = False

    def result_opts(self):
        m = {k: float(sp.value()) for k, sp in self._margins.items()}
        return {
            "paper_size": self._paper.currentData(),
            "orientation": self._orient.currentData(),
            "margin_top_mm": m["top"],
            "margin_right_mm": m["right"],
            "margin_bottom_mm": m["bottom"],
            "margin_left_mm": m["left"],
            "margin_mm": m["top"],          # 旧键：兼容历史调用方
            "margin_uniform": self._uniform.isChecked(),
            "scale_pct": int(self._scale.value()),
            "line_spacing": round(float(self._line.value()), 2),
            "font_family": self._font.currentData() or "",
            "font_size_pt": self._size.value(),
            "save_default": self._save.isChecked(),
        }

    def _reset_to_defaults(self):
        """v3.48.38（PDF-DEF）：将对话框控件重置为内置最佳默认参数（PDF_DEFAULT_OPTS）。

        仅复位本对话框，不直接写盘；如需固化默认值，可勾选「保存为默认」后确定。"""
        from bookexport import PDF_DEFAULT_OPTS
        d = PDF_DEFAULT_OPTS
        idx = self._paper.findData(d["paper_size"])
        self._paper.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self._orient.findData(d["orientation"])
        self._orient.setCurrentIndex(idx if idx >= 0 else 0)
        self._uniform.setChecked(bool(d["margin_uniform"]))
        for key, sp in self._margins.items():
            sp.setValue(float(d["margin_" + key + "_mm"]))
        self._scale.setValue(int(d["scale_pct"]))
        self._line.setValue(float(d["line_spacing"]))
        idx = self._font.findData(d["font_family"])
        self._font.setCurrentIndex(idx if idx >= 0 else 0)
        self._size.setValue(float(d["font_size_pt"]))
        self._apply_uniform_state()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1240, 830)
        self.file_path = None
        self._dirty = False
        self._saving = False   # v3.40（UI-R7）：状态栏保存格「⟳ 保存中」标记
        self._pdf_view = None
        self._pdf_path = None
        self._quitting = False
        self._book = None     # v3.44.34（BOOK-1）：当前打开的书籍信息（bookmode.read_book 返回）
        # v3.45.7（BOOK-READ-1）：书籍阅读进度恢复
        self._pending_book_scroll = None   # 启动后待恢复的滚动比例
        self._book_scroll_ts = 0.0         # 上次记录滚动位置的时间戳（节流）

        self._settings = QSettings("WorkBuddy", "WorkBuddyMarkdown")
        # ---- 主题 / 外观（启动即恢复上次选择）----
        self._theme = self._settings.value("theme", "light")
        if self._theme not in styles.THEME_IDS:
            self._theme = "light"
        # v3.39.15（UISTYLE-1）：界面风格（Qt 层皮肤，默认 ps01 现代经典）。
        # 非法 / 已删除的风格 ID 在 set_active 内自动回退默认风格。
        uistyles.set_active(str(self._settings.value("uiStyle", uistyles.DEFAULT_ID) or uistyles.DEFAULT_ID))
        self._uistyle = uistyles.active()
        # v3.41.0（UISTYLE-2 方案 A）：mac 统一工具栏 + 无边框窗口（懒创建，切换风格装/卸）
        self._mac_wrap = None
        self._mac_title = None
        self._mac_frame_on = False
        self._mac_prev_tb_vis = True
        self._zoom = float(self._settings.value("zoom", 1.0) or 1.0)
        self._autosave = self._settings.value("autosave", True, type=bool)
        # v3.44（AUTOSAVE-INT）：自动保存节流间隔（秒，0=实时写盘）
        self._autosave_interval = int(self._settings.value("autosaveInterval", 0) or 0)
        # v3.44（RECENT-MAX）：最近文件保留条数（0=不保留）
        self._recent_max = int(self._settings.value("recentMax", 10) or 10)
        # v3.44（SESSION）：会话保存 / 自动保存节流时间戳
        self._session_ts = 0.0
        self._autosave_ts = 0.0
        # 代码块默认语言（插入代码块时预选，可在 系统设置→编辑器 修改）
        self._code_lang = str(self._settings.value("codeLang", "C") or "C")
        # v3.25 代码块行号 / 代码风格（系统设置→编辑器 可改；代码栏「风格」按钮可临时切换）
        self._code_lnum = str(self._settings.value("codeLineNum", "1")) not in ("0", "false")
        self._code_style = str(self._settings.value("codeStyle", "classic") or "classic")
        # 打字机 / 专注模式（视图菜单或系统设置开关，持久化，重启保持）
        self._typewriter = self._settings.value("typewriter", False, type=bool)
        self._focus = self._settings.value("focus", False, type=bool)
        # P1-1 自动配对 / P1-8 Emoji 补全（默认开，系统设置→编辑器可关）
        self._auto_pair = self._settings.value("autoPair", True, type=bool)
        self._emoji = self._settings.value("emojiComplete", True, type=bool)
        # P1-6 版本历史保留份数（v3.43.1：默认 20 → 5，上限 200 → 100）
        try:
            self._history_keep = max(1, min(100, int(self._settings.value("historyKeep", 5))))
        except (TypeError, ValueError):
            self._history_keep = 5
        # 斜杠（/）菜单配置（系统设置→编辑器 可改）
        raw_order = str(self._settings.value("slashMenuOrder", "") or "")
        saved_order = [x for x in raw_order.split(",") if x in SLASH_IDS]
        self._slash_order = merge_slash_order(saved_order)
        saved_def = str(self._settings.value("slashMenuDef", "heading") or "heading")
        self._slash_def = saved_def if saved_def in self._slash_order else self._slash_order[0]
        def _sub_int(key, dft):
            try:
                return max(0, int(self._settings.value(key, dft)))
            except (TypeError, ValueError):
                return dft
        self._slash_sub = {
            "heading": _sub_int("slashSubHeading", SLASH_SUB_DEFAULTS["heading"]),
            "list": _sub_int("slashSubList", SLASH_SUB_DEFAULTS["list"]),
            "chart": _sub_int("slashSubChart", SLASH_SUB_DEFAULTS["chart"]),
            "math": _sub_int("slashSubMath", SLASH_SUB_DEFAULTS["math"]),
        }
        # 大纲显示级别（1~6，默认 3）与文件列表显示模式（current=当前 / blank=空白项）
        try:
            self._outline_level = max(1, min(6, int(self._settings.value("outlineLevel", 3))))
        except (TypeError, ValueError):
            self._outline_level = 3
        _flm = str(self._settings.value("fileListMode", "current") or "current")
        self._file_list_mode = "blank" if _flm == "blank" else "current"
        # v3.31.2（#3）：大纲分节字数后缀显示开关（默认关）
        self._outline_words = self._settings.value("outlineWords", False, type=bool)
        # v3.44.8（OUT-STRIP）：大纲不再暴露 H1/H2/H3 级别过滤 UI，强制全部显示（filter=0）。
        self._outline_filter = 0
        # v3.31.2（#8）：段落首行缩进格数（0~4，默认 0）
        try:
            self._para_indent = max(0, min(4, int(self._settings.value("paraIndent", 0))))
        except (TypeError, ValueError):
            self._para_indent = 0
        # v3.31.2（#9）：标题 1 全局居中（默认关）
        self._h1_center = self._settings.value("h1Center", False, type=bool)
        # 图片存放方式：assets=落盘到「文档名.assets/」并插入相对路径（推荐）
        #              embed =内嵌 data URL（图片写入 Markdown 本身）
        _imgm = str(self._settings.value("imageMode", "assets") or "assets")
        self._image_mode = "embed" if _imgm == "embed" else "assets"
        # v3.39.8（FMT-LOG）：格式化操作日志开关（v3.48.38 起默认关；内核经 collect 差量上报落盘）
        self._fmt_log = self._settings.value("fmtLog", False, type=bool)
        # 外部 pandoc 路径（导出 docx / EPUB 时优先使用；留空则自动探测 PATH）
        self._pandoc_path = str(self._settings.value("pandocPath", "") or "")
        # v3.48.12（SEM-2）：本地语义搜索总开关（默认开；查找 → 全局搜索 → 语义搜索）
        self._sem_enabled = self._settings.value("semSearchEnabled", True, type=bool)
        # v3.48.13（BACKLINK-4）：反链扫描缓存 {abspath: (mtime, size, [(line, snippet)])}
        self._bl_cache = {}
        # P1-7 外部编辑器可执行文件（留空 = 用系统默认关联程序打开）
        self._external_editor = str(self._settings.value("externalEditor", "") or "")
        # 统计详情缓存（状态栏点击查看）与搜索结果跳转等待状态
        self._stats = {}
        self._outline_cache = []    # 最近一次大纲（导出 PDF 时生成书签）
        # v3.32.2（TPL-C）：用户自定义模板（/ 菜单「模板」二级 + 悬浮栏 📄 共用）
        self._custom_templates = self._load_custom_templates()
        self._pending_toc = None
        self._pending_goto = None
        self._pending_tries = 0
        # v3.46（TOC-SEL）：目录改为「侧栏选择入口」触发 —— 记录待插入目录的目标与类型
        self._toc_insert_kind = None      # None | "file" | "book"
        self._toc_insert_path = None      # 待插入目录的目标文档绝对路径
        self._toc_remove_path = None      # 待删除目录的目标文档绝对路径
        self._book_toc_page = None        # 已插入书籍目录页的绝对路径（None=无）
        self._book_toc_rel = None         # 目录页相对 summary 的路径（如 "目录.md"）

        # ---- 多文档 ----
        self._docs = []          # [{"path": str|None, "content": str|None, "dirty": bool}]
        self._cur = -1
        self._switching = False
        self._pending_switch = -1
        # v3.38（TAB-3）：已关闭标签栈（Ctrl+Alt+T 逐个回溯，浏览器语义）
        self._closed_stack = []
        # v3.38（TAB-B）：多选标签（N++ 对标）—— Ctrl+单击增减 / Shift+单击区间，
        # 集合存标签索引；任何切换 / 批量关闭后清空重建。
        self._tab_multi = set()
        self._multi_anchor = -1
        # v3.38（TAB-8）：最近使用顺序（MRU，存 doc 字典引用；切换时前插、关闭时惰性剔除）
        self._mru = []

        # ---- 模式（edit=写作 / src=源码 / dual=分屏）----
        self._mode = "edit"
        self._dual = False
        self._last_preview_md = None

        # ---- 每个视图的加载状态 ----
        # role -> {"loaded": bool, "pending": str, "src": bool, "preview": bool}
        self._vstate = {
            "edit": {"loaded": False, "pending": DEMO_MD, "src": False, "preview": False},
            "src": {"loaded": False, "pending": "", "src": True, "preview": False},
            "prev": {"loaded": False, "pending": "", "src": False, "preview": True},
        }

        # v3.38（OUT-5）：启动行为默认值（设置页可改，QSettings 持久化）
        # v3.44.1：默认改为「session」——启动时优先恢复上次多标签会话
        self._startup_action = "session"
        self._startup_folder = ""
        # v3.38（FLP-1）：文件列表默认打开路径（config 默认值 + QSettings 覆盖）
        self._file_list_default_dir = str(
            self._settings.value("files/defaultDir", FILE_LIST_DEFAULT_DIR) or "")

        self._init_ui()
        self._init_menu_toolbar()
        self.apply_theme(self._theme, persist=False)

        # 初始文档：v3.38（OUT-5）「启动时」；v3.44（SESSION）新增「session」完整会话恢复。
        # session=恢复上次多标签会话（默认）/ lastFile=恢复上次单个文件 / blank=欢迎页 /
        # folder=打开指定文件夹（仅侧栏定位，不打开文档）。旧 lastFileSide 值兼容映射为 session。
        _sa = str(self._settings.value("startupAction", self._startup_action) or "session")
        if _sa == "lastFileSide":
            _sa = "session"
        _lf = str(self._settings.value("lastFile", "") or "")

        if _sa == "session":
            if not self._restore_session():
                self._add_doc(path=None, text=DEMO_MD)
                self._sidebar.restore_initial_dir()
        elif _sa == "lastFile" and _lf and os.path.isfile(_lf):
            self._add_doc(path=_lf, text=self._read_file(_lf))
            self._add_recent(_lf)
        elif _sa == "folder":
            self._add_doc(path=None, text=DEMO_MD)
            # v3.44：folder 档复用「默认打开位置」(files/defaultDir)，去重 startupFolder
            _sf = str(self._settings.value("files/defaultDir", "") or "")
            if _sf and os.path.isdir(_sf):
                self._sidebar.set_root(_sf)
        else:  # blank（默认）
            self._add_doc(path=None, text=DEMO_MD)

        # v3.38（FLP-1）：文件列表默认打开路径 —— 上次访问目录（优先）→ 默认路径 → 根层。
        # session / folder / lastFile 三档已由上方各自决定侧栏位置（OUT-5），
        # 仅 blank 档（默认）接管 restore_initial_dir；folder 已定位则标记不再二次接管。
        if _sa == "blank":
            self._sidebar.restore_initial_dir()
        elif _sa == "folder" and self._sidebar._cur_dir:
            self._sidebar._initial_restored = True
        # session 档在 _restore_session 内部已完成侧栏定位并标记 _initial_restored

        # v3.45.7（BOOK-READ-1）：启动若上次在阅读书籍，自动恢复书籍 + 阅读进度
        if _sa != "blank":
            self._restore_book()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(700)

        # v3.45.3（LINK-NAV）：链接导航队列 drain —— 独立 150ms 快轮询，
        # 避免点击链接跳转有可感知的滞后（与双栏同步滚动同量级，开销可忽略）
        self._nav_timer = QTimer(self)
        self._nav_timer.timeout.connect(self._poll_nav)
        self._nav_timer.start(150)

        # v3.29 双栏同步滚动：独立轻量定时器，非双栏时空转开销可忽略
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._poll_sync_scroll)
        self._sync_timer.start(160)

        # v3.49.1（OUT-SYNC）：大纲「当前内容」高亮随文档滚动同步（200ms 轻轮询）
        self._outline_sync_timer = QTimer(self)
        self._outline_sync_timer.timeout.connect(self._sync_outline_active)
        self._outline_sync_timer.start(200)

        self._update_title()

    # ================= UI =================
    def _init_ui(self):
        self._view = QWebEngineView(self)       # WYSIWYG 编辑视图
        # 分屏用的源码 / 预览视图惰性创建（见 _ensure_dual_views）：
        # 每个视图都要加载 editor.html + KaTeX，启动只加载当前需要的 1 个可明显提速
        self._view_src = None
        self._view_prev = None
        self._dual_split = None

        # 自定义页面：JS prompt / alert / confirm 使用中文对话框
        self._view.setPage(EditorPage(self._view, self))
        # file:// 页面默认禁止加载远程资源（README 徽章图等显示不出来），放开
        _v = self._view
        _v.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        _v.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        _v.loadFinished.connect(lambda ok: self._on_loaded(ok, "edit"))
        _v.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), "editor.html")))
        # Typora 式中文右键菜单（替代 Chromium 默认英文菜单）
        _v.setContextMenuPolicy(Qt.CustomContextMenu)
        _v.customContextMenuRequested.connect(
            lambda pos: self._show_ctx_menu(self._view, pos))

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._view)        # 0 单栏 WYSIWYG（1 = 双栏，惰性添加）

        # 多文件标签页
        self._tabbar = _TabBar(self)
        self._tabbar.setTabsClosable(True)
        self._tabbar.setMovable(True)
        self._tabbar.setExpanding(False)
        self._tabbar.setDrawBase(False)
        self._tabbar.setCursor(Qt.PointingHandCursor)
        self._tabbar.currentChanged.connect(self._on_tab_clicked)
        self._tabbar.tabCloseRequested.connect(self._close_tab)
        self._tabbar.tabMoved.connect(self._on_tab_moved)
        # v3.38（TAB-1）：标签右键菜单（Notepad++ 对标）—— 右键先选中该标签再弹菜单
        self._tabbar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tabbar.customContextMenuRequested.connect(self._on_tab_menu)
        # v3.38（TAB-5）：中键点击标签即关闭 / 双击空白处新建标签（N++ / 浏览器对标）
        self._tabbar.installEventFilter(self)
        tab_wrap = QWidget(self)
        tab_wrap.setObjectName("tabstrip")
        tl = QHBoxLayout(tab_wrap)
        # v3.39.14（HEAD-1）：页面头对齐——左右 10px 与侧栏基准线一致；行高 42px
        # 与侧栏「文件/大纲」头行同高，页签垂直居中
        tl.setContentsMargins(12, 3, 12, 3)
        tl.addWidget(self._tabbar)
        # v3.38（TAB-9）：标签溢出下拉（N++ / VS Code 对标）—— 列出全部标签带
        # • 未保存 / 📌 固定标记，点击切换；仅在总宽超出可视宽度时启用
        self._btn_tb_more = QToolButton(tab_wrap)
        self._btn_tb_more.setObjectName("tbMore")
        self._btn_tb_more.setText("»")
        self._btn_tb_more.setAutoRaise(True)
        self._btn_tb_more.setFixedWidth(24)
        self._btn_tb_more.setCursor(Qt.PointingHandCursor)
        self._btn_tb_more.clicked.connect(self._show_tb_more_menu)
        self._btn_tb_more.setEnabled(False)
        tl.addWidget(self._btn_tb_more)
        tl.addStretch(1)
        tab_wrap.setFixedHeight(40)  # HEAD-2：与侧栏头行同高（40px，紧凑适中）

        right = QWidget(self)
        right.setObjectName("contentArea")   # v3.44.3（DESIGN01）：编辑区显式底色
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(tab_wrap)
        rl.addWidget(self._stack, 1)

        self._sidebar = Sidebar(self)
        # v3.49.x（OUT-SYNC）：apply_theme 在 __init__ 早期（创建侧栏之前）已跑过一次，
        # 彼时 self._sidebar 尚未存在 → set_outline_active_theme 被 hasattr 跳过，
        # 导致启动后激活项背景始终回退系统 Highlight、且换肤前的强调浅底从未初始化。
        # 故在侧栏创建后立即补一次，确保激活项高亮底色随主题正确初始化。
        if hasattr(self._sidebar, "set_outline_active_theme"):
            self._sidebar.set_outline_active_theme(self._theme)
        # 应用持久化的侧栏设置：大纲显示级别 / 分节字数开关 / 文件列表显示模式
        self._sidebar.set_outline_level(self._outline_level)
        self._sidebar.set_outline_words(self._outline_words)
        self._sidebar.set_file_mode(self._file_list_mode)
        # v3.44.34（BOOK-1）：书籍页签信号接线
        self._sidebar.bookEntryOpen.connect(self.open_book_link)
        # v3.45.3（BOOK-6）：书籍树选中章节 → 状态栏显示对应文件名
        self._sidebar.bookEntrySelected.connect(self.on_book_entry_selected)
        self._sidebar.bookStructureChanged.connect(self.on_book_structure_changed)
        self._sidebar.bookExportRequested.connect(self.on_book_export_requested)
        self._sidebar.bookRevealRequested.connect(self.on_book_reveal)
        self._sidebar.bookCloseRequested.connect(self.close_book)
        # v3.45.7（BOOK-TOC）：书籍右键「编辑目录」→ 以普通文档打开 summary.md
        self._sidebar.bookSummaryEditRequested.connect(self._open_summary_for_edit)
        # v3.46（TOC-SEL）：书籍右键「插入目录」→ 为整本书生成并插入完整目录
        self._sidebar.bookTocInsertRequested.connect(self.insert_toc_for_book)
        # v3.47.1（BOOK-TOC）：书籍右键「删除目录」→ 移除 summary 项 + 目录页文件
        self._sidebar.bookTocRemoveRequested.connect(self.remove_toc_for_book)
        # v3.45.8（REQ3#9）：导航跳转历史栈状态
        self._nav_stack = []   # 历史条目：{"path": 绝对路径, "ratio": 0~1 滚动比例}
        self._nav_idx = -1     # 当前位置指针
        self._nav_lock = False  # 恢复跳转时加锁，防止重入 / 产生新历史
        self._nav_seeded = False
        split = QSplitter(Qt.Horizontal, self)
        split.setObjectName("mainSplit")   # v3.44.4（DESIGN01 修复）：主分栏手柄着 chrome_line 分隔线
        split.setChildrenCollapsible(False)
        split.addWidget(self._sidebar)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setHandleWidth(1)
        self.setCentralWidget(split)
        self.setAcceptDrops(True)
        # v3.48.35（DROP-MD）：应用级 .md 拖放（子控件吞不掉，见方法注释）
        self._install_app_drop_filter()

        # v3.46（SoloMD P1）：AI 助手停靠面板（默认隐藏，经「视图 → AI 助手」开启）
        self._ai_bridge = AIBridge(self)
        self._ai_dock = QDockWidget("AI 助手", self)
        self._ai_dock.setObjectName("aiDock")
        self._ai_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        # v3.48.23（AI-UI）：面板宽度缩减 1/4（460 → 345），更紧凑；
        # v3.48.37（AI-UI-2）：再缩 1/6（345 → 288）—— 345 在 1080p 下与正文
        # 抢宽度明显，288 仍能放下一行按钮 + 消息气泡。
        # 首次展开时按新宽度定型（见 _show_ai_dock），避免沿用旧残留宽度。
        self._ai_dock.setMinimumWidth(288)
        self._ai_dock_width_sized = False
        self._ai_pane = ai_pane.AIPane(self._ai_bridge)
        self._ai_dock.setWidget(self._ai_pane)
        self.addDockWidget(Qt.RightDockWidgetArea, self._ai_dock)
        self._ai_dock.hide()
        # v3.47.5（REQ3）：移除面板标题栏的「关闭 / 浮动」按钮（仅保留可移动），
        # 隐藏面板改由「视图 → 显示 / 隐藏 AI 助手」菜单或顶栏图标按钮控制。
        self._ai_dock.setFeatures(QDockWidget.DockWidgetMovable)
        # v3.47.3：AI 面板显示时自动收起左侧栏（专注书写 / 对话），隐藏时恢复；
        # 用 visibilityChanged 统一收口「显示 / 隐藏」两条路径（菜单、顶栏按钮、关闭钮）。
        self._ai_collapsed_sidebar = False
        self._ai_dock.visibilityChanged.connect(self._on_ai_dock_visibility)

        self._status = QLabel(T("就绪", "Ready"))
        self.statusBar().addWidget(self._status)
        # v3.29d（B3）：临时提示独立区域（右侧、3 秒自动还原），不再覆盖左侧常驻信息
        self._toast = QLabel("")
        self._toast.setStyleSheet("padding-right: 12px;")
        self.statusBar().addPermanentWidget(self._toast)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast.setText(""))
        # v3.30.10（HP-1）：状态栏「当前块」——光标进入任何块即显示类型 / 标题级别，
        # （数据随 getCaretLineCol 轮询通道返回）
        self._blktype = QLabel("")
        self._blktype.setStyleSheet("padding-right: 4px;")
        self.statusBar().addPermanentWidget(self._blktype)
        # v3.40（UI-R7①）：状态栏六格 —— 消息区 | 模式 | 字数 | 行,列 | 缩放 | 保存态
        # （UI-SPEC PS-03；模式格点击循环切换、缩放格点击重置 100%）
        self._cell_mode = QLabel(T("写作", "Writing"))
        self._cell_mode.setToolTip(T("当前模式 · 点击循环切换（写作 → 源码 → 分屏）", "Current mode · click to cycle (Writing → Source → Split)"))
        self._cell_mode.setCursor(Qt.PointingHandCursor)
        self._cell_mode.mousePressEvent = lambda _e: self.cycle_mode()
        self.statusBar().addPermanentWidget(self._cell_mode)
        self._count = QLabel(T("字数 0 · 约 0 分钟", "Words 0 · ~0 min"))
        self._count.setCursor(Qt.PointingHandCursor)
        self._count.setToolTip(T("字数统计（中文按字 / 英文按词）· 点击查看详情", "Word count (Chinese by char / English by word) · click for details"))
        self._count.installEventFilter(self)
        self.statusBar().addPermanentWidget(self._count)
        self._pos = QLabel(T("行 1 · 列 1", "Line 1 · Col 1"))
        self._pos.setToolTip(T("光标所在行 / 列（Ctrl+G 可跳转到指定行）", "Cursor line / column (Ctrl+G to jump to a line)"))
        self.statusBar().addPermanentWidget(self._pos)
        self._cell_zoom = QLabel("100%")
        self._cell_zoom.setToolTip(T("编辑区缩放 · 点击重置 100%（Ctrl+= 放大 / Ctrl+- 缩小）", "Editor zoom · click to reset 100% (Ctrl+= zoom in / Ctrl+- zoom out)"))
        self._cell_zoom.setCursor(Qt.PointingHandCursor)
        self._cell_zoom.mousePressEvent = lambda _e: self.set_zoom(1.0)
        self.statusBar().addPermanentWidget(self._cell_zoom)
        self._cell_save = QLabel(T("✓ 已保存", "✓ Saved"))
        self._cell_save.setToolTip(T("当前文档保存状态（自动保存开启时停留时间极短）", "Current document save state (very brief when auto-save is on)"))
        self._save_state = ""
        self.statusBar().addPermanentWidget(self._cell_save)
        # v3.29d（UX #26）：状态栏常驻「⌘ 命令」入口，提高命令面板发现率
        self._cmd_entry = QLabel(T("⌘ 命令", "⌘ Command"))
        self._cmd_entry.setToolTip(T("打开命令面板（Ctrl+Shift+P）", "Open command palette (Ctrl+Shift+P)"))
        self._cmd_entry.setCursor(Qt.PointingHandCursor)
        self._cmd_entry.setStyleSheet("padding: 0 8px;")
        self._cmd_entry.mousePressEvent = lambda _e: self.show_command_palette()
        self.statusBar().addPermanentWidget(self._cmd_entry)
        # v3.40（UI-R7②）：状态栏可见性持久化（视图 → 显示 / 隐藏状态栏）
        self.statusBar().setVisible(
            self._settings.value("ui/statusbarVisible", True, type=bool))
        self._update_save_cell()
        self._cell_zoom.setText(f"{int(round(self._zoom * 100))}%")

    def _ensure_dual_views(self):
        """首次进入分屏时才创建源码 / 预览视图并加载编辑器页面（启动提速）。"""
        if self._view_src is not None:
            return
        self._view_src = QWebEngineView(self)
        self._view_prev = QWebEngineView(self)
        for role, v in (("src", self._view_src), ("prev", self._view_prev)):
            v.setPage(EditorPage(v, self))
            v.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            v.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            v.loadFinished.connect(lambda ok, r=role: self._on_loaded(ok, r))
            v.setContextMenuPolicy(Qt.CustomContextMenu)
            v.customContextMenuRequested.connect(
                lambda pos, view=v: self._show_ctx_menu(view, pos))
            _ed_url = QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), "editor.html"))
            _ed_url.setQuery("dual")   # v3.44.9（SPLIT-EDGE）：分屏视图带 ?dual 触发 body.dual 贴边
            v.load(_ed_url)

        self._dual_split = QSplitter(Qt.Horizontal, self)
        self._dual_split.setChildrenCollapsible(False)
        self._dual_split.addWidget(self._view_src)
        self._dual_split.addWidget(self._view_prev)
        self._dual_split.setStretchFactor(0, 1)
        self._dual_split.setStretchFactor(1, 1)
        self._dual_split.setHandleWidth(1)
        self._stack.addWidget(self._dual_split)  # index 1

        # v3.38（SYN-3）：预览 → 源码反向同步的循环防护 / 变更检测状态
        self._sync_ts_src2prev = 0.0   # 最近一次程序性滚动预览（源码同步所致）的时刻
        self._sync_ts_prev2src = 0.0   # 最近一次用户滚动预览触发反向同步的时刻
        self._sync_manual_ts = 0.0     # v3.49.1（OUT-SYNC）：手动跳转后抑制自动同步的时刻
        self._last_src_pair = None     # 上次发给预览的 (块号, frac)——无变化不重发
        self._last_prev_pair = None    # 上次从预览收到并转发的 (块号, frac)

    # ================= 工具栏 + 菜单 =================
    def _init_menu_toolbar(self):
        # v3.41.3（UI-R7 校准）：QToolBar 条目间距由样式 PM_ToolBarItemSpacing 控制
        # （QSS spacing/margin 对 QToolBar 均不生效，实测 _m173），代理样式对齐设计稿 gap 2px
        class _SideTBStyle(QProxyStyle):
            def pixelMetric(self, pm, option=None, widget=None):
                if pm == QStyle.PM_ToolBarItemSpacing and widget is not None \
                        and widget.objectName() == "sideTB":
                    return 2
                return super().pixelMetric(pm, option, widget)

        # ---- 左侧竖向工具栏：只保留文件级高频操作，统一线性图标 ----
        tb = QToolBar(T("主工具栏"), self)
        self._main_tb = tb
        tb.setObjectName("sideTB")
        tb.setStyle(_SideTBStyle(tb.style()))
        tb.setMovable(False)
        tb.setOrientation(Qt.Vertical)
        tb.setIconSize(QSize(20, 20))
        # v3.39.14（HEAD-2）：三列比例调优——左按钮列钉宽 42px（原 ~53px），
        # 层次感：窄按钮列(42) : 侧栏(224) : 内容区(其余)
        tb.setFixedWidth(46)
        self.addToolBar(Qt.LeftToolBarArea, tb)
        self._tool_tb = tb

        def v_sep():
            # v3.41.3：分组分隔线 24x1（对齐设计稿 .vsep 24px 宽居中；
            # QSS ::separator 宽度/margin 同样不生效，改用受控 QFrame）
            s = QFrame(tb)
            s.setObjectName("sideSep")
            s.setFixedSize(24, 1)
            tb.addWidget(s)

        # v3.38（TB-1）：工具栏可被隐藏（右键菜单 / 视图菜单 / 快捷键），而隐藏后原本
        # 没有任何恢复入口 —— 连工具栏顶部的侧栏开关也一起消失，等同死局。
        # 这里在窗口左侧边缘常驻一个展开按钮，只在工具栏隐藏时显形、始终置顶可点。
        # v3.44.9（TB-EXP）：原文字「»」钮改为线性双右箭头矢量图标（icon_toolbar_expand），
        # 与整体线性图标风格统一，去除老式文字钮观感。
        self._btn_tb_show = QToolButton(self)
        self._btn_tb_show.setObjectName("tbExpand")
        self._btn_tb_show.setIcon(icon_toolbar_expand(16))
        self._btn_tb_show.setIconSize(QSize(16, 16))
        self._btn_tb_show.setToolTip(T("展开工具栏（视图 → 显示 / 隐藏工具栏，或 Ctrl+Shift+B）", "Expand toolbar (View → Show/Hide Toolbar, or Ctrl+Shift+B)"))
        self._btn_tb_show.setCursor(Qt.PointingHandCursor)
        self._btn_tb_show.setAutoRaise(True)
        self._btn_tb_show.setFixedSize(20, 58)
        self._btn_tb_show.clicked.connect(lambda: self.set_toolbar_visible(True))
        self._btn_tb_show.hide()
        self._btn_tb_show.raise_()

        def tb_act(icon, tooltip, slot):
            a = QAction(self)
            a.setIcon(icon)
            a.setProperty("zh_tip", tooltip)
            a.setToolTip(T(tooltip))
            a.triggered.connect(slot)
            tb.addAction(a)
            # v3.39.14（HEAD-2）：三列比例调优——按钮统一 36px，左列收窄到 ~42px
            # v3.41.3（UI-R7 校准）：按钮 36x32 对齐设计稿 .vbtn（36x32）；
            # 间隙 2px 由 styles.py 的 QSS margin 驱动（QToolBar 无 spacing API）
            wd = tb.widgetForAction(a)
            if wd is not None:
                wd.setFixedSize(38, 34)
            return a

        # 顶部：侧边栏开关（v3.40 UI-R7③：R3.5 定稿——「«」文本钮统一为线性侧栏面板图标）
        self._btn_side = QToolButton(tb)
        self._btn_side.setAutoRaise(True)
        self._btn_side.setIcon(icon_sidepanel(20))
        self._btn_side.setIconSize(QSize(20, 20))
        self._btn_side.setToolTip(T("收起侧边栏 (Ctrl+Shift+L)"))
        self._btn_side.setCursor(Qt.PointingHandCursor)
        self._btn_side.setFixedSize(38, 34)  # v3.44.5（DESIGN01）：对齐设计稿 .vbtn 38x34
        self._btn_side.clicked.connect(self.toggle_sidebar)
        tb.addWidget(self._btn_side)
        v_sep()

        tb_act(icon_new(), "新建 (Ctrl+N)", self.new_file)
        tb_act(icon_open(), "打开 (Ctrl+O)", lambda: self.open_file(None))
        tb_act(icon_save(), "保存 (Ctrl+S)", self.save_file)
        v_sep()
        # 撤销 / 重做：快捷键仍由编辑菜单注册，这里只放图标按钮
        tb_act(icon_undo(), "撤销 (Ctrl+Z)", lambda: self._js_active('window.cmd("undo")'))
        tb_act(icon_redo(), "重做 (Ctrl+Y)", lambda: self._js_active('window.cmd("redo")'))
        # v3.45.8（REQ3#9）：导航后退 / 前进（跳转历史）
        self._nav_back_act = tb_act(icon_nav_back(), "后退 (Alt+Left)", lambda: self._nav_go(-1))
        self._nav_forward_act = tb_act(icon_nav_forward(), "前进 (Alt+Right)", lambda: self._nav_go(1))
        self._nav_update_buttons()
        v_sep()
        tb_act(icon_find(), "查找 / 替换 (Ctrl+F)", lambda: self.show_find(False))
        v_sep()
        # v3.40（UI-R7④）：R4 定稿——历史版本前置为高频安全操作（工具菜单保留同源入口）
        tb_act(icon_history(), "历史版本 (Ctrl+Shift+H)", self.show_history)
        # v3.40（UI-R7⑤）：R4 定稿——设置齿轮上移，紧随历史版本之后（不再沉底）；
        # 原模式循环钮移除，模式切换改由菜单栏右端分段钮承担（单击直切）
        tb_act(icon_settings(), "系统设置", self.show_settings)
        # v3.38（TB-1）：工具栏被隐藏（右键菜单 / 视图菜单 / 快捷键）→ 同步边缘展开按钮。
        # 注意只同步 UI、不写 QSettings：窗口关闭 / 隐藏时 Qt 也会给子控件发 HideToParent，
        # 若在此落盘会把「关闭程序」误记成「用户隐藏了工具栏」。
        tb.visibilityChanged.connect(lambda _v=False: self._sync_toolbar_state(persist=False))

        self._shortcut_acts = {}   # 动作名 -> QAction（设置->快捷键设置 可配置）
        self._shortcut_defs = []   # [(分组, [(动作名, 默认快捷键), ...]), ...]

        self._build_menubar()

        # ---- v3.40（UI-R7⑩）：菜单栏右端「视图状态区」（R5 定稿）——
        #      ◉ 专注 / ≡ 打字机 快捷开关 + 写作|源码|分屏 分段钮（单击直切）。
        #      状态唯一源 = self._mode / _typewriter / _focus（性能红线：单向订阅，无双向广播）
        corner = QWidget(self)
        corner.setObjectName("vsz")
        cl = QHBoxLayout(corner)
        cl.setContentsMargins(0, 0, 6, 0)
        cl.setSpacing(2)

        def _qk(text, tip, slot):
            b = QToolButton(corner)
            b.setProperty("zh", text)
            b.setText(T(text))
            b.setObjectName("qk")
            b.setProperty("zh_tip", tip)
            b.setToolTip(T(tip))
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.setFixedHeight(22)
            b.clicked.connect(slot)
            cl.addWidget(b)
            return b

        self._qk_focus = _qk("◉ 专注", "专注模式（隐藏侧栏 / 工具栏，居中书写）",
                             self.toggle_focus)
        self._qk_tw = _qk("≡ 打字机", "打字机模式（当前行恒居屏幕中部）",
                          self.toggle_typewriter)
        self._qk_sep = QLabel(corner)
        self._qk_sep.setFixedSize(1, 14)
        cl.addWidget(self._qk_sep)
        # v3.44.6：模式分段钮（写作|源码|分屏）重构为「立体分段控件」——
        # 外层圆角容器（浮雕渐变 + 描边）包裹三钮，钮间 1px 分隔线；选中段 accent 实心填充（凸起激活段）。
        # 与左侧 专注/打字机 的「扁平」风格形成对比，整体仍属同一套现代经典语言。
        self._seg_group = QButtonGroup(corner)
        self._seg_group.setExclusive(True)
        self._seg_btns = {}
        seg_group = QWidget(corner)
        seg_group.setObjectName("segGroup")
        seg_group.setAttribute(Qt.WA_StyledBackground, True)  # 普通 QWidget 需此属性才会绘制 QSS 背景/边框（立体容器）
        sgl = QHBoxLayout(seg_group)
        sgl.setContentsMargins(1, 1, 1, 1)
        sgl.setSpacing(0)
        self._seg_divs = []
        for i, (mid, label, tip) in enumerate((
            ("edit", "写作", "写作模式（所见即所得）"),
            ("src", "源码", "源码模式（直接编辑 Markdown 源码）"),
            ("dual", "分屏", "分屏模式（左侧源码 · 右侧实时预览，Ctrl+Shift+D）"),
        )):
            if i > 0:
                dv = QLabel(seg_group)
                dv.setObjectName("segDiv")
                dv.setFixedSize(1, 14)
                sgl.addWidget(dv)
                self._seg_divs.append(dv)
            b = QToolButton(seg_group)
            b.setObjectName("seg")
            b.setProperty("zh", label)
            b.setText(T(label))
            b.setProperty("zh_tip", tip)
            b.setToolTip(T(tip))
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
            b.setFixedHeight(18)
            b.clicked.connect(lambda _=False, m=mid: self._set_mode(m))
            self._seg_group.addButton(b)
            self._seg_btns[mid] = b
            sgl.addWidget(b)
        self._seg_group_widget = seg_group
        seg_group.setFixedHeight(24)  # v3.44.28 RIBBON-14：容器仅略高于 18px 按钮
        cl.addWidget(seg_group)

        # v3.47.5（REQ3）：以线性图标按钮替代文字「AI 助手」，节省顶栏空间、
        # 与左侧扁平图标风格一致；点击展开 / 收起 AI 助手面板（默认连接本地 Ollama）。
        self._btn_ai = QToolButton(corner)
        self._btn_ai.setObjectName("aiCornerBtn")
        self._btn_ai.setIcon(icon_ai(18))
        self._btn_ai.setIconSize(QSize(18, 18))
        self._btn_ai.setToolTip(T("AI 助手（点击展开 / 收起，默认连接本地 Ollama）"))
        self._btn_ai.setCursor(Qt.PointingHandCursor)
        self._btn_ai.setAutoRaise(True)
        self._btn_ai.setFixedSize(26, 24)
        self._btn_ai.clicked.connect(self._toggle_ai_dock)
        cl.addWidget(self._btn_ai)

        self.menuBar().setCornerWidget(corner, Qt.TopRightCorner)
        self._vsz_corner = corner
        self._qk_focus.setChecked(self._focus)
        self._qk_tw.setChecked(self._typewriter)
        self._seg_btns[self._mode].setChecked(True)
        self._apply_chrome_styles()

        # v3.38（TB-1）：恢复上次的工具栏可见性（隐藏 → 同步显形边缘展开按钮）
        self.set_toolbar_visible(
            self._settings.value("ui/toolbarVisible", True, type=bool), toast=False)

    # ---- v3.38（TB-1）：工具栏展开按钮的摆放与右键菜单 ----
    def _place_tb_expand_btn(self):
        """把边缘展开按钮摆到左侧工具栏原本的顶部位置（菜单栏下方）。"""
        b = getattr(self, "_btn_tb_show", None)
        if b is None:
            return
        top = self.menuBar().height() if self.menuBar() is not None else 0
        b.move(2, top + 18)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_tb_expand_btn()
        self._update_tb_more()   # v3.38（TAB-9）：窗口缩放重算标签溢出态

    def createPopupMenu(self):
        """工具栏 / 菜单栏右键菜单：只给「显示 / 隐藏工具栏」一项。

        复用视图菜单同一个 QAction，避免出现两套互不同步的开关（默认实现只给
        QToolBar 自带的 toggleViewAction，取消勾选后即无法找回）。
        """
        m = QMenu(self)
        act = getattr(self, "_act_toolbar", None)
        if act is not None:
            m.addAction(act)
        return m

    def _set_mmd_theme(self, val):
        """v3.30.19（MMD-7）/ v3.34（MMD-11）：全局图表主题切换。

        持久化 QSettings.mmdTheme 并下发全部已加载视图；旧版原生主题值
        （default/dark/forest/neutral）先归一化到新主题，保证升级无感。
        设置面板下拉与图表块右键子菜单共用本方法，两处状态天然一致。"""
        val = MMD_LEGACY.get(val, val) or ""
        self._settings.setValue("mmdTheme", val)
        self._js_all(f"window.setMmdTheme({js(val)})")
        lbl = MMD_THEME_LABELS.get(val, "")
        self.show_status(T(f"图表主题：{lbl or val}", f"Chart theme: {lbl or val}") if val else "图表主题已更新（跟随界面主题）")

    def _js_all(self, code):
        """对全部已加载的编辑器视图执行 JS。"""
        for role, view in (("edit", self._view), ("src", getattr(self, "_view_src", None)),
                           ("prev", getattr(self, "_view_prev", None))):
            st = self._vstate.get(role)
            if view is not None and st and st.get("loaded"):
                self._js_view(view, code)

    def _build_menubar(self):
        """构建（或重建）菜单栏。语言切换时清空后重跑即可即时刷新。"""
        self._shortcut_acts = {}
        self._shortcut_defs = []
        # ---- 文件菜单 ----
        m_file = self.menuBar().addMenu(T("文件") + "(&F)")
        self._reg_act("文件", "新建", "Ctrl+N", self.new_file, menu=m_file)
        # v3.44.36（BOOK-4）：新建书籍紧随「新建」之后（同类新建操作相邻）
        self._reg_act("文件", "新建书籍…", None, self.create_new_book, menu=m_file)
        self._reg_act("文件", "打开…", "Ctrl+O", lambda: self.open_file(None), menu=m_file)
        self._reg_act("文件", "打开文件夹…", None, self.open_folder, menu=m_file)
        # v3.44.34（BOOK-1）：书籍模式入口
        self._reg_act("文件", "打开书籍…", None, self.open_book, menu=m_file)
        # v3.46（SoloMD P2）：Excel/CSV 表格导入（对话框选文件 → 光标处插入 Markdown 表格）
        self._reg_act("文件", "导入表格…", None, self.import_table, menu=m_file)
        m_recent = self._recent_menu = m_file.addMenu(T("最近文件"))
        m_recent.aboutToShow.connect(self._rebuild_recent_menu)
        m_file.addSeparator()
        self._reg_act("文件", "保存", "Ctrl+S", self.save_file, menu=m_file)
        self._reg_act("文件", "另存为…", "Ctrl+Shift+S", self.save_file_as, menu=m_file)
        # v3.38（TAB-6）：多文档批量保存（只保存「有路径且已修改」的标签，未命名不批量弹窗）
        self._reg_act("文件", "全部保存", "Ctrl+Alt+S", self.save_all, menu=m_file)
        self._reg_act("文件", "关闭标签页", "Ctrl+W", lambda: self._close_tab(self._cur), menu=m_file)
        # v3.38（TAB-B）：走 _close_all_tabs（跳过固定标签 + 未保存汇总确认 + 状态栏反馈）
        self._reg_act("文件", "关闭所有标签", None,
                      self._close_all_tabs, menu=m_file)
        # v3.38（TAB-3）：重新打开刚关闭的标签（可连按逐个回溯）。
        # 浏览器习惯是 Ctrl+Shift+T，但该组合在本工程已属「插入表格」（v3.31 起），
        # 故改用 Ctrl+Alt+T，避免抢键。
        self._reg_act("文件", "重新打开关闭的标签", "Ctrl+Alt+T", self._reopen_closed_tab, menu=m_file)
        m_file.addSeparator()
        # v3.40（UI-R7⑥）：R6/3.2 定稿——导出 5 项收拢为「导出」子菜单（Word/WPS 惯例），
        # 文件菜单只留文档生命周期
        m_export = m_file.addMenu(T("导出"))
        self._reg_act("文件", "导出 HTML…", None, self.export_html, menu=m_export)
        self._reg_act("文件", "导出 PDF…（含书签）", None, self.export_pdf, menu=m_export)
        self._reg_act("文件", "导出 Word (docx)…", None, self.export_docx, menu=m_export)
        self._reg_act("文件", "导出 EPUB…", None, self.export_epub, menu=m_export)
        self._reg_act("文件", "导出图片 (PNG)…", None, self.export_png, menu=m_export)
        # v3.32（P1-2②）：「复制为 HTML」是中文用户最高频交付动作（随导出组收拢）
        a = QAction(T("复制为 HTML（公众号 / Word 富文本）"), self)
        a.triggered.connect(self.copy_as_html)
        m_export.addAction(a)
        m_file.addSeparator()
        self._reg_act("文件", "退出", "Ctrl+Q", self.close, menu=m_file)

        # ---- 编辑菜单（剪贴板操作由 Web 内核原生处理，不注册全局快捷键）----
        m_edit = self.menuBar().addMenu(T("编辑") + "(&E)")
        self._reg_act("编辑", "撤销", "Ctrl+Z", lambda: self._js_active('window.cmd("undo")'), menu=m_edit)
        self._reg_act("编辑", "重做", "Ctrl+Y", lambda: self._js_active('window.cmd("redo")'), menu=m_edit)
        m_edit.addSeparator()
        for label, act_name in (("剪切", QWebEnginePage.Cut), ("复制", QWebEnginePage.Copy),
                                ("粘贴", QWebEnginePage.Paste)):
            a = QAction(T(label), self)
            a.triggered.connect(lambda _=False, x=act_name: self._page_action(x))
            m_edit.addAction(a)
        a = QAction(T("全选"), self)
        a.triggered.connect(lambda: self._page_action(QWebEnginePage.SelectAll))
        m_edit.addAction(a)
        # v3.32（P1-2②）：「复制为 HTML」已提级到文件菜单（此处不再重复）
        m_edit.addSeparator()
        self._reg_act("编辑", "查找…", "Ctrl+F", lambda: self.show_find(False), menu=m_edit)
        self._reg_act("编辑", "替换…", "Ctrl+H", lambda: self.show_find(True), menu=m_edit)
        self._reg_act("编辑", "转到行…", "Ctrl+G", self.goto_line, menu=m_edit)
        self._reg_act("编辑", "在文件夹中搜索…", "Ctrl+Shift+F", self.show_search,
                      menu=m_edit)  # v3.24：打开「查找」对话框的「全局搜索」页签
        # Ctrl+/ 唤起块菜单（空块时等价于 "/" 插入菜单）
        self._reg_act("编辑", "块菜单", "Ctrl+/",
                      lambda: self._js_active("window.openBlockMenu ? window.openBlockMenu() : null"),
                      menu=m_edit)
        # v3.48.15（MC-3）：多光标 —— Ctrl+D 选下一个相同词（Alt+点击增删光标 / Esc 退出）
        self._reg_act("编辑", "选择下一个相同词", "Ctrl+D",
                      lambda _=False: self._fmt("selnext"), menu=m_edit)
        m_edit.addSeparator()
        # P1-3 命令面板
        self._reg_act("编辑", "命令面板…", "Ctrl+Shift+P", self.show_command_palette, menu=m_edit)

        # ---- 格式命令：不再单设菜单（行菜单 / 斜杠菜单 / 快捷键已覆盖），
        #      仍注册为隐藏动作，使快捷键生效并可在"设置->快捷键设置"中修改 ----
        for _name, _seq, _cmd in (
            ("加粗", "Ctrl+B", "bold"), ("斜体", "Ctrl+I", "italic"),
            ("删除线", "Ctrl+Shift+X", "strike"), ("行内代码", "Ctrl+E", "code"),
            ("标题 1", "Ctrl+1", "h1"), ("标题 2", "Ctrl+2", "h2"),
            ("标题 3", "Ctrl+3", "h3"), ("正文", "Ctrl+0", "p"),
            ("引用", "Ctrl+Shift+Q", "quote"),
            ("插入表格", "Ctrl+Shift+T", "table"), ("插入代码块", "Ctrl+Shift+K", "fence"),
            ("插入数学公式", "Ctrl+Shift+M", "math"), ("插入分割线", "Ctrl+Shift+-", "hr"),
        ):
            self._reg_act("格式", _name, _seq, lambda _=False, c=_cmd: self._fmt(c))

        # ---- 视图菜单 ----
        m_view = self.menuBar().addMenu(T("视图") + "(&V)")
        # 三种模式：互斥单选（与左侧工具栏按钮联动）
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_acts = {}
        _mode_seq = {"edit": None, "src": None, "dual": "Ctrl+Shift+D"}
        # （Ctrl+/ 已分配给「块菜单」，源码模式经左侧模式按钮或菜单切换）
        for mode_id, _icon, label, _desc in MODES:
            act = self._reg_act("视图", label, _mode_seq[mode_id],
                                lambda _=False, m=mode_id: self._set_mode(m),
                                menu=m_view, checkable=True)
            self._mode_group.addAction(act)
            self._mode_acts[mode_id] = act
        self._mode_acts["edit"].setChecked(True)
        m_view.addSeparator()
        self._act_sidebar = self._reg_act("视图", "显示 / 隐藏侧边栏", "Ctrl+Shift+L",
                                          self.toggle_sidebar, menu=m_view, checkable=True)
        self._act_sidebar.setChecked(True)
        # v3.38（TB-1）：主工具栏显示 / 隐藏（隐藏时左侧边缘常驻展开按钮，杜绝「无法恢复」）
        # v3.38（TAB-3）：默认快捷键由 TB-1 初版的 Ctrl+Shift+T 改为 Ctrl+Shift+B ——
        # Ctrl+Shift+T 早已被「插入表格」（格式命令，v3.31 起）占用，不能再抢。
        self._act_toolbar = self._reg_act("视图", "显示 / 隐藏工具栏", "Ctrl+Shift+B",
                                          self.toggle_toolbar, menu=m_view, checkable=True)
        self._act_toolbar.setChecked(True)
        # v3.47.5（REQ1）：状态栏 与 AI 助手 互斥（不可同时显示），与「侧边栏 / 工具栏」
        # 平级展示于视图菜单（不再收纳进「显示 / 隐藏」子菜单）。AI 面板宽度随之加大
        # 以利用互斥获得更大气的布局（见 _ai_dock 构造）。
        self._act_statusbar = self._reg_act(
            "视图", "显示 / 隐藏状态栏", None,
            self.toggle_statusbar, menu=m_view, checkable=True)
        self._act_statusbar.setChecked(
            self._settings.value("ui/statusbarVisible", True, type=bool))
        # v3.47.5（REQ1）：AI 助手入口与状态栏平级（替代原顶层「AI 助手」/ 子菜单），
        # 二者互斥；原「AI 连接设置…」菜单项已移除 —— 连接面板仍由 AI 面板内
        # 「连接设置」按钮唤起（bridge.open_connection → open_ai_connection）。
        self._act_ai = self._reg_act(
            "视图", "显示 / 隐藏 AI 助手", None,
            self._toggle_ai_dock, menu=m_view, checkable=True)
        self._act_ai.setChecked(False)
        m_view.addSeparator()
        # v3.45.8（REQ3#9）：导航后退 / 前进（跳转历史栈）
        self._reg_act("视图", "后退", "Alt+Left", lambda: self._nav_go(-1), menu=m_view)
        self._reg_act("视图", "前进", "Alt+Right", lambda: self._nav_go(1), menu=m_view)
        # ---- v3.43.0（VIEW-REF）：条目文案与分组对齐设计稿 02_视图菜单 ----
        m_view.addSeparator()
        self._reg_act("视图", "文件列表页签", "Ctrl+Shift+E", lambda: self._show_sidebar_tab(0), menu=m_view)
        self._reg_act("视图", "大纲页签", "Ctrl+Shift+O", lambda: self._show_sidebar_tab(1), menu=m_view)
        self._reg_act("视图", "反向链接页签", "Ctrl+Alt+B", lambda: self._show_sidebar_tab(Sidebar.TAB_BACKLINKS), menu=m_view)
        m_view.addSeparator()
        # v3.38（TAB-4）：上一 / 下一标签页（Ctrl+PgUp / Ctrl+PgDn，N++ 与 VS Code 同款）
        self._reg_act("视图", "上一标签页", "Ctrl+PgUp", lambda: self._cycle_tab(-1), menu=m_view)
        self._reg_act("视图", "下一标签页", "Ctrl+PgDown", lambda: self._cycle_tab(1), menu=m_view)
        # v3.38（TAB-8）：Ctrl+Tab MRU 快切面板（松开 Ctrl 或回车确认，Esc 取消）
        self._reg_act("视图", "标签快切面板", "Ctrl+Tab", self._open_tab_switcher, menu=m_view)
        m_view.addSeparator()
        # v3.40（UI-R7⑧）：缩放组（参照图未含此组，v3.40 起保留；Ctrl+0 已属「正文」格式命令不能抢）
        self._reg_act("视图", "放大", "Ctrl+=", lambda: self.set_zoom(self._zoom + 0.1), menu=m_view)
        self._reg_act("视图", "缩小", "Ctrl+-", lambda: self.set_zoom(self._zoom - 0.1), menu=m_view)
        self._reg_act("视图", "重置缩放", None, lambda: self.set_zoom(1.0), menu=m_view)
        m_view.addSeparator()
        # P1-2 标题折叠（参照图：折叠组在打字机 / 专注之前）
        self._reg_act("视图", "折叠全部标题", "Ctrl+Shift+[",
                      lambda: self.fold_all_headings(True), menu=m_view)
        self._reg_act("视图", "展开全部标题", "Ctrl+Shift+]",
                      lambda: self.fold_all_headings(False), menu=m_view)
        m_view.addSeparator()
        self._act_typewriter = self._reg_act("视图", "打字机模式", None,
                                             self.toggle_typewriter, menu=m_view, checkable=True)
        self._act_focus = self._reg_act("视图", "专注模式", None,
                                        self.toggle_focus, menu=m_view, checkable=True)
        # v3.47.5（REQ1）：「显示 / 隐藏 AI 助手」已上移与状态栏平级（见上方视图菜单），
        # 此处不再重复注册。
        # 启动时恢复上次持久化的模式勾选状态（模式本身随页面加载 setMode 下发）
        self._act_typewriter.setChecked(self._typewriter)
        self._act_focus.setChecked(self._focus)
        m_view.addSeparator()
        self._reg_act("视图", "全屏", "F11", self.toggle_fullscreen, menu=m_view)
        # v3.34（MMD-11）：图表主题入口从视图菜单移到「设置 → 系统设置 → 外观」，
        # 与界面主题 / 字号同处一页集中配置；切换逻辑仍走 _set_mmd_theme
        self._theme_acts = {}

        # ---- 外观（v3.43.0 LOOK-1）：原「系统设置 → 外观」页整体提升为一级菜单 ----
        #      位置：视图(V) 之后、工具(T) 之前（设计稿 01~06 顶栏同序）；
        #      四个子菜单均为 QActionGroup 互斥单选 + 当前项打勾，展开时同步选中态。
        m_look = self.menuBar().addMenu(T("外观") + "(&A)")
        self._m_look = m_look
        m_look.aboutToShow.connect(self._sync_look_menu)

        # 1) 界面风格 —— 严格取自设计稿的 6 套，名称纯净（无编号 / 后缀）
        self._sm_style = m_look.addMenu(T("界面风格"))
        self._style_group = QActionGroup(self)
        self._style_group.setExclusive(True)
        self._sm_style.aboutToShow.connect(self._rebuild_style_menu)

        # 2) 主题 —— 六套，色卡图标取 THEMES 的 swatch
        self._sm_theme = m_look.addMenu(T("主题"))
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for t in styles.THEMES:
            act = QAction(T(t["label"]), self)
            act.setCheckable(True)
            act.setIcon(self._chip_icon(t.get("swatch") or "#ffffff"))
            act.triggered.connect(lambda _=False, tid=t["id"]: self.apply_theme(tid))
            self._theme_group.addAction(act)
            self._sm_theme.addAction(act)
            self._theme_acts[t["id"]] = act

        # 3) 图表风格（mermaid）—— 与图表块右键子菜单共用 QSettings.mmdTheme
        self._sm_mmd = m_look.addMenu(T("图表风格"))
        self._mmd_group = QActionGroup(self)
        self._mmd_group.setExclusive(True)
        self._mmd_acts = {}
        for _label, _val in MMD_THEMES:
            act = QAction(T(_label), self)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, v=_val: self._set_mmd_theme(v))
            self._mmd_group.addAction(act)
            self._sm_mmd.addAction(act)
            self._mmd_acts[_val] = act

        # 4) 代码风格 —— 与代码块默认配置共用 config.CODE_STYLES
        self._sm_code = m_look.addMenu(T("代码风格"))
        self._code_group = QActionGroup(self)
        self._code_group.setExclusive(True)
        self._code_acts = {}
        for _sid, _slabel in CODE_STYLES:
            act = QAction(T(_slabel), self)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, s=_sid: self.set_code_prefs(style=s))
            self._code_group.addAction(act)
            self._sm_code.addAction(act)
            self._code_acts[_sid] = act

        # v3.43.1（SET-4）：「界面风格管理…」菜单项移除 —— 管理对话框没有就地
        # 新增能力（新增 = 把风格 JSON 放进风格文件夹再刷新），单独挂一级入口
        # 价值有限；命令面板（Ctrl+Shift+P）保留「界面风格管理…」兜底，
        # show_style_manager() 方法与 StyleManagerDialog 均保留。

        # ---- 工具（v3.40 UI-R7⑨：R6 定稿「工具(T)」——版本容灾 / 批量工具 / 设置并入；
        #      3.2 迁移清单：文件菜单的版本组与批量工具、「设置」菜单整体迁入）----
        m_tool = self.menuBar().addMenu(T("工具") + "(&T)")
        self._reg_act("工具", "历史版本…", "Ctrl+Shift+H", self.show_history, menu=m_tool)
        # v3.32（P0-3）：命令面板同款「立即留档」在工具菜单也可见，主动打点
        self._reg_act("工具", "立即留档（版本快照）", None, self.manual_snapshot, menu=m_tool)
        m_tool.addSeparator()
        self._reg_act("工具", "迁移内嵌图片为文件…", None, self.migrate_embedded_images, menu=m_tool)
        # v3.32（P0-7）：本地唯一副本的最低成本容灾出口
        self._reg_act("工具", "归档整个工作区…", None, self.archive_workspace, menu=m_tool)
        m_tool.addSeparator()
        self._reg_act("工具", "系统设置…", "Ctrl+,", self.show_settings, menu=m_tool)
        self._reg_act("工具", "快捷键设置…", None, self.show_shortcut_settings, menu=m_tool)

        # ---- 帮助（始终放最后）----
        m_help = self.menuBar().addMenu(T("帮助") + "(&H)")
        # v3.38（HELP-1）：使用手册（只读渲染视图，滚动浏览全功能参考指南）
        self._reg_act("帮助", "使用手册", "F12", self._show_manual, menu=m_help)
        # v3.44.31（FIX ④）：移除「快捷键一览」F1 对话框，快捷键统一收录于《使用手册》第 10 章
        # v3.32（P0-6①）：检查更新（version.json 只提示不强升）
        self._reg_act("帮助", "检查更新…", None, self.check_update, menu=m_help)
        # v3.32（P0-5②）：复制诊断信息（版本 / 系统 / 依赖 / 最近日志）
        self._reg_act("帮助", "复制诊断信息", None, self.copy_diagnostics, menu=m_help)
        self._reg_act("帮助", "关于", None, self._about, menu=m_help)

    def _apply_language(self):
        """界面语言变更后即时刷新：菜单栏 / 工具栏提示 / 侧栏 / 顶栏分段 / 编辑器内核。"""
        self.menuBar().clear()
        self._build_menubar()
        self._retranslate_chrome()
        sb = getattr(self, "_sidebar", None)
        if sb is not None and hasattr(sb, "_retranslate"):
            sb._retranslate()
        self._push_lang_to_js()

    def _retranslate_chrome(self):
        """重翻工具栏与顶栏分段 / 快捷钮（这些控件不在菜单栏内，需单独处理）。"""
        tb = getattr(self, "_main_tb", None)
        if tb is not None:
            for act in tb.actions():
                zh = act.property("zh_tip")
                if zh is not None:
                    act.setToolTip(T(zh))
        for mid in ("edit", "src", "dual"):
            b = self._seg_btns.get(mid)
            if b is not None:
                if b.property("zh") is not None:
                    b.setText(T(b.property("zh")))
                if b.property("zh_tip") is not None:
                    b.setToolTip(T(b.property("zh_tip")))
        for b in (getattr(self, "_qk_focus", None), getattr(self, "_qk_tw", None),
                  getattr(self, "_btn_ai", None)):
            if b is not None:
                if b.property("zh") is not None:
                    b.setText(T(b.property("zh")))
                if b.property("zh_tip") is not None:
                    b.setToolTip(T(b.property("zh_tip")))
        # 侧栏开关钮（动态 tooltip：展开 / 收起）随语言重翻
        if getattr(self, "_btn_side", None) is not None:
            self._update_side_btn()

    def _push_lang_to_js(self):
        """把当前界面语言下发给 editor.html 内核（window.__setLang），覆盖三视图。"""
        code = "window.__setLang && window.__setLang(%s)" % json.dumps(get_lang())
        for role, view in (("edit", self._view), ("src", self._view_src), ("prev", self._view_prev)):
            v = view
            if v is not None and self._vstate.get(role, {}).get("loaded"):
                try:
                    self._js_view(v, code)
                except Exception:
                    pass

    def _reg_act(self, group, name, seq, slot, menu=None, checkable=False):
        """创建动作并纳入快捷键管理体系（设置 -> 快捷键设置 可查看 / 修改）。

        seq 为 None 表示无默认快捷键（动作仍登记在案）；已有用户自定义值时优先使用。
        """
        act = QAction(T(name), self)
        if checkable:
            act.setCheckable(True)
        act.triggered.connect(slot)
        if seq:
            saved = self._settings.value(f"shortcut/{name}")
            act.setShortcut(QKeySequence(saved if isinstance(saved, str) and saved else seq))
            act.setShortcutContext(Qt.ApplicationShortcut)
        if menu is not None:
            menu.addAction(act)
        else:
            self.addAction(act)   # 不进菜单也要加入窗口，快捷键才能全局生效
        self._shortcut_acts[name] = act
        for g, items in self._shortcut_defs:
            if g == group:
                items.append((name, seq))
                break
        else:
            self._shortcut_defs.append((group, [(name, seq)]))
        return act

    # ================= v3.43.0（LOOK-1）：外观菜单辅助 =================
    def _chip_icon(self, hexc):
        """菜单项色卡图标（圆角小方块）：主题取 swatch、界面风格取风格强调色。"""
        pm = QPixmap(14, 14)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(hexc or "#ffffff")))
        p.setPen(QPen(QColor("#9aa2ab"), 1))
        p.drawRoundedRect(1, 1, 12, 12, 3, 3)
        p.end()
        return QIcon(pm)

    def _rebuild_style_menu(self):
        """「外观 → 界面风格」每次展开重建：注册表可增删，菜单需跟随。"""
        cur = uistyles.active()
        for act in self._sm_style.actions():
            self._style_group.removeAction(act)
        self._sm_style.clear()
        for sid, label in uistyles.menu_styles():
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(sid == cur)
            act.setIcon(self._chip_icon(uistyles.style_accent(sid, self._theme)))
            act.setToolTip(uistyles.get_style(sid).get("desc", "") if uistyles.get_style(sid) else "")
            act.triggered.connect(lambda _=False, s=sid: self.set_uistyle(s))
            self._style_group.addAction(act)
            self._sm_style.addAction(act)

    def _sync_look_menu(self):
        """展开「外观」时同步主题 / 图表风格 / 代码风格的勾选态。

        三处状态都可能被别处改动（图表块右键主题、代码块「风格」按钮、
        命令面板、启动恢复），故以 QSettings / 主窗口当前值为准统一回写勾选。
        """
        for tid, act in self._theme_acts.items():
            act.setChecked(tid == self._theme)
        _mmd = MMD_LEGACY.get(self._settings.value("mmdTheme", "") or "",
                              self._settings.value("mmdTheme", "") or "")
        for val, act in self._mmd_acts.items():
            act.setChecked(val == _mmd)
        for sid, act in self._code_acts.items():
            act.setChecked(sid == self._code_style)

    def show_style_manager(self):
        """界面风格管理（原设置中心「外观」页的风格组，含刷新 / 文件夹 / 删除）。"""
        if not hasattr(self, "_style_dlg"):
            self._style_dlg = StyleManagerDialog(self)
        dlg = self._style_dlg
        dlg._apply_theme_qss(self._theme)
        dlg.reload()
        dlg.show()
        dlg.raise_()

    def shortcut_groups(self):
        """给快捷键设置对话框：[(分组, [动作名, ...]), ...]"""
        return [(g, [n for n, _ in items]) for g, items in self._shortcut_defs]

    def all_shortcuts(self):
        """给快捷键设置对话框：[(动作名, 默认快捷键), ...]（无默认为 None）"""
        out = []
        for _g, items in self._shortcut_defs:
            out.extend(items)
        return out

    def apply_shortcut(self, name, seq):
        """应用并持久化某个动作的快捷键（seq 为空序列表示清除）。"""
        act = self._shortcut_acts.get(name)
        if act is None:
            return
        act.setShortcut(seq)
        if isinstance(seq, QKeySequence) and not seq.isEmpty():
            self._settings.setValue(f"shortcut/{name}",
                                    seq.toString(QKeySequence.PortableText))
        else:
            self._settings.remove(f"shortcut/{name}")

    def show_shortcut_settings(self):
        if not hasattr(self, "_sc_dlg"):
            self._sc_dlg = ShortcutDialog(self)
        self._sc_dlg.show()
        self._sc_dlg.raise_()

    # ================= JS bridge =================
    def _js_view(self, view, code, callback=None):
        if callback is None:
            view.page().runJavaScript(code)
        else:
            view.page().runJavaScript(code, callback)

    def _active_role(self):
        return "src" if self._dual else "edit"

    def _active_view(self):
        return self._view_src if self._dual else self._view

    def _js_active(self, code, callback=None):
        self._js_view(self._active_view(), code, callback)

    def _doc_dir(self):
        """当前文档所在目录（绝对路径）；未保存文档返回空串。"""
        if self.file_path:
            return os.path.dirname(os.path.abspath(self.file_path))
        return ""

    def _push_doc_dir(self):
        """文档目录 / 图片模式变化后同步到全部视图（切换文档、另存为后调用）。

        只推给已加载完成的视图：页面尚未注入 editor.html 时调用会报
        “window.setDocDir is not a function”，加载完成后 _on_loaded 会自行补齐。
        """
        code_dir = js(self._doc_dir())
        code_mode = js(self._image_mode)
        for role, v in (("edit", self._view), ("src", self._view_src), ("prev", self._view_prev)):
            if v is not None and self._vstate.get(role, {}).get("loaded"):
                self._js_view(v, f"window.setDocDir({code_dir})")
                self._js_view(v, f"window.setImageMode({code_mode})")

    def _page_action(self, name):
        """对活动视图的渲染页面执行剪切 / 复制 / 粘贴 / 全选。"""
        self._active_view().page().triggerAction(name)

    def _fmt(self, cmd):
        """把格式命令派发到当前编辑视图。"""
        self._js_active(f'window.cmd("{cmd}")')

    # ================= v3.46（SoloMD P1）：AI 助手桥接 =================
    def _toggle_ai_dock(self):
        if self._ai_dock.isVisible():
            self._hide_ai_dock()
        else:
            self._show_ai_dock()

    def _show_ai_dock(self):
        """打开 AI 助手面板（统一入口：视图菜单 / 顶栏按钮 / 选中即问）。"""
        if not self._ai_dock.isVisible():
            self._ai_dock.show()
        # v3.48.23（AI-UI）：首次展开按定型宽度（宽度已缩减 1/4）；
        # v3.48.37（AI-UI-2）：定型宽度 345 → 288（再缩 1/6）。
        # 之后尊重用户手动拖拽的宽度，不再强行重置。
        if not getattr(self, "_ai_dock_width_sized", False):
            # show() 后停靠布局会把 dock 的最小宽度抬回「内容最小宽度」，
            # 此处重新压回 288 再定型，否则 resizeDocks 会被 356/460 这类
            # 旧内容宽度卡住（v3.48.37 AI-UI-2 实测）。
            self._ai_dock.setMinimumWidth(288)
            self.resizeDocks([self._ai_dock], [288], Qt.Horizontal)
            self._ai_dock_width_sized = True
        self._ai_dock.raise_()

    def _hide_ai_dock(self):
        self._ai_dock.hide()

    # v3.47.3：AI 面板显隐与左侧栏联动 —— 显示时收起侧栏、隐藏时恢复，
    # 仅当侧栏当前可见且非专注模式时才自动收起，避免与专注模式抢管侧栏。
    # v3.47.6（REQ1）：改为「AI 助手 与 侧边栏 互斥」—— 显示 AI 时收起侧栏，
    # 隐藏 AI 时恢复侧栏；**取消**原先与状态栏的互斥（状态栏由用户独立控制）。
    def _on_ai_dock_visibility(self, visible):
        # 同步菜单勾选态（菜单 / 顶栏按钮 / 关闭钮任一途径开关都更新）
        act_ai = getattr(self, "_act_ai", None)
        if act_ai is not None and act_ai.isChecked() != visible:
            act_ai.setChecked(visible)
        if getattr(self, "_focus", False):
            return
        if visible:
            # 需求1：AI 与侧边栏互斥 —— 显示 AI 时收起侧栏（不再触碰状态栏）
            if self._sidebar.isVisible() and not self._ai_collapsed_sidebar:
                self._ai_collapsed_sidebar = True
                self._sidebar.setVisible(False)
                act = getattr(self, "_act_sidebar", None)
                if act is not None:
                    act.setChecked(False)
        else:
            # 隐藏 AI 时恢复此前被收起的侧栏
            if self._ai_collapsed_sidebar:
                self._ai_collapsed_sidebar = False
                self._sidebar.setVisible(True)
                act = getattr(self, "_act_sidebar", None)
                if act is not None:
                    act.setChecked(True)

    # v3.47.2（SoloMD 对标）：打开独立 AI 连接面板（从主面板「连接设置」按钮 / 视图菜单跳转）
    def open_ai_connection(self):
        if not hasattr(self, "_ai_conn_dlg") or self._ai_conn_dlg is None:
            self._ai_conn_dlg = ai_connection.AIConnectionDialog(self._settings, self)
            self._ai_conn_dlg.form.connection_changed.connect(self._refresh_ai_status)
        self._ai_conn_dlg.show()
        self._ai_conn_dlg.raise_()

    # v3.47.2（SoloMD 对标）：连接参数变化后刷新主面板状态条
    def _refresh_ai_status(self):
        if hasattr(self, "_ai_pane") and hasattr(self._ai_pane, "refresh_status"):
            self._ai_pane.refresh_status()

    # v3.47.1（AI-BYOK）：选中即问 —— 唤起 AI 面板并带入选中文本作为上下文
    def ask_ai_about_selection(self, text=None):
        if not isinstance(text, str):
            text = ""   # 菜单 / 快捷键触发会传入 bool，此时由面板自行取选中
        self._show_ai_dock()
        if hasattr(self._ai_pane, "ask_about_selection"):
            self._ai_pane.ask_about_selection(text)

    # v3.48.0（F3-b）：右键「AI」子菜单 —— 实时取回当前选区文本
    def _ai_ctx_action(self, action_key, sel_text=None, prompt=None):
        """右键 AI 子菜单统一入口：选中=仅带上下文提问；其余=按预设提示词改写。

        sel_text 为 None 时（菜单构造期间未阻塞取选区）实时取回当前编辑器选区，
        避免右键菜单构造时同步等待 runJavaScript 引发的嵌套事件循环死锁。"""
        if not sel_text:
            self._js_active(
                "window.aiSelText()",
                lambda v: self._ai_ctx_dispatch(
                    action_key, v if isinstance(v, str) else "", prompt))
            return
        self._ai_ctx_dispatch(action_key, sel_text, prompt)

    def _ai_ctx_dispatch(self, action_key, sel_text, prompt=None):
        self._show_ai_dock()
        pane = getattr(self, "_ai_pane", None)
        if pane is None or not hasattr(pane, "ai_action"):
            return
        if action_key == "select":
            pane.ask_about_selection(sel_text)
        else:
            pane.ai_action(action_key, sel_text, prompt)

    # v3.48.24（AI-DOC）：整篇 AI 优化（编辑器 / 标签右键「AI优化 → 整篇优化」）
    def _ai_doc_action(self, action_key, prompt=None):
        """整篇 AI 优化：唤起 AI 面板并对当前活动文档整篇发起预设改写。

        v3.48.36（AI-MENUS）：prompt 非空 = 菜单里的自定义提示词。"""
        self._show_ai_dock()
        pane = getattr(self, "_ai_pane", None)
        if pane is None or not hasattr(pane, "ai_action_doc"):
            return
        pane.ai_action_doc(action_key, prompt)

    def _ai_doc_action_from_tab(self, action_key, idx, prompt=None):
        """标签右键：先切到该标签（确保活动编辑器为其内容），再整篇优化。

        切换后内容经异步加载，延迟一拍取活动文档全文，避免取到旧文档。"""
        if not (0 <= idx < len(self._docs)):
            return
        if idx != self._cur:
            self._tabbar.setCurrentIndex(idx)
        QTimer.singleShot(350, lambda: self._ai_doc_action(action_key, prompt))

    # v3.48.31（MENU-AI）：文件列表右键「AI优化」—— 对**该文件**整篇发起预设
    # 改写（原正文选区右键的「整篇优化」迁到此处，语义由「当前文档」变为
    # 「右键所指文件」，避免用户以为作用于当前打开的文档）。
    def _ai_doc_action_for_path(self, action_key, path, prompt=None):
        path = os.path.abspath(path)
        norm = os.path.normpath(path)
        # 已在标签页中打开 → 复用标签右键逻辑（切到该标签 → 整篇优化）
        for i, d in enumerate(self._docs):
            dp = d.get("path")
            if dp and os.path.normpath(dp) == norm:
                # v3.48.36（AI-MENUS 修正）：prompt 必须一并透传，否则
                # 「文件已打开」分支会退回内置提示词（探针 E2 抓到实锤）
                self._ai_doc_action_from_tab(action_key, i, prompt)
                return
        # 未打开 → 先打开，待「活动文档 == 目标文件」且视图就绪后再发起
        # （open_file 为异步加载，直接执行会作用到旧文档上）
        self._ai_doc_pending = (action_key, norm, 0, prompt)
        self.open_file(path)
        QTimer.singleShot(400, self._flush_ai_doc_pending)

    def _flush_ai_doc_pending(self):
        """轮询等待目标文件成为活动文档后再发起整篇优化（最多约 6s）。

        open_file 走 _load_path 异步装载，大文件就绪晚于 400ms；只在
        「活动文档路径 == 目标路径」时执行，杜绝作用到错误文档。"""
        pend = getattr(self, "_ai_doc_pending", None)
        if not pend:
            return
        key, norm, tries = pend[0], pend[1], pend[2]
        prompt = pend[3] if len(pend) > 3 else None
        cur = ""
        if 0 <= self._cur < len(self._docs):
            cur = self._docs[self._cur].get("path") or ""
        ready = bool(cur) and os.path.normpath(cur) == norm
        if not ready and tries < 12:
            self._ai_doc_pending = (key, norm, tries + 1, prompt)
            QTimer.singleShot(500, self._flush_ai_doc_pending)
            return
        self._ai_doc_pending = None
        if ready:
            self._ai_doc_action(key, prompt)
        else:
            self.show_status(T("AI 优化目标文件未就绪：", "AI optimize target file not ready: ") + os.path.basename(norm))

    # ================= v3.46（SoloMD P2）：Excel/CSV 表格导入 =================
    def import_table(self):
        """从 Excel/CSV 文件读取数据，生成 Markdown 表格并插入光标处。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "从 Excel/CSV 插入表格", "",
            "表格文件 (*.xlsx *.xlsm *.csv);;Excel (*.xlsx *.xlsm);;CSV (*.csv)")
        if not path:
            return
        try:
            md = table_file_to_markdown(path)
        except Exception as e:
            QMessageBox.critical(self, T("导入失败", "Import failed"), "读取表格文件出错：\n%s" % e)
            return
        if not md:
            QMessageBox.information(self, T("导入失败", "Import failed"), T("文件为空或无法解析出表格数据。", "File is empty or no tabular data could be parsed."))
            return
        self._js_active('window.insertMarkdown(' + js(md) + ')')
        self.show_status(T("已插入表格（%s）", "Table inserted (%s)") % os.path.basename(path))



    def _on_loaded(self, ok, role):
        if not ok:
            return
        st = self._vstate[role]
        st["loaded"] = True
        view = {"edit": self._view, "src": self._view_src, "prev": self._view_prev}[role]
        text = st["pending"] if st["pending"] is not None else ""
        # 图片相对路径解析依赖文档目录与图片模式，必须在 setMarkdown 之前下发
        self._js_view(view, f"window.setDocDir({js(self._doc_dir())})")
        self._js_view(view, f"window.setImageMode({js(self._image_mode)})")
        # v3.39.8（FMT-LOG）：日志开关在 setMarkdown 前下发（与图片模式同序）
        self._js_view(view, f"window.setFmtLog && window.setFmtLog({js(bool(self._fmt_log))})")
        self._js_view(view, f"window.setMarkdown({js(text)})")
        if st["src"]:
            self._js_view(view, "window.setSourceMode(true)")
        if st["preview"]:
            self._js_view(view, "window.setPreviewMode(true)")
            self._js_view(view, f"window.setPreviewContent({js(text)})")
        st["pending"] = ""
        # v3.46（TOC-SEL）：目标文档经 _load_path 全新加载完成后，执行待插入的目录
        if role == "edit" and self._toc_insert_kind:
            kind = self._toc_insert_kind
            self._toc_insert_kind = None
            self._toc_insert_path = None
            QTimer.singleShot(200, lambda k=kind: self._run_pending_toc(k))
        # v3.47.1（TOC-FIX）：目标文档经 _load_path 全新加载完成后，执行待删除的目录
        if role == "edit" and self._toc_remove_path:
            self._toc_remove_path = None
            QTimer.singleShot(200, lambda: self._remove_toc_text())
        # 主题 / 缩放 / 写作辅助随视图加载同步（含惰性创建的分屏视图）
        self._js_view(view, f"window.setTheme({js(self._theme)})")
        # v3.42.0：界面风格内容级 CSS 随视图加载注入
        self._js_view(view, self._style_patch_js())
        view.setZoomFactor(self._zoom)
        self._js_view(view,
                      f"window.setMode({{typewriter: {str(bool(getattr(self, '_typewriter', False))).lower()}, "
                      f"focus: {str(bool(getattr(self, '_focus', False))).lower()}, "
                      f"autoPair: {str(bool(getattr(self, '_auto_pair', True))).lower()}, "
                      f"emoji: {str(bool(getattr(self, '_emoji', True))).lower()}}})")
        self._js_view(view, f"window.setDefaultCodeLang({js(self._code_lang)})")
        self._js_view(view, f"window.setCodePrefs({{lnum: {str(self._code_lnum).lower()}, "
                            f"style: {js(self._code_style)}}})")
        # v3.30.19（MMD-7）/ v3.34（MMD-11）：图表主题随视图加载同步（空 = 跟随界面主题；
        # 旧版值归一化到新主题）
        _mmd0 = self._settings.value('mmdTheme', '') or ''
        self._js_view(view, f"window.setMmdTheme({js(MMD_LEGACY.get(_mmd0, _mmd0))})")
        # v3.40（UI-R7 R6 补偿②）：首次空白文档一次性气泡（写作视图加载完成后判一次）
        if role == "edit":
            self._maybe_slash_bubble()
        # v3.31.2（#8/#9）：段首缩进 / 标题 1 居中随视图加载下发
        self._js_view(view, f"window.setParaIndent({int(getattr(self, '_para_indent', 0))})")
        self._js_view(view,
                      f"window.setH1Center({str(bool(getattr(self, '_h1_center', False))).lower()})")
        self._js_view(view, f"window.setSlashMenuConfig({js(json.dumps(self._slash_cfg()))})")
        # v3.32.2（TPL-C）：自定义模板随视图加载下发
        self._js_view(view, f"window.setCustomTemplates({self._custom_templates_js()})")
        # v3.48.x（I18N）：界面语言随视图加载下发到内核（window.__setLang）；
        # 覆盖 edit/src/prev 三视图，确保启动即生效，与语言选择器即时切换互补
        self._js_view(view, f"window.__setLang && window.__setLang({js(get_lang())})")
        self._install_drop_filter()

    def _push_text(self, text):
        """把文本推送到当前模式的编辑视图（含双栏两侧）。"""
        if self._dual:
            st = self._vstate["src"]
            if st["loaded"]:
                self._js_view(self._view_src, f"window.setMarkdown({js(text)})")
                self._js_view(self._view_src, "window.setSourceMode(true)")
            else:
                st["pending"] = text
            stp = self._vstate["prev"]
            if stp["loaded"]:
                self._js_view(self._view_prev, "window.setPreviewMode(true)")
                self._js_view(self._view_prev, f"window.setPreviewContent({js(text)})")
            else:
                stp["pending"] = text
        else:
            st = self._vstate["edit"]
            if st["loaded"]:
                self._js_view(self._view, f"window.setMarkdown({js(text)})")
            else:
                st["pending"] = text

    # ================= 轮询同步 =================
    def show_status(self, msg, timeout_ms=3000):
        """v3.29d（B3）：临时提示走状态栏右侧独立区域，超时自动还原；
        「已保存 / 自动保存 / 已打开」等常驻信息仍走左侧 _status，二者互不覆盖。"""
        self._toast.setText(str(msg or ""))
        self._toast_timer.start(timeout_ms)

    def _poll(self):
        if self._cur < 0:
            return
        self._js_active("window.collect ? window.collect() : null", self._on_collect)
        self._js_active("window.getCaretLineCol ? window.getCaretLineCol() : null",
                        self._on_caret)
        # v3.29d（S2/C1）：取走编辑器侧的轻量提示（删除可撤销 / 模式提示等）
        self._js_active("window.takeToast ? window.takeToast() : null", self._on_toast)
        # v3.44（SESSION）：周期性保存会话（每 ~3 秒），崩溃 / 断电可恢复多标签
        _n = time.time()
        if _n - self._session_ts >= 3:
            self._session_ts = _n
            self.save_session()
        # v3.45.7（BOOK-READ-1）：在书籍章节中时，节流记录滚动位置（每 ~5 秒）
        if self._book and self.file_path:
            node = bookmode.find_chapter(self._book["root"], self.file_path)
            if node and (_n - self._book_scroll_ts) >= 5:
                self._book_scroll_ts = _n
                self._js_view(self._view, "window.getScrollRatio()", self._on_book_scroll)

    # ---------------- v3.45.3（LINK-NAV）：链接导航通道 ----------------
    def _poll_nav(self):
        """drain 编辑器侧链接导航队列（__navQ）。

        mdeditor:// 自定义协议会被 Chromium 静默丢弃（location.href 赋值后
        acceptNavigationRequest 不被调用），旧桥接已失效；改为 JS 分类入队、
        这里 150ms 消费。表达式保持极轻：队列为空时直接返回空串。"""
        self._js_active(
            "window.__navDrain ? JSON.stringify(window.__navDrain()) : ''",
            self._on_nav)

    def _on_nav(self, res):
        if not res or not isinstance(res, str):
            return
        try:
            items = json.loads(res)
        except (TypeError, ValueError):
            return
        if not isinstance(items, list):
            return
        for it in items:
            if not isinstance(it, dict):
                continue
            k = it.get("k")
            u = str(it.get("u") or "")
            if k == "ext":
                self._open_external(u)
            elif k == "anchor":
                self._scroll_to_anchor(u)
            elif k == "wiki":
                self.on_wikilink(u)
            elif k == "md":
                self._open_local_link(u)
            elif k == "ai":
                self.ask_ai_about_selection(u)

    # ================= v3.45.8（REQ3#9）：导航跳转历史（前进 / 后退） =================
    def _nav_ensure_seed(self):
        """首次导航前，以当前文档作为历史起点（保证后退有可回之处）。"""
        if self._nav_stack:
            return
        if self.file_path:
            self._nav_stack = [{"path": os.path.abspath(self.file_path), "ratio": 0.0}]
            self._nav_idx = 0
            self._nav_update_buttons()

    def _nav_push(self, path, ratio=0.0):
        """压入一条到达（landing）历史；截断指针之后的前进历史。"""
        if self._nav_lock or not path:
            return
        path = os.path.abspath(path)
        if self._nav_idx >= 0 and self._nav_idx < len(self._nav_stack):
            cur = self._nav_stack[self._nav_idx]
            if cur["path"] == path and abs(cur["ratio"] - ratio) < 1e-3:
                return  # 同一位置不重复堆叠
        self._nav_stack = self._nav_stack[:self._nav_idx + 1]
        self._nav_stack.append({"path": path, "ratio": ratio})
        self._nav_idx = len(self._nav_stack) - 1
        self._nav_update_buttons()

    def _nav_arrive(self, path, delay=450):
        """导航到达后（文档加载 / 锚点定位完成）异步读取滚动比例并压入目标条目。"""
        if self._nav_lock or not path:
            return
        path = os.path.abspath(path)

        def on_ratio(r):
            try:
                ratio = float(r)
            except Exception:
                ratio = 0.0
            self._nav_push(path, ratio)
        QTimer.singleShot(delay, lambda: self._js_view(
            self._view, "window.getScrollRatio()", on_ratio))

    def _nav_update_buttons(self):
        """根据栈指针启用 / 禁用后退、前进按钮与菜单项。"""
        has_back = self._nav_idx > 0
        has_fwd = 0 <= self._nav_idx < len(self._nav_stack) - 1
        if hasattr(self, "_nav_back_act"):
            self._nav_back_act.setEnabled(has_back)
        if hasattr(self, "_nav_forward_act"):
            self._nav_forward_act.setEnabled(has_fwd)

    def _nav_go(self, delta):
        """delta=-1 后退 / +1 前进；越界或加锁则忽略。"""
        if self._nav_lock:
            return
        ni = self._nav_idx + delta
        if ni < 0 or ni >= len(self._nav_stack):
            return
        self._nav_idx = ni
        entry = self._nav_stack[ni]
        self._nav_restore(entry)
        self._nav_update_buttons()

    def _nav_restore(self, entry):
        """恢复一条历史：同文档则滚动定位，异文档则打开后滚动定位；加锁防重入。"""
        if self._nav_lock:
            return
        self._nav_lock = True
        path, ratio = entry["path"], entry["ratio"]
        cur = os.path.abspath(self.file_path) if self.file_path else None
        try:
            if cur and cur == os.path.abspath(path):
                self._js_view(self._view, "window.scrollToRatio(%s)" % json.dumps(ratio))
            elif os.path.exists(path):
                self._load_path(path)
                QTimer.singleShot(500, lambda: self._js_view(
                    self._view, "window.scrollToRatio(%s)" % json.dumps(ratio)))
            else:
                # 目标文件已不存在（如被删除的章节）：同文档仅滚动，异文档提示并不导航
                self.show_status(T("跳转历史目标文件不存在：", "Jump-history target file does not exist: ") + os.path.basename(path))
                if cur:
                    self._js_view(self._view, "window.scrollToRatio(%s)" % json.dumps(ratio))
        finally:
            QTimer.singleShot(650, lambda: setattr(self, "_nav_lock", False))

    def _open_external(self, url):
        """外部链接（http/https/mailto/…）交系统浏览器。"""
        from PySide6.QtGui import QDesktopServices
        url = (url or "").strip()
        if not url:
            return
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:   # noqa: BLE001
            self.show_status(T("无法打开链接：%s", "Cannot open link: %s") % e)

    def _scroll_to_anchor(self, slug):
        """页内锚点跳转：先按标题 slug（scrollToAnchor），再按元素 id
        （脚注定义 #fn-x 等）定位。"""
        slug = (slug or "").strip()
        if not slug:
            return
        # v3.45.8（REQ3#9）：页内锚点跳转记入跳转历史
        self._nav_ensure_seed()
        self._nav_arrive(self.file_path or "", delay=450)
        self._js_active(
            "(function(s){"
            "if (window.scrollToAnchor && window.scrollToAnchor(s)) return 'ok';"
            "var el=document.getElementById(s);"
            "if(el){el.scrollIntoView({block:'center'});"
            "el.classList.add('flash');"
            "setTimeout(function(){el.classList.remove('flash');},1600);"
            "return 'ok';}"
            "return 'no';"
            "})(%s)" % json.dumps(slug, ensure_ascii=False))

    def _open_local_link(self, href):
        """文档内本地文件链接 → 编辑器内打开。

        href 为 markdown 原始相对路径（可带 #fragment）；按当前文档目录
        解析为绝对路径后走 open_book_link（内含 .html→.md 回退与锚点滚动）。"""
        from urllib.parse import unquote
        href = (href or "").strip()
        if not href:
            return
        low = href.lower()
        if "://" in low or low.startswith(("mailto:", "data:", "blob:", "file:")):
            self._open_external(href)
            return
        base = self._doc_dir()
        if not base:
            self.show_status(T("文档尚未保存，无法解析相对链接：", "Document not saved; cannot resolve relative link: ") + href)
            return
        path, sep, frag = href.partition("#")
        path = unquote(path).replace("\\", "/")
        if not path:
            self._scroll_to_anchor(frag)
            return
        ap = os.path.normpath(os.path.join(base, path))
        # v3.45.3（LINK-EXT）：非 Markdown 文件（.html/.htm/.pdf/图片…）编辑器无法
        # 编辑，已存在则交系统默认程序打开（.html 走浏览器），不再把源码当正文加载；
        # 缺失的 .html 仍走 open_book_link 回退同名 .md（LINK-FB）。
        if not ap.lower().endswith((".md", ".markdown")) and os.path.exists(ap):
            self._open_external(QUrl.fromLocalFile(ap).toString())
            return
        self.open_book_link(ap + (sep + frag if sep else ""))

    def _on_toast(self, res):
        msg = res if isinstance(res, str) else None
        if not msg:
            return
        # v3.34（MMD-11）：图表主题命令通道 —— 图表块右键子菜单切换后由编辑器侧
        # 推来「##mmdtheme:<id>」，此处落 QSettings 并广播全部视图（RPC 复用 toast 槽）
        if msg.startswith("##mmdtheme:"):
            self._set_mmd_theme(msg[len("##mmdtheme:"):])
            return
        # v3.38（QUO-11）：引用操作一次性提示 —— 编辑器侧首次在引用内按键时
        # 推来 ##quotetip，此处落 QSettings（每台机器只提示一次）
        if msg == "##quotetip":
            if not self._settings.value("quoteTipShown", False, type=bool):
                self._settings.setValue("quoteTipShown", True)
                # v3.38（QUO-12）：提示明确化 —— 退出条件 = 空行上回车
                self.show_status(T("提示：引用末尾空行上按回车即可退出（行尾连按两次回车）；Tab 加一层嵌套 / Shift+Tab 减一层", "Tip: press Enter on the blank line at the end of a quote to exit (double Enter at line end); Tab adds one nesting level / Shift+Tab removes one"))
            return
        self.show_status(msg)

    def _on_caret(self, res):
        try:
            data = json.loads(res) if isinstance(res, str) else res
        except (TypeError, ValueError):
            return
        if isinstance(data, dict) and data.get("line"):
            self._pos.setText(T(f"行 {int(data['line'])} · 列 {int(data.get('col', 1))}", f"Line {int(data['line'])} · Col {int(data.get('col', 1))}"))
            # v3.30.10（HP-1）：当前块类型（标题 N / 表格 / 图表 / 公式 / 引用…）
            self._blktype.setText(data.get("type") or "")
        elif isinstance(data, dict) and data.get("imgsel"):
            # v3.30.17：选中图片 → 状态栏显示存储方式 / 存储文件名；取消选中 → 清空
            # v3.39.2（IMG-16）：追加完整路径（相对路径由内核按文档目录解析为绝对路径）
            _t16 = data.get("type") or ""
            _p16 = data.get("path") or ""
            self._blktype.setText((_t16 + " · " + _p16) if _p16 else _t16)

    def _poll_sync_scroll(self):
        """v3.29 双栏同步滚动：源码视图滚动位置 / 光标段落 → 预览视图。

        v3.38（SYN-3）：同时轮询预览视图，用户滚动预览时反向带动源码。
        非双栏直接返回；两侧页面都加载完成后才发查询，避免 JS 未注入报错。"""
        if not self._dual or self._view_src is None or self._view_prev is None:
            return
        # v3.49.1（OUT-SYNC）：手动跳转后的短暂窗口内不自动回拉，保证跳转落点稳定
        if time.monotonic() - self._sync_manual_ts < 0.7:
            return
        st = self._vstate.get("src", {})
        stp = self._vstate.get("prev", {})
        if not (st.get("loaded") and stp.get("loaded")):
            return
        self._js_view(self._view_src,
                      "window.pollSrcScroll ? window.pollSrcScroll() : null",
                      self._on_src_scroll)
        self._js_view(self._view_prev,
                      "window.pollPrevScroll ? window.pollPrevScroll() : null",
                      self._on_prev_scroll)

    def _on_src_scroll(self, res):
        try:
            data = json.loads(res) if isinstance(res, str) else res
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict) or data.get("idx") is None:
            return
        # v3.38（SYN-3）：用户刚滚动过预览 → 反向同步优先，源码侧暂时让权，
        # 否则光标锁定（cv）会把预览拉回光标段落、抵消用户的预览滚动。
        if time.monotonic() - self._sync_ts_prev2src < 1.2:
            return
        # 光标在源码视口内可见 → 预览优先定位到光标所在段落（编辑跟随）
        if data.get("cv") and data.get("cidx") is not None:
            idx, frac = data["cidx"], data.get("cfrac", 0)
        else:  # 否则按两侧滚动位置映射（滚动跟随）
            idx, frac = data["idx"], data.get("frac", 0)
        try:
            idx = int(idx)
            frac = max(0.0, min(1.0, float(frac)))
        except (TypeError, ValueError):
            return
        pair = (idx, round(frac, 2))
        if pair == self._last_src_pair:   # 无变化不重发（防程序性滚动再触反向）
            return
        self._last_src_pair = pair
        self._sync_ts_src2prev = time.monotonic()
        self._js_view(self._view_prev, f"window.scrollPreviewToBlock({idx},{frac})")

    def _on_prev_scroll(self, res):
        """v3.38（SYN-3）：预览滚动 → 反向带动源码视图。"""
        try:
            data = json.loads(res) if isinstance(res, str) else res
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict) or data.get("idx") is None:
            return
        now = time.monotonic()
        # 这是源码同步程序性设置的滚动位置 → 不回传，切断回环
        if now - self._sync_ts_src2prev < 0.6:
            return
        try:
            idx = int(data["idx"])
            frac = max(0.0, min(1.0, float(data.get("frac", 0))))
        except (TypeError, ValueError, KeyError):
            return
        pair = (idx, round(frac, 2))
        if pair == self._last_prev_pair:  # 预览没动（或仍是上次位置）不重发
            return
        # v3.38（SYN-3）：与上次正向发给预览的目标同块且 frac 微差 → 是正向
        # 程序性落点（两侧参照残余偏差），不反向，杜绝正反向互相追逐
        if (self._last_src_pair is not None and idx == self._last_src_pair[0]
                and abs(frac - self._last_src_pair[1]) < 0.12):
            self._last_prev_pair = pair
            return
        self._last_prev_pair = pair
        self._sync_ts_prev2src = now
        self._js_view(self._view_src, f"window.scrollSrcToBlock({idx},{frac})")

    def goto_line(self):
        n, ok = QInputDialog.getInt(self, T("转到行", "Go to Line"), T("行号：", "Line number:"), 1, 1, 1_000_000)
        if ok:
            self._js_active(f"window.gotoLine({n})")

    def _show_stats_detail(self):
        """状态栏点击 → 字数 / 字符 / 段落 / 阅读时长详情。"""
        s = self._stats or {}
        if not s:
            QMessageBox.information(self, T("统计", "Statistics"), T("暂无统计数据。", "No statistics yet."))
            return
        g = lambda k: int(s.get(k, 0) or 0)  # noqa: E731
        QMessageBox.information(
            self, "统计详情",
            f"<b>字数</b>：{g('chars'):,}"
            f"　<span style='color:#888;'>（中文字符 {g('cjk'):,} ＋ 英文单词 {g('words'):,}）</span><br>"
            f"<b>字符数</b>（不含空白）：{g('raw'):,}<br>"
            f"<b>数字</b>：{g('digits'):,}　<b>标点</b>：{g('punct'):,}<br>"
            f"<b>段落</b>：{g('paragraphs'):,}　<b>行数</b>：{g('lines'):,}<br>"
            f"<b>阅读时长</b>：约 {g('readMin')} 分钟"
            "<br><br><span style='color:#888;'>统计口径：中文按字计、英文按词计；"
            "代码块不计入字数。</span>")

    # ================= P1-3 命令面板 =================
    def copy_as_html(self):
        """v3.29d（UX #34）：把整篇文档导出为带格式 HTML 并复制进剪贴板，
        粘贴到微信 / Word / 邮件时保留标题、加粗、表格等格式。"""
        def cb(html):
            if not html:
                return
            md = QMimeData()
            md.setHtml(html)
            md.setText(html)
            QApplication.clipboard().setMimeData(md)
            self.show_status(T("已复制为 HTML · 粘贴到微信 / Word 可保留格式", "Copied as HTML · pasting to WeChat / Word preserves formatting"))
        self._js_active("window.getExportHTML()", cb)

    def extra_commands(self):
        """命令面板里的补充命令（不在菜单 / 快捷键体系中的编辑器命令）。"""
        def js_cmd(code, tip):
            return lambda: self._js_active(code)

        def theme_cmd(tid):
            return lambda: self.apply_theme(tid)

        rows = [
            {"group": "视图", "name": "折叠全部标题", "seq": "Ctrl+Shift+[",
             "enabled": True, "run": lambda: self.fold_all_headings(True)},
            {"group": "视图", "name": "展开全部标题", "seq": "Ctrl+Shift+]",
             "enabled": True, "run": lambda: self.fold_all_headings(False)},
            {"group": "编辑", "name": "插入脚注引用", "seq": "",
             "enabled": True, "run": js_cmd('window.cmd && window.cmd("footnote")', "脚注")},
            {"group": "编辑", "name": "插入定义列表", "seq": "",
             "enabled": True, "run": js_cmd('window.cmd && window.cmd("deflist")', "定义列表")},
            # v3.37（TBL-F3）：blkmenu 块级能力收录进命令面板 ——「想得起就搜得到」；
            # 目标块由 window.__blkCmd 解析（对象选中态优先，否则光标所在块）
            {"group": "编辑", "name": "表格标注…", "seq": "",
             "enabled": True, "run": js_cmd('window.__blkCmd && window.__blkCmd("cap")', "表格标注")},
            {"group": "编辑", "name": "表格还原尺寸", "seq": "",
             "enabled": True, "run": js_cmd('window.__blkCmd && window.__blkCmd("resetsize")', "表格还原尺寸")},
            {"group": "编辑", "name": "复制当前块", "seq": "",
             "enabled": True, "run": js_cmd('window.__blkCmd && window.__blkCmd("dup")', "复制当前块")},
            {"group": "文件", "name": "历史版本", "seq": "Ctrl+Shift+H",
             "enabled": True, "run": self.show_history},
            {"group": "文件", "name": "立即留档（版本快照）", "seq": "",
             "enabled": True, "run": self.manual_snapshot},
            {"group": "文件", "name": "归档整个工作区…", "seq": "",
             "enabled": True, "run": self.archive_workspace},
        ]
        for t in styles.THEMES:
            rows.append({"group": "外观", "name": T(f"切换主题：{t['label']}", f"Switch theme: {t['label']}"), "seq": "",
                         "enabled": True, "run": theme_cmd(t["id"])})
        # v3.43.0（LOOK-1）：外观四项全部进命令面板 —— mac / zen 两套风格会藏掉菜单栏，
        # 命令面板是唯一不受布局门控影响、任何风格下都能改回外观的通道。
        for sid, label in uistyles.menu_styles():
            rows.append({"group": "外观", "name": T(f"切换界面风格：{label}", f"Switch UI style: {label}"), "seq": "",
                         "enabled": True, "run": (lambda s=sid: self.set_uistyle(s))})
        for _label, _val in MMD_THEMES:
            rows.append({"group": "外观", "name": T(f"切换图表风格：{_label}", f"Switch diagram style: {_label}"), "seq": "",
                         "enabled": True, "run": (lambda v=_val: self._set_mmd_theme(v))})
        for _sid, _slabel in CODE_STYLES:
            rows.append({"group": "外观", "name": T(f"切换代码风格：{_slabel}", f"Switch code style: {_slabel}"), "seq": "",
                         "enabled": True, "run": (lambda s=_sid: self.set_code_prefs(style=s))})
        rows.append({"group": "外观", "name": T("界面风格管理…", "UI Style Manager…"), "seq": "",
                     "enabled": True, "run": self.show_style_manager})
        for m_id, _icon, label, _desc in MODES:
            rows.append({"group": "视图", "name": T(f"切换到{label}", f"Switch to {label}"), "seq": "",
                         "enabled": True, "run": (lambda m=m_id: self._set_mode(m))})
        return rows

    def show_command_palette(self):
        """打开命令面板（Ctrl+Shift+P）。v3.25：面板停靠在菜单栏下方顶端。"""
        if not hasattr(self, "_cmd_dlg"):
            self._cmd_dlg = CommandPaletteDialog(self)
        dlg = self._cmd_dlg
        dlg._apply_theme_qss(self._theme)
        dlg.show()
        # v3.25：show 后显式停靠到菜单栏下方居中（Qt 默认会把对话框居中覆盖掉 showEvent 里的定位）
        geo = self.geometry()
        menu_h = self.menuBar().height() if self.menuBar() else 0
        dlg.move(geo.x() + max(8, (geo.width() - dlg.width()) // 2), geo.y() + menu_h + 10)
        dlg.raise_()
        dlg.activateWindow()

    # ================= P1-6 版本历史 =================
    def _history_dir(self, path):
        """历史快照目录：<文档目录>/.mdeditor-history/<文档名>/"""
        if not path:
            return ""
        base = os.path.splitext(os.path.basename(os.path.abspath(path)))[0] or "untitled"
        return os.path.join(os.path.dirname(os.path.abspath(path)),
                            ".mdeditor-history", base)

    def list_history(self, path):
        """返回 [(快照文件, mtime)]，按时间倒序。"""
        d = self._history_dir(path)
        if not d or not os.path.isdir(d):
            return []
        out = []
        for name in os.listdir(d):
            if not name.lower().endswith(".md"):
                continue
            fp = os.path.join(d, name)
            try:
                out.append((fp, os.path.getmtime(fp)))
            except OSError:
                continue
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    def snapshot_history(self, path, text):
        """保存前把上一版内容留档（内容与磁盘一致时跳过，避免无意义快照）。"""
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                old = f.read()
        except OSError:
            return None
        if text is not None and old == text:
            return None
        d = self._history_dir(path)
        if not d:
            return None
        try:
            os.makedirs(d, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            fp = os.path.join(d, f"{stamp}.md")
            n = 1
            while os.path.exists(fp):
                fp = os.path.join(d, f"{stamp}-{n}.md")
                n += 1
            with open(fp, "w", encoding="utf-8") as f:
                f.write(old)
        except OSError:
            return None
        # 只保留最近 N 份
        items = self.list_history(path)
        for fp_old, _mt in items[self._history_keep:]:
            try:
                os.remove(fp_old)
            except OSError:
                pass
        return fp

    def show_history(self):
        """打开历史版本对话框（文件菜单 / Ctrl+Shift+H）。"""
        if not hasattr(self, "_hist_dlg"):
            self._hist_dlg = HistoryDialog(self)
        self._hist_dlg._apply_theme_qss(self._theme)
        self._hist_dlg.show_for(self.file_path)

    def manual_snapshot(self):
        """v3.32（P0-3）：「立即留档」—— 不等写盘节流，把当前内容直接存一份
        快照（与自动快照不同：内容相同也保留，用户主动打点应有痕迹）。"""
        if not self.file_path:
            self.show_status(T("未命名文档暂不支持版本快照 · 保存到文件后可用", "Untitled documents do not support version snapshots yet · available after saving to a file"))
            return

        def cb(md):
            if md is None:
                return
            d = self._history_dir(self.file_path)
            if not d:
                return
            try:
                os.makedirs(d, exist_ok=True)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                fp = os.path.join(d, f"{stamp}.md")
                n = 1
                while os.path.exists(fp):
                    fp = os.path.join(d, f"{stamp}-{n}.md")
                    n += 1
                out = md if md.endswith("\n") else md + "\n"
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(out)
            except OSError as e:
                QMessageBox.warning(self, T("留档失败", "Snapshot failed"), str(e))
                return
            self.show_status(T(f"已留档 · {os.path.basename(fp)}", f"Snapshot saved · {os.path.basename(fp)}"))

        self._js_active("window.getMarkdown()", cb)

    def restore_history(self, snap_path, mtime=None):
        """把某个历史快照内容恢复到当前编辑区（未保存状态）。"""
        try:
            with open(snap_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            QMessageBox.critical(self, T("恢复失败", "Restore failed"), str(e))
            return
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)) if mtime else "历史版本"
        if QMessageBox.question(
                self, "恢复历史版本",
                f"确定用 {when} 的内容替换当前编辑区吗？\n\n"
                "（当前内容不会被删除：恢复后处于未保存状态，可撤销 / 不保存直接关闭）",
                QMessageBox.Ok | QMessageBox.Cancel) != QMessageBox.Ok:
            return
        self._push_text(text)
        self._dirty = True
        self._update_title()
        self.show_status(T(f"已恢复历史版本（{when}）· 按 Ctrl+S 保存", f"Restored historical version ({when}) · press Ctrl+S to save"))

    def apply_merged_text(self, text):
        """v3.47.4（REQ3）：把合并结果（可能含冲突标记）写入当前编辑区。

        与 restore_history 同理：处于未保存状态，需再按 Ctrl+S 落盘；不覆盖磁盘。
        返回是否成功写入。"""
        if not isinstance(text, str):
            return False
        self._push_text(text)
        self._dirty = True
        self._update_title()
        self.show_status(T("已应用合并结果到当前编辑区 · 按 Ctrl+S 保存", "Applied merge result to current editor · press Ctrl+S to save"))
        return True

    # ================= 侧栏文件管理支撑（回收站删除 / 重命名同步） =================
    def recycle_path(self, path):
        """把文件 / 文件夹移入回收站（跨平台：Windows→回收站 / macOS→~/.Trash /
        Linux→gio trash 或 XDG Trash / 兜底→永久删除）。返回是否成功。"""
        try:
            import trash
            return trash.send_to_trash(path)
        except Exception:
            # 兜底：极罕见（trash 模块异常）时直接永久删除并报失败
            try:
                p = os.path.abspath(path)
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p)
                elif os.path.exists(p):
                    os.remove(p)
                return True
            except Exception:
                return False

    def rename_current_file(self, old, new):
        """侧栏把当前打开的文件改名后同步内部状态（保存路径 / 标签 / 标题）。"""
        if old and self.file_path and \
                os.path.abspath(self.file_path) == os.path.abspath(old):
            self.file_path = new
            if 0 <= self._cur < len(self._docs):
                self._docs[self._cur]["path"] = new
            self._refresh_tab_texts()
            self._update_title()

    # ================= v3.31（#7）大纲拖拽调序 =================
    def reorder_sections(self, pairs):
        """把同级章节的新顺序（[start, end) 块区间列表）发给内核整段重排。"""
        try:
            payload = json.dumps(pairs)
        except (TypeError, ValueError):
            return
        if self._dual and self._view_src is not None:
            # v3.38（OUT-6）：分屏下双视图同时下发（原只发激活视图，预览侧要等 1~2s poll 收敛）
            self._js_view(self._view_src, f"window.reorderSections({js(payload)})")
            self._js_view(self._view_prev, f"window.reorderSections({js(payload)})")
        else:
            self._js_active(f"window.reorderSections({js(payload)})")
        self.show_status(T("已调整章节顺序", "Chapter order adjusted"))

    # ================= P1-7 外部打开 =================
    def show_in_explorer(self, path=None):
        """在资源管理器中定位当前文档（无文档时打开所在目录）。"""
        target = path or self.file_path
        if not target:
            QMessageBox.information(self, T("在资源管理器中显示", "Show in Explorer"), T("当前文档尚未保存到文件。", "Current document is not saved to a file yet."))
            return
        target = os.path.abspath(target)
        try:
            if os.path.exists(target):
                subprocess.Popen(["explorer", "/select,", target])
            else:
                d = os.path.dirname(target)
                subprocess.Popen(["explorer", d if d else "."])
        except OSError as e:
            QMessageBox.critical(self, T("打开失败", "Open failed"), str(e))

    def open_external(self, path=None):
        """用系统默认程序打开指定文件（缺省 = 当前文档；
        可用系统设置里的外部编辑器路径覆盖）。v3.25：支持侧栏文件列表右键调用。"""
        target = path or self.file_path
        if not target:
            QMessageBox.information(self, T("用外部程序打开", "Open with external program"), T("当前文档尚未保存到文件。", "Current document is not saved to a file yet."))
            return
        target = os.path.abspath(target)
        if not os.path.exists(target):
            QMessageBox.information(self, T("用外部程序打开", "Open with external program"), f"文件不存在：{target}")
            return
        cmd = str(getattr(self, "_external_editor", "") or "").strip()
        try:
            if cmd:
                subprocess.Popen([cmd, target])
            else:
                openutil.open_path(target)     # 跨平台：Windows=startfile / mac=open / linux=xdg-open
            self.show_status(T(f"已用外部程序打开 · {target}", f"Opened with external program · {target}"))
        except OSError as e:
            QMessageBox.critical(self, T("打开失败", "Open failed"), str(e))

    # ================= P1-2 折叠 =================
    def fold_all_headings(self, close):
        """折叠 / 展开全部标题（视图菜单、命令面板）。"""
        self._js_active(
            f"window.foldAllHeadings ? window.foldAllHeadings({str(bool(close)).lower()}) : 0",
            lambda n: self.show_status(
                ("已折叠 " if close else "已展开 ") + f"{int(n or 0)} 个标题"))

    # ================= P1-1 / P1-8 输入增强 =================
    def set_auto_pair(self, on):
        """自动配对括号 / 引号开关。"""
        self._auto_pair = bool(on)
        self._settings.setValue("autoPair", bool(on))
        self._js_active(f"window.setMode({{autoPair: {str(bool(on)).lower()}}})")
        self.show_status(T("自动配对：开", "Auto-pair: On") if on else "自动配对：关")

    def set_emoji_complete(self, on):
        """Emoji 短代码自动补全开关。"""
        self._emoji = bool(on)
        self._settings.setValue("emojiComplete", bool(on))
        self._js_active(f"window.setMode({{emoji: {str(bool(on)).lower()}}})")
        self.show_status(T("Emoji 补全：开", "Emoji completion: On") if on else "Emoji 补全：关")

    def set_history_keep(self, n):
        """历史版本保留份数（1~100，系统设置→通用；v3.43.1 上限 200 → 100）。"""
        try:
            n = max(1, min(100, int(n)))
        except (TypeError, ValueError):
            return
        self._history_keep = n
        self._settings.setValue("historyKeep", n)
        self.show_status(T(f"历史版本保留 {n} 份", f"History versions kept: {n}"))

    def set_external_editor(self, path):
        """外部编辑器可执行文件路径（留空 = 系统默认关联程序，系统设置→通用）。"""
        self._external_editor = str(path or "").strip()
        self._settings.setValue("externalEditor", self._external_editor)
        self.show_status(T("外部编辑器：", "External editor: ") + (self._external_editor or "系统默认程序"))

    # ================= 跨文件搜索 =================
    def show_search(self):
        """打开「查找」对话框的「全局搜索」页签（Ctrl+Shift+F / 编辑菜单）。

        v3.24：全局搜索不再单独占用工具栏按钮 / 侧栏面板，与查找整合为一个对话框，
        「查找」「全局搜索」各占一个页签，可随时切换。"""
        self.show_find(False)
        self._find_dlg.show_global()

    def search_root(self):
        """搜索根目录：当前文档所在目录 → 侧栏当前目录 → 用户主目录。"""
        if self.file_path:
            return os.path.dirname(os.path.abspath(self.file_path))
        cur = getattr(self._sidebar, "_cur_dir", None)
        if cur and os.path.isdir(cur):
            return cur
        return os.path.expanduser("~")

    def open_file_at(self, path, line):
        """打开文件并跳转到指定行（搜索结果点击）。"""
        if not path or not os.path.exists(path):
            self.show_status(T(f"文件不存在：{path}", f"File does not exist: {path}"))
            return
        self._pending_goto = (os.path.abspath(path), max(1, int(line)))
        self._pending_tries = 0
        self.open_file(path)
        QTimer.singleShot(500, self._flush_pending_goto)

    def _flush_pending_goto(self):
        """等待文档真正加载进视图后再跳行（跨标签 / 首次打开都要等）。"""
        pg = self._pending_goto
        if not pg:
            return
        path, line = pg
        loaded = (self.file_path and os.path.abspath(self.file_path) == path
                  and self._vstate[self._active_role()]["loaded"])
        if loaded:
            self._pending_goto = None
            self._js_active(f"window.gotoLine({line})")
            self.show_status(T(f"已跳转到 {os.path.basename(path)} 第 {line} 行", f"Jumped to line {line} of {os.path.basename(path)}"))
            return
        self._pending_tries += 1
        if self._pending_tries < 12:
            QTimer.singleShot(300, self._flush_pending_goto)
        else:
            self._pending_goto = None

    # ================= 图片插入（落盘相对路径 / 内嵌 data URL 双模式） =================
    def _pick_local_image(self):
        """斜杠菜单 / 编辑器「图片」→ v3.27 唯一插入面板（不再有编辑器内第二层弹窗）。

        「本地相对路径存储」勾选框默认跟随系统设置预勾选，用户可在面板内改；
        存储名称插入后单击图片「修改存储文件名」指定。
        面板里输入 http(s) 地址则按网络图片直接插入。"""
        dlg = InsertImageDialog(self)
        if not dlg.exec():
            return
        src = dlg.src_path()
        if not src:
            return
        if dlg.is_url():
            name = dlg._cur_stem() or "图片"
            self._js_active(f"window.insertImageMarkdown({js(src)}, {js(name)})")
            self.show_status(T(f"已插入网络图片 · {src[:60]}", f"Inserted network image · {src[:60]}"))
            return
        self._insert_image_file(src, mode=dlg.mode())

    def _numbered_asset_name(self, name, ext):
        """v3.25：默认存储名 = 「assets 现有文件数 + 1」5 位编号 _ 名称。
        （00011_我的图片.png —— 编号自动生成，重名再由 _unique_name 兜底）
        v3.31.3（IMG-11）：名称里已带 5 位编号前缀（如「转相对路径」弹框的
        默认名经二次编号）时先剥掉，杜绝 00001_00001_图片.png 双重编号。"""
        assets = self._assets_dir_for(self.file_path) if self.file_path else None
        count = 0
        if assets and os.path.isdir(assets):
            count = len([n for n in os.listdir(assets)
                         if os.path.isfile(os.path.join(assets, n))])
        stem = os.path.splitext(name)[0] or name      # 名称里带了扩展名则剥掉
        stem = re.sub(r"^\d{5}_", "", stem)           # v3.31.3：剥已有编号前缀
        return f"{count + 1:05d}_{stem}{ext or '.png'}"

    def _insert_image_file(self, path, mode=None, name=None):
        """插入本地图片：assets 模式落盘为相对路径，embed 模式内嵌 data URL。

        v3.25：mode / name 来自插入对话框（缺省取系统设置里的图片存放方式）。"""
        name = name or os.path.splitext(os.path.basename(path))[0] or "图片"
        mode = mode or self._image_mode
        rel = None
        if mode == "assets":
            fname = self._numbered_asset_name(name, os.path.splitext(path)[1].lower())
            try:
                rel = self._save_image_to_assets(path, filename=fname)
            except OSError as e:
                self.show_status(T(f"图片落盘失败，已改为内嵌：{e}", f"Image save failed; switched to embedded: {e}"))
                rel = None
            else:
                if rel is None:
                    self._status_prefer_assets()
        if rel:
            self._js_active(f"window.insertImageMarkdown({js(rel)}, {js(name)})")
            self.show_status(T(f"已插入图片（相对路径）· {rel}", f"Inserted image (relative path) · {rel}"))
            return
        try:
            ext = os.path.splitext(path)[1].lower()
            mime = IMG_MIME.get(ext, "image/png")
            with open(path, "rb") as f:
                raw = f.read()
            # v3.29d（B8/UX #35）：内嵌超过 1MB 的大图给出提示（建议相对路径存储）
            if len(raw) > 1024 * 1024:
                self.show_status(
                    f"提示：内嵌图片 {os.path.basename(path)} 约 {len(raw) // 1024 // 1024 + 1} MB，"
                    "可能拖慢文档加载；建议改用相对路径（assets）存储", 6000)
            b64 = base64.b64encode(raw).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"
            self._js_active(f"window.insertImageMarkdown({js(data_url)}, {js(name)})")
            self.show_status(T(f"已插入图片（内嵌）· {os.path.basename(path)}", f"Inserted image (embedded) · {os.path.basename(path)}"))
        except OSError as e:
            self.show_status(T(f"插入图片失败：{e}", f"Insert image failed: {e}"))

    def _status_prefer_assets(self):
        self.show_status(T("当前文档尚未保存，图片已改为内嵌；保存后插入的图片会自动落到 assets 目录", "Document not saved; image switched to embedded; inserted images will land in the assets folder after saving"))

    # ---- 落盘：资源目录 ----
    def _assets_dir_for(self, doc_path):
        """图片资源目录。

        v3.45.7（REQ2）：书籍模式下统一为「<summary_dir>/assets/」（规范统一存放）；
        非书籍为与文档同级的「<文档名>.assets/」（Typora 风格）。"""
        if doc_path and self._book:
            sd = self._book.get("summary_dir")
            if sd and os.path.abspath(doc_path).startswith(os.path.abspath(sd)):
                return os.path.join(sd, "assets")
        base = os.path.splitext(os.path.basename(doc_path))[0] or "文档"
        return os.path.join(os.path.dirname(os.path.abspath(doc_path)), base + ".assets")

    @staticmethod
    def _unique_name(directory, filename):
        """重名自动追加 -1、-2 …（与 Typora 行为一致）。"""
        stem, ext = os.path.splitext(filename)
        cand, k = filename, 1
        while os.path.exists(os.path.join(directory, cand)):
            cand = f"{stem}-{k}{ext}"
            k += 1
        return cand

    def _save_image_to_assets(self, src_path=None, data=None, filename=None):
        """把图片写入资源目录，返回写进 Markdown 的相对路径（正斜杠）。

        v3.45.7（REQ2）：书籍模式统一落到 <summary_dir>/assets/；相对路径按章节
        文件所在目录推算（嵌套章节会得到 ../assets 之类），保证跨章节引用一致。
        未保存文档（无路径）时返回 None，由调用方回退为内嵌 data URL。
        """
        if not self.file_path:
            return None
        assets = self._assets_dir_for(self.file_path)
        doc_dir = os.path.dirname(os.path.abspath(self.file_path))
        rel_dir = os.path.relpath(assets, doc_dir).replace(os.sep, "/")
        fname = filename or os.path.basename(src_path)
        # 源文件已在目标目录内：直接复用，避免复制出 -1 副本
        if src_path:
            try:
                if os.path.normcase(os.path.dirname(os.path.abspath(src_path))) == \
                        os.path.normcase(assets):
                    return rel_dir + "/" + os.path.basename(src_path)
            except (OSError, ValueError):
                pass
        os.makedirs(assets, exist_ok=True)
        dest_name = self._unique_name(assets, fname)
        dest = os.path.join(assets, dest_name)
        if data is not None:
            with open(dest, "wb") as f:
                f.write(data)
        else:
            shutil.copy2(src_path, dest)
        return rel_dir + "/" + dest_name

    def _handle_pasted_image(self, info):
        """剪贴板 / 截图粘贴的图片：assets 模式落盘，否则内嵌。"""
        if not isinstance(info, dict):
            return
        url = str(info.get("url") or "")
        name = str(info.get("name") or "粘贴图片")
        if not url.startswith("data:"):
            return
        rel = None
        if self._image_mode == "assets":
            m = re.match(r"data:([^;,]+);base64,(.*)$", url, re.S)
            if m:
                ext = MIME_EXT.get(m.group(1).lower(), ".png")
                stem = os.path.splitext(name)[0] or "图片"
                try:
                    rel = self._save_image_to_assets(
                        data=base64.b64decode(m.group(2)), filename=stem + ext)
                except (OSError, ValueError, binascii.Error):
                    rel = None
                if rel is None and not self.file_path:
                    self._status_prefer_assets()
        if rel:
            self._js_active(f"window.insertImageMarkdown({js(rel)}, {js(name)})")
            self.show_status(T(f"已粘贴图片（相对路径）· {rel}", f"Pasted image (relative path) · {rel}"))
        else:
            # v3.29d（B8）：大图内嵌提示（粘贴网络图 / 未保存文档回退内嵌时）
            m2 = re.match(r"^data:image/[^;]+;base64,", url or "")
            if m2 and len(url) > 1024 * 1365:   # base64 后约 >1MB 原始数据
                self.show_status(T("提示：粘贴的内嵌图片超过 1MB，可能拖慢文档加载；建议保存文档后改用相对路径（assets）存储",
                                     "Tip: pasted embedded images over 1MB may slow document loading; after saving the document, consider switching to relative-path (assets) storage"), 6000)
            self._js_active(f"window.insertImageMarkdown({js(url)}, {js(name)})")
            self.show_status(T("已粘贴图片（内嵌 data URL）", "Pasted image (embedded data URL)"))

    def set_image_mode(self, mode):
        """设置图片存放方式：assets=落盘相对路径（推荐）/ embed=内嵌 data URL。"""
        mode = "embed" if str(mode) == "embed" else "assets"
        self._image_mode = mode
        self._settings.setValue("imageMode", mode)
        self._push_doc_dir()
        self.show_status(T("图片存放方式：", "Image storage method: ") + (
            "相对路径（保存到「文档名.assets」文件夹）" if mode == "assets"
            else "内嵌 data URL（图片写入文档本身）"))

    # ---- v3.39.8（FMT-LOG）：格式化操作日志 ----
    def _append_fmt_log(self, entries):
        """内核 collect 差量带出的格式化操作记录，JSON Lines 追加落盘
        （%APPDATA%/mdEditor/fmtlog/fmt-YYYYMMDD.log，每行一条 JSON：
        n 序号 / t 时间 / act 动作 / obj 应用前块源码 / res 应用后 / note 备注 / doc 文档名）。"""
        try:
            os.makedirs(FMTLOG_DIR, exist_ok=True)
            fp = os.path.join(FMTLOG_DIR, time.strftime("fmt-%Y%m%d.log"))
            doc = ""
            if 0 <= self._cur < len(self._docs):
                doc = os.path.basename(self._docs[self._cur].get("path") or "未命名")
            with open(fp, "a", encoding="utf-8") as f:
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    e = dict(e)
                    e["doc"] = doc
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def set_fmt_log(self, on):
        """设置开关（即时生效）：QSettings 持久化 + 内核侧窗口标志下发。"""
        self._fmt_log = bool(on)
        self._settings.setValue("fmtLog", self._fmt_log)
        self._push_fmt_log_flag()
        self.show_status(T("格式化操作日志已开启", "Format operation logging enabled") if self._fmt_log else "格式化操作日志已关闭")

    def _push_fmt_log_flag(self):
        """向所有已加载视图下发日志开关（window.setFmtLog）。"""
        code = f"window.setFmtLog && window.setFmtLog({js(bool(self._fmt_log))})"
        for role, v in (("edit", self._view), ("src", self._view_src), ("prev", self._view_prev)):
            if v is not None and self._vstate.get(role, {}).get("loaded"):
                self._js_view(v, code)

    def show_fmt_log(self):
        """帮助 → 格式化操作日志：查看 / 复制 / 导出 / 清空。"""
        dlg = FmtLogDialog(self)
        dlg.exec()

    # ---- v3.25 图片存储操作：重命名 / 内嵌 ↔ 相对路径（编辑器悬浮按钮发起） ----
    def _handle_img_req(self, req):
        """处理编辑器 collect 轮询带出的图片操作请求，完成后回调 imgReqDone。"""
        if not isinstance(req, dict):
            return
        act = str(req.get("act") or "")
        idx = req.get("idx")
        src = str(req.get("src") or "")
        if act == "imgRename":
            self._img_rename(idx, src, str(req.get("name") or "").strip())
        elif act == "imgToEmbed":
            self._img_to_embed(idx, src)
        elif act == "imgToAssets":
            self._img_to_assets(idx, src)
        elif act == "imgCopy":
            self._img_copy(idx, src)
        elif act == "imgCrop":                                                     # v3.39.6（IMG-CROP）
            # v3.39.8：异常兜底 —— 此前未捕获异常会让裁剪静默失败（无提示无回调）
            try:
                self._img_crop(idx, src, req)
            except Exception as e:                                                 # noqa: BLE001
                self.show_status(T(f"裁剪失败：{e}", f"Crop failed: {e}"))
        elif act == "imgReplace":
            self._img_replace(idx, str(req.get("mode") or "assets"))   # v3.38
        elif act == "mmdToImg":
            self._mmd_to_img(idx, str(req.get("dataUrl") or ""))       # v3.38（MMD-TOIMG）

    def _mmd_to_img(self, idx, data_url):
        """v3.38（MMD-TOIMG）：图表「转化为图片」—— PNG 落盘 assets（相对路径），
        回调后编辑器整块替换为图片语法；单向不可逆（不保留图表源码）。"""
        m = re.match(r"^data:image/png;base64,(.*)$", data_url, re.S)
        if not m:
            self.show_status(T("图表转图片失败：图片数据无效", "Chart-to-image failed: invalid image data"))
            return
        try:
            data = base64.b64decode(m.group(1))
        except (ValueError, binascii.Error):
            self.show_status(T("图表转图片失败：图片数据无效", "Chart-to-image failed: invalid image data"))
            return
        rel = self._save_image_to_assets(data=data, filename="chart.png")
        if not rel:
            self.show_status(T("图表转图片失败：请先保存文档", "Chart-to-image failed: save the document first"))
            return
        self._js_active(f"window.__doMmdToImg({int(idx)}, {js(rel)})")
        self.show_status(T(f"图表已转换为图片 · {rel}", f"Chart converted to image · {rel}"))

    def _img_replace(self, idx, mode):
        """v3.38（图片报告 §四#9）：右键「替换图片」—— 选图后按当前存储形态替换 src。"""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "替换图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg);;所有文件 (*)")
        if not path:
            return
        name = os.path.basename(path)
        new_src = None
        if mode == "assets":
            new_src = self._save_image_to_assets(src_path=path, filename=name)
        if not new_src:
            try:
                with open(path, "rb") as f:
                    raw = f.read()
            except OSError as e:
                self.show_status(T(f"替换图片失败：{e}", f"Replace image failed: {e}"))
                return
            mime = IMG_MIME.get(os.path.splitext(name)[1].lower() or ".png", "image/png")
            new_src = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        self._js_active(f"window.__doImgReplace({int(idx)}, {js(new_src)})")
        self.show_status(T(f"已替换图片 · {name}", f"Image replaced · {name}"))

    def _img_bytes(self, src):
        """v3.30.16：把图片块的 src 取成字节（本地文件 / data URL / 网络图）。"""
        m = re.match(r"^data:([^;,]+);base64,(.*)$", src, re.S)
        if m:
            try:
                return base64.b64decode(m.group(2))
            except (ValueError, binascii.Error):
                return None
        if re.match(r"^https?:", src, re.I):
            try:
                import urllib.request
                with urllib.request.urlopen(src, timeout=15) as resp:
                    return resp.read()
            except Exception:      # noqa: BLE001
                return None
        fp = self._img_local_path(src)
        if not fp or not os.path.isfile(fp):
            return None
        try:
            with open(fp, "rb") as f:
                return f.read()
        except OSError:
            return None

    def _img_copy(self, idx, src):
        """v3.30.16：右键「复制图片」—— 以位图形式写入系统剪贴板，
        可直接粘贴到微信 / Word / 画图等。不改文档、不入撤销历史。"""
        data = self._img_bytes(src)
        if not data:
            self.show_status(T("复制图片失败：取不到图片数据（本地文件缺失 / 网络图下载失败）", "Copy image failed: cannot get image data (local file missing / network image download failed)"))
            return
        img = QImage()
        if not img.loadFromData(data):
            self.show_status(T("复制图片失败：无法识别的图片格式", "Copy image failed: unrecognized image format"))
            return
        QGuiApplication.clipboard().setImage(img)
        self.show_status(T(f"图片已复制到剪贴板（{img.width()}×{img.height()}）", f"Image copied to clipboard ({img.width()}×{img.height()})"))

    def _img_crop(self, idx, src, req):
        """v3.39.6（IMG-CROP）：按自然像素裁剪图片并写回。
        内嵌 → 新 data URL（保留原格式）；本地文件 → 同目录另存 *-crop 新文件
        （相对路径回相对路径、绝对路径回绝对路径，原图保留不动）；
        网络图 → 下载后落 assets（未保存文档时内核侧已拦截）。
        完成后回调 __doImgCrop（保留 alt / 图注 / 对齐，清除旧显示尺寸）。"""
        try:
            x = max(0, int(req.get("x") or 0))
            y = max(0, int(req.get("y") or 0))
            w = int(req.get("w") or 0)
            h = int(req.get("h") or 0)
        except (TypeError, ValueError):
            self.show_status(T("裁剪失败：裁剪区域参数无效", "Crop failed: invalid crop-region parameters"))
            return
        data = self._img_bytes(src)
        if not data:
            self.show_status(T("裁剪失败：取不到图片数据（文件缺失 / 下载失败）", "Crop failed: cannot get image data (file missing / download failed)"))
            return
        img = QImage()
        if not img.loadFromData(data):
            self.show_status(T("裁剪失败：无法识别的图片格式", "Crop failed: unrecognized image format"))
            return
        w = min(w, img.width() - x)
        h = min(h, img.height() - y)
        if w < 2 or h < 2:
            self.show_status(T("裁剪失败：裁剪区域过小", "Crop failed: crop region too small"))
            return
        crop = img.copy(x, y, w, h)

        def _fmt_of(name_or_mime):
            n = str(name_or_mime or "").lower()
            if n.endswith((".jpg", ".jpeg")) or "jpeg" in n:
                return "JPG"
            if n.endswith(".webp"):
                return "WEBP"
            return "PNG"

        new_src = None
        if re.match(r"^data:", src, re.I):
            mm = re.match(r"^data:([^;,]+);base64,", src, re.I)
            fmt = _fmt_of(mm.group(1) if mm else "png")
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            if not crop.save(buf, fmt):
                self.show_status(T("裁剪失败：图片编码失败", "Crop failed: image encoding failed"))
                return
            buf.close()
            mime = "image/jpeg" if fmt == "JPG" else ("image/webp" if fmt == "WEBP" else "image/png")
            new_src = f"data:{mime};base64,{bytes(ba.toBase64()).decode('ascii')}"
        else:
            fp = self._img_local_path(src)
            if fp and os.path.isfile(fp):
                out_dir = os.path.dirname(fp)
                stem, ext = os.path.splitext(os.path.basename(fp))
                if ext.lower() not in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
                    ext = ".png"
                new_name = self._unique_name(out_dir, f"{stem}-crop{ext}")
                out_path = os.path.join(out_dir, new_name)
                if not crop.save(out_path, _fmt_of(ext)):
                    self.show_status(T("裁剪失败：写入文件失败", "Crop failed: file write failed"))
                    return
                if re.match(r"^[A-Za-z]:[\\/]", src):
                    new_src = out_path
                else:
                    # v3.39.10（IMG-CROP-2）：按「原 src 携带的相对目录前缀」回写 ——
                    # 裸文件名（图片与文档同目录）→ 记裸文件名（v3.39.8 语义）；
                    # 带目录前缀（<doc>.assets/xxx.png 等）→ 原样保留该前缀。
                    # 旧判据 dirname(abspath(fp)) == out_dir 恒为真（out_dir 本就
                    # 取自 fp），assets 子目录图片被误记裸文件名 → 相对文档目录
                    # 解析 404，用户感知「裁剪后未生效」
                    _norm = src.replace("\\", "/").strip()
                    while _norm.startswith("./"):
                        _norm = _norm[2:]
                    _dir, _ = os.path.split(_norm)
                    new_src = f"{_dir}/{new_name}" if _dir else new_name
            elif re.match(r"^https?:", src, re.I) and self.file_path:
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QIODevice.WriteOnly)
                if crop.save(buf, "PNG"):
                    buf.close()
                    rel = self._save_image_to_assets(
                        data=bytes(ba), filename=f"image-crop-{int(time.time())}.png")
                    new_src = rel
                else:
                    buf.close()
            if not new_src:
                # v3.39.11（IMG-CROP-3）：区分「未保存无法定位」与「文件真的缺失」
                if not self.file_path:
                    self.show_status(T("裁剪失败：文档未保存，相对路径图片无法定位原图，请先保存文档", "Crop failed: document not saved; cannot locate original of relative-path image; save the document first"))
                else:
                    self.show_status(T(f"裁剪失败：本地图片文件缺失（{src}），请检查路径或重新插入图片", f"Crop failed: local image file missing ({src}); check the path or re-insert the image"))
                return
        # v3.39.12（IMG-CROP-7）：回调带原 src，内核比对一致才写回（防跨块 / 跨文档污染）
        self._js_active(f"window.__doImgCrop && window.__doImgCrop({int(idx)}, {js(new_src)}, {js(src)})")
        self.show_status(T(f"已裁剪图片（{crop.width()}×{crop.height()}）", f"Image cropped ({crop.width()}×{crop.height()})"))

    def _img_local_path(self, src):
        """把图片块的 src 解析成本地文件绝对路径；非本地文件返回 None。"""
        if not src or re.match(r"^(data:|https?:)", src, re.I):
            return None
        if re.match(r"^[A-Za-z]:[\\/]", src):
            return os.path.normpath(src)
        if not self.file_path:
            return None
        rel = src.replace("\\", "/").lstrip("/")
        try:
            rel = urllib.parse.unquote(rel)
        except Exception:      # noqa: BLE001
            pass
        return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(self.file_path)), rel))

    def _img_ask_name(self, title, default_stem):
        """弹框让用户指定存储名称（默认带 5 位自动编号前缀，可连编号一起改）。"""
        fname = self._numbered_asset_name(default_stem, "")   # 借用编号逻辑（不带扩展名）
        text, ok = QInputDialog.getText(self, title, T("存储名称（含编号前缀，可修改）：", "Storage name (with number prefix, editable):"), text=fname)
        if not ok or not text.strip():
            return None
        text = text.strip()
        if not re.match(r'^[^\\/:*?"<>|]+$', text):
            QMessageBox.information(self, title, T("名称包含非法字符（不能含 \\ / : * ? \" < > |）。", 'Name contains illegal characters (cannot include \\ / : * ? \" < > |).'))
            return None
        return text

    def _img_rename(self, idx, src, name):
        """重命名 assets 里的图片文件（连编号一起改），并更新 Markdown 里的路径。"""
        if not name:
            return
        old = self._img_local_path(src)
        if not old or not os.path.isfile(old):
            self.show_status(T("重命名失败：只支持本地 assets 中的图片（内嵌 / 网络图片无文件名）", "Rename failed: only images in local assets are supported (embedded / network images have no filename)"))
            return
        directory = os.path.dirname(old)
        ext = os.path.splitext(old)[1] or ".png"
        stem = name if os.path.splitext(name)[1] else name + ext
        if not os.path.splitext(stem)[1]:
            stem += ext
        new_name = self._unique_name(directory, stem)
        try:
            os.rename(old, os.path.join(directory, new_name))
        except OSError as e:
            self.show_status(T(f"重命名失败：{e}", f"Rename failed: {e}"))
            return
        new_rel = f"{os.path.basename(directory)}/{new_name}"
        self._js_active(f"window.imgReqDone && window.imgReqDone({int(idx)}, {js(new_rel)})")
        self.show_status(T(f"图片已重命名 · {new_name}", f"Image renamed · {new_name}"))

    def _img_to_embed(self, idx, src):
        """相对路径 → 内嵌：读文件转 data URL 写回。
        v3.31.3（IMG-12）：写回成功后删除 assets 里的原文件（避免留下
        不再被引用的孤儿文件）；删除失败（占用 / 只读）仅提示、不影响转换。"""
        fp = self._img_local_path(src)
        if not fp or not os.path.isfile(fp):
            self.show_status(T("转为内嵌失败：找不到图片文件", "Convert to embedded failed: image file not found"))
            return
        ext = os.path.splitext(fp)[1].lower()
        mime = IMG_MIME.get(ext, "image/png")
        try:
            with open(fp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except OSError as e:
            self.show_status(T(f"转为内嵌失败：{e}", f"Convert to embedded failed: {e}"))
            return
        data_url = f"data:{mime};base64,{b64}"
        self._js_active(f"window.imgReqDone && window.imgReqDone({int(idx)}, {js(data_url)})")
        removed = ""
        try:
            # 安全守卫：只删当前文档 assets 目录内的文件（绝对路径引用的
            # 外部图片不删 —— 那可能是用户其它场景仍在用的源文件）
            assets = self._assets_dir_for(self.file_path) if self.file_path else None
            in_assets = bool(assets) and os.path.normcase(os.path.dirname(os.path.abspath(fp))) == \
                os.path.normcase(os.path.abspath(assets))
            if in_assets:
                os.remove(fp)
                removed = "，原文件已删除"
            else:
                removed = "（图片在 assets 目录外，原文件保留）"
        except OSError as e:
            removed = f"，原文件删除失败（{e}），请手动清理"
        self.show_status(T(f"图片已转为内嵌 data URL{removed}", f"Image converted to embedded data URL{removed}"))

    def _img_to_assets(self, idx, src):
        """内嵌 data URL / 网络图片 / 本地文件 → 相对路径落盘（弹框指定名称）。"""
        data = None
        default_stem = "图片"
        m = re.match(r"^data:([^;,]+);base64,(.*)$", src, re.S)
        if m:
            ext = MIME_EXT.get(m.group(1).lower(), ".png")
            try:
                data = base64.b64decode(m.group(2))
            except (ValueError, binascii.Error):
                self.show_status(T("转为相对路径失败：内嵌数据解码错误", "Convert to relative path failed: embedded data decode error"))
                return
            default_stem = "图片" + ext
            name = self._img_ask_name("转为相对路径", os.path.splitext(default_stem)[0])
        elif re.match(r"^https?:", src, re.I):
            name = self._img_ask_name("下载网络图片", "图片")
            if name is None:
                return
            try:
                import urllib.request
                with urllib.request.urlopen(src, timeout=15) as resp:
                    raw = resp.read()
                ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                ext = MIME_EXT.get(ctype, ".png")
                data = raw
            except Exception as e:      # noqa: BLE001 — 网络 / 超时 / 解码错误统一提示
                self.show_status(T(f"网络图片下载失败，已保持原样：{e}", f"Network image download failed; kept as-is: {e}"))
                return
        else:
            fp = self._img_local_path(src)
            if not fp or not os.path.isfile(fp):
                self.show_status(T("转为相对路径失败：找不到图片文件", "Convert to relative path failed: image file not found"))
                return
            default_stem = os.path.splitext(os.path.basename(fp))[0] or "图片"
            name = self._img_ask_name("转为相对路径", default_stem)
            if name is None:
                return
            try:
                with open(fp, "rb") as f:
                    data = f.read()
                ext = os.path.splitext(fp)[1].lower() or ".png"
            except OSError as e:
                self.show_status(T(f"转为相对路径失败：{e}", f"Convert to relative path failed: {e}"))
                return
        if name is None:
            return
        if not self.file_path:
            self.show_status(T("请先把文档保存到文件，再转为相对路径（需要确定 assets 目录）", "Save the document to a file first, then convert to relative path (assets folder must be determined)"))
            return
        uext = os.path.splitext(name)[1].lower()
        if uext:                        # 用户在名称里自带了扩展名
            ext, stem = uext, os.path.splitext(name)[0]
        else:
            stem = name
        fname = self._numbered_asset_name(stem, ext or ".png")
        try:
            rel = self._save_image_to_assets(data=data, filename=fname)
        except OSError as e:
            self.show_status(T(f"图片落盘失败：{e}", f"Image save failed: {e}"))
            return
        if not rel:
            self.show_status(T("请先把文档保存到文件，再转为相对路径", "Save the document to a file first, then convert to relative path"))
            return
        self._js_active(f"window.imgReqDone && window.imgReqDone({int(idx)}, {js(rel)})")
        self.show_status(T(f"图片已转为相对路径 · {rel}", f"Image converted to relative path · {rel}"))

    # ---- 迁移：把文档里已有的内嵌图片抽出成文件 ----
    def migrate_embedded_images(self):
        """把当前文档中内嵌的 data URL 图片写入 assets 目录并替换为相对路径。"""
        if not self.file_path:
            QMessageBox.information(
                self, "迁移内嵌图片",
                "请先把文档保存到文件，再执行迁移（需要据此确定 assets 目录位置）。")
            return

        def cb(md):
            if not md:
                return
            new_md, count, failed = self._extract_embedded_images(md)
            if count == 0:
                QMessageBox.information(self, T("迁移内嵌图片", "Migrate Embedded Images"),
                                        "本文档没有内嵌的 data URL 图片，无需迁移。")
                return
            assets = os.path.basename(self._assets_dir_for(self.file_path))
            btn = QMessageBox.question(
                self, "迁移内嵌图片",
                f"检测到 {count} 张内嵌图片。\n\n"
                f"将把它们写入 「{assets}」文件夹，并把文档中的路径替换为相对路径，\n"
                f"文档体积会显著变小（相对路径图片也可被其它编辑器复用）。\n\n"
                f"是否继续？",
                QMessageBox.Ok | QMessageBox.Cancel)
            if btn != QMessageBox.Ok:
                return
            try:
                out = new_md if new_md.endswith("\n") else new_md + "\n"
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(out)
            except OSError as e:
                QMessageBox.critical(self, T("迁移失败", "Migration failed"), str(e))
                return
            if 0 <= self._cur < len(self._docs):
                self._docs[self._cur]["content"] = out
            self._dirty = False
            self._js_active(f"window.setMarkdown({js(new_md)})")
            self._push_doc_dir()
            msg = f"已迁移 {count} 张内嵌图片到 {assets}"
            if failed:
                msg += f"（{failed} 张解码失败已保留原样）"
            self.show_status(msg + T("，请按 Ctrl+S 确认保存", ", press Ctrl+S to confirm save"))

        self._js_active("window.getMarkdown()", cb)

    def _extract_embedded_images(self, md):
        """把 md 中的 data URL 图片落盘，返回 (新文本, 成功数, 失败数)。"""
        ok = [0]
        bad = [0]

        def repl(m):
            alt, _url, subtype, b64 = m.group(1), m.group(2), m.group(3), m.group(4)
            ext = "." + subtype.lower().replace("jpeg", "jpg").replace("svg+xml", "svg")
            stem = (alt or "image").strip() or "image"
            stem = re.sub(r'[\\/:*?"<>|\s]+', "_", stem)[:40] or "image"
            try:
                raw = base64.b64decode(re.sub(r"\s+", "", b64))
                rel = self._save_image_to_assets(data=raw, filename=stem + ext)
            except (OSError, ValueError, binascii.Error):
                rel = None
            if not rel:
                bad[0] += 1
                return m.group(0)
            ok[0] += 1
            return f"![{alt}]({rel})"

        return IMG_DATA_RE.sub(repl, md), ok[0], bad[0]

    def _on_collect(self, res):
        if not res:
            return
        try:
            data = json.loads(res)
        except (TypeError, ValueError):
            return
        if data.get("stats"):
            s = data["stats"]
            self._stats = dict(s) if isinstance(s, dict) else {}
            n = int(self._stats.get("chars", 0) or 0)
            self._count.setText(T(f"字数 {n:,} · 约 {int(self._stats.get('readMin', 0) or 0)} 分钟", f"Words {n:,} · ~{int(self._stats.get('readMin', 0) or 0)} min"))
        if data.get("img"):
            self._handle_pasted_image(data.get("img"))
        if data.get("req"):
            self._handle_img_req(data.get("req"))
        # v3.39.8（FMT-LOG）：内核格式化操作日志差量上报 → JSON Lines 追加落盘
        if data.get("fmt"):
            self._append_fmt_log(data["fmt"])
        if data.get("border"):
            self._theme_border = str(data.get("border"))   # v3.38（HR-8②）
        if data.get("outline") is not None:
            self._outline_cache = data.get("outline") or []
            self._sidebar.set_outline(data.get("outline"))
        if data.get("pick"):
            self._js_active("window.__wantPick = false")
            self._pick_local_image()
        md = data.get("md")
        dirty = bool(data.get("dirty"))
        # v3.38（TAB-1）：JS 的 dirty 是「自上次 collect 以来有改动」的**边沿**信号
        # （editor.html 读取即清零），只能用来「置脏」；清脏只由保存 / 关闭负责，
        # 否则停止敲键 0.7s 后 • 标记就会消失。per-doc 落盘见 _docs[i]["dirty"]。
        if 0 <= self._cur < len(self._docs):
            _doc = self._docs[self._cur]
            if dirty:
                _doc["dirty"] = True
            self._dirty = bool(_doc.get("dirty"))
        else:
            self._dirty = dirty
        # v3.40（UI-R7）：保存态格跟随脏态（内部有变化检测，无变化零开销）
        self._update_save_cell()
        if self._autosave and 0 <= self._cur < len(self._docs):
            doc = self._docs[self._cur]
            if dirty and doc.get("path"):
                # v3.44（AUTOSAVE-INT）：非实时档按间隔节流写盘
                _iv = int(getattr(self, "_autosave_interval", 0) or 0)
                _now = time.time()
                if _iv <= 0 or (_now - getattr(self, "_autosave_ts", 0)) >= _iv:
                    self._autosave_ts = _now
                    # 自动保存（保证文件以单个换行结尾）
                    try:
                        out = md or ""
                        if out and not out.endswith("\n"):
                            out += "\n"
                        # v3.29d（B1）：写盘前先把上一版留档到版本历史 —— 此前自动保存
                        # 直接写盘，磁盘内容永远等于新内容，之后手动保存的快照被去重
                        # 跳过，默认配置下版本历史形同虚设。加 60 秒节流控制 IO 频率。
                        last = getattr(self, "_snap_ts", {})
                        if _now - last.get(doc["path"], 0) >= 60:
                            self.snapshot_history(doc["path"], out)
                            last[doc["path"]] = _now
                            self._snap_ts = last
                        self._write_text(doc["path"], out)   # v3.29d（B2）：按原编码写盘
                        self.show_status(T(f"已自动保存 · {doc['path']}", f"Auto-saved · {doc['path']}"))
                    except OSError as e:
                        self._status.setText(T(f"自动保存失败：{e}", f"Auto-save failed: {e}"))
        # v3.32（P0-1）：未命名文档影子草稿 —— 10 秒节流写入 %APPDATA%/mdEditor/drafts/，
        # 崩溃 / 断电后启动可恢复；内容清空即删草稿；保存到路径后由 save_file_as 收走。
        if 0 <= self._cur < len(self._docs):
            doc = self._docs[self._cur]
            if not doc.get("path") and md is not None:
                if md.strip():
                    if dirty:
                        self._save_draft(doc, md)
                elif doc.get("draft"):
                    self._remove_draft(doc)
        # 双栏：同步到预览
        if self._dual and md is not None and md != self._last_preview_md:
            self._last_preview_md = md
            stp = self._vstate["prev"]
            if stp["loaded"]:
                self._js_view(self._view_prev, f"window.setPreviewContent({js(md)})")
        self._refresh_tab_texts()
        self._update_title()

    def _refresh_tab_texts(self):
        for i, doc in enumerate(self._docs):
            name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
            # v3.38（TAB-1）：改读 per-doc dirty —— 顺带修掉「非当前标签不显示 •」
            mark = " • " if doc.get("dirty") else "  "
            # v3.38（TAB-7）：固定标签加 📌 前缀（N++ / 浏览器对标，强提示 + 排左）
            if doc.get("pinned"):
                mark = "📌 " + mark.lstrip()
            self._tabbar.setTabText(i, f"{mark}{name}")
        self._update_tb_more()   # v3.38（TAB-9）：标签溢出态随文本变化重算
        self._update_multi_highlight()   # v3.38（TAB-B）：多选高亮随重建恢复

    # ---- TAB-B：多选标签高亮 ----
    def _update_multi_highlight(self):
        """多选标签着主题强调色；未选中的恢复默认文字色（QColor() = 清除覆盖）。"""
        self._tab_multi = {i for i in self._tab_multi if 0 <= i < len(self._docs)}
        # v3.39.15（UISTYLE-1）：强调色取「主题 + 风格」合并调色板，与界面观感一致
        col = QColor(uistyles.merge_palette(self._theme)["accent"]) if self._tab_multi else None
        for i in range(self._tabbar.count()):
            self._tabbar.setTabTextColor(i, col if (col and i in self._tab_multi)
                                         else QColor())

    # ---- TAB-7：固定标签（Pin）----
    def _toggle_pin(self, idx):
        """固定 / 取消固定：固定标签不可关闭、批量关闭跳过、强制排在未固定之前。"""
        if not (0 <= idx < len(self._docs)):
            return
        doc = self._docs[idx]
        doc["pinned"] = not doc.get("pinned")
        name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
        self.show_status(T(f"已{'固定' if doc['pinned'] else '取消固定'} · {name}", f"{'Pinned' if doc['pinned'] else 'Unpinned'} · {name}"))
        self._enforce_pin_order()
        self._refresh_tab_texts()

    def _enforce_pin_order(self):
        """把固定标签稳定地排到未固定标签之前（必要时重建标签条，保持当前文档）。"""
        order = sorted(range(len(self._docs)),
                       key=lambda i: not self._docs[i].get("pinned"))   # 稳定排序
        if order == list(range(len(self._docs))):
            return
        old_cur = self._cur
        self._docs = [self._docs[i] for i in order]
        self._tabbar.blockSignals(True)
        while self._tabbar.count():
            self._tabbar.removeTab(0)
        for _ in self._docs:
            self._tabbar.addTab("")
        self._tabbar.blockSignals(False)
        if 0 <= old_cur < len(self._docs):
            self._cur = order.index(old_cur)
            self._tabbar.setCurrentIndex(self._cur)

    # ---- TAB-9：标签溢出下拉（N++ / VS Code 对标）----
    def _update_tb_more(self):
        """标签总宽超出标签栏可视宽度时启用 » 下拉按钮。"""
        if not hasattr(self, "_btn_tb_more"):
            return
        tb = self._tabbar
        overflow = (tb.count() > 1 and tb.sizeHint().width() > tb.width() + 2)
        self._btn_tb_more.setEnabled(overflow)
        self._btn_tb_more.setToolTip(T("所有标签页", "All Tabs") if overflow else "所有标签页（无溢出）")

    def _show_tb_more_menu(self):
        m = QMenu(self)
        for i, doc in enumerate(self._docs):
            name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
            text = ("📌 " if doc.get("pinned") else "") + ("• " if doc.get("dirty") else "") + name
            a = m.addAction(("● " if i == self._cur else "    ") + text)
            a.triggered.connect(lambda _c=False, k=i: self._tabbar.setCurrentIndex(k))
        m.exec(self._btn_tb_more.mapToGlobal(
            self._btn_tb_more.rect().bottomLeft()))

    def _update_title(self):
        name = os.path.basename(self.file_path) if self.file_path else "未命名"
        star = " •" if self._dirty else ""
        self.setWindowTitle(f"{name}{star} — {APP_NAME}")

    # ================= 多文档标签 =================
    def _add_doc(self, path=None, text=None):
        # v3.38（TAB-1）：per-doc dirty —— 每个标签自带修改标记（切走再切回不丢）
        # v3.45.7（REQ4）：per-doc mode —— 渲染 / 源码 / 分屏 状态随文件独立保留
        self._docs.append({"path": path, "content": text, "dirty": False, "mode": "edit"})
        idx = len(self._docs) - 1
        self._tabbar.addTab(T("未命名", "Untitled") if not path else os.path.basename(path))
        self._tabbar.setCurrentIndex(idx)  # 触发 _on_tab_clicked -> 激活
        return idx

    def _on_tab_clicked(self, idx):
        # 信号同时来自 addTab / setCurrentIndex / 用户点击
        if idx < 0 or idx >= len(self._docs):
            return
        if self._switching:
            return
        if idx == self._cur:
            return
        # v3.45.8（REQ3#9）：跳转历史起点播种（首次导航前以当前文档为起点）
        self._nav_ensure_seed()
        # v3.38（TAB-B）：普通切换即放弃多选（Ctrl/Shift 路径在 eventFilter 已消费事件）
        if self._tab_multi:
            self._tab_multi.clear()
            self._multi_anchor = -1
            self._update_multi_highlight()
        # 编辑视图尚未加载完成时无法取回内容，直接同步激活
        if not self._vstate[self._active_role()]["loaded"]:
            # v3.45.8（REQ3#9）：记录本次切换到达的目标文档
            self._nav_arrive(self._docs[idx]["path"], delay=550)
            self._pending_switch = idx
            self._on_switch_capture(None)
            return
        # 切换前先把当前内容存入缓存
        self._pending_switch = idx
        self._switching = True
        # v3.45.8（REQ3#9）：记录本次切换到达的目标文档（延迟到加载后读比例）
        self._nav_arrive(self._docs[idx]["path"], delay=550)
        self._js_active("window.getMarkdown()", self._on_switch_capture)

    def _on_switch_capture(self, md):
        # v3.38（TAB-1）：切走前把当前文档的修改标记存回 doc（旧实现直接丢弃，
        # 切走再切回 • 就没了，「关闭所有未修改」也无从判断）
        if 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["dirty"] = bool(self._dirty)
        if self._cur >= 0 and self._cur < len(self._docs) and md is not None:
            self._docs[self._cur]["content"] = md
        target = self._pending_switch
        self._switching = False
        if target < 0 or target >= len(self._docs):
            return
        self._cur = target
        doc = self._docs[target]
        # v3.38（TAB-8）：切换完成 → 该文档移到 MRU 最前
        self._mru = [doc] + [x for x in self._mru if x is not doc]
        self.file_path = doc.get("path")
        text = doc.get("content")
        if text is None:
            text = self._read_file(self.file_path) if self.file_path else ""
            doc["content"] = text
        self._last_preview_md = None
        self._push_doc_dir()   # 图片相对路径随文档目录变化（先于正文下发）
        self._push_text(text)
        # v3.45.7（REQ4）：恢复该文件自身的模式（渲染 / 源码 / 分屏）
        doc_mode = doc.get("mode", "edit")
        if doc_mode == "dual":
            self._set_mode("dual", force=True)
        elif doc_mode != self._mode:
            self._set_mode(doc_mode, force=True)
        else:
            # v3.48.22（LINUX-FIX2）：视图未加载完成时 window.setSourceMode 尚未定义，
            # 直接 runJavaScript 会报 "is not a function"（Linux 真机启动日志实测）。
            # 与 1569/6018/6034 各点同口径：未加载时跳过，_on_loaded 会按 st["src"] 重新下发。
            if self._vstate["edit"]["loaded"]:
                self._js_active("window.setSourceMode(%s)"
                                % ("true" if doc_mode == "src" else "false"))
            self._dual = False
            self._update_mode_button()
        self._dirty = bool(doc.get("dirty"))   # v3.38（TAB-1）：恢复该文档自己的修改标记
        self._update_title()
        self._refresh_tab_texts()
        if self.file_path:
            self._sidebar.set_root(self.file_path)
            self._status.setText(T(f"已打开 · {self.file_path}", f"Opened · {self.file_path}"))
            if self._book:   # v3.44.34（BOOK-1）：书籍中切换文档时高亮对应章节
                self._sidebar.highlight_book_path(self.file_path)
                self._record_book_chapter()   # v3.45.7（BOOK-READ-1）
        else:
            self._sidebar.clear_current_file()   # v3.38（OUT-3）：清除残留的文件上下文与高亮
            self.show_status(T("未命名文档", "Untitled Document"))
        self._remember_last_session()   # v3.38（OUT-5）
        # 期间用户又点了其他标签 -> 继续处理最新请求
        self.refresh_wiki()  # v3.44.37（BACKLINK-3）：切换后重建双链索引与反向链接
        self.refresh_backlinks()  # v3.48.13（BACKLINK-4）：反链页可见时同步刷新
        if self._tabbar.currentIndex() != self._cur:
            QTimer.singleShot(0, lambda: self._on_tab_clicked(self._tabbar.currentIndex()))

    def _on_tab_moved(self, frm, to):
        doc = self._docs.pop(frm)
        self._docs.insert(to, doc)
        if self._cur == frm:
            self._cur = to
        elif frm < self._cur <= to:
            self._cur -= 1
        elif to <= self._cur < frm:
            self._cur += 1
        # v3.38（TAB-7）：拖动后固定标签仍须排在未固定之前
        self._enforce_pin_order()

    def _close_tab(self, idx):
        if idx < 0 or idx >= len(self._docs) or self._switching:
            return
        doc = self._docs[idx]
        # v3.38（TAB-7）：固定标签不可关闭（关闭按钮 / Ctrl+W / 菜单统一入口守卫）
        if doc.get("pinned"):
            name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
            self.show_status(T(f"标签已固定，请先取消固定再关闭 · {name}", f"Tab is pinned; unpin it before closing · {name}"))
            return

        def do_close(cached_md=None):
            if cached_md is not None:
                doc["content"] = cached_md
            # 未命名且非空 -> 提示保存
            if doc.get("path") is None and (doc.get("content") or "").strip():
                btn = QMessageBox.question(
                    self, "关闭未命名文档",
                    "该文档尚未保存到文件，关闭将丢失内容。是否保存？",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                if btn == QMessageBox.Cancel:
                    return
                if btn == QMessageBox.Save:
                    self._cur = idx
                    self.file_path = None
                    if not self.save_file_as():
                        return
                    doc["path"] = self.file_path
                elif btn == QMessageBox.Discard:
                    self._remove_draft(doc)   # v3.32（P0-1）：明确丢弃 → 草稿一并删除
            self._drop_doc(idx)   # v3.38（TAB-3）：关闭即压入回溯栈（Ctrl+Shift+T 可恢复）
            if not self._docs:
                self._cur = -1
                self.file_path = None
                self._add_doc(path=None, text="")
                return
            if idx == self._cur:
                self._cur = -1
                new_idx = min(idx, len(self._docs) - 1)
                self._tabbar.setCurrentIndex(new_idx)
                self._on_tab_clicked(new_idx)
            else:
                if idx < self._cur:
                    self._cur -= 1
            self._refresh_tab_texts()
            self._update_title()

        if idx == self._cur:
            do_close(self._capture_current_md())
        else:
            do_close()

    # ============ 标签页：选中 / 关闭 / 批量 / 复制路径（v3.38 TAB-1~TAB-6） ============
    # 设计依据：docs/archive/标签页右键菜单方案-批量关闭与复制路径-v3.38.md
    CLOSED_STACK_MAX = 10

    def _capture_current_md(self):
        """同步取回当前视图的实时 Markdown 并回写当前 doc。

        批量关闭 / 关闭前判定「未命名非空」都要用实时内容——doc["content"] 只在
        切换与保存时才回写，停在编辑器里敲的字还留在 WebEngine 侧。
        """
        from PySide6.QtCore import QEventLoop
        box = {}
        loop = QEventLoop()

        def cb(md):
            box["md"] = md
            loop.quit()

        self._js_active("window.getMarkdown()", cb)
        loop.exec()
        md = box.get("md")
        if md is not None and 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["content"] = md
        return md

    def _doc_text(self, idx):
        """第 idx 个文档的 Markdown。

        当前文档取**实时内容**（编辑器里的字还没回写 doc）；其余文档直接取缓存 ——
        切走时 `_on_switch_capture` 已把实时内容写回，缓存即最新，无需再切视图取回
        （切视图取回有「页面还没渲染完就开始读」的竞态，反而会读到上一个文档的内容）。
        """
        if idx == self._cur:
            md = self._capture_current_md()
            if md is not None:
                return md
        return self._docs[idx].get("content") or ""

    def _drop_doc(self, idx, remember=True):
        """移除第 idx 个文档（缓存 + 标签），按需压入「重新打开」回溯栈。"""
        doc = self._docs.pop(idx)
        self._tabbar.removeTab(idx)
        if remember:
            self._closed_stack.append(dict(doc))
            del self._closed_stack[:-self.CLOSED_STACK_MAX]
        return doc

    def _unnamed_nonempty(self, idx):
        """未命名且非空 —— 沿用 _close_tab 的确认口径。"""
        doc = self._docs[idx]
        if doc.get("path") is not None:
            return False
        if idx == self._cur:
            return bool(self._dirty or (doc.get("content") or "").strip())
        return bool((doc.get("content") or "").strip())

    def _save_doc_as_sync(self, idx):
        """给指定标签弹「另存为」并**同步**落盘（批量流程用，避免异步写入与切标签交错）。"""
        doc = self._docs[idx]
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Markdown 文件", self._dlg_start("save", doc.get("path") or "未命名.md"),
            "Markdown 文件 (*.md);;所有文件 (*.*)")
        if not path:
            return False
        path = os.path.abspath(path)
        md = self._doc_text(idx)
        text = md if md.endswith("\n") else md + "\n"
        try:
            self.snapshot_history(path, text)
            self._write_text(path, text)
        except OSError as e:
            QMessageBox.critical(self, T("保存失败", "Save failed"), f"{path}\n{e}")
            return False
        self._remember_dir("save", path)
        doc["path"] = path
        doc["content"] = md
        doc["dirty"] = False
        if idx == self._cur:
            self.file_path = path
            self._dirty = False
            self._push_doc_dir()
        self._remove_draft(doc)                  # v3.32（P0-1）：有路径后草稿收走
        self._remember_last_session()            # v3.38（OUT-5）
        self._refresh_tab_texts()
        self._update_title()
        # v3.48.30（FILE-SAVE）：另存为后自动刷新侧栏文件列表
        self._sidebar.refresh_after_save(path)
        return True

    def _perform_batch_close(self, idxs, discard_unnamed=False):
        """倒序移除给定索引集合，随后修正 _cur / 选中态 / 正文（索引不漂移）。"""
        self._clear_tab_multi()   # v3.38（TAB-B）：关闭后索引漂移，多选集作废
        idxset = {i for i in idxs if 0 <= i < len(self._docs)}
        if not idxset:
            return 0
        old_cur = self._cur
        cur_closed = old_cur in idxset
        closed = 0
        for i in sorted(idxset, reverse=True):
            if discard_unnamed and self._docs[i].get("path") is None:
                self._remove_draft(self._docs[i])   # 明确丢弃 → 草稿一并删除
            self._drop_doc(i)
            closed += 1
        if not self._docs:
            self._cur = -1
            self.file_path = None
            self._switching = False
            self._dirty = False
            self._add_doc(path=None, text="")        # 沿用「空栈自动补空白页」
            self._update_title()
            self._refresh_tab_texts()
            return closed
        if cur_closed:
            # 当前文档被关掉：置 -1 后走激活路径，让 _on_tab_clicked 从缓存装载正文
            # （否则会被 idx == self._cur 的短路守卫挡掉）
            self._cur = -1
            self._switching = False
            new_idx = min(max(old_cur - sum(1 for i in idxset if i < old_cur), 0),
                          len(self._docs) - 1)
            self._tabbar.setCurrentIndex(new_idx)
            self._on_tab_clicked(new_idx)
        else:
            # 当前文档保留：只同步索引漂移，**不要**从 doc["content"] 重载
            # （当前文档的缓存可能滞后于编辑器，重载会吞掉正在输入的内容）
            self._cur = old_cur - sum(1 for i in idxset if i < old_cur)
            self._tabbar.blockSignals(True)
            self._tabbar.setCurrentIndex(self._cur)
            self._tabbar.blockSignals(False)
        self._refresh_tab_texts()
        self._update_title()
        return closed

    def _batch_close(self, idxs, ask=True):
        """批量关闭确认链（Notepad++ 对标）：

        未保存文档（含**已命名但 dirty** 的）→ 一次汇总确认
        「全部保存 / 全部不保存 / 取消」→ 倒序执行，任一保存被取消则整批中止。
        """
        if self._switching:
            return 0
        idxs = sorted({i for i in idxs if 0 <= i < len(self._docs)})
        if not idxs:
            return 0
        if self._cur in idxs:
            self._capture_current_md()               # 实时内容回写，保证判定与保存内容正确
            self._docs[self._cur]["dirty"] = bool(self._dirty)   # 当前文档脏标记取实时
        need_unnamed = [i for i in idxs if self._unnamed_nonempty(i)]
        # v3.38（TAB-B）：已命名未保存的文档**必须**进确认（旧版只确认未命名，
        # 有路径的 dirty 文档会被静默关闭丢内容）
        need_named = [i for i in idxs if self._docs[i].get("path") is not None
                      and self._docs[i].get("dirty")]
        need = need_unnamed + need_named
        discard = not need
        if need and ask:
            box = QMessageBox(self)
            box.setWindowTitle(T("批量关闭", "Batch Close"))
            box.setIcon(QMessageBox.Question)
            names = []
            for i in need[:8]:
                nm = os.path.basename(self._docs[i]["path"]) \
                    if self._docs[i].get("path") else "未命名"
                names.append(f"    {nm}")
            if len(need) > 8:
                names.append(T(f"    …等共 {len(need)} 个", f"    ...and {len(need)} more"))
            box.setText(T(f"要关闭的 {len(idxs)} 个标签页中，{len(need)} 个文档未保存，是否保存后关闭？\n",
                         f"Of the {len(idxs)} tabs to close, {len(need)} documents are unsaved, close after saving?\n") + "\n".join(names))
            b_save = box.addButton(T("全部保存", "Save All"), QMessageBox.AcceptRole)
            b_skip = box.addButton(T("全部不保存", "Don't Save All"), QMessageBox.DestructiveRole)
            box.addButton(T("取消", "Cancel"), QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not b_save and box.clickedButton() is not b_skip:
                return 0
            if box.clickedButton() is b_save:
                for i in sorted(need_unnamed, reverse=True):
                    if not self._save_doc_as_sync(i):
                        return 0                     # 用户取消 → 整批中止，不动任何标签
                for i in sorted(need_named, reverse=True):
                    if not self._save_named_doc_sync(i):
                        return 0
            else:
                discard = True
        return self._perform_batch_close(idxs, discard_unnamed=discard)

    def _save_named_doc_sync(self, idx):
        """v3.38（TAB-B）：已命名文档同步落盘（批量「全部保存」用）。"""
        doc = self._docs[idx]
        if doc.get("path") is None:
            return False
        md = self._doc_text(idx)
        if md is None:
            return False
        text = md if md.endswith("\n") else md + "\n"
        try:
            self.snapshot_history(doc["path"], text)
            self._write_text(doc["path"], text)
        except OSError as e:
            QMessageBox.critical(self, T("保存失败", "Save failed"), f"{doc['path']}\n{e}")
            return False
        self._remember_dir("save", doc["path"])
        doc["content"] = md
        doc["dirty"] = False
        if idx == self._cur:
            self._dirty = False
        self._refresh_tab_texts()
        # v3.48.30（FILE-SAVE）：保存后自动刷新侧栏文件列表
        self._sidebar.refresh_after_save(doc["path"])
        return True

    def _clear_tab_multi(self):
        self._tab_multi.clear()
        self._multi_anchor = -1
        self._update_multi_highlight()

    def _close_all_tabs(self):
        """v3.38（TAB-B）：关闭所有标签页（固定标签跳过，全固定则提示）。"""
        if 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["dirty"] = bool(self._dirty)
        idxs = [i for i in range(len(self._docs)) if not self._docs[i].get("pinned")]
        if not idxs:
            self.show_status(T("没有可关闭的标签页（固定标签需先取消固定）", "No closable tabs (pinned tabs must be unpinned first)"))
            return
        n = self._batch_close(idxs)
        if n:
            self.show_status(T(f"已关闭 {n} 个标签页", f"Closed {n} tabs"))

    def _close_unmodified(self):
        """关闭所有未修改的标签（右键菜单项）；固定标签跳过（TAB-7 语义：不许自动关）。"""
        if 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["dirty"] = bool(self._dirty)   # 实时脏标记优先
        idxs = [i for i in range(len(self._docs))
                if not self._docs[i].get("dirty") and not self._docs[i].get("pinned")]
        if not idxs:
            self.show_status(T("没有未修改的标签页", "No unmodified tabs"))
            return
        n = self._batch_close(idxs)
        if n:
            self.show_status(T(f"已关闭 {n} 个未修改的标签页", f"Closed {n} unmodified tabs"))

    def _open_terminal(self, path):
        """v3.38（TAB-10）：在文件所在目录打开 PowerShell。"""
        d = os.path.dirname(path or "") or None
        try:
            subprocess.Popen("start powershell", shell=True, cwd=d)
            self.show_status(T(f"已打开终端 · {d or '当前目录'}", f"Terminal opened · {d or 'Current Directory'}"))
        except OSError as e:
            QMessageBox.warning(self, T("打开终端失败", "Failed to Open Terminal"), str(e))

    def _when_idle(self, fn):
        """等切换锁释放后再执行（右键即选中的异步窗口期保护）。"""
        if self._switching:
            QTimer.singleShot(20, lambda: self._when_idle(fn))
            return
        fn()

    def _on_tab_menu(self, pos):
        """标签右键菜单（对标 Notepad++）：先选中被点标签，再弹菜单。"""
        idx = self._tabbar.tabAt(pos)
        if idx < 0:
            idx = self._cur
        if not (0 <= idx < len(self._docs)):
            return
        # v3.38（TAB-B）：多选感知 —— 右键命中选中集 → 选中与当前标签都保持不动
        #（N++ 语义：对选中集操作）；右键在选中集外 → 放弃多选走普通路径
        multi = {i for i in self._tab_multi if 0 <= i < len(self._docs)} \
            if idx in self._tab_multi else set()
        if self._tab_multi and not multi:
            self._tab_multi.clear()
            self._multi_anchor = -1
            self._update_multi_highlight()
        if not multi and idx != self._cur:
            self._tabbar.setCurrentIndex(idx)        # 右键即选中
        doc = self._docs[idx]
        has_path = doc.get("path") is not None
        # v3.38（TAB-B 修正）：_add_doc 的文档没有 pinned 键 → get 返回 None，
        # setChecked(None) 会 TypeError 令整个右键菜单弹不出来，必须转 bool
        pinned = bool(doc.get("pinned"))
        last = len(self._docs) - 1
        m = QMenu(self)
        # v3.38（TAB-B）：多选生效 → 首位给「关闭选中标签页」+「取消多选」（N++ 对标）
        if multi:
            a = m.addAction(f"关闭选中的 {len(multi)} 个标签页")
            a.triggered.connect(lambda: self._when_idle(
                lambda: self._batch_close(sorted(multi))))
            a = m.addAction("取消多选")
            a.triggered.connect(self._clear_tab_multi)
            m.addSeparator()
        # v3.38（TAB-7）：固定 / 取消固定（Notepad++ 对标第一项）
        a = m.addAction("固定 / 取消固定标签")
        a.setCheckable(True)
        a.setChecked(pinned)
        a.triggered.connect(lambda: self._when_idle(lambda: self._toggle_pin(idx)))
        a = m.addAction("关闭\tCtrl+W")
        a.setEnabled(not pinned)             # TAB-7：固定标签不可直接关闭
        a.triggered.connect(lambda: self._when_idle(lambda: self._close_tab(idx)))
        a = m.addAction("关闭其它所有")
        a.triggered.connect(lambda: self._when_idle(lambda: self._batch_close(
            [i for i in range(len(self._docs)) if i != idx and not self._docs[i].get("pinned")])))
        a = m.addAction("关闭左侧所有")
        a.setEnabled(any(not self._docs[i].get("pinned") for i in range(idx)))
        a.triggered.connect(lambda: self._when_idle(lambda: self._batch_close(
            [i for i in range(idx) if not self._docs[i].get("pinned")])))
        a = m.addAction("关闭右侧所有")
        a.setEnabled(any(not self._docs[i].get("pinned") for i in range(idx + 1, len(self._docs))))
        a.triggered.connect(lambda: self._when_idle(
            lambda: self._batch_close(
                [i for i in range(idx + 1, len(self._docs)) if not self._docs[i].get("pinned")])))
        a = m.addAction("关闭所有未修改")
        a.triggered.connect(lambda: self._when_idle(self._close_unmodified))
        a = m.addAction("关闭所有标签页")
        a.triggered.connect(lambda: self._when_idle(self._close_all_tabs))
        m.addSeparator()
        a = m.addAction("在资源管理器中显示")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self.show_in_explorer(doc.get("path")))
        # v3.38（TAB-10）：在终端中打开（文件所在目录起 PowerShell）
        a = m.addAction("在终端中打开")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self._open_terminal(doc.get("path")))
        m.addSeparator()
        a = m.addAction("复制文件名")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self._copy_to_clip(os.path.basename(doc.get("path") or ""), "文件名"))
        a = m.addAction("复制文件路径")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self._copy_to_clip(doc.get("path") or "", "文件路径"))
        a = m.addAction("复制所在目录")
        a.setEnabled(has_path)
        a.triggered.connect(lambda: self._copy_to_clip(os.path.dirname(doc.get("path") or ""), "所在目录"))
        # v3.48.24（AI-DOC）：标签右键「整篇 AI 优化」—— 先切到该标签再整篇优化
        m.addSeparator()
        # v3.48.36（AI-MENUS）：菜单项可在 系统设置 → AI 菜单 自定义
        from ai_pane import ai_menu_items
        ai_menu = m.addMenu(T("AI优化", "AI Optimize"))
        for _it in ai_menu_items(self._settings, "doc"):
            ai_menu.addAction(
                _it["label"],
                lambda k=_it["key"], pr=_it["prompt"], i=idx:
                self._ai_doc_action_from_tab(k, i, pr))
        m.exec(self._tabbar.mapToGlobal(pos))

    def _copy_to_clip(self, text, what):
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.show_status(T(f"已复制{what}：{text}", f"Copied {what}: {text}"))

    # ---- TAB-3：重新打开关闭的标签 ----
    def _reopen_closed_tab(self):
        if not self._closed_stack:
            self.show_status(T("没有可重新打开的标签页", "No tabs to reopen"))
            return
        doc = self._closed_stack.pop()
        idx = self._add_doc(path=doc.get("path"), text=doc.get("content"))
        self._docs[idx]["dirty"] = bool(doc.get("dirty"))
        self._refresh_tab_texts()
        name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
        self.show_status(T(f"已重新打开 · {name}", f"Reopened · {name}"))

    # ---- TAB-4：上一个 / 下一个标签 ----
    def _cycle_tab(self, step):
        n = len(self._docs)
        if n < 2:
            return
        self._tabbar.setCurrentIndex((self._cur + step) % n)

    # ---- TAB-8：Ctrl+Tab MRU 快切面板 ----
    class _TabSwitcher(QDialog):
        """无边框快切浮层：按 MRU 列出标签，Ctrl+Tab / Ctrl+Shift+Tab 移动选区，
        松开 Ctrl（或回车）确认，Esc 取消。"""

        def __init__(self, win, entries, sel):
            super().__init__(win, Qt.Dialog | Qt.FramelessWindowHint)
            self.setWindowTitle(T("切换标签页", "Switch Tabs"))
            self._win = win
            self._entries = entries          # [(idx, 文本), ...]
            self._sel = sel
            self._result_idx = -1
            lay = QVBoxLayout(self)
            lay.setContentsMargins(10, 10, 10, 10)
            self._list = QLabel(self)
            self._list.setTextFormat(Qt.RichText)
            lay.addWidget(self._list)
            self._render()

        def _render(self):
            rows = []
            for k, (idx, text) in enumerate(self._entries):
                cur = "▶ " if k == self._sel else "&nbsp;&nbsp;&nbsp;"
                rows.append(f"<div style='padding:2px 6px;{'' if k != self._sel else 'background:#3d6db5;color:#fff;border-radius:3px;'}'>"
                            f"{cur}{text}</div>")
            self._list.setText("".join(rows))

        def keyPressEvent(self, ev):
            k, mods = ev.key(), ev.modifiers()
            if k in (Qt.Key_Tab, Qt.Key_Backtab) and mods & Qt.ControlModifier:
                d = 1 if k == Qt.Key_Tab else -1
                n = len(self._entries)
                self._sel = (self._sel + d) % n
                self._render()
                ev.accept()
                return
            if k in (Qt.Key_Return, Qt.Key_Enter):
                self.accept()
                ev.accept()
                return
            if k == Qt.Key_Escape:
                self.reject()
                ev.accept()
                return
            super().keyPressEvent(ev)

        def keyReleaseEvent(self, ev):
            # 松开 Ctrl = 确认（VS Code 语义）
            if ev.key() == Qt.Key_Control:
                self.accept()
                ev.accept()
                return
            super().keyReleaseEvent(ev)

        def run(self):
            self.exec()
            return self._entries[self._sel][0] if self.result() else -1

    def _open_tab_switcher(self):
        self._mru = [d for d in self._mru
                     if any(d is x for x in self._docs)]   # 惰性剔除已关闭
        if len(self._docs) < 2:
            self.show_status(T("只有一个标签页", "Only one tab"))
            return
        # MRU 序优先，缺项（从未切过的标签）按标签条顺序补尾
        order = [self._docs.index(d) if any(d is x for x in self._docs) else -1
                 for d in self._mru]
        order = [i for i in order if i >= 0]
        order += [i for i in range(len(self._docs)) if i not in order]
        entries = []
        for i in order:
            doc = self._docs[i]
            name = os.path.basename(doc["path"]) if doc.get("path") else "未命名"
            if doc.get("dirty"):
                name = "● " + name
            if doc.get("pinned"):
                name = "📌 " + name
            entries.append((i, name))
        sel = 1 if len(entries) > 1 else 0
        idx = self._TabSwitcher(self, entries, sel).run()
        if 0 <= idx < len(self._docs) and idx != self._cur:
            self._tabbar.setCurrentIndex(idx)

    # ---- TAB-6：全部保存 ----
    def save_all(self) -> bool:
        """批量保存「有路径且已修改」的文档；未命名文档不批量弹窗，仅在提示里计数。"""
        n = 0
        skipped = 0
        for i, doc in enumerate(list(self._docs)):
            if not doc.get("dirty"):
                continue
            if not doc.get("path"):
                skipped += 1
                continue
            md = self._doc_text(i)
            if md is None:
                continue
            text = md if md.endswith("\n") else md + "\n"
            try:
                self.snapshot_history(doc["path"], text)
                self._write_text(doc["path"], text)
            except OSError as e:
                QMessageBox.critical(self, T("保存失败", "Save failed"), f"{doc['path']}\n{e}")
                continue
            doc["content"] = md
            doc["dirty"] = False
            if i == self._cur:
                self._dirty = False
            n += 1
        if 0 <= self._cur < len(self._docs):
            self._dirty = bool(self._docs[self._cur].get("dirty"))
        self._refresh_tab_texts()
        # v3.48.30（FILE-SAVE）：全部保存后自动刷新侧栏文件列表
        if n:
            cur_path = self._docs[self._cur].get("path") if 0 <= self._cur < len(self._docs) else None
            self._sidebar.refresh_after_save(cur_path)
        self._update_title()
        msg = f"已保存 {n} 个文档" if n else "没有需要保存的修改"
        if skipped:
            msg += f"（{skipped} 个未命名文档请单独另存）"
        self.show_status(msg)
        return n > 0

    # ---- TAB-5：标签栏鼠标手势见文件末尾 eventFilter（QMainWindow 只能有一个
    #      eventFilter 定义，末位定义生效 —— 早期在此处另写一份会被静默遮蔽）----

    # ================= 文件操作 =================
    @staticmethod
    def _detect_encoding(path):
        """v3.29d（B2）：探测文件编码（BOM / UTF-8 / GBK），供按原编码写回。"""
        try:
            with open(path, "rb") as f:
                raw = f.read(65536)
        except OSError:
            return "utf-8"
        if raw.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass
        try:
            raw.decode("gbk")
            return "gbk"
        except UnicodeDecodeError:
            return "utf-8"

    @staticmethod
    def _read_file(path):
        """读文件：BOM → UTF-8 → GBK 自动回退，避免中文乱码/打不开。
        v3.48.30（IMG-EMBED）：读入后自动愈合被换行拆断的内嵌图片 data URL
        （外部编辑器 / AI 按 76 列换行 base64 会导致图片永远显示源码不渲染）。"""
        with open(path, "rb") as f:
            raw = f.read()
        if raw.startswith(b"\xef\xbb\xbf"):
            return heal_wrapped_images(raw.decode("utf-8-sig", errors="replace"))
        try:
            return heal_wrapped_images(raw.decode("utf-8"))
        except UnicodeDecodeError:
            pass
        try:
            return heal_wrapped_images(raw.decode("gbk"))
        except UnicodeDecodeError:
            return heal_wrapped_images(raw.decode("utf-8", errors="replace"))

    def _write_text(self, path, text):
        """v3.29d（B2）：按打开时识别的原编码写盘 —— GBK 文件保存后仍是 GBK、
        带 BOM 的 UTF-8 保留 BOM，不再一律静默转码成 UTF-8（导出文件除外）。"""
        enc = getattr(self, "_enc_map", {}).get(path, "utf-8")
        if enc not in ("utf-8", "utf-8-sig", "gbk"):
            enc = "utf-8"
        with open(path, "w", encoding=enc) as f:
            f.write(text)

    def new_file(self):
        self._add_doc(path=None, text="")
        # v3.40（UI-R7 R6 补偿②）：新空白文档 → 首次一次性「试试输入 /」气泡
        self._maybe_slash_bubble()

    # ================= v3.32（P0-1）未命名文档影子草稿 =================
    def _save_draft(self, doc, md):
        """未命名文档内容暂存为影子草稿（10 秒节流）。有路径的文档不走此路径。"""
        if os.environ.get("MDEDITOR_SKIP_DRAFT"):
            return   # 测试进程禁用（_runner.py 统一设置），避免污染用户草稿目录
        try:
            os.makedirs(DRAFT_DIR, exist_ok=True)
        except OSError:
            return
        fp = doc.get("draft")
        if not fp:
            fp = os.path.join(DRAFT_DIR, "draft-%s-%d.md"
                              % (time.strftime("%Y%m%d-%H%M%S"), abs(id(doc)) % 100000))
            doc["draft"] = fp
        now = time.time()
        if now - doc.get("draft_ts", 0) < 10:
            return
        try:
            out = md if md.endswith("\n") else md + "\n"
            with open(fp, "w", encoding="utf-8") as f:
                f.write(out)
        except OSError:
            return
        doc["draft_ts"] = now
        self.show_status(T("草稿已自动暂存（未命名文档，崩溃可恢复）", "Draft auto-saved (untitled document, recoverable after crash)"))

    def _remove_draft(self, doc):
        """草稿收走 / 清空时删除对应草稿文件。"""
        fp = doc.pop("draft", None)
        doc.pop("draft_ts", None)
        if fp:
            try:
                if os.path.exists(fp):
                    os.remove(fp)
            except Exception as e:   # noqa: BLE001 — 删除失败不影响主流程
                _log.debug("草稿删除失败: %s (%s)", fp, e)

    def check_draft_recovery(self):
        """v3.32（P0-1）：启动时检测孤儿草稿（上次会话未保存的未命名文档），
        弹窗展示预览与时间，问是否恢复；选择忽略则标记 .dismissed 不再打扰。"""
        if os.environ.get("MDEDITOR_SKIP_DRAFT") or not os.path.isdir(DRAFT_DIR):
            return
        drafts = []
        for name in os.listdir(DRAFT_DIR):
            if not name.endswith(".md"):
                continue
            fp = os.path.join(DRAFT_DIR, name)
            try:
                if os.path.getsize(fp) > 0:
                    drafts.append((fp, os.path.getmtime(fp)))
            except OSError:
                continue
        if not drafts:
            return
        drafts.sort(key=lambda x: x[1], reverse=True)
        try:
            with open(drafts[0][0], "r", encoding="utf-8", errors="replace") as f:
                head = f.read(200)
        except OSError:
            return
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(drafts[0][1]))
        detail = "\n".join(
            "· %s（%s）" % (os.path.basename(fp),
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt)))
            for fp, mt in drafts)
        btn = QMessageBox.question(
            self, "发现未恢复内容",
            f"检测到 {len(drafts)} 份未命名文档的自动暂存草稿，"
            f"可能是上次异常退出遗留。\n\n"
            f"最近一份预览（{when}）：\n「{head}」\n\n"
            f"是否恢复到编辑器？\n\n{detail}",
            QMessageBox.Yes | QMessageBox.No)
        if btn != QMessageBox.Yes:
            for fp, _mt in drafts:      # 忽略：改名归档，不再提示也不丢失
                try:
                    os.replace(fp, fp + ".dismissed")
                except OSError:
                    pass
            return
        for fp, _mt in drafts:
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            idx = self._add_doc(path=None, text=text)
            if 0 <= idx < len(self._docs):
                self._docs[idx]["draft"] = fp       # 草稿跟随文档继续更新，保存后收走
        self.show_status(T("已恢复草稿内容 · 保存到文件后自动清理", "Draft content recovered · auto-cleared after saving to a file"))

    def open_folder(self):
        """打开文件夹：左侧文件栏定位并显示该文件夹的一级内容。"""
        d = QFileDialog.getExistingDirectory(self, "打开文件夹", "")
        if not d:
            return
        self._sidebar.setVisible(True)
        self._update_side_btn()
        self._sidebar.select_tab(Sidebar.TAB_FILES)
        self._sidebar.set_root(d)
        self.show_status(T(f"已打开文件夹：{d}", f"Folder opened: {d}"))

    def open_file(self, path=None):
        # QAction.triggered 会把 checked(bool) 作为第一个参数传入，
        # 必须把非字符串的 path 归一化为 None，否则打开对话框永远不会弹出
        if not isinstance(path, str) or not path:
            path = None
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "打开 Markdown 文件", self._dlg_dir("open"),
                "Markdown 文件 (*.md *.markdown *.mdown *.txt);;所有文件 (*.*)")
            if not path:
                return
            self._remember_dir("open", path)
        if not os.path.exists(path):
            QMessageBox.warning(self, T("打开失败", "Open failed"), f"文件不存在：\n{path}")
            return
        self._load_path(path)

    def _load_path(self, path):
        """打开文件：已在标签页中则切换，否则新开标签。"""
        path = os.path.abspath(path)
        # v3.38（FLP-2）：记录「最近一次成功打开文件所在目录」（覆盖对话框 /
        # 最近文件 / 侧栏双击 / 拖放 / 启动恢复全部入口；记录失败不影响打开）
        if os.path.isfile(path):
            self._remember_open_dir(path)
        for i, doc in enumerate(self._docs):
            if doc.get("path") == path:
                self._tabbar.setCurrentIndex(i)
                self._on_tab_clicked(i)
                return
        text = self._read_file(path)
        self._add_doc(path=path, text=text)
        self._add_recent(path)
        self._remember_last_session()   # v3.38（OUT-5）

    # ================= v3.44.34（BOOK-1）：书籍模式 =================
    def open_book(self):
        """打开 mdBook 项目：选择书籍根目录（含 book.toml 或 SUMMARY.md）。"""
        d = QFileDialog.getExistingDirectory(self, "打开书籍（选择书籍根目录）", "")
        if not d:
            return
        info = bookmode.read_book(d)
        if not info:
            QMessageBox.warning(self, T("打开书籍失败", "Open book failed"),
                                T("未检测到 mdBook 项目：\n需要在该目录下存在 book.toml 或 SUMMARY.md。",
                                  "No mdBook project detected:\nA book.toml or SUMMARY.md must exist in that directory."))
            return
        self._load_book(info)
        self.show_status(T("已打开书籍：", "Book opened: ") + info["title"])
        # 打开第一章（含链接的章节）
        first = self._book_first_chapter(info["root"])
        if first and first.get("abs_path"):
            self.open_book_link(first["abs_path"])

    # v3.44.35（BOOK-2）：新建书籍向导
    def create_new_book(self):
        """向导式新建 mdBook 项目：选择根目录 + 书名 → 生成 book.toml / src/SUMMARY.md / src/README.md。"""
        d = QFileDialog.getExistingDirectory(
            self, "选择书籍根目录（将在此处创建 book.toml 与 src/）", "")
        if not d:
            return
        title, ok = QInputDialog.getText(self, T("新建书籍", "New Book"), T("书籍名称：", "Book name:"), text="未命名书籍")
        if not ok or not title.strip():
            return
        title = title.strip()
        book_dir = os.path.abspath(d)
        # 冲突检查：已存在书籍项目则拒绝（避免覆盖既有 book.toml / SUMMARY.md）
        if (os.path.exists(os.path.join(book_dir, "book.toml"))
                or os.path.exists(os.path.join(book_dir, "SUMMARY.md"))
                or os.path.exists(os.path.join(book_dir, "src", "SUMMARY.md"))):
            QMessageBox.warning(self, T("新建书籍失败", "New Book Failed"),
                                "该目录已存在 mdBook 项目（book.toml / SUMMARY.md），请另选目录。")
            return
        src_dir = os.path.join(book_dir, "src")
        try:
            os.makedirs(src_dir, exist_ok=True)
            with open(os.path.join(book_dir, "book.toml"), "w", encoding="utf-8") as f:
                f.write('[book]\n')
                f.write('title = "%s"\n' % title.replace('"', "'"))
                f.write('authors = [""]\n')
                f.write('language = "zh-CN"\n')
                f.write('src = "src"\n')
            with open(os.path.join(src_dir, "SUMMARY.md"), "w", encoding="utf-8") as f:
                f.write("# %s\n\n- [简介](README.md)\n" % title)
            with open(os.path.join(src_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write("# %s\n\n> 这是《%s》的第一章。在右侧编辑内容，"
                        "或从「书籍」页签右键新增章节。\n" % (title, title))
        except OSError as e:
            QMessageBox.critical(self, T("新建书籍失败", "New Book Failed"), str(e))
            return
        info = bookmode.read_book(book_dir)
        if not info:
            QMessageBox.warning(self, T("新建书籍失败", "New Book Failed"),
                                "书籍文件已生成，但无法解析，请检查目录权限。")
            return
        self._load_book(info)
        self.show_status(T("已新建书籍：", "New book created: ") + info["title"])
        first = self._book_first_chapter(info["root"])
        if first and first.get("abs_path"):
            self.open_book_link(first["abs_path"])

    # ================= v3.45.7（BOOK-READ-1）：启动恢复书籍 + 阅读进度 =================
    def _load_book(self, info):
        """载入一本书籍（设置 _book + 侧栏），不自动打开章节。
        同时记录为「上次阅读的书籍」供启动恢复。"""
        self._book = info
        self._sidebar.set_book(info)
        self.refresh_book_links()
        self._sidebar.select_tab(Sidebar.TAB_BOOK)
        self._sidebar.setVisible(True)
        self._update_side_btn()
        self._settings.setValue("lastBook", info["book_dir"])
        # v3.47.1（BOOK-TOC）：登记书籍是否已有目录页（存在则可同步/删除）
        self._book_toc_page = None
        self._book_toc_rel = None
        for ch in bookmode.flat_chapters(info["root"]):
            if ch.get("path") and os.path.basename(ch["path"]) == "目录.md":
                self._book_toc_page = (ch.get("abs_path")
                                      or os.path.normpath(os.path.join(
                                          info["summary_dir"], ch["path"])))
                self._book_toc_rel = ch["path"]
                break

    # ================= v3.45.7（BOOK-TOC）：编辑目录 + 在正文前插入目录 =================
    def _open_summary_for_edit(self, summary_path):
        """书籍右键「编辑目录」：以普通文档标签打开该书的 summary.md（保留书籍关联）。"""
        if not summary_path or not os.path.isfile(summary_path):
            self.show_status(T("未找到目录文件：", "Table-of-contents file not found: ") + str(summary_path))
            return
        self._load_path(summary_path)
        self.show_status(T("正在编辑目录：", "Editing table of contents: ") + os.path.basename(summary_path))

    # ================= v3.46（TOC-SEL）：目录改为「侧栏选择入口」触发 =================
    def insert_toc_for_file(self, path):
        """从文件列表选择单个文件 → 仅对该文件生成并插入标题大纲目录。"""
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            self.show_status(T("文件不存在：", "File does not exist: ") + path)
            return
        if self.file_path and os.path.normpath(self.file_path) == path:
            # 已是当前活动文档：直接取回正文后插入标题大纲
            self._js_view(self._view, "window.getMarkdown()",
                          lambda md: self._insert_toc_text(self._build_heading_toc(md or "")))
            return
        # 否则打开该文件（成为活动文档），加载完成后插入
        self._toc_insert_kind = "file"
        self._toc_insert_path = path
        self._load_path(path)
        self._maybe_run_pending_toc()

    def insert_toc_for_book(self, summary_path):
        """书籍插入目录：在书籍最前生成「目录」页（独立 .md），并在 summary.md
        首行登记该章节；目录页内容随 summary.md 章节变动自动同步。"""
        summary_path = os.path.abspath(summary_path)
        info = bookmode.read_book(os.path.dirname(summary_path))
        if not info:
            self.show_status(T("无法解析书籍目录：", "Cannot parse book table of contents: ") + summary_path)
            return
        summary_dir = info["summary_dir"]
        toc_rel = "目录.md"
        toc_path = os.path.normpath(os.path.join(summary_dir, toc_rel))
        root = info["root"]
        # 生成目录页内容（排除目录页自身，避免自引用）
        toc = self._build_book_toc_from_root(root, exclude_rel=toc_rel)
        if not toc:
            self.show_status(T("该书暂无可用于生成目录的章节", "This book has no chapters available for generating a TOC"))
            return
        try:
            self._write_text(toc_path, toc)
        except OSError as e:
            self.show_status(T("目录页创建失败：", "TOC page creation failed: ") + str(e))
            return
        # 在 summary.md 首行（书籍标题之后）登记「目录」章节项
        self._insert_toc_entry_into_summary(root, toc_rel, "目录")
        try:
            bookmode.write_summary(summary_path, root)
        except OSError as e:
            self.show_status(T("目录写入 SUMMARY 失败：", "TOC write to SUMMARY failed: ") + str(e))
            return
        # 重新载入书籍并登记目录页
        info2 = bookmode.read_book(os.path.dirname(summary_path))
        if info2:
            self._load_book(info2)
        self._book_toc_page = toc_path
        self._book_toc_rel = toc_rel
        self.show_status(T("已在书籍最前插入目录（随 SUMMARY.md 自动同步）", "Inserted TOC at the front of the book (auto-synced with SUMMARY.md)"))

    def _maybe_run_pending_toc(self):
        """目标文档已打开且编辑视图就绪时立即插入；否则由 _on_loaded 加载后插入。"""
        if (self._toc_insert_kind
                and self.file_path
                and os.path.normpath(self.file_path)
                == os.path.normpath(self._toc_insert_path or "")
                and self._vstate[self._active_role()]["loaded"]):
            kind = self._toc_insert_kind
            self._toc_insert_kind = None
            self._toc_insert_path = None
            QTimer.singleShot(200, lambda k=kind: self._run_pending_toc(k))

    def _run_pending_toc(self, kind):
        if kind == "book":
            toc = self._build_book_toc()
            if not toc:
                self.show_status(T("该书暂无可用于生成目录的章节", "This book has no chapters available for generating a TOC"))
                return
            self._insert_toc_text(toc)
        else:
            self._js_view(self._view, "window.getMarkdown()",
                          lambda md: self._insert_toc_text(self._build_heading_toc(md or "")))

    def _insert_toc_text(self, toc):
        """把目录文本插入到当前文档正文最前（取回当前正文后前置）。"""
        if not toc:
            self.show_status(T("暂无可用于生成目录的标题/章节", "No headings/chapters available for generating a TOC"))
            return

        def on_md(md):
            text = md if md is not None else ""
            # 若开头已是目录块，先整段移除（避免叠加重复），再前置新目录
            body, had = self._strip_leading_toc(text)
            new_md = toc.rstrip("\n") + "\n\n" + body.lstrip("\n")
            self._js_view(self._view, f"window.setMarkdown({js(new_md)})")
            self.show_status(T("已更新目录", "TOC updated") if had else "已在正文前插入目录")
        self._js_view(self._view, "window.getMarkdown()", on_md)

    @staticmethod
    def _strip_leading_toc(md):
        """若文档以「# 目录」标题块开头，移除该目录块（含其后连续列表），
        返回 (剩余正文, 是否移除)。用于插入时去重与「删除目录」。"""
        lines = md.split("\n")
        i = 0
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        if i >= len(lines):
            return md, False
        if not re.match(r"^#\s+目录\s*$", lines[i].strip()):
            return md, False
        # 消费标题之后的连续列表项（允许项间空行；遇非列表非空行即止）
        k = i + 1
        while k < len(lines):
            line = lines[k]
            if re.match(r"^\s*[-*+]\s", line):
                k += 1
            elif line.strip() == "":
                nk = k + 1
                while nk < len(lines) and lines[nk].strip() == "":
                    nk += 1
                if nk < len(lines) and re.match(r"^\s*[-*+]\s", lines[nk]):
                    k = nk
                else:
                    break
            else:
                break
        rest = lines[k:]
        while rest and rest[0].strip() == "":
            rest.pop(0)
        return "\n".join(rest), True

    def remove_toc_for_file(self, path):
        """从文件列表选择单个文件 → 移除其正文前（若有）的目录块。"""
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            self.show_status(T("文件不存在：", "File does not exist: ") + path)
            return
        if self.file_path and os.path.normpath(self.file_path) == path:
            self._remove_toc_text()
            return
        # 否则打开该文件（成为活动文档），加载完成后移除
        self._toc_remove_path = path
        self._load_path(path)
        self._maybe_run_pending_toc_remove()

    def remove_toc_for_current(self):
        """从大纲右键等入口 → 移除当前活动文档的目录块。"""
        if not self.file_path:
            self.show_status(T("当前没有打开的文档", "No document currently open"))
            return
        self._remove_toc_text()

    def _remove_toc_text(self):
        def on_md(md):
            text = md if md is not None else ""
            body, had = self._strip_leading_toc(text)
            if not had:
                self.show_status(T("该文档未包含目录", "This document does not contain a TOC"))
                return
            self._js_view(self._view, f"window.setMarkdown({js(body)})")
            self.show_status(T("已删除目录", "TOC deleted"))
        self._js_view(self._view, "window.getMarkdown()", on_md)

    def _maybe_run_pending_toc_remove(self):
        """目标文档已打开且编辑视图就绪时立即移除；否则由 _on_loaded 加载后移除。"""
        if (self._toc_remove_path
                and self.file_path
                and os.path.normpath(self.file_path)
                == os.path.normpath(self._toc_remove_path)
                and self._vstate[self._active_role()]["loaded"]):
            self._toc_remove_path = None
            QTimer.singleShot(200, lambda: self._remove_toc_text())

    def _build_book_toc_from_root(self, root, exclude_rel=None):
        """由书籍 root 树生成嵌套 Markdown 目录（相对路径链接）。
        exclude_rel：跳过该相对路径对应的章节（目录页自身），避免自引用。"""
        if root is None:
            return None
        chapters = self._book_chapters_with_depth({"root": root})
        chapters = [c for c in chapters if c.get("title")]
        if exclude_rel:
            ex = os.path.normpath(exclude_rel).lower()
            chapters = [c for c in chapters
                        if not (c.get("path")
                                and os.path.normpath(c["path"]).lower() == ex)]
        if not chapters:
            return None
        lines = ["# 目录", ""]
        for ch in chapters:
            depth = ch.get("depth", 0)
            indent = "  " * depth
            title = ch["title"]
            path = ch.get("path") or ""
            if path:
                lines.append("%s- [%s](%s)" % (indent, title, path))
            else:
                lines.append("%s- %s" % (indent, title))
        return "\n".join(lines) + "\n"

    def _build_book_toc(self):
        """由当前书籍章节清单生成嵌套 Markdown 目录（相对路径链接）。"""
        if not self._book:
            return None
        return self._build_book_toc_from_root(self._book["root"])

    def _insert_toc_entry_into_summary(self, root, toc_rel, title):
        """在 summary 根的首位插入指向目录页的章节项（已存在则跳过，避免重复）。"""
        for ch in bookmode.flat_chapters(root):
            if (ch.get("path")
                    and os.path.normpath(ch["path"]).lower()
                    == os.path.normpath(toc_rel).lower()):
                return
        node = {"kind": "chapter", "title": title, "path": toc_rel,
                "abs_path": None, "children": [], "line": -1}
        root["children"].insert(0, node)

    def _remove_toc_entry_from_summary(self, root, toc_rel):
        """从 summary 树中移除指向目录页的章节项，返回是否移除。"""
        ex = os.path.normpath(toc_rel).lower()
        removed = [False]

        def walk(node):
            kids = node.get("children", [])
            new = []
            for ch in kids:
                if (ch.get("kind") == "chapter" and ch.get("path")
                        and os.path.normpath(ch["path"]).lower() == ex):
                    removed[0] = True
                    continue
                if ch.get("children"):
                    walk(ch)
                new.append(ch)
            node["children"] = new
        walk(root)
        return removed[0]

    def remove_toc_for_book(self, summary_path):
        """书籍删除目录：移除 summary.md 中的目录章节项并删除目录页文件。"""
        summary_path = os.path.abspath(summary_path)
        info = bookmode.read_book(os.path.dirname(summary_path))
        if not info:
            self.show_status(T("无法解析书籍目录：", "Cannot parse book table of contents: ") + summary_path)
            return
        root = info["root"]
        toc_rel = "目录.md"
        if not self._remove_toc_entry_from_summary(root, toc_rel):
            self.show_status(T("该书未包含目录", "This book does not contain a TOC"))
            return
        try:
            bookmode.write_summary(summary_path, root)
        except OSError as e:
            self.show_status(T("目录移除失败：", "TOC removal failed: ") + str(e))
            return
        # 删除目录页文件（仅限我们生成的 目录.md，避免误删）
        toc_path = os.path.normpath(os.path.join(info["summary_dir"], toc_rel))
        if os.path.isfile(toc_path):
            try:
                os.remove(toc_path)
            except OSError:
                pass
        info2 = bookmode.read_book(os.path.dirname(summary_path))
        if info2:
            self._load_book(info2)
        self._book_toc_page = None
        self._book_toc_rel = None
        self.show_status(T("已删除书籍目录", "Book TOC deleted"))

    def _refresh_book_toc_page(self):
        """summary.md 章节变动后，按最新结构重建目录页（自动同步）。"""
        if not self._book or not self._book_toc_page:
            return
        sp = self._book.get("summary_path")
        if not sp or not os.path.isfile(sp):
            return
        try:
            with open(sp, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return
        root = bookmode.parse_summary(text)
        toc = self._build_book_toc_from_root(
            root, exclude_rel=self._book_toc_rel or "目录.md")
        if not toc:
            return
        try:
            self._write_text(self._book_toc_page, toc)
        except OSError as e:
            self.show_status(T("目录页刷新失败：", "TOC page refresh failed: ") + str(e))
            return
        self._sync_open_doc_if_match(self._book_toc_page, toc)
        self.show_status(T("目录已随 SUMMARY.md 自动更新", "TOC auto-updated with SUMMARY.md"))

    def _sync_open_doc_if_match(self, path, content):
        """若 path 正作为标签页打开，同步其内容与磁盘（活动标签则刷新视图）。"""
        ap = os.path.normpath(path)
        for i, d in enumerate(self._docs):
            if d.get("path") and os.path.normpath(d["path"]) == ap:
                d["content"] = content
                if i == self._cur:
                    self._js_view(self._view,
                                  f"window.setMarkdown({js(content)})")
                    self._dirty = False
                    self._update_title()
                    self._refresh_tab_texts()
                break

    @staticmethod
    def _slugify(text):
        """与 editor.html slugify 同源：trim→折叠空白→小写→仅留字母数字空格
        （CJK 原样）→ 空格转 '-' → 去首尾/连续 '-'。用于标题锚点。"""
        if not text:
            return ""
        s = " ".join(str(text).strip().split()).lower()
        out = []
        for ch in s:
            if ch.isalnum() or ch == " ":   # isalnum 含 CJK/字母/数字
                out.append(ch)
        s = "".join(out).replace(" ", "-").replace("--", "-").strip("-")
        return s

    def _build_heading_toc(self, md):
        """由文档标题大纲生成嵌套 Markdown 目录（#slug 锚点链接）。"""
        if not md:
            return None
        import re as _re
        lines = ["# 目录", ""]
        stack = []   # (level, slug, count)
        seen = {}
        any_h = False
        for raw in md.splitlines():
            m = _re.match(r"^(#{1,6})\s+(.*\S)\s*$", raw)
            if not m:
                continue
            level = len(m.group(1))
            title = m.group(2).strip()
            base = self._slugify(title) or "section"
            n = seen.get(base, 0)
            seen[base] = n + 1
            # 与 editor.html slugify 去重同源：首条 = base，其后 = base-2 / base-3 …
            # （旧版用 base-1，导致导出 HTML/PDF 内目录锚点跳转失效）
            slug = base if n == 0 else "%s-%d" % (base, n + 1)
            indent = "  " * (level - 1)
            lines.append("%s- [%s](#%s)" % (indent, title, slug))
            any_h = True
        if not any_h:
            return None
        return "\n".join(lines) + "\n"

    def _restore_book(self):
        """启动若上次在阅读书籍，自动恢复书籍 + 阅读进度（章节 + 滚动位置）。"""
        _lb = str(self._settings.value("lastBook", "") or "")
        if not _lb or not os.path.isdir(_lb):
            return
        info = bookmode.read_book(_lb)
        if not info:
            return
        self._load_book(info)
        self.show_status(T("已恢复书籍：", "Book restored: ") + info["title"])
        # 恢复上次章节
        _lc = str(self._settings.value("lastBookChapter", "") or "")
        target = None
        if _lc:
            cand = os.path.normpath(os.path.join(info["summary_dir"], _lc))
            target = bookmode.find_chapter(info["root"], cand)
        if not target:
            target = self._book_first_chapter(info["root"])
        if target and target.get("abs_path"):
            self.open_book_link(target["abs_path"])
        # 恢复滚动位置（内容渲染后重试定位）
        try:
            _sr = float(self._settings.value("lastBookScroll", 0.0) or 0.0)
        except (TypeError, ValueError):
            _sr = 0.0
        if _sr > 0:
            self._pending_book_scroll = _sr
            self._schedule_book_scroll()

    def _schedule_book_scroll(self, tries=0):
        """内容渲染完成后把视图滚到上次比例（带重试，最多 ~5s）。"""
        if self._pending_book_scroll is None:
            return
        ratio = self._pending_book_scroll

        def cb(res):
            if res == "ok":
                self._pending_book_scroll = None
            elif tries < 12:
                QTimer.singleShot(400, lambda: self._schedule_book_scroll(tries + 1))
        self._js_view(self._view, "window.scrollToRatio(%s)" % json.dumps(ratio), cb)

    def _on_book_scroll(self, res):
        """周期性记录当前章节滚动比例（0~1）。"""
        try:
            v = float(res)
        except (TypeError, ValueError):
            return
        if 0 <= v <= 1:
            self._settings.setValue("lastBookScroll", v)

    def _record_book_chapter(self):
        """若当前文件是书籍章节，记录为「上次章节」（相对路径）。"""
        if not self._book or not self.file_path:
            return
        node = bookmode.find_chapter(self._book["root"], self.file_path)
        if node and node.get("path"):
            self._settings.setValue("lastBookChapter", node["path"])

    def _save_book_progress(self):
        """退出前记录书籍 / 章节（滚动比例由 _poll 周期写入兜底）。"""
        self._record_book_chapter()
        if self._book:
            self._settings.setValue("lastBook", self._book["book_dir"])

    def _book_first_chapter(self, root):
        for ch in bookmode.flat_chapters(root):
            if ch.get("abs_path"):
                return ch
        return None

    def open_book_link(self, abs_path):
        """通用增强：在编辑器内打开一个 Markdown 文件（书籍章节 / 文档内相对链接共用）。

        绝对路径交给 _load_path（已开则切换、否则新开标签）；文件不存在时提示。
        v3.45.3（LINK-FB）：链接以 .html 结尾但文件不存在时，回退打开同名 .md
        （导出 HTML 站点后的双向兼容：站点内链写 .html，源文件是 .md）。
        链接可携带 #fragment（如 page.html#slug），此处剥落后按纯路径处理。"""
        if not abs_path:
            return
        # 剥离开头 fragment（#slug 不进文件系统判断）
        _frag = ""
        _p = str(abs_path)
        _q = _p.find("#")
        if _q >= 0:
            _frag = _p[_q:]
            _p = _p[:_q]
        p = os.path.abspath(_p)
        if not os.path.exists(p):
            _root, _ext = os.path.splitext(p)
            _fb = ""
            if _ext.lower() == ".html":
                _cand = _root + ".md"
                if os.path.exists(_cand):
                    _fb = _cand
            if _fb:
                self.show_status(T("未找到 %s，已回退打开 %s", "Not found %s; fell back to opening %s")
                                 % (os.path.basename(p), os.path.basename(_fb)))
                p = _fb
            else:
                QMessageBox.warning(self, T("打开失败", "Open failed"), f"文件不存在：\n{p}")
                return
        self._load_path(p)
        # 携带 #锚点：打开后滚动定位（与 on_wikilink 同口径）
        if _frag and len(_frag) > 1:
            self._js_active("setTimeout(function(){ scrollToAnchor(%s); }, 400);"
                            % json.dumps(_frag[1:], ensure_ascii=False))
        # 若当前处于书籍模式且打开的恰是书中章节，侧栏会随标签切换自动高亮

    def on_book_entry_selected(self, rel):
        """v3.45.3（BOOK-6）：书籍树章节被点击 → 状态栏显示对应文件名。

        树内不再双行显示文件名（只显示子章节名），文件名改在这里呈现；
        打开章节时会异步写「已打开 · 路径」常驻信息，故延后一拍覆盖，
        保证用户看到的是文件名（连接顺序在 bookEntryOpen 之后）。"""
        name = (rel or "").strip()
        text = "文件：" + (name if name else "（无对应文件）")
        QTimer.singleShot(120, lambda: self._status.setText(text))

    def on_book_structure_changed(self, root):
        """书籍目录结构变化（拖拽重排 / 新增 / 重命名 / 删除）→ 写回 SUMMARY.md。"""
        if not self._book:
            return
        self._book["root"] = root
        try:
            bookmode.write_summary(self._book["summary_path"], root)
            self.show_status(T("已更新书籍目录 ", "Book TOC updated ") + os.path.basename(self._book["summary_path"]))
        except OSError as e:
            QMessageBox.warning(self, T("写回失败", "Write-back failed"), str(e))
            return
        # v3.47.1（BOOK-TOC）：目录结构变动后，同步重建目录页
        self._refresh_book_toc_page()

    # v3.44.35（BOOK-2）：整本书级导出 / 关闭
    def close_book(self):
        """关闭当前书籍（清空侧栏书籍目录与 _book 状态）。

        v3.48.38（BOOK-AUTO）：用户主动关闭书籍后，清除「上次阅读书籍」记录
        （lastBook / lastBookChapter / lastBookScroll），使下次启动默认不再自动
        重新打开这些已关闭的书籍；仅当用户再次手动打开时才重新登记。"""
        self._book = None
        self._sidebar.set_book(None)
        for _k in ("lastBook", "lastBookChapter", "lastBookScroll"):
            self._settings.remove(_k)
        self.show_status(T("已关闭书籍", "Book closed"))

    def _book_chapters_with_depth(self, info):
        """返回书籍全部 chapter 节点（按文档顺序），并就地标注 depth（嵌套层级）。"""
        out = []

        def walk(node, depth):
            for ch in node.get("children", []):
                if ch["kind"] == "chapter":
                    ch["depth"] = depth
                    out.append(ch)
                    walk(ch, depth + 1)
                elif ch["kind"] == "part":
                    walk(ch, depth)
        walk(info["root"], 0)
        return out

    def on_book_export_requested(self, fmt, summary_path):
        """书籍右键「导出整本书」派发：PDF / HTML / EPUB / Word。"""
        info = bookmode.read_book(summary_path)
        if not info:
            QMessageBox.warning(self, T("导出失败", "Export failed"), "无法解析书籍：" + str(summary_path))
            return
        # v3.47.1（BOOK-TOC）：导出前刷新目录页，保证导出物目录最新
        if (self._book and self._book_toc_page
                and os.path.normpath(self._book.get("summary_path", ""))
                == os.path.normpath(summary_path)):
            self._refresh_book_toc_page()
        chapters = self._book_chapters_with_depth(info)
        chapters = [c for c in chapters
                    if c.get("abs_path") and os.path.exists(c["abs_path"])]
        if not chapters:
            QMessageBox.information(self, T("导出失败", "Export failed"), T("该书没有可导出的章节。", "This book has no exportable chapters."))
            return
        if fmt == "pdf":
            self._export_book_pdf(info, chapters)
        elif fmt == "html":
            self._export_book_html(info, chapters)
        else:
            self._export_book_ebook(info, chapters, fmt)

    def _export_book_pdf(self, info, chapters):
        """整本书 PDF：有界并行渲染 + pypdf 合并（书签 / 页码）。

        v3.48.38（BOOK-PDF）：导出前弹出与单文件一致的 PDF 设置对话框，默认取
        已保存设置或内置最佳默认值；两种导出链路共用 bookexport 同一套 opts 应用
        逻辑（纸张 / 边距 / 行距 / 字体），保证整书与单文件默认导出效果完全一致。"""
        dlg = PdfExportDialog(self, self._settings)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        opts = dlg.result_opts()
        if opts.get("save_default"):
            # 与单文件导出一致：勾选「保存为默认」时落盘
            from bookexport import save_opts
            save_opts(self._settings, opts)
        self._pdf_opts = opts
        path, _ = QFileDialog.getSaveFileName(
            self, "导出整本书 PDF",
            self._dlg_start("pdf", (info["title"] or "book") + ".pdf"), "PDF 文件 (*.pdf)")
        if not path:
            return
        self._remember_dir("pdf", path)
        self.show_status(T("正在导出整本书 PDF（并行渲染 %d 章）…", "Exporting whole-book PDF (rendering %d chapters in parallel)…") % len(chapters))
        from bookexport import BookPdfExporter
        editor_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor.html")
        self._book_pdf_exp = BookPdfExporter(
            self, EditorPage, editor_html, max_slots=3, opts=opts,
            on_done=lambda ok_path, msg: self._book_pdf_done(ok_path, msg),
            on_progress=lambda d, t: self.show_status(
                "整本书 PDF：已渲染 %d / %d 章" % (d, t)))
        self._book_pdf_exp.start(list(chapters), info["summary_dir"], path)

    def _book_pdf_done(self, ok_path, msg):
        if not ok_path:
            self.show_status(T("整本书 PDF 导出失败", "Whole-book PDF export failed"))
            QMessageBox.warning(self, T("导出失败", "Export failed"), msg or T("未知错误", "Unknown error"))
            return
        self.show_status(T("已导出整本书 PDF · ", "Whole-book PDF exported · ") + ok_path
                        + ("（" + msg + "）" if msg else ""))
        self._export_done("PDF", ok_path)

    def _book_combined_md(self, chapters):
        """把多章 markdown 拼接为一个文档（章标题作为分隔标题），用于无 pandoc 回退。"""
        parts = []
        for ch in chapters:
            try:
                with open(ch["abs_path"], "r", encoding="utf-8") as f:
                    md = f.read().strip()
            except OSError:
                md = ""
            title = ch.get("title") or os.path.basename(ch.get("path") or "")
            if md and not md.lstrip().startswith("#"):
                parts.append("# " + title + "\n\n" + md)
            else:
                parts.append(md)
        return "\n\n\n".join(parts)

    def _book_build_html(self, md, base_dir, title):
        from exporters import parse_blocks, _blocks_to_xhtml
        body = _blocks_to_xhtml(parse_blocks(md), base_dir, {}, None, None)
        return ("<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
                "<title>%s</title></head><body>\n%s\n</body></html>" % (title, body))

    def _export_book_html(self, info, chapters):
        """整本书 HTML：按 mdBook 方式生成多页站点（每章一个 HTML + 目录页 +
        共享样式 + 上下章导航），并用内置本地服务器以网址打开。

        v3.44.36（BOOK-5）：由「导出单个 HTML 文件」改为「导出多页站点」——
        输出目录含 index.html（目录）、NN-章节名.html（每章一页）、style.css。
        可用 file:// 直接打开，或经 http://127.0.0.1:<port>/index.html 访问。
        """
        import bookhtml
        from PySide6.QtGui import QDesktopServices

        base = info.get("book_dir") or info.get("summary_dir") or os.getcwd()
        default = os.path.join(base, "_site")
        try:
            os.makedirs(default, exist_ok=True)
        except OSError:
            default = base
        out_dir = QFileDialog.getExistingDirectory(
            self, "选择整本书 HTML 站点输出目录（每章生成一个 HTML）", default)
        if not out_dir:
            return
        self.show_status(T("正在生成整本书 HTML 站点…", "Generating whole-book HTML site…"))
        ok, msg, index_path = bookhtml.build_site(info, chapters, out_dir)
        if not ok:
            QMessageBox.warning(self, T("导出失败", "Export failed"), msg)
            return
        # 本地 HTTP 服务器：http://127.0.0.1:<port>/index.html（可输入网址访问）
        url = None
        try:
            old = getattr(self, "_book_site_server", None)
            if old is not None:
                old.stop()
            self._book_site_server = bookhtml.LocalSiteServer(out_dir)
            url = self._book_site_server.start()
        except Exception:   # noqa: BLE001
            self._book_site_server = None
            url = None
        if not os.environ.get("MDEDITOR_NO_BROWSER"):
            try:
                target = QUrl(url) if url else QUrl.fromLocalFile(index_path)
                QDesktopServices.openUrl(target)
            except Exception:   # noqa: BLE001
                pass
        if url:
            self.show_status(T("已生成整本书 HTML 站点（%d 章）：%s", "Whole-book HTML site generated (%d chapters): %s")
                             % (len(chapters), url))
        else:
            self.show_status(T("已生成整本书 HTML 站点（%d 章）：%s", "Whole-book HTML site generated (%d chapters): %s")
                             % (len(chapters), index_path))

    def _export_book_ebook(self, info, chapters, fmt):
        """整本书 EPUB / Word：pandoc 优先；缺失则内置回退（合并 md 单文件）。"""
        label = "EPUB" if fmt == "epub" else "Word (docx)"
        ext = ".epub" if fmt == "epub" else ".docx"
        filt = "EPUB 电子书 (*.epub)" if fmt == "epub" else "Word 文档 (*.docx)"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出整本书 " + label,
            self._dlg_start(fmt, (info["title"] or "book") + ext), filt)
        if not path:
            return
        self._remember_dir(fmt, path)
        self.show_status(T("正在导出整本书 %s…", "Exporting whole book %s…") % label)
        pandoc = self._pandoc_exe()
        if pandoc:
            if self._book_pandoc(pandoc, chapters, path, info, [], 300):
                self.show_status(T("已导出整本书 %s · %s", "Whole book %s exported · %s") % (label, path))
                self._export_done(label, path)
            return
        # 内置回退
        md = self._book_combined_md(chapters)
        base_dir = info["summary_dir"]
        title = info["title"] or "book"
        if fmt == "epub":
            ok, msg = exporters.write_epub(
                md, path, base_dir, title,
                border_color=getattr(self, "_theme_border", "") or "#ddd")
        else:
            ok, msg = exporters.write_docx(md, path, base_dir, title)
        self.show_status(msg)
        if not ok:
            QMessageBox.warning(self, T("导出失败", "Export failed"), msg)
        else:
            self._export_done(label, path)

    def _book_pandoc(self, pandoc, chapters, out_path, info, extra, timeout):
        """调用 pandoc 多文件合并导出；返回是否成功。"""
        import subprocess as _sp
        files = [c["abs_path"] for c in chapters]
        cmd = ([pandoc] + files + ["-o", out_path, "--from", "gfm+tex_math_dollars",
                "--resource-path", info["summary_dir"], "--standalone",
                "--toc", "--toc-depth=3"] + list(extra))
        try:
            r = _sp.run(cmd, capture_output=True, timeout=timeout)
        except Exception as e:   # noqa: BLE001
            QMessageBox.warning(self, T("导出失败", "Export failed"), str(e))
            return False
        if r.returncode != 0:
            QMessageBox.warning(self, T("导出失败", "Export failed"),
                                (r.stderr or b"").decode("utf-8", "replace")[-400:])
            return False
        return True

    def on_book_reveal(self, book_dir):
        """书籍右键「打开所在文件」：在资源管理器打开书籍根目录。"""
        if not book_dir or not os.path.exists(book_dir):
            QMessageBox.information(self, T("打开所在文件", "Open Containing File"),
                                    T("书籍目录不存在：", "Book directory does not exist: ") + str(book_dir))
            return
        try:
            subprocess.Popen(["explorer", os.path.abspath(book_dir)])
        except OSError as e:
            QMessageBox.critical(self, T("打开失败", "Open failed"), str(e))

    def save_file(self) -> bool:
        if not self.file_path:
            return self.save_file_as()

        def cb(md):
            if md is None:
                return
            try:
                if md and not md.endswith("\n"):
                    md += "\n"
                # P1-6：写入前把上一版留档（内容相同则不产生快照）
                self.snapshot_history(self.file_path, md)
                self._write_text(self.file_path, md)   # v3.29d（B2）：按原编码写盘
                self._dirty = False
                if 0 <= self._cur < len(self._docs):
                    self._docs[self._cur]["content"] = md
                self._update_title()
                self._refresh_tab_texts()
                self._update_save_cell()   # v3.40（UI-R7）：✓ 已保存（静默）
                self.show_status(T(f"已保存 · {self.file_path}", f"Saved · {self.file_path}"))
                # v3.48.30（FILE-SAVE）：保存后自动刷新侧栏文件列表
                self._sidebar.refresh_after_save(self.file_path)
                self.refresh_wiki()  # v3.44.37（BACKLINK-3）：保存后重建双链索引与反向链接
                self.refresh_backlinks()  # v3.48.13（BACKLINK-4）：反链页可见时同步刷新
                # v3.47.1（BOOK-TOC）：若保存的恰是书籍 SUMMARY.md → 同步目录页
                if (self._book and self._book_toc_page
                        and os.path.normpath(self.file_path)
                        == os.path.normpath(self._book.get("summary_path", ""))):
                    self._refresh_book_toc_page()
            except OSError as e:
                self._update_save_cell()
                QMessageBox.critical(self, T("保存失败", "Save failed"), str(e))

        self._js_active("window.getMarkdown()", cb)
        return True

    def save_file_as(self) -> bool:
        # v3.29d（B7）：对话框记忆上次保存目录
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Markdown 文件",
            self._dlg_start("save", self.file_path or "未命名.md"),
            "Markdown 文件 (*.md);;所有文件 (*.*)")
        if not path:
            return False
        self._remember_dir("save", path)
        self._remember_open_dir(path)   # v3.39.2（PATH-1）：保存目录纳入上次使用路径
        self.file_path = os.path.abspath(path)
        if 0 <= self._cur < len(self._docs):
            self._docs[self._cur]["path"] = self.file_path
            self._refresh_tab_texts()
        self._push_doc_dir()
        if 0 <= self._cur < len(self._docs):
            self._remove_draft(self._docs[self._cur])   # v3.32（P0-1）：有路径后草稿收走
        self._remember_last_session()   # v3.38（OUT-5）
        self.save_file()
        return True

    # ================= 导出 =================
    def _export_selfcheck(self, md, kinds):
        """v3.32（P0-4③ / P1-10①）：导出前"交付自检"——扫描文档里会降级 /
        需联网的元素，弹窗明示后果；返回 True 继续、False 取消。
        kinds: 'docx'|'epub'（块级公式降源码、图表位图化）或 'html'|'pdf'。"""
        if not md:
            return True
        math_n = len(re.findall(r"^```math\s*$", md, flags=re.M))
        mmd_n = len(re.findall(r"^```mermaid\s*$", md, flags=re.M))
        img_n = len(re.findall(r"!\[[^\]]*\]\((?:https?:)?//", md)) \
            + len(re.findall(r"<img[^>]*\ssrc=[\"'](?:https?:)?//", md))
        lines = []
        if kinds in ("docx", "epub") and math_n:
            lines.append(T(f"· {math_n} 处块级公式：导出后将保留 LaTeX 源码并加标注（暂不渲染）", f"· {math_n} block formulas: LaTeX source retained with annotations after export (not rendered yet)"))
        if kinds in ("docx", "epub") and mmd_n:
            lines.append(T(f"· {mmd_n} 张 Mermaid 图表：将以已渲染的位图嵌入（不可再编辑）", f"· {mmd_n} Mermaid diagrams: embedded as rendered bitmaps (no longer editable)"))
        if img_n:
            lines.append(T(f"· {img_n} 张网络图片：需联网才能显示（本地图片不受影响）", f"· {img_n} network images: require internet to display (local images unaffected)"))
        if not lines:
            return True
        ret = QMessageBox.question(
            self, "导出前自检",
            "本文档包含以下导出时需要注意的元素：\n\n" + "\n".join(lines)
            + "\n\n是否继续导出？",
            QMessageBox.Yes | QMessageBox.No)
        return ret == QMessageBox.Yes

    def _export_selfcheck_remote(self, n):
        """v3.32（P0-4③）：仅网络图片的自检（HTML / PDF 导出路径）。"""
        ret = QMessageBox.question(
            self, "导出前自检",
            f"本文档包含 {n} 张网络图片（http/https），查看时需联网加载；"
            "本地图片与公式 / 图表已内嵌，离线可用。\n\n是否继续导出？",
            QMessageBox.Yes | QMessageBox.No)
        return ret == QMessageBox.Yes

    def _export_done(self, label, path):
        """v3.32（P1-2①）：导出完成的收尾动作——打开该文件 / 打开所在文件夹。"""
        box = QMessageBox(self)
        box.setWindowTitle(T("导出完成", "Export Complete"))
        box.setText(T(f"已导出 {label}：\n{path}", f"Exported {label}:\n{path}"))
        b_open = box.addButton(T("打开该文件", "Open File"), QMessageBox.YesRole)
        b_dir = box.addButton(T("打开所在文件夹", "Open Containing Folder"), QMessageBox.ActionRole)
        box.addButton(T("完成", "Done"), QMessageBox.NoRole)
        box.exec()
        clicked = box.clickedButton()
        try:
            if clicked is b_open:
                openutil.open_path(path)
            elif clicked is b_dir:
                openutil.open_in_folder(path)
        except OSError:
            self.show_status(T("无法打开：系统缺少关联程序", "Cannot open: system lacks an associated program"))
        return

    # ================= v3.44.37（BACKLINK-1~3）：双链 / 反向链接 =================
    def on_wikilink(self, target):
        """点击 [[双链]] 或 [[章节#锚点]]：解析标题/章节→文件→打开；不存在则新建。
        v3.45（BOOKLINK-C）：支持 target#anchor，拆分后跳章并滚动到锚点。"""
        if not target or not target.strip():
            return
        target = target.strip()
        anchor = ""
        if "#" in target:
            ti, _, anchor = target.partition("#")
            ti = ti.strip()
            anchor = anchor.strip()
        else:
            ti = target
        if not ti:
            return
        if self._book:
            # 书籍模式：按章节标题解析，命中则在本编辑器内打开该章并滚动锚点
            path = self._resolve_book_chapter(ti)
            if path and os.path.exists(path):
                self.open_book_link(path)
                if anchor:
                    self._js_active("setTimeout(function(){ scrollToAnchor(%s); }, 400);"
                                    % json.dumps(anchor, ensure_ascii=False))
                return
            self.show_status(T("书籍中未找到章节：", "No chapter found in book: ") + ti)
            return
        idx = getattr(self, "_note_index", {}) or {}
        path = idx.get(ti)
        if path and os.path.exists(path):
            self._load_path(path)
            if anchor:
                self._js_active("setTimeout(function(){ scrollToAnchor(%s); }, 400);"
                                % json.dumps(anchor, ensure_ascii=False))
            return
        base = self._doc_dir() or getattr(self._sidebar, "_cur_dir", "") or ""
        if not base or not os.path.isdir(base):
            self.show_status(T("无法定位笔记目录，无法新建笔记：", "Cannot locate notes folder; cannot create new note: ") + ti)
            return
        safe = "".join(c if c not in '\\/:*?"<>|' else "_" for c in ti)
        fp = os.path.join(base, safe + ".md")
        if os.path.exists(fp):
            self._load_path(fp)
            if anchor:
                self._js_active("setTimeout(function(){ scrollToAnchor(%s); }, 400);"
                                % json.dumps(anchor, ensure_ascii=False))
            return
        try:
            self._write_text(fp, "# " + ti + "\n\n")
        except OSError as e:
            self.show_status(T("新建笔记失败：", "New note failed: ") + str(e))
            return
        self._add_recent(fp)
        self._load_path(fp)

    def _resolve_book_chapter(self, title):
        """书籍模式下按章节标题查找章节绝对路径（精确匹配标题，回退匹配文件名）。"""
        if not self._book:
            return None
        for ch in self._book_chapters_with_depth(self._book):
            ap = ch.get("abs_path")
            if not ap:
                continue
            if (ch.get("title") or "").strip() == title:
                return ap
            if os.path.basename(ap).rsplit(".", 1)[0] == title:
                return ap
        return None

    def _doc_first_title(self, md):
        """取文档首个一级 / 二级标题作为笔记标题（用于双链索引与反向链接）。"""
        if not md:
            return ""
        for line in md.splitlines():
            st = line.strip()
            if st.startswith("# "):
                return st[2:].strip()
            if st.startswith("## "):
                return st[3:].strip()
        return ""

    def refresh_wiki(self):
        """重建笔记索引（标题→路径）并刷新反向链接面板。"""
        base = self._doc_dir() or getattr(self._sidebar, "_cur_dir", "") or ""
        idx = {}
        if base and os.path.isdir(base):
            count = 0
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for fn in filenames:
                    if count >= 4000:
                        break
                    if not fn.lower().endswith((".md", ".markdown", ".mdown", ".txt")):
                        continue
                    fp = os.path.join(dirpath, fn)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                            head = f.read(8000)
                    except OSError:
                        continue
                    title = self._doc_first_title(head)
                    if title and title not in idx:
                        idx[title] = fp
                    count += 1
                if count >= 4000:
                    break
        for doc in self._docs:
            c = doc.get("content")
            if not c:
                continue
            title = self._doc_first_title(c)
            if title:
                p = doc.get("path")
                idx[title] = p if p else idx.get(title)
        self._note_index = idx
        try:
            self._js_active("window.__noteIndex = " + json.dumps(idx, ensure_ascii=False) + ";")
        except Exception:
            pass

    # ---- v3.48.13（BACKLINK-4）：反向链接 ----
    _BL_MAX_FILES = 4000
    _BL_MAX_SIZE = 1_500_000
    _WL_RE = re.compile(r"\[\[([^\[\]\n]+)\]\]")

    def _bl_active(self):
        """反链页签是否为当前可见页（决定切换/保存时是否顺带刷新）。"""
        try:
            return self._sidebar.stack.currentIndex() == self._sidebar.TAB_BACKLINKS
        except Exception:
            return False

    def refresh_backlinks(self, force=False):
        """反链面板数据源：扫描笔记库，找出链接到当前文档的全部 (文件, 行, 摘录)。

        口径与 on_wikilink 导航一致：[[X]] / [[X#锚]] / [[X#锚|别名]] 的头部 X
        命中当前文档标题（_doc_first_title）或文件名（去扩展名）即计入；指向
        自身的链接不计。增量：按 (mtime, size) 缓存，只重读变更文件；面板不可见
        且非 force 时跳过（进入反链页签 / 点刷新按钮时会强制刷）。
        """
        if not force and not self._bl_active():
            return
        cur_path = os.path.abspath(self.file_path) if self.file_path else ""
        title = ""
        if cur_path:
            try:
                with open(cur_path, "r", encoding="utf-8", errors="ignore") as f:
                    title = self._doc_first_title(f.read(8000))
            except OSError:
                title = ""
        elif self._cur >= 0 and self._docs[self._cur].get("content"):
            title = self._doc_first_title(self._docs[self._cur]["content"])
        stem = os.path.splitext(os.path.basename(cur_path))[0] if cur_path else ""
        keys = {k.lower() for k in (title, stem) if k}
        base = self._doc_dir() or getattr(self._sidebar, "_cur_dir", "") or ""
        items = []
        if base and os.path.isdir(base) and cur_path and keys:
            cache = getattr(self, "_bl_cache", None)
            if cache is None:
                cache = {}
                self._bl_cache = cache
            seen = set()
            count = 0
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for fn in filenames:
                    if count >= self._BL_MAX_FILES:
                        break
                    if not fn.lower().endswith((".md", ".markdown", ".mdown", ".txt")):
                        continue
                    fp = os.path.join(dirpath, fn)
                    ap = os.path.abspath(fp)
                    if ap == cur_path:
                        continue          # 自链不计
                    count += 1
                    seen.add(ap)
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    if st.st_size > self._BL_MAX_SIZE:
                        continue
                    rows = None
                    old = cache.get(ap)
                    if old and not force and abs(old[0] - st.st_mtime) < 0.01 \
                            and int(old[1]) == st.st_size:
                        rows = old[2]
                    else:
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                text = f.read()
                        except OSError:
                            continue
                        rows = []
                        for no, line in enumerate(text.split("\n"), 1):
                            for m in self._WL_RE.finditer(line):
                                head = m.group(1).split("#", 1)[0]
                                head = head.split("|", 1)[0].strip()
                                if head and head.lower() in keys:
                                    snip = line.strip()
                                    if len(snip) > 90:
                                        snip = snip[:90] + "…"
                                    rows.append((no, snip))
                                    break
                        cache[ap] = (st.st_mtime, st.st_size, rows)
                    items.extend((ap, no, snip) for no, snip in (rows or []))
            for ap in [k for k in cache if k not in seen]:
                cache.pop(ap, None)
        try:
            self._sidebar.set_backlinks(title or stem or "未命名文档", items)
        except Exception:
            pass

    def refresh_book_links(self):
        """构建本书全部章节 + 各章标题锚点清单，注入 window.__bookLinks
        供浮动栏「本书链接」选择器（章节 / 锚点两级）使用。
        数据结构（与 mdutil.slugify 同源，导出阶段复用）：
            [{title, path, headings:[{level, text, slug, line}]}, ...]"""
        if not self._book:
            try:
                self._js_active("window.__bookLinks = [];")
            except Exception:
                pass
            return
        chapters = self._book_chapters_with_depth(self._book)
        out = []
        for ch in chapters:
            ap = ch.get("abs_path")
            if not ap or not os.path.exists(ap):
                continue
            title = ch.get("title") or os.path.basename(ap)
            headings = []
            try:
                with open(ap, "r", encoding="utf-8", errors="ignore") as f:
                    md = f.read()
                headings = mdutil.extract_headings(md, max_level=4)
            except OSError:
                pass
            out.append({"title": title, "path": ap, "headings": headings})
        self._book_links = out
        try:
            self._js_active("window.__bookLinks = "
                            + json.dumps(out, ensure_ascii=False) + ";")
        except Exception:
            pass

    def _on_backlink_open(self, path, line):
        """反向链接被双击：打开来源文档并跳转到引用所在行。"""
        self.open_file_at(path, line)

    def archive_workspace(self):
        """v3.32（P0-7）：把当前工作区（当前文档所在目录或侧栏根目录）
        打包为带时间戳的 zip —— 含全部 .md / assets / .mdeditor-history，
        作为"本地唯一副本"的最低成本容灾出口。"""
        root = ""
        for cand in (self._doc_dir(), getattr(self._sidebar, "_cur_dir", "")):
            if cand and os.path.isdir(cand):
                root = os.path.abspath(cand)
                break
        if not root:
            QMessageBox.information(
                self, "归档工作区",
                "当前没有已保存的文档或已打开的文件夹，没有可归档的工作区。")
            return
        default = os.path.join(os.path.dirname(root) or root,
                               "%s-workspace-%s.zip"
                               % (os.path.basename(root), time.strftime("%Y%m%d-%H%M%S")))
        path, _ = QFileDialog.getSaveFileName(
            self, "归档整个工作区", default, "压缩包 (*.zip)")
        if not path:
            return
        n_file = 0
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [d for d in dirnames
                                   if d not in ("__pycache__", "$RECYCLE.BIN")]
                    for name in filenames:
                        fp = os.path.join(dirpath, name)
                        if os.path.abspath(fp) == os.path.abspath(path):
                            continue        # 归档包自身落在工作区内时跳过
                        try:
                            zf.write(fp, os.path.relpath(fp, root))
                            n_file += 1
                        except OSError:
                            continue
        except (OSError, zipfile.BadZipFile) as e:
            QMessageBox.warning(self, T("归档失败", "Archive failed"), str(e))
            return
        self.show_status(T(f"已归档工作区 · {n_file} 个文件 → {path}", f"Workspace archived · {n_file} files → {path}"))
        QMessageBox.information(
            self, "归档完成",
            f"已归档 {n_file} 个文件（含历史快照与图片资产）：\n{path}\n\n"
            "建议定期归档并复制到另一块磁盘 / 网盘，避免单点丢失。")

    # v3.29d（B7/UX #28）：按用途记忆文件对话框的上次目录（导出 / 另存 / 打开）
    def _dlg_dir(self, key):
        """v3.39.2（PATH-1）：对话框起点目录三级回退 ——
        进程内按用途记忆 → QSettings 持久（重启沿用）→ 上次使用目录（lastOpenDir）。"""
        d = getattr(self, "_dir_map", {}).get(key, "")
        if not d:
            try:
                d = str(self._settings.value("files/dlgDir/%s" % key, "") or "")
            except Exception:      # noqa: BLE001
                d = ""
        if not d:
            d = self.last_open_dir()
        return d if (d and os.path.isdir(d)) else ""

    def _dlg_start(self, key, fallback=""):
        d = self._dlg_dir(key)
        if d and os.path.isdir(d):
            return os.path.join(d, os.path.basename(fallback or " "))
        return fallback

    def _remember_dir(self, key, path):
        if not hasattr(self, "_dir_map"):
            self._dir_map = {}
        d = os.path.dirname(os.path.abspath(str(path)))
        if os.path.isdir(d):
            self._dir_map[key] = d
            # v3.39.2（PATH-1）：按用途持久化，重启后打开 / 保存 / 导出对话框
            # 默认路径仍为上次使用的目录
            try:
                self._settings.setValue("files/dlgDir/%s" % key, d)
            except Exception:      # noqa: BLE001
                pass

    def export_html(self):
        def cb(html):
            if not html:
                return
            # v3.32（P0-4③）：网络图片需查看端联网，先明示（本地图片已内嵌）
            remote = len(re.findall(r"<img[^>]*\ssrc=[\"'](?:https?:)?//", html))
            if remote and not self._export_selfcheck_remote(remote):
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "导出 HTML",
                self._dlg_start("html",
                    os.path.splitext(self.file_path or "未命名")[0] + ".html"),
                "HTML 文件 (*.html)")
            if not path:
                return
            self._remember_dir("html", path)
            # v3.30.11（MATH-1）：内嵌本地 katex.min.css（字体转 data URI），
            # 导出 HTML 断网可用，不再依赖 CDN
            html = self._inline_katex_css(html)
            # v3.30.18（IMG-2）：本地相对路径图片内嵌为 data URI ——
            # 单文件 HTML 发给别人不再裂图（默认内嵌；失败图片保留原样）
            html, n_img = self._embed_local_images(html)
            # v3.45.3（EXPORT-LINK）：指向本地 .md 的链接改写为 .html
            # （单文件 HTML 的配套文件若也导出为 .html，链接才指得过去）
            html, n_link = self._rewrite_md_links(html)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.show_status(T(f"已导出 HTML · {path}", f"HTML exported · {path}")
                             + (f"（内嵌 {n_img} 张图片）" if n_img else "")
                             + (f"（{n_link} 条链接改为 .html）" if n_link else ""))
            self._export_done("HTML", path)
        self._js_active("window.getExportHTML()", cb)

    def export_png(self):
        """v3.45.8（REQ3#8）：将当前渲染区导出为 PNG 图片（补齐竞品短板 #8）。

        抓取当前可见的编辑视图（写作态渲染区）；若当前处于源码态则改抓源码视图。
        采用对当前可见视图直接 grab 的方式，避免离屏 QWebEngineView 在无 GPU /
        远程会话下可能出现的渲染阻塞，稳定可靠。"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出图片 (PNG)",
            self._dlg_start("png",
                os.path.splitext(self.file_path or "未命名")[0] + ".png"),
            "PNG 图片 (*.png)")
        if not path:
            return
        self._remember_dir("png", path)
        view = self._view
        if not view.isVisible():
            vs = getattr(self, "_view_src", None)
            if vs is not None and vs.isVisible():
                view = vs
        if not view.isVisible():
            self.show_status(T("导出 PNG 失败：当前无可渲染视图", "PNG export failed: no renderable view currently"))
            return
        pix = view.grab()
        if pix.isNull():
            self.show_status(T("导出 PNG 失败：截图为空", "PNG export failed: screenshot is empty"))
            return
        out = QImage(pix.size(), QImage.Format_ARGB32_Premultiplied)
        out.fill(Qt.white)
        p = QPainter(out)
        p.drawImage(0, 0, pix.toImage())
        p.end()
        if out.save(path, "PNG"):
            self.show_status(T("已导出 PNG 图片 · ", "PNG image exported · ") + path)
            self._export_done("PNG", path)
        else:
            self.show_status(T("导出 PNG 失败：保存失败", "PNG export failed: save failed"))

    def _rewrite_md_links(self, html):
        """v3.45.3（EXPORT-LINK）：导出 HTML 里指向本地 .md 的 <a href>
        改写为 .html（保留 #fragment）。外部 / 锚点 / data / 绝对路径不动。
        返回 (html, 改写条数)。"""
        if not html or ".md" not in html.lower():
            return html, 0
        count = [0]

        def _repl(m):
            href = m.group(1)
            low = href.lower()
            if low.startswith(("http://", "https://", "mailto:", "data:",
                               "blob:", "file:", "#", "/")):
                return m.group(0)
            path = href.split("#", 1)[0]
            if not re.search(r"\.(md|markdown|mdown)$", path, re.I):
                return m.group(0)
            new = exporters._rewrite_export_link(href, "", None)
            if new == href:
                return m.group(0)
            count[0] += 1
            return m.group(0).replace(href, new, 1)

        html = re.sub(r'<a\s[^>]*href="([^"]+)"', _repl, html)
        return html, count[0]

    def _embed_local_images(self, html):
        """v3.30.18（IMG-2）：把导出 HTML 里的本地图片内嵌为 base64 data URI。

        - data: / http(s): 已自包含或远程，不动；
        - file:/// 绝对 URL 与相对路径都按本地文件解析（相对路径相对文档目录）；
        - 文件缺失时保留原样（与既有「找不到则跳过」原则一致）。
        返回 (html, 内嵌张数)。"""
        if not html:
            return html, 0
        import urllib.parse
        doc_dir = os.path.dirname(self.file_path) if self.file_path else ""
        count = 0

        def _repl(m):
            nonlocal count
            src = m.group(1)
            if src.startswith(("data:", "http://", "https://")):
                return m.group(0)
            path = src
            if path.lower().startswith("file:///"):
                path = urllib.parse.unquote(path[len("file:///"):])
            elif path.lower().startswith("file:"):
                path = urllib.parse.unquote(path[5:])
                path = path.lstrip("/") if os.path.isabs(path.lstrip("/")) else path
            if not os.path.isabs(path):
                if not doc_dir:
                    return m.group(0)      # 未保存文档无法解析相对路径
                path = os.path.join(doc_dir, path.replace("/", os.sep))
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
            except OSError:
                return m.group(0)
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "gif": "image/gif", "webp": "image/webp",
                    "svg": "image/svg+xml", "bmp": "image/bmp"}.get(ext, "image/png")
            count += 1
            return m.group(0).replace(src, "data:" + mime + ";base64," + b64)

        html = re.sub(r'<img[^>]*\ssrc="([^"]+)"', _repl, html)
        return html, count

    def _inline_katex_css(self, html):
        """v3.30.11（MATH-1）：把 editor 侧留下的 __KATEX_CSS__ 占位替换为本地
        katex.min.css —— 字体文件转 base64 data URI（仅保留 woff2，woff/ttf 分支
        去掉），导出单文件离线可用。无占位（文档无公式）或 css 缺失时原样返回。
        结果缓存：字体 base64 转换约几百 KB，同一会话只算一次。"""
        if not html or "__KATEX_CSS__" not in html:
            return html
        css = getattr(self, "_katex_css_cache", None)
        if css is None:
            css = ""
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "katex")
            css_path = os.path.join(base, "katex.min.css")
            try:
                with open(css_path, "r", encoding="utf-8") as f:
                    css = f.read()
                fonts_dir = os.path.join(base, "fonts")
                # woff / ttf 分支直接去掉（现代浏览器均支持 woff2）
                css = re.sub(
                    r",?url\(\"?fonts/[^)]+?\.(?:woff|ttf)\"?\)\s*format\(\"(?:woff|truetype)\"\)",
                    "", css)

                def _font_uri(m):
                    # m.group(1) 形如 "fonts/KaTeX_AMS-Regular.woff2"，取basename
                    # 拼进字体目录（避免二次拼接 fonts/ 导致路径不存在）
                    fp = os.path.join(fonts_dir, os.path.basename(m.group(1)))
                    try:
                        with open(fp, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("ascii")
                    except OSError:
                        return m.group(0)
                    return 'url(data:font/woff2;base64,' + b64 + ') format("woff2")'

                css = re.sub(r"url\(\"?(fonts/[^)]+?\.woff2)\"?\)", _font_uri, css)
            except OSError:
                css = ""
            self._katex_css_cache = css
        if not css:
            # css 缺失（异常安装）：去掉整个占位 style，避免留下字面标记
            return html.replace('<style>__KATEX_CSS__</style>\n', "").replace(
                "<style>__KATEX_CSS__</style>", "")
        return html.replace("__KATEX_CSS__", css)

    def export_pdf(self):
        # v3.47.1（PDF-SET）：导出前弹出页边距 / 字体 / 字号设置（可保存为默认）
        dlg = PdfExportDialog(self, self._settings)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        opts = dlg.result_opts()
        if opts.get("save_default"):
            # v3.48.34（PDF-LAYOUT）：纸张 / 方向 / 四边边距 / 缩放 / 行距一并落盘
            from bookexport import save_opts
            save_opts(self._settings, opts)
        self._pdf_opts = opts
        # v3.45.3（EXPORT-LINK）：书签数据在导出瞬间实时取（700ms 轮询缓存
        # 可能滞后，刚切文档就导出会拿到空大纲 → 无书签）
        self._js_active(
            "window.getOutline() ? JSON.stringify(window.getOutline()) : '[]'",
            self._export_pdf_go)

    def _export_pdf_go(self, outline_json):
        try:
            self._pending_toc = json.loads(outline_json) \
                if isinstance(outline_json, str) else list(outline_json or [])
        except (TypeError, ValueError):
            self._pending_toc = []
        self._js_active("window.getExportHTML()", self._export_pdf_html)

    def _export_pdf_html(self, html):
        # v3.48.3（PDF-FIX）：旧版 html 为空时静默 return，表现为「点了导出没反应」。
        # 现在明确报错（JS 异常 / 空文档 / 视图未就绪都会走到这里）。
        if not html:
            self.show_status(T("导出 PDF 失败：未能获取文章内容", "PDF export failed: could not retrieve document content"))
            QMessageBox.warning(self, T("导出 PDF 失败", "PDF Export Failed"),
                T("未能从编辑器获取文章内容（可能当前视图未就绪或页面脚本报错）。\n"
                  "请切换到编辑视图后重试；若仍失败请把 ai.log / 控制台信息反馈。",
                  "Could not get document content from the editor (the view may not be ready or the page script errored).\n"
                  "Switch to the editing view and retry; if it still fails, send the ai.log / console output."))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 PDF",
            self._dlg_start("pdf",
                os.path.splitext(self.file_path or "未命名")[0] + ".pdf"),
            "PDF 文件 (*.pdf)")
        if not path:
            return
        self._remember_dir("pdf", path)
        self._pdf_path = path
        self._pdf_view = QWebEngineView(self)  # 隐藏的导出视图
        self._pdf_view.hide()
        v = self._pdf_view
        v.setPage(EditorPage(v, self))
        v.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        v.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        # v3.30.11（MATH-1）：PDF 渲染同样走离线内嵌 css（公式静态化后零依赖）
        html = self._inline_katex_css(html)
        # v3.48.5（PDF-BG）：导出 HTML 的 body 背景随主题（--canvas 灰），
        # printToPdf 会把整页画布背景印出来 —— PDF 末页空白区一片灰。
        # PDF 导出强制白底（正文卡片 .page 本身是白底，不受影响）。
        html = html.replace(
            "</head>",
            "<style>html,body{background:#ffffff !important}</style>\n</head>",
            1)
        # v3.47.1（PDF-SET）：应用用户设定的字体 / 字号（注入 !important 样式）
        opts = getattr(self, "_pdf_opts", None)
        if opts and opts.get("font_size_pt"):
            html = self._apply_pdf_font_css(
                html, opts.get("font_family", ""), opts["font_size_pt"])
        if opts:
            # v3.48.34（PDF-LAYOUT）：缩放 / 行间距（打印期 CSS，body zoom）
            html = self._apply_pdf_layout_css(html, opts)
        base = QUrl.fromLocalFile(
            (os.path.dirname(self.file_path) if self.file_path else os.path.expanduser("~")) + "/")
        v.loadFinished.connect(self._print_pdf)
        v.setHtml(html, base)

    def _print_pdf(self, ok):
        if not self._pdf_view:
            return
        # v3.48.3（PDF-FIX）：加载失败不再静默 —— 旧版 ok=False 直接 return，
        # 表现为「点了导出没反应、也没有任何提示」
        if not ok:
            self.show_status(T("导出 PDF 失败：内容页面加载失败", "PDF export failed: content page failed to load"))
            self._pdf_done_cleanup()
            QMessageBox.warning(self, T("导出 PDF 失败", "PDF Export Failed"),
                T("导出内容页面加载失败，请重试；若持续失败请反馈。",
                  "The export content page failed to load; please retry. If it keeps failing, send feedback."))
            return
        try:
            page = self._pdf_view.page()
            page.pdfPrintingFinished.connect(self._pdf_done)
            opts = getattr(self, "_pdf_opts", None)
            # v3.48.4（PDF-KW）：PySide6 6.11 的 printToPdf 只支持位置参数传
            # QPageLayout（pageLayout= 关键字抛 AttributeError），且该异常类型
            # 不是 TypeError——降级分支改为 Exception 兜底。
            # v3.48.34（PDF-LAYOUT）：纸张 / 方向 / 四边独立边距统一由
            # bookexport.pdf_page_layout 构造（单位显式 Millimeter）。
            if opts:
                try:
                    from bookexport import pdf_page_layout
                    page.printToPdf(self._pdf_path, pdf_page_layout(opts))
                except Exception:
                    page.printToPdf(self._pdf_path)
            else:
                page.printToPdf(self._pdf_path)
        except Exception as e:
            self.show_status(T("导出 PDF 失败：%s", "PDF export failed: %s") % e)
            self._pdf_done_cleanup()
            QMessageBox.critical(self, T("导出 PDF 失败", "PDF Export Failed"), str(e))

    def _pdf_done_cleanup(self):
        """v3.48.3（PDF-FIX）：失败路径同样回收隐藏导出视图，避免句柄残留。"""
        self._pending_toc = None
        if self._pdf_view:
            self._pdf_view.deleteLater()
            self._pdf_view = None

    # v3.47.1（PDF-SET）：PDF 字体 / 字号注入（覆盖导出模板默认 16px 正文）
    @staticmethod
    def _apply_pdf_font_css(html, font_family, font_size_pt):
        fam = (font_family or "").strip()
        if not fam:
            fam = '"Microsoft YaHei", "PingFang SC", sans-serif'
        style = (
            "<style id='mded-pdf-font'>"
            "body,.page,#editor{font-family:%s!important;"
            "font-size:%.1fpt!important;}"
            "@media print{body{font-size:%.1fpt!important;}}"
            "</style>"
            % (fam, font_size_pt, font_size_pt))
        if "</head>" in html:
            return html.replace("</head>", style + "</head>", 1)
        return html + style

    @staticmethod
    def _apply_pdf_layout_css(html, opts):
        """v3.48.34（PDF-LAYOUT）：缩放 / 行间距打印期 CSS。"""
        from bookexport import _apply_pdf_layout_css as _f
        return _f(html, opts)

    def _pdf_defaults(self):
        """读取已保存的 PDF 默认设置（无则取界面字体 / 常规值）。"""
        from bookexport import opts_from_settings
        return opts_from_settings(self._settings)

    def _pdf_done(self, path, ok):
        if not ok:
            self.show_status(T("导出 PDF 失败", "PDF export failed"))
        else:
            n, msg = exporters.add_pdf_bookmarks(path, getattr(self, "_pending_toc", None))
            # v3.45.5（PDF-LINK-2）：本地 .md 链接注解 → 相对 .html 路径。
            # 单文档导出此前完全不做链接改写，file:// 注解在多数阅读器里
            # 点了没反应；与 HTML 导出口径对齐（换后缀 + 相对路径）。
            m = exporters.linkify_pdf_links(
                path, {}, out_dir=os.path.dirname(os.path.abspath(path)))
            if m:
                msg += f"，{m} 条链接改为相对 .html 路径"
            self.show_status(T(f"已导出 PDF · {path}", f"PDF exported · {path}") + (f"（{msg}）" if n else f"（{msg}）"))
            self._export_done("PDF", path)
        self._pending_toc = None
        if self._pdf_view:
            self._pdf_view.deleteLater()
            self._pdf_view = None

    # ---- Word / EPUB ----
    def _pandoc_exe(self):
        return exporters.find_pandoc(getattr(self, "_pandoc_path", ""))

    def set_pandoc_path(self, path):
        """设置外部 pandoc 路径（留空 = 自动探测 PATH）。"""
        self._pandoc_path = str(path or "").strip()
        self._settings.setValue("pandocPath", self._pandoc_path)
        found = self._pandoc_exe()
        self.show_status(T(f"pandoc 路径已保存：{found}", f"Pandoc path saved: {found}") if found
                             else "pandoc 路径已保存（当前未探测到 pandoc，将使用内置导出）")

    # ---- v3.48.12（SEM-2）：本地语义搜索 ----
    def set_semantic_search(self, on):
        """本地语义搜索总开关（系统设置 → 通用 → 本地语义搜索）。"""
        self._sem_enabled = bool(on)
        self._settings.setValue("semSearchEnabled", bool(on))
        self.show_status(T("本地语义搜索：开", "Local semantic search: On") if on else "本地语义搜索：关")

    def sem_index_stats(self):
        """语义索引状态（设置页展示）。异常退化为空 dict。"""
        try:
            idx = semsearch.SemIndex()
            st = idx.stats()
            idx.close()
            return st
        except Exception:
            return {}

    def sem_rebuild_index(self):
        """清空语义索引（下次语义搜索自动全量重建）。"""
        try:
            idx = semsearch.SemIndex()
            idx.clear()
            idx.close()
            self.show_status(T("语义索引已清除，下次语义搜索时自动重建", "Semantic index cleared; rebuilt automatically on next semantic search"))
        except Exception as e:
            self.show_status(T(f"清除语义索引失败：{e}", f"Clear semantic index failed: {e}"))

    def _export_document(self, kind):
        """kind: 'docx' | 'epub'。优先 pandoc，未安装则回退内置实现。"""
        label = "Word (docx)" if kind == "docx" else "EPUB"
        ext = ".docx" if kind == "docx" else ".epub"
        filt = "Word 文档 (*.docx)" if kind == "docx" else "EPUB 电子书 (*.epub)"

        def cb(md):
            if md is None:
                return
            # v3.32（P0-4③/P1-10①）：导出前"交付自检"——明示降级项再让用户决定
            if not self._export_selfcheck(md, kind):
                return
            # v3.29d（B6/UX #33）：pandoc 未安装时导出前先预警（每会话只提示一次），
            # 说明降级影响并给出安装指引，不再静默回退内置转换
            pandoc = self._pandoc_exe()
            if not pandoc and not getattr(self, "_pandoc_warned", False):
                self._pandoc_warned = True
                ret = QMessageBox.question(
                    self, "未检测到 pandoc",
                    "未检测到 pandoc，将使用内置转换导出：\n"
                    "· 公式与图表会降级为「源码 + 标注」形式\n"
                    "· 标题 / 表格 / 图片等其余内容正常导出\n\n"
                    "如需完整的公式 / 图表导出效果，可到 pandoc 官网"
                    "（pandoc.org）下载安装，并在 系统设置 → 通用 中配置路径。\n\n"
                    "是否继续使用内置转换导出？",
                    QMessageBox.Yes | QMessageBox.No)
                if ret != QMessageBox.Yes:
                    return
            path, _ = QFileDialog.getSaveFileName(
                self, f"导出 {label}",
                self._dlg_start(kind,
                    os.path.splitext(self.file_path or "未命名")[0] + ext), filt)
            if not path:
                return
            self._remember_dir(kind, path)
            base_dir = self._doc_dir()
            title = os.path.splitext(os.path.basename(self.file_path or "未命名"))[0]
            if pandoc:
                ok, msg = exporters.pandoc_convert(pandoc, md, path, kind, base_dir)
                self.show_status(msg)
                if not ok:
                    QMessageBox.warning(self, T(f"导出 {label} 失败", f"Export {label} failed"), msg)
                return
            # v3.30.19（MMD-2）+ v3.44.31（MATH-EXP）：内置导出前把已渲染图表与公式位图化
            self._export_with_render(kind, label, md, path, base_dir, title)

        self._js_active("window.getMarkdown()", cb)

    def _export_with_mmd(self, kind, label, md, path, base_dir, title):
        """v3.30.19（MMD-2）：让编辑器把已渲染 SVG 转 PNG，收齐后执行内置导出。"""
        def start(total):
            if not total:
                self._export_now(kind, label, md, path, base_dir, title, {})
                return
            self._mmd_export = {"total": int(total), "t0": time.time()}
            self._mmd_poll(kind, label, md, path, base_dir, title)
        self._js_active("window.__mmdExportStart ? window.__mmdExportStart() : 0", start)

    def _mmd_poll(self, kind, label, md, path, base_dir, title):
        def got(state):
            st = state or {}
            done = int(st.get("done", 0) or 0)
            total = int(st.get("total", 0) or 0)
            if done >= total or time.time() - self._mmd_export["t0"] > 12:
                mmd_png = {}
                for it in st.get("items", []):
                    src = str(it.get("src") or "")
                    data = str(it.get("data") or "")
                    if not src or not data or src in mmd_png:
                        continue
                    try:
                        fd, tmp = tempfile.mkstemp(suffix=".png")
                        with os.fdopen(fd, "wb") as f:
                            f.write(base64.b64decode(data.split(",", 1)[-1]))
                        mmd_png[src] = tmp
                    except Exception as e3:
                        _log.debug("图表 PNG 落盘失败: %s", e3)
                self._export_now(kind, label, md, path, base_dir, title, mmd_png)
                return
            QTimer.singleShot(300, lambda: self._mmd_poll(kind, label, md, path, base_dir, title))
        self._js_active("window.__mmdExportState || null", got)

    def _export_with_render(self, kind, label, md, path, base_dir, title):
        """v3.44.31（MATH-EXP）：内置导出前把已渲染图表(MMD-2)与公式位图化，收齐后导出。

        与 _export_with_mmd 同构，但并行启动图表(__mmdExportStart)与公式(__mathExportStart)
        两侧收集；公式位图化需在 foreignObject 内携带 KaTeX 字体，这里先把内联 katex CSS
        注入页面（缺失则给空串，仍尝试位图化、回落默认字体）。"""
        import json as _json
        css = self._inline_katex_css("__KATEX_CSS__")
        if "__KATEX_CSS__" in css:
            css = ""   # 字体缺失（异常安装）：不阻塞导出，位图化回落默认字体
        js = ("(function(){window.__KATEX_CSS__=" + _json.dumps(css) +
              ";var n=0;if(window.__mmdExportStart)n+=window.__mmdExportStart();"
              "if(window.__mathExportStart)n+=window.__mathExportStart();return n;})()")

        def start(_total):
            self._export_render_poll(kind, label, md, path, base_dir, title, time.time())

        self._js_active(js, start)

    def _export_render_poll(self, kind, label, md, path, base_dir, title, t0):
        def got(payload):
            st = payload or {}
            mmd = st.get("mmd") or {}
            math = st.get("math") or {}
            md_done = int(mmd.get("done", 0) or 0)
            md_total = int(mmd.get("total", 0) or 0)
            mt_done = int(math.get("done", 0) or 0)
            mt_total = int(math.get("total", 0) or 0)
            if (md_done >= md_total and mt_done >= mt_total) or (time.time() - t0 > 12):
                mmd_png, math_png = {}, {}
                for it in (mmd.get("items") or []):
                    src = str(it.get("src") or "")
                    data = str(it.get("data") or "")
                    if not src or not data or src in mmd_png:
                        continue
                    try:
                        fd, tmp = tempfile.mkstemp(suffix=".png")
                        with os.fdopen(fd, "wb") as f:
                            f.write(base64.b64decode(data.split(",", 1)[-1]))
                        mmd_png[src] = tmp
                    except Exception as e3:
                        _log.debug("图表 PNG 落盘失败: %s", e3)
                for it in (math.get("items") or []):
                    src = str(it.get("src") or "")
                    data = str(it.get("data") or "")
                    if not src or not data or src in math_png:
                        continue
                    try:
                        fd, tmp = tempfile.mkstemp(suffix=".png")
                        with os.fdopen(fd, "wb") as f:
                            f.write(base64.b64decode(data.split(",", 1)[-1]))
                        math_png[src] = tmp
                    except Exception as e3:
                        _log.debug("公式 PNG 落盘失败: %s", e3)
                self._export_now(kind, label, md, path, base_dir, title, mmd_png, math_png)
                return
            QTimer.singleShot(
                300, lambda: self._export_render_poll(kind, label, md, path, base_dir, title, t0))

        self._js_active(
            "({mmd:(window.__mmdExportState||null),math:(window.__mathExportState||null)})", got)

    def _export_now(self, kind, label, md, path, base_dir, title, mmd_png, math_png=None):
        if kind == "docx":
            ok, msg = exporters.write_docx(md, path, base_dir, title,
                                          mmd_png=mmd_png, math_png=math_png)
        else:
            ok, msg = exporters.write_epub(
                md, path, base_dir, title, mmd_png=mmd_png, math_png=math_png,
                border_color=getattr(self, "_theme_border", "") or "#ddd")   # v3.38（HR-8②）
        self.show_status(msg)
        if not ok:
            QMessageBox.warning(self, T(f"导出 {label} 失败", f"Export {label} failed"), msg)
        else:
            self._export_done(label, path)

    def export_docx(self):
        self._export_document("docx")

    def export_epub(self):
        self._export_document("epub")

    # ================= 杂项 =================
    def check_update(self):
        """v3.32（P0-6①）：检查更新 —— 拉取 version.json（{"version","url"}），
        只提示不强升；URL 可在 QSettings.updateUrl 覆盖，留空提示未配置。"""
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
        from PySide6.QtCore import QUrl as _QUrl
        url = str(self._settings.value("updateUrl", "") or "") or UPDATE_URL
        if not url:
            QMessageBox.information(
                self, "检查更新",
                f"当前版本 v{APP_VERSION}。\n\n尚未配置更新源（updateUrl）。\n"
                "发布新版本时请到下载页获取最新安装包。")
            return
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, T("检查更新", "Check for Updates"), T("更新源地址无效（须为 http/https）。", "Update source URL is invalid (must be http/https)."))
            return
        self.show_status(T("正在检查更新…", "Checking for updates…"))
        nam = QNetworkAccessManager(self)

        def _done(reply):
            reply.deleteLater()
            if reply.error() != QNetworkReply.NoError:
                QMessageBox.warning(
                    self, "检查更新",
                    f"无法连接更新源：\n{reply.errorString()}\n\n"
                    f"当前版本 v{APP_VERSION}。请检查网络后重试，或直接到下载页查看。")
                return
            try:
                info = json.loads(bytes(reply.readAll()).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                QMessageBox.warning(self, T("检查更新", "Check for Updates"), T("更新源返回内容不是有效的 version.json。", "Update source returned an invalid version.json."))
                return
            remote = str(info.get("version") or "").strip()
            if not remote:
                QMessageBox.warning(self, T("检查更新", "Check for Updates"), T("version.json 中缺少 version 字段。", "version.json is missing the version field."))
                return
            if self._ver_ge(remote, APP_VERSION):
                QMessageBox.information(self, T("检查更新", "Check for Updates"),
                                        f"已是最新版本（v{APP_VERSION}）。")
                return
            btn = QMessageBox.question(
                self, "发现新版本",
                f"当前版本 v{APP_VERSION}\n最新版本 v{remote}\n"
                f"{info.get('note') or ''}\n\n是否前往下载页？",
                QMessageBox.Yes | QMessageBox.No)
            if btn == QMessageBox.Yes and info.get("url"):
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(_QUrl(str(info["url"])))

        nam.finished.connect(_done)
        nam.get(QNetworkRequest(_QUrl(url)))

    @staticmethod
    def _ver_ge(a, b):
        """版本号比较：a >= b（按 . 分段数值比较，长度不齐补 0）。"""
        pa = [int(x) for x in re.findall(r"\d+", a)] or [0]
        pb = [int(x) for x in re.findall(r"\d+", b)] or [0]
        n = max(len(pa), len(pb))
        pa += [0] * (n - len(pa))
        pb += [0] * (n - len(pb))
        return pa >= pb

    def copy_diagnostics(self):
        """v3.32（P0-5②）：把版本 / 系统 / 依赖 / 最近日志拼成诊断文本复制到剪贴板，
        用户报障时一次给全信息。"""
        import platform
        import PySide6
        pandoc = self._pandoc_exe()
        lines = [
            f"版本: mdEditor v{APP_VERSION}",
            f"系统: {platform.platform()}",
            f"Python: {platform.python_version()}　PySide6: {PySide6.__version__}",
            f"主题: {self._theme}　自动保存: {'开' if self._autosave else '关'}",
            f"pandoc: {pandoc or '未检测到（导出 Word/EPUB 将用内置转换）'}",
        ]
        try:
            log_fp = os.path.join(LOG_DIR, "mdEditor.log")
            with open(log_fp, "r", encoding="utf-8", errors="replace") as f:
                tail = [ln.rstrip() for ln in f.readlines()[-50:]]
            lines.append(T("--- 最近日志（50 行）---", "--- Recent logs (50 lines) ---"))
            lines.extend(tail or ["（日志为空）"])
        except OSError:
            lines.append(T("（日志文件不可读）", "(log file not readable)"))
        QApplication.clipboard().setText("\n".join(lines))
        self.show_status(T("诊断信息已复制到剪贴板，可粘贴给开发者", "Diagnostic info copied to clipboard; you can paste it to the developer"))

    def _about(self):
        """v3.29d（UX #29）：关于页显示版本号，并提供「查看更新日志」入口。"""
        ret = QMessageBox.question(
            self, "关于",
            f"<b>{APP_NAME}</b>　<span style='color:#888;'>v{APP_VERSION}</span><br>"
            "由YY先生研发的一款所见即所得 Markdown 编辑器<br>"
            "支持多文件标签页、双栏（源码 / 预览）模式、数学公式<br>"
            "基于 Python + PySide6 (QtWebEngine) 构建。<br><br>"
            "是否查看更新日志（CHANGELOG.md）？",
            QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        log_md = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "CHANGELOG.md")
        if not os.path.exists(log_md):
            log_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md")
        if os.path.exists(log_md):
            try:
                openutil.open_path(log_md)     # 跨平台：系统默认程序打开
            except OSError:
                self.show_status(T("无法打开更新日志", "Cannot open update log"))
        else:
            self.show_status(T("未找到 CHANGELOG.md", "CHANGELOG.md not found"))

    # ---- v3.38（HELP-1）：使用手册 ----
    def _manual_md(self):
        """读取使用手册 Markdown（开发态 src/，打包态 _internal/）。"""
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "使用手册.md")
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return "# 使用手册\n\n手册文件缺失：" + p

    def _show_manual(self):
        """使用手册：独立非模态窗口，用编辑器内核只读渲染（滚动浏览）。"""
        if getattr(self, "_manual_dlg", None) is None:
            dlg = QDialog(self)
            dlg.setWindowTitle(T(f"使用手册 · {APP_NAME}", f"User Manual · {APP_NAME}"))
            dlg.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
            dlg.resize(960, 720)
            v = QWebEngineView(dlg)
            v.settings().setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            lay = QHBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(v)
            dlg._view = v
            dlg._ready = False

            def _fill(ok):
                if not ok:
                    return
                self._js_view(v, f"window.setTheme({js(self._theme)})")
                v.setZoomFactor(self._zoom)
                self._js_view(v, "window.setPreviewMode(true)")
                self._js_view(v, f"window.setPreviewContent({js(self._manual_md())})")
                dlg._ready = True

            v.loadFinished.connect(_fill)
            v.load(QUrl.fromLocalFile(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor.html")))
            self._manual_dlg = dlg
        self._manual_dlg.show()
        self._manual_dlg.raise_()
        self._manual_dlg.activateWindow()
        self.show_status(T("已打开使用手册（滚动浏览，Esc 关闭）", "User manual opened (scroll to browse, Esc to close)"))


    # ---- 最近文件 ----
    def _add_recent(self, path):
        lst = self._settings.value("recentFiles", []) or []
        if isinstance(lst, str):
            lst = [lst]
        path = os.path.abspath(path)
        if path in lst:
            lst.remove(path)
        lst.insert(0, path)
        self._trim_recent(lst)

    def _trim_recent(self, lst=None):
        """v3.44（RECENT-MAX）：按 _recent_max 裁剪最近文件列表（0=清空）。"""
        if lst is None:
            lst = self._settings.value("recentFiles", []) or []
            if isinstance(lst, str):
                lst = [lst]
        if self._recent_max <= 0:
            self._settings.setValue("recentFiles", [])
        else:
            self._settings.setValue("recentFiles", lst[:self._recent_max])

    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        lst = self._settings.value("recentFiles", []) or []
        if isinstance(lst, str):
            lst = [lst]
        if not lst:
            self._recent_menu.addAction("(空)").setEnabled(False)
            return
        for p in lst:
            act = self._recent_menu.addAction(p)
            act.triggered.connect(lambda _=False, f=p: self.open_file(f))
        self._recent_menu.addSeparator()
        clr = self._recent_menu.addAction("清空最近文件")
        clr.triggered.connect(lambda: self._settings.setValue("recentFiles", []))

    # ---- 侧边栏 ----
    def toggle_sidebar(self):
        # v3.47.6（REQ1）：AI 助手 与 侧边栏 互斥。若 AI 面板当前可见，则强制
        # 隐藏 AI（并显示侧栏），实现「显示其一即隐藏另一」；否则正常切换侧栏。
        if self._ai_dock.isVisible():
            self._hide_ai_dock()
            act_ai = getattr(self, "_act_ai", None)
            if act_ai is not None:
                act_ai.setChecked(False)
            self._sidebar.setVisible(True)
            self._update_side_btn()
            return
        self._sidebar.setVisible(not self._sidebar.isVisible())
        self._update_side_btn()

    def _update_side_btn(self):
        """左侧工具栏顶部开关（v3.40 UI-R7③：线性侧栏面板图标，展开/收起双态）。"""
        vis = self._sidebar.isVisible()
        self._btn_side.setIcon(icon_sidepanel(20, collapsed=not vis))
        self._btn_side.setToolTip(
            T(("收起" if vis else "展开") + "侧边栏 (Ctrl+Shift+L)"))
        if getattr(self, "_act_sidebar", None) is not None:
            self._act_sidebar.setChecked(vis)
        mtb = getattr(self, "_mac_title", None)   # v3.41.0：mac 统一工具栏同款钮同步
        if mtb is not None:
            mtb.sync_side_icon(vis)

    def _show_sidebar_tab(self, tab):
        self._sidebar.setVisible(True)
        self._update_side_btn()
        self._sidebar.select_tab(tab)
        # v3.38（FLP-2）：启动时未定位过侧栏（如 lastFile 档 / 定位失败）→
        # 首次打开文件列表 tab 时按 FLP-2 优先级链补定位（once 仅一次，
        # 不打断用户后续浏览；已定位过则此调用是空操作）
        if tab == 0:
            self._sidebar.restore_initial_dir(once=True)

    # ---- 主工具栏 显示 / 隐藏（v3.38 TB-1）----
    def set_toolbar_visible(self, vis, toast=True):
        """显示 / 隐藏左侧主工具栏；隐藏时左侧边缘常驻「»」展开按钮。"""
        vis = bool(vis)
        self._tool_tb.setVisible(vis)
        # 注意：窗口尚未 show() 时 isVisible() 恒为 False（Qt 语义），**不能**拿它当
        # 「用户意图」落盘 —— 否则每次启动都会把 ui/toolbarVisible 写成 False，下次
        # 启动工具栏就凭空消失（TB-1 的症状换个马甲复发）。故显式把 vis 传下去。
        self._sync_toolbar_state(toast=toast and not vis, vis=vis)

    def toggle_toolbar(self, checked=True):
        """视图菜单 / 右键菜单 / 快捷键入口（checkable 动作带新勾选态）。"""
        self.set_toolbar_visible(bool(checked))

    def _sync_toolbar_state(self, toast=False, persist=True, vis=None):
        """按工具栏可见性同步展开按钮 / 菜单勾选 / 持久化，并给出恢复提示。

        vis=None → 取控件真实可见性（visibilityChanged 路径，此时窗口已 show，可信）；
        显式传入 → 以调用方意图为准（启动初始化阶段 isVisible() 不可信）。
        """
        vis = self._tool_tb.isVisible() if vis is None else bool(vis)
        btn = getattr(self, "_btn_tb_show", None)
        if btn is not None:
            btn.setVisible(not vis)
            if not vis:
                self._place_tb_expand_btn()
                btn.raise_()
        act = getattr(self, "_act_toolbar", None)
        if act is not None and act.isChecked() != vis:
            act.setChecked(vis)
        if persist:
            self._settings.setValue("ui/toolbarVisible", vis)
        if toast and not vis:
            self.show_status(T("工具栏已隐藏：点击左侧边缘的 » 或按 Ctrl+Shift+B 可重新展开", "Toolbar hidden: click the » at the left edge or press Ctrl+Shift+B to expand again"))

    # ---- 模式切换（写作 / 源码 / 分屏）----
    def _mode_label(self):
        for m in MODES:
            if m[0] == self._mode:
                return m[2], m[3]
        return "写作模式", ""

    def _update_mode_button(self):
        """v3.40（UI-R7⑪）：模式状态唯一源 = self._mode，订阅者三处单向刷新——
        菜单栏右端分段钮 / 状态栏模式格 / 视图菜单单选项（原左工具栏循环钮已退役）。"""
        name, _desc = self._mode_label()
        # 菜单栏右端分段钮（blockSignals 防回环）
        seg = getattr(self, "_seg_btns", {})
        for mid, b in seg.items():
            b.blockSignals(True)
            b.setChecked(mid == self._mode)
            b.blockSignals(False)
        # v3.44.12（RIBBON-1）：功能区「模式」大钮同步
        rb = getattr(self, "_ribbon_body", None)
        if rb is not None:
            rb.sync_mode(self._mode)
        # 状态栏模式格 / status-bar mode cell
        cell = getattr(self, "_cell_mode", None)
        if cell is not None:
            cell.setText(name.replace("模式", "") or T("写作", "Writing"))
        # 菜单里的模式单选同步勾选状态 / sync the mode radio state in the menu
        act = getattr(self, "_mode_acts", {}).get(self._mode)
        if act and not act.isChecked():
            act.setChecked(True)

    def cycle_mode(self):
        order = [m[0] for m in MODES]
        nxt = order[(order.index(self._mode) + 1) % len(order)]
        self._set_mode(nxt)

    def _set_mode(self, mode, force=False):
        """统一的三态模式切换，保留各视图内容不丢失。

        v3.45.7（REQ4）：force=True 时即便目标模式与当前相同也强制重应用
        （用于切换文件后让视图与「该文件自身模式」严格对齐，消除源态漂移）。"""
        if mode not in ("edit", "src", "dual") or (mode == self._mode and not force):
            return
        if mode == "dual":
            # 首次进入分屏：此时才创建源码/预览视图（启动提速）
            self._ensure_dual_views()

            # 进入分屏：把写作视图内容推到 源码 + 预览
            def apply(md):
                text = md if md is not None else ""
                self._mode = mode
                self._store_doc_mode()
                self._dual = True
                self._last_preview_md = None
                self._push_text(text)
                self._stack.setCurrentIndex(1)
                self._update_mode_button()
                self.show_status(T("分屏模式：左侧源码编辑 · 右侧实时预览", "Split mode: source editing on left · live preview on right"))
            self._js_view(self._view, "window.getMarkdown()", apply)
            return
        # 回到单栏（写作 或 源码）
        src_on = "true" if mode == "src" else "false"

        def apply_back(md):
            text = md if md is not None else ""
            self._stack.setCurrentIndex(0)
            self._last_preview_md = None
            st = self._vstate["edit"]
            if st["loaded"]:
                self._js_view(self._view, f"window.setMarkdown({js(text)})")
                self._js_view(self._view, f"window.setSourceMode({src_on})")
            else:
                st["pending"] = text
            self._mode = mode
            self._store_doc_mode()
            self._dual = False
            self._update_mode_button()
            name, _ = self._mode_label()
            self.show_status(name)

        if self._mode == "dual":
            self._js_view(self._view_src, "window.getMarkdown()", apply_back)
        else:
            # 写作 <-> 源码：同一视图，直接开关源码态
            st = self._vstate["edit"]
            if st["loaded"]:
                self._js_view(self._view, f"window.setSourceMode({src_on})")
            self._mode = mode
            self._store_doc_mode()
            self._update_mode_button()
            name, _ = self._mode_label()
            self.show_status(name)

    def _store_doc_mode(self):
        """v3.45.7（REQ4）：把当前全局模式写入当前文档字典，供切走再切回时恢复。"""
        if 0 <= self._cur < len(self._docs):
            d = self._docs[self._cur]
            if "mode" not in d:
                d["mode"] = "edit"
            d["mode"] = self._mode

    def toggle_typewriter(self):
        self._typewriter = not getattr(self, "_typewriter", False)
        self._settings.setValue("typewriter", bool(self._typewriter))
        self._act_typewriter.setChecked(self._typewriter)
        # v3.40（UI-R7）：菜单栏右端快捷开关镜像（单向订阅）
        qk = getattr(self, "_qk_tw", None)
        if qk is not None:
            qk.blockSignals(True)
            qk.setChecked(self._typewriter)
            qk.blockSignals(False)
        self._js_active(
            f"window.setMode({{typewriter: {str(self._typewriter).lower()}}})")
        self.show_status(T("打字机模式：开", "Typewriter mode: On") if self._typewriter else "打字机模式：关")

    def toggle_focus(self):
        self._focus = not getattr(self, "_focus", False)
        self._settings.setValue("focus", bool(self._focus))
        self._act_focus.setChecked(self._focus)
        # v3.40（UI-R7）：菜单栏右端快捷开关镜像（单向订阅）
        qk = getattr(self, "_qk_focus", None)
        if qk is not None:
            qk.blockSignals(True)
            qk.setChecked(self._focus)
            qk.blockSignals(False)
        self._js_active(f"window.setMode({{focus: {str(self._focus).lower()}}})")
        self.show_status(T("专注模式：开", "Focus mode: On") if self._focus else "专注模式：关")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ---- v3.40（UI-R7）：状态栏 / 视图状态区辅助 ----
    def toggle_statusbar(self, checked=True):
        """视图 → 显示 / 隐藏状态栏（checkable 动作，QSettings 持久化）。

        v3.47.6（REQ1）：状态栏与 AI 助手不再互斥 —— 仅由用户显隐控制，
        与侧边栏 / AI 面板相互独立。"""
        vis = bool(checked)
        self.statusBar().setVisible(vis)
        self._settings.setValue("ui/statusbarVisible", vis)

    def _update_save_cell(self):
        """保存态格：✓ 已保存（静默绿）/ ● 未保存（琥珀）/ ⟳ 保存中（强调色）。

        性能红线：状态变化才 setText（_on_collect 轮询驱动 + 保存流程主动推送）。"""
        cell = getattr(self, "_cell_save", None)
        if cell is None:
            return
        state = "saving" if getattr(self, "_saving", False) else (
            "dirty" if self._dirty else "saved")
        if state == getattr(self, "_save_state", None):
            return
        self._save_state = state
        text, color = {
            "saved": ("✓ 已保存", "#1d9e75"),     # UI-SPEC --success
            "dirty": ("● 未保存", "#b7791f"),
            "saving": ("⟳ 保存中", "#0052d9"),
        }[state]
        cell.setText(text)
        cell.setStyleSheet(f"color: {color}; padding: 0 4px;")

    def _apply_chrome_styles(self):
        """v3.40（UI-R7⑫）：菜单栏右端视图状态区 + 状态栏交互格随主题 / 风格调色。

        令牌取「主题调色板 + 界面风格覆盖」合并结果（uistyles.merge_pipeline 同源）。"""
        if getattr(self, "_vsz_corner", None) is None:
            return
        p = uistyles.merge_palette(self._theme)
        # 专注 / 打字机：扁平风格（无边框、无实底，仅文字 + 轻量 hover / 选中浅色强调）
        qk_css = (
            f"QToolButton#qk {{ border: none; background: transparent;"
            f" padding: 0 8px; color: {p['text_muted']}; }}"
            f"QToolButton#qk:hover {{ background: {p['menu_hover_bg']}; color: {p['accent']}; }}"
            f"QToolButton#qk:checked {{ background: {p['accent_soft']}; color: {p['accent']}; }}")
        # 写作 / 源码 / 分屏：分段控件内的钮（无独立边框，靠容器描边成组；选中段 accent 凸起）
        # v3.44.29：极简无界(zen)风格要求「统一配色、无强调蓝」——选中段改用中性灰
        # （hover 同族底色 + 正文色），避免与主题强调蓝割裂；其余风格沿用主题 accent。
        _is_zen = (uistyles.active() == "zen")
        if _is_zen:
            seg_css = (
                f"QToolButton#seg {{ border: none; background: transparent;"
                f" padding: 0 12px; color: {p['text_muted']}; }}"
                f"QToolButton#seg:hover {{ background: {p['menu_hover_bg']}; color: {p['text']}; }}"
                f"QToolButton#seg:checked {{ background: {p['hover_bg']}; color: {p['text']};"
                f" border-radius: 6px; }}")
        else:
            seg_css = (
                f"QToolButton#seg {{ border: none; background: transparent;"
                f" padding: 0 12px; color: {p['text_muted']}; }}"
                f"QToolButton#seg:hover {{ background: {p['menu_hover_bg']}; color: {p['accent']}; }}"
                f"QToolButton#seg:checked {{ background: {p['accent']}; color: #ffffff;"
                f" border-radius: 6px; }}")
        for b in (self._qk_focus, self._qk_tw):
            b.setStyleSheet(qk_css)
        for b in self._seg_btns.values():
            b.setStyleSheet(seg_css)
        self._qk_sep.setStyleSheet(f"background: {p['sep']};")
        # 分段控件容器：扁平浅底 + 细描边 + 小圆角（v3.44.28 RIBBON-14：去浮雕渐变，仅略高于按钮）
        seg_group_css = (
            f"QWidget#segGroup {{ border: 1px solid {p['input_border']}; border-radius: 8px;"
            f" background: {p['input_bg']}; }}")
        if getattr(self, "_seg_group_widget", None) is not None:
            self._seg_group_widget.setStyleSheet(seg_group_css)
        # 分段控件内部分隔线
        for dv in getattr(self, "_seg_divs", []):
            dv.setStyleSheet(f"background: {p['input_border']};")
        # 状态栏可点击格：hover 提示强调色
        for c in (self._cell_mode, self._cell_zoom):
            c.setStyleSheet(f"color: {p['text_muted']}; padding: 0 6px;")
        # 状态栏常驻格随主题着色（令牌驱动，避免写死浅色强调/次级字色导致深主题割裂）
        if getattr(self, "_toast", None) is not None:
            self._toast.setStyleSheet(f"color: {p['accent']}; padding-right: 12px;")
        if getattr(self, "_blktype", None) is not None:
            self._blktype.setStyleSheet(f"color: {p['text_muted']}; padding-right: 4px;")
        if getattr(self, "_cmd_entry", None) is not None:
            self._cmd_entry.setStyleSheet(f"color: {p['accent']}; padding: 0 8px;")
        self._cell_mode.setToolTip(self._cell_mode.toolTip())
        # v3.44.8（TB-DWM）：同步原生标题栏亮/暗（窗口未显示时由 showEvent 兜底）
        self._sync_titlebar_dark()

    # v3.44.8（TB-DWM）：Windows 原生标题栏沉浸式暗色同步
    def _sync_titlebar_dark(self):
        """仅 win32 + 窗口已显示时，按当前主题族切换原生标题栏亮/暗。"""
        if sys.platform != "win32" or not self.isVisible():
            return
        try:
            hwnd = int(self.winId())
        except Exception:
            return
        _win_set_immersive_dark(hwnd, self._theme in _DARK_THEMES)

    def showEvent(self, event):
        """v3.44.8（TB-DWM）：窗口显示时（含首次）同步原生标题栏亮/暗。"""
        super().showEvent(event)
        self._sync_titlebar_dark()

    def _maybe_slash_bubble(self):
        """v3.40（UI-R7 R6 补偿②）：首次空白文档一次性气泡「试试输入 /」。

        一次性（QSettings 已读标记），3s 自动淡出（内核 showSlashBubble 内置）。"""
        if self._settings.value("ui/slashTipShown", False, type=bool):
            return
        self._settings.setValue("ui/slashTipShown", True)
        QTimer.singleShot(900, lambda: self._js_active(
            "window.showSlashBubble ? window.showSlashBubble() : null"))

    # ================= v3.41.0（UISTYLE-2 方案 A）：mac 风格统一工具栏 =================
    def _mac_source_menus(self):
        """MacTitleBar 胶囊菜单条数据源：menubar 既有 5 个 QMenu（同源，不复制）。"""
        out = []
        for act in self.menuBar().actions():
            m = act.menu()
            if m is not None:
                out.append((re.sub(r"\s*\(&.\)", "", str(act.text())), m))
        return out

    def _mac_toggle_max(self):
        """红绿灯绿钮 / 标题栏双击：最大化 ↔ 还原（全屏时先退出全屏）。"""
        if self.isFullScreen() or self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        tb = getattr(self, "_mac_title", None)
        if tb is not None:
            tb.set_doc_title(str(title).split(" — ")[0])
        rb = getattr(self, "_ribbon_bar", None)
        if rb is not None:
            rb.set_doc_title(str(title).split(" — ")[0])

    def nativeEvent(self, eventType, message):
        # v3.41.0：mac 无边框窗口（WM_NCCALCSIZE 去标题栏 + WM_NCHITTEST 拖拽/缩放）；
        # 非 mac 形态下直通默认处理，零影响
        r = mactitlebar.handle_native_event(self, message, self)
        if r is not None:
            return r
        return super().nativeEvent(eventType, message)

    def _force_mac_frame(self):
        """窗口形态标记变化后强制重算非客户区（SetWindowPos FRAMECHANGED，不闪烁）。"""
        try:
            mactitlebar.force_frame_recalc(int(self.winId()))
        except Exception:
            pass

    def _apply_layout_chrome(self):
        """v3.42.0：按风格 layout 标记做结构门控。

        - "mac"：macOS 统一工具栏形态（_apply_mac_chrome 全权处理）；
        - "hide_vtool"：隐藏左竖工具栏（notion/paper/ribbon/term——设计稿无竖列）；
        - "zen"：hide_vtool 基础上再隐藏菜单栏 + 收起侧栏（无界沉浸）；
        - ""（标准）：全部还原。工具栏可见性偏好（ui/toolbarVisible）不受门控影响，
          切回标准布局时按记忆还原；zen 收起的侧栏同样记忆还原。
        """
        layout = uistyles.active_layout()
        self._apply_mac_chrome(layout == "mac")
        if layout == "mac":
            return
        # v3.44.12（RIBBON-1）：PS01-RIBBON 结构化布局（chrome 全权处理菜单/工具栏/边框）
        self._apply_ribbon_chrome(layout == "ribbon")
        if layout == "ribbon":
            return
        if layout in ("hide_vtool", "zen"):
            if getattr(self, "_layout_vtool_was", None) is None:
                self._layout_vtool_was = self._tool_tb.isVisible()
            self._tool_tb.setVisible(False)
            # 偏好保持不变（persist=False），仅门控级隐藏；左缘展开钮不出现
            self._btn_tb_show.hide()
            # v3.44.27(REQ2)：极简 / 隐藏竖工具栏形态均保留菜单栏（顶栏始终可访问），
            # 不再依赖 zen hover 召回——该机制在 QWebEngineView 原生控件下鼠标事件不
            # 向上传递到主窗口过滤器，导致顶栏消失且无法召回。卸载可能存在的 zen hover 监听。
            self.menuBar().setVisible(True)
            if getattr(self, "_mac_frame_on", False):
                self._mac_frame_on = False
                self._force_mac_frame()
            if getattr(self, "_zen_autohide", False):
                self._zen_autohide = False
                self._zen_filter_installed = False
                self.removeEventFilter(self)
            if layout == "zen":
                # 仅收起侧栏（保持极简沉浸），菜单栏常驻可访问
                if getattr(self, "_zen_sidebar_was", None) is None:
                    self._zen_sidebar_was = self._sidebar.isVisible()
                if self._sidebar.isVisible():
                    self._sidebar.setVisible(False)
                    self._update_side_btn()
        else:
            self.menuBar().setVisible(True)
            # v3.44.9（ZEN-HOVER）：从 zen 退出到标准布局时卸掉顶部 hover 监听
            if getattr(self, "_zen_autohide", False):
                self._zen_autohide = False
                self._zen_filter_installed = False
                self.removeEventFilter(self)
            was = getattr(self, "_layout_vtool_was", None)
            if was is not None:
                self._layout_vtool_was = None
                self._tool_tb.setVisible(was)
                self._sync_toolbar_state(persist=False, vis=was)
            zs = getattr(self, "_zen_sidebar_was", None)
            if zs is not None:
                self._zen_sidebar_was = None
                if zs:
                    self._sidebar.setVisible(True)
                    self._update_side_btn()

    def _install_zen_autohide(self):
        """v3.44.9（ZEN-HOVER）：zen 顶部 hover 监听的安装入口。

        标记 _zen_autohide=True 并向自身安装事件过滤器（顶部 MouseMove 检测）。
        幂等：已安装（_zen_filter_installed）时不重复 install，避免重复派发。
        卸载在 _apply_layout_chrome 非 zen 分支完成。"""
        self._zen_autohide = True
        if getattr(self, "_zen_filter_installed", False):
            return
        try:
            self.installEventFilter(self)
            self._zen_filter_installed = True
        except Exception:
            self._zen_filter_installed = False

    def _style_patch_js(self):
        """v3.42.0：界面风格 editor_css → 独立 <style id=uiStylePatch> 注入脚本。

        独立 id（非 #app-style）：getExportHTML 只收集 app-style，风格纸张/窄栏
        观感属界面层，不随导出走。"""
        css = uistyles.editor_css(self._theme)
        return ("(function(){var s=document.getElementById('uiStylePatch');"
                "if(!s){s=document.createElement('style');s.id='uiStylePatch';"
                "document.head.appendChild(s);}s.textContent=" + js(css) + ";})()")

    def _apply_mac_chrome(self, on):
        """进入 / 退出 macOS 形态（PS01-MAC 设计稿）。

        - 统一工具栏（红绿灯 + ☰菜单条 + 工具钮 + 居中标题 + 右端视图状态区）
          装在 central widget 上方（包装容器懒创建一次）；
        - _vsz_corner 在菜单栏 ↔ 统一工具栏之间反_parent（模式/专注/打字机状态单一源不复制）；
        - 无边框不改窗口 flags（避免 re-show 闪烁），只切 nativeEvent 命中标记；
        - 退出时菜单栏 / 左工具栏 / corner / 无边框全部还原。

        v3.47（P0 跨平台）：无边框窗口是 Win32 专属实现（nativeEvent 拦截
        WM_NCCALCSIZE / WM_NCHITTEST）。非 Windows 平台强制关闭该形态，
        改用系统原生窗口（含原生标题栏 / 拖拽 / 缩放），避免无边框逻辑在
        macOS / Linux 上失效导致窗口无法拖拽。"""
        if platform.system() != "Windows":
            on = False
        tb = getattr(self, "_mac_title", None)
        if on:
            # v3.44.12（RIBBON-1）：从功能区形态切入 mac 时，先把主区取回 mac 包装
            self._unwrap_ribbon_for_mac()
            if tb is None:
                tb = mactitlebar.MacTitleBar(self)
                self._mac_title = tb
                split = self.centralWidget()
                wrap = QWidget(self)
                wrap.setObjectName("macWrap")
                wl = QVBoxLayout(wrap)
                wl.setContentsMargins(0, 0, 0, 0)
                wl.setSpacing(0)
                wl.addWidget(tb)
                wl.addWidget(split)
                self.setCentralWidget(wrap)
                self._mac_wrap = wrap
            tb.set_doc_title(str(self.windowTitle()).split(" — ")[0])
            tb.apply_palette(uistyles.merge_palette(self._theme))
            tb.show()
            if self._vsz_corner is not None and self._vsz_corner.parent() is not tb:
                self._vsz_corner.setParent(tb)
                tb.relayout_vsz()
            self._mac_prev_tb_vis = self._tool_tb.isVisible()
            self.menuBar().setVisible(False)
            self._tool_tb.setVisible(False)
            self._btn_tb_show.hide()
            if not self._mac_frame_on:
                self._mac_frame_on = True
                self._force_mac_frame()
        else:
            if tb is None:
                return
            if self._mac_frame_on:
                self._mac_frame_on = False
                self._force_mac_frame()
            tb.hide()
            if self._vsz_corner is not None and self._vsz_corner.parent() is not self.menuBar():
                self.menuBar().setCornerWidget(self._vsz_corner, Qt.TopRightCorner)
            self.menuBar().setVisible(True)
            self._tool_tb.setVisible(bool(getattr(self, "_mac_prev_tb_vis", True)))
            self._sync_toolbar_state(persist=False)

    # ================= v3.44.12（RIBBON-1）：PS01-RIBBON 结构化功能区 =================
    def _central_split(self):
        """真实主区控件（穿透 mac / ribbon 包装层）。"""
        cw = self.centralWidget()
        mac_wrap = getattr(self, "_mac_wrap", None)
        if mac_wrap is not None and cw is mac_wrap:
            lay = mac_wrap.layout()
            for i in range(lay.count()):
                wgt = lay.itemAt(i).widget()
                if wgt is not None and wgt is not getattr(self, "_mac_title", None):
                    return wgt
        rib_wrap = getattr(self, "_ribbon_wrap", None)
        if rib_wrap is not None and cw is rib_wrap:
            return getattr(self, "_ribbon_split", None) or cw
        return cw

    def _unwrap_ribbon_for_mac(self):
        """从功能区形态切入 mac：把主区 split 从 ribbon 包装取回 mac 包装。"""
        rib_wrap = getattr(self, "_ribbon_wrap", None)
        if rib_wrap is None or self.centralWidget() is not rib_wrap:
            return
        split = getattr(self, "_ribbon_split", None)
        if split is None:
            return
        rib_wrap.layout().removeWidget(split)
        mac_wrap = getattr(self, "_mac_wrap", None)
        if mac_wrap is not None:
            mac_wrap.layout().insertWidget(1, split)
            self.setCentralWidget(mac_wrap)
        else:
            # mac 包装尚未创建（本会话未进过 mac 形态）：直接还原 split 为 central
            self.setCentralWidget(split)

    def _apply_ribbon_chrome(self, on):
        """进入 / 退出 Office 功能区形态（PS01-RIBBON 设计稿，RIBBON-1）。

        - 标题栏 + 页签行 + 四页功能区装在 central widget 上方（包装容器懒创建一次）；
        - _vsz_corner 在菜单栏 ↔ 页签行之间反_parent（与 mac 形态同构，状态单一源）；
        - 无边框复用 mac 机制（_mac_frame_on 标记；mactitlebar 命中白名单已泛化）；
        - Ctrl+F1 / ▴ 折叠功能区内容（折叠后仅剩页签行）；
        - 退出时菜单栏 / 左工具栏 / corner / 无边框全部还原。"""
        bar = getattr(self, "_ribbon_bar", None)
        if on:
            if bar is None:
                bar = ribbonchrome.RibbonTitleBar(self)
                self._ribbon_bar = bar
            tabs = getattr(self, "_ribbon_tabs", None)
            if tabs is None:
                tabs = ribbonchrome.RibbonTabsRow(self)
                self._ribbon_tabs = tabs
                body = ribbonchrome.RibbonBody(self)
                self._ribbon_body = body
                tabs.tab_selected.connect(self._on_ribbon_tab)
                tabs.pinbtn.clicked.connect(self._toggle_ribbon_pin)
                # v3.44.27(REQ1)：默认「固定」（始终展开），状态由图钉钮明确反映
                self._ribbon_pinned = True
                self._ribbon_collapsed = False
                tabs.set_pin_state(True)
                # v3.44.27(REQ1)：收拢模式下，焦点离开功能区进入编辑区即自动收起
                app = QApplication.instance()
                if app is not None and not getattr(self, "_rib_focus_conn", False):
                    app.focusChanged.connect(self._on_focus_changed)
                    self._rib_focus_conn = True

                def _fire(name):
                    a = self._shortcut_acts.get(name)
                    if a is not None:
                        a.trigger()
                bar.qat_save.clicked.connect(lambda: _fire("保存"))
                bar.qat_undo.clicked.connect(lambda: _fire("撤销"))
                bar.qat_redo.clicked.connect(lambda: _fire("重做"))
                # Ctrl+F1 折叠（仅 ribbon 形态在位期间注册）
                self._rib_sc = ribbonchrome.QShortcut(
                    ribbonchrome.QKeySequence("Ctrl+F1"), self)
                self._rib_sc.activated.connect(self._toggle_ribbon_collapse)
            # 主区包装（穿透 mac 包装取回 split；容器懒建一次）
            split = self._central_split()
            wrap = getattr(self, "_ribbon_wrap", None)
            if wrap is None:
                wrap = QWidget(self)
                wrap.setObjectName("ribbonWrap")
                wl = QVBoxLayout(wrap)
                wl.setContentsMargins(0, 0, 0, 0)
                wl.setSpacing(0)
                wl.addWidget(bar)
                wl.addWidget(tabs)
                wl.addWidget(self._ribbon_body)
                self._ribbon_wrap = wrap
            self._ribbon_split = split
            rl = wrap.layout()
            for wgt in (bar, tabs, self._ribbon_body, split):
                if rl.indexOf(wgt) < 0:
                    rl.addWidget(wgt)
            if self.centralWidget() is not wrap:
                self.setCentralWidget(wrap)
            bar.set_doc_title(str(self.windowTitle()).split(" — ")[0])
            _rib_p = uistyles.merge_palette(self._theme)
            bar.apply_palette(_rib_p)
            bar.show()
            tabs.show()
            tabs.apply_palette(_rib_p)
            self._ribbon_body.apply_palette(_rib_p)
            self._ribbon_body.setVisible(
                not getattr(self, "_ribbon_collapsed", False))
            if self._vsz_corner is not None and \
                    self._vsz_corner.parent() is not tabs.right_zone:
                self._vsz_corner.setParent(tabs.right_zone)
            self._ribbon_prev_tb = self._tool_tb.isVisible()
            self.menuBar().setVisible(False)
            self._tool_tb.setVisible(False)
            self._btn_tb_show.hide()
            self._ribbon_body.sync_mode(self._mode)
            self._ribbon_body.sync_display()
            if not self._mac_frame_on:
                self._mac_frame_on = True
                self._force_mac_frame()
        else:
            if bar is None:
                return
            if self._mac_frame_on:
                self._mac_frame_on = False
                self._force_mac_frame()
            bar.hide()
            self._ribbon_tabs.hide()
            self._ribbon_body.hide()
            if getattr(self, "_rib_sc", None) is not None:
                self._rib_sc.setParent(None)
                self._rib_sc = None
            if self._vsz_corner is not None and \
                    self._vsz_corner.parent() is not self.menuBar():
                self.menuBar().setCornerWidget(self._vsz_corner, Qt.TopRightCorner)
            self.menuBar().setVisible(True)
            self._tool_tb.setVisible(bool(getattr(self, "_ribbon_prev_tb", True)))
            self._sync_toolbar_state(persist=False)

    def _toggle_ribbon_collapse(self):
        """Ctrl+F1 / ▴：手动折叠 / 展开功能区内容（折叠后仅剩页签行，编辑区最大化）。"""
        body = getattr(self, "_ribbon_body", None)
        if body is None or uistyles.active_layout() != "ribbon":
            return
        vis = not body.isVisible()
        body.setVisible(vis)
        self._ribbon_collapsed = not vis
        self.show_status(T("功能区已折叠（Ctrl+F1 还原）", "Ribbon collapsed (Ctrl+F1 to restore)") if not vis else "功能区已展开")

    def _on_ribbon_tab(self, pid):
        """页签切换：切页 + 外观页刷新勾选；收拢模式下点页签临时展开功能区。"""
        body = getattr(self, "_ribbon_body", None)
        if body is None:
            return
        order = ("home", "view", "look", "tools")
        try:
            body.setCurrentIndex(order.index(pid))
        except ValueError:
            pass
        if pid == "look":
            body.sync_look()
        # v3.44.27(REQ1)：收拢（自动隐藏）模式下，点页签即临时展开功能区
        if not getattr(self, "_ribbon_pinned", True) and not body.isVisible():
            body.setVisible(True)
            self._ribbon_collapsed = False

    def _toggle_ribbon_pin(self):
        """v3.44.27(REQ1)：固定 ↔ 收拢 双态切换（图钉钮，状态明确可感知）。

        - 固定（pinned=True）：功能区始终展开；
        - 收拢（pinned=False）：默认仅留页签行，点页签临时展开，点文档自动收起。
        """
        if uistyles.active_layout() != "ribbon":
            return
        self._ribbon_pinned = not getattr(self, "_ribbon_pinned", True)
        pinned = self._ribbon_pinned
        tabs = getattr(self, "_ribbon_tabs", None)
        body = getattr(self, "_ribbon_body", None)
        if tabs is not None:
            tabs.set_pin_state(pinned)
        if body is not None:
            body.setVisible(pinned)
            self._ribbon_collapsed = not pinned
        self.show_status(T("功能区已固定（始终展开）", "Ribbon pinned (always expanded)") if pinned
                         else "功能区已设为自动收拢（点页签临时展开，点文档自动收起）")

    def _is_descendant(self, child, ancestor):
        """child 是否为 ancestor 自身或其后裔控件。"""
        if child is None or ancestor is None:
            return False
        w = child
        while w is not None:
            if w is ancestor:
                return True
            w = w.parent()
        return False

    def _on_focus_changed(self, old, now):
        """v3.44.27(REQ1)：收拢模式下，焦点离开功能区进入编辑区时自动收起功能区。"""
        if getattr(self, "_ribbon_pinned", True):
            return   # 固定模式：永不自动收拢
        if uistyles.active_layout() != "ribbon":
            return
        body = getattr(self, "_ribbon_body", None)
        if body is None or not body.isVisible():
            return
        if now is None:
            return
        # 焦点落在功能区 chrome（标题栏 / 页签行 / 内容）内 → 不收拢
        for w in (self._ribbon_bar, self._ribbon_tabs, self._ribbon_body):
            if w is not None and self._is_descendant(now, w):
                return
        # 否则视为进入编辑区（或窗口外）→ 自动收起功能区
        body.setVisible(False)
        self._ribbon_collapsed = True

    def set_theme(self, name):
        """兼容旧调用：等价于 apply_theme。"""
        self.apply_theme(name)

    def apply_theme(self, name, persist=True):
        """全局换肤：Qt 界面（菜单/工具栏/状态栏/对话框/侧栏）+ 编辑器网页视图。"""
        if name not in styles.THEME_IDS:
            name = "light"
        self._theme = name
        # 1) Qt 层：全局 QSS + 侧栏 + 已打开的对话框
        #    v3.39.15（UISTYLE-1）：QSS 改由 uistyles 生成（当前主题调色板 + 界面风格覆盖，
        #    默认风格 ps01 不覆盖任何 token，外观与旧管线完全一致）
        QApplication.instance().setStyleSheet(uistyles.app_qss(name))
        self._sidebar.setStyleSheet(uistyles.sidebar_qss(name))
        if hasattr(self._sidebar, "set_tree_arrows"):
            self._sidebar.set_tree_arrows(name)   # v3.26：展开/收拢箭头随主题换色
        if hasattr(self._sidebar, "set_folder_theme"):
            self._sidebar.set_folder_theme(name)  # v3.44.2：文件夹图标随主题强调色
        if hasattr(self._sidebar, "set_outline_active_theme"):
            self._sidebar.set_outline_active_theme(name)  # v3.49.x（OUT-SYNC）：激活项背景随主题强调浅底动态更新
        # v3.38（TB-1）：左侧边缘「展开工具栏」按钮随主题换色（仅工具栏隐藏时可见）
        if getattr(self, "_btn_tb_show", None) is not None:
            p = uistyles.merge_palette(name)   # v3.39.15（UISTYLE-1）：随风格取色
            self._btn_tb_show.setStyleSheet(
                "QToolButton#tbExpand {{ background: {bg}; border: 1px solid {bd};"
                " border-radius: 9px; color: {ac}; font-size: 15px; font-weight: 800;"
                " padding: 0; }}"
                "QToolButton#tbExpand:hover {{ background: {acs}; color: {ac}; }}".format(
                    bg=p["bg_soft"], bd=p["border"], ac=p["accent"], acs=p["accent_soft"]))
        for dlg_attr in ("_find_dlg", "_sc_dlg", "_set_dlg", "_cmd_dlg", "_hist_dlg"):
            dlg = getattr(self, dlg_attr, None)
            if dlg is not None:
                dlg._apply_theme_qss(name)
        # v3.40（UI-R7）：菜单栏右端视图状态区 + 状态栏交互格随主题 / 风格调色
        self._apply_chrome_styles()
        # v3.44.5（DESIGN01）：标签栏选中指示条 accent 随主题同步
        try:
            self._tabbar.set_accent(uistyles.merge_palette(name).get("accent", "#0052d9"))
            self._tabbar.update()
        except Exception:
            pass
        # v3.41.0（UISTYLE-2）：mac 统一工具栏调色 + 结构形态（进入 / 退出，含启动恢复）
        self._apply_layout_chrome()  # v3.42.0：mac / hide_vtool / zen 统一布局门控
        # 2) Web 层：所有已加载的编辑器视图
        views = {"edit": self._view, "src": self._view_src, "prev": self._view_prev}
        for role, view in views.items():
            if view is not None and self._vstate[role]["loaded"]:
                self._js_view(view, f"window.setTheme({js(name)})")
        # v3.42.0（UISTYLE-3）：风格内容级 CSS（纸张/窄栏）随主题 / 风格刷新
        for role, view in views.items():
            if view is not None and self._vstate[role]["loaded"]:
                self._js_view(view, self._style_patch_js())
        # 3) 菜单勾选状态
        for tid, act in self._theme_acts.items():
            act.setChecked(tid == name)
        if persist:
            self._settings.setValue("theme", name)
        self.show_status(T(f"主题：{styles.theme_label(name)}", f"Theme: {styles.theme_label(name)}"))

    def set_uistyle(self, sid):
        """v3.39.15（UISTYLE-1）：切换界面风格（仅 Qt 层观感皮肤，编辑器主题不变）。

        - 非法 / 已删除的风格 ID 自动回退默认风格 ps01（uistyles.resolve）；
        - 持久化 QSettings.uiStyle，重启保持；
        - 重走 apply_theme 完成全局刷新（对话框沿用 _apply_theme_qss 通道）。
        """
        sid = uistyles.set_active(sid)
        self._uistyle = sid
        self._settings.setValue("uiStyle", sid)
        self.apply_theme(self._theme, persist=False)
        # v3.43.0：菜单名是纯净名（无编号 / 后缀），状态栏与菜单保持一致
        self.show_status(T(f"界面风格：{uistyles.menu_style_label(sid)}", f"UI style: {uistyles.menu_style_label(sid)}"))

    def set_zoom(self, factor):
        """编辑区字号缩放（对所有视图生效并持久化）。"""
        self._zoom = max(0.8, min(1.6, float(factor)))
        views = (self._view, self._view_src, self._view_prev)
        for v in views:
            if v is not None:
                v.setZoomFactor(self._zoom)
        self._settings.setValue("zoom", self._zoom)
        # v3.40（UI-R7）：状态栏缩放格同步
        cell = getattr(self, "_cell_zoom", None)
        if cell is not None:
            cell.setText(f"{int(round(self._zoom * 100))}%")
        self.show_status(T(f"编辑区缩放：{int(round(self._zoom * 100))}%", f"Editor zoom: {int(round(self._zoom * 100))}%"))

    def set_autosave(self, on):
        self._autosave = bool(on)
        self._settings.setValue("autosave", self._autosave)
        self.show_status(T("自动保存：开", "Auto-save: On") if self._autosave else "自动保存：关")

    def set_code_lang(self, lang):
        """设置代码块默认语言（插入代码块时预选），即时下发到编辑器并持久化。"""
        lang = str(lang or "C").strip() or "C"
        self._code_lang = lang
        self._settings.setValue("codeLang", lang)
        self._js_active(f"window.setDefaultCodeLang({js(lang)})")
        self.show_status(T(f"代码块默认语言：{lang}", f"Code block default language: {lang}"))

    def set_code_prefs(self, lnum=None, style=None):
        """v3.25：设置代码块行号显示 / 默认代码风格，即时下发并持久化。

        新插入 / 重新渲染的代码块默认取此配置；代码栏「风格」按钮可对单个
        代码块临时切换（会话内生效，不写入 Markdown）。"""
        if lnum is not None:
            self._code_lnum = bool(lnum)
            self._settings.setValue("codeLineNum", "1" if lnum else "0")
        if style:
            self._code_style = str(style)
            self._settings.setValue("codeStyle", self._code_style)
        self._js_active(
            f"window.setCodePrefs({{lnum: {str(self._code_lnum).lower()}, "
            f"style: {js(self._code_style)}}})")
        self.show_status(
            f"代码块：行号{'开' if self._code_lnum else '关'} · "
            f"风格 {self._code_style}")

    # ================= 侧栏显示设置 =================
    def set_outline_level(self, level):
        """设置大纲显示级别（1~6，默认 3），持久化并立即重建大纲。"""
        try:
            level = max(1, min(6, int(level)))
        except (TypeError, ValueError):
            return
        self._outline_level = level
        self._settings.setValue("outlineLevel", level)
        self._sidebar.set_outline_level(level)
        self.show_status(T(f"大纲显示级别：{level} 级", f"Outline display level: {level}"))

    def set_outline_words(self, on):
        """v3.31.2（#3）：大纲分节字数后缀显示开关，持久化并原地刷新后缀。"""
        self._outline_words = bool(on)
        self._settings.setValue("outlineWords", self._outline_words)
        self._sidebar.set_outline_words(self._outline_words)
        self.show_status(T("大纲分节字数：", "Outline section word count: ") + ("已显示" if self._outline_words else "已隐藏"))

    def set_outline_filter(self, level):
        """v3.43.0（OUT-LOOK）：大纲级别过滤（0=全部 / 1~3=只看该级及其祖先链）。

        与「大纲显示级别」（通用页，控制默认折叠深度）分工不同：过滤是「看哪些级」，
        显示级别是「默认展开到第几级」，两者可叠加生效。
        """
        try:
            level = max(0, min(3, int(level)))
        except (TypeError, ValueError):
            return
        self._outline_filter = level
        self._settings.setValue("ui/outlineFilter", level)
        self._sidebar.set_outline_filter(level)
        self.show_status(T("大纲过滤：", "Outline filter: ") + ("全部标题" if level == 0 else f"只看 H1–H{level}"))

    def set_startup_action(self, mode):
        """v3.38（OUT-5）/ v3.44（SESSION）：启动时行为 ——
        blank=欢迎页（默认）/ lastFile=恢复上次单个文件 /
        session=恢复上次完整会话（多标签 + 位置）/ folder=打开指定文件夹。下次启动生效。"""
        mode = str(mode or "blank")
        if mode not in ("blank", "lastFile", "session", "folder"):
            mode = "blank"
        self._startup_action = mode
        self._settings.setValue("startupAction", mode)

    def set_autosave_interval(self, sec):
        """v3.44（AUTOSAVE-INT）：自动保存节流间隔（秒），0=实时写盘（每次改动即写）。"""
        try:
            sec = max(0, int(sec))
        except (TypeError, ValueError):
            return
        self._autosave_interval = sec
        self._settings.setValue("autosaveInterval", sec)
        self._autosave_ts = time.time()   # 切换间隔后允许立即写一次

    def set_recent_max(self, n):
        """v3.44（RECENT-MAX）：最近文件保留条数（0=不保留）。"""
        try:
            n = max(0, min(50, int(n)))
        except (TypeError, ValueError):
            return
        self._recent_max = n
        self._settings.setValue("recentMax", n)
        self._trim_recent()   # 立即按新上限裁剪

    def last_sidebar_dir(self):
        """v3.38（FLP-1）：上次访问的侧栏目录（无则空串）。"""
        return str(self._settings.value("lastSidebarDir", "") or "")

    def last_open_dir(self):
        """v3.38（FLP-2）：最近一次成功打开文件所在目录（无则空串）。"""
        return str(self._settings.value("files/lastOpenDir", "") or "")

    def _remember_open_dir(self, path):
        """v3.38（FLP-2）：记录最近一次成功打开文件的所在目录并立即落盘，
        供文件列表默认定位（重启保留）。"""
        try:
            d = os.path.dirname(os.path.abspath(path))
            if d and os.path.isdir(d):
                self._settings.setValue("files/lastOpenDir", d)
                self._settings.sync()      # 立即落盘，防异常退出丢记录
        except Exception:      # noqa: BLE001 —— 记录失败不影响打开流程
            pass

    def file_list_default_dir(self):
        """v3.38（FLP-1）：文件列表「默认打开路径」的**原始配置值**（未解析，空 = 未配置）。

        字段：QSettings `files/defaultDir`；默认值 = `config.FILE_LIST_DEFAULT_DIR`（""）。
        """
        return str(self._settings.value("files/defaultDir", FILE_LIST_DEFAULT_DIR) or "")

    def set_file_list_default_dir(self, text):
        """v3.38（FLP-1）：设置文件列表默认打开路径（留空 = 不启用），并即时定位一次。"""
        self._file_list_default_dir = str(text or "").strip()
        self._settings.setValue("files/defaultDir", self._file_list_default_dir)
        self._sidebar.apply_default_dir(toast=True)

    def _remember_last_session(self):
        """v3.38（OUT-5）：记录最近文档与侧栏目录，供「启动时」恢复上次会话。"""
        try:
            if self.file_path and os.path.isfile(self.file_path):
                self._settings.setValue("lastFile", self.file_path)
            sdir = self._sidebar.current_dir()
            if sdir and os.path.isdir(sdir):
                self._settings.setValue("lastSidebarDir", sdir)
        except Exception:      # noqa: BLE001
            pass

    def _restore_session(self):
        """v3.44（SESSION）：恢复上次完整会话（多标签 + 当前标签 + 侧栏位置）。

        返回 True 表示成功恢复至少 1 个有效文档，False 表示无可恢复内容。
        """
        try:
            paths = self._settings.value("sessionDocs", []) or []
            if isinstance(paths, str):
                paths = [paths]
            paths = [p for p in paths if p and os.path.isfile(p)]
            if not paths:
                return False
            for p in paths:
                self._add_doc(path=p, text=self._read_file(p))
            cur = int(self._settings.value("sessionCur", 0) or 0)
            cur = max(0, min(cur, len(paths) - 1))
            if cur != self._cur:
                self._tabbar.setCurrentIndex(cur)
            # 侧栏位置恢复（优先于文件目录）
            _sd = str(self._settings.value("lastSidebarDir", "") or "")
            if _sd and os.path.isdir(_sd):
                self._sidebar.set_root(_sd)
            self._sidebar._initial_restored = True
            return True
        except Exception:      # noqa: BLE001
            return False

    def save_session(self):
        """v3.44（SESSION）：记录当前多标签会话（路径列表 + 当前索引），供下次恢复。"""
        try:
            paths = [d.get("path") for d in self._docs
                     if d.get("path") and os.path.isfile(d.get("path"))]
            if paths:
                self._settings.setValue("sessionDocs", paths)
                cur = self._cur if 0 <= self._cur < len(self._docs) else 0
                cur_doc = self._docs[cur] if 0 <= cur < len(self._docs) else None
                cur_path = cur_doc.get("path") if cur_doc else None
                self._settings.setValue(
                    "sessionCur", paths.index(cur_path) if cur_path in paths else 0)
            else:
                self._settings.remove("sessionDocs")
                self._settings.remove("sessionCur")
        except Exception:      # noqa: BLE001
            pass

    def set_para_indent(self, n):
        """v3.31.2（#8）：段落首行缩进格数（0~4），持久化并全视图即时生效。"""
        try:
            n = max(0, min(4, int(n)))
        except (TypeError, ValueError):
            return
        self._para_indent = n
        self._settings.setValue("paraIndent", n)
        for v in (self._view, self._view_src, self._view_prev):
            if v is not None:
                self._js_view(v, f"window.setParaIndent({n})")
        self.show_status(T(f"段首缩进：{n} 格", f"Paragraph indent: {n}") if n else "段首缩进：无")

    def set_h1_center(self, on):
        """v3.31.2（#9）：标题 1 全局居中，持久化并全视图即时生效。"""
        self._h1_center = bool(on)
        self._settings.setValue("h1Center", self._h1_center)
        s = str(self._h1_center).lower()
        for v in (self._view, self._view_src, self._view_prev):
            if v is not None:
                self._js_view(v, f"window.setH1Center({s})")
        self.show_status(T("标题 1 居中：", "Heading 1 centered: ") + ("开" if self._h1_center else "关"))

    def set_file_list_mode(self, mode):
        """设置文件列表显示模式：current=跟随当前文档（默认）/ blank=空白项。"""
        mode = "blank" if str(mode) == "blank" else "current"
        if mode == getattr(self, "_file_list_mode", "current") and \
                self._sidebar._file_mode == mode:
            return
        self._file_list_mode = mode
        self._settings.setValue("fileListMode", mode)
        self._sidebar.set_file_mode(mode)
        self.show_status(T("文件列表：空白项", "File list: blank item") if mode == "blank" else "文件列表：跟随当前文档")

    # ================= 斜杠（/）菜单配置 =================
    def _slash_cfg(self):
        """把当前菜单配置整理为下发给编辑器的 dict。"""
        order = [x for x in self._slash_order if x in SLASH_IDS] or list(SLASH_ORDER_DEFAULT)
        return {"order": order, "def": self._slash_def, "sub": dict(self._slash_sub)}

    def set_slash_menu_config(self, order, def_id, sub):
        """设置斜杠菜单：一级顺序 / 默认项 / 二级默认项，即时生效并持久化。"""
        # 缺省项按默认相对位置补齐（持久化完整顺序），不覆盖用户排序
        ids = merge_slash_order(order)
        self._slash_order = ids
        self._slash_def = def_id if def_id in ids else ids[0]
        cleaned = {}
        for key, dft in SLASH_SUB_DEFAULTS.items():
            try:
                cleaned[key] = max(0, int(sub.get(key, dft)))
            except (TypeError, ValueError):
                cleaned[key] = dft
        self._slash_sub = cleaned
        self._settings.setValue("slashMenuOrder", ",".join(ids))
        self._settings.setValue("slashMenuDef", self._slash_def)
        self._settings.setValue("slashSubHeading", cleaned["heading"])
        self._settings.setValue("slashSubList", cleaned["list"])
        self._settings.setValue("slashSubChart", cleaned["chart"])
        self._settings.setValue("slashSubMath", cleaned["math"])
        self._js_active(f"window.setSlashMenuConfig({js(json.dumps(self._slash_cfg()))})")
        self.show_status(T("斜杠菜单设置已保存", "Slash menu settings saved"))

    # ================= v3.32.2（TPL-C）自定义模板 =================
    # v3.36（TPL-E）：模板体系统一 —— 内置模板也落 templates.json，与自建模板
    # 同等管理（/ 菜单「模板」二级的内容即这份列表）
    def _tpl_entry(self, name, content, ic=""):
        """构造一条模板记录（ic 为空时不写该键，保持与旧数据的字典形态一致）。"""
        it = {"name": name, "content": content}
        ic = normalize_template_icon(ic)
        if ic:
            it["ic"] = ic
        return it

    def _templates_from_data(self, data):
        """templates.json 内容 → (模板列表, 结构版本号)。

        v2 = {"v": 2, "templates": [...]}；v1 = 早期纯数组 [{name, content}]；
        0 = 缺失 / 损坏（按首次运行处理）。
        """
        if isinstance(data, dict):
            raw = data.get("templates")
            try:
                ver = int(data.get("v", 0) or 0)
            except (TypeError, ValueError):
                ver = 0
        elif isinstance(data, list):
            raw, ver = data, 1
        else:
            raw, ver = [], 0
        items = []
        for t in raw or []:
            if not isinstance(t, dict):
                continue
            name = normalize_template_name(t.get("name", ""))
            content = str(t.get("content", ""))
            if name and content.strip():
                items.append(self._tpl_entry(name, content, t.get("ic", "")))
        return items, ver

    def _merge_builtin_templates(self, items):
        """并入内置模板：同名保留用户版本（位置不动），缺失的按内置顺序补在末尾。"""
        have = set(t.get("name") for t in items or [])
        out = [dict(t) for t in items or []]
        for b in BUILTIN_TEMPLATES:
            if b["name"] in have:
                continue
            out.append(self._tpl_entry(b["name"], b["content"], b.get("ic", "")))
        return out

    def _reorder_builtin_templates(self, items):
        """v3.38（TPL-F）：内置模板重排到默认顺序（自建模板保持相对顺序排其后）。

        仅在结构版本 < 3 的一次性迁移中执行 —— 此后用户在设置页调整的顺序
        落在 templates.json（ver=3）里，不会再被改动。"""
        rank = {b["name"]: i for i, b in enumerate(BUILTIN_TEMPLATES)}
        bi = sorted((t for t in items if t.get("name") in rank),
                    key=lambda t: rank[t["name"]])
        us = [t for t in items if t.get("name") not in rank]
        return bi + us

    def _write_template_file(self, templates):
        """按 v2 结构写盘（"v" 同时是「内置模板已并入」的迁移标记）。"""
        try:
            os.makedirs(USER_DATA_DIR, exist_ok=True)
            with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"v": TPL_FILE_VERSION, "templates": templates}, f,
                          ensure_ascii=False, indent=2)
            return True
        except OSError as e:
            self.show_status(T(f"模板保存失败：{e}", f"Template save failed: {e}"))
            return False

    def _load_custom_templates(self):
        """读取模板列表（templates.json）。

        v3.36（TPL-E）：内置模板并入统一列表 ——
          · 文件缺失 / 损坏 → 以内置模板初始化（首次运行）；
          · 旧格式（v1 纯数组）→ 合并缺失的内置模板后写回 v2（一次性迁移，
            用户既有模板保持原顺序，内置补在末尾）；
          · v2 → v3：内置模板重排为默认顺序（TPL-F，一次性迁移；自建模板
            保持相对顺序排其后），写回 v3；
          · 已是 v3 → 原样返回。
        名称统一过 normalize_template_name —— 手改过 json 或历史遗留的超长名称
        在这里被收回到显示上限，菜单与列表展示始终一致。
        """
        data = None
        try:
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = None
        items, ver = self._templates_from_data(data)
        if ver >= TPL_FILE_VERSION:
            return items
        merged = self._merge_builtin_templates(items)
        merged = self._reorder_builtin_templates(merged)   # v3.38（TPL-F）
        self._write_template_file(merged)
        return merged

    def _custom_templates_js(self):
        """模板列表序列化为下发参数（json 字符串字面量）。"""
        return js(json.dumps(self._custom_templates, ensure_ascii=False))

    def _sync_custom_templates(self, view=None):
        """把自定义模板下发给编辑器（缺省 = 当前活跃视图）。"""
        code = f"window.setCustomTemplates({self._custom_templates_js()})"
        if view is not None:
            self._js_view(view, code)
        else:
            self._js_active(code)

    def save_custom_templates(self, templates):
        """保存模板列表（模板设置页 / 设为模板文件共用）：写盘并即时下发。

        返回 True 表示已写盘并下发；False 表示写盘失败（调用方可据此决定是否再提示）。
        """
        cleaned, seen = [], set()
        for t in templates or []:
            name = normalize_template_name((t or {}).get("name", ""))
            content = str((t or {}).get("content", ""))
            if name and content.strip() and name not in seen:
                seen.add(name)
                cleaned.append(self._tpl_entry(name, content, (t or {}).get("ic", "")))
        self._custom_templates = cleaned
        if not self._write_template_file(cleaned):
            return False
        self._sync_custom_templates()
        self.show_status(T(f"模板已保存（{len(cleaned)} 个）", f"Templates saved ({len(cleaned)})"))
        return True

    def make_template_from_file(self, path):
        """v3.35（TPL-D）：把文件列表里的某个文档收编为自定义模板。

        流程：读磁盘内容（体积 / 空内容 / 编码兜底）→ 弹输入框填名称（输入层硬限
        TPL_NAME_MAX 字）→ 归一化 + 重名自动编号 → 追加到列表末尾（= 菜单末尾）
        → 写 templates.json 并即时下发编辑器。
        """
        p = str(path or "")
        try:
            size = os.path.getsize(p)
        except OSError as e:
            QMessageBox.warning(self, T("设为模板", "Set as Template"), T(f"无法读取该文件：{e}", f"Failed to read the file: {e}"))
            return
        if size > TPL_MAX_BYTES:
            QMessageBox.warning(
                self, "设为模板",
                f"文件过大（{size / 1024:.0f} KB）。\n"
                f"模板内容上限为 {TPL_MAX_BYTES // 1024} KB，请先精简后再试。")
            return
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            QMessageBox.warning(self, T("设为模板", "Set as Template"), T(f"无法读取该文件：{e}", f"Failed to read the file: {e}"))
            return
        if not content.strip():
            QMessageBox.warning(self, T("设为模板", "Set as Template"), T("该文件内容为空，无法作为模板。", "The file is empty and cannot be used as a template."))
            return

        base = os.path.splitext(os.path.basename(p))[0]
        default = normalize_template_name(base) or "新模板"
        label = f"模板名称（最多 {TPL_NAME_MAX} 字，将显示在 / 菜单与悬浮模板菜单中）："
        if (os.path.abspath(p) == os.path.abspath(self.file_path or "")
                and getattr(self, "_dirty", False)):
            label += "\n注意：该文件有未保存的修改，模板内容取磁盘上的版本（可先 Ctrl+S）。"
        dlg = QInputDialog(self)
        dlg.setWindowTitle(T("设为模板", "Set as Template"))
        dlg.setLabelText(label)
        dlg.setTextValue(default)
        le = dlg.findChild(QLineEdit)
        if le is not None:
            le.setMaxLength(TPL_NAME_MAX)   # 输入层硬限：手动输入 / 粘贴超长都会被截住
            le.selectAll()
        if dlg.exec() != QDialog.Accepted:
            return

        name = normalize_template_name(dlg.textValue())
        if not name:
            self.show_status(T("模板名称为空，未创建", "Template name empty; not created"))
            return
        renamed = unique_template_name(name, [t.get("name") for t in self._custom_templates])
        self._custom_templates.append({"name": renamed, "content": content})
        if self.save_custom_templates(self._custom_templates):
            self.show_status(T(f"已设为模板：{renamed}", f"Set as template: {renamed}") + ("（名称重复，已自动编号）" if renamed != name else ""))
        else:
            self._custom_templates.pop()   # 落盘失败：撤销内存追加，避免与磁盘不一致

    def open_template_manager(self):
        """打开「系统设置 → 模板」页。

        v3.36（TPL-E）：模板管理从独立对话框提升为设置面板的一级页（与外观 /
        编辑器 / 通用同级），这里保留入口便于侧栏 / 菜单 / 命令面板复用。
        """
        self.show_settings("模板")

    def show_settings(self, page=None):
        """打开系统设置；page 给定时定位到该页（如 "模板"）。"""
        if not hasattr(self, "_set_dlg"):
            self._set_dlg = SettingsDialog(self)
        if page:
            self._set_dlg.select_page(page)
        self._set_dlg.show()
        self._set_dlg.raise_()

    # ---- 查找替换 ----
    def show_find(self, with_replace):
        if not hasattr(self, "_find_dlg"):
            self._find_dlg = FindDialog(self)
        self._find_dlg.show_replace(with_replace)
        self._find_dlg.show()
        self._find_dlg.raise_()
        self._find_dlg.focus_find()

    # ================= v3.49.1（OUT-SYNC）大纲当前内容高亮 =================
    def _active_reading_view(self):
        """返回「正在被阅读」的视图：双栏取预览，单栏取主视图。"""
        if self._dual and self._view_prev is not None:
            return self._view_prev
        return self._view

    def _sync_outline_active(self):
        """轮询当前阅读视图，取视口顶部的标题块序号，驱动大纲「当前内容」高亮。"""
        view = self._active_reading_view()
        if view is None:
            return
        self._js_view(view, "window.getActiveHeading()", self._on_active_heading)

    def _on_active_heading(self, res):
        try:
            idx = int(res)
        except (TypeError, ValueError):
            return
        if self._sidebar is not None:
            self._sidebar.set_outline_active(idx)

    def jump_to_heading(self, index, text=None):
        """v3.38（OUT-4）：text = 大纲缓存标题文本，JS 侧先校验再跳（过期自动重查）。
        v3.49.1（OUT-SYNC）：按当前视图模式选择跳转函数 —— 源码态用 gotoHeadingSrc，
        渲染 / 双栏预览态用 gotoHeading，修复「源码 / 双栏模式点击大纲不跳转」。"""
        # v3.45.8（REQ3#9）：页内锚点跳转记入跳转历史
        self._nav_ensure_seed()
        self._nav_arrive(self.file_path or "", delay=450)
        suffix = f", {js(text)}" if text else ""
        if self._mode == "dual" and self._view_src is not None:
            self._js_view(self._view_src, f"window.gotoHeadingSrc({index}{suffix})")
            self._js_view(self._view_prev, f"window.gotoHeading({index}{suffix})")
        elif self._mode == "src":
            self._js_view(self._view, f"window.gotoHeadingSrc({index}{suffix})")
        else:
            self._js_view(self._view, f"window.gotoHeading({index}{suffix})")
        # v3.49.1（OUT-SYNC）：手动跳转后短暂抑制双栏滚动同步，避免被程序性回拉覆盖
        self._sync_manual_ts = time.monotonic()

    # ================= 拖拽 =================
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        # v3.30.10（IMG-1）：拖入多图时全部插入（原先只插第一张就 break），
        # 并给数量提示；拖入 .md 仍只打开第一个
        img_cnt = 0
        opened = False
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if not opened and p.lower().endswith(MD_EXTS):
                self.open_file(p)
                opened = True
                continue
            if p.lower().endswith(IMG_EXTS):
                self._insert_image_file(p)
                img_cnt += 1
        if img_cnt > 1:
            self.show_status(T(f"已插入 {img_cnt} 张图片", f"Inserted {img_cnt} images"))

    # ---------- v3.48.35（DROP-MD）：应用级 .md 拖放 ----------
    def _install_app_drop_filter(self):
        """把 .md 拖放提升到应用级，任何子控件都吞不掉。

        Qt 的拖放目标 = 光标下「接受 drop」的最近控件：QLineEdit / 大纲树 /
        书签树 / AI 输入框等都自带 drop 实现，会先消费掉事件，主窗口的
        dragEnterEvent/dropEvent 根本收不到（用户实测「拖进来没反应」）。
        应用级过滤器在目标控件之前执行，因此能稳定截获 URL 拖放。
        幂等：重复调用只装一次。
        """
        if getattr(self, "_app_drop_installed", False):
            return
        app = QApplication.instance()
        if app is None:          # 无 QApplication（单测导入）时静默跳过
            return
        app.installEventFilter(self)
        self._app_drop_installed = True

    @staticmethod
    def _md_drop_path(ev):
        """拖放载荷里的第一个本地 .md 绝对路径（没有则空串）。"""
        md = ev.mimeData()
        if md is None or not md.hasUrls():
            return ""
        for url in md.urls():
            p = url.toLocalFile()
            if p and p.lower().endswith(MD_EXTS) and os.path.isfile(p):
                return p
        return ""

    # QWebEngineView 的渲染子控件会吞掉 drop 事件，需要事件过滤器
    def _install_drop_filter(self):
        for v in (self._view, self._view_src, self._view_prev):
            if v is None:
                continue
            fp = v.focusProxy()
            if fp:
                fp.installEventFilter(self)
            v.setAcceptDrops(True)

    def eventFilter(self, obj, ev):
        # v3.48.35（DROP-MD）：应用级 .md 拖放 —— 先于目标控件处理，
        # 拖到任何位置（编辑器 / 文件列表 / 大纲 / 输入框）都能打开。
        # 模态对话框期间不接管（避免弹窗未关就切文档）；不含 .md 的
        # 载荷（图片等）直接放行，交给原有 dragEnterEvent/dropEvent。
        if ev.type() in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop):
            if QApplication.activeModalWidget() is None:
                _md_p = self._md_drop_path(ev)
                if _md_p:
                    ev.acceptProposedAction()   # 必须 accept，否则 Qt 不投递 Drop
                    if ev.type() == QEvent.Drop:
                        self.open_file(_md_p)
                        self.show_status(T('已打开拖入的文档：%s', 'Opened dragged-in document: %s')
                                         % os.path.basename(_md_p))
                    return True
        # v3.44.9（ZEN-HOVER）：极简（zen）模式下菜单栏默认隐藏；鼠标移到窗口顶部
        # （标题栏下方客户区顶部阈值内）时显示，离开后自动隐藏（滞回 28/40px 防抖，
        # 弹出菜单期间不隐藏）。全局事件过滤器仅在 zen 模式安装（见 _apply_layout_chrome）。
        if getattr(self, "_zen_autohide", False) and ev.type() == QEvent.MouseMove:
            mb = self.menuBar()
            gp = ev.globalPosition().toPoint()
            wr = self.geometry()
            if wr.contains(gp):
                if gp.y() <= wr.y() + 28:
                    if not mb.isVisible():
                        mb.setVisible(True)
                elif gp.y() > wr.y() + 40 and mb.isVisible() \
                        and QApplication.activePopupWidget() is None:
                    mb.setVisible(False)
        # v3.38（TAB-5）：标签栏鼠标手势 —— 中键点击标签即关闭 / 双击标签即关闭 /
        # 双击空白处新建标签（Notepad++ 与浏览器对标）
        if obj is self._tabbar:
            if ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.MiddleButton:
                i = self._tabbar.tabAt(ev.position().toPoint())
                if i >= 0:
                    self._close_tab(i)
                    return True
            elif (ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton
                  and ev.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                # v3.38（TAB-B）：Ctrl+单击增减选中 / Shift+单击区间选中（消费事件
                # 阻止 QTabBar 内部切标签；固定标签不参与多选）
                i = self._tabbar.tabAt(ev.position().toPoint())
                if i >= 0 and not self._docs[i].get("pinned"):
                    if ev.modifiers() & Qt.ControlModifier:
                        if i in self._tab_multi:
                            self._tab_multi.discard(i)   # 取消选中：锚点保持不变
                        else:
                            self._tab_multi.add(i)
                            self._multi_anchor = i
                    else:   # Shift：锚点（上次 Ctrl 单击，缺省当前标签）到本标签的区间
                        a = self._multi_anchor if self._multi_anchor >= 0 else self._cur
                        lo, hi = sorted((a, i))
                        self._tab_multi = {k for k in range(lo, hi + 1)
                                           if not self._docs[k].get("pinned")}
                    self._update_multi_highlight()
                    self.show_status(
                        f"已选中 {len(self._tab_multi)} 个标签页（Ctrl+单击增减，Shift+单击区间，右键可批量关闭）")
                return True
            elif (ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton):
                # 普通左键单击：清多选（正常切标签路径不受影响）。
                # 注意右键**不能**在这里清 —— 右键命中选中集时要保持多选弹批量关闭菜单
                if self._tab_multi:
                    self._tab_multi.clear()
                    self._multi_anchor = -1
                    self._update_multi_highlight()
            elif ev.type() == QEvent.MouseButtonDblClick:
                i = self._tabbar.tabAt(ev.position().toPoint())
                if i >= 0:
                    self._close_tab(i)
                else:
                    self.new_file()
                return True
        # 状态栏「字数」点击 → 统计详情
        if obj is getattr(self, "_count", None) and ev.type() == QEvent.MouseButtonPress:
            self._show_stats_detail()
            return True
        if ev.type() == QEvent.DragEnter and ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            return True
        if ev.type() in (QEvent.DragMove, QEvent.DragLeave):
            return True
        if ev.type() == QEvent.Drop:
            opened = False
            for url in ev.mimeData().urls():
                p = url.toLocalFile()
                if p.lower().endswith(MD_EXTS):
                    self.open_file(p)
                    opened = True
                    break
                if p.lower().endswith(IMG_EXTS):
                    self._insert_image_file(p)
                    opened = True
                    break
            if opened:
                return True
        return super().eventFilter(obj, ev)

    # ================= 右键菜单 =================
    def _show_ctx_menu(self, view, pos):
        """Typora 式中文右键菜单（预览侧只读，无剪切/粘贴）。"""
        page = view.page()
        readonly = view is self._view_prev
        menu = QMenu(self)
        # v3.48.3（F3-b）：「AI优化」子菜单置顶 —— 右键选中文字后可直接发起
        # 预设 AI 操作（润色/精简/扩写/纠错/翻译/改语气/选中）。注意：菜单构造
        # 期间**不**同步阻塞等待 runJavaScript（嵌套事件循环易与右键上下文菜单
        # 事件死锁，导致右键菜单整片不弹出）；点击子菜单项时**实时**取回选区文本。
        if not readonly:
            # v3.48.36（AI-MENUS）：菜单项可在 系统设置 → AI 菜单 自定义
            from ai_pane import ai_menu_items
            ai_menu = menu.addMenu(T("AI优化", "AI Optimize"))
            for _it in ai_menu_items(self._settings, "ctx"):
                ai_menu.addAction(
                    _it["label"],
                    lambda k=_it["key"], pr=_it["prompt"]:
                    self._ai_ctx_action(k, prompt=pr))
            # v3.48.31（MENU-AI）：「整篇优化」子菜单已从正文选区右键移除 ——
            # 选区右键语义是「对所选文字操作」，整篇级入口迁到文件列表右键
            # 「AI优化」（见 _ai_doc_action_for_path）。
            menu.addSeparator()
        if not readonly:
            menu.addAction(T("撤销", "Undo"), lambda: page.triggerAction(QWebEnginePage.Undo))
            menu.addAction(T("重做", "Redo"), lambda: page.triggerAction(QWebEnginePage.Redo))
            menu.addSeparator()
            menu.addAction(T("剪切", "Cut"), lambda: page.triggerAction(QWebEnginePage.Cut))
        menu.addAction(T("复制", "Copy"), lambda: page.triggerAction(QWebEnginePage.Copy))
        if not readonly:
            menu.addAction(T("粘贴", "Paste"), lambda: page.triggerAction(QWebEnginePage.Paste))
        menu.addSeparator()
        menu.addAction(T("全选", "Select All"), lambda: page.triggerAction(QWebEnginePage.SelectAll))
        menu.exec(view.mapToGlobal(pos))

    # ================= 退出 =================
    def closeEvent(self, e):
        if self._quitting:
            e.accept()
            return
        # 自动保存机制下，有路径的文档内容已实时落盘；未命名文档询问保存
        need_ask = False
        if self._cur >= 0 and self._cur < len(self._docs):
            cur_doc = self._docs[self._cur]
            if not cur_doc.get("path") and (cur_doc.get("content") or "").strip():
                need_ask = True
        if not need_ask:
            self._remember_last_session()   # v3.38（OUT-5）
            self.save_session()             # v3.44（SESSION）
            self._save_book_progress()       # v3.45.7（BOOK-READ-1）
            self._quitting = True
            e.accept()
            return
        btn = QMessageBox.question(
            self, "未保存的更改",
            "当前未命名文档尚未保存到文件，退出前是否保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if btn == QMessageBox.Cancel:
            e.ignore()
            return
        if btn == QMessageBox.Discard and 0 <= self._cur < len(self._docs):
            self._remove_draft(self._docs[self._cur])   # v3.32（P0-1）：明确丢弃 → 删草稿
        if btn == QMessageBox.Save:
            from PySide6.QtCore import QEventLoop
            res = {}
            loop = QEventLoop()

            def cb(md):
                res["md"] = md
                loop.quit()

            self._js_active("window.getMarkdown()", cb)
            loop.exec()
            md = res.get("md")
            if md is not None:
                if not self.file_path:
                    path, _ = QFileDialog.getSaveFileName(
                        self, "保存 Markdown 文件",
                        self._dlg_start("save", "未命名.md"), "Markdown 文件 (*.md)")
                    if not path:
                        e.ignore()
                        return
                    self._remember_dir("save", path)
                    self.file_path = os.path.abspath(path)
                self._write_text(self.file_path, md)   # v3.29d（B2）
        self._remember_last_session()   # v3.38（OUT-5）
        self.save_session()             # v3.44（SESSION）
        self._quitting = True
        e.accept()


# ================= v3.46（SoloMD P1）：AI 助手桥接（模块级，供主窗口实例化） =================
class AIBridge(QObject):
    """把 AI 面板需要的编辑器操作转接到主窗口（runJavaScript）。"""

    def __init__(self, mw):
        super().__init__()
        self._mw = mw

    def settings(self):
        return self._mw._settings

    def get_selection(self, callback):
        self._mw._js_active('window.aiSelText()',
                            lambda v: callback(v if isinstance(v, str) else ''))

    # ---- v3.48.33（AI-ANCHOR）：片段替换「位置锚点」 ----
    def _doc_identity(self):
        """当前活动文档标识 (index, path)：识别 AI 往返期间是否切了文档。"""
        mw = self._mw
        try:
            cur = int(mw._cur)
        except (AttributeError, TypeError, ValueError):
            return -1, ""
        try:
            doc = mw._docs[cur] if 0 <= cur < len(mw._docs) else {}
            return cur, str(doc.get("path") or "")
        except (AttributeError, IndexError, TypeError):
            return cur, ""

    def get_fragment_anchor(self, callback):
        """生成时记录「原文 + 位置」，供稍后精确写回。

        JS 侧 window.aiSelSnapshot() 返回 {ok, mode, bi/bj, s/e, text,
        blkA/blkB, blkCount, docGen}；这里补上文档标识（标签页下标 + 路径），
        回调始终收到 dict（失败为 {} 或 {"ok": False, ...}），不抛异常。"""
        def _cb(v):
            anchor = {}
            if isinstance(v, str) and v.strip():
                try:
                    import json as _json
                    parsed = _json.loads(v)
                    if isinstance(parsed, dict):
                        anchor = parsed
                except ValueError:
                    anchor = {}
            idx, path = self._doc_identity()
            anchor.setdefault("docIndex", idx)
            anchor.setdefault("docPath", path)
            if callback:
                callback(anchor)

        self._mw._js_active("window.aiSelSnapshot()", _cb)

    def replace_at_anchor(self, text, anchor, callback=None):
        """按生成时记录的位置精确写回；不做全文重新定位。

        callback(ok, code, detail)：code 为 JS 错误码
        （no-anchor / mode-changed / doc-changed / block-moved /
         block-changed / text-mismatch / stale-dom / bad-offset /
         insert-failed / empty），detail 为诊断信息 dict。"""
        if not isinstance(anchor, dict) or not anchor.get("v"):
            if callback:
                callback(False, "no-anchor", {"reason": "empty-anchor"})
            return

        # 文档身份前置校验：换标签页 / 换文件时不必再进 JS
        idx, path = self._doc_identity()
        a_path = str(anchor.get("docPath") or "")
        a_idx = anchor.get("docIndex")
        if a_path and path and a_path != path:
            if callback:
                callback(False, "doc-changed",
                         {"want": a_path, "now": path})
            return
        if (not a_path and not path and a_idx is not None
                and int(a_idx) != idx):
            if callback:
                callback(False, "doc-changed",
                         {"want": a_idx, "now": idx})
            return

        def _cb(v):
            ok, code = False, "unknown"
            info = {}
            if isinstance(v, str) and v.strip():
                try:
                    import json as _json
                    d = _json.loads(v)
                    if isinstance(d, dict):
                        ok = bool(d.get("ok"))
                        code = str(d.get("code") or d.get("err")
                                   or ("ok" if ok else "unknown"))
                        info = d
                except ValueError:
                    code = "bad-json"
            if callback:
                callback(ok, code, info)

        try:
            import json as _json
            payload = _json.dumps(anchor, ensure_ascii=False)
        except (TypeError, ValueError):
            if callback:
                callback(False, "no-anchor", {"reason": "unserializable"})
            return
        self._mw._js_active(
            "window.aiReplaceAnchor(" + js(payload) + ", " + js(text) + ")", _cb)

    def replace_selection(self, text, callback=None, orig_text=""):
        """v3.48.3（AI-FIX）：aiReplaceSel 返回 JSON {ok, err, hosts, recovered}。
        v3.48.5（AI-REDESIGN）：带 orig_text（发起改写时的原文快照）—— JS 侧
        预检当前选区文本是否仍一致（AI 往返期间原文被改 → stale-selection）；
        callback(ok, err)。"""
        def _cb(v):
            ok, err = False, "unknown"
            if isinstance(v, str):
                try:
                    import json as _json
                    d = _json.loads(v)
                    if isinstance(d, dict):
                        ok = bool(d.get("ok"))
                        err = str(d.get("err") or ("ok" if ok else "unknown"))
                except ValueError:
                    err = "bad-json"
            if callback:
                callback(ok, err)
        self._mw._js_active(
            'window.aiReplaceSel(' + js(text) + ', ' + js(orig_text or "") + ')', _cb)

    def insert_at_caret(self, text, callback=None):
        """v3.48.5（AI-REDESIGN）：旧版调 window.insertTextAtCaret —— 该函数是
        IIFE 内局部函数、window 上不存在 → AI「插入」一直静默失败。改调
        window.aiInsertAtCaret（本次新增，带 {ok, err} 返回），结果回传。"""
        def _cb(v):
            ok, err = False, "unknown"
            if isinstance(v, str):
                try:
                    import json as _json
                    d = _json.loads(v)
                    if isinstance(d, dict):
                        ok = bool(d.get("ok"))
                        err = str(d.get("err") or ("ok" if ok else "unknown"))
                except ValueError:
                    err = "bad-json"
            if callback:
                callback(ok, err)
        self._mw._js_active('window.aiInsertAtCaret(' + js(text) + ')', _cb)

    def get_markdown(self, callback):
        """v3.48.5（AI-REDESIGN）：取当前编辑器全文（Markdown），供插入预览
        过期检测（预览期间文档被改 → 不直接覆盖，先询问用户）。"""
        self._mw._js_active(
            'window.getMarkdown()',
            lambda v: callback(v if isinstance(v, str) else ''))

    # v3.48.18（AI-CTX）：自适应上下文的数据源 —— 文档全文 + 光标块 + 选区 +
    # 书籍目录/当前章节。JS 侧 aiContextInfo() 一次性取回，避免多次往返。
    def get_document_context(self, callback):
        """回调 dict：{md, block, selText, book}。

        安全兜底：页面未就绪 / JS 异常时 1.5s 后以空上下文回调，
        保证 AI 请求不会因为「取不到上下文」而永远不发出。"""
        state = {"done": False}

        def _fin(info):
            if state["done"]:
                return
            state["done"] = True
            callback(info if isinstance(info, dict) else {})

        def _cb(v):
            info = {}
            if isinstance(v, str):
                try:
                    d = json.loads(v)
                    if isinstance(d, dict):
                        info = d
                except ValueError:
                    info = {}
            info["book"] = self._book_ctx_info()
            _fin(info)

        try:
            QTimer.singleShot(1500, lambda: _fin({}))
            self._mw._js_active('window.aiContextInfo()', _cb)
        except Exception:      # noqa: BLE001
            _fin({})

    def _book_ctx_info(self):
        """书籍模式：返回 {title, toc:[(depth,title,path)], chapter_path,
        chapter_title}；非书籍模式返回 None。"""
        mw = self._mw
        book = getattr(mw, "_book", None)
        if not book:
            return None
        chapters = []
        try:
            chapters = mw._book_chapters_with_depth(book)
        except Exception:      # noqa: BLE001
            chapters = []
        toc = []
        for c in chapters:
            try:
                toc.append((int(c.get("depth") or 0), c.get("title") or "",
                            c.get("abs_path") or ""))
            except Exception:  # noqa: BLE001
                continue
        cur = getattr(mw, "file_path", None) or ""
        cur_abs = os.path.abspath(cur) if cur else ""
        cur_title = ""
        for c in chapters:
            p = c.get("abs_path") or ""
            if cur_abs and p and os.path.abspath(p) == cur_abs:
                cur_title = c.get("title") or ""
                break
        return {"title": book.get("title") or "", "toc": toc,
                "chapter_path": cur_abs, "chapter_title": cur_title}

    # v3.47.8（AI-PREVIEW）：插入前先计算修改前/修改后，供预览面板展示
    def get_insert_plan(self, text, callback):
        def _cb(v):
            try:
                import json as _json
                d = _json.loads(v) if isinstance(v, str) else v
            except Exception:
                d = None
            callback(d)
        self._mw._js_active('window.aiInsertPlan(' + js(text) + ')', _cb)

    # v3.47.8（AI-PREVIEW）：确认后把合并后全文写回编辑区（与版本合并一致：
    # 经 _push_text 落盘前写入并置脏，不覆盖磁盘；会重置该视图内部撤销栈）
    def apply_whole_doc(self, text, callback=None):
        """v3.48.24（AI-DOC）：整篇替换当前文档（可撤销）。

        经 window.aiApplyInsert（快照压栈，Ctrl+Z 撤销插入、重做恢复）；
        返回 'ok' 表示成功。源码/双栏视图无快照栈，走 _push_text 原路径。"""
        def _cb(v):
            ok, err = False, "unknown"
            if isinstance(v, str):
                ok = (v == "ok")
                err = "" if ok else v
            if callback:
                callback(ok, err)
        if self._dual:
            self._mw._push_text(text)   # 双栏源码视图仍走原路径（源码态无快照栈）
            self._mw._dirty = True
            self._mw._update_title()
            self._mw.show_status(T("已用 AI 优化结果整体替换文档 · Ctrl+Z 可撤销 · Ctrl+S 保存", "Replaced document with AI optimize result · Ctrl+Z to undo · Ctrl+S to save"))
            if callback:
                callback(True, "")
            return
        self._mw._js_view(self._mw._view, f"window.aiApplyInsert({js(text)})", _cb)

    # v3.47.2（SoloMD 对标）：主面板「连接设置」按钮 → 打开独立连接面板
    def open_connection(self):
        self._mw.open_ai_connection()

    def connection_status(self):
        from ai_core import connection_status as _cs
        return _cs(self._mw._settings)
