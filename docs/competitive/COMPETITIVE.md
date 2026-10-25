# mdEditor 竞品分析（v3.48.20 · 已开源 Apache-2.0 · 跨平台 Win/mac/Linux）

> 分析时间：2026-10-25 ｜ 分析对象：mdEditor **v3.48.20**（Apache-2.0 开源，Python + PySide6 / QtWebEngine 外壳 + 自研 JS 块级内核；Windows 已发布，macOS 已构建，Linux 脚本就绪）
> 对标对象：**Typora / MarkText / Obsidian / VS Code**（四大流派样本）＋ 2026 新晋：**SoloMD / Zettlr / iA Writer / Bear**
> 方法：竞品侧读官方站 + 第三方横向评测；mdEditor 侧以 `README.md`「功能总览」+ `CHANGELOG.md` + `src/` 源码逐项核对，避免凭印象。
> 数据有效性：SoloMD 迭代为周级，本报告对 SoloMD 的结论有效期约 2–4 周，须以 GitHub Releases 为准二次核对。

---

## 〇、两个历史性短板已关闭（2026-10 重大变更）

| 旧短板 | 旧状态 | 2026-10 状态 | 说明 |
| --- | --- | --- | --- |
| **闭源** | 闭源单体 | ✅ **已关闭 · Apache-2.0 开源** | 项目已开源，源码托管 GitHub，允许自由使用 / 修改 / 分发、商用 |
| **仅 Windows** | 仅 Windows | ✅ **已关闭 · 跨平台构建就绪** | Windows 持续发布；macOS 已通过 GitHub Actions（`build-mac.yml`）出包；Linux 提供 `build_linux.sh` 脚本 |

> 影响：旧报告「Weakness #1 仅 Windows」「Weakness #2 闭源」两项正式关闭。剩余差距清单（第六节）已重排，原 12 项 → 现 10 项核心差距。移动端（iOS/Android）仍缺失，见 G-1。

---

## 一、为什么是这五个（含新晋）

Markdown 编辑器分四个流派，样本覆盖如下；另补 2026 新晋代表，因其正在改写"免费 + 跨端 + AI"的基线。

| 流派 | 代表 | 选择理由 |
| --- | --- | --- |
| 专用 WYSIWYG 写作型 | **Typora** | 行业标杆，mdEditor 直接对标（README 即 Typora 功能对照） |
| 同形态免费替代 | **MarkText** | 同为块级 / 实时渲染，MIT 免费，是 Typora 首选平替，用户群重叠最高 |
| 本地知识库型 | **Obsidian** | 2026 社区规模最大（1,500+ 插件），"Markdown 之上再建一层"路线代表 |
| 通用 IDE 型 | **VS Code + 扩展** | 事实使用量最大的 md 写法（约 78% 开发者用它处理 md），能力上限最高 |
| 2026 新晋 | **SoloMD / Zettlr / iA Writer / Bear** | 分别代表"免费跨端 AI""学术 Pandoc""写作至上原生""Apple 笔记库"四条新路线 |

**四个核心竞品的客观短板**（它们并非全面碾压，机会在此）：
- **Typora**：闭源 + 付费（¥89 / $14.99，3 设备）、无插件生态、无协作、无移动端、无云同步；v1.13 才试水 AI（预览版）。
- **MarkText**：2022 后曾长期停滞，2026 复活（0.19 于 5 月、0.20 于 10-02），仍无内置 AI；导出格式较少（v0.20 起靠 Pandoc 补 Word）。
- **Obsidian**：闭源核心、Sync 付费（$5/月）、插件生态是优势也是维护 / 安全面；"先知识库、后文件编辑器"，纯写作手感不如 Typora。
- **VS Code**：无就地渲染写作模式（仅源码 + 分屏预览），默认体验"工具化"，无专注 / 打字机、排版不精美；启动 3~5 秒。

---

## 二、竞品画像（2026-10 实测口径，含 SoloMD）

