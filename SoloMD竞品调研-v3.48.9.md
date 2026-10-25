# SoloMD 竞品深度调研（更新版 · v3.48.9 基准）

> 调研时间：**2026-10-24**　｜　上一版：2026-10-22（`SoloMD竞品调研-v3.44.33.md`，v3.44.33 基准）
> 本版更新原因：mdEditor 两日内从 **v3.44.33 → v3.48.9**（dist165），且几乎逐项兑现了上一版报告提出的 P0/P1 建议（跨平台 / AI BYOK / PNG 导出 / 表格导入）。本版因此不是重述，而是**刷新基线 + 追踪建议落地 + 重估剩余差距**。
> mdEditor 事实来源：`src/config.py`（`APP_VERSION="3.48.9"`）、`CHANGELOG.md`（v3.45.0~v3.48.9 条目）、`src/ai_core.py`、`build_mac.sh` / `build_linux.sh`、产物 Glob 扫描。
> SoloMD 事实来源：官网 solomd.app、GitHub 快照（beeknoee / agentindex，2026-10-18~10-22）、Microsoft Store 页面。
> 可信度：仍**未亲自安装 SoloMD 实测**；mdEditor 侧已尽量回到源码/产物核对。凡未能证实处标注「待核」。

---

## 〇、本次更新摘要（先给结论）

| 上一版（10-22）判断 | 当前状态（10-24） | 结论 |
|---|---|---|
| 差距 #1 **跨平台**是 P0 天花板 | **v3.47.0 已建跨平台构建体系**（build.py + build_mac.sh + build_linux.sh），抽象了 secretstore / trash / openutil / 盘符枚举 / 无边框守卫 | ⚠️ **代码层就绪，分发层未落地**——无任何 AppImage/dmg/deb 产物，dist161/164/165 仍全为 Windows |
| 差距 #3 **AI BYOK** 建议优先补 | **v3.46.0 起步 → v3.47.x~v3.48.x 深度落地**：15 家 OpenAI 兼容预设（含本地 Ollama，v3.47.3 起为**默认 provider**）、SSE 流式、独立连接面板、诊断日志 `ai.log`、右键「AI优化」子菜单（润色/精简/扩写/纠错/翻译/改语气）、片段对比插入、插入到光标且**可 Ctrl+Z 撤销** | ✅ **AI 差距基本闭合**（缺 Agent 自动化，见后） |
| 建议首要补 **本地语义搜索** | 未启动 | ❌ 仍是 Singleton 差距 |
| 差距 #2 **双链/知识库** 排 P2 | v3.45.0 落地 **BOOKLINK 书籍内链接**（`[[目标#锚\|别名]]`、锚点诊断、批量修复、导出解析）；此前曾有「反向链接」页签后迁入书籍页 | 🟡 **部分闭合**——书籍场景有，通用 vault 双链 / 关系图 / Properties inspector 仍缺；而 SoloMD 4.6 正强化这块，**建议上调优先级** |
| 建议强化表格护城河 | v3.46.0 新增「文件 → 导入表格…」（xlsx/xlsm/csv） | ✅ 护城河加厚 |
| 清单 #8 PNG 导出 | v3.45.8 已补「导出图片 (PNG)…」 | ✅ 闭合 |
| 多光标（清单 #5） | 未做。v3.48.0 F2 做的是**跨块选区叠加层**（解决"选不中多段"），非多光标编辑 | ❌ 仍缺 |

---

## 一、双端现状速览

### mdEditor v3.48.9（dist165，2026-10-24）
- **形态**：Python + PySide6(QtWebEngine) 外壳 + 单文件 JS 内核，块级 WYSIWYG；近两日主线三是 **AI 助手打磨**（v3.47.2~v3.48.9 连续 9 个版本修 AI 链路）+ **跨平台基建**（v3.47.0）+ **历史版本 Beyond Compare 式行级合并**（v3.48.2/3/5）。
- **产物**：Windows onedir（exe 约 8.0–8.3MB，dist 目录含 Qt 全套 ~603 文件）+ Inno Setup 安装包 `installer/mdEditor-setup-3.45.8.exe` + 打包 zip `release/mdEditor-v3.44.32-win64.zip`（约 217MB）。
- **近两日关键能力增量**：AI 助手（15 provider + Ollama 默认 + 流式 + 诊断日志 + 可撤销插入 + reasoning 思考模型兼容）、跨平台脚本、书籍 BOOKLINK 双链、表格导入、PNG 导出、PDF 导出设置（页边距/字体/字号）、历史合并审阅、目录下手动插入。

