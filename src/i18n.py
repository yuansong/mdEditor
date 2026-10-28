# -*- coding: utf-8 -*-
"""国际化（i18n）基础设施：界面语言读取 / 保存 + T() 取词。

设计要点
--------
- 以「中文原文」为 key，英文译文存于 EN 字典（zh -> en）。
- ``T(zh)`` 在中文环境下原样返回；英文环境下返回 EN[zh]，缺失译文时
  回退到调用方传入的 en 参数（若有）或原中文，**绝不抛错、绝不显示 key**。
- 动态串（含 f-string 变量）请用 ``T(f"中文{n}", f"English {n}")`` 形式，
  英文模式直接返回已格式化的 en 参数。
- 语言存于 QSettings("WorkBuddy", "WorkBuddyMarkdown") 的 "language" 键，
  "zh" / "en" 二选一，缺省 "zh"。

用法
----
    from i18n import T, get_lang, set_lang
    self.setWindowTitle(T("系统设置"))
    self.setWindowTitle(T(f"关闭选中的 {n} 个标签页", f"Close selected {n} tabs"))
"""
from PySide6.QtCore import QSettings

APP_ORG = "WorkBuddy"
APP_NAME = "WorkBuddyMarkdown"
LANG_KEY = "language"
DEFAULT_LANG = "zh"
SUPPORTED = ("zh", "en")