| 维度 | Typora 1.13.7 | MarkText 0.20 | Obsidian 1.x | VS Code 1.9x | **SoloMD 5.0.5** | **mdEditor v3.48.20** |
| --- | --- | --- | --- | --- | --- | --- |
| 价格 | $14.99 买断（¥89） | 免费（MIT） | 个人/商业免费，Sync $5/月 | 免费（MIT） | 免费（MIT，$0） | 免费（Apache-2.0） |
| 开源 | 闭源 | MIT | 闭源核心 | MIT | MIT | **Apache-2.0 已开源** |
| 平台 | Win/mac/Linux（+ARM） | Win/mac/Linux（x64） | 桌面 + iOS/Android | 桌面（+Web） | **5 平台**（Win/mac/Linux/Android/iOS） | **Win ✅ / macOS ✅构建 / Linux 脚本** |
| 体积（安装包） | ~70MB | ~85MB（Electron） | ~130MB | ~95MB | ~15MB（mac universal 32MB） | 绿色文件夹 ~8MB exe |
| 实时渲染写作 | ✅ 业界标杆 | ✅ | ✅ Live Preview | ❌ 仅分屏 | ✅ CodeMirror 6 | ✅ 块级 |
| 定位一句话 | 最成熟纯写作体验 | 免费 Typora 平替 | 本地笔记知识库 | 开发工作流一体 | 免费跨端 AI 写作 | 中文写作 + 离线绿色 + 开源 |

---

## 三、功能对照大表（以 v3.48.20 当前状态重评）

✅ = 完整支持　🟡 = 部分支持 / 需配置　❌ = 无

### A. 编辑与写作体验

| 能力 | Typora | MarkText | Obsidian | VS Code | **SoloMD** | **mdEditor** |
| --- | --- | --- | --- | --- | --- | --- |
| 就地实时渲染（单栏 WYSIWYG） | ✅ | ✅ | ✅ Live Preview | ❌ 仅分屏 | ✅ CM6 单宿主 | ✅ 块级 |
| 源码 / 分屏对照 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 三模式 |
| 专注模式 | ✅ | ✅ | 🟡 插件 | ❌ | ✅ | ✅ |
| 打字机模式 | ✅ | ✅ | ❌ | ❌ | ✅（演讲模式） | ✅ |
| 段落 / 标题折叠 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅（已落地 P1-2） |
| 多光标编辑 | ✅ | ❌ | ✅ | ✅ | ✅ CM6 | ✅（v3.48.16 MC） |
| 自动配对括号/引号/Markdown 符号 | ✅ | 🟡 | 🟡 | ✅ | ✅ | ✅（P1-1） |
| Emoji 自动补全（`:smile:`） | ✅ | ❌ | ✅ | 🟡 | ✅ | ✅（P1-8） |
| 拼写检查 | ✅ | ✅ | ✅ | ✅ 扩展 | ✅ Hunspell + 中文校对 | ❌（主动 `spellcheck=false`） |
| 字数统计 / 阅读时长 | ✅ | 🟡 | ✅ | 🟡 扩展 | ✅ | ✅ 状态栏（P0-2） |
| 键盘插入菜单（`/`） | 🟡 | ❌ | ✅ 命令面板 | 🟡 | ✅ | ✅ 可配置优先级与默认项 |
| 块手柄菜单（拖拽/复制/转类型） | 🟡 | ❌ | 🟡 | ❌ | 🟡 | ✅ |
| 主题换肤 | ✅ ~200 社区主题 | ✅ 6 套 | ✅ 社区主题 | ✅ | ✅ 14 UI 语言 + CSS | ✅ 六主题 + 十界面风格（ribbon） |
| 快捷键自定义 | ✅ | 🟡 | ✅ | ✅ | ✅ | ✅ |
| 中文界面 / 输入法兼容 / CJK 排版 | 🟡 界面中文 | ❌ 英文界面 | ✅ 社区中文 | 🟡 | ✅ GBK/Big5/Shift-JIS 识别 + CJK 计数 + 简繁转换 | ✅ **强项** |

### B. 导航与检索

| 能力 | Typora | MarkText | Obsidian | VS Code | **SoloMD** | **mdEditor** |
| --- | --- | --- | --- | --- | --- | --- |
| 大纲面板（可跳转） | ✅ | ✅ | ✅ | 🟡 | ✅ | ✅ 纯文本/级别过滤/拖拽调序/分节字数/折叠子节点 |
| 文件树侧栏 | ✅ | ✅ | ✅ 资料库 | ✅ | ✅ | ✅ |
| 文档内查找/替换（正则） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **跨文件全文搜索** | ❌ | 🟡 | ✅ 强 | ✅ 强 | ✅ 本地 RAG 语义 | ✅（P0-3） |
| 命令面板（`Ctrl+Shift+P`） | ❌ | ❌ | ✅ | ✅ | ✅ | ✅（P1-3） |
| 双链 `[[笔记]]` + 反向链接 | ❌ | ❌ | ✅ 核心 | 🟡 扩展 | ✅ 核心 | 🟡 通用 wikilink + 反链面板（v3.48.13），缺图谱 |
| 标签 / YAML 元数据视图 | 🟡 Front Matter | 🟡 | ✅ | 🟡 | ✅ Properties 表格化 | 🟡 仅识别 Front Matter |
| 文档内跳转历史（前进/后退） | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| 最近文件 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### C. 内容能力（语法与素材）