### SoloMD v5.0.4 / GitHub 线 4.6（2026-10-20~22）
- **定位升级**：由 "the bridge to your LLM" 变为 **"The editor where agents live"**（agents 第一）。
- **规模**（GitHub 快照 10-18~10-22）：⭐ 约 1.3k、下载 75,655+、贡献者 30、fork 91、Issues 80~102、2026-04-08 建库、主语言 TypeScript。
- **新动向**：**4.6 知识图谱层**（Properties inspector ⌘⇧I、Type-driven sidebar、Typed relationships 含自动反向链接、Relationship graph "Neighborhood"）；**Gitee 镜像**（中国下载加速）+ 13 语种 README（中/日/韩/德/法/西/葡/意/波/荷/土/瑞典/乌克兰）——**中文市场投放意图明确**。
- **版本口径提示**：官网称 v5.0.4（2026-10-20），GitHub README 强调 "New in 4.6" 知识图谱层，两个来源版本号不一致（**待核**，可能 5.0 为 UI 重设计线、4.6 为功能线）。

---

## 二、上一版建议 → 落地追踪（本表是本版核心价值）

| 优先级 | 建议能力 | 落地情况 | 证据 |
|---|---|---|---|
| **P0** | 跨平台构建（打包/测试矩阵） | **部分**：构建体系建成，产物未出 | `build_mac.sh`/`build_linux.sh` 存在且完整（含 codesign/notarytool/AppImage/.deb）；但 Glob 扫描**无任何 .AppImage/.dmg/.deb/.rpm** |
| **P1** | AI BYOK 轻量入口（选中即问 + 本地 Ollama） | **达成并超出** | `ai_core.py` PROVIDERS 含 deepseek/qwen/siliconflow/openrouter/**ollama**；v3.47.3 缺省 provider=`ollama`、base=`http://localhost:11434/v1`；悬浮「💬 问 AI」→右键「AI优化」子菜单 |
| **P1** | 本地语义/向量搜索 | 未启动 | CHANGELOG 未见相关条目 |
| **P2** | 双链 / 反向链接 / 关系图 | **部分（书籍域）** | v3.45.0 BOOKLINK；通用 vault 层未见 |
| **P2** | 强化表格（Excel/CSV 导入等） | **达成** | v3.46.0「文件 → 导入表格…」 |
| **P3** | Pandoc/高保真导出、PNG 导出 | PNG 达成，Word 保真未动 | v3.45.8 PNG 导出；Word 仍走 python-docx |
| — | 多光标 | 未做 | v3.48.0 F2 是跨块**选区**，非多光标 |

---

## 三、刷新版：20 维对比矩阵

> mdEditor 列已按 v3.48.9 事实重写；🆕 = 相对上一版发生变化。

| # | 维度 | SoloMD | mdEditor v3.48.9 | 胜方 |
|---|---|---|---|---|
| 1 | 价格 | 免费 | 免费 | 平 |
| 2 | 开源 | **MIT** | 闭源 | SoloMD |
| 3 | 平台 | **5 平台**（macOS/Win x64+ARM64/Linux x64+ARM/iOS/Android） | 🆕 **代码层三平台就绪，实际仅 Windows 有产物** | SoloMD |
| 4 | 分发体量 | ~15MB 安装包（Mac~32MB），空闲 80–150MB | Windows 安装包 + onedir（exe 8.0–8.3MB，总目录 ~200MB 级） | SoloMD |
| 5 | 编辑范式 | 实时 WYSIWYG + 源码 + 分栏 + 预览四视图 | 块级 WYSIWYG + 源码/预览/分屏 + 🆕 跨块选区叠加 | 平 |
| 6 | **表格** | 弱（无像样 WYSIWYG 表格编辑器） | **Office 级**（合并/拆分/拖选/列宽/行高 + 🆕 Excel·CSV 导入） | **mdEditor** |
| 7 | 图片 | 粘贴落 `_assets` | 相对路径 / 内嵌双模式 + 裁剪 + 尺寸 + 状态栏存储显示 | mdEditor |
| 8 | 中文支持 | GBK/Big5/UTF-16 识别、简繁转换、拼音、CJK 字数 | 全中文 UI + CJK 字数；GBK/简繁**待核** | SoloMD（更系统） |
| 9 | **知识管理** | Wiki 双链 + 反向链接 + **4.6 关系图 + Properties inspector + Type-driven sidebar + 白板** | 🆕 仅**书籍域** BOOKLINK 双链 + 锚点诊断 + 批量修复 | **SoloMD** |
| 10 | **AI** | 14 BYOK + Ollama + Agent 面板 + 定时食谱 + AutoGit 沙箱 + 可回放 trace | 🆕 **15 provider + Ollama 默认 + 流式 + 诊断日志 + 右键 AI 子菜单 + 片段对比插入 + 可撤销** | **平手**（见下方判词） |
| 11 | 搜索 | **本地 RAG 语义搜索** | 跨文件全文检索（无语义） | SoloMD |
| 12 | 版本历史 | AutoGit 每次保存本地快照 + 分支 accept/reject | 文档级历史对话框 + 🆕 **Beyond Compare 式行级合并 / 冲突标记 / 差异助手** | **mdEditor**（更直观） |
| 13 | 同步/多端 | 文件夹同步 + GitHub/E2EE + 移动端原生 | 无 | SoloMD |
| 14 | 导出保真 | **Pandoc**：DOCX/EPUB/ODT/LaTeX/RTF/PDF(公式图表内嵌) | docx/EPUB/PDF(书签/页边距/字体设置) + 🆕 PNG；Word 保真弱于 Pandoc | SoloMD |
| 15 | 扩展性 | 刻意无插件；有 **MCP server**（13 工具，含 AutoGit log/diff/rollback） | 闭源无生态、无 MCP | SoloMD |
| 16 | 移动端 | **iOS/Android 原生** | 无 | SoloMD |
| 17 | 隐私/离线 | 无账号/无遥测/MIT/纯 .md | 完全离线/本地 .md/无账号；🆕 API Key 跨平台密钥环（wincred/Keychain/secret-tool） | 平 |
| 18 | 命令面板/快捷键 | Ctrl+Shift+K；自定义快捷键疑似不支持 | 命令面板；快捷键设置（v3.7 起） | mdEditor（略优，待核自定义程度） |
| 19 | 主题/自定义 | 浅/深跟随系统 + 自定义 CSS | 六主题 + 多界面风格 + 图表六主题 | mdEditor |
| 20 | 启动速度 | Tauri 轻量快 | ~1.5s（历史实测；🆕 AI 依赖后**待复测**） | 平（待核） |

**第 10 项（AI）判词**：两者路线不同，难分绝对胜负。SoloMD 强在 **Agent 自动化**（定时食谱、AutoGit 分支沙箱、可回放 trace、多 vault MCP 联合），适合"让 AI 替我干活"；mdEditor 强在**写作闭环**（选中润色/扩写/翻译/改语气、片段对比后替换、可撤销、本地 Ollama 默认零成本零外发、诊断日志排障），更适合"我写 AI 帮我改一句"。**对本项目的中文写作用户，mdEditor 的克制路线反而是对的**；缺的是 SoloMD 那种"可审查的批量自动化"。

---

## 四、差距格局重估

**已闭合**：AI BYOK（含本地 Ollama）、表格导入、PNG 导出、书籍域双链。
**已缩小**：跨平台（从"不可能"→"待上机构建验证"）、版本历史（反而反超一行级合并）。
**仍是主战场**（建议作为下一阶段焦点）：
1. **跨平台真产物**——QtWebEngine 在 macOS/Linux 的坑（codesign/公证、libnss3 等 QtWebEngine 依赖）脚本注释里自己已列出，**风险在构建机而不在代码**。建议尽快找一台 macOS/Linux 跑一次 `build_mac.sh` / `build_linux.sh`，哪怕只是 await validation。
2. **通用双链 / 知识图谱**——SoloMD 4.6 正在这块发力，而我们只有书籍域。考虑把 BOOKLINK 的 slug/解析能力**推广到普通 vault**（不必一步到关系图，先做 `[[wikilink]]` 解析 + 反向链接面板）。
3. **本地语义搜索**——差距最尖锐的一项且未被启动；可先做离线 embedding + sqlite 索引（SoloMD 同款技术路径，`.solomd/embeddings.sqlite` 可参照）。
4. 次级补齐：Word 保真（Pandoc 路线）、多光标（Ctrl+D / Alt+Click）、公开 vinegar 后站 Skip。

---

## 五、mdEditor 应坚守并放大的护城河（含新发现）

1. **Office 级表格**——SoloMD 最弱处，且 v3.46 加了 Excel/CSV 导入后更完整（"从 Excel 迁过来直接编辑"是实打实的迁移理由）。
2. **🆕 书籍 / 长文档工作流**——`summary.md` 目录树 + 章节 + BOOKLINK 双链 + 整本书 PDF/EPUB/HTML 站点导出 + 目录下手动插入。这是 **SoloMD（笔记库思维）没有的形态差异**，值得作为独立卖点。
3. **🆕 历史版本行级合并**——超越 SoloMD 的"分支 accept/reject"，对不会 git 的写作者友好得多。
4. **Windows 原生体验**——标准安装包（Inno Setup）、文件关联、回收站、凭据管理器；WebView 跨端应用难做到同深度。
5. **图片全链路**——双存储模式 + 裁剪 + 尺寸 + 状态栏存储方式。
6. **块级渲染健壮性**——大量 FMT-*/MMD-* 根修沉淀，交互细节成熟度高于年轻项目。

