# 参与贡献 · Contributing to mdEditor

> **中文为主，附英文摘要。** 改动代码前请务必先读 [`AGENTS.md`](AGENTS.md)（人 / AI 协作共用的开发规范）。
>
> **English summary:** mdEditor is a Python + PySide6 desktop Markdown editor. To contribute: fork → branch → make changes → open a PR against `main`. Before touching code, read [`AGENTS.md`](AGENTS.md). Run `pip install -r requirements.txt`, then `python src/main.py` to launch. Tests: `python tests/_syntax_check.py` + `node tests/test_core.js`. Keep docs in sync with code (see the doc-sync matrix in AGENTS.md). Chinese is the primary language of this repo; English docs/comments are welcome but not required.

---

## 一、你能怎么参与

| 方式 | 说明 |
|---|---|
| 提 Issue | 报告缺陷（Bug report 模板）、建议功能（Feature request 模板）、或疑问。请先用搜索确认没有重复。 |
| 提 PR | 修复缺陷、补充功能、完善文档、补充示例与截图。小改动直接提；大改动建议先开 Issue 讨论方向。 |
| 文档与翻译 | 补充用户指南、翻译 README / 界面文案、贡献截图与演示 GIF（放进 `assets/screenshots/`）。 |
| 构建与测试 | 在 macOS / Linux 上实测构建脚本与适配项（见 `docs/dev/MAC_BUILD.md`、`.github/workflows/`）。 |

---

## 二、开发环境

### 1. 克隆与依赖

```bash
git clone https://github.com/yuansong/mdEditor.git
cd mdEditor
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.13.x | 建议使用 3.13.x（venv 或系统 Python） |
| PySide6 | ≥ 6.7 | 必须含 `QtWebEngineWidgets` |
| python-docx / pypdf / fpdf2 | — | 文档 / PDF 导出相关，缺失时相应功能降级 |
| Node.js | 22.x | 内核单测与语法检查（`node tests/test_core.js`） |

> 本仓库 Bash 在部分环境会污染 `PATH`，跑命令前先 `export PATH="/usr/bin:/bin:$PATH";`（详见 AGENTS.md 第二节）。

### 2. 从源码运行

```bash
python src/main.py                 # 空文档启动
python src/main.py path/to/note.md # 打开指定文件
```

---

## 三、构建（打包）

跨平台共用核心 [`build.py`](build.py)（PyInstaller onedir），再由平台脚本封装：

```bash
# Windows
powershell.exe -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1

# macOS（.app + ad-hoc 签名 + .dmg；配置证书后可公证）
bash build_mac.sh

# Linux（AppImage；加 --deb 额外产出 .deb）
bash build_linux.sh
bash build_linux.sh --deb
```

- 产物：Windows `distNN\mdEditor\`；macOS `dist/mdEditor.app` + `installer/mdEditor-macOS.dmg`；Linux `installer/mdEditor-Linux-*.AppImage`。
- 不要给 `build_exe.ps1` 加 `--clean`（会重建全部缓存、显著变慢）。
- macOS / Linux 的 CI 自动构建已配置在 `.github/workflows/`，push 到 `main` 即触发。

---

## 四、测试（三段式，改动后必跑前两段）

```bash
# 1) 内核语法检查（抽取 editor.html 内联脚本 → node --check）
python tests/_syntax_check.py

# 2) Node 内核单测（纯逻辑，秒级，期望 "ALL TESTS PASSED"）
node tests/test_core.js

# 3) GUI 探针（起真实 Qt 窗口，需在 venv 解释器下跑，约 9 分钟全量）
python tests/_run_full.py
```

- **判定以结果文件里的 `PASS` / `FAIL` 计数为准，不看退出码**（teardown 崩溃是噪声）。
- 探针命名 `_mNN.py` → 结果 `_mNN.txt`；纳入全量回归需登记进 `tests/_run_full.py` 的清单。

---

## 五、项目结构（速览）

```
src/
  main.py          入口：单实例、滚动日志、Qt 中文翻译、启动 MainWindow
  mainwindow.py    主窗口：菜单 / 工具栏 / 标签页 / 导出 / 模板 / 设置
  editor.html      ★ 单文件编辑内核（HTML+CSS+JS，~700KB，CRLF）：块解析/渲染/交互
  ai_core.py       大模型接入内核（15 家 BYOK + 本地 Ollama 流式）
  ai_connection.py / ai_pane.py / ai_context.py   AI 连接 / 问答面板 / 上下文约束
  semsearch.py     本地语义检索（TF-IDF + 同义词，零依赖）
  diffmerge.py     片段级差异合并（AI 改写 diff / 版本历史三色 diff）
  exporters.py     Markdown 解析 + HTML/PDF/docx/EPUB/pandoc 通道
  styles.py        六套主题调色板与 QSS
  config.py        版本号、常量、内置模板、图表主题
build.py / build_exe.ps1 / build_mac.sh / build_linux.sh   跨平台打包
tests/            测试脚本与运行结果（结果 .txt 不入 Git）
docs/             规范 / 审计 / 测试报告 / 功能清单 / 用户指南
```

更细的模块明细见 [`docs/功能列表-v3.31.md`](docs/功能列表-v3.31.md)。

---

## 六、改动规范（硬性，摘要）

完整规则见 [`AGENTS.md`](AGENTS.md)，要点：

1. **先读 AGENTS.md 再改代码。**
2. **代码改动必须同步更新相关文档**（CHANGELOG / 功能列表 / 缺陷台账 / 交互规范 / 测试登记），矩阵见 AGENTS.md 第四节。
3. `src/editor.html` 是 CRLF 单文件内核：改动只能用「一次性补丁脚本」（读时 `\r\n`→`\n`、写时恢复），**禁止同文件并行编辑**，每处替换 `assert s.count(old) == 1`。
4. 同源常量需多处同步（如 `config.MMD_THEMES` ↔ `editor.html MMD_THEMES`、模板名称上限三处）。
5. 提交前必须跑通 `tests/_syntax_check.py` 与 `node tests/test_core.js`。

---

## 七、提交与 PR 约定

- 分支命名随意，建议 `fix/xxx`、`feat/xxx`、`docs/xxx`。
- 提交信息清晰描述「为什么改、改了什么」；涉及版本号 / 行为变更请在 PR 描述里说明。
- 勿用 `git add -A` 一把梭：本仓库 `.gitignore` 排除 `dist*/ spec*/ build*/ _*.txt` 等，请显式 add 文件名，避免误带本地产物。
- 一个 PR 聚焦一件事，便于 review 与回滚。
- 合并目标分支：`main`。
- 行为 / 文案 / 默认值的变更，请在 PR 中同步说明对文档（README / 功能列表 / 使用手册）的影响。

---

## 八、行为准则

参与本仓库即视为同意 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)（Contributor Covenant）。请保持友善、就事论事、对 newcomers 包容。

---

## 九、去哪问

- 使用问题 / 缺陷 → [GitHub Issues](https://github.com/yuansong/mdEditor/issues)
- 方向讨论 / 大改动 → 先开 Issue，再提 PR
- 开发约定疑问 → 读 [`AGENTS.md`](AGENTS.md)，仍有疑问在 Issue 里 @ 维护者
