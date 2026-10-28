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
        # v3.44.3（DESIGN01）：对齐设计01「现代经典风」区域令牌 ——
        # chrome2 = 标签条底（设计稿 --chrome2）；chrome_line = 各 chrome 区域
        # 边界线（设计稿 --line，比 border 更清晰，保证标题栏/侧栏/工具栏边界可见）
        chrome2="#f2f3f5", chrome_line="#dde1e7", side="#e9edf2",
        # v3.44.29：风格 chrome 令牌（原仅 office/code 等风格 JSON 强制蓝，切主题后
        # 不与主题协调；下放到主题调色板，使 menubar/statusbar 主底色随主题）。
        # chrome_bar = 标题栏 / 状态栏主底色（取各主题 chrome2 同值）；
        # chrome_bar_text = 其上文字（随主题正/负色自动翻转）；
        # status_sep = 状态栏内分隔线（浅色主题用深半透明、深色主题用浅半透明）。
        chrome_bar="#f2f3f5", chrome_bar_text="#1f2328", status_sep="rgba(0,0,0,.08)",
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
        chrome2="#e2edf8", chrome_line="#dde8f1", side="#eaf2fa",
        chrome_bar="#e2edf8", chrome_bar_text="#243342", status_sep="rgba(0,0,0,.08)",
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
        chrome2="#efe7d3", chrome_line="#e7dcc2", side="#f3ecda",
        chrome_bar="#efe7d3", chrome_bar_text="#4a4238", status_sep="rgba(0,0,0,.08)",
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
        chrome2="#222730", chrome_line="#2c3138", side="#191d22",
        chrome_bar="#222730", chrome_bar_text="#dce2e8", status_sep="rgba(255,255,255,.18)",
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
        chrome2="#1f2125", chrome_line="#26282c", side="#131417",
        chrome_bar="#1f2125", chrome_bar_text="#d5d9de", status_sep="rgba(255,255,255,.18)",
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
        chrome2="#2c3034", chrome_line="#34383d", side="#212427",
        chrome_bar="#2c3034", chrome_bar_text="#e2e6e9", status_sep="rgba(255,255,255,.18)",
    ),
}


def palette(theme_id: str) -> dict:
    pal = dict(PALETTES.get(theme_id, PALETTES["light"]))
    # v3.42.0：页签选中态 token 缺省（主模板 ::tab:selected 引用；六主题均未
    # 显式定义 → 回退 bg/text，ps01 等默认外观与历史版本完全一致）
    pal.setdefault("tab_sel_bg", pal["bg"])
    pal.setdefault("tab_sel_text", pal["text"])
    return pal


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
  color: {text_soft}; background: transparent; font-size: 13px; font-family: 'Microsoft YaHei';
}}
QMenuBar::item:selected {{ background: {hover_bg}; }}
QMenuBar::item:pressed {{ background: {accent_soft}; color: {accent}; }}
QMenu {{
  background: {menu_bg}; border: 1px solid {menu_border};
  border-radius: 7px; padding: 5px;
}}
/* RIBBON-12（v3.44.26）：命令菜单项间距/字体统一为 WorkBuddy 标准观感 ——
   Microsoft YaHei 13px，上下 5px 内距 + 5px 菜单内距，单行 ≈ 23px，
   比 RIBBON-6 的紧凑档略宽松，与各下拉命令菜单整体风格一致。 */
QMenu::item {{
  padding: 5px 32px 5px 14px; border-radius: 4px; color: {text};
  font-size: 13px; font-family: 'Microsoft YaHei';
}}
/* v3.43.0（VIEW-REF）：参照 02_视图菜单.png —— hover/选中 = 浅蓝底深字（非实心蓝白字），
   勾选项整体铺浅蓝底（分屏模式 / 侧边栏 / 工具栏三行的参照形态） */
