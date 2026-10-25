# SoloMD 竞品深度调研

> 对标对象：mdEditor（dist130 / v3.44.33，Windows 单机 Markdown 编辑器）
> 调研时间：2026-10-22
> 信息来源：SoloMD 官网（solomd.app）、GitHub 仓库公开数据（agentindex.app 镜像）、Microsoft Store / App Store 页面、第三方评测（GadgeteerZA、vgover、易有料等）
> 可信度说明：本报告基于官方宣称 + 公开仓库元数据 + 第三方评测，**未亲自安装实测**。SoloMD 官方有一份"2026 免费编辑器横评"含自我宣传成分，已用多来源交叉校验；凡无法独立证实之处，文中标注"待核"。

---

## 一、执行摘要

SoloMD 是 2026 年横空出世的**免费、MIT 开源、全平台（macOS/Win/Linux/iOS/Android）** Markdown 编辑器，技术栈 Tauri 2（系统 WebView + Rust），安装包仅 ~15MB、空闲内存 80–150MB。它同时抢占两条赛道：

- **Typora 平替**：实时 WYSIWYG（光标离开行后标记自动隐藏）、极简写作、轻量；
- **Obsidian 开源替代**：Wiki 链接 + 反向链接 + 关系图、本地 RAG 语义搜索、AutoGit 版本历史、内置 MCP server、14 个 BYOK AI 提供商 + Agent 面板。

**对 mdEditor 的战略含义**：SoloMD 的"全平台 + 开源 + AI 原生 + 知识库 + 社区势能"四件套，恰好命中 mdEditor 在 `COMPETITIVE.md` 中列的最大差距（#1 跨平台、#2 双链/知识库、#3 AI BYOK）。它不是又一个 MarkText（已停滞），而是**活跃度爆表**（90 天 100+ commits、30 个 release、5 人贡献者、102 open issues）的 real threat。**但 SoloMD 有一个明确软肋——表格编辑很弱（无像样的 WYSIWYG 表格编辑器），而这正是 mdEditor 的 Office 级表格护城河。** 此外 mdEditor 在 Windows 原生集成、图片双模式+裁剪、文档级版本历史对话框、块级 WYSIWYG 成熟度上仍可坚守。

---

## 二、SoloMD 产品画像

| 维度 | 事实 |
|---|---|
| 首发 / 当前版本 | 2026-04-08 首版；**v5.0.4（2026-10-20/21）** |
| 许可证 | **MIT**（完全可审计，无账号、无遥测、无内购） |
| 技术栈 | Tauri 2 + Rust + Vue 3 + CodeMirror 6（系统 WebView，**不打包 Chromium**） |
| 安装包 / 内存 | ~15MB（Mac 通用包 ~32MB）；空闲 80–150MB |
| 平台 | macOS（Apple Silicon+Intel）、Windows（x64 + ARM64/Snapdragon X）、Linux（x64+aarch64）、iOS 15+、Android API 24+ |
| 团队 | 人类维护者定方向，**几乎全部由 Claude Code 编写/测试/发布/答 issue**（维护者坦诚声明） |
| 活跃度 | 90 天 100+ commits、30 releases、30 贡献者、91 fork、82 open issues/PR（2026-10-22 数据） |
| UI 语言 | 14–15 种（含简体中文，首启按系统 locale 自动选） |
| 价格 | 永久免费，无付费档、无订阅、无 AI 抽成（AI 仅按你选的提供商 token 计费） |

**设计五原则**（官网自述）：① 默认本地优先；② MIT 完全可审计；③ 数据永远是普通 .md 文件；④ 刻意不做插件市场（保持轻量稳定）；⑤ GitHub Discussions 友好社区（无 Discord/微信群）。

---

## 三、SoloMD 功能全景（按维度）