---

## 六、下一步行动建议（重排）

| 优先级 | 行动 | 理由 |
|---|---|---|
| **P0** | 在真实 macOS / Linux 上跑一次 `build_mac.sh` / `build_linux.sh`，产出并验证首个 .dmg / .AppImage | 代码已就绪，**唯一缺口是没上机**；这是发财捷径也是最大未知风险 |
| **P1** | 本地语义搜索（离线 embedding + sqlite，可开关，索引不入 Git） | SoloMD 有的我们独缺，且技术路径已被验证 |
| **P1** | 把 BOOKLINK 推广到普通文档：`[[wikilink]]` 解析 + 反向链接面板 | 与已有资产同源，收益杠杆高（不必先做关系图） |
| **P2** | AI 侧：增加**可审查的批量操作**（如"对全书/全文执行同一提示词，结果先预览 diff 再应用"） | 吸收 SoloMD AutoGit 沙箱的"安全感"，但不引入 git 复杂度 |
| **P2** | 多光标（Ctrl+D 选中下一个相同词 / Alt+点击） | 竞品普遍具备，用户会问 |
| **P3** | Word 导出引入 Pandoc 路线 | 提升办公交付保真度 |
| — | 移动端 / CRDT 同步 | SoloMD 也在 roadmap（未落地），非当前瓶颈，继续观察 |

