# -*- coding: utf-8 -*-
"""应用级常量与配置。"""
import json
import os
import sys

APP_NAME = "mdEditor"

if getattr(sys, "frozen", False):  # PyInstaller 打包后资源目录
    HERE = sys._MEIPASS
else:
    HERE = os.path.dirname(os.path.abspath(__file__))

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
- 「视图 → 主题」或左侧齿轮按钮可切换 **六套主题** 全局换肤
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

- [x] 支持所见即所得编辑
- [x] 支持实时预览与导出
- [ ] 开始写下你的第一篇文档吧！

> 提示：文档会自动保存。拖拽 .md 文件到窗口即可打开。
"""
