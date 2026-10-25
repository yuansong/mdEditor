# -*- coding: utf-8 -*-
"""mdBook 书籍模式：SUMMARY.md 解析 / 序列化 / 探测（纯函数，无 Qt 依赖）。

设计约束（产品需求）：必须支持 3000+ 页的超大型书籍。因此本模块
**只解析 SUMMARY.md 的目录索引文本**，绝不在内存中读取任何章节正文；
章节正文由编辑器在「点击时惰性加载」。所有函数均为纯函数（输入文本 /
路径 → 输出数据），便于探针独立验证。

mdBook SUMMARY.md 约定：
  - 首行 `# 标题` 为书籍标题（仅出现一次）；其后 `# 标题` 为「Part 分区」。
  - `- [文本](相对路径)` 为章节条目；缩进（2 空格/级）表达嵌套层级。
  - `---` 为分隔符。
  - 章节可无子弹头直接写为 `[文本](路径)`（mdBook 官方顶层级写法），
    也能处理带子弹头 `- 文本`（无链接的占位条目）。
"""

import os
import re

# 节点 kind 取值：'root' | 'part' | 'chapter' | 'separator'

_MD_EXT_RE = re.compile(r"\.(md|markdown|mdown)$", re.IGNORECASE)


def parse_summary(text):
    """把 SUMMARY.md 文本解析为层级树。

    返回 root 节点：{"kind":"root","title":<书籍标题|None>,"children":[...]}。
    每个节点形如：
      part:     {"kind":"part","title":str,"children":[...],"line":int}
      chapter:  {"kind":"chapter","title":str,"path":str|None,
                 "abs_path":str|None,"children":[...],"line":int}
      separator:{"kind":"separator","line":int}

    不读取任何章节内容；path 保持原文相对字符串，abs_path 在 read_book
    阶段按 SUMMARY 所在目录解析（本函数不解析 abs_path）。
    """
    root = {"kind": "root", "title": None, "children": []}
    lines = text.split("\n")
    book_title = None
    seen_title = False
    current_part = None
    # 缩进栈：(indent, container_node)；栈底 base = current_part 或 root
    stack = [(-1, root)]

    def base():
        return current_part if current_part is not None else root

    for idx, raw in enumerate(lines):
        line = raw.rstrip("\r")
        stripped = line.strip()
        if not stripped:
            continue

        # ---- 标题：首行 # 为书籍标题，其余 # 均为 Part 分区 ----
        if stripped.startswith("#"):
            level = 0
            i = 0
            while i < len(stripped) and stripped[i] == "#":
                level += 1
                i += 1
            title = stripped[i:].strip()
            if level == 1 and not seen_title:
                book_title = title
                seen_title = True
                continue
            node = {"kind": "part", "title": title, "children": [], "line": idx}
            root["children"].append(node)
            current_part = node
            stack = [(-1, current_part)]   # Part 之后的章节归该 Part
            continue

        # ---- 分隔符 ----
        if re.match(r"^-{3,}\s*$", stripped):
            root["children"].append({"kind": "separator", "line": idx})
            continue

        # ---- 列表 / 章节条目（子弹头可选，缩进表达层级）----
        m = re.match(r"^(\s*)([-*+])?\s*(.*\S)\s*$", line)
        if m:
            indent = len(m.group(1).replace("\t", "    "))
            has_bullet = m.group(2) is not None
            content = m.group(3).strip()
            lm = re.match(r"^\[(.*?)\]\((.*?)\)\s*$", content)
            if lm:
                node = {"kind": "chapter", "title": lm.group(1).strip(),
                        "path": lm.group(2).strip(), "abs_path": None,
                        "children": [], "line": idx}
            elif has_bullet:
                # 带子弹头但无链接的占位条目
                node = {"kind": "chapter", "title": content, "path": None,
                        "abs_path": None, "children": [], "line": idx}
            else:
                # 纯散文行：跳过（SUMMARY 中章节均为链接）
                continue
            while len(stack) > 1 and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]
            parent["children"].append(node)
            stack.append((indent, node))
            continue
        # 其它内容（脚注、注释等）忽略

    root["title"] = book_title
    return root


def _serialize_node(node, depth, out):
    if node["kind"] == "separator":
        out.append("---")
        return
    if node["kind"] == "part":
        out.append("# " + node["title"])
        if node["children"]:
            out.append("")   # Part 标题与其首章之间空一行（mdBook 习惯）
        for ch in node["children"]:
            _serialize_node(ch, 0, out)
        return
    if node["kind"] == "chapter":
        indent = "  " * depth
        if node.get("path"):
            out.append("%s- [%s](%s)" % (indent, node["title"], node["path"]))
        else:
            out.append("%s- %s" % (indent, node["title"]))
        for ch in node["children"]:
            _serialize_node(ch, depth + 1, out)
        return


