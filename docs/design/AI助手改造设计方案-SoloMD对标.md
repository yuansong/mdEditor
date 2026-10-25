# mdEditor AI 助手改造设计方案（对标 SoloMD）

> 目标：把现有 v3.47.x 的「BYOK 轻量入口」重做成与 **SoloMD** 同量级、同交互质感、同隐私立场的 AI 能力体系。
> 范围覆盖用户点名的三块：**模型设置模块**、**智能体问答界面（Agent Panel）**、以及 SoloMD 标志性的**行内改写（⌘J diff 浮层）**。
> 设计依据：SoloMD 官方文档（solomd.app/docs/ai、/agents、v2.0 博客）与社区实测反馈；现有代码见 `src/ai_pane.py` / `src/mainwindow.py:AIBridge` / `src/editor.html` 浮动栏 `ai-ask`。

---

## 0. 现状盘点（改造前）

| 能力 | 当前状态 | 与 SoloMD 的差距 |
|---|---|---|
| 模型设置 | 面板内 3 个输入框（Base/Model/Key）+ 保存/测试/检测 Ollama | 无 provider 预设、无状态点、测试仅 ping、无"安装 Ollama"按钮 |
| 问答 | 右侧停靠面板，非流式整包返回，气泡式 | 无流式、无停止/重试、无工具卡、无 Trace、无引用跳转 |
| 改写 | 「改写选中内容」按钮，直接替换 | 无动作菜单、无 diff 并排对比、无接受/拒绝/重生成 |
| 上下文 | 仅"选中即问"预填输入区 | 无"当前笔记上下文"开关、无 vault 检索 |
| 隐私/日志 | 无结构化日志 | 异常被 `str(e)` 吞掉，难以回溯 |

**关键代码事实**
- 问答走 `AIWorker`（非流式、`stream:False`、`urlopen(timeout=60)`，见 `ai_pane.py:39-64`）。
- 连接测试 `_on_test` 仅发 `{"content":"ping"}` 成功即判"连接成功"（`ai_pane.py:214-223`）。
- 面板挂载于 `QDockWidget("AI 助手")`，`mainwindow.py:644-650`；桥接 `AIBridge` 提供 `settings/get_selection/replace_selection/insert_at_caret`（`:7039-7057`）。

---

## 1. 设计原则（沿用 SoloMD 立场）

1. **BYOK + Local-first**：默认关闭 AI，开启后既可用云（自带 key）也可全本地（Ollama，零成本、最强隐私）。
2. **不经过中间服务器**：请求直达用户配置的 provider；Ollama 全程本机。
3. **无后台上传**：任何 AI 调用都需用户显式触发，绝不在后台上传笔记内容。
4. **密钥入 OS 钥匙串**：复用现有 `secretstore`（Windows 凭据管理器），不进明文配置。
5. **克制克制的视觉**：系统字体、浅/深自适应、细边框、圆角、状态点；信息密度低、留白足。

---

## 2. 模块一：模型设置模块（对标 SoloMD「设置 → AI」）

### 2.1 信息架构
- **Provider 选择器**（下拉/卡片）：内置 14+ 预设——OpenAI、Anthropic Claude、Google Gemini、xAI Grok、Mistral、Groq、DeepSeek、通义千问 Qwen、智谱 GLM、Moonshot Kimi、火山方舟/豆包、硅基流动 SiliconFlow、MiniMax… + **Ollama（本地）** + **自定义/Custom**。
- 选 provider 即**自动填 Base URL 与模型提示**；多 product 线的厂商在 model 字段下方给档位提示（如 DeepSeek 的 standard/coder/reasoner）。
- **API Key**：仅云 provider 需填；存入 `secretstore`（已具备）。切换 provider **不清空其它 provider 的 key**（可并存多家）。
- **自定义 Base URL**：必填项，支持代理与兼容端点（LM Studio / vLLM / 公司网关）。
- **模型名：可自由输入 + 可下拉候选**——**专门修复 SoloMD 自身缺陷**（SoloMD 只能选官方目录，指向 LM Studio 时无法键入本地模型名）；本地场景必须允许手填。
- **连接测试 + 实时状态点**：
  - 状态点三态：**绿=已连通 / 红=失败 / 灰=未测**。
  - 测试改为**发一条真实 chat 请求并校验 `choices[0].message.content` 非空**（而非单 ping），结果实时反映到状态点。
