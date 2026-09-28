# -*- coding: utf-8 -*-
"""应用样式体系：六套主题（调色板驱动的全局 QSS）。

v3.8 起，所有 QSS 由主题调色板生成，覆盖：
- 全局界面（菜单栏 / 工具栏 / 标签页 / 状态栏 / 对话框）
- 左侧边栏（文件列表 / 大纲）
- 查找替换、快捷键设置、系统设置等对话框
编辑器内（QWebEngine 页面）的主题由 editor.html 的 theme-style 层承担，
两侧使用同一套主题 ID：light / azure / sepia / dark / night / panda。
"""

# ---------------------------------------------------------------------------
# 主题定义：label 用于菜单显示，swatch 用于系统设置中的预览色
# ---------------------------------------------------------------------------
THEMES = [
    {"id": "light", "label": "浅色（默认）", "swatch": "#ffffff", "editor_bg": "#ffffff"},
    {"id": "azure", "label": "青空", "swatch": "#f3f8fd", "editor_bg": "#f3f8fd"},
    {"id": "sepia", "label": "护眼米黄", "swatch": "#f8f2e4", "editor_bg": "#f8f2e4"},
    {"id": "dark",  "label": "深色", "swatch": "#16191d", "editor_bg": "#16191d"},
    {"id": "night", "label": "墨夜（Typora Night）", "swatch": "#131417", "editor_bg": "#131417"},
    {"id": "panda", "label": "熊猫（Panda）", "swatch": "#232527", "editor_bg": "#232527"},
]
THEME_IDS = [t["id"] for t in THEMES]


def _pal(**kw):
    """生成一份完整调色板：缺省取浅色值，避免模板缺 key。"""
    base = dict(
        bg="#ffffff", bg_soft="#fafbfc", border="#f2f3f5",
        text="#1f2328", text_muted="#6b7280", text_soft="#384048",
        hover_bg="#eef2f7", hover_text="#1f2328",
        accent="#0052d9", accent_soft="#e3edfd",
        menu_bg="#ffffff", menu_border="#e6e8eb", menu_hover_bg="#eef4fe",
        menu_disabled="#b8bec6", sep="#eef0f2",
        input_border="#d8dce2", input_bg="#ffffff",
        btn_bg="#f5f6f8", btn_border="#e2e5ea",
        btn_hover_bg="#e9edf3", btn_hover_border="#d5dae2", btn_pressed="#dfe4ec",
        tooltip_bg="#2b2f33", tooltip_fg="#f5f6f7",
        list_hover="#eceff3", sel_text="#0052d9",
        scroll="#d4d9df", scroll_hover="#bcc3cc",
        tab_text="#57606a", tab_border="#e9ecef",
    )
    base.update(kw)
    return base