| 能力 | Typora | MarkText | Obsidian | VS Code | **SoloMD** | **mdEditor** |
| --- | --- | --- | --- | --- | --- | --- |
| 表格可视化编辑 | ✅ 含列宽拖拽 | ✅ | 🟡 核心较弱需插件 | 🟡 格式化 | ❌ **明确短板** | ✅ 增删行列/对齐/**合并拆分**/标注/列宽行高拖拽（Office 级） |
| 代码块（100+ 语言高亮） | ✅ 行号/折行 | ✅ | ✅ | ✅ 最强 | ✅ CM6 | ✅ 103 语言/搜索/行号/风格切换 |
| 数学公式（KaTeX/MathJax） | ✅ MathJax v4 | ✅ | ✅ 插件 | ✅ 扩展 | ✅ | ✅ 离线 KaTeX |
| Mermaid 图表 | ✅ 11.13 | ✅ | ✅ 插件 | ✅ 扩展 | 🟡 | ✅ 离线 9.x（7 种图，较旧） |
| 图片：粘贴/拖入自动存相对路径 | ✅ + 图床 | ✅ + 图床 | ✅ | ✅ Paste Image | ✅ 到 `_assets/` | ✅ 相对路径落盘 + 内嵌双模式（P0-1） |
| 图片尺寸/对齐可视化调整 | ✅ | ✅ | 🟡 | 🟡 | 🟡 | ✅ 拖拽手柄 + 裁剪 + 对齐（P1-5/IMG-CROP） |
| 脚注 / 上下标 / 定义列表 | ✅ | ✅ Pandoc | ✅ | ✅ | ✅（Pandoc） | ✅（P1-4） |
| `[TOC]` 目录 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| YAML Front Matter | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 版本历史 / 文件复原 | ✅ | ❌ | 🟡 插件 | ✅ Git | ✅ AutoGit | ✅ 保存前快照 + 行级三色 diff（P1-6） |

### D. 导出与交付

| 能力 | Typora | MarkText | Obsidian | VS Code | **SoloMD** | **mdEditor** |
| --- | --- | --- | --- | --- | --- | --- |
| HTML | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ **单文件离线**（KaTeX 字体 base64、图表静态 SVG、零 CDN） |
| PDF | ✅ 带书签 | ✅ | 🟡 插件 | ✅ 扩展 | ✅ Pandoc | ✅ 分页 + 标题书签（pypdf） |
| **Word / docx** | ✅ Pandoc 保真 | 🟡 v0.20 起 Pandoc | 🟡 插件 | ✅ 扩展 | ✅ Pandoc | ✅ python-docx / pandoc 通道（复杂表格·图表降级位图） |
| **EPUB** | ✅ | ❌ | 🟡 插件 | 🟡 | ✅ | ✅ EPUB 3（按一级标题分章 + nav） |
| LaTeX / Pandoc 多格式 | ✅ | ❌ | ❌ | 🟡 | ✅ Pandoc（含 ODT/LaTeX/@citekey） | 🟡 配置 pandoc 路径后可用 |
| 导出图片（PNG） | ✅ | ❌ | ❌ | 🟡 | ✅ | 🟡 待核（渲染区截图导出） |
| 复制为富文本 HTML | ❌ | ❌ | ❌ | ❌ | ✅ | ✅（粘到 Word/公众号） |

### E. 工程与生态

