# -*- coding: utf-8 -*-
"""应用级常量与配置。"""
import json
import os
import sys

APP_NAME = "mdEditor"

# v3.32（P0-6①）：版本号统一由此维护（关于页 / 检查更新 / 诊断信息共用）
APP_VERSION = "3.38.0"

# v3.32（P0-6①）：检查更新源。留空 = 功能存在但提示"未配置更新源"；
# 可在 QSettings 里写 updateUrl 覆盖（JSON：{"version":"x.y.z","url":"下载页"}）
UPDATE_URL = ""

if getattr(sys, "frozen", False):  # PyInstaller 打包后资源目录
    HERE = sys._MEIPASS
else:
    HERE = os.path.dirname(os.path.abspath(__file__))

# v3.32（P0-1/P0-5）：用户数据目录（草稿 / 日志）。
# 草稿 = 未命名文档的影子落盘；日志 = 滚动文件，供"复制诊断信息"使用。
USER_DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                             "mdEditor")
DRAFT_DIR = os.path.join(USER_DATA_DIR, "drafts")
LOG_DIR = os.path.join(USER_DATA_DIR, "logs")
# v3.32.2（TPL-C）：模板持久化文件。
# v3.36（TPL-E）：内置模板并入统一列表后，文件形态为
#   {"v": 2, "templates": [{"name": str, "content": str, "ic"?: str}, ...]}
# 旧版（纯数组 [{name, content}]）仍可读入并自动迁移；"v" 同时充当
# 「内置模板已并入」的迁移标记（不再需要 QSettings 开关，换机器 / 清配置后
# 行为一致）。
TEMPLATE_FILE = os.path.join(USER_DATA_DIR, "templates.json")
# v3.35（TPL-D）：「设为模板文件」的名称与体积约束。
# 名称上限 30 字 —— 该名称会显示在 / 菜单「模板」二级里，
# 过长会撑破菜单宽度，故 30 为**显示长度上限**：三处同源
# （config.TPL_NAME_MAX / mainwindow.normalize_template_name / editor.html TPL_NAME_MAX）。
TPL_NAME_MAX = 10   # v3.38（TPL-F）：30 → 10（名称显示上限，三处同源）
# 内容上限 200KB —— 防止把超大文件设为模板导致菜单构建 / 插入卡顿
TPL_MAX_BYTES = 200 * 1024
# v3.36（TPL-E）：templates.json 结构版本。v1 = 早期纯数组（无内置模板）；
# v2 = 内置模板已并入统一列表（首次读入旧文件 / 缺失文件时自动补齐并写回 v2）；
# v3 = 内置模板重排为默认顺序（v3.38 TPL-F，一次性迁移，自建模板排其后）。
TPL_FILE_VERSION = 3

# v3.38（FLP-1）：文件列表（侧栏「文件」页）的**默认打开路径**。
# 取值规则：
#   · 空字符串（默认）= 不启用 —— 侧栏回退到「此电脑」盘符层
#   · 绝对路径（如 E:\notes 或 \\server\share\docs）= 原样使用
#   · 相对路径 = 相对**应用目录** HERE 解析（与启动时的当前工作目录无关，
#     保证从任何位置启动行为一致）
#   · 以 ~ 开头 = 展开为用户主目录
# 安全回退：路径不存在 / 不是目录 / 无访问权限时一律回退到根层，不弹窗不报错。
# 运行期可在「系统设置 → 通用 → 文件与启动」修改（QSettings 键 files/defaultDir，
# 该键优先于本默认值）。
FILE_LIST_DEFAULT_DIR = ""