PALETTES = {
    "light": _pal(),
    "azure": _pal(
        bg="#f3f8fd", bg_soft="#eaf2fa", border="#dde8f1",
        hover_bg="#e6eff8", accent="#2f7bd9", accent_soft="#ddeafc",
        menu_bg="#ffffff", menu_border="#d8e4ee", menu_hover_bg="#e6f0fa",
        sep="#e2ecf5", input_border="#c9d9e8",
        btn_bg="#eef5fb", btn_border="#d8e4ee", btn_hover_bg="#e2eef8",
        btn_hover_border="#c8d9ea", btn_pressed="#d6e6f4",
        list_hover="#e2edf7", sel_text="#2f7bd9",
        scroll="#c7d7e5", scroll_hover="#adc4d8", tab_border="#d8e4ee",
    ),
    "sepia": _pal(
        bg="#f8f2e4", bg_soft="#f3ecda", border="#e7dcc2",
        text="#4a4238", text_muted="#8a7f70", text_soft="#5a5248",
        hover_bg="#efe6d2", hover_text="#3c362e",
        accent="#a06a2c", accent_soft="#f0e2c6",
        menu_bg="#fbf6ea", menu_border="#e4d9c3", menu_hover_bg="#f0e4c8",
        menu_disabled="#c0b49c", sep="#e8ddc4",
        input_border="#d8c9a5", input_bg="#fdf9ef",
        btn_bg="#f1e9d6", btn_border="#e0d4b8",
        btn_hover_bg="#e9dec4", btn_hover_border="#d3c6a8", btn_pressed="#ddd0b2",
        tooltip_bg="#4a4238", tooltip_fg="#f8f2e4",
        list_hover="#ede2c8", sel_text="#a06a2c",
        scroll="#d3c6a6", scroll_hover="#bfae8a", tab_border="#e0d4b8",
        tab_text="#7d7264",
    ),
    "dark": _pal(
        bg="#1e2227", bg_soft="#191d22", border="#2c3138",
        text="#dce2e8", text_muted="#97a1ac", text_soft="#c3cad2",
        hover_bg="#262c33", hover_text="#e8edf2",
        accent="#5c9dff", accent_soft="#24334d",
        menu_bg="#23282e", menu_border="#333a42", menu_hover_bg="#2a3648",
        menu_disabled="#59636e", sep="#2f353c",
        input_border="#3a424b", input_bg="#1a1e23",
        btn_bg="#272d34", btn_border="#373f48",
        btn_hover_bg="#2f3740", btn_hover_border="#414b56", btn_pressed="#252b32",
        tooltip_bg="#333a42", tooltip_fg="#e8edf2",
        list_hover="#252b32", sel_text="#5c9dff",
        scroll="#3a424b", scroll_hover="#4a545f", tab_border="#333a42",
        tab_text="#97a1ac", tab_sel_bg="#262c33", tab_sel_text="#e8edf2",
    ),
    "night": _pal(
        bg="#17181b", bg_soft="#131417", border="#26282c",
        text="#d5d9de", text_muted="#8a939d", text_soft="#bcc2c8",
        hover_bg="#222428", hover_text="#e2e6ea",
        accent="#38b28c", accent_soft="#1f3a33",
        menu_bg="#1b1d21", menu_border="#2e3238", menu_hover_bg="#243029",
        menu_disabled="#565e66", sep="#26292d",
        input_border="#34383e", input_bg="#101114",
        btn_bg="#212428", btn_border="#303439",
        btn_hover_bg="#282c31", btn_hover_border="#3a3f46", btn_pressed="#1e2125",
        tooltip_bg="#2e3238", tooltip_fg="#e2e6ea",
        list_hover="#212428", sel_text="#38b28c",
        scroll="#34383e", scroll_hover="#454b52", tab_border="#2e3238",
        tab_text="#8a939d", tab_sel_bg="#222428", tab_sel_text="#e2e6ea",
    ),
    "panda": _pal(
        bg="#26292c", bg_soft="#212427", border="#34383d",
        text="#e2e6e9", text_muted="#9aa4ad", text_soft="#c9d0d6",
        hover_bg="#2d3134", hover_text="#eaeef1",
        accent="#19d3b4", accent_soft="#1d3b36",
        menu_bg="#2a2d31", menu_border="#3a3f44", menu_hover_bg="#2b4a44",
        menu_disabled="#5d666e", sep="#33373b",
        input_border="#41474d", input_bg="#1c1e21",
        btn_bg="#2d3134", btn_border="#3d4349",
        btn_hover_bg="#353a3e", btn_hover_border="#474e55", btn_pressed="#282c2f",
        tooltip_bg="#3a3f44", tooltip_fg="#eaeef1",
        list_hover="#2b2f33", sel_text="#19d3b4",
        scroll="#41474d", scroll_hover="#525a61", tab_border="#3a3f44",
        tab_text="#9aa4ad", tab_sel_bg="#2d3134", tab_sel_text="#eaeef1",
    ),
}


def palette(theme_id: str) -> dict:
    return PALETTES.get(theme_id, PALETTES["light"])