QMenu::item:selected {{ background: {menu_hover_bg}; color: {text}; }}
QMenu::item:checked {{ background: {accent_soft}; }}
QMenu::item:checked:selected {{ background: {menu_hover_bg}; color: {accent}; }}
QMenu::item:disabled {{ color: {menu_disabled}; }}
QMenu::separator {{ height: 1px; background: {sep}; margin: 5px 10px; }}
QToolBar {{
  background: {bg}; border: none; border-bottom: 1px solid {border};
  padding: 4px 12px; spacing: 3px;
}}
QToolBar::separator {{ width: 1px; background: {sep}; margin: 7px 9px; }}
QToolBar QToolButton {{ padding: 6px 11px; font-size: 13px; }}
QToolBar#sideTB {{
  background: {bg_soft}; border: none; border-right: 1px solid {chrome_line};
  padding: 7px 0;
}}
/* v3.41.3：对齐设计稿 .vtool——按钮间 gap 2px 由 _SideTBStyle(QProxyStyle) 的
   PM_ToolBarItemSpacing 驱动（QSS spacing/margin 对 QToolBar 条目均不生效）；
   分组分隔线为 24x1 QFrame#sideSep（原生 ::separator 宽度不可控） */
QFrame#sideSep {{ background: {sep}; }}
QToolBar#sideTB QToolButton {{ padding: 7px 0; min-width: 38px; font-size: 14px; }}
QToolButton {{
  border: none; border-radius: 6px; padding: 5px 10px;
  color: {text_muted}; background: transparent;
}}
QToolButton:hover {{ background: {hover_bg}; color: {hover_text}; }}
QToolButton:pressed, QToolButton:checked {{ background: {accent_soft}; color: {accent}; }}
QStatusBar {{
  background: {bg_soft}; border-top: 1px solid {chrome_line}; min-height: 28px;
}}
QStatusBar QLabel {{
  color: {text_muted}; font-size: 11px; padding: 0 8px;
  border-right: 1px solid {sep};
}}
QStatusBar QToolButton {{ padding: 2px 9px; }}
QToolTip {{
  background: {tooltip_bg}; color: {tooltip_fg}; border: none;
  border-radius: 8px; padding: 7px 12px; font-size: 12px;
}}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {accent_soft}; }}
/* v3.44.4（DESIGN01 修复）：主分栏手柄着 chrome_line —— 侧栏/编辑区之间的竖向分隔线，
   由分栏手柄绘制（位于两控件之间，永不被子控件覆盖），保证「边线」稳定可见 */
#mainSplit::handle {{ background: {chrome_line}; }}
/* v3.44.3（DESIGN01）：编辑区容器显式底色（设计稿 .content background = mica），
   标签条底 = chrome2（设计稿 --chrome2），底边线 = chrome_line（--line）；
   选中页签强调色指示条按设计稿放「底部」（与编辑区卡片连成一体），
   不再压顶边——即标题栏下缘不再出现蓝色线条 */
#contentArea {{ background: {bg}; }}
#tocBar {{ background: {chrome2}; border-top: 1px solid {chrome_line}; }}
#btnInsertToc {{ background: {accent}; color: #ffffff; border: none;
  padding: 5px 14px; border-radius: 6px; font-size: 12.5px; font-weight: 600; }}
#tabstrip {{ background: {chrome2}; border-bottom: 1px solid {chrome_line}; }}
#tabstrip QTabBar {{
  background: transparent; font-size: 12.5px;
}}
#tabstrip QTabBar::tab {{
  background: transparent; color: {tab_text};
  padding: 6px 12px 5px 14px; margin: 0px 2px 0;
  border-radius: 6px 6px 0 0; border: 1px solid transparent;
  border-top: 2px solid transparent;
  border-bottom: none;
}}
#tabstrip QTabBar::tab:hover:!selected {{ background: {hover_bg}; color: {hover_text}; }}
#tabstrip QTabBar::tab:selected {{
  background: {tab_sel_bg}; color: {tab_sel_text}; font-weight: 600;
  border-color: {tab_border};
  border-bottom: 2px solid transparent;
}}
QDialog QLabel {{ color: {text_soft}; }}
QDialog QLineEdit, QDialog QCheckBox {{ color: {text}; }}
QDialog QLineEdit {{
  border: 1px solid {input_border}; border-radius: 6px;
  padding: 6px 10px; background: {input_bg};
}}
QDialog QLineEdit:focus {{ border-color: {accent}; }}
QDialog QPushButton {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 6px;
  padding: 6px 18px; color: {text};
}}
QDialog QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
QDialog QPushButton:pressed {{ background: {btn_pressed}; }}
QDialog QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
QDialog QListWidget {{
  background: {input_bg}; border: 1px solid {menu_border};
  border-radius: 6px; color: {text}; outline: 0; font-size: 13px;
}}
QDialog QListWidget::item {{ padding: 7px 10px; border-radius: 6px; }}
QDialog QListWidget::item:hover {{ background: {list_hover}; }}
QDialog QListWidget::item:selected {{ background: {accent_soft}; color: {accent}; }}
QDialog QSlider::groove:horizontal {{
  height: 4px; background: {sep}; border-radius: 2px;
}}
QDialog QSlider::handle:horizontal {{
  width: 14px; height: 14px; margin: -6px 0; border-radius: 6px; background: {accent};
}}
QDialog QSpinBox {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 4px 8px;
  background: {input_bg}; color: {text};
}}
/* v3.47.3（AI 面板美化 + Ollama 引导）：统一主题观感 —— 卡片化边框、协调间距 */
#aiPane {{ background: {bg}; }}
#aiPane #aiStatusText {{ color: {text_soft}; font-size: 12.5px; background: transparent; }}
#aiPane #aiThinkBtn {{ padding: 4px 10px; font-size: 12px; }}
#aiPane #aiThinkBtn:checked {{ background: {accent_soft}; border-color: {accent}; color: {accent}; }}
#aiPane QPushButton {{ background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 7px;
  padding: 5px 12px; color: {text}; font-size: 12.5px; }}
