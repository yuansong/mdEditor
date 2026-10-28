<!-- 提 PR 前请先读 CONTRIBUTING.md 与 AGENTS.md -->
## 这个 PR 做了什么 / What this PR does

<!-- 简明描述改动与动机 -->

## 改动类型 / Type of change

- [ ] 缺陷修复 (Bug fix)
- [ ] 新功能 (Feature)
- [ ] 文档 / 示例 (Docs / samples)
- [ ] 构建 / CI (Build / CI)
- [ ] 重构 / 其它 (Refactor / other)

## 自检清单 / Checklist

- [ ] 已读 `AGENTS.md` 的改动规范
- [ ] 已跑通 `python tests/_syntax_check.py` 与 `node tests/test_core.js`
- [ ] 代码改动已同步更新相关文档（README / CHANGELOG / 功能列表 / 缺陷台账，见 AGENTS.md 文档同步矩阵）
- [ ] `src/editor.html` 的改动使用一次性补丁脚本（CRLF 归一化），未做同文件并行编辑
- [ ] 同源常量已同步（如 `config.MMD_THEMES` ↔ `editor.html`）
- [ ] 未用 `git add -A` 误带 `dist*/ spec*/ build*/` 等本地产物

## 截图 / 演示（如涉及 UI）

<!-- 放进 assets/screenshots/ 并在此处引用 -->
