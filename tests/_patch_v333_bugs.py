# -*- coding: utf-8 -*-
"""v3.31.1 缺陷修复补丁（依据《测试报告-v3.31》BUG-1 / BUG-2）

BUG-1（P3）：管道表格表头含转义管道或裸表头（GFM 允许不带首尾竖线）时，
  splitBlocks 的 kindOf 只识别「整行全竖线」形式，导致「裸表头 + 竖线分隔行」
  按类型不一致被拆块，整表降级为段落且往返后结构劣化。
  修复：splitBlocks 补表格分组规则（表头进入 + 表体延续），与 blockInfo
  的表格判定语义对齐；新增 isSepRow 分隔行判定。

BUG-2（P4）：斜杠菜单「标题 7」解析为 h7 但渲染钳制为 h6（视觉无差异、
  不入大纲），设计不一致。按测试报告方案 A：移除标题 7 入口，#{1,7} 全部
  收敛为 #{1,6}，`#######` 按正文段落处理。

每处替换先校验出现次数（恰好 1 次），失败即 exit 1（幂等可重放）。
"""
import io
import sys

EDITOR = r"E:\WorkBuddy\md-editor\src\editor.html"
DIALOGS = r"E:\WorkBuddy\md-editor\src\dialogs.py"


def patch(path, pairs):
    with io.open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    for i, (old, new) in enumerate(pairs, 1):
        n = txt.count(old)
        if n != 1:
            print("FAIL %s pair#%d count=%d\n  old=%r" % (path, i, n, old[:90]))
            sys.exit(1)
        txt = txt.replace(old, new)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(txt)
    print("OK %s (%d pairs)" % (path, len(pairs)))


# ---------------- BUG-1：splitBlocks 管道表格分组 ----------------
EDITOR_PAIRS = [
    # 1) 循环状态加 tblOpen（当前块是否为已开启的表格块）
    ("var blocks = [], cur = [], fence = false, yamlDone = false;",
     "var blocks = [], cur = [], fence = false, yamlDone = false, tblOpen = false;"),

    # 2) flush 同时复位 tblOpen（fence / 空行 / HTML 块等所有收块路径都走 flush）
    ("function flush() { if (cur.length) { blocks.push(cur.join('\\n')); cur = []; } }",
     "function flush() { if (cur.length) { blocks.push(cur.join('\\n')); cur = []; } tblOpen = false; }"),

    # 3) kindOf 前插入分隔行判定 isSepRow
    ("    function kindOf(line) {",
     "    /* v3.31.1（BUG-1）：分隔行判定 —— 竖线分隔的 :?-+:? 列（GFM 允许\n"
     "       首尾不带竖线，如 `--- | ---`）；纯 `---`（hr）因无竖线不误判 */\n"
     "    function isSepRow(line) {\n"
     "      if (!/\\|/.test(line)) return false;\n"
     "      var s = line.trim();\n"
     "      if (!/^[-|\\s:]+$/.test(s) || !/-/.test(s)) return false;\n"
     "      var cols = s.replace(/^\\|/, '').replace(/\\|$/, '').split('|');\n"
     "      for (var i = 0; i < cols.length; i++) {\n"
     "        if (!/^\\s*:?-+:?\\s*$/.test(cols[i])) return false;\n"
     "      }\n"
     "      return cols.length >= 1;\n"
     "    }\n"
     "    function kindOf(line) {"),

    # 4) 块首类型 + 表格分组两条规则
    ("      var pk = cur.length ? kindOf(cur[0]) : null; // 以块首行类型为准\n"
     "      if (cur.length && kind !== pk) {",
     "      var pk = cur.length ? (tblOpen ? 'table' : kindOf(cur[0])) : null; // 以块首行类型为准\n"
     "      /* v3.31.1（BUG-1）：管道表格分组补全 —— kindOf 只识别整行全竖线形式，\n"
     "         GFM 允许表头/数据行不带首尾竖线（`列A | 列C`），导致「裸表头 + 竖线\n"
     "         分隔行」按类型不一致被拆块，整表降级为段落且往返结构劣化。\n"
     "         ① 表头进入：当前块为空、本行含非转义竖线且下一行是分隔行 → 表格行；\n"
     "         ② 表体延续：表格块已开启、本行含竖线（转义亦算）→ 并入当前表格块。 */\n"
     "      if (kind === 'text') {\n"
     "        if (tblOpen && /\\|/.test(line)) kind = 'table';\n"
     "        else if (!tblOpen && !cur.length && /(?<!\\\\)\\|/.test(line) &&\n"
     "                 k + 1 < lines.length && isSepRow(lines[k + 1])) {\n"
     "          kind = 'table'; tblOpen = true;\n"
     "        }\n"
     "      }\n"
     "      if (!cur.length && kind === 'table') tblOpen = true;\n"
     "      if (cur.length && kind !== pk) {"),
]