---

## 七、风险与待核项

- **SoloMD 版本号口径冲突**（官网 v5.0.4 ↔ GitHub "New in 4.6"），后续引用需注明来源与抓取日期。
- **未实测 SoloMD**：其宣称的"本地 RAG 语义搜索""13 MCP 工具"等未亲手验证；建议后续找一台机装一下做实感对比（尤其表格编辑体验与我们对比）。
- mdEditor 侧待核：GBK/Big5 自动识别、简繁转换、快捷键自定义程度、AI 依赖引入后的冷启动耗时是否仍 ~1.5s。
- **信息时效性**：SoloMD 迭代极快（周级 release），本建议有效期约 2–4 周，之后需再刷新。

---

## 八、信息来源
- `src/config.py`、`CHANGELOG.md`（v3.45.0~v3.48.9）、`src/ai_core.py`、`build_mac.sh`、`build_linux.sh`、产物 Glob 扫描（本地核对）
- SoloMD 官网 https://solomd.app/（英文）/ https://solomd.app/zh（中文）
- GitHub 快照 https://platform.beeknoee.com/github/zhitongblog/solomd、https://agentindex.app/tool/zhitongblog-solomd
- Microsoft Store https://www.microsoft.com/zh-cn/p/solomd/9nxghk2ll1q4
- 上一版报告 `SoloMD竞品调研-v3.44.33.md`（2026-10-22）
