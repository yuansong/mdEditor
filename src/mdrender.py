# -*- coding: utf-8 -*-
"""轻量 Markdown → HTML 渲染器（无外部依赖，输出 QTextBrowser 支持的子集）。

供 AI 助手气泡、版本合并结果、AI 插入预览等场景复用。

v3.48.18（MD-STRUCT）重写块级解析器，解决「整段纯文本输出」的五类缺陷：

1. **嵌套列表断裂**：旧版列表正则 `^[-*+]\\s+` 不认缩进，`   - 子项` 被当作
   普通段落 → 结构塌陷；且有序列表被嵌套打断后重新从 1 编号。
   新版按缩进构建列表树，`<ul>/<ol>` 逐层嵌套，编号连续。
2. **表格未渲染**：GFM 管道表格整块变成带 `<br>` 的段落。
   新版识别表头分隔行，输出 `<table>`（表头加底色）。
3. **代码块无语言标识**：围栏信息串被丢弃；新版保留语言并渲染语言角标。
4. **引用块换行丢失**：多段引用被压成一行；新版按段渲染。
5. **任务列表**：`- [ ]` / `- [x]` 渲染为 ☐ / ☑。

设计约束（Qt 富文本子集）：只使用 QTextDocument 可靠支持的标签与内联样式——
`h1~h6 / p / ul / ol / li / blockquote / pre / table / tr / th / td / hr / br /
b / i / s / code / a / img`，样式仅 color、background、font-*、text-align、
border、margin、padding；不使用 border-radius / flex / grid（Qt 会忽略）。

每个块级元素输出为**独立段落**，从而在 QTextBrowser 中一段一行，
便于 diff 对比与片段合并时按段定位。
"""
import re

# ---------------------------------------------------------------- 基础转义

def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


# ---------------------------------------------------------------- 行内格式

# 行内代码占位符（避免被粗体 / 斜体 / 链接规则误伤）
_PH = "\x00%d\x00"
_PH_RE = re.compile(r"\x00(\d+)\x00")


def _inline(s):
    """行内 Markdown → HTML。入参应为**已转义**文本。"""
    store = []

    def _stash(html):
        store.append(html)
        return _PH % (len(store) - 1)

    # 1) 行内代码：内容需再次转义（原文此时已转义，反引号内不应解析格式）
    def _code(m):
        body = m.group(1)
        # 已转义文本：撤销一次转义再重新转义，保证 &amp; 不被二次处理
        return _stash("<code>%s</code>" % body.strip())

    s = re.sub(r"`([^`]+)`", _code, s)

    # 2) 图片 ![alt](src) —— 必须早于链接规则
    s = re.sub(r"!\[([^\]]*)\]\((https?://[^)\s]+|data:[^)\s]+)\)",
               lambda m: _stash('<img src="%s" alt="%s">'
                                % (m.group(2), m.group(1))), s)

    # 3) 链接 [文本](url)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               r'<a href="\2">\1</a>', s)

    # 4) 粗斜体 / 粗体 / 斜体 / 删除线（先长后短，避免 **** 歧义）
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"___(.+?)___", r"<b><i>\1</i></b>", s)
    s = re.sub(r"__(.+?)__", r"<b>\1</b>", s)
    s = re.sub(r"~~(.+?)~~", r"<s>\1</s>", s)
    s = re.sub(r"(?<![\*\w])\*(?![\s\*])(.+?)(?<![\s\*])\*(?![\*\w])",
               r"<i>\1</i>", s)
    s = re.sub(r"(?<![\w_])_(?![\s_])(.+?)(?<![\s_])_(?![\w_])",
               r"<i>\1</i>", s)

    # 5) 换行符（段落内硬换行）
    s = s.replace("\n", "<br>")

    # 6) 还原占位符
    def _unstash(m):
        return store[int(m.group(1))]

    return _PH_RE.sub(_unstash, s)