# ---------------- BUG-2：移除标题 7，按 6 级封顶 ----------------
EDITOR_PAIRS += [
    # 5) blockInfo：#{1,7} → #{1,6}
    ("if ((m = first.match(/^(#{1,7})\\s+(.*)$/))) return { type: 'h' + m[1].length };",
     "if ((m = first.match(/^(#{1,6})\\s+(.*)$/))) return { type: 'h' + m[1].length };"),

    # 6)~12) 其余 #{1,7} 正则统一收敛（各处上下文唯一）
    ("var txt = state.raw[t].replace(/^#{1,7}\\s+/, '');",
     "var txt = state.raw[t].replace(/^#{1,6}\\s+/, '');"),
    ("var text = raw.replace(/^#{1,7}\\s+/, '');",
     "var text = raw.replace(/^#{1,6}\\s+/, '');"),
    ("var m = lines[0].match(/^#{1,7}\\s+/);",
     "var m = lines[0].match(/^#{1,6}\\s+/);"),
    ("String(state.raw[i] || '').replace(/^#{1,7}\\s+/, '')",
     "String(state.raw[i] || '').replace(/^#{1,6}\\s+/, '')"),
    ("state.raw[i].replace(/^#{1,7}\\s+/, '')",
     "state.raw[i].replace(/^#{1,6}\\s+/, '')"),
    ("el.textContent.replace(/^#{1,7}\\s+/, '')",
     "el.textContent.replace(/^#{1,6}\\s+/, '')"),
    ("return r.replace(/^#{1,7}\\s+/, '')",
     "return r.replace(/^#{1,6}\\s+/, '')"),

    # 13) raw-edit 样式删除 .t-h7
    (".raw-edit.t-h7 { font-size: 0.95em; font-weight: 600; color: var(--text-2); "
     "margin: 0.75em 0 0.35em; line-height: 1.4; }\n",
     ""),

    # 14) 渲染 switch 移除 case 'h7'（blockHTML）
    ("case 'h6': case 'h7': {\n        var n = +info.type[1];",
     "case 'h6': {\n        var n = +info.type[1];"),

    # 15) 偏移映射 switch 移除 case 'h7'（lineWalker）
    ("case 'h6': case 'h7': {\n        var m = lines[0].match",
     "case 'h6': {\n        var m = lines[0].match"),

    # 16) 斜杠菜单：删除「标题 7」子项（H6 行尾逗号一并收敛）
    ("      { ic: 'H6', lb: '标题 6', t: '###### ' },\n"
     "      { ic: 'H7', lb: '标题 7', t: '####### ' }",
     "      { ic: 'H6', lb: '标题 6', t: '###### ' }"),

    # 17) 块类型中文名映射移除 h7
    ("h6: '标题 6', h7: '标题 7' })[t] || t;",
     "h6: '标题 6' })[t] || t;"),

    # 18) 块菜单「转为标题」子项移除 h7
    ("['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7'].map",
     "['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].map"),

    # 19) 加固：斜杠二级默认选中下标按 children 数量封顶
    #    （老配置若存过标题 7 的下标 6，收窄后不越界）
    ("        it.def = (sub[id] != null && !isNaN(+sub[id]))\n"
     "          ? Math.max(0, +sub[id])",
     "        it.def = (sub[id] != null && !isNaN(+sub[id]))\n"
     "          ? Math.max(0, Math.min(it.children.length - 1, +sub[id]))"),
]

# ---------------- dialogs.py：设置对话框「标题默认」下拉同步 ----------------
DIALOGS_PAIRS = [
    ('SUB_HEADING = ["标题 1", "标题 2", "标题 3", "标题 4", "标题 5", "标题 6", "标题 7"]',
     'SUB_HEADING = ["标题 1", "标题 2", "标题 3", "标题 4", "标题 5", "标题 6"]  # v3.31.1 移除标题7'),
]

patch(EDITOR, EDITOR_PAIRS)
patch(DIALOGS, DIALOGS_PAIRS)
print("ALL PATCHED")
