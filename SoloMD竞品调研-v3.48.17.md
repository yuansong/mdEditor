# SoloMD 竞品深度调研 · 差距追踪更新版

> **mdEditor 基线**：v3.48.17（dist173），exe 8,440,211 B ≈ **8.05 MB**
> **调研日期**：2026-10-25
> **上一版**：`SoloMD竞品调研-v3.48.9.md`（基线 v3.48.9 / dist165）
> **性质**：本报告不是重做，而是**差距项刷新**——重点回答「上一版列出的差距，现在还剩多少」。

---

## 〇、一句话结论

**上一版列的 6 项待办，5 项已落地（且是并行会话明确标注「SoloMD 对标」推进的）；唯一没动的是 P0 跨平台——而它恰恰是投入最小（约 3 人天）、收益最大（+6 分、可直接反超 SoloMD）的那一项。**

当前差距已从「面状落后」收敛为「**单点卡死**」：跨平台 / 移动端。其余维度基本拉平，部分（表格、历史合并、书籍工作流、体积）保持领先。

---

## 一、上一版建议 → 落地追踪（本版核心）

| # | 上一版建议 | 优先级 | 状态 | 证据 / 版本 |
|---|---|---|---|---|
| 1 | macOS/Linux 真机各跑一次构建 | **P0** | ❌ **完全未启动** | `find` 全仓扫描：**无任何 `.dmg` / `.AppImage` / `.deb` / `.rpm` / `.app`**；`installer/` 仅 `mdEditor-setup-3.45.8.exe`；`release/` 仅 `mdEditor-v3.44.32-win64.zip`（均为 Windows 且停留在旧版本）。`build.py`(177行)/`build_mac.sh`(104行)/`build_linux.sh`(151行) 三者**文件存在但从未产生产物** |
| 2 | 本地语义搜索 | P1-1 | ✅ **达成** | **v3.48.12（dist168）SEM-1~4**：新增 `src/semsearch.py`（24 KB，纯标准库零依赖）。TF-IDF 稀疏向量 + sqlite 倒排 + ~50 组中英同义词；中文 bigram 切词；「搜索」可召回写「检索」的段落。入口=查找对话框「语义搜索」勾选，背景 QThread，相关度 pct% |
| 3 | BOOKLINK 推广到通用 vault 双链 | P1-2 | ✅ **达成（超出预期）** | **v3.48.13（dist169）BACKLINK-4**：调研时实证 `[[X#锚\|别名]]` 的解析/渲染/序列化/导出/`[[` 补全**早已是通用实现**（此前误判为书籍域专属），唯一缺口只是反链面板 → 新增侧栏第 4 页签「反链」(`TAB_BACKLINKS=3`)、`refresh_backlinks()`、`Ctrl+Alt+B` |
| 4 | AI 可审查批量操作 | P2-1 | ✅ **达成** | **v3.48.15（dist171）AI-BATCH**：`AIBatchDialog` 三页向导（配置→执行→审查），`_batch_split_blocks` 分段 + `_batch_diff_html` 行级 diff（红删/绿增），逐条「采纳/跳过」+ 全选，经 `apply_ai_insert` 写回且 **Ctrl+Z 可撤销** |
| 5 | 多光标 | P2-2 | ✅ **达成** | **v3.48.16（dist172）MC**：`Ctrl+D` 选择下一个相同词（VS Code 语义）+ `Alt+点击` 增删光标；`mcDescs[]` 为唯一事实源；**beforeinput 同步管道**处理 insertText / deleteContentBackward / insertLineBreak；`mcIsWordCh` 排除 CJK 标点 0x3000-303F 与全角 0xFF00-FFEF（「苹果」不误中「苹果汁」）|
| 6 | Pandoc 提 Word 保真 | P3-1 | ✅ **无需改动，验收确认已存在** | **v3.48.16** 验收探针实证：`exporters.find_pandoc` / `pandoc_convert` + 设置项 `pandocPath` + 单文档与整书 pandoc 优先、内置回退、未安装预警——**路线早已完整**，上一版列为差距是误判 |

**净结果**：5/6 落地。**未完成的那一项 = 全场 ROI 最高的一项。**