#aiPane QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
#aiPane QPushButton:disabled {{ background: {bg_soft}; color: {text_muted}; border-color: {sep}; }}
#aiPane QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
#aiPane #aiSendBtn {{ padding: 3px 16px; }}   /* v3.48.14：发送按钮上下留白压缩 */
#aiPane #aiChat {{ background: {bg_soft}; border: 1px solid {border}; border-radius: 10px;
  padding: 8px 10px; color: {text}; }}
#aiPane #aiInput {{ background: {input_bg}; border: 1px solid {input_border}; border-radius: 8px;
  padding: 5px 8px; color: {text}; font-size: 13px; }}
#aiPane #aiSplit::handle {{ background: {sep}; border-radius: 3px; }}
/* 本地 Ollama 引导框（主面板与设置页通用） */
#aiOllamaBox {{ border: 1px solid {border}; border-radius: 9px; margin-top: 10px;
  background: {bg_soft}; padding-top: 4px; }}
#aiOllamaBox::title {{ subcontrol-origin: border; subcontrol-position: top left;
  left: 12px; top: -7px; padding: 0 5px; background: {bg}; color: {accent};
  font-size: 12px; font-weight: 600; }}
#aiLink {{ color: {accent}; background: transparent; }}
/* 顶栏「AI 助手」图标按钮（v3.47.5 REQ3）：扁平、低调，与左侧线性图标一致；
   替代原文字按钮以节省空间，自身不再带强调底色 */
#aiCornerBtn {{ border: none; background: transparent; padding: 3px; }}
#aiCornerBtn:hover {{ background: {accent_soft}; border-radius: 6px; }}
"""

SIDEBAR_QSS_TPL = """
#sidebar {{
  background: {side};
}}
/* v3.39.14（HEAD-1）：页面头配色重设计——胶囊由淡蓝块改为中性分段控件：
   浅灰描边容器 + 白底选中块，与主区页签（白底+accent 顶线）统一高亮语言 */
#tabcap {{
  background: transparent; border: none;
  border-bottom: 1px solid {border};
  border-radius: 0; padding: 0;
}}
#tabcap QToolButton {{
  border: none; background: transparent; color: {text_muted};
  /* v3.48.30（TAB-FIX）：水平内边距 16→8 —— 三个页签（文件/书籍/大纲）
     在 224px 侧栏内完整显示，此前 16px 时每钮需 59px、三钮 177px 超出
     152px 可用宽，文字全部被省略成「…」 */
  padding: 8px 8px; border-radius: 0; font-size: 12px;
  border-bottom: 2px solid transparent;
}}
#tabcap QToolButton:hover {{ background: {hover_bg}; color: {text}; }}
#tabcap QToolButton:checked {{
  background: transparent; color: {text}; font-weight: 600;
  border-bottom: 2px solid {accent};
}}
/* v3.48.35（CRUMB-TAIL）：路径段按钮 / 「…」折叠按钮的内边距 —— 用双 ID 选择器
   压过上面 #sidebar QToolButton 的 5px 12px（否则每段空耗 24px，224px 侧栏放不下三层） */
