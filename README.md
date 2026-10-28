# mdEditor

Typora 风格的**所见即所得**（块级 WYSIWYG）Markdown 编辑器，**开源、跨平台**的桌面应用（Windows / Linux / macOS）。
Python + PySide6 (QtWebEngine) 外壳 + 单文件 JS 编辑内核 `src/editor.html`，全部能力离线可用（KaTeX / Mermaid 均内置）；并内建**端侧可控的 AI 写作能力**——15 家主流大模型 BYOK + 本地 Ollama 原生推理，智能生成 / 语义级改写 / 本地语义检索均可离线运行，密钥与文本始终由用户掌控。

> 当前版本 **v3.48.38**（`src/config.py: APP_VERSION`）。
> 仓库：<https://github.com/yuansong/mdEditor> · 许可：**Apache-2.0**（见 [LICENSE](LICENSE)）。
> 「现在能用什么」看本文；「每个版本动了什么」看 [`CHANGELOG.md`](CHANGELOG.md)；「模块级功能明细」看 [`docs/功能列表-v3.31.md`](docs/功能列表-v3.31.md)；「开发 / AI 协作规则」看 [`AGENTS.md`](AGENTS.md)。

**mdEditor 的定位** —— 不只是 Typora 级的所见即所得，更是面向中文写作者与知识工作者的**本地优先、AI 原生** Markdown 工作台：以块级 WYSIWYG 写作手感为底座，叠加端侧可控的智能生成、语义理解与自动化处理能力，同时坚守「真 Markdown 文件、数据完全本地、零账号、离线可用」的隐私底线。

**核心差异化优势**

| 维度 | mdEditor 的差异化 |
|---|---|
| 中文写作全栈 | 全中文界面 + 中文输入法混输兼容 + CJK 排版与字数分计，竞品普遍未到位 |
| 端侧 AI 原生 | 15 家主流大模型 BYOK + 本地 Ollama 原生推理（免 Key）；智能生成、语义级改写、本地语义检索均可离线运行 |
| 表格护城河 | Office 级表格：合并 / 拆分 / 拖选 / 列宽行高写回，WYSIWYG 表格能力对标乃至超越 Typora |
| 长文档工作流 | 书籍 / 大纲 / 章节树 + 整本书 PDF·EPUB·HTML 站点导出，面向技术文档与知识沉淀 |
| 轻量离线 · 极速 | 绿色文件夹即拷即用、启动约 1.5s、完全离线（KaTeX / Mermaid / 语义检索零 CDN），无需账号 |
| 开源 · 跨平台 | Apache-2.0 已开源，Windows 持续发布、macOS / Linux 构建就绪，可审计、可社区共建 |

> 竞品各有取舍（Typora 闭源付费、Obsidian 偏知识库、VS Code 无就地渲染、SoloMD 表格弱），mdEditor 的差异化不在功能数量堆砌，而在**中文写作手感 + 端侧 AI + 轻量离线 + 表格 / 书籍护城河 + 现已开源跨平台**的深耦合。完整对标见 [`docs/competitive/COMPETITIVE.md`](docs/competitive/COMPETITIVE.md)。

---

## 一、快速开始

### 方式 1：直接运行打包产物（推荐，无需装环境）

```
distNN\mdEditor\mdEditor.exe                # 双击运行
distNN\mdEditor\mdEditor.exe path/to/note.md # 命令行带文件打开
```

> `NN` 是**每次打包递增的滚动序号**（如 `dist185`），属本地产物编号，文档不写死具体值；请以你本地存在的最大序号目录为准。

