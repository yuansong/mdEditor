# mdEditor 开发规范（人 / AI 协作共用）

> 本文件是 **mdEditor 项目**的协作契约。无论是人类开发者还是 AI 会话，改动本仓库前都按同一套规则工作。
> 阅读顺序：`README.md`（项目是什么）→ 本文件（怎么改）→ `docs/功能列表-v3.31.md`（模块明细）→ `CHANGELOG.md`（历史）。
> 适用版本：**v3.38.0**　项目根：`E:\WorkBuddy\md-editor`

---

## 一、项目定位与边界

- **是什么**：Windows 单机 Markdown 编辑器，Python + PySide6 (QtWebEngine) 外壳 + 单文件 JS 内核（`src/editor.html`），块级 WYSIWYG，对标 Typora；表格交互对标 Office；全部能力离线。
- **明确不做**：云同步、协作、移动端、代码自动补全、自动缩进继承、粘贴自动识别语言。
- **项目边界**：mdEditor 是独立项目，**不得混入其它小程序 / 业务代码**；也不要把外部项目的约定带进来。
- **工作边界**：用户要求「只测试、不自动修复」时，只出报告不动 `src/`。
- **删除约定**：本项目工程内的删除（清理产物、重命名结果文件等）**直接执行，不再逐条确认**；但**用户个人目录**（桌面 / 下载 / 文档）一律先扫描出清单再确认。

---

## 二、环境与常用命令

| 工具 | 路径 |
|---|---|
| Python（venv，GUI 测试必须用它） | `C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe` |
| Node（内核单测 / 语法检查） | `C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-3/node.exe` |
| Git | 仓库已初始化，branch `main` |

**Bash 每次都要先重置 PATH**（本机 shim 会污染 `PATH`，否则 `dirname` / `cd` 不可用）：

```bash
export PATH="/usr/bin:/bin:$PATH";
```

常用命令（工作目录为仓库根或 `tests/`）：

```bash
# 内核语法检查 + Node 内核单测（改动 editor.html 后必跑）
python tests/_syntax_check.py
node tests/test_core.js                    # 期望 ALL TESTS PASSED

# GUI 探针（结果写 tests/_mNN.txt）
python tests/_runner.py tests/_m113.py
python tests/_run_full.py                  # 全量回归（后台跑，约 9 分钟）

# 打包（PowerShell）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
```

---

## 三、架构硬约束（改前必读）

### 3.1 单文件内核 `src/editor.html`

- 约 700KB 的 HTML + CSS + JS 全部内联，**行尾是 CRLF**。
- 改它**必须**用「一次性补丁脚本」：读取时 `s.replace("\r\n", "\n")` 归一化 → 替换 → 写回时按原样恢复 `newline="\r\n"`。直接 Edit 会因锚点含 `\r` 而匹配失败。
- 补丁脚本每处替换都要 `assert s.count(old) == 1`，命中 0 或多处立即报错，不要"大致替换"。
- **禁止对同一文件的并行编辑 / 并行补丁**：实测会静默丢更新（踩过 3 次）。批量改动串行分消息执行。

### 3.2 同源常量必须多处同步

| 常量 | 同步位置 |
|---|---|
| 版本号 | `config.APP_VERSION`（唯一权威源；关于页 / 检查更新 / 诊断信息共用） |
| 图表主题 | `config.MMD_THEMES` ↔ `editor.html MMD_THEMES`（顺序需与 `window.mmdMenuItems()` 一致） |
| 内置模板 | `config.BUILTIN_TEMPLATES`（权威源） ↔ `editor.html TPL_BUILTIN`（独立打开时的兜底副本） |
| 模板名上限 | `config.TPL_NAME_MAX` ↔ `editor.html TPL_NAME_MAX` ↔ `mainwindow.normalize_template_name`（各 UI 走常量自动同步） |
| 代码语言 / 风格 | `editor.html CODE_LANGS` / `DEFAULT_CODE_LANG`，落 QSettings `codeLang` / `codeStyle` / `codeLineNum` |

改动任一侧，必须同时改另一侧并在文档中记录。

### 3.3 存储原则

**能原生 Markdown 就原生 Markdown**，表达不了才升级为 HTML / `<figure>` / 围栏属性。典型：纯管道表格保持原生；带列宽 / 合并 / 标注的表格以 HTML 存储。

### 3.4 内核稳定层（改动前先确认理解）

- **表格 = 逻辑矩阵模型**（`tblModelFromPipe` / `FromDom` / `ToStorage` 恒输出 HTML）；拖选 = 锚点-指针矩形（零门控）；边线拖动 = 显式 px 表宽（`tblPinWidth`）；行高压缩 = `--rzs:1` 标记。
- **行内格式链路**：`applyFloatAction` → `currentSelectionInfo` → MKS 边界吸附 → `wrapSelection` / `clearSelectionFormat`；单元格格式化走 `cellFormatCtx`，**禁止**走块级 `mapPlainToRaw`。
- **渲染态直编**：富块（含行内格式的标题 / 列表 / 引用 / 定义列表 / 脚注定义）单击恒为渲染态，DOM→Markdown 无损序列化。
- **世代校验**：`code.__docGen !== docGen` 时丢弃失焦回写（防换文档脏写）。
- **懒渲染**：≥400 块启用 IntersectionObserver，导出前自动全量渲染。