# v3.36（TPL-E）：内置模板（模板体系的权威源）。
# 首次运行 / 从 v1 迁移时并入 templates.json，此后与自建模板同等管理
# （可改名 / 改内容 / 删除 / 调整顺序）。ic 为 / 菜单里的图标，缺省走 ⭐。
# 注意：editor.html 的 TPL_BUILTIN 是「独立打开 editor.html（未经 Python 下发）」时的
# 兜底副本，内容需与本表保持一致。
BUILTIN_TEMPLATES = [
    {"ic": "👥", "name": "会议纪要", "content": (
        "# 会议纪要\n\n- 时间：\n- 地点 / 线上：\n- 参会人：\n\n## 议题与讨论\n\n1. \n\n"
        "## 决议\n\n- \n\n## 行动项\n\n| 事项 | 负责人 | 截止时间 |\n| ---- | ------ | -------- |\n"
        "|      |        |          |")},
    {"ic": "🗓", "name": "周报", "content": (
        "# 周报（YYYY-MM-DD ~ MM-DD）\n\n## 本周完成\n\n1. \n\n## 进行中\n\n- \n\n"
        "## 下周计划\n\n1. \n\n## 需要支持\n\n- 无")},
    {"ic": "📋", "name": "需求文档", "content": (
        "# 需求文档：\n\n- 需求编号：\n- 提出人 / 日期：\n- 优先级：P0 / P1 / P2\n"
        "- 关联版本：\n\n## 1 背景与目标\n\n（为什么做，给谁解决什么问题）\n\n"
        "## 2 用户场景\n\n| 角色 | 场景 | 诉求 |\n| ---- | ---- | ---- |\n"
        "|      |      |      |\n\n## 3 功能需求\n\n"
        "| 编号 | 需求描述 | 优先级 | 验收标准 |\n| ---- | -------- | ------ | -------- |\n"
        "| R1   |          | P0     |          |\n\n## 4 非功能需求\n\n"
        "- 性能：\n- 兼容性：\n- 安全与隐私：\n\n## 5 不在范围内\n\n- \n\n"
        "## 6 风险与依赖\n\n- ")},
    {"ic": "🎨", "name": "设计文档", "content": (
        "# 设计文档：\n\n- 作者 / 日期：\n- 关联需求：\n- 状态：草稿 / 评审中 / 已定稿\n\n"
        "## 1 目标与约束\n\n## 2 总体设计\n\n```mermaid\nflowchart LR\n"
        "  A[入口] --> B[核心模块]\n  B --> C[存储]\n```\n\n## 3 模块设计\n\n"
        "| 模块 | 职责 | 关键接口 |\n| ---- | ---- | -------- |\n"
        "|      |      |          |\n\n## 4 数据结构\n\n## 5 关键流程\n\n1. \n\n"
        "## 6 兼容性与迁移\n\n## 7 测试要点\n\n- [ ] \n\n## 8 备选方案与取舍")},
    {"ic": "📝", "name": "技术笔记", "content": (
        "# 技术笔记：\n\n## 背景\n\n（为什么记录这篇笔记）\n\n## 关键结论\n\n- \n\n"
        "## 详细内容\n\n\n## 参考\n\n- ")},
    {"ic": "📦", "name": "项目文档", "content": (
        "# 项目文档\n\n## 项目概述\n\n（一句话说明项目目标）\n\n## 范围\n\n"
        "| 阶段 | 内容 | 负责人 | 状态 |\n| ---- | ---- | ------ | ---- |\n"
        "|      |      |        |      |\n\n## 里程碑\n\n- [ ] \n\n## 风险与依赖\n\n- ")},
    {"ic": "🧐", "name": "评审记录", "content": (
        "# 评审记录\n\n- 日期：\n- 参与人：\n- 评审对象：\n\n## 结论\n\n"
        "（通过 / 有条件通过 / 不通过）\n\n## 意见与行动项\n\n"
        "| # | 意见 | 类型 | 责任人 | 截止 |\n| - | ---- | ---- | ------ | ---- |\n"
        "| 1 |      |      |        |      |")},
    {"ic": "🎓", "name": "论文骨架", "content": (
        "# 论文标题\n\n## 摘要\n\n（200 字左右概述研究问题、方法与结论）\n\n## 1 引言\n\n"
        "## 2 相关工作\n\n## 3 方法\n\n## 4 实验与结果\n\n"
        "| 方法 | 指标 1 | 指标 2 |\n| ---- | ------ | ------ |\n|      |        |        |\n\n"
        "## 5 讨论\n\n## 6 结论\n\n## 参考文献\n\n[^1]: ")},
]