### 3.1 核心编辑
- **实时 WYSIWYG**（Typora 式）：光标离开当前行后 Markdown 标记淡出；标题真大、粗体真粗、代码真等宽。
- **四视图**：实时（Live）/ 源码（Source）/ 分栏（Split，源码与渲染并排、滚动同步）/ 预览（Preview），一键切换。
- **多标签**（带脏标识）、**文件树侧栏**、**大纲视图**、**ripgrep 风格全局搜索**。
- **多编码自动识别**：UTF-8 / UTF-16 / GBK / GB18030 / Big5 / Shift_JIS。
- **语法增强**：KaTeX 公式（行内+块级）、Mermaid（流程图/序列图/甘特图）、可点击任务列表、脚注、YAML front-matter、`==高亮==`、13+ 语言代码高亮。
- **图片**：粘贴自动存入 `_assets/` 并生成链接（与 mdEditor 的 `_assets` 落盘思路一致）。
- **表格**：⚠️ **明确弱项**——评测直言"没有漂亮的 WYSIWYG 表格编辑器"，加列/改结构常用"把表格丢给 AI 改"或手动写。

### 3.2 写作者工具
- **专注模式**（非当前段变暗）、**打字机模式**（光标垂直居中）。
- **会话恢复**（自动保存，不丢稿）。
- **中文利器**：简繁转换、拼音、CJK 字符数统计——中文"一等公民"。
- **拼写检查**、**自定义 CSS**（给预览换样式）。
- **演讲模式（Slideshow）**：同一份 .md 直接当全屏幻灯片放。

### 3.3 知识管理
- **Wiki links + 反向链接**面板（不做臃肿图谱视图，但提供 Typed relationships + 关系图）。
- **Properties inspector**（类型/日期/状态/关系选择器编辑 YAML front-matter）。
- **Type-driven sidebar**（给笔记设类型，成员变一级可折叠区）。
- **保存的过滤视图 + Inbox workflow**（inbox zero）。
- **Whiteboards**：Markdown 支撑的 tldraw 白板（嵌在代码围栏内）。

### 3.4 AI（v4.0 起的头号差异化）
- **14 个 BYOK 提供商**：OpenAI、Claude、Gemini、xAI Grok、Mistral、Groq、DeepSeek、Qwen、GLM、Kimi、Doubao、SiliconFlow、OpenRouter、**Ollama（本地零成本）**。Key 存系统钥匙串（macOS Keychain / Win Credential Manager / Linux libsecret），不经手 SoloMD 服务器。
- **Inline Agent Panel**：右侧面板"与笔记库对话"，带 wikilink 引用 + 可见 tool-call 卡片。
- **Scheduled Agent Recipes**：YAML 声明式（cron / on-save / on-commit / on-tag-add / 手动触发）。
- **AutoGit Branch Sandbox**：每次 agent 写入落在独立 git 分支，你 accept/reject 才合入 main；每轮写入上限（默认 5）、dirty tree 拒绝启动、留可回放 `trace.jsonl`。
- **Clean AI artifacts**：一键去除 `[cite_start]`、`【†source】`、智能引号、零宽字符等 LLM 垃圾。

### 3.5 本地优先 / 隐私
- **本地语义搜索**：on-device embedder（Rust 进程内），无模型下载、无云调用、可关；索引存 `.solomd/embeddings.sqlite`（自动 gitignore）。
- **AutoGit 版本历史**：每次 ⌘S 自动提交到工作区内本地 .git，侧栏历史面板一键回滚（竞争对手要手动接 git）。
- **MCP server**（1.5MB sidecar，stdio 无网络端口）：8 只读工具（list/read/search/backlinks/tags/outline/export…）+ 2 写工具（需 `--allow-write`），路径穿越防护。
- **同步**：任意文件夹同步服务（iCloud/Dropbox/OneDrive/Syncthing）或 AutoGit + 私有 GitHub；可选 Argon2id + XChaCha20-Poly1305 **端到端加密**；内置 CRDT 同步在 roadmap（刻意不做 SoloMD 专属服务器）。
- **离线**：编辑器零网络请求；仅可选启动更新检查 + 你主动触发的 AI 调用会直连提供商。