---

## 四、文档同步矩阵（**硬性规则**）

**任何代码改动，必须在同一次交付里同步更新文档，不允许"先改代码、文档后补"。** 按下表对号入座：

| 改动类型 | 必须同步的文档 |
|---|---|
| 新增 / 修改 / 删除**功能** | `CHANGELOG.md` 当前版本条目 + `docs/功能列表-v3.31.md` 对应模块表行（含「限制 / 注意」列） |
| 修复**缺陷** | `docs/未实现BUG与优化清单-v3.30.11.md` 台账翻 ✅ 并注明修复版本；同时在 `CHANGELOG.md` 版本行登记 |
| 变更**交互行为** | 对应 `docs/*交互规范-v3.3x.md`（引用 / 代码块 / 图表）；若规范与此前实现冲突，先指出冲突与取舍依据再改 |
| 新增 / 变更**配置项** | `docs/功能列表-v3.31.md` 第 5 节 QSettings 表 + `dialogs.py` 设置页说明 |
| 新增 / 变更**快捷键** | README 第四节速查表 + `docs/功能列表-v3.31.md` 第 4 节 |
| 新增 / 变更**主题**（界面 / 图表） | README 第三节 + `docs/功能列表-v3.31.md` J 模块 + `config.MMD_THEMES` 注释 |
| 新增 **GUI 探针** | 若要纳入全量回归，登记进 `tests/_run_full.py` 的 `PROBE_SCRIPT` / 循环清单 |
| 新增 / 变更 **模板** | `config.BUILTIN_TEMPLATES` + `editor.html TPL_BUILTIN` + README 第三节 |
| **版本号**变更 | `config.APP_VERSION`（唯一源）+ CHANGELOG 新版本行 + README 头部版本标注 |
| 修改**打包配置** | README 第六节 + `build_exe.ps1` 头部注释 |

文档写作要求：
- 条目里写清**改了什么、为什么、影响范围、回归场景**，不要只写"优化某某"。
- 探针结论要带**实测数字**（如 `_m113.py 22/0`），不写"已验证"这种无证据表述。
- 术语统一：用「**模板**」不是「模版」。

---

## 五、改动流程（七步）

1. **读规范**：涉及交互的先读 `docs/` 对应规范 / 审计报告，明确验收条文。
2. **定位**：以**函数名 / 常量名**为锚点重新定位（src 被高频并发修改，行号会漂）。
3. **最小修改**：只动达成目标所必需的代码，不顺手重构、不改无关命名、不加规范外的交互。
4. **写补丁**：一次性串行补丁脚本 + `assert count == 1`；CRLF 归一化处理。
5. **自测**：
   - `python tests/_syntax_check.py`
   - `node tests/test_core.js`（必须 ALL TESTS PASSED）
   - 相关 GUI 探针（新增或复用 `_mNN.py`）
6. **同步文档**：按第四节矩阵逐项更新。
7. **交付报告**：列出「改动文件 + 关键改动说明 + 人工回归步骤 + 探针结果」。

打包与提交**需用户确认后再做**。

---

## 六、测试约定

### 三层测试

| 层 | 命令 | 范围 |
|---|---|---|
| 语法 | `tests/_syntax_check.py` | 抽取 `editor.html` 内联脚本 → `node --check` |
| 内核单测 | `node tests/test_core.js` | 纯逻辑（解析 / 序列化 / 模型），秒级 |
| GUI 探针 | `tests/_runNN.py` + `_mNN.py` | 真实 Qt 窗口 + WebEngine，验证交互 |

### 硬性规则

- **判定以结果文件 `_mNN.txt` 里的 `PASS` / `FAIL` 计数为准，不看进程退出码**（teardown 崩溃是噪声）。
- 探针命名 `_mNN.py` → 结果 `_mNN.txt`；命名撞车时加后缀（如 `_m102b_code.py`），不要覆盖他人文件。
- 跑批前先把旧结果文件 **rename**（`_mNN.txt` → `.bak`），不要 `os.remove` —— 环境有**每轮 50 次删除配额**，耗尽会把 runner 打挂。
- 探针里的 JS 回调**必须 `JSON.stringify`**，裸对象会得到空字符串。
- 断言 toast 前先包装 `window.takeToast` 留痕 —— Qt 主窗口每秒轮询会把消息取走（竞态）。
- 页面就绪守卫：`setmd` 后 `wait(3000)` 并轮询 `!!window.setMarkdown`，首例渲染未就绪会读到空 DOM。
- QSettings 跨运行持久化 → 探针开头复位相关配置（否则读到上一轮脏状态）。
- 禁止在单个进程里创建第二个 `MainWindow`。
- 块选择器用 `'#editor .blk'`；`window.__raw()` 返回 **JSON 字符串**（结构 `{raw:[...], editIdx}`）。