# ---------------------------------------------------------------- 代码块

def _looks_like_diff(code):
    """判断一段代码是否像 diff（patch）内容。"""
    lines = code.split("\n")
    head = 0
    while head < len(lines) and not lines[head].strip():
        head += 1
    if head >= len(lines):
        return False
    first = lines[head]
    if first.startswith(("diff --git", "--- ", "+++ ", "index ", "@@ ",
                         "*** ")):
        return True
    plus = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    minus = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
    total = max(1, len([l for l in lines if l.strip()]))
    has_hunk = any(l.startswith("@@ ") for l in lines)
    return has_hunk and (plus + minus) / total > 0.25


def _render_diff_code(code):
    """把 diff 文本逐行着色，返回 <pre> 片段（已转义）。"""
    out = []
    for line in code.split("\n"):
        e = _esc(line) + "\n"
        if line.startswith("+") and not line.startswith("+++"):
            out.append('<span style="background:#e6ffed;color:#1a7f37;">%s</span>'
                       % e)
        elif line.startswith("-") and not line.startswith("---"):
            out.append('<span style="background:#ffeef0;color:#cf222e;">%s</span>'
                       % e)
        elif line.startswith("@@ "):
            out.append('<span style="background:#f0f3f6;color:#57606a;">%s</span>'
                       % e)
        else:
            out.append(e)
    body = "".join(out)
    return ('<pre style="background:#f6f8fa;padding:8px 10px;'
            'font-family:Consolas,Monaco,monospace;font-size:13px;'
            'white-space:pre;line-height:1.45;margin:6px 0;">%s</pre>' % body)


_PRE_STYLE = ("background:#f6f8fa;padding:8px 10px;"
              "font-family:Consolas,Monaco,monospace;font-size:13px;"
              "white-space:pre;margin:6px 0;")


def _render_plain_code(code, lang=""):
    """普通代码块。lang 非空时输出语言角标（独立一行，不影响代码排版）。"""
    badge = ""
    if lang:
        badge = ('<div style="font-size:11px;color:#6e7781;margin:6px 0 -2px 2px;'
                 'font-family:Consolas,Monaco,monospace;">%s</div>' % _esc(lang))
    return (badge + '<pre style="%s">%s</pre>' % (_PRE_STYLE, _esc(code)))


def _code_block(buf, lang=""):
    code = "\n".join(buf)
    if _looks_like_diff(code):
        return _render_diff_code(code)
    return _render_plain_code(code, lang)


# ---------------------------------------------------------------- 表格