> ⚠️ 需更正我自己的两处旧判断：
> 1. 《评分榜 v3.48.11》中「写作手感」扣分的理由写了「无多光标」——**该依据已作废**（v3.48.16 已落地）。
> 2. 上一版 SoloMD 调研把 Pandoc Word 列为差距——**经核误判**，实际早已贯通。

---

## 二、SoloMD 情报刷新（2026-10-25）

### 版本口径（三源冲突，标注待核）

| 来源 | 版本号 | 日期 |
|---|---|---|
| GitHub Releases | **v5.0.5** | 2026-10-22 |
| 官网 solomd.app 首屏 | v4.6.2 | 2026-06-12（疑为页面缓存） |
| KingDownloads 镜像 | v4.11.17 | 2026-08-24（第三方镜像滞后） |

以 GitHub 为准 → **v5.0.5**。另：README 仍写 "New in 4.6"，与 release tag 不同步。

### 活跃度（较上次进一步攀升）

- Stars：**925**（上次调研口径 ~372，口径差异可能来自不同镜像，待核）
- Commits 近 90 天：**100+**；近 12 周周峰值 **181 commits**
- Releases 近 90 天：**30 个**；Open issues 82
- 首次发布 2026-04-08 → **至今约 6.5 个月做到 925 星**，增长曲线陡峭

### 上次调研后新增/确认的能力（构成新的追赶目标）

| 能力 | 说明 | mdEditor 有否 |
|---|---|---|
| **MCP sidecar** | 捆绑 `solomd-mcp`（1.5 MB），stdio-only，**13 个工具**（其中 5 个 SoloMD 独有：`autogit_log`/`autogit_diff`/`autogit_rollback`/`sync_status`/`share_url`）；v4.0 起支持 `--workspace path1 --workspace path2` **多 vault 联邦** | ❌ **无**（`grep -ril "mcp" src/*.py` 零命中）|
| **solomd agent CLI** | 把任务直接交给 Claude Code / Codex CLI，MCP 已预连 | ❌ 无 |
| **白板 tldraw 集成** | markdown-backed | ❌ 无（grep 零命中）|
| **Properties inspector** | YAML frontmatter 表格化属性编辑 | ❌ 无（grep frontmatter 零命中）|
| **Recipes 定时 Agent** | YAML in `.solomd/agents/*.yml`，触发器 cron / on-save / on-commit / on-tag-add / 手动 | ❌ 无 |
| **Per-run write cap** | 默认 5 次写入上限 + AutoGit 独立分支 accept/reject + `trace.jsonl` 可回放 | 🟡 mdEditor v3.48.15 AI-BATCH 提供「逐条采纳/跳过 + 可撤销」，机制不同但**审查语义已覆盖**，缺 write-cap 与 trace 回放 |
| Bases 属性表 / @citekey | Pandoc 端到端 citing | ❌ 无 |
| **编辑器基础设施** | Hunspell 拼写 + 中文校对、Vim 模式、演讲模式 ⌘⌥P、CJK 编码（GBK/Big5/Shift-JIS）自动识别 | ❌ 无 Hunspell / Vim；演讲模式待核 |

### 未变的部分（交叉验证一致）

- MIT 开源、$0 无订阅、无账号、零遥测
- Tauri 2 + Rust + Vue 3 + **CodeMirror 6**（单宿主·源码态；/Typora 的富文本单宿主不同）
- 14 家 BYOK AI（含本地 Ollama，自动检测）
- 5 平台桌面+移动（Win / macOS / Linux x64+ARM64 / Android API24+ / iOS 15+）
- installer ~15 MB（macOS universal 32 MB；AppImage 因打包方式达 87 MB）
- 14 种 UI 语言
- **表格仍是短板**：评测直言「没有像样的 WYSIWYG 表格编辑器」

---

## 三、mdEditor 侧同期增量（v3.48.9 → v3.48.17）

除上述 5 项对标外，这期间还加固了 AI 链路的可靠性——差异不在功能清单，而在「纸上能用」与「实际能用」之间：