- **未检测到 Ollama**：显示「安装 Ollama」按钮，链接 ollama.com（不代理下载）；检测到则自动填 Base URL + 默认模型（现有 `_on_detect_ollama` 已部分具备，提升为设置页一等公民）。

### 2.2 布局与视觉（SoloMD 风）
- 独立「AI 设置」对话框（可从 AI 面板标题栏齿轮或 Ribbon 入口打开），分区清晰：
  ```
  ┌─ AI 设置 ──────────────────────────┐
  │ ● 已连通        (状态点 + 文字)      │
  │ 服务商   [ OpenAI ▾ ]               │
  │ Base URL  [https://api.openai.com/v1]│
  │ 模型     [ gpt-4o-mini ▾/输入 ]      │
  │ API Key  [••••••••••]  [显示]        │
  │ [ 测试连接 ]   [ 保存 ]              │
  │ ── 本地 ──                          │
  │ [ 检测本地 Ollama ] / [ 安装 Ollama ]│
  │ 提示：密钥存于系统凭据管理器          │
  └────────────────────────────────────┘
  ```
- 视觉：12-14px 系统字体、8px 圆角输入框、1px 浅灰边框、状态点 8px 圆（绿 `#34c759` / 红 `#ff3b30` / 灰 `#c7c7cc`），按钮主色沿用编辑器主题。

### 2.3 关键交互
- 保存即持久化（`QSettings` + `secretstore`）；修改不立即生效，需「保存」。
- 设置页与面板共享同一份配置来源（`AIBridge.settings()`）。

---

## 3. 模块二：智能体问答面板（对标 SoloMD Agent Panel）

### 3.1 布局
- 右侧停靠（与「大纲」「反向链接」同级，peer 关系），可左/右停靠（`mainwindow.py:646` 已支持）。
- **标题栏**：标题 + 状态点 + `当前笔记上下文` 开关 + `允许写入` 开关 + `停止`/`重试` 按钮。
- **消息流**（气泡式）：用户（右对齐、主题色底）/ AI（左对齐、白底细边框）/ system（灰小字）/ error（红字）。每条 AI 回复 **hover 出现三个动作**：`插入到光标` `复制` `重新生成`。
- **工具调用卡（Cursor 风格）**：未来扩展——读取笔记 / 搜索 vault / 写入。折叠展示参数与结果，展开看完整 args/result。
- **Trace / 运行历史**：每次对话落盘为纯 markdown（如 `.mdeditor/ai-runs/<id>.md`），可 grep、可 git 回溯，非黑盒。

### 3.2 流式输出（**核心修复点，顺带解决"无响应"Bug**）
- 改用 `stream:true`，**增量 SSE 解析**，首个 token 到达即开始渲染 → 用户立刻看到"在输出"，不再有"长时间静默后整包返回"。
- 渲染期间显示**打字指示器 / 进度条**；提供**停止按钮**（`worker.cancel()` 关闭连接）。
- 流式让"首 token 慢"的本地模型不再触发整包 60s 超时（见 Bug 分析 C-7）。

### 3.3 上下文与写入控制
- **`当前笔记上下文`**（默认关）：开启则把当前文档 markdown 注入 system prompt，让 AI 基于你正在写的笔记回答。
- **`允许写入`**（默认关）：门控 `insert_at_caret` / `replace_selection`；未开启时"插入到光标"按钮禁用，避免误写。
- **引用 chip**：若回答提及 `[[wikilink]]`，渲染为可点击 chip，点击在编辑器中打开该笔记（复用现有导航桥 `navPush`）。

### 3.4 视觉风格（SoloMD 一致感）
- 系统字体、行高舒适；气泡 10px 圆角、1px 边框、左右间距留白；
- 浅/深主题自适应（读取编辑器主题）；状态色克制使用；
- 输入区：多行 `QPlainTextEdit`，Enter 发送 / Shift+Enter 换行（现有），底部一排 `发送 / 插入 / 复制`。

---