- 采用 PyInstaller **onedir** 模式：整个 `mdEditor` 文件夹缺一不可，只拷 exe 无法运行。
- `buildNN\` / `specNN\` 是打包中间产物，**其中的 exe 不能直接运行**，属正常现象。
- 最近一次成功打包的产物即本地序号最大的 `distNN`；另有跨平台脚本 `build.py`（输出 `dist/mdEditor/`）。要体验最新代码请用方式 2 从源码运行。

### 方式 2：从源码运行

环境（已在开发机验证）：

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.13.x | 建议使用 Python 3.13.x（venv 或系统 Python） |
| PySide6 | 6.11.2 | 必须含 `QtWebEngineWidgets` |
| python-docx | — | 导出 Word，缺失时该菜单项降级提示 |
| pypdf | — | PDF 书签，缺失时 PDF 仍可导出但无书签 |
| pandoc | 可选 | 配置路径后 docx / EPUB 导出优先走 pandoc |

```bash
# 在 venv 中安装依赖（一次性）
pip install PySide6 python-docx pypdf

# 运行
python src/main.py                 # 空文档启动
python src/main.py path/to/note.md # 打开指定文件
```

启动后：单实例互斥（二次启动会把文件参数转发给已运行实例）；命令行只取第一个存在的 `.md/.markdown/.mdown/.txt` 参数。

---

## 二、界面与调用方式

| 区域 | 内容 |
|---|---|
| 菜单栏 | 文件（「导出」子菜单）/ 编辑 / 视图 / 外观（界面风格·主题·图表风格·代码风格）/ 工具（系统设置·快捷键设置·历史版本·迁移图片·归档）/ 帮助；**右端视图状态区**：专注 / 打字机快捷开关 + 写作 \| 源码 \| 分屏分段钮（单击直切） |
| 左侧竖向工具栏 | 侧栏开关（面板图标）、新建、打开、保存、撤销、重做、查找、**历史版本**、系统设置 |
| 侧栏（三页） | 文件列表（磁盘目录树）、书籍列表（章节目录树）、大纲（级别 1~6、拖拽调序、分节字数）；跨文件全文检索在「查找 / 替换 → 全局搜索」页签（`Ctrl+Shift+F`） |
| 编辑区 | 块级渲染态直编；写作 / 源码 / 分屏三模式（`Ctrl+Shift+D` 分屏，双栏 160ms 同步滚动）；空行占位提示「输入 / …」 |
| 状态栏 | 消息区 · **模式**（点击循环）· 字数与阅读时长（点击明细）· 行列位置 · **缩放**（点击重置 100%）· **保存态**（✓ 已保存 / ● 未保存 / ⟳ 保存中）· 当前块类型 · ⌘ 命令入口 |

三个交互入口贯穿全编辑器：**斜杠菜单**（空行 `/`）、**块菜单**（`Ctrl+/` 或块左侧 `⠿`）、**命令面板**（`Ctrl+Shift+P`，支持汉字 / 拼音首字母 / 子序列匹配）。

---

## 三、功能总览

### 文档管理
多标签页（可拖动排序、未保存 `•` 标记）· 自动保存（有路径文档，700ms 轮询）· 未命名文档**影子草稿**（`%APPDATA%\mdEditor\drafts`，启动可恢复）· **版本历史**（保存前快照 + 60s 节流，`.mdeditor-history/`，可预览 / 恢复 / 行级三色 diff）· 最近文件 10 条 · 编码自动识别（BOM / UTF-8 / GBK）· 归档整个工作区。

### 编辑内核
块级所见即所得（存储恒为纯 Markdown）· 三视图模式 · 斜杠菜单 11 个一级项（标题 / 列表 / 表格 / 代码块 / 分割线 / 引用 / 图片 / 图表 / 脚注与定义 / 模板 / 公式）· 悬浮格式栏（粗 / 斜 / 下划线 / 删除线 / 高亮 / 行内码 / 链接 / 清除格式）· **渲染态直编**（标题 / 列表 / 引用 / 定义列表 / 脚注定义含行内格式时单击仍是渲染态）· 自动配对 · Emoji `:smile:` 补全 · 标题折叠 · 打字机 / 专注模式 · 超长文档懒渲染（≥400 块启用 IntersectionObserver）。

### 表格
拖选矩形选区 · 右键上下文菜单（**只显示当前可执行项**）· 行列增删 · 合并 / 拆分 · 单元格对齐 · 表格标注（caption，入口为块菜单 / 命令面板）· 网格键盘导航 · 列宽行高拖拽写回源码。

### 公式与图表
KaTeX 行内 `$...$` 与块级（25 个模板，离线）· Mermaid 七类图表（流程 / 时序 / 类 / 状态 / E-R / 甘特 / 饼图，双击回源码编辑，默认**自然尺寸**渲染）· 图表主题 8 项（跟随界面 + 晴空 / 薄荷 / 暖沙 / 石墨 / 暗夜 / 琥珀 / **黑白**，浅色界面默认黑白）。

### 代码块
103 种语言（可搜索、可手输、最近使用置顶，写入源码统一小写）· 4 种风格 + 行号开关（顶栏「语言 / 风格」两钮）· 轻量 tokenizer 高亮（关键字 / 字符串 / 注释 / 数字，聚焦时还原纯文本保光标）· Tab 插 2 空格与跨行批量缩进 · 复制全部代码 = **语言栏右键**或选中 `Ctrl+C` · 引用内代码块仅可编辑，切语言 / 风格 / 行号会给出明确 toast。

### 图片管理
本地落盘 `<文档名>.assets/`（5 位编号命名）或 Base64 内嵌双模式 · 粘贴截图自动落盘 · 内嵌图片批量迁移为文件 · 右键图注 / 尺寸 / 对齐 / 复制 / 重命名 / 转内嵌 / 转相对路径 / 下载网络图。

### 查找 · 导航
查找替换（正则 + 8 种预设 + 全部命中高亮，CSS Custom Highlight API）· 跨文件全局搜索（上限 1500 文件 / 单文件 1.5MB / 400 命中）· **本地语义检索**（TF-IDF + 同义词，离线近义召回）· 大纲树（纯文本、级别过滤、拖拽调序、分节字数）· 转到行 `Ctrl+G`。

### 导出
| 通道 | 说明 |
|---|---|
| HTML | **单文件离线**：KaTeX 字体 base64 内嵌、图表为静态 SVG、本地图片转 data URI，零 CDN |
| PDF | WebEngine 打印，按标题写入 PDF 书签（依赖 pypdf） |
| Word (.docx) | python-docx，代码块灰底等宽，图表位图化嵌 PNG |
| EPUB 3 | 纯标准库，按一级标题分章 + nav 目录 |
| 图片 (PNG) | 当前文档 / 选区导出为 PNG 位图 |
| pandoc 通道 | 配置了路径则优先走 pandoc（`gfm+tex_math_dollars --toc`） |
| 复制为 HTML | 富文本进剪贴板，可直接粘到 Word / 公众号 |

### 外观与设置
六套主题（浅色 / 青空 / 护眼米黄 / 深色 / 墨夜 / 熊猫，窗口 + 编辑区 + 弹层同步换肤）· 缩放 80%~160% · 系统设置五页（**通用 / 编辑器 / 写作与输入 / 模板 / AI 连接**）· 快捷键自定义与冲突检测 · 8 个内置模板 + 自建模板统一管理（名称上限 10 字，可改名 / 改内容 / 排序 / 恢复内置，也可在侧栏文件右键「设为模板…」）。

### AI 智能写作（端侧可控）

mdEditor 将大模型能力内建为写作闭环，而非外挂插件；默认本地优先、按需上云，**密钥与文本始终由用户掌控**。

- **多模型接入（BYOK）**：内置 15 家主流大模型服务（OpenAI / DeepSeek / 通义千问 / 智谱 GLM / Kimi / Gemini / Azure / OpenRouter / 硅基流动 / MiniMax / 百川 / Mistral / Together 等），含**本地 Ollama 原生推理（免 API Key、自动检测已装模型）**与「自定义 OpenAI 兼容端点」；默认连接本地 Ollama，云端服务按需填 Key，数据不出本机可控。
- **右键一键优化（语义级改写）**：框选文字后正文右键、或选中整篇后文件 / 标签右键，调出「AI 优化」菜单——润色 / 精简 / 扩写 / 纠错 / 翻译 / 改语气 / 选中提问七类动作（文档级六类），每项独立预设提示词，且菜单项可在「AI 连接」设置中自定义。
- **片段级可控采纳**：AI 改写结果以**片段 diff** 呈现，可逐处采纳或回退，全程 `Ctrl+Z` 可撤销，绝不无声覆盖原文。
- **流式 AI 问答面板**：侧栏 AI 助手支持流式增量生成、生成中 `ESC` 中止、回答一键复制 / 插入；内置上下文约束（仅依据当前文档上下文作答与改写，抑制模型臆造）。
- **本地语义检索**：`semsearch` 以 TF-IDF + 同义词实现**零依赖语义搜索**，与跨文件关键词检索互补，离线即可做近义召回，不牺牲体积与隐私。

> 工程取舍：以「自带密钥 + 本地端侧」为前提规避订阅与遥测；语义改写与检索均可在纯离线环境运行，契合政企内网 / 无网写作场景。

---

## 四、快捷键速查

| 快捷键 | 功能 | 快捷键 | 功能 |
|---|---|---|---|
| `Ctrl+N` / `O` / `S` / `Shift+S` | 新建 / 打开 / 保存 / 另存为 | `Ctrl+B` / `I` / `E` | 加粗 / 斜体 / 行内代码 |
| `Ctrl+W` / `Q` | 关闭标签 / 退出 | `Ctrl+Shift+X` / `Q` | 删除线 / 引用 |
| `Ctrl+F` / `H` / `G` | 查找 / 替换 / 转到行 | `Ctrl+1/2/3` / `0` | 标题 1~3 / 正文 |
| `Ctrl+Shift+F` | 全局搜索 | `Ctrl+Shift+T` / `K` | 插入表格 / 代码块 |
| `Ctrl+/` | 块菜单 | `Ctrl+Shift+M` / `-` | 公式 / 分割线 |
| `Ctrl+Shift+P` | 命令面板 | `Ctrl+Shift+D` | 分屏模式 |
| `Ctrl+Shift+L` | 侧栏开关 | `Ctrl+Shift+E` / `O` | 文件列表 / 大纲 |
| `Ctrl+Shift+[` / `]` | 折叠 / 展开全部标题 | `Ctrl+Shift+H` | 历史版本 |
| `Ctrl+=` / `Ctrl+-` | 编辑区放大 / 缩小（重置点状态栏缩放格） | `Ctrl+PgUp` / `PgDn` | 上 / 下一标签页 |
| `F11` / `F12` | 全屏 / 使用手册 | `Ctrl+Z` / `Y` | 撤销 / 重做（300 步） |
| `Tab` / `Shift+Tab` | 表格跳格 / 代码缩进 | `Ctrl+Enter` | 从代码块 / 引用中跳出 |

> 全部快捷键均可在「工具 → 快捷键设置…」自定义；以该设置页与《使用手册》第 10 章的实际值为准。`Ctrl+0` 仍为「正文」段落样式，缩放重置走状态栏缩放格。
> 提示：原 F1「快捷键一览」弹窗已于 v3.44.31 移除，快捷键统一收录于《使用手册》（`F12` 或「帮助 → 使用手册」）。

---

## 五、目录结构

```
mdEditor/
├─ src/
│  ├─ main.py          入口：单实例（QLocalServer）、滚动日志、Qt 中文翻译、启动 MainWindow
│  ├─ mainwindow.py    主窗口：菜单 / 工具栏 / 标签页 / 导出 / 模板 / 设置 / QSettings 桥接
│  ├─ editor.html      ★ 单文件编辑内核（HTML+CSS+JS，~700KB）：块解析、渲染、全部交互
│  ├─ sidebar.py       侧栏：全局搜索面板、大纲树、目录树
│  ├─ dialogs.py       查找替换 / 快捷键设置 / 系统设置（四页）/ 插入图片
│  ├─ exporters.py     Markdown 解析 + HTML / PDF / docx / EPUB / pandoc 通道
│  ├─ styles.py        六套主题调色板与 QSS 模板
│  ├─ config.py        版本号、常量、内置模板、图表主题、演示文档
│  ├─ ai_core.py       大模型接入内核（15 家 BYOK + 本地 Ollama 流式）
│  ├─ ai_connection.py AI 连接设置（BYOK / 本地 Ollama 引导）
│  ├─ ai_pane.py       AI 问答面板（流式 / 上下文约束 / 复制插入）
│  ├─ ai_context.py    AI 上下文约束提示词
│  ├─ semsearch.py     本地语义检索（TF-IDF + 同义词，零依赖）
│  ├─ diffmerge.py     片段级差异合并（AI 改写 diff / 版本历史三色 diff）
│  ├─ icons.py         QPainter 矢量线性图标
│  ├─ mdeditor.ico
│  ├─ katex/           离线 KaTeX（随包分发）
│  └─ mermaid/         离线 Mermaid（随包分发）
├─ tests/              测试脚本与运行结果（222 个 .py；结果 .txt 不入 Git）
├─ docs/               规范 / 审计 / 测试报告 / 功能清单（见第七节）
├─ build_exe.ps1       PyInstaller 一键打包（输出目录见脚本内 --distpath，即 distNN）
├─ distNN/mdEditor/    打包产物（gitignored）
├─ CHANGELOG.md        逐版本变更总览
├─ OPTIMIZATION.md     交互优化清单
├─ COMPETITIVE.md      竞品调研与差距清单
├─ README.md           本文件
└─ AGENTS.md           开发规范（人 / AI 协作同一套规则）
```

---

## 六、构建与测试

### 打包

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
```

