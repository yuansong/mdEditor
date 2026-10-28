# 常见问题 · FAQ

> 高频疑问速查。仍有疑问请在 [GitHub Issues](https://github.com/yuansong/mdEditor/issues) 提问。

---

## 安装与运行

**Q：一定要装 Python 才能用吗？**
A：不用。下载 [GitHub Releases](https://github.com/yuansong/mdEditor/releases) 的预打包产物（Windows 解压即跑；macOS 用 `.app`/`.dmg`；Linux 用 AppImage），整个文件夹缺一不可。

**Q：macOS 打开提示「无法打开 / 已损坏」？**
A：CI 默认做的是 **ad-hoc 签名（无 Apple 开发者证书）**，首次打开会被 Gatekeeper 拦。绕过：`xattr -dr com.apple.quarantine /Applications/mdEditor.app`，或右键「打开」→ 弹窗里点「打开」。正式分发需公证（见 `docs/dev/MAC_BUILD.md`）。

**Q：Linux 运行 AppImage 报缺少 `.so`？**
A：按提示 `apt-get install` 缺失的库（如 libnss3、libxcomposite 等），详见 `build_linux.sh` 头部说明。

---

## 数据与隐私

**Q：我的文档存在哪？**
A：就在你打开的 `.md` 文件本身（存储恒为纯 Markdown）。未命名文档有「影子草稿」在 `%APPDATA%\mdEditor\drafts`（启动时可恢复）；版本历史在 `<文档目录>\.mdeditor-history\`。

**Q：需要登录 / 联网吗？**
A：不需要。全部能力离线可用（KaTeX / Mermaid / 语义检索零 CDN）。只有你**主动**配置云端 AI（BYOK）时才会上网调用对应厂商。

**Q：AI 的密钥安全吗？**
A：云端 Key 只存本机凭据库（Windows Credential Manager / macOS Keychain / Linux Secret Service），不写文档、不上云。本地 Ollama 完全离线、零 Key。

---

## 格式与兼容

**Q：为什么复杂表格在别的编辑器里显示成 HTML？**
A：合并单元格、列宽等表达不了原生 Markdown，mdEditor 以 HTML 存储。这是「表格护城河」的代价——在 mdEditor 内体验最佳，纯文本兼容场景会看到 HTML 片段。

**Q：Mermaid 图为什么要求英文名？**
A：E-R 图的实体名 / 属性名 / `title` 请用英文，关系标签写成 `: "中文"`（见主 README「已知限制」）。

**Q：能导出 Word / EPUB 吗？**
A：能。Word(.docx) 用 python-docx，EPUB 3 用标准库；配了 pandoc 路径则优先走 pandoc。PDF 见 [`PDF-EXPORT.md`](PDF-EXPORT.md)。

---

## 快捷键

**Q：哪里看完整快捷键？**
A：主 README「四、快捷键速查」有总表；更全的在应用内「帮助 → 使用手册」（`F12`）第 10 章，且都可在「工具 → 快捷键设置…」自定义。

---

## 贡献与协议

**Q：怎么参与贡献？**
A：见 [`CONTRIBUTING.md`](../../CONTRIBUTING.md)：fork → 分支 → 改 → 提 PR。改动前先读 [`AGENTS.md`](../../AGENTS.md)。

**Q：协议是什么？**
A：Apache-2.0，可自由使用、修改、再分发（含商用），再分发须保留版权与许可声明。