# 中文 -> 英文 译文表（随翻译推进持续扩充）
EN = {
    # ---- 通用动作 ----
    "确定": "OK", "取消": "Cancel", "应用": "Apply", "关闭": "Close", "打开": "Open",
    "保存": "Save", "另存为": "Save As", "删除": "Delete", "重命名": "Rename",
    "复制": "Copy", "粘贴": "Paste", "剪切": "Cut", "全选": "Select All",
    "清空": "Clear", "重置": "Reset", "还原默认设置": "Restore Defaults",
    "添加": "Add", "移除": "Remove", "上移": "Move Up", "下移": "Move Down",
    "启用": "Enable", "禁用": "Disable", "是": "Yes", "否": "No",
    "确定要删除吗？": "Are you sure you want to delete this?",
    "操作成功": "Operation succeeded", "操作失败": "Operation failed",

    # ---- 设置导航 / 页面 ----
    "通用": "General", "编辑器": "Editor", "写作与输入": "Writing & Input",
    "模板": "Templates", "AI 菜单": "AI Menus", "AI 连接": "AI Connection",
    "系统设置": "Settings", "界面语言": "Interface Language",
    "中文": "Chinese", "英文": "English",
    "编辑区显示": "Editor Display", "编辑区字号缩放": "Editor Zoom",
    "图片存储": "Image Storage",
    "图片存放方式": "Image Storage Mode",
    "相对路径：保存到「文档名.assets」文件夹（推荐）": "Relative path: save to 'docname.assets' folder (recommended)",
    "内嵌 data URL：图片写进文档本身": "Embed as data URL: image written into the document",
    "代码块外观": "Code Block Appearance",
    "默认语言（插入代码块时预选，可输入自定义值）": "Default language (preselected when inserting a code block, customizable)",
    "代码块显示行号": "Show line numbers in code blocks",

    # ---- 文件 / 编辑菜单 ----
    "文件": "File", "编辑": "Edit", "视图": "View", "插入": "Insert",
    "格式": "Format", "帮助": "Help",
    "新建": "New", "打开文件": "Open File", "打开文件夹": "Open Folder",
    "保存全部": "Save All", "导出": "Export", "导入": "Import",
    "打印": "Print", "退出": "Exit",
    "撤销": "Undo", "重做": "Redo", "剪切": "Cut", "复制": "Copy",
    "粘贴": "Paste", "查找 / 替换": "Find / Replace", "查找": "Find",
    "全选": "Select All",

    # ---- 视图 / 外观 ----
    "显示 / 隐藏状态栏": "Show / Hide Status Bar",
    "显示 / 隐藏 AI 助手": "Show / Hide AI Assistant",
    "界面风格": "UI Style", "主题": "Theme", "图表风格": "Diagram Style",
    "代码风格": "Code Style",
    "写作模式": "Writing Mode", "源码模式": "Source Mode", "分屏模式": "Split Mode",
    "所见即所得，像 Typora 一样边写边渲染": "WYSIWYG, write and render like Typora",
    "直接编辑 Markdown 源代码": "Edit the Markdown source directly",
    "左侧源码 · 右侧实时预览": "Source on the left, live preview on the right",

    # ---- 标签右键 / 多标签 ----
    "关闭选中的 %d 个标签页": "Close selected %d tabs",
    "固定 / 取消固定标签": "Pin / Unpin Tab",
    "关闭其它所有": "Close All Others",
    "关闭左侧所有": "Close All to the Left",
    "关闭右侧所有": "Close All to the Right",
    "关闭所有未修改": "Close All Unmodified",
    "关闭所有标签页": "Close All Tabs",
    "在资源管理器中显示": "Show in Explorer",
    "在终端中打开": "Open in Terminal",
    "复制文件名": "Copy File Name",
    "复制文件路径": "Copy File Path",
    "复制所在目录": "Copy Directory",
    "切换标签页": "Switch Tab",
    "批量关闭": "Batch Close",

    # ---- 对话框 ----
    "查找 / 替换": "Find / Replace",
    "快捷键设置": "Keyboard Shortcuts",
    "命令面板": "Command Palette",
    "版本对比": "Version Compare",
    "格式化操作日志": "Format Operation Log",
    "历史版本": "History",
    "合并版本": "Merge Versions",
    "插入图片": "Insert Image",
    "界面风格管理": "UI Style Manager",
    "请输入命令名称 / 拼音首字母 / 快捷键，回车执行…": "Type a command name / pinyin initials / shortcut, press Enter to run…",

    # ---- AI 面板 ----
    "AI 助手": "AI Assistant",
    "连接设置": "Connection Settings",
    "发送": "Send", "停止": "Stop", "清空对话": "Clear Chat",
    "复制": "Copy", "插入到光标处": "Insert at Cursor",
    "改写选中内容": "Rewrite Selection",
    "问 AI": "Ask AI",
    "未配置 AI 连接，点击「连接设置」进行配置": "No AI connection configured. Open 'Connection Settings' to set it up",
    "正在思考…": "Thinking…", "等待响应…": "Waiting for response…",

    # ---- 状态 / 提示 ----
    "已保存": "Saved", "已自动保存": "Auto-saved",
    "文档已修改": "Document modified", "就绪": "Ready",
    "加载中…": "Loading…", "生成中…": "Generating…",

    # ---- 设置 / 对话框（补充） ----
    "Emoji 自动补全（正文输入「:」+ 名称弹出候选）": "Emoji autocomplete (type ':' + name in body to show candidates)",
    "Pandoc 路径": "Pandoc Path",
    "· 0 = 不保留最近文件（菜单项隐藏）": "· 0 = do not keep recent files (menu item hidden)",
    "一级菜单默认选项": "Default Top-level Menu Item",
    "上一个": "Previous", "下一个": "Next",
    "上次编辑的文档（预览）": "Last edited document (preview)",
    "与上一版本对比": "Compare with previous version",
    "与当前文档对比": "Compare with current document",
    "专注模式（淡化非当前段落）": "Focus mode (dim non-current paragraphs)",
    "全局搜索": "Global Search", "全部替换": "Replace All",
    "公式默认": "Default Formula", "列表默认": "Default List",
    "删除所选": "Delete Selected", "刷新": "Refresh",
    "单栏": "Single Pane", "双栏": "Two Panes",
    "历史版本保留份数": "History Versions Kept",
    "合并所选两项": "Merge Selected Two",
    "启动": "Startup", "启动时": "On Startup",
    "启动时打开的文件夹": "Folder to open on startup",
    "启用本地语义搜索（查找 → 全局搜索 → 语义搜索）": "Enable local semantic search (Find → Global Search → Semantic Search)",
    "图片文件或网络地址": "Image file or URL",
    "图表默认": "Default Chart", "在文件夹中显示": "Show in Folder",
    "外部编辑器": "External Editor", "始终空白": "Always Blank",
    "实时（每次改动即写盘）": "Real-time (write on every change)",
    "对比所选两项": "Compare Selected Two",
    "导出为文本…": "Export as Text…",
    "应用到当前文档": "Apply to Current Document", "当前文件": "Current File",
    "恢复上次会话（多标签 + 位置，默认）": "Restore last session (tabs + positions, default)",
    "恢复上次打开的文件": "Restore last opened file",
    "恢复全部默认": "Restore All Defaults", "恢复内置": "Restore Built-in",
    "恢复此版本": "Restore This Version",
    "打字机模式（光标所在行始终居中）": "Typewriter mode (cursor line always centered)",
    "打开指定文件夹": "Open specified folder", "打开欢迎页": "Open welcome page",
    "提示": "Tip",
    "支持拖拽整段调序；右键可跳转 / 复制标题 / 展开折叠 / 移到首尾": "Drag to reorder; right-click to jump / copy title / expand-collapse / move to start or end",
    "文件列表": "File List", "斜杠（/）菜单": "Slash (/) Menu",
    "显示分节字数（标题后追加「· N 字」）": "Show section word count (append '· N words' after title)",
    "显示级别（超过该级别的标题默认折叠）": "Display level (headings beyond this level are collapsed by default)",
    "替换": "Replace", "最近文件保留": "Recent Files Kept",
    "未打开文件时显示": "Show when no file is open",
    "本地语义搜索": "Local Semantic Search",
    "标题 1 始终居中显示（导出跟随；单个标题可用格式栏按钮单独切换）": "Heading 1 always centered (follows on export; per-heading toggle via format bar button)",
    "标题默认": "Default Heading",
    "段落与标题": "Paragraph & Heading",
    "段首缩进（每段首行空出的格数）": "Paragraph indent (spaces before first line of each paragraph)",
    "每 30 秒": "Every 30 seconds", "每 5 分钟": "Every 5 minutes",
    "浏览…": "Browse…", "清空日志文件…": "Clear log file…",
    "版本历史": "Version History",
    "用上移 / 下移调整一级菜单优先级顺序": "Use Move Up / Move Down to adjust top-level menu priority",
    "插入": "Insert", "复制全部": "Copy All",
    "自动保存（编辑后自动写入文件）": "Auto-save (write to file after editing)",
    "自动配对括号 / 引号（选中文字可直接用符号包裹）": "Auto-pair brackets / quotes (wrap selected text directly)",
    "范围": "Scope", "菜单名称": "Menu Name",
    "菜单名称不能为空。": "Menu name cannot be empty.",
    "输入辅助": "Input Assistance",
    "选中功能后录制快捷键，松开即生效并保存；Esc / 单键将被忽略。": "After selecting a feature, press the shortcut; it takes effect and saves on release; Esc / single key is ignored.",
    "请先在列表中选择一个菜单项。": "Please select a menu item in the list first.",
    "重建索引": "Rebuild Index", "风格文件夹…": "Style Folder…",
    # AI 菜单页
    "自定义两处「AI优化」菜单的菜单项名称与提示词。提示词留空表示使用内置提示词（翻译会按内容语种自动定向）。设置即时生效。":
        "Customize menu item names and prompts for the two 'AI Optimize' menus. Empty prompt uses the built-in prompt (auto-directed by content language). Takes effect immediately.",
    "框选文字后 · 右键「AI优化」": "After selecting text · right-click 'AI Optimize'",
    "选中文章后 · 文件列表 / 标签右键「AI优化」": "After selecting article · right-click 'AI Optimize' in file list / tab",
    "添加…": "Add…", "编辑…": "Edit…", "恢复默认": "Restore Defaults",
    "恢复该菜单为内置菜单项？自定义项将被清除。": "Restore this menu to built-in items? Custom items will be cleared.",
    "提示词（内置项已预填内置提示词，保持原样即继续使用内置；自定义提示词请写明「只输出结果文本本身，不要附加解释」）":
        "Prompt (built-in items are pre-filled with the built-in prompt; keeping as-is continues using it; for custom prompts specify 'output only the result text itself, no extra explanation')",
    "例如：请把下面的文本改写成 FAQs 问答对，每条以「Q: / A:」开头，不要附加解释。":
        "e.g.: rewrite the text below into FAQ Q&A pairs, each starting with 'Q: / A:', no extra explanation.",
    # 占位符
    "留空 = 不定位": "Leave empty = no location",
    "留空 = 自动探测；未安装 pandoc 时使用内置转换": "Leave empty = auto-detect; use built-in conversion if pandoc is not installed",
    "留空 = 系统默认关联程序（可填 Notepad++ / VS Code 等可执行文件）": "Leave empty = system default association (can fill in Notepad++ / VS Code etc. executable)",
    # 占位符（补充）
    "替换为…": "Replace with…",
    "搜索内容（支持正则，如 \\d+、https?://…）": "Search content (regex supported, e.g. \\d+, https?://…)",
    "输入命令名称 / 拼音首字母 / 快捷键，回车执行…": "Type a command name / pinyin initials / shortcut, press Enter to run…",
    "选择 / 粘贴本地图片完整路径，或 https:// 图片地址…": "Select / paste the full local image path, or an https:// image URL…",
    "（选择左侧快照查看内容）": "(Select a snapshot on the left to view content)",
    "# 标题\n\n正文…": "# Title\n\nBody…",
    # 语言选择器
    "语言": "Language",
    "切换后菜单栏 / 工具栏 / 编辑器内核立即刷新，其余对话框重开生效": "After switching, the menu bar / toolbar / editor kernel refresh immediately; other dialogs apply after reopening",

    # ---- 补全（源码侧实际用到的静态串） ----
    "工具": "Tools",
    "外观": "Appearance",
    "大纲": "Outline",
    "最近文件": "Recent Files",
    "主工具栏": "Main Toolbar",
    "保存时机": "Save Timing",
    "另存为…": "Save As…",
    "复制为 HTML（公众号 / Word 富文本）": "Copy as HTML (WeChat / Word rich text)",
    "收起侧边栏 (Ctrl+Shift+L)": "Collapse Sidebar (Ctrl+Shift+L)",
    "展开侧边栏 (Ctrl+Shift+L)": "Expand Sidebar (Ctrl+Shift+L)",
    "AI 助手（点击展开 / 收起，默认连接本地 Ollama）": "AI Assistant (click to expand / collapse; connects to local Ollama by default)",

    # ---- 菜单动作名（_reg_act 注册的菜单项标签） ----
    "上一标签页": "Previous Tab", "下一标签页": "Next Tab",
    "专注模式": "Focus Mode", "打字机模式": "Typewriter Mode",
    "使用手册": "User Manual", "全屏": "Full Screen",
    "全部保存": "Save All", "关于": "About",
    "关闭所有标签": "Close All Tabs", "关闭标签页": "Close Tab",
    "重新打开关闭的标签": "Reopen Closed Tab",
    "前进": "Forward", "后退": "Back",
    "历史版本…": "Version History…", "立即留档（版本快照）": "Snapshot Now (version snapshot)",
    "反向链接页签": "Backlinks Tab", "大纲页签": "Outline Tab", "文件列表页签": "File List Tab",
    "命令面板…": "Command Palette…", "标签快切面板": "Tab Quick-Switch Panel",
    "在文件夹中搜索…": "Search in Folder…", "复制诊断信息": "Copy Diagnostic Info",
    "块菜单": "Block Menu", "导入表格…": "Import Table…",
    "导出 HTML…": "Export HTML…", "导出 PDF…（含书签）": "Export PDF… (with bookmarks)",
    "导出 Word (docx)…": "Export Word (docx)…", "导出 EPUB…": "Export EPUB…",
    "导出图片 (PNG)…": "Export Image (PNG)…",
    "展开全部标题": "Expand All Headings", "折叠全部标题": "Collapse All Headings",
    "归档整个工作区…": "Archive Entire Workspace…", "快捷键设置…": "Keyboard Shortcuts…",
    "打开…": "Open…", "打开书籍…": "Open Book…", "打开文件夹…": "Open Folder…",
    "新建书籍…": "New Book…",
    "显示 / 隐藏侧边栏": "Show / Hide Sidebar", "显示 / 隐藏工具栏": "Show / Hide Toolbar",
    "替换…": "Replace…", "查找…": "Find…", "转到行…": "Go to Line…",
    "检查更新…": "Check for Updates…", "系统设置…": "Settings…",
    "放大": "Zoom In", "缩小": "Zoom Out", "重置缩放": "Reset Zoom",
    "迁移内嵌图片为文件…": "Migrate Embedded Images to Files…",
    "选择下一个相同词": "Select Next Matching Word",
}


def get_lang():
    """返回当前界面语言（'zh' / 'en'），缺省 'zh'。"""
    s = QSettings(APP_ORG, APP_NAME)
    v = s.value(LANG_KEY, DEFAULT_LANG)
    return v if v in SUPPORTED else DEFAULT_LANG


def set_lang(lang):
    """设置并持久化界面语言；非法值回退 'zh'。"""
    if lang not in SUPPORTED:
        lang = DEFAULT_LANG
    s = QSettings(APP_ORG, APP_NAME)
    s.setValue(LANG_KEY, lang)
    return lang


def T(zh, en=None):
    """按当前语言取词。

    - 中文环境：返回 zh（en 参数被忽略）。
    - 英文环境：优先返回 en 参数，否则返回 EN[zh]，再否则返回 zh（回退）。
    """
    if get_lang() == "en":
        if en is not None:
            return en
        return EN.get(zh, zh)
    return zh