#sidebar QToolButton#crumbSeg {{ border:none; background:transparent;
  padding:4px 6px; border-radius:5px; }}
#sidebar QToolButton#crumbDots {{ border:none; background:transparent;
  padding:4px 4px; border-radius:5px; }}
#sidebar #crumbUp {{
  border: 1px solid {input_border}; background: {input_bg};
  color: {text_muted}; border-radius: 6px; font-size: 13px;
}}
#sidebar #crumbUp:hover {{ border-color: {accent}; color: {accent}; }}
#sidebar QToolButton {{
  border: none; background: transparent; color: {text_muted};
  padding: 5px 12px; border-radius: 6px; font-size: 12px;
}}
#sidebar QToolButton:hover {{ background: {list_hover}; color: {text}; }}
#sidebar QToolButton:checked {{ background: {accent_soft}; color: {accent}; font-weight: 600; }}
#sidebar QListWidget, #sidebar QTreeWidget {{
  background: transparent; border: none; outline: 0;
  font-size: 12px; color: {text};
  show-decoration-selected: 0;
}}
/* branch 列（展开箭头区）透明：去掉系统默认的绿色选中阴影 */
#sidebar QTreeWidget::branch {{ background: transparent; }}
#sidebar QListWidget::item {{
  padding: 5px 10px; margin: 1px 10px; border-radius: 6px; color: {text};
}}
#sidebar QListWidget::item:hover {{ background: {list_hover}; }}
#sidebar QListWidget::item:selected {{
  background: {accent_soft}; color: {accent};
}}
#sidebar QTreeWidget::item {{
  padding: 4px 6px; margin: 1px 10px; border-radius: 6px; color: {text};
}}
#sidebar QTreeWidget::item:hover {{ background: {list_hover}; }}
#sidebar QTreeWidget::item:selected {{ background: {accent_soft}; color: {accent}; }}
#sidebar #fileHeader {{
  text-align: left; padding: 7px 10px; margin: 0; min-height: 0;
  border: none; border-radius: 0; font-size: 13px; font-weight: 600;
  color: {text}; background: transparent;
}}
#sidebar #fileHeader:hover {{ background: {list_hover}; color: {accent}; }}
#sidebar #fileHeader:pressed {{ background: {accent_soft}; color: {accent}; }}
#sidebar QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
#sidebar QScrollBar::handle:vertical {{ background: {scroll}; border-radius: 4px; min-height: 30px; }}
#sidebar QScrollBar::handle:vertical:hover {{ background: {scroll_hover}; }}
#sidebar QScrollBar::add-line:vertical, #sidebar QScrollBar::sub-line:vertical {{ height: 0; }}
#sidebar QLabel {{ color: {text_muted}; font-size: 11px; padding: 6px 10px 2px; }}
/* ---- 搜索面板（跨文件搜索）---- */
#sidebar QLineEdit {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 6px 10px;
  margin: 4px 10px 0 10px; font-size: 12.5px; background: {input_bg}; color: {text};
}}
#sidebar QLineEdit:focus {{ border-color: {accent}; }}
/* v3.48.35（FILE-SCOPE）：筛选框与「显示范围」漏斗按钮同处一行 —— 筛选框右
   边距收 0（按钮自己带右边距），按钮固定 26×26、边框与输入框同款。 */
