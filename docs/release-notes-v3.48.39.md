# Release Notes 草稿 · mdEditor v3.48.39

> 本文件是发版说明的**草稿**。本机无法直接发布 GitHub Release；发布步骤见文末「发布操作清单」。
> 产物：`mdEditor-v3.48.39.zip`（Windows，已生成本地）；macOS / Linux 由 CI 自动构建（见 `.github/workflows/`）。

---

## 版本信息

- **版本**：v3.48.39（`src/config.py: APP_VERSION`）
- **Windows 产物**：`mdEditor-v3.48.39.zip`（onedir 绿色文件夹，解压即跑）
- **exe SHA256**：`b05eb247f1d4f5b272da0fdaf16a211254eea86d5d85c38dfba9f912632ef024`
- **协议**：Apache-2.0

---

## 新增与修复（代码）

- **设置「AI 菜单」页背景统一（AI-MENU-BG）**：去掉滚动区多余底色，组框恢复与其它设置页一致的浅灰圆角卡片；`aiMenuList` 补 `#settingsDlg` 级样式，深色主题下不再白底、横向滚动条消失。

（v3.48.38 已交付：书籍关闭不再自动重开、PDF 默认最佳中文配置 + 还原按钮、整本导出复用对话框、格式化日志默认关、绿色版 + 发布包 + 提交。）

---

## 仓库 / 开源基建（本批，非代码版本）

- **双语 README**：英文定位 / Features / 下载 / 构建段 + 语言切换锚点；补 `samples/demo-book` 一键体验与截图占位。
- **CONTRIBUTING.md + CODE_OF_CONDUCT.md**：开发环境、构建、测试、改动规范、提交约定。
- **CI**：`test.yml`（PR 上跑语法检查 + 内核单测）、`build-linux.yml`（AppImage + .deb，mirror 已有的 `build-mac.yml`）、`welcome.yml`（首次贡献者欢迎）；dependabot 周更。
- **模板**：Bug / Feature Issue 模板 + PR 模板 + config（禁用空白 Issue、引导 Discussions / 安全通告）。
- **ROADMAP.md** 与用户指南：`docs/user-guide/AI-GUIDE.md`（AI 接入）、`PDF-EXPORT.md`（PDF 最佳实践）、`FAQ.md`。
- **测试基建修复**：README 引用的 `tests/_syntax_check.py` 此前缺失，本批补全为跨平台、无硬编码路径版本（CI 可直接调用）。

---

## 下载与安装

| 平台 | 方式 |
|---|---|
| Windows | 下载 `mdEditor-v3.48.39.zip` → 解压 → 双击 `mdEditor\mdEditor.exe`（整个文件夹需保留） |
| macOS | 下载 CI 产物 `mdEditor-macOS-dmg`（或 `.app`）；首次打开若被拦：`xattr -dr com.apple.quarantine /Applications/mdEditor.app` 或右键「打开」 |
| Linux | 下载 CI 产物 `mdEditor-Linux-*.AppImage`（需 `chmod +x`），或 `.deb` 包 |

> 提示：macOS / Linux 的 CI 为 ad-hoc 签名（无公证），正式分发需按 `docs/dev/MAC_BUILD.md` 走证书 + 公证流程。

---

## 已知限制

1. 单机本地应用：无云同步 / 协作 / 移动端。
2. 复杂表格以 HTML 存储，在别的编辑器里显示为 HTML 片段。
3. Mermaid E-R 图实体 / 属性请用英文。
4. pandoc 为可选增强，未安装时 docx / EPUB 自动降级内置转换。
5. 全局搜索有上限（1500 文件 / 1.5MB 单文件 / 400 命中）。

---

## 发布操作清单（需要你 / 维护者手动执行）

> 本机无法登录 GitHub 发版，请按以下步骤在浏览器完成：

1. 打开 <https://github.com/yuansong/mdEditor/releases/new>
2. **Tag**：填 `v3.48.39`（与 `APP_VERSION` 一致）；**Target**：`main`
3. **Title**：`mdEditor v3.48.39`
4. **正文**：把本文件「新增与修复 + 下载与安装 + 已知限制」贴入（去掉草稿字样）
5. **上传资产（Assets）**：
   - `mdEditor-v3.48.39.zip`（Windows，本地已生成）
   - macOS：`mdEditor-macOS-dmg`（GitHub Actions → 最新 `Build macOS` 运行 → Artifacts）
   - Linux：`mdEditor-Linux-*.AppImage` 与 `mdeditor_*.deb`（GitHub Actions → 最新 `Build Linux` 运行 → Artifacts）
6. 勾选「Set as the latest release」→ **Publish release**
7. 验证 Release 页面的三个平台资产均可下载、SHA256 与本文一致（Windows）。