| 能力 | Typora | MarkText | Obsidian | VS Code | **SoloMD** | **mdEditor** |
| --- | --- | --- | --- | --- | --- | --- |
| Git 集成 | ❌ | ❌ | 🟡 插件 | ✅ 原生 | ✅ AutoGit（分支 accept/reject） | ❌（仅"在文件夹中显示/外部打开"） |
| 插件 / 扩展机制 | ❌ | ❌ | ✅ 1,500+ | ✅ | 🟡 MCP 13 tools（无传统插件） | ❌（开源后生态待建） |
| AI 辅助写作 | 🟡 v1.13 预览 | ❌ | 🟡 插件 | ✅ Copilot | ✅ 14 BYOK + Ollama + Agent 面板 | ✅ 15 家 BYOK + 批量审查 + 可撤销 + Ollama 原生端 |
| 云同步 / 移动端 | ❌ | ❌ | ✅ 付费 Sync + 移动端 | 🟡 | ✅ E2EE GitHub 同步 + 5 平台 | ❌ 单机绿色版（无移动端） |
| 启动速度 | 快 | 中（Electron） | 中 | 3~5s | 快（Tauri） | ✅ **约 1.5s** |
| 便携免安装 | ❌ | 🟡 AppImage | ❌ | 🟡 便携版 | ❌ 安装包 | ✅ 绿色文件夹 |
| 跨平台 | ✅ | ✅ | ✅ | ✅ | ✅ 5 平台 | ✅ **Win/mac/Linux 构建就绪** |

---

## 四、逐竞品优缺点

### 4.1 Typora —— 直接标杆

**Typora 优点**
- 实时渲染写作手感仍是业界天花板，主题 / CSS 生态成熟（~200 社区主题）。
- 导出最全最稳：PDF（书签）/Word/HTML/ePub/LaTeX/PNG，且 Pandoc 保真度高。
- 数学（MathJax v4）+ 图表（Mermaid 11.13）版本新、类型全。
- 买断制 $14.99 三设备，性价比高，先试后买。

**Typora 缺点**
- 闭源 + 付费，无插件生态、无协作、无移动端、无云同步。
- 无跨文件全文搜索、无命令面板、无双链（纯单文档写作器）。
- v1.13 才试水 AI，且为预览版，远落后于 VS Code / 新晋 AI 原生工具。

**mdEditor vs Typora**：写作手感同一梯队；**mdEditor 反超项**——跨文件搜索、命令面板、版本历史 diff、斜杠菜单可配置、Office 级表格合并拆分、六主题+十风格换肤、全中文+中文输入兼容、绿色离线便携、启动更快、**已开源免费**。**落后项**——导出 Word 保真度（Typora Pandoc > python-docx 降级）、Mermaid 版本旧、无 PNG 导出、无移动端（Typora 跨三端）。

### 4.2 MarkText —— 免费平替

**MarkText 优点**
- 完全免费、MIT、与 Typora 同形态实时渲染；2026 已复活（0.19→0.20），v0.20 起靠 Pandoc 补 Word 导出。
- 体积可控、启动快于多数 Electron 应用。

**MarkText 缺点**
- 2022 前长期停滞，2026 虽复活但工程活跃度仍不及 Typora/Obsidian/SoloMD。
- 无内置 AI、无命令面板、无跨文件搜索（弱）、无版本历史；英文界面，中文体验弱。

**mdEditor vs MarkText**：两者同为 Typora 平替，但 mdEditor **功能面更广**（搜索/命令面板/版本历史/表格 Office 级/中文全栈/AI），且**已开源免费 + 跨平台**。MarkText 的唯一优势是跨平台 + 开源（现已不在 mdEditor 短板之列）。

### 4.3 Obsidian —— 知识库路线

**Obsidian 优点**
- 免费（个人/商业），双链 + 反向链接 + 图谱 + 1,500+ 插件，本地纯 .md 文件可控。
- Sync 付费但可选，移动端齐全，是"第二大脑"事实标准。

**Obsidian 缺点**
- 闭源核心，Sync $5/月；插件生态带来维护 / 安全面。
- "先知识库、后文件编辑器"，纯写作手感与渲染精致度不如 Typora/mdEditor。
- 表格等核心能力弱，需插件补；导出依赖插件。

**mdEditor vs Obsidian**：定位根本不同——Obsidian 是"知识库"，mdEditor 是"写作器"。mdEditor 在**写作手感、表格、图片、导出齐全度、离线绿色、启动速度**上占优；Obsidian 在**双链/反链/图谱/插件生态/跨端同步**上碾压。若用户要"写长文 + 偶尔检索"，mdEditor 更轻快；若要"建第二大脑"，Obsidian 不可替代。