#sidebar #fileFilter {{ margin: 4px 0 0 10px; }}
#sidebar #fileScope {{
  border: 1px solid {input_border}; background: {input_bg};
  border-radius: 6px; margin: 4px 10px 0 0; padding: 0;
}}
#sidebar #fileScope:hover {{ border-color: {accent}; }}
#sidebar QComboBox {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 4px 8px;
  font-size: 12px; background: {input_bg}; color: {text};
}}
#sidebar QComboBox QAbstractItemView {{
  background: {bg}; color: {text}; selection-background-color: {accent_soft};
  selection-color: {accent}; border: 1px solid {border};
}}
#sidebar QCheckBox {{ color: {text_muted}; font-size: 11.5px; }}
#sidebar QPushButton {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 5px 12px;
  font-size: 12px; background: {input_bg}; color: {text};
}}
#sidebar QPushButton:hover {{ border-color: {accent}; color: {accent}; }}
#sidebar #searchTitle {{
  font-size: 12px; font-weight: 600; padding: 6px 10px 0 10px; color: {text};
}}
#sidebar #searchScope, #sidebar #searchInfo {{
  font-size: 11px; padding: 2px 10px; color: {text_muted};
}}
"""

# 对话框独立样式（查找替换 / 快捷键设置 / 系统设置共用）
DIALOG_QSS_TPL = """
#findDlg {{ background: {bg}; }}
#findDlg QLabel {{ color: {text_muted}; font-size: 12px; }}
#findDlg QLineEdit {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 7px 10px;
  font-size: 13px; background: {input_bg}; color: {text};
}}
#findDlg QLineEdit:focus {{ border-color: {accent}; }}
#findDlg QPushButton {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 6px;
  padding: 7px 14px; color: {text}; font-size: 12.5px;
}}
#findDlg QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
#findDlg QPushButton:pressed {{ background: {btn_pressed}; }}
#findDlg QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
#findDlg QPushButton:default:hover {{ background: {btn_hover_bg}; }}
#findDlg QCheckBox {{ color: {text_soft}; font-size: 12.5px; }}
/* v3.27：查找面板——范围分段切换 + 计数胶囊 + 正则帮助按钮 */
#findDlg QToolButton#scopeBtn {{
  background: transparent; border: 1px solid transparent; border-radius: 6px;
  padding: 6px 12px; color: {text_muted}; font-size: 12.5px;
}}
#findDlg QToolButton#scopeBtn:hover {{ color: {text}; background: {btn_hover_bg}; }}
#findDlg QToolButton#scopeBtn:checked {{
  background: {accent_soft}; color: {accent}; border-color: {accent};
  font-weight: 600;
}}
#findDlg QToolButton#helpBtn {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 6px;
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
  border: 1px solid {menu_border}; border-radius: 6px; background: {input_bg};
  font-size: 12.5px; color: {text}; outline: 0;
}}
#findDlg QTreeWidget::item {{ height: 24px; border-radius: 6px; }}
#findDlg QTreeWidget::item:selected {{ background: {accent_soft}; color: {accent}; }}
#findDlg QComboBox {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 5px 8px;
  background: {input_bg}; color: {text}; font-size: 12.5px;
}}
#shortcutDlg QTreeWidget {{
  border: 1px solid {menu_border}; border-radius: 6px; background: {input_bg};
  font-size: 13px; color: {text}; outline: 0;
}}
#shortcutDlg QTreeWidget::item {{ height: 28px; border-radius: 6px; }}
#shortcutDlg QTreeWidget::item:selected {{ background: {accent_soft}; color: {accent}; }}
#shortcutDlg QHeaderView::section {{
  background: {bg_soft}; border: none; border-bottom: 1px solid {sep};
  padding: 6px 8px; font-size: 12px; color: {text_muted};
}}
#shortcutDlg QKeySequenceEdit {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 6px 10px; background: {input_bg};
  color: {text};
}}
#shortcutDlg QKeySequenceEdit:focus {{ border-color: {accent}; }}
#hint {{ color: {text_muted}; font-size: 11.5px; }}
#settingsDlg {{ background: {bg}; }}
#settingsDlg QLabel {{ color: {text_soft}; font-size: 12.5px; background: transparent; }}
#settingsDlg #navList {{
  background: {bg_soft}; border: none; border-right: 1px solid {border};
  font-size: 13.5px; color: {text}; outline: 0; padding-top: 8px;
}}
#settingsDlg #navList::item {{ padding: 9px 16px; margin: 2px 8px; border-radius: 6px; }}
#settingsDlg #navList::item:hover {{ background: {list_hover}; }}
#settingsDlg #navList::item:selected {{ background: {accent_soft}; color: {accent}; }}
#settingsDlg #pageTitle {{ font-size: 17px; font-weight: 600; color: {text}; }}
#settingsDlg #pageHint {{ color: {text_muted}; font-size: 12px; }}
#settingsDlg QGroupBox {{
  border: 1px solid {border}; border-radius: 9px; margin-top: 8px;
  background: {bg_soft}; font-weight: 600; padding-top: 4px;
}}
/* v3.29d：组框标题呈「嵌入式图例」—— 标题垂直中点压在顶部边框线上，
   文字底下垫页面底色，边框线在文字处断开（fieldset legend 视觉效果） */