| 版本 | 关键修复 | 意义 |
|---|---|---|
| v3.48.11 | reasoning-only 兜底：**Ollama 追加 `think:false`**；AI 插入一键直达；「显示思考过程」开关；片段替换 MergeDialog 化（行级 diff） | AI 从「能跑」到「本地小模型也真的能用」 |
| v3.48.14 | Ollama **原生端 `/api/chat` 通道**（NDJSON），think:false 原生可靠生效，失败回退兼容端 | 实测 **0.8s 直出正文**（旧路径 175s 零正文）——质的跨越 |
| v3.48.17 | SEM-FIX 三修：结果三重过滤+失效回收 / 新查询不再被忙态吞 / worker 引用兜底（修 0xC0000409 析构崩溃） | 语义搜索从 demo 到生产可用 |

**AI provider 数核实**：`src/ai_core.py` 实装 **15 家**（openai / deepseek / qwen / glm / kimi / siliconflow / gemini / azure / openrouter / minimax / baichuan / mistral / together / **ollama** / custom）——**与 SoloMD 的 14 家持平**。

**测试资产**：现有 `tests/_probe_*.py` **15 个探针**，本期间新增/重写 `_probe_semsearch`(39)、`_probe_backlinks`(32)、`_probe_mc`(41)、`_probe_aibatch`(86)、`_probe_pandoc`(26)、`_probe_aifrag`(38)——**覆盖率显著提升**。

---

## 四、刷新版差距矩阵

> ✅ 持平或领先｜🟡 部分差距｜❌ 明确差距

| 维度 | SoloMD | mdEditor v3.48.17 | 判定 |
|---|---|---|---|
| **写作手感** | CM6 单宿主，原生选区/撤销；Vim 模式 | 逐块多宿主 + 已补丁化（F2 跨块选区、MC 多光标） | 🟡 差距约 0.5–1 分（架构性，非感知性）|
| **表格 Office 级** | ❌ 明确短板 | ✅ 合并/拆分/拖选/列宽/导入 xlsx | ✅ **领先（唯一全场第一项）** |
| **导出** | Pandoc PDF/DOCX/EPUB/ODT/LaTeX + @citekey | Pandoc 路线已贯通（v3.48.16 验收）+ 内置回退 + PNG | ✅ 基本持平（缺 citekey）|
| **图片** | 粘贴到 `_assets/` | 图片双模式 + 落盘/裁剪 | ✅ 持平 |
| **检索 / 知识** | 本地 RAG 语义 + wikilink + 反链 + 图谱 | **语义搜索 ✅ + 反链面板 ✅**（缺图谱视图、缺 vault 联邦） | 🟡 差距**大幅收窄**（原 −5 → 现约 −1~2）|
| **AI** | 14 BYOK + Agent 面板 + Recipes 定时 + write-cap + trace | **15 家 + 批量审查 + 可撤销 + Ollama 原生端** | 🟡 写作闭环更强，自动化更弱 |
| **平台 / 同步** | **5 平台含 iOS/Android** ~15MB | **仅 Windows 有产物**，无 macOS/Linux 产物 | ❌ **唯一结构性差距** |
| **性能 / 体积** | ~15MB install，空闲 80–150MB | **8.05MB** exe | ✅ **领先** |
| **开放生态** | MIT 开源 + **MCP 13 tools** + CLI + 联邦 | 闭源，无 MCP / 无插件 | ❌ 差距（生态维度）|
| **中文** | GBK/Big5/Shift-JIS 识别、CJK 计数、简繁转换、14 语言 | 全中文 UI + CJK 安全的多光标分词 | ✅ 持平偏优 |

### 剩余差距清单（按痛感排序）

| # | 差距 | 性质 | 成本估计 |
|---|---|---|---|
| **G1** | **跨平台无产物**（macOS .dmg / Linux .deb·AppImage） | 阻塞增长天花板 | **约 3 人天**（脚本 v3.47.0 已就绪） |
| G2 | 无 iOS / Android 移动端 | SoloMD 亦刚起，实际可用性待核 | 数月（架构级） |
| **G3** | 无 MCP server 暴露笔记库给 Claude/Cursor | 开发者向，新增长极 | 约 5–10 人天 |
| G4 | 无白板 / Properties / Bases 属性表 | PKM 扩展能力 | 各 1–2 周 |
| G5 | 无拼写检查（Hunspell）/ Vim 模式 | 体验补齐 | Vim 约 1 周；拼写约 3 天 |
| G6 | 无关系图谱视图 | 视觉向 | 约 1 周 |
| G7 | 闭源、无插件生态 | 战略选择 | 需决策 |