# v3.34（MMD-11）：图表主题（与 editor.html 的 MMD_THEMES 同源；空 id = 跟随界面主题）
# 顺序需与内核 window.mmdMenuItems() 一致（设置面板下拉 / 右键子菜单同一份清单）
MMD_THEMES = [("跟随界面主题", ""), ("晴空", "azure"), ("薄荷", "mint"), ("暖沙", "sepia"),
              ("石墨", "graphite"), ("暗夜", "night"), ("琥珀", "ember"),
              ("黑白", "mono")]   # v3.38（MMD-12）：新增黑白（浅色界面默认）
MMD_THEME_LABELS = dict((v, k) for k, v in MMD_THEMES)
# 旧版（MMD-7）原生 mermaid 主题值 → 新主题（升级用户 QSettings 无缝过渡）
MMD_LEGACY = {"default": "azure", "dark": "night", "forest": "mint", "neutral": "graphite"}

# 支持打开的文件扩展名
MD_EXTS = (".md", ".markdown", ".mdown", ".txt")

# 三种编辑模式：(内部标识, 图标名, 名称, 一句话说明)
MODES = [
    ("edit", "write", "写作模式", "所见即所得，像 Typora 一样边写边渲染"),
    ("src", "code", "源码模式", "直接编辑 Markdown 源代码"),
    ("dual", "split", "分屏模式", "左侧源码 · 右侧实时预览"),
]


def js(s: str) -> str:
    """把 Python 字符串变成合法的 JS 字符串字面量。"""
    return json.dumps(s)


DEMO_MD = """# 欢迎使用 mdEditor

这是一款 **所见即所得** 的 Markdown 编辑器：点击任意位置即可编辑，
光标所在段落显示原始语法，其余内容 *实时渲染* —— 体验与 Typora 一致。

## 快速上手

- 直接输入 `# ` 创建标题，`- ` 创建列表，`> ` 创建引用
- 空行输入 `/` 可唤起 **插入菜单**（标题、表格、代码块、公式、图表…）
- 选中文字浮现 **行编辑菜单**，悬停块前 `⠿` 可整块操作
- 使用 ``Ctrl+B`` **加粗**、``Ctrl+I`` *斜体*、``Ctrl+E`` `行内代码`
- ``Ctrl+1`` / ``Ctrl+2`` / ``Ctrl+3`` 一键设置标题层级
- 按 ``Ctrl+Enter`` 从代码块 / 引用中跳出
- ``Ctrl+Shift+D`` 切换 **分屏模式**（左源码 / 右预览）
- 「设置 → 系统设置」或左侧齿轮按钮可切换 **六套主题** 全局换肤
- 顶部标签页可同时编辑多个文件

## 数学公式

行内公式：质能方程 $E = mc^2$，块级公式：

```math
\\int_{-\\infty}^{+\\infty} e^{-x^2} \\, dx = \\sqrt{\\pi}
```

## 图表（Mermaid）

空行输入 `/` 选择「图表」可插入流程图、时序图、类图、状态图、E-R 图等，
双击图表可回到源码编辑：

```mermaid
flowchart TD
  A[打开文档] --> B{是否编辑?}
  B -->|是| C[所见即所得编辑]
  B -->|否| D[阅读预览]
  C --> E[自动保存]
  D --> E
```

## 表格与任务

| 功能   | 状态 | 快捷键   |
| ------ | :--: | -------- |
| 加粗   |  ✅  | Ctrl+B   |
| 斜体   |  ✅  | Ctrl+I   |
| 图表   |  ✅  | 输入 /   |
| 导出PDF |  ✅  | 文件菜单 |

## 3 分钟上手清单

- [ ] 空行输入 `/` 打开插入菜单，选一个「模板」开始写作
- [ ] 试试表格：插入后右键单元格可 **合并 / 拆分**（对标 Office）
- [ ] 插入一张图片（直接粘贴截图也可以）
- [ ] 输入一个公式：`/` → 公式，或按 ``Ctrl+Shift+M``
- [ ] 导出一次 PDF 或 Word（文件菜单），交付给别人看
- [ ] 按 ``Ctrl+Shift+P`` 打开命令面板，搜索任何功能

> 提示：有路径的文档会自动保存；未命名文档的内容会自动暂存为草稿，
> 下次启动时可恢复。拖拽 .md 文件到窗口即可打开。
"""