- 输出到 `distNN\mdEditor\`（`NN` 为滚动序号，见脚本内 `--distpath`），日志写 `_build_log.txt`。
- **不要加 `--clean`**（会重建全部缓存、显著变慢且易出错）。
- 重打同一 `distNN` 前先删掉 `distNN\mdEditor` 目录（目录被占用时用 `robocopy 空目录 目标 /MIR` 清空再删壳）。
- `--add-data` 必须用**绝对路径**；脚本已带 `mdeditor.ico`、KaTeX、Mermaid、Qt 中文翻译。
- 校验方式：exe SHA256 一致 + 特征串匹配 + 启动自检。

### 测试（三段式）

```bash
# 1) 内核语法检查（抽取 editor.html 内联脚本 → node --check）
python tests/_syntax_check.py

# 2) Node 内核单测（纯逻辑，秒级）
node tests/test_core.js                       # 期望 "ALL TESTS PASSED"

# 3) GUI 探针（起真实 Qt 窗口，需在 venv 解释器下跑）
python tests/_runner.py tests/_m113.py        # 结果写 tests/_m113.txt
python tests/_run_full.py                     # 全量回归（语法+内核+探针+smoke，约 9 分钟）
```

- **判定以结果文件里的 `PASS` / `FAIL` 计数为准，不看退出码**（teardown 崩溃是噪声）。
- 探针命名 `_mNN.py` → 结果 `_mNN.txt`；纳入全量回归需登记进 `tests/_run_full.py` 的清单。
- 自动化隔离开关：`MDEDITOR_SINGLETON_KEY`（允许多实例）、`MDEDITOR_SKIP_DRAFT`（跳过草稿恢复询问）。

---

## 七、数据存放位置

| 位置 | 内容 |
|---|---|
| `%APPDATA%\mdEditor\templates.json` | 模板（内置 8 个 + 自建，结构版 v3） |
| `%APPDATA%\mdEditor\drafts\` | 未命名文档影子草稿 |
| `%APPDATA%\mdEditor\logs\mdEditor.log` | 滚动日志 512KB×3（「帮助 → 复制诊断信息」可汇总） |
| `<文档目录>\.mdeditor-history\<文档名>\` | 版本历史快照（默认保留 20 份，1~200 可配） |
| `<文档名>.assets\` | 落盘的图片资源 |
| QSettings（组织 `WorkBuddy` / 应用 `WorkBuddyMarkdown`） | 主题、缩放、自动保存、代码语言、图片模式、图表主题、快捷键等 |

---

## 八、已知限制

1. **单机本地应用**：无云同步 / 协作 / 移动端。
2. **复杂表格以 HTML 存储**（列宽、合并、标注表达不了原生 Markdown），在别的编辑器里会显示为 HTML 片段。
3. **Mermaid E-R 图只认 ASCII**：实体名 / 属性名 / `title` 请用英文，关系标签写成 `: "中文"`。
4. **pandoc 为可选增强**，未安装时 docx / EPUB 自动降级内置转换（公式与图表降级为源码 / 位图）。
5. **全局搜索有上限**（1500 文件 / 1.5MB 单文件 / 400 命中），超大目录建议缩小范围。
6. 编码探测为 BOM / UTF-8 / GBK 三段回退，Big5 等冷门编码未覆盖。

---

## 九、文档索引

| 文件 | 用途 |
|---|---|
| `README.md` | 本文：项目说明、快速开始、功能总览、构建与测试 |
| `CHANGELOG.md` | 逐版本变更（v1 → v3.38）、踩坑记录 |
| `AGENTS.md` | 开发规范：改动流程、**文档同步矩阵**、测试约定、已知工具坑 |
| `docs/功能列表-v3.31.md` | 模块级功能明细 + QSettings 一览 + 限制汇总（累计至 v3.38） |
| `docs/未实现BUG与优化清单-v3.30.11.md` | 缺陷与优化台账（销账式） |
| `docs/代码块模块交互规范-v3.37.md` | 代码块交互规范与验收条文 |
| `docs/引用模块交互规范-v3.37.md` | 引用块交互规范与验收条文 |
| `docs/格式栏全块型一致性审计-v3.37.md` | floatbar 全块型一致性审计报告 |
| `docs/表格交互三浮层功能划分分析-v3.37.md` | 表格 objbar / floatbar / 右键菜单职责划分 |
| `docs/图表交互四层功能划分分析-v3.37.md` | 图表四层交互划分 |
| `docs/产品评审与优化清单-v3.31.md` | 模块产品评审与优先级矩阵 |
| `docs/待实现清单-v3.32.md` | 待实现项登记 |
| `docs/测试报告-v3.31.md` 等 | 各批次测试报告 |
| `docs/图表主题预览-v3.34.html` | 图表主题可视化预览 |
| `OPTIMIZATION.md` / `COMPETITIVE.md` | 交互优化清单 / 竞品调研 |

---

## 十、开发约定

改动代码前请先读 [`AGENTS.md`](AGENTS.md)。其中的**硬性规则**摘要：

- **代码改动必须同步更新相关文档**（CHANGELOG / 功能列表 / 缺陷台账 / 交互规范 / 测试登记），矩阵见 AGENTS.md 第四节。
- `src/editor.html` 是 CRLF 单文件内核：改动用一次性补丁脚本（读时归一化 `\r\n`→`\n`，写时恢复），禁止同文件并行编辑。
- 同源常量需多处同步（如 `config.MMD_THEMES` ↔ `editor.html MMD_THEMES`、模板名称上限三处、`BUILTIN_TEMPLATES` ↔ `TPL_BUILTIN`）。
- 提交前必须跑通 `tests/_syntax_check.py` 与 `node tests/test_core.js`。

---

## 十一、开源与许可

- **协议**：Apache License 2.0（见 [LICENSE](LICENSE)）。可自由使用、修改、再分发，含商用；再分发须保留版权与许可声明，修改过的文件须标注改动。
- **仓库**：<https://github.com/yuansong/mdEditor>
- **问题反馈**：GitHub Issues。
- **参与贡献**：欢迎 Issue / Pull Request；改动前请先阅读 [`AGENTS.md`](AGENTS.md) 的开发规范。