# ---------------------------------------------------------------------------
# QSS 模板（{} 占位由 palette 填充；双 {{ }} 为字面大括号）
# ---------------------------------------------------------------------------
APP_QSS_TPL = """
* {{ outline: none; }}
QMainWindow, QDialog {{ background: {bg}; }}
QMenuBar {{
  background: {bg}; border: none; padding: 3px 10px 0;
}}
QMenuBar::item {{
  padding: 6px 12px; margin: 0 1px; border-radius: 6px;
  color: {text_soft}; background: transparent; font-size: 13px;
}}
QMenuBar::item:selected {{ background: {hover_bg}; }}
QMenuBar::item:pressed {{ background: {accent_soft}; color: {accent}; }}
QMenu {{
  background: {menu_bg}; border: 1px solid {menu_border};
  border-radius: 10px; padding: 6px;
}}
QMenu::item {{
  padding: 7px 30px 7px 16px; border-radius: 6px; color: {text}; font-size: 13px;
}}
QMenu::item:selected {{ background: {menu_hover_bg}; color: {accent}; }}
QMenu::item:disabled {{ color: {menu_disabled}; }}
QMenu::separator {{ height: 1px; background: {sep}; margin: 5px 10px; }}
QToolBar {{
  background: {bg}; border: none; border-bottom: 1px solid {border};
  padding: 4px 12px; spacing: 3px;
}}
QToolBar::separator {{ width: 1px; background: {sep}; margin: 7px 9px; }}
QToolBar QToolButton {{ padding: 6px 11px; font-size: 13px; }}
QToolBar#sideTB {{
  background: {bg_soft}; border: none; border-right: 1px solid {border};
  padding: 8px 5px; spacing: 3px;
}}
QToolBar#sideTB::separator {{ height: 1px; background: {sep}; margin: 7px 6px; }}
QToolBar#sideTB QToolButton {{ padding: 8px 0; min-width: 36px; font-size: 13px; }}
QToolButton {{
  border: none; border-radius: 7px; padding: 5px 10px;
  color: {text_muted}; background: transparent;
}}
QToolButton:hover {{ background: {hover_bg}; color: {hover_text}; }}
QToolButton:pressed, QToolButton:checked {{ background: {accent_soft}; color: {accent}; }}
QStatusBar {{
  background: {bg_soft}; border-top: 1px solid {border}; min-height: 28px;
}}
QStatusBar QLabel {{ color: {text_muted}; font-size: 12px; padding: 0 6px; }}
QStatusBar QToolButton {{ padding: 2px 9px; }}
QToolTip {{
  background: {tooltip_bg}; color: {tooltip_fg}; border: none;
  border-radius: 6px; padding: 6px 11px; font-size: 12px;
}}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {accent_soft}; }}
#tabstrip {{ background: {bg_soft}; border-bottom: 1px solid {border}; }}
#tabstrip QTabBar {{
  background: transparent; font-size: 12.5px;
}}
#tabstrip QTabBar::tab {{
  background: transparent; color: {tab_text};
  padding: 6px 12px 6px 14px; margin: 4px 2px 0;
  border-radius: 8px 8px 0 0; border: 1px solid transparent;
  border-bottom: none;
}}
#tabstrip QTabBar::tab:hover:!selected {{ background: {hover_bg}; color: {hover_text}; }}
#tabstrip QTabBar::tab:selected {{
  background: {bg}; color: {text}; font-weight: 600;
  border-color: {tab_border};
}}
QDialog QLabel {{ color: {text_soft}; }}
QDialog QLineEdit, QDialog QCheckBox {{ color: {text}; }}
QDialog QLineEdit {{
  border: 1px solid {input_border}; border-radius: 7px;
  padding: 6px 10px; background: {input_bg};
}}
QDialog QLineEdit:focus {{ border-color: {accent}; }}
QDialog QPushButton {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 7px;
  padding: 6px 18px; color: {text};
}}
QDialog QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
QDialog QPushButton:pressed {{ background: {btn_pressed}; }}
QDialog QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
QDialog QListWidget {{
  background: {input_bg}; border: 1px solid {menu_border};
  border-radius: 8px; color: {text}; outline: 0; font-size: 13px;
}}
QDialog QListWidget::item {{ padding: 7px 10px; border-radius: 6px; }}
QDialog QListWidget::item:hover {{ background: {list_hover}; }}
QDialog QListWidget::item:selected {{ background: {accent_soft}; color: {accent}; }}
QDialog QSlider::groove:horizontal {{
  height: 4px; background: {sep}; border-radius: 2px;
}}
QDialog QSlider::handle:horizontal {{
  width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; background: {accent};
}}
QDialog QSpinBox {{
  border: 1px solid {input_border}; border-radius: 7px; padding: 4px 8px;
  background: {input_bg}; color: {text};
}}
"""