### 4.4 VS Code —— 通用 IDE

**VS Code 优点**
- 免费 MIT、跨平台、Git 原生、插件海量、AI（Copilot）最强、代码高亮/多光标无敌。
- 跨文件搜索、命令面板是业界标杆。

**VS Code 缺点**
- **无就地渲染写作模式**（仅源码 + 分屏预览），默认 Markdown 体验"工具化"，无专注/打字机、排版不精美。
- 启动 3~5 秒，安装包 ~95MB，写纯 md 文档"杀鸡用牛刀"。

**mdEditor vs VS Code**：写 Markdown 文档的场景下，mdEditor 的**渲染写作手感、专注/打字机、表格可视化、图片/图表闭环、离线绿色、已开源**全面胜出；VS Code 仅在"顺手在 IDE 里改个 README"或"要 Git/AI/多光标"时更合适。两者互补而非替代。

### 4.5 SoloMD —— 2026 头号新晋（深度对标，v5.0.5）

> 数据口径（2026-10-25）：GitHub Releases **v5.0.5**（2026-10-22）为准；官网首屏 v4.6.2、KingDownloads 镜像 v4.11.17 均滞后/缓存，未二次验证。Stars 约 925（口径差异待核），近 90 天 100+ commits、30 个 releases，首次发布 2026-04 至今约 6.5 个月。

**SoloMD 画像**
- **技术栈**：Tauri 2 + Rust + Vue 3 + **CodeMirror 6**（单宿主·源码态；与 Typora 富文本单宿主、mdEditor 逐块多宿主均不同）。
- **授权/价格**：MIT 开源、$0 无订阅、无账号、零遥测。
- **平台**：**5 平台桌面+移动**（Win / macOS / Linux x64+ARM64 / Android API24+ / iOS 15+）；installer ~15MB（macOS universal 32MB；AppImage 因打包方式达 87MB）。14 种 UI 语言。
- **AI**：14 家 BYOK（含本地 Ollama，自动检测）+ Agent 面板 + Recipes 定时 Agent（cron/on-save/on-commit/on-tag）+ Per-run write cap + trace 回放。
- **同步/版本**：E2EE GitHub 同步 + **AutoGit**（独立分支 accept/reject）；**MCP sidecar** `solomd-mcp`（~1.5MB，stdio-only，13 个工具，含 5 个 SoloMD 独有：`autogit_log`/`autogit_diff`/`autogit_rollback`/`sync_status`/`share_url`），v4.0 起支持多 vault 联邦。
- **知识/检索**：本地 **RAG 语义搜索** + wikilink + 反向链接 + 图谱；Bases 属性表 / @citekey（Pandoc 端到端引用）。
- **编辑器基础设施**：Hunspell 拼写 + 中文校对、Vim 模式、演讲模式 ⌘⌥P、CJK 编码（GBK/Big5/Shift-JIS）自动识别；白板 tldraw 集成、Properties inspector。
- **硬性短板**：**表格是明确短板**（评测直言"没有像样的 WYSIWYG 表格编辑器"）—— 单宿主架构在单元格独立富文本上结构性吃亏。

**mdEditor vs SoloMD（同代对标结论）**
- **mdEditor 领先/护城河**：① Office 级表格（合并/拆分/拖选/列宽/导入 xlsx）—— SoloMD 结构性做不到；② Beyond Compare 式行级历史合并（对不会 git 的写作者更友好）；③ 书籍/长文档工作流（summary.md 目录树 + 章节 + BOOKLINK + 整本书 PDF/EPUB/HTML 站点导出）；④ AI 写作闭环质量（右键「AI优化」七动作 + 片段 diff + Ctrl+Z 可撤销 + Ollama 原生端 0.8s 直出）；⑤ 体积 8MB vs 15MB；⑥ 本地语义搜索零依赖（TF-IDF+同义词，不牺牲体积）。
- **SoloMD 领先**：① 5 平台含移动端；② MCP 13 tools 开发者生态；③ RAG 语义 + 图谱视图 + vault 联邦；④ Agent/Recipes 自动化；⑤ Hunspell 拼写 + Vim + 演讲模式 + CJK 编码识别。
- **基本持平**：写作手感（🟡 架构性差距约 0.5–1 分，非感知性）、导出（Pandoc 路线双方贯通）、图片、AI provider 数（mdEditor 15 vs SoloMD 14）、中文。