### 3.6 导出
HTML（newsletter 级）、PDF（KaTeX/Mermaid 内嵌）、**Word(.docx) 保留表格**、PNG、EPUB、ODT、LaTeX、RTF、**Pandoc Template**——靠 Pandoc 保真度明显高于多数竞品。

---

## 四、SoloMD × mdEditor 逐维度对比矩阵

> mdEditor 现状取自 dist130 / v3.44.33（含 `COMPETITIVE.md` 已确认功能集）。标注「待核」= 本次未在源码层面验证。

| # | 维度 | SoloMD v5.0.4 | mdEditor v3.44.33 | 胜方 |
|---|---|---|---|---|
| 1 | 价格 | 永久免费 | 免费（自用） | 平 |
| 2 | 开源 | **MIT** | 闭源 | SoloMD |
| 3 | 平台 | **5 平台全**（含移动端/iOS/Android/ARM64） | **仅 Windows x64** | SoloMD |
| 4 | 分发体量 | ~15MB 安装包，含全部（系统 WebView） | exe ~5.33MB（但需 Python+Qt 运行时，整体分发更大，**口径不同待核**） | 口径不可比 |
| 5 | 编辑范式 | 实时 WYSIWYG（标记淡出）+ 源码 + 分栏 + 预览四视图 | 块级 WYSIWYG + 源码/预览/分屏三视图（dual 贴边） | 平（取向不同） |
| 6 | **表格** | ⚠️ 弱：无像样 WYSIWYG 表格编辑器 | **强：Office 级**（合并/拆分单元格、行列增删、对齐、拖选矩形、列宽拖拽、行高压缩） | **mdEditor** |
| 7 | 图片 | 粘贴自动落 `_assets` + 生成链接 | 落盘相对路径 + 嵌入 base64 双模式 + 裁剪/尺寸（更全） | mdEditor（略优） |
| 8 | 中文支持 | GBK/Big5/UTF-16 自动识别、简繁转换、拼音、CJK 字数（一等公民） | 全中文 UI + CJK 字数统计；GBK/Big5 识别与简繁转换**待核** | SoloMD（更系统） |
| 9 | **知识管理** | **Wiki 链接 + 反向链接 + 关系图 + 视图 + Inbox + 白板** | 无双链/图谱（差距项 #2）；仅大纲/文件树/检索 | **SoloMD** |
| 10 | **AI** | **14 BYOK + Ollama + Agent 面板 + Recipes + AutoGit 沙箱** | 无内置 AI（差距项 #3，可后置 BYOK） | **SoloMD** |
| 11 | 搜索 | **本地 RAG 语义搜索**（按"意思"排，无云） | 跨文件全文检索（grep 式）+ 文件名；无语义 | SoloMD（语义更强） |
| 12 | 版本历史 | AutoGit 每次保存本地快照 + 一键回滚 | 文档级"历史版本对比"对话框（对普通用户更友好的 GUI） | mdEditor（GUI 更友好） |
| 13 | 同步/多端 | 文件夹同步 + GitHub/AutoGit + E2EE；**移动端原生** | 无云同步、无移动端 | SoloMD |
| 14 | 导出保真 | **Pandoc**：DOCX/EPUB/ODT/LaTeX/RTF/PDF（公式+图表内嵌） | docx/EPUB/PDF 书签（Word 保真度一般，python-docx 降级）；**无 PNG 导出** | SoloMD |
| 15 | 扩展性 | 刻意无插件市场；但有 **MCP server** 接外部 AI | 闭源无生态 | SoloMD（MCP 路线） |
| 16 | 移动端 | **iOS / Android 原生** | 无 | SoloMD |
| 17 | 隐私/离线 | 无账号/无遥测/MIT/纯 .md | 完全离线/本地 .md/无账号 | 平 |
| 18 | 命令面板/快捷键 | Ctrl+Shift+K 命令面板；**自定义快捷键疑似不支持（评测吐槽）** | 命令面板（Ctrl+Shift+P 类）；快捷键定制**待核** | 平（各存疑） |
| 19 | 主题/自定义 | 浅/深跟随系统 + 自定义 CSS | 六主题 + 多界面风格（ps01/mac/zen 等）+ 可换肤 | mdEditor（主题更细） |
| 20 | 启动速度 | Tauri 轻量，快 | ~1.5s（前测），快 | 平 |