SIDEBAR_QSS_TPL = """
#sidebar {{
  background: {bg_soft}; border-right: 1px solid {border};
}}
#tabcap {{
  background: {accent_soft}; border-radius: 9px; padding: 3px;
}}
#tabcap QToolButton {{
  border: none; background: transparent; color: {text_muted};
  padding: 5px 16px; border-radius: 7px; font-size: 12.5px;
}}
#tabcap QToolButton:hover {{ background: rgba(255, 255, 255, 0.35); color: {text}; }}
#tabcap QToolButton:checked {{
  background: {bg}; color: {text}; font-weight: 600;
}}
#sidebar QToolButton {{
  border: none; background: transparent; color: {text_muted};
  padding: 5px 12px; border-radius: 7px; font-size: 12px;
}}
#sidebar QToolButton:hover {{ background: {list_hover}; color: {text}; }}
#sidebar QToolButton:checked {{ background: {accent_soft}; color: {accent}; font-weight: 600; }}
#sidebar QListWidget, #sidebar QTreeWidget {{
  background: transparent; border: none; outline: 0;
  font-size: 13px; color: {text};
  show-decoration-selected: 0;
}}
/* branch 列（展开箭头区）透明：去掉系统默认的绿色选中阴影 */
#sidebar QTreeWidget::branch {{ background: transparent; }}
#sidebar QListWidget::item {{
  padding: 5px 9px; margin: 1px 10px; border-radius: 7px; color: {text};
}}
#sidebar QListWidget::item:hover {{ background: {list_hover}; }}
#sidebar QListWidget::item:selected {{
  background: {accent_soft}; color: {accent};
}}
#sidebar QTreeWidget::item {{
  padding: 4px 6px; margin: 1px 8px; border-radius: 7px; color: {text};
}}
#sidebar QTreeWidget::item:hover {{ background: {list_hover}; }}
#sidebar QTreeWidget::item:selected {{ background: {accent_soft}; color: {accent}; }}
#sidebar #fileHeader {{
  text-align: left; padding: 7px 14px; margin: 0; min-height: 0;
  border: none; border-radius: 0; font-size: 13px; font-weight: 600;
  color: {text}; background: transparent;
}}
#sidebar #fileHeader:hover {{ background: {list_hover}; color: {accent}; }}
#sidebar #fileHeader:pressed {{ background: {accent_soft}; color: {accent}; }}
#sidebar QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
#sidebar QScrollBar::handle:vertical {{ background: {scroll}; border-radius: 4px; min-height: 30px; }}
#sidebar QScrollBar::handle:vertical:hover {{ background: {scroll_hover}; }}
#sidebar QScrollBar::add-line:vertical, #sidebar QScrollBar::sub-line:vertical {{ height: 0; }}
#sidebar QLabel {{ color: {text_muted}; font-size: 11px; padding: 6px 14px 2px; }}
/* ---- 搜索面板（跨文件搜索）---- */
#sidebar QLineEdit {{
  border: 1px solid {input_border}; border-radius: 7px; padding: 6px 10px;
  margin: 4px 8px 0 8px; font-size: 12.5px; background: {input_bg}; color: {text};
}}
#sidebar QLineEdit:focus {{ border-color: {accent}; }}
#sidebar QComboBox {{
  border: 1px solid {input_border}; border-radius: 7px; padding: 4px 8px;
  font-size: 12px; background: {input_bg}; color: {text};
}}
#sidebar QComboBox QAbstractItemView {{
  background: {bg}; color: {text}; selection-background-color: {accent_soft};
  selection-color: {accent}; border: 1px solid {border};
}}
#sidebar QCheckBox {{ color: {text_muted}; font-size: 11.5px; }}
#sidebar QPushButton {{
  border: 1px solid {input_border}; border-radius: 7px; padding: 5px 12px;
  font-size: 12px; background: {input_bg}; color: {text};
}}
#sidebar QPushButton:hover {{ border-color: {accent}; color: {accent}; }}
#sidebar #searchTitle {{
  font-size: 12px; font-weight: 600; padding: 6px 12px 0 12px; color: {text};
}}
#sidebar #searchScope, #sidebar #searchInfo {{
  font-size: 11px; padding: 2px 12px; color: {text_muted};
}}
"""