### 探针失败的处理顺序

先怀疑**探针本身陈旧**（选择器变了、入口已被移除、断言过严、raw 口径是块数组不是行数组），再怀疑产品缺陷。判定为探针伪影时必须同步修正探针并在报告里说明，不能靠"忽略"消掉 FAIL。

---

## 七、编码风格

**Python**
- 文件头 `# -*- coding: utf-8 -*-`；模块 docstring 说明职责与版本演进。
- 沿用现有命名：`_on_xxx` 信号槽、`_reg_act` 注册动作、`_js_active` / `_js_all` 执行 JS。
- 新增设置项走 QSettings，读写集中，默认值写在 `config.py` 或函数签名里，不要散落魔法值。
- 改动处补「vX.YY（编号）：动机 + 行为」注释，方便后人理解为什么这么写。

**JS（editor.html）**
- 函数用 `lowerCamelCase`，内部常量 `UPPER_SNAKE`，DOM id 沿用既有前缀（`langpop` / `floatbar` / `objbar` / `tblbar` / `blkmenu`）。
- 新交互优先复用现有浮层与弹层机制，不另造一套。
- 涉及落盘的形态必须同时考虑：渲染态 → 源码回写 → rebuild 后不丢。

**CSS**：主题变量走 `var(--xxx)`，三套（浅 / 深 / 各主题）都要覆盖到；新增颜色先在 `styles.py` 调色板与 `editor.html` 主题块里对齐。

---

## 八、打包与发布

- 脚本：`build_exe.ps1`（当前输出 `dist62`）；**禁止加 `--clean`**。
- `--add-data` 必须用**绝对路径**；随包资源：`editor.html`、`mdeditor.ico`、`katex/`、`mermaid/`、Qt 中文翻译 `qt_zh_CN.qm` / `qtbase_zh_CN.qm`。
- 重打同一 `distNN` 前先删 `distNN\mdEditor`；目录删不掉时用 `robocopy 空目录 目标 /MIR` 清空再删壳。
- 校验三件套：exe SHA256 一致 + 特征串匹配 + 启动自检。
- 归档约定：dist / zip 各保留最近 **3 版**（当前仓库仍有 dist53~dist61 历史堆积，清理前须经用户确认）。
- 打包成功后再更新 README「快速开始」里的产物路径与版本说明。

---

## 九、Git 约定

- 分支：`main`。提交粒度按**需求 / 缺陷批次**，不要把几十个无关改动塞进一个 commit。
- 提交信息格式：`vX.YY: <主题>（<编号列表>）`，例：`v3.38: 引用模块对齐规范 QUO-8/9/10/11 + 图表黑白主题 MMD-12`。
- 仓库当前身份：`yyuansong <yyuansong@126.com>`。用户另提到过 `ysyuan136****@163.com` —— **如需变更提交身份，先与用户确认**再改 config。
- 提交前必跑：语法检查 + 内核单测；涉及 GUI 的附探针结果。
- `tests/_*.txt`、`dist*/`、`build*/`、`spec*/`、`.workbuddy/` 已在 `.gitignore` 中，不要强行入库。

---

## 十、已知工具坑（踩过的，别再踩）

1. **同文件并行 Edit 丢更新**（3 次）→ 一律串行 + 一次性补丁脚本。
2. **CRLF 锚点匹配失败** → 补丁脚本读时归一化、写时恢复。
3. **`TPL_BUILTIN` 重排丢失尾逗号** → 条目数组改完必须 `node --check`（曾导致 `SyntaxError: Unexpected token '{'`，整个内核变坏）。
4. **删除配额 50/轮** → 用 rename 代替 remove；大目录用 `robocopy /MIR`。
5. **PowerShell 输出中文是 UTF-16** → 需要 ASCII 时 `Out-File -Encoding ascii` 转存。
6. **Bash PATH 污染** → 命令前 `export PATH="/usr/bin:/bin:$PATH";`。
7. **后台任务无输出** → 以结果文件 mtime 判断是否跑完，不要轮询。
8. **GUI 段集体 crash 无结果文件** → 多半是 `src` import 错误，单跑一个探针看 traceback。
9. **探针命名冲突**（`_m102.txt` 被占用）→ 加后缀 `_m102b_code.py`。

---

## 十一、需要用户确认才做的事

- 打包新 dist、删除历史 dist / build 目录。
- 提交 Git、变更提交身份。
- 引入新的第三方依赖。
- 变更交互规范文档里的既有条文（先说明冲突与取舍）。
- 任何超出当前需求范围的重构。
