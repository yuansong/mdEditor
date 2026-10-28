# 截图与演示素材 · Screenshots & Demo Assets

本目录用于存放 README 与文档引用的**界面截图、演示 GIF**。

## 建议补充的素材

| 文件名建议 | 用于 | 说明 |
|---|---|---|
| `main-ui.png` | README 顶部 / 界面总览 | 主窗口：写作模式 + 侧栏（文件 / 书籍 / 大纲） |
| `wysiwyg-edit.png` | 编辑内核说明 | 渲染态直编（标题 / 列表 / 引用 / 表格） |
| `table-office.png` | 表格护城河 | Office 级表格：合并 / 拖选 / 列宽写回 |
| `ai-optimize.png` | AI 原生能力 | 选中文字 → 右键「AI 优化」菜单 |
| `ai-panel.png` | AI 原生能力 | 侧栏流式问答面板 + 片段 diff 采纳 |
| `pdf-settings.png` | PDF 导出 | PDF 设置对话框（默认最佳 + 还原按钮） |
| `theme-dark.png` | 六套主题 | 深色 / 墨夜主题效果 |
| `demo.gif` | 快速开始 | 30 秒演示：新建 → 斜杠菜单 → 导出 |

## 提交方式

1. 把图片放进本目录（建议 PNG，宽度 ≤ 1280px，单图 ≤ 500KB）。
2. 在 `README.md` 对应位置用相对路径引用，例如：

   ```markdown
   ![主界面](assets/screenshots/main-ui.png)
   ```

3. 提 PR 时一并提交即可（图片走 Git LFS 或直传均可；本仓库未强制 LFS）。

> 暂无截图时，README 中的 `assets/screenshots/` 链接仅为占位，不影响渲染。
