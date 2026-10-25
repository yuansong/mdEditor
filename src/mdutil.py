# -*- coding: utf-8 -*-
"""mdEditor 共享工具：锚点命名规范（与编辑器 JS slugify 同源）。

算法（单一事实来源，编辑器 editor.html 的 slugify 必须逐字符等价）：
  slugify(text):
    1. trim，内部连续空白折叠为单个空格
    2. 小写化（仅用于匹配，展示保留原文）
    3. 仅保留 Unicode 字母 / 数字 / 空格（CJK 原样保留），其余（标点）丢弃
    4. 空格 -> '-'，去首尾与连续 '-'
    空结果由调用方回退 'section-n'。
"""
import re


def slugify(text):
    if not text:
        return ""
    s = " ".join(str(text).strip().split()).lower()
    out = []
    for ch in s:
        # str.isalnum() 覆盖 Unicode 字母/数字（含 CJK），与 JS [\p{L}\p{N}] 等价
        if ch.isalnum() or ch == " ":
            out.append(ch)
    s = "".join(out).replace(" ", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def heading_anchors(texts):
    """给定一组标题文本，返回去重后的锚点 slug 列表（同章同名靠 -2/-3 区分）。"""
    seen = {}
    out = []
    for t in texts:
        base = slugify(t) or "section"
        if base in seen:
            seen[base] += 1
            slug = "%s-%d" % (base, seen[base])
            while slug in seen:
                seen[base] += 1
                slug = "%s-%d" % (base, seen[base])
        else:
            slug = base
            seen[base] = 1
        out.append(slug)
    return out


def extract_headings(md, max_level=4):
    """从 markdown 文本提取 ATX 标题（# ~ ######），返回
    [{level, text, slug, line}]，slug 已按章内去重。"""
    if not md:
        return []
    lines = md.splitlines()
    heads = []
    for ln, raw in enumerate(lines, start=1):
        st = raw.strip()
        m = re.match(r"^(#{1,6})\s+(.*)$", st)
        if not m:
            continue
        level = len(m.group(1))
        if level > max_level:
            continue
        text = m.group(2).strip()
        heads.append({"level": level, "text": text, "slug": None, "line": ln})
    texts = [h["text"] for h in heads]
    slugs = heading_anchors(texts)
    for h, s in zip(heads, slugs):
        h["slug"] = s
    return heads
