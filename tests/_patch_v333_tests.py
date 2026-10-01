# -*- coding: utf-8 -*-
"""v3.31.1 测试断言同步：BUG-1 修复（smoke33 表格断言转正）+ BUG-2（smoke13 h7 用例改写）"""
import io
import sys

S13 = r"E:\WorkBuddy\md-editor\tests\_smoke13.py"
S33 = r"E:\WorkBuddy\md-editor\tests\_smoke33.py"


def patch(path, pairs):
    with io.open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    for i, (old, new) in enumerate(pairs, 1):
        n = txt.count(old)
        if n == 0 and new and txt.count(new) >= 1:
            print("SKIP %s pair#%d (already applied)" % (path, i))
            continue
        if n != 1:
            print("FAIL %s pair#%d count=%d\n  old=%r" % (path, i, n, old[:90]))
            sys.exit(1)
        txt = txt.replace(old, new)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(txt)
    print("OK %s (%d pairs)" % (path, len(pairs)))


# ---------------- smoke13：标题子菜单 7→6 级；####### 按段落处理 ----------------
P13 = [
    # 1) 斜杠菜单标题二级：7 项 → 6 项，末项 标题 7 → 标题 6
    ('check("标题 submenu 7 levels", d.get("show") is True and d.get("items") == 7 and d.get("last") == "标题 7", d)',
     'check("标题 submenu 6 levels（v3.31.1 移除标题7）", d.get("show") is True and d.get("items") == 6 and d.get("last") == "标题 6", d)'),

    # 2) 「标题 7 全链路」改写为「6 级封顶」验证：####### 按正文段落处理
    ('# ---------- 4) 标题 7 全链路 ----------\n'
     'js("window.setMarkdown(\'####### 七级标题内容\')")\n'
     'wait(800)\n'
     'r = js("(function(){var b=document.querySelector(\'.blk\');"\n'
     '       "return JSON.stringify({cls:b.className,tag:b.querySelector(\'h1,h2,h3,h4,h5,h6\')?"\n'
     '       "b.querySelector(\'h1,h2,h3,h4,h5,h6\').tagName:\'\'})})()")\n'
     'd = json.loads(r or "{}")\n'
     'check("h7 block type", "b-h7" in (d.get("cls") or ""), d)\n'
     'r = js("window.__core.blockInfo(\'####### t\').type")\n'
     'check("blockInfo h7", r == "h7", r)\n'
     'r = js("window.getMarkdown()")\n'
     'check("h7 roundtrip", (r or "").startswith("####### 七级"), (r or "")[:40])',

     '# ---------- 4) 七级标题按 6 级封顶（v3.31.1 BUG-2：####### 按正文段落处理） ----------\n'
     'js("window.setMarkdown(\'####### 七级标题内容\')")\n'
     'wait(800)\n'
     'r = js("(function(){var b=document.querySelector(\'.blk\');"\n'
     '       "return JSON.stringify({cls:b.className,tag:b.querySelector(\'h1,h2,h3,h4,h5,h6\')?"\n'
     '       "b.querySelector(\'h1,h2,h3,h4,h5,h6\').tagName:\'\'})})()")\n'
     'd = json.loads(r or "{}")\n'
     'check("####### 按段落处理（b-p，无 heading 标签）",\n'
     '      "b-p" in (d.get("cls") or "") and not (d.get("tag") or ""), d)\n'
     'r = js("window.__core.blockInfo(\'####### t\').type")\n'
     'check("blockInfo \'####### t\' = p", r == "p", r)\n'
     'r = js("window.getMarkdown()")\n'
     'check("####### 原文往返保留", (r or "").startswith("####### 七级"), (r or "")[:40])'),

    # 3) 块菜单标题二级：7 项 → 6 项
    ('check("block 标题 submenu 7 items", d.get("show") is True and d.get("items") == 7, d)',
     'check("block 标题 submenu 6 items（v3.31.1 移除标题7）", d.get("show") is True and d.get("items") == 6, d)'),

    # 4) 转换目标：索引 6（标题 7）→ 索引 5（标题 6）
    ('   "var c=s.querySelector(\'.si[data-k=\\"6\\"]\');"  # 标题 7 索引 6\n'
     '   "c.dispatchEvent(new MouseEvent(\'mousedown\',{bubbles:true}));return \'p\'})()")\n'
     'wait(500)\n'
     'r = js("window.getMarkdown()")\n'
     'check("transform to 标题7", (r or "").startswith("####### 普通段落"), (r or "")[:40])',

     '   "var c=s.querySelector(\'.si[data-k=\\"5\\"]\');"  # 标题 6 索引 5（v3.31.1 移除标题7）\n'
     '   "c.dispatchEvent(new MouseEvent(\'mousedown\',{bubbles:true}));return \'p\'})()")\n'
     'wait(500)\n'
     'r = js("window.getMarkdown()")\n'
     'check("transform to 标题6", (r or "").startswith("###### 普通段落"), (r or "")[:40])'),
]