> 结论：SoloMD 是 2026 唯一在"免费 Typora 平替"心智上正面抢 mdEditor 用户的对手，但其表格短板 + 笔记库定位，恰好撞上 mdEditor 的两道护城河。mdEditor 的应对重点不在功能数量追赶，而在**守住表格/书籍/离线绿色/中文**，并补齐**移动端（G-1）**与**MCP/生态（G-9）**以堵住增长天花板。

---

## 五、mdEditor 自身优缺点（SWOT 精简）

**优点（Strengths）**
1. 块级 WYSIWYG 写作手感对标 Typora，桌面端体验优于 VS Code。
2. **中文全栈**：全中文界面 + 中文输入法混输兼容 + CJK 排版，竞品普遍不到位。
3. **已开源（Apache-2.0）+ 跨平台构建就绪**（Win 发布 / macOS 构建 / Linux 脚本），从闭源单机转为可审计、可社区共建。
4. 完全离线 + 绿色便携（拷文件夹即用）+ 启动 ~1.5s，无需账号。
5. 深度可定制：斜杠菜单优先级/默认项持久化、六主题 + 十界面风格整窗换肤。
6. 表格交互 Office 级（合并/拆分/拖拽/列宽行高/标注）；图片双模式（落盘/内嵌）+ 裁剪 + 尺寸对齐。
7. 检索与保全：跨文件全文搜索、本地语义搜索（零依赖）、版本历史快照 + 行级 diff、反链面板、未命名影子草稿。
8. 导出齐全：HTML（单文件离线）/PDF（书签）/Word/EPUB/Pandoc/复制富文本；AI 链路口（15 家 BYOK + 批量审查可撤销 + Ollama 原生端）。
9. KaTeX + Mermaid 全离线；自研内核迭代快，无插件维护负担。

**缺点（Weaknesses）**
1. ~~**仅 Windows**~~ → ✅ **已关闭（跨平台构建就绪）**。
2. ~~**闭源无生态**~~ → ✅ **已关闭（Apache-2.0 开源）**；无传统插件机制仍成立，但开源后社区生态可逐步建立。
3. 无双链图谱视图 / vault 联邦（通用 wikilink + 反链面板已落地，仍缺图谱与多库联邦）。
4. 无协作 / 多人实时编辑。
5. 无拼写检查（Hunspell）/ Vim 模式；无文档内跳转历史。
6. 导出 Word 依赖 python-docx，复杂表格/图表降级位图，不如 Typora Pandoc 保真；无 PNG 导出、无 LaTeX 高级定制。
7. Mermaid 9.x 较旧（Typora 已 11.13）。
8. 用户基数小，社区/生态薄弱；文档版本号仍有漂移技术债（README/CHANGELOG 需与发版同步）。

**机会（Opportunities）**
- 中文写作市场大；Typora 付费闭源持续留出"平替"需求，且 mdEditor 现已免费开源 + 跨平台。
- AI 已后置嵌入 **BYOK**（15 家，默认关闭、显式提示发往所选服务），无运维负担，且 Ollama 原生端让本地小模型真能用。
- 开源后：社区贡献、MCP server（暴露笔记库给 Claude/Cursor）是新的开发者增长极。
- "离线绿色 + 启动快 + 中文 + 跨平台"在政企内网 / 无网环境是刚需。

**威胁（Threats）**
- **SoloMD** 等 2026 新晋免费跨端 + AI 产品，正在重设"免费 Typora 平替"基线（但表格/书籍是其硬伤）。
- MarkText 复活、Obsidian 生态碾压、VS Code 通用无敌，挤压"纯写作器"空间。
- 移动端缺失使其在与 SoloMD 的"全平台"心智竞争中天然吃亏。

---

## 六、结论、定位与剩余差距

### 已领先或持平（守住，别在迭代中丢掉）
纯写作手感、中文全栈、离线绿色便携、启动速度、可定制菜单/换肤、Office 级表格、图片双模式+裁剪、跨文件搜索、本地语义搜索、版本历史、反链面板、导出齐全度、AI 链路口——这十数项已把旧报告的"18 项差距"闭合大半。

### 剩余差距（按可感知痛感排序，共 10 项核心）