_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _split_row(line):
    """拆分管道表格行 → 单元格文本列表（支持 \\| 转义）。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, buf, i = [], "", 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf += "|"
            i += 2
            continue
        if ch == "|":
            cells.append(buf.strip())
            buf = ""
            i += 1
            continue
        buf += ch
        i += 1
    cells.append(buf.strip())
    return cells


def _is_table_start(lines, i):
    """判断 i 行是否为表格表头（下一行为分隔行且列数一致）。"""
    if i + 1 >= len(lines):
        return False
    if "|" not in lines[i]:
        return False
    if not _TABLE_SEP_RE.match(lines[i + 1]):
        return False
    return len(_split_row(lines[i])) == len(_split_row(lines[i + 1]))


def _render_table(header, rows, aligns):
    ncol = len(header)

    def cell(tag, txt, k):
        al = aligns[k] if k < len(aligns) else ""
        st = 'padding:5px 9px;border:1px solid #d0d7de;'
        if al:
            st += 'text-align:%s;' % al
        if tag == "th":
            st += "background:#f2f4f7;font-weight:bold;"
        return '<%s style="%s">%s</%s>' % (tag, st, _inline(_esc(txt)), tag)

    out = ['<table border="1" cellspacing="0" cellpadding="0" '
           'style="border-collapse:collapse;margin:8px 0;font-size:13px;">']
    out.append("<tr>" + "".join(cell("th", h, k)
                               for k, h in enumerate(header)) + "</tr>")
    for r in rows:
        cells = list(r) + [""] * (ncol - len(r))
        out.append("<tr>" + "".join(cell("td", c, k)
                                    for k, c in enumerate(cells[:ncol])) + "</tr>")
    out.append("</table>")
    return "".join(out)


def _parse_aligns(sep_line):
    out = []
    for c in _split_row(sep_line):
        c = c.strip()
        left, right = c.startswith(":"), c.endswith(":")
        out.append("center" if left and right else "right" if right
                   else "left" if left else "")
    return out


# ---------------------------------------------------------------- 列表

_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_TASK_RE = re.compile(r"^\[([ xX])\]\s+(.*)$")


def _is_list_line(line):
    return bool(_LIST_RE.match(line))


def _collect_list(lines, i, N):
    """收集从 i 起的一段列表（允许 2 空格以上的续行）。

    返回 (items, next_i)；items 为扁平列表 [{indent, ordered, text, num}]，
    缩进层级在渲染阶段按 indent 构建树（简单且对中文 / 全角空格友好）。
    """
    items = []
    while i < N:
        line = lines[i]
        m = _LIST_RE.match(line)
        if m:
            indent = len(m.group(1).replace("\t", "    "))
            marker = m.group(2)
            ordered = marker[0].isdigit()
            num = int(re.sub(r"\D", "", marker)) if ordered else 0
            items.append({"indent": indent, "ordered": ordered,
                          "num": num, "text": m.group(3)})
            i += 1
            continue
        # 续行：缩进 >= 当前列表首项缩进+2 且非空 → 并入上一项
        if items and line.strip() and line[:1] in (" ", "\t"):
            items[-1]["text"] += "\n" + line.strip()
            i += 1
            continue
        break
    return items, i


def _render_list(items):
    """按 indent 构建列表树并渲染为嵌套 <ul>/<ol>。"""
    # 统一基准缩进，避免整体缩进导致的假嵌套
    base = min(it["indent"] for it in items) if items else 0
    for it in items:
        it["indent"] -= base

    root = []
    stack = [(-1, root)]          # (indent, 当前层的子项列表)
    for it in items:
        while len(stack) > 1 and it["indent"] <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        node = {"item": it, "children": []}
        parent.append(node)
        stack.append((it["indent"], node["children"]))

    def render(nodes, ordered, depth=0):
        tag = "ol" if ordered else "ul"
        style = "margin:4px 0 4px 6px;padding-left:20px;"
        out = ['<%s style="%s">' % (tag, style)]
        for n in nodes:
            it = n["item"]
            txt = it["text"]
            m = _TASK_RE.match(txt)
            if m:
                mark = "\u2611" if m.group(1).lower() == "x" else "\u2610"
                txt = mark + " " + m.group(2)
            body = _inline(_esc(txt))
            # 子列表沿用首个子项的列表类型
            if n["children"]:
                child_ordered = n["children"][0]["item"]["ordered"]
                body += render(n["children"], child_ordered, depth + 1)
            out.append("<li style=\"margin:2px 0;\">%s</li>" % body)
        out.append("</%s>" % tag)
        return "".join(out)

    return render(root, items[0]["ordered"] if items else False)


# ---------------------------------------------------------------- 主入口

_HR_RE = re.compile(r"^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$")
_HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")


def md_to_html(text):
    """Markdown → HTML（结构化块级渲染，聊天 / 合并 / 预览通用）。

    段落、标题、列表、代码块、表格、引用各自成为独立 HTML 块元素，
    在 QTextBrowser 中表现为独立段落，便于 diff 与片段合并定位。
    """
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    i, N = 0, len(lines)
    while i < N:
        line = lines[i]
        stripped = line.strip()

        # 空行
        if stripped == "":
            i += 1
            continue

        # 围栏代码块 ``` / ~~~（保留语言标识）
        fm = re.match(r"^\s*(`{3,}|~{3,})\s*([^\s`]*)\s*$", line)
        if fm:
            fence = fm.group(1)
            lang = fm.group(2) or ""
            fch = fence[0]
            buf = []
            i += 1
            while i < N:
                cand = lines[i].strip()
                # 闭合围栏：整行仅由同种字符组成且长度 >= 开围栏长度
                if cand and set(cand) == {fch} and len(cand) >= len(fence):
                    i += 1
                    break
                buf.append(lines[i])
                i += 1
            out.append(_code_block(buf, lang))
            continue

        # 表格（必须先于段落判定）
        if _is_table_start(lines, i):
            header = _split_row(lines[i])
            aligns = _parse_aligns(lines[i + 1])
            i += 2
            rows = []
            while i < N and lines[i].strip() and "|" in lines[i]:
                rows.append(_split_row(lines[i]))
                i += 1
            out.append(_render_table(header, rows, aligns))
            continue

        # ATX 标题
        m = _HEAD_RE.match(line)
        if m:
            lvl = len(m.group(1))
            out.append('<h%d style="margin:12px 0 6px 0;">%s</h%d>'
                       % (lvl, _inline(_esc(m.group(2))), lvl))
            i += 1
            continue

        # 分割线
        if _HR_RE.match(stripped):
            out.append('<hr style="border:none;border-top:1px solid #d0d7de;'
                       'margin:10px 0;">')
            i += 1
            continue

        # 引用块（连续 `>` 行；空引用行分隔段落）
        if stripped.startswith(">"):
            paras, cur = [], []
            while i < N and lines[i].strip().startswith(">"):
                body = re.sub(r"^\s*>\s?", "", lines[i])
                if body.strip():
                    cur.append(body)
                else:
                    if cur:
                        paras.append(cur)
                        cur = []
                i += 1
            if cur:
                paras.append(cur)
            inner = "".join(
                '<p style="margin:3px 0;">%s</p>'
                % _inline(_esc("\n".join(p))) for p in paras)
            out.append('<blockquote style="border-left:3px solid #d0d7de;'
                       'margin:6px 0;padding:2px 12px;color:#57606a;">%s'
                       '</blockquote>' % inner)
            continue

        # 列表（含嵌套 / 任务列表）
        if _is_list_line(line):
            items, i = _collect_list(lines, i, N)
            out.append(_render_list(items))
            continue

        # 段落：聚合连续普通行，遇到任何块级起始即中断
        buf = []
        while i < N:
            l = lines[i]
            ls = l.strip()
            if (ls == "" or _is_list_line(l)
                    or re.match(r"^\s*(`{3,}|~{3,})", l)
                    or _HEAD_RE.match(l) or ls.startswith(">")
                    or _HR_RE.match(ls) or _is_table_start(lines, i)):
                break
            buf.append(l)
            i += 1
        if buf:
            out.append('<p style="margin:6px 0;">%s</p>'
                       % _inline(_esc("\n".join(buf))))
        else:
            # 兜底：空前进一步，避免死循环
            i += 1

    return "".join(out)


# ---------------------------------------------------------------- 纯文本降级

def md_to_plain(text):
    """Markdown → 可见纯文本（用于选区比对 / diff 归一，忽略 Markdown 符号）。"""
    s = str(text or "")
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"(?m)^\s{0,3}(`{3,}|~{3,})", "", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*\*|\*\*|___|__|~~", "", s)
    s = re.sub(r"(?<!\w)\*(?!\*)", "", s)
    s = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", s)
    s = re.sub(r"(?m)^\s{0,3}>\s?", "", s)
    s = re.sub(r"(?m)^\s*[-*+]\s+", "", s)
    s = re.sub(r"(?m)^\s*\d+[.)]\s+", "", s)
    s = re.sub(r"(?m)^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", "", s)
    s = s.replace("|", " ")
    return s