# ---------------- smoke33：BUG-1 断言转正 + BUG-2 断言更新 ----------------
P33 = [
    # 1) BUG-1 现状记录 → 修复验证（表格渲染 + 往返结构不劣化）
    ('# 表格特殊内容：转义管道（已知 BUG-1：表头含 \\| 时整表降级为段落）\n'
     'setmd("列A\\\\|B | 列C\\n| --- | --- |\\n| 1 | 2 |")\n'
     'check("BUG-1(现状记录) 转义管道表头表格降级为段落（修复后应改为断言 table=1）",\n'
     '      num("document.querySelectorAll(\'#editor table\').length") == 0,\n'
     '      str(num("document.querySelectorAll(\'#editor table\').length")))\n'
     'check("E6 转义管道往返保留", "\\\\|" in (js("window.getMarkdown()") or ""), (js("window.getMarkdown()") or "")[:40])',

     '# 表格特殊内容：转义管道 + 裸表头（v3.31.1 BUG-1 已修复）\n'
     'setmd("列A\\\\|B | 列C\\n| --- | --- |\\n| 1 | 2 |")\n'
     'check("BUG-1(已修复) 转义管道+裸表头渲染为 1 张表格",\n'
     '      num("document.querySelectorAll(\'#editor table\').length") == 1,\n'
     '      str(num("document.querySelectorAll(\'#editor table\').length")))\n'
     'check("BUG-1(已修复) 往返结构不劣化（单表格块，分隔行保留）",\n'
     '      num("document.querySelectorAll(\'#editor table\').length") == 1 and\n'
     '      "| --- | --- |" in (js("window.getMarkdown()") or ""),\n'
     '      (js("window.getMarkdown()") or "")[:60])\n'
     'check("E6 转义管道往返保留", "\\\\|" in (js("window.getMarkdown()") or ""), (js("window.getMarkdown()") or "")[:40])\n'
     '# GFM 混合管道风格：裸表头 + 裸分隔行 + 裸数据行\n'
     'setmd("甲 | 乙\\n--- | ---\\n1 | 2")\n'
     'check("BUG-1(已修复) GFM 裸管道表格渲染为 1 张表格",\n'
     '      num("document.querySelectorAll(\'#editor table\').length") == 1,\n'
     '      str(num("document.querySelectorAll(\'#editor table\').length")))\n'
     'check("BUG-1(已修复) 裸管道表格往返保真",\n'
     '      "甲 | 乙" in (js("window.getMarkdown()") or "") and "--- | ---" in (js("window.getMarkdown()") or ""),\n'
     '      (js("window.getMarkdown()") or "")[:40])'),

    # 2) E2：h6 钳制断言 → 段落处理断言
    ('check("E2 H7 渲染钳制为 h6 元素（与标题 6 视觉一致——已知不一致，见 BUG-2）",\n'
     '      num("document.querySelectorAll(\'#editor .blk h6\').length") == 1,\n'
     '      str(num("document.querySelectorAll(\'#editor .blk h6\').length")))',

     'check("E2 H7 按段落处理（b-p，无 h6 元素——BUG-2 已修复）",\n'
     '      num("document.querySelectorAll(\'#editor .blk.b-p\').length") == 1 and\n'
     '      num("document.querySelectorAll(\'#editor .blk h6\').length") == 0,\n'
     '      "p=%d,h6=%d" % (num("document.querySelectorAll(\'#editor .blk.b-p\').length"),\n'
     '                      num("document.querySelectorAll(\'#editor .blk h6\').length")))'),

    # 3) E2 段首注释同步
    ('# H7：内核按 #{1,7} 解析为 h7，但大纲只收 h1~h6（非标准语法，观察行为）',
     '# H7：v3.31.1（BUG-2）按 6 级封顶 —— `####### ` 不再解析为标题，按正文段落处理'),
]

patch(S13, P13)
patch(S33, P33)
print("ALL PATCHED")