def serialize_summary(root):
    """把解析后的层级树反向序列化为规范 SUMMARY.md 文本。

    约定：书籍标题 `# 标题` + 空行；顶层条目间空一行；Part 后紧跟其章节
    （无额外空行）；相对路径与缩进保持。返回带结尾换行的字符串。"""
    out = []
    title = root.get("title")
    if title:
        out.append("# " + title)
        out.append("")
    children = root.get("children", [])
    for i, child in enumerate(children):
        if i > 0:
            out.append("")  # 顶层条目之间空一行
        _serialize_node(child, 0, out)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# ================= 文件系统探测 =================

def detect_book_dir(path):
    """从给定 path（book.toml / 目录 / SUMMARY.md / 某章节 .md）推断书籍根目录。

    返回书籍根目录绝对路径；无法判定返回 None。"""
    if not path:
        return None
    if os.path.isfile(path):
        p = os.path.abspath(path)
        d = os.path.dirname(p)
        base = os.path.basename(p).lower()
        if base == "book.toml" or base == "summary.md":
            return d
        # 普通 .md：若其所在目录（或 src/）含 SUMMARY.md 则视为书籍根
        if (os.path.exists(os.path.join(d, "book.toml"))
                or os.path.exists(os.path.join(d, "SUMMARY.md"))
                or os.path.exists(os.path.join(d, "src", "SUMMARY.md"))):
            return d
        return None
    if os.path.isdir(path):
        d = os.path.abspath(path)
        if os.path.exists(os.path.join(d, "book.toml")):
            return d
        if os.path.exists(os.path.join(d, "SUMMARY.md")):
            return d
        if os.path.exists(os.path.join(d, "src", "SUMMARY.md")):
            return os.path.join(d, "src")
        return None
    return None


def find_summary_path(book_dir):
    """在书籍根目录下定位 SUMMARY.md（优先根目录，其次 src/）。"""
    for cand in ("SUMMARY.md", os.path.join("src", "SUMMARY.md")):
        p = os.path.join(book_dir, cand)
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


def _resolve_paths(node, base):
    """递归解析章节 abs_path（相对 SUMMARY 目录）；就地填充节点。"""
    for ch in node.get("children", []):
        if ch["kind"] == "chapter" and ch.get("path"):
            ch["abs_path"] = os.path.normpath(
                os.path.join(base, ch["path"]))
        _resolve_paths(ch, base)


def read_book(path):
    """读取并解析一本书籍，返回书籍信息字典；非书籍返回 None。

    返回：{"book_dir","summary_path","summary_dir","root","title"}。
    root 中每个 chapter 节点含 abs_path（按 SUMMARY 所在目录解析）。
    不读取任何章节正文（满足 3000 页大文件约束）。"""
    book_dir = detect_book_dir(path)
    if not book_dir:
        return None
    summary = find_summary_path(book_dir)
    if not summary:
        return None
    summary = os.path.abspath(summary)
    try:
        with open(summary, "r", encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        return None
    root = parse_summary(text)
    summary_dir = os.path.dirname(summary)
    _resolve_paths(root, summary_dir)
    # book_dir 取书籍根（SUMMARY 在 src/ 下时上溯一级），用于标题与写回定位
    if os.path.basename(summary_dir).lower() == "src":
        book_dir = os.path.dirname(summary_dir)
    else:
        book_dir = summary_dir
    return {
        "book_dir": book_dir,
        "summary_path": summary,
        "summary_dir": summary_dir,
        "root": root,
        "title": root.get("title") or os.path.basename(book_dir),
    }


def write_summary(summary_path, root):
    """把层级树序列化并写回 SUMMARY.md（utf-8）。"""
    text = serialize_summary(root)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(text)


# ================= 树操作辅助 =================

def flat_chapters(root):
    """深度优先展开所有 chapter 节点（文档顺序），便于上一章/下一章与高亮。"""
    res = []

    def walk(n):
        for ch in n.get("children", []):
            if ch["kind"] == "chapter":
                res.append(ch)
                walk(ch)
            elif ch["kind"] == "part":
                walk(ch)
    walk(root)
    return res


def find_chapter(root, abs_path):
    """按绝对路径定位 chapter 节点（大小写不敏感、归一化比较）。"""
    if not abs_path:
        return None
    target = os.path.normpath(os.path.abspath(abs_path)).lower()
    for ch in flat_chapters(root):
        ap = ch.get("abs_path")
        if ap and os.path.normpath(os.path.abspath(ap)).lower() == target:
            return ch
    return None


def chapter_neighbors(root, node):
    """返回 (prev_chapter, next_chapter) 或 None；node 必须是 chapter 节点。"""
    flat = flat_chapters(root)
    for i, ch in enumerate(flat):
        if ch is node:
            prev_c = flat[i - 1] if i > 0 else None
            next_c = flat[i + 1] if i + 1 < len(flat) else None
            return prev_c, next_c
    return None, None


def iter_all(root):
    """生成器：按文档顺序产出所有节点（root 自身除外）。"""
    def walk(n):
        for ch in n.get("children", []):
            yield ch
            for x in walk(ch):
                yield x
    for x in walk(root):
        yield x


def is_md_path(p):
    """判断路径是否像 Markdown 文件（用于相对链接拦截）。"""
    if not p:
        return False
    return bool(_MD_EXT_RE.search(p.split("#")[0]))