---

## 五、SoloMD 客观优缺点

### 优点
1. **全平台 + 移动端**，一次购买（免费）覆盖桌面与手机，用户无锁定焦虑。
2. **MIT 开源 + 由 Claude Code 全栈维护**，代码可审计、迭代极快（周级 release）。
3. **AI 原生且路线正确**：BYOK（不抽成）+ 本地 Ollama（零成本/零云）+ Agent 面板 + AutoGit 沙箱（写入可审查、可回放）——把"AI 改笔记"做得安全可逆。
4. **本地 RAG 语义搜索**：按语义而非关键词，对长 vault 极有价值，且完全离线。
5. **知识管理内置**：双链/反向链接/关系图/白板，免插件。
6. **Pandoc 导出保真度**行业前列，公式/图表内嵌。
7. **中文一等公民**：GBK/Big5 老文件识别、简繁转换、CJK 字数。
8. **MCP server** 让笔记库变成可被 Claude/Cursor 读写的开放资源，开发者友好。

### 缺点 / 风险
1. **极年轻（首版 2026-04）**：架构与交互仍在快速变动，v4 大特性（agent/recipes/sync）被评测明示"expect rough edges"。
2. **表格编辑是明确短板**——对写技术文档/教程（大量表格）的用户是硬伤。
3. **刻意不做插件生态**：功能靠核心团队交付，节奏受限于单人+AI；无 Obsidian 式社区扩展。
4. **社区规模远小于 Obsidian**，102 open issues 中仅 19/30 有回复（维护压力可见）。
5. **Windows 源码模式语法高亮有限**（为可靠 CJK 输入在 WebView2 上的取舍）。
6. **自定义快捷键疑似不支持**（评测诉求点）。
7. **AI 走云端提供商时笔记文本会外发**（仅 Ollama 路线规避）——隐私有前提条件。
8. **CRDT 实时同步未落地**（仅为 roadmap），多端靠文件夹同步/AutoGit，冲突解决弱于专业同步。

---

## 六、对 mdEditor 的战略含义

### 6.1 威胁（SoloMD 直接打 mdEditor 的软肋）
- **跨平台 + 移动端**：mdEditor 仅 Windows，SoloMD 用"同一份 .md、五个平台同一种安静"直接吸走多端用户。→ 印证差距项 **#1 跨平台** 是最高优先级。
- **AI 原生**：SoloMD 把"选中即问 AI / Agent 改笔记"做成默认能力。→ 印证 **#3 AI BYOK** 必须排进路线图。
- **知识管理**：双链/反向链接是 2026 用户心智标配。→ **#2 双链/知识库** 是中长期必答题。
- **语义搜索**：grep 式全文检索在"找段落而非关键词"场景吃亏。→ 建议追加"本地向量检索"子项。

### 6.2 机会（mdEditor 可坚守/反超的阵地）
- **Office 级表格**：SoloMD 最弱处，mdEditor 已是强项——**这是当下最硬的差异化护城河**，应在营销与功能上持续放大（合并/拆分/拖选/列宽，对标 Notion/Word 表格）。
- **Windows 原生集成**：文件关联、系统外观跟随、右键、打印/导出与 Office 互操作——桌面深度是 WebView 跨端应用难及的。
- **图片双模式 + 裁剪 + 尺寸**：比 SoloMD 的单纯 `_assets` 落盘更完整。
- **文档级版本历史对话框**：比"每次保存进 git、命令行回滚"对普通写作者更友好——GUI 易用性是 mdEditor 的温情点。
- **块级 WYSIWYG 成熟度**：mdEditor 自研块编辑器历经多版打磨，SoloMD 在年轻期交互细节尚不稳定。
- **主题/风格细分**：六主题 + ps01/mac/zen 多界面，比 SoloMD"浅/深跟随系统"更可控。