---

## 五、mdEditor 仍保持的护城河（SoloMD 打不到）

1. **Office 级表格**（9/10）—— 源码单宿主这条路走到头就是 "| --- |" 文本，**结构性做不到**；mdEditor 的逐块宿主让单元格天然是独立富文本区。这是同一枚硬币的两面：多宿主牺牲了选区连续性，换来表格独占优势。
2. **Beyond Compare 式行级历史合并**（v3.48.2/3/5）—— 对**不会 git 的写作者**远比 SoloMD 的 AutoGit 分支 accept/reject 友好。
3. **书籍 / 长文档工作流** —— summary.md 目录树 + 章节 + BOOKLINK + 整本书 PDF/EPUB/HTML 站点导出。SoloMD 是笔记库思维，没有这种形态。
4. **AI 写作闭环质量** —— 右键「AI优化」七动作 + 片段 diff 替换 + **Ctrl+Z 可撤销** + Ollama 原生端 0.8s 直出。比 SoloMD 的 Agent 路线更贴合「改一句话」的真实场景。
5. **体积 8.05MB vs 15MB**（vs Typora ~70MB / Obsidian ~110MB）。
6. **本地语义搜索零依赖** —— SoloMD 用 embedding（模型重量级），mdEditor 用 TF-IDF+同义词，**不牺牲体积**，且中文同义召回可用。

---

## 六、建议重排

### 为什么 G1 现在是唯一该做的事

| 项 | 成本 | 收益 | ROI |
|---|---|---|---|
| **G1 跨平台真机构建** | ~3 人天 | **+6 分（77→83 反超 SoloMD）** | ⭐⭐⭐⭐⭐ |
| G3 MCP server | ~5–10 人天 | +2~3 分 + 开发者增长极 | ⭐⭐⭐ |
| G4 白板/Properties | ~2–3 周 | +1~2 分 | ⭐⭐ |
| G5 Vim/拼写 | ~1.5 周 | +0.5~1 分 | ⭐⭐ |
| G6 图谱视图 | ~1 周 | +0.5 分 | ⭐ |

**G1 的脚本已经写好了**（`build.py` 177 行 + `build_mac.sh` 104 行 + `build_linux.sh` 151 行），缺的不是代码，是**一次真机执行**。配套依赖也都不缺：Pandoc 导出链路已贯通、无需新增第三方运行时。**唯二风险**是 macOS codesign/公证账号、以及 Linux QtWebEngine 的 libnss3 之类运行时依赖——都需要真机才能暴露。

### 执行顺序建议

1. **本周**：`build_mac.sh` / `build_linux.sh` 各真机跑一次，固化 `.dmg` / `.AppImage` / `.deb` 到 `release/`，更新 `installer/`。这是当前唯一能让 mdEditor 反超 SoloMD 的动作。
2. **下周**：G3 MCP read-only server（stdio，8–13 tools 暴露当前 vault）—— 这是 SoloMD v4.0 后的主要增长引擎，且 mdEditor 已有现成的 `semsearch` 索引可复用为后端。
3. **之后**：按 G4 → G5 顺序补齐 PKM 面。
4. **暂缓**：G2 移动端（SoloMD 自己的移动端成熟度也待核，先看市场反馈再决策）。

---

## 七、待核事项（诚实标注）

| 项 | 状态 |
|---|---|
| SoloMD 版本号口径冲突（v5.0.5 / v4.6.2 / v4.11.17） | 本版以 GitHub v5.0.5 为准，**未二次验证** |
| SoloMD Star 数（925 vs 372） | 镜像口径差异，须以 GitHub 页面为准 |
| SoloMD 表格短板的实测程度 | 沿用第三方评测表述，**未亲自安装实测** |
| SoloMD 移动端（iOS/Android）实际完成度 | 仅依据分发页面存在安装包，**未测可用性** |
| mdEditor 是否有演讲/演示模式 | 本轮未核实 |

**本报告所有 mdEditor 侧结论均可回溯至 `src/` 源码或 `CHANGELOG.md` 逐条验证；所有 SoloMD 侧结论基于官网 + GitHub 元数据 + 第三方评测交叉验证，未安装实测。SoloMD 迭代为周级，本报告有效期约 2–4 周。**