# 对话框独立样式（查找替换 / 快捷键设置 / 系统设置共用）
DIALOG_QSS_TPL = """
#findDlg {{ background: {bg}; }}
#findDlg QLabel {{ color: {text_muted}; font-size: 12px; }}
#findDlg QLineEdit {{
  border: 1px solid {input_border}; border-radius: 7px; padding: 7px 10px;
  font-size: 13px; background: {input_bg}; color: {text};
}}
#findDlg QLineEdit:focus {{ border-color: {accent}; }}
#findDlg QPushButton {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 7px;
  padding: 7px 14px; color: {text}; font-size: 12.5px;
}}
#findDlg QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
#findDlg QPushButton:pressed {{ background: {btn_pressed}; }}
#findDlg QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
#findDlg QPushButton:default:hover {{ background: {btn_hover_bg}; }}
#findDlg QCheckBox {{ color: {text_soft}; font-size: 12.5px; }}
/* v3.27：查找面板——范围分段切换 + 计数胶囊 + 正则帮助按钮 */
#findDlg QToolButton#scopeBtn {{
  background: transparent; border: 1px solid transparent; border-radius: 7px;
  padding: 6px 12px; color: {text_muted}; font-size: 12.5px;
}}
#findDlg QToolButton#scopeBtn:hover {{ color: {text}; background: {btn_hover_bg}; }}
#findDlg QToolButton#scopeBtn:checked {{
  background: {accent_soft}; color: {accent}; border-color: {accent};
  font-weight: 600;
}}
#findDlg QToolButton#helpBtn {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 7px;
  padding: 6px 9px; color: {text_muted}; font-size: 12.5px; font-weight: 600;
}}
#findDlg QToolButton#helpBtn:hover {{ color: {accent}; border-color: {accent}; }}
#findDlg #countLbl {{
  color: {accent}; font-size: 12px; background: {accent_soft};
  border-radius: 9px; padding: 3px 9px;
}}
#findDlg #countLbl[warn="true"] {{
  color: #e5484d; background: rgba(229, 72, 77, 0.14); font-weight: 600;
}}
/* v3.24：全局搜索面板状态行与结果树样式 */
#findDlg #searchScope, #findDlg #searchInfo {{ color: {text_muted}; font-size: 12px; }}
#findDlg QTreeWidget {{
  border: 1px solid {menu_border}; border-radius: 8px; background: {input_bg};
  font-size: 12.5px; color: {text}; outline: 0;
}}
#findDlg QTreeWidget::item {{ height: 24px; border-radius: 6px; }}
#findDlg QTreeWidget::item:selected {{ background: {accent_soft}; color: {accent}; }}
#findDlg QComboBox {{
  border: 1px solid {input_border}; border-radius: 7px; padding: 5px 8px;
  background: {input_bg}; color: {text}; font-size: 12.5px;
}}
#shortcutDlg QTreeWidget {{
  border: 1px solid {menu_border}; border-radius: 8px; background: {input_bg};
  font-size: 13px; color: {text}; outline: 0;
}}
#shortcutDlg QTreeWidget::item {{ height: 28px; border-radius: 6px; }}
#shortcutDlg QTreeWidget::item:selected {{ background: {accent_soft}; color: {accent}; }}
#shortcutDlg QHeaderView::section {{
  background: {bg_soft}; border: none; border-bottom: 1px solid {sep};
  padding: 6px 8px; font-size: 12px; color: {text_muted};
}}
#shortcutDlg QKeySequenceEdit {{
  border: 1px solid {input_border}; border-radius: 7px; padding: 6px 10px; background: {input_bg};
  color: {text};
}}
#shortcutDlg QKeySequenceEdit:focus {{ border-color: {accent}; }}
#hint {{ color: {text_muted}; font-size: 11.5px; }}
#settingsDlg {{ background: {bg}; }}
#settingsDlg QLabel {{ color: {text_soft}; font-size: 13px; background: transparent; }}
#settingsDlg #navList {{
  background: {bg_soft}; border: none; border-right: 1px solid {border};
  font-size: 13.5px; color: {text}; outline: 0; padding-top: 8px;
}}
#settingsDlg #navList::item {{ padding: 9px 16px; margin: 2px 8px; border-radius: 8px; }}
#settingsDlg #navList::item:hover {{ background: {list_hover}; }}
#settingsDlg #navList::item:selected {{ background: {accent_soft}; color: {accent}; }}
#settingsDlg #pageTitle {{ font-size: 17px; font-weight: 600; color: {text}; }}
#settingsDlg #pageHint {{ color: {text_muted}; font-size: 12px; }}
#settingsDlg QGroupBox {{
  border: 1px solid {border}; border-radius: 10px; margin-top: 12px;
  background: {bg_soft}; font-weight: 600; padding-top: 6px;
}}
/* v3.29d：组框标题呈「嵌入式图例」—— 标题垂直中点压在顶部边框线上，
   文字底下垫页面底色，边框线在文字处断开（fieldset legend 视觉效果） */
#settingsDlg QGroupBox::title {{
  subcontrol-origin: border; subcontrol-position: top left;
  left: 14px; top: -8px; padding: 0 6px;
  background: {bg}; color: {accent}; font-size: 12.5px; font-weight: 600;
}}
#settingsDlg QCheckBox {{ color: {text}; font-size: 13px; }}
#settingsDlg QLineEdit, #settingsDlg QComboBox {{
  border: 1px solid {input_border}; border-radius: 7px; padding: 5px 10px;
  background: {input_bg}; color: {text};
}}
#settingsDlg #themeList {{
  background: {input_bg}; border: 1px solid {menu_border};
  border-radius: 8px; color: {text}; outline: 0;
}}
#settingsDlg #themeList::item {{ padding: 8px 10px; border-radius: 6px; }}
#settingsDlg #themeList::item:hover {{ background: {list_hover}; }}
#settingsDlg #themeList::item:selected {{ background: {accent_soft}; color: {accent}; }}
#settingsDlg QSlider::groove:horizontal {{ height: 4px; background: {sep}; border-radius: 2px; }}
#settingsDlg QSlider::handle:horizontal {{
  width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; background: {accent};
}}
#settingsDlg QPushButton {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 7px;
  padding: 6px 18px; color: {text};
}}
#settingsDlg QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
#settingsDlg QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
"""


def app_qss(theme_id: str = "light") -> str:
    return APP_QSS_TPL.format(**palette(theme_id))


def sidebar_qss(theme_id: str = "light") -> str:
    return SIDEBAR_QSS_TPL.format(**palette(theme_id))


def dialog_qss(theme_id: str = "light") -> str:
    return DIALOG_QSS_TPL.format(**palette(theme_id))


def theme_label(theme_id: str) -> str:
    for t in THEMES:
        if t["id"] == theme_id:
            return t["label"]
    return THEMES[0]["label"]


# 兼容旧引用（main.py 启动时的初始浅色样式）
APP_QSS = app_qss("light")
SIDEBAR_QSS = sidebar_qss("light")