| # | 差距 | 谁最擅长 | 痛感 | 建议 |
| --- | --- | --- | --- | --- |
| G-1 | **无移动端（iOS/Android）** | SoloMD | 🔴 高 | 跨平台桌面已就绪，移动端为下一增长天花板；先看 SoloMD 移动端市场反馈再决策 |
| G-2 | 无双链图谱视图 / vault 联邦 | Obsidian / SoloMD | 🔴 高 | wikilink + 反链面板已落地，补图谱视图 + 多库联邦即可对齐 |
| G-3 | 无协作 / 多人实时编辑 | Obsidian / VS Code | 🟠 中高 | 写作器定位可后置，先补单人保全 |
| G-4 | 无拼写检查（Hunspell）/ Vim 模式 | SoloMD / Typora | 🟠 中 | 离线词典（Hunspell zh/en）+ Vim 模式，中文场景可缓做 |
| G-5 | 无多光标之外的编辑器基础设施 | SoloMD / VS Code | 🟠 中 | 列选择 + 选中相同文本批量替换最小子集已做，续补跳转历史 |
| G-6 | 导出 Word 复杂表格/图表降级 | Typora | 🟠 中 | 强化 python-docx 映射，或优先走 pandoc 通道 |
| G-7 | Mermaid 版本旧（9.x vs 11.13） | Typora | 🟡 中低 | 升级内嵌 Mermaid |
| G-8 | 无 PNG 导出 | Typora | 🟡 低 | 渲染区截图导出（待核是否已部分支持） |
| G-9 | 无 MCP server / 插件生态 | SoloMD / VS Code | 🟡 中低 | read-only MCP（stdio，暴露当前 vault）复用 `semsearch` 索引，开发者增长极 |
| G-10 | 文档版本号漂移（README/CHANGELOG 同步） | — | 🟡 低 | 打包后同步文档头部版本（现 v3.48.20） |

> 已关闭项（不再计入差距）：仅 Windows（跨平台就绪）、闭源（Apache-2.0 开源）。

### 一句话定位建议

> **mdEditor = Typora 级的写作手感 + 全中文 + 可深度定制的菜单/换肤体系 + 绿色离线 + 开源免费 + 跨平台构建就绪的 Markdown 写作器**，面向"用 Markdown 写长文、写技术文档、做知识沉淀的中文用户"。

竞品各有硬伤（Typora 闭源付费、MarkText 曾停滞/英文界面、Obsidian 偏知识库且 Sync 付费、VS Code 无就地渲染、SoloMD 表格弱且笔记库思维），我们的差异化不在"功能数量"追赶，而在**中文写作手感 + 可定制性 + 轻量离线 + 表格/书籍护城河 + 现已开源跨平台**。下一阶段建议优先补 **移动端（G-1）** 与 **双链图谱/生态（G-2/G-9）**——前者破增长天花板，后者应对 2026 新晋产品的 AI + 知识库冲击；拼写检查/Vim/PNG 导出为体验补齐项，可顺手做。

---

## 附：与旧版（dist130 / v3.44.33）对比的演进

旧报告 18 项差距中，截至 v3.48.20 已闭合：图片落盘相对路径（P0-1）、字数统计（P0-2）、跨文件搜索（P0-3）、docx/EPUB/PDF 书签导出（P0-4）、自动配对（P1-1）、标题折叠（P1-2）、命令面板（P1-3）、脚注/上下标/定义列表（P1-4）、图片尺寸调整+表格列宽拖拽（P1-5）、版本历史（P1-6）、外部打开（P1-7）、Emoji 补全（P1-8）、**开源（Apache-2.0）**、**跨平台构建（Win/mac/Linux）**、本地语义搜索（v3.48.12）、通用 wikilink + 反链面板（v3.48.13）、AI 批量审查可撤销（v3.48.15）、多光标（v3.48.16）、Pandoc Word 贯通。

**仍未闭合**集中在：移动端、双链图谱/vault 联邦、协作、拼写检查/Vim、Word 保真、Mermaid 升级、PNG 导出、MCP/插件生态、文档版本同步（即上文 G-1~G-10，原 #1 仅Windows 与 #2 闭源已关闭）。

> 本报告 mdEditor 侧结论均可回溯至 `src/` 源码或 `CHANGELOG.md` 逐条验证；SoloMD 侧结论基于官网 + GitHub 元数据 + 第三方评测交叉验证，未安装实测，有效期约 2–4 周。