## 4. 模块三：行内改写（对标 SoloMD「AI Rewrite / ⌘J」）

### 4.1 交互
- 选中文本 → 按 **⌘J / Ctrl+J**（或浮动栏「AI 改写」）→ 弹出**动作菜单**：润色 / 精简 / 扩写 / 翻译为英文 / 翻译为中文 / 解释 / 自定义提示词。
- 选动作 → 调模型 → 弹出 **Diff 浮层**：左=原文，右=建议；底部 `接受` `拒绝` `重新生成`。
- 接受 → `bridge.replace_selection(建议)`；拒绝 → 关闭；重新生成 → 重发同动作。
- 接受后**正常可用撤销（Ctrl+Z）**。

### 4.2 视觉
- 并排两栏 `QTextEdit`（只读对比），diff 行高亮（增=浅绿 / 删=浅红）；
- 底部三按钮居中；浮层模态但可 Esc 放弃（SoloMD 行为）。

---

## 5. 端到端交互流程

```
[配置] 设置→AI：选 provider / 填 key / 测连通(真实chat) → 状态点转绿
                │
                ├─[问答] 右侧 Agent 面板：输入 → 流式输出 → 插入/复制/重生成
                │         （可选 当前笔记上下文 / 允许写入）
                │
                └─[改写] 选中文本 → ⌘J → 动作菜单 → Diff 浮层 → 接受/拒绝/重生成
```

---

## 6. 工程落地建议（文件与改动）

| 项 | 现状文件 | 改造建议 |
|---|---|---|
| 模型设置 | `ai_pane.py` 内联 | 拆出 `ai_settings.py`（Provider 预设表 + 设置对话框 + 状态点 + 真连通测试） |
| 问答面板 | `ai_pane.py:AIPane` | 重构 `AIPane`：流式 worker、气泡 hover 动作、上下文/写入开关、停止/重试 |
| 行内改写 | `ai_pane.py:_on_rewrite` | 拆出 `ai_rewrite.py`：动作菜单 + Diff 浮层 |
| 流式 worker | `AIWorker`（非流式） | 改为 `AIStreamWorker`：`stream:true` + SSE 增量 + `chunk`/`done`/`error`/`cancelled` 信号 |
| 桥接扩展 | `AIBridge` | 增加 `read_note(path)` / `search_vault(q)` / `current_doc()` 供未来工具卡使用 |
| 日志 | 无 | 新增结构化日志（`logging` 落盘 + 内存环形，设置页「导出诊断日志」） |
| 入口 | 浮动栏 `ai-ask` + 菜单 Ctrl+Shift+Y | 保留并扩展：⌘J 改写、面板标题栏齿轮开设置 |

> 建议分三批落地：**P0 流式+状态点+诊断日志（先灭"无响应"Bug）→ P1 设置模块重构 → P2 改写 Diff 浮层与工具卡**。

---

## 7. 与「提问偶尔完全无响应」Bug 的关联修复

本设计的 **流式输出 + 终态信号 + 结构化日志 + 真实连通测试** 恰好系统性消除该 Bug 的几大根因（详见下方 Bug 分析）。其中两项**最小修复**即便不改架构也应立即做：
1. 把"清空输入/显示用户气泡"移到请求守卫**通过之后**再执行，杜绝竞态吞请求（见 Bug 分析 C-8）。
2. `AIWorker` 增加 `chunk`(流式) 与 `terminated` 兜底，**保证每次请求必有终态**（成功/失败/取消），绝不静默。

--- 

# 附录：「本地模型显示已连，但提问偶尔完全无响应、不返回任何回答」排查分析

> 以下基于 `src/ai_pane.py` 当前实现逐一定位。

## A. 连接状态（Connection Status）
- **A-1 测试与真实问答是两条独立请求**：`_on_test` 仅发 `{"content":"ping"}` 成功即判"连接成功"（`ai_pane.py:214-223`）；真实问答走 `AIWorker`，payload 更大（带 history）、生成更长，二者路由/超时/body 不同。**ping 成功 ≠ 真实请求成功**。
- **A-2 Ollama 检测 ≠ chat 端点**：`_on_detect_ollama` 探测 `:11434/api/tags` 可达，与 `/v1/chat/completions` 是不同端点。
- **排查方向**：将"连接测试"改为发**真实 chat 请求并校验 `choices[0].message.content` 非空**；面板常驻**实时状态点**（每次请求前后更新绿/红/黄），而非依赖一次手动测试。