#settingsDlg QGroupBox::title {{
  subcontrol-origin: border; subcontrol-position: top left;
  left: 12px; top: -7px; padding: 0 5px;
  background: {bg}; color: {accent}; font-size: 12px; font-weight: 600;
}}
#settingsDlg QCheckBox {{ color: {text}; font-size: 12.5px; }}
#settingsDlg QLineEdit, #settingsDlg QComboBox {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 4px 9px;
  background: {input_bg}; color: {text};
}}
#settingsDlg QSpinBox {{
  border: 1px solid {input_border}; border-radius: 6px; padding: 4px 9px;
  background: {input_bg}; color: {text};
}}
#settingsDlg #themeList {{
  background: {input_bg}; border: 1px solid {menu_border};
  border-radius: 6px; color: {text}; outline: 0;
}}
#settingsDlg #themeList::item {{ padding: 8px 10px; border-radius: 6px; }}
#settingsDlg #themeList::item:hover {{ background: {list_hover}; }}
#settingsDlg #themeList::item:selected {{ background: {accent_soft}; color: {accent}; }}
/* v3.48.39（AI-MENU-BG）：AI 菜单页列表补 settingsDlg 级样式，与 #themeList
   完全同源 —— 此前仅落回通用 QDialog QListWidget，在滚动区内 viewport 未随主题
   着色，深色主题下呈白底，与本页组框及其他列表页不统一。 */
#settingsDlg #aiMenuList {{
  background: {input_bg}; border: 1px solid {menu_border};
  border-radius: 6px; color: {text}; outline: 0;
}}
#settingsDlg #aiMenuList::item {{ padding: 8px 10px; border-radius: 6px; }}
#settingsDlg #aiMenuList::item:hover {{ background: {list_hover}; }}
#settingsDlg #aiMenuList::item:selected {{ background: {accent_soft}; color: {accent}; }}
#settingsDlg QSlider::groove:horizontal {{ height: 4px; background: {sep}; border-radius: 2px; }}
#settingsDlg QSlider::handle:horizontal {{
  width: 14px; height: 14px; margin: -6px 0; border-radius: 6px; background: {accent};
}}
#settingsDlg QPushButton {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 6px;
  padding: 5px 14px; color: {text};
}}
#settingsDlg QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
#settingsDlg QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
/* v3.39.7（HIST-2）：历史版本对话框 —— 按钮禁用态明显置灰 */
#historyDlg {{ background: {bg}; }}
#historyDlg QLabel {{ color: {text_soft}; font-size: 13px; background: transparent; }}
#historyDlg QPushButton {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 6px;
  padding: 6px 14px; color: {text};
}}
#historyDlg QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
#historyDlg QPushButton:disabled {{
  background: {bg_soft}; color: {text_muted}; border-color: {sep};
}}
/* v3.47.4（REQ3）：合并版本对话框 —— 对照双栏只读 + 可编辑合并结果 */
#mergeDlg {{ background: {bg}; }}
#mergeDlg QLabel {{ color: {text_soft}; font-size: 12.5px; background: transparent; }}
#mergeDlg #pageTitle {{ font-size: 16px; font-weight: 600; color: {text}; }}
#mergeDlg #pageHint {{ color: {text_muted}; font-size: 12px; }}
#mergeDlg #mergeViewA, #mergeDlg #mergeViewB, #mergeDlg #mergeEdit {{
  border: 1px solid {input_border}; border-radius: 8px; padding: 8px;
  background: {input_bg}; color: {text}; font-size: 13px;
  font-family: 'Consolas', 'Microsoft YaHei', monospace;
}}
#mergeDlg #mergeEdit {{ background: {bg_soft}; }}
#mergeDlg QPushButton {{
  background: {btn_bg}; border: 1px solid {btn_border}; border-radius: 6px;
  padding: 6px 14px; color: {text}; font-size: 12.5px;
}}
#mergeDlg QPushButton:hover {{ background: {btn_hover_bg}; border-color: {btn_hover_border}; }}
#mergeDlg QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
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
