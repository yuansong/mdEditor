# mdEditor

Typora 风格的**所见即所得**（块级 WYSIWYG）Markdown 编辑器，Windows 桌面单机应用。
Python + PySide6 (QtWebEngine) 外壳 + 单文件 JS 编辑内核 `src/editor.html`，全部能力离线可用（KaTeX / Mermaid 均内置）。

> 当前版本 **v3.38.0**（`src/config.py: APP_VERSION`）。
> 「现在能用什么」看本文；「每个版本动了什么」看 [`CHANGELOG.md`](CHANGELOG.md)；「模块级功能明细」看 [`docs/功能列表-v3.31.md`](docs/功能列表-v3.31.md)；「开发 / AI 协作规则」看 [`AGENTS.md`](AGENTS.md)。

---

## 一、快速开始

### 方式 1：直接运行打包产物（推荐，无需装环境）

```
dist61\mdEditor\mdEditor.exe                 # 双击运行
dist61\mdEditor\mdEditor.exe D:\docs\note.md # 命令行带文件打开
```

- 采用 PyInstaller **onedir** 模式：整个 `mdEditor` 文件夹缺一不可，只拷 exe 无法运行。
- `build61\` / `spec61\` 是打包中间产物，**其中的 exe 不能直接运行**，属正常现象。
- dist61 为最近一次成功打包的产物；v3.38 批次（2026-10-01 08:00 之后的改动）**尚未打包**，`build_exe.ps1` 已指向 `dist62`。要体验最新代码请用方式 2 从源码运行。

### 方式 2：从源码运行

环境（已在开发机验证）：

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.13.x | 项目使用 venv：`C:\Users\Administrator\.workbuddy\binaries\python\envs\default` |
| PySide6 | 6.11.2 | 必须含 `QtWebEngineWidgets` |
| python-docx | — | 导出 Word，缺失时该菜单项降级提示 |
| pypdf | — | PDF 书签，缺失时 PDF 仍可导出但无书签 |
| pandoc | 可选 | 配置路径后 docx / EPUB 导出优先走 pandoc |

```bash
# 在 venv 中安装依赖（一次性）
pip install PySide6 python-docx pypdf

# 运行
python src/main.py                 # 空文档启动
python src/main.py D:\docs\note.md # 打开指定文件
```

启动后：单实例互斥（二次启动会把文件参数转发给已运行实例）；命令行只取第一个存在的 `.md/.markdown/.mdown/.txt` 参数。

---

## 二、界面与调用方式

| 区域 | 内容 |
|---|---|
| 菜单栏 | 文件 / 编辑 / 格式（隐藏，仅承载快捷键）/ 视图 / 设置 / 帮助 |
| 左侧竖向工具栏 | 侧栏开关、新建、打开、保存、撤销、重做、查找、**模式循环**、系统设置 |
| 侧栏（三页） | 文件列表（目录树）、大纲（级别 1~6、拖拽调序、分节字数）、搜索（跨文件全文检索） |
| 编辑区 | 块级渲染态直编；写作 / 源码 / 分屏三模式（`Ctrl+Shift+D` 分屏，双栏 160ms 同步滚动） |
| 状态栏 | 字数与阅读时长（点击查看明细）、行列位置、当前块类型、toast 提示 |

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
查找替换（正则 + 8 种预设 + 全部命中高亮，CSS Custom Highlight API）· 跨文件全局搜索（上限 1500 文件 / 单文件 1.5MB / 400 命中）· 大纲树（纯文本、级别过滤、拖拽调序、分节字数）· 转到行 `Ctrl+G`。

### 导出
| 通道 | 说明 |
|---|---|
| HTML | **单文件离线**：KaTeX 字体 base64 内嵌、图表为静态 SVG、本地图片转 data URI，零 CDN |
| PDF | WebEngine 打印，按标题写入 PDF 书签（依赖 pypdf） |
| Word (.docx) | python-docx，代码块灰底等宽，图表位图化嵌 PNG |
| EPUB 3 | 纯标准库，按一级标题分章 + nav 目录 |
| pandoc 通道 | 配置了路径则优先走 pandoc（`gfm+tex_math_dollars --toc`） |
| 复制为 HTML | 富文本进剪贴板，可直接粘到 Word / 公众号 |

### 外观与设置
六套主题（浅色 / 青空 / 护眼米黄 / 深色 / 墨夜 / 熊猫，窗口 + 编辑区 + 弹层同步换肤）· 缩放 80%~160% · 系统设置四页（外观 / 编辑器 / 通用 / **模板**）· 快捷键自定义与冲突检测 · 8 个内置模板 + 自建模板统一管理（名称上限 10 字，可改名 / 改内容 / 排序 / 恢复内置，也可在侧栏文件右键「设为模板…」）。

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
| `F1` / `F11` | 快捷键一览 / 全屏 | `Ctrl+Z` / `Y` | 撤销 / 重做（300 步） |
| `Tab` / `Shift+Tab` | 表格跳格 / 代码缩进 | `Ctrl+Enter` | 从代码块 / 引用中跳出 |

> 全部快捷键均可在「设置 → 快捷键设置」自定义；以 `F1` 一览中的实际值为准。

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
│  ├─ icons.py         QPainter 矢量线性图标
│  ├─ mdeditor.ico
│  ├─ katex/           离线 KaTeX（随包分发）
│  └─ mermaid/         离线 Mermaid（随包分发）
├─ tests/              测试脚本与运行结果（222 个 .py；结果 .txt 不入 Git）
├─ docs/               规范 / 审计 / 测试报告 / 功能清单（见第七节）
├─ build_exe.ps1       PyInstaller 一键打包（当前指向 dist62）
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

- 输出到 `dist62\mdEditor\`，日志写 `_build_log.txt`。
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