### 6.3 行动建议（呼应 `COMPETITIVE.md` 差距优先级）

| 优先级 | 能力 | 与 SoloMD 的关系 | 建议 |
|---|---|---|---|
| **P0** | 跨平台构建（PySide6 本身跨平台，重点在打包/测试矩阵） | 破 SoloMD 最大杠杆 | 先验证 Linux/ARM64 + macOS 打包链路 |
| **P1** | **AI BYOK 轻量入口**（选中即问 + 本地 Ollama 可选） | SoloMD 已验证该路线正确且受欢迎 | 先做"侧栏聊天/选中改写"，密钥存系统钥匙串，不抽成 |
| **P1** | 语义/向量搜索（本地 embedder，可选开关） | 对抗 SoloMD 本地 RAG | 离线优先、索引随仓库、可关 |
| **P2** | 双链 / 反向链接 / 关系图 | 对标 SoloMD 知识管理 | 重，后置；先支持 `[[wikilink]]` 解析+反向链接面板 |
| **P2** | 强化表格（已强，做"导入 Excel/CSV"、表格转图表） | 放大护城河 | 营销+功能双管齐下 |
| **P3** | 移动端 / 云同步 | SoloMD 压倒性优势区 | 最重，最后；或借"纯 .md + 文件夹同步"低成本满足 |
| **P3** | Pandoc/高保真导出、PNG 导出 | 补 SoloMD 领先项 | 引入 Pandoc 或增强 python-docx 表格保真 |

---

## 七、结论

SoloMD 是 mdEditor 在 2026 年遇到的**最重要的同类竞品**——它用"免费 + 开源 + 全平台 + AI 原生 + 知识库"组合，正面冲击 Typora/Obsidian 用户群，且活跃度与产品完成度远超停滞的 MarkText。对 mdEditor 而言：

- **不要硬刚其平台/AI/知识库广度**，那是 SoloMD 的主场且 Heavy。
- **要死守并放大 Office 级表格、Windows 原生、图片完整处理、GUI 易用性、块级渲染成熟度**——这是 SoloMD 当前补不齐的短板。
- **必须正面回应三件事**：跨平台（破增长天花板）、AI BYOK 轻量入口（用户已默认编辑器该有 AI）、本地语义搜索（检索体验代差）。这三件恰是 `COMPETITIVE.md` 已排定的 #1/#3 与新增搜索子项。

> 建议：将本报告核心结论并入 `COMPETITIVE.md` 第五节（差距清单），把 SoloMD 列为"首要竞品（2026 新晋）"，并据此微调路线图优先级。

---

## 八、附：信息来源清单
- SoloMD 官网（英文）https://solomd.app/
- SoloMD 官网（中文）https://solomd.app/zh
- Microsoft Store（Windows）https://www.microsoft.com/zh-cn/p/solomd/9nxghk2ll1q4
- GitHub 仓库公开元数据镜像 https://agentindex.app/en/tool/zhitongblog-solomd/
- 第三方评测：GadgeteerZA（开 Obsidian vault 实测）、vgover 横评、易有料私有化评测
- SoloMD 官方"2026 免费编辑器横评" https://solomd.app/compare/best-free-markdown-editors （含自我宣传，已交叉校验）
- 注：mdEditor 侧数据来自本仓库 `COMPETITIVE.md` 与 dist130 代码核对结论；标「待核」项建议后续在源码层验证后再定稿。