## B. 请求收发（Request / Response）
- **B-4 非流式整包**：`stream:False` 时本地模型"先长时间无输出、最后整包返回"，体感即"无响应"；超 60s 直接失败。
- **B-5 解析脆弱**：`obj["choices"][0]["message"]["content"]`（`ai_pane.py:54`）在以下情形 KeyError 或取到空串：Ollama 返回空 content / 仅有 `tool_calls` 或 reasoning 占位 / 200 但结构异常 / 模型返回拒绝或空答。KeyError 虽会被 `except Exception` 捕获走错误分支（应显示"错误：…"），所以"**连错误都没有**"更指向信号/线程终态未触发（见 C/D）。
- **排查方向**：开启 wire 级日志（URL、headers、payload 长度、响应 status、raw body 前 N 字节、解析结果），确认请求是否真发出、响应是否真到达、content 是否非空。

## C. 超时与错误处理
- **C-7 固定 60s 单超时偏紧**：本地模型首 token 慢（idle 后模型从磁盘加载到显存、CPU 推理），`urlopen(timeout=60)` 在"读满整个响应或超时"时抛 `URLError` → 错误分支（应显示错误），但用户感知为"无回答"。
- **C-8 时序竞态吞请求（最可疑，解释"连错误都没有"）**：`_on_send` 先 `self._input.clear()` + `append_chat(user)`，**再**调 `_run_api`（`ai_pane.py:338-346`）；而 `_run_api` 在 `self._worker.isRunning()` 为真时**直接 return，既不调 done_cb 也不报错**（`ai_pane.py:197-199`）。于是用户问题进了对话框却永远等不到回复。任何"上一次请求仍在跑"的竞态（多线程、菜单/Ctrl+Shift+Y 绕开按钮禁用、worker 未真正结束）都会吞掉本次提问。
- **C-9 终态信号丢失**：`finished` 用 lambda 连接（`ai_pane.py:209-211`），`_on_send_done` 是**唯一**向聊天框追加"助手回复/错误"的地方；若 `finished` 因线程对象被提前释放等未发射，UI 既无回复也无错误。
- **排查方向**：①把清空输入/用户气泡移到守卫通过之后；②worker 增加 `chunk`/`error`/`cancelled` 独立信号 + `terminated` 兜底，保证**每次请求必有终态**；③超时改为**流式 + 更长等待首 token + 可取消**。

## D. 日志输出
- **D-10 几乎无 AI 层日志**：`except Exception as e: self.finished.emit(False, str(e))` 只留一行文本，丢失 URL/状态码/耗时/body；偶发难复现，弹窗无法事后回溯。
- **排查方向**：建立结构化日志（`logging` 落盘 + 内存环形，设置页「导出诊断日志」）：
  - 请求：time、method、url、model、messages 条数、payload bytes；
  - 响应：status、首字节耗时 ttfb、总耗时、content 长度、是否解析成功；
  - 异常：完整 traceback（非仅 str）、是否超时；
  - worker 生命周期：start / finished / terminated / cancelled。
  - 复现一次即可定位"没发出 / 发了没回 / 回了没解析 / 解析了没渲染"。

## 综合可疑度排序
1. **C-8 时序竞态吞请求** —— 完美解释"连错误都没有"。
2. **C-7 60s 整包超时** —— 本地模型慢 → 失败/无答。
3. **A-1 连接测试≠真实链路** —— "显示已连"误导判断。
4. **B-5 响应解析/空 content** —— 偶发空答。

## 立即可做的最小修复（不改架构）
- 清空输入与用户气泡移到 `_run_api` 守卫通过之后；
- `AIWorker` 增加 `terminated` 兜底 + 流式 `chunk`，保证终态必达；
- 本地(Ollama)默认超时提到 120s+；
- 加 `logging` 落盘 + 设置页「诊断日志」。

> 注：本方案 P0 的「流式 + 状态点 + 诊断日志」即系统性落地上述最小修复并根治。
