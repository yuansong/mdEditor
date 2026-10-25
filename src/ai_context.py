# -*- coding: utf-8 -*-
"""AI 上下文自适应裁剪（v3.48.18，AI-CTX）。

目标：在保证改写 / 问答准确的前提下显著降低送入模型的 token 消耗。
按「文档体量 + 是否书籍 + 是否有选区」自动选择三档策略：

  ┌ full    篇幅 <= 阈值（默认 6000 字）           → 整篇输入（保真最高）
  ├ outline 篇幅 >  阈值                           → 标题 + 大纲 + 目标段落前后邻段
  └ book    书籍模式（正编辑某章节）               → 完整目录 + 定位到的章节（章节过长再降为 outline）

阈值与邻段数可配置（QSettings `ai/ctx_threshold`、`ai/ctx_neighbors`），
也可由调用方显式传入（便于测试与批量任务覆盖）。

对外只暴露：
  · load_config(settings) / save_config(settings, threshold, neighbors)
  · split_blocks(md) / build_outline(blocks)
  · build_context(markdown, target_text=..., caret_block=..., ..., book=...)
      -> (context_text, meta)
  · est_tokens(text) / summarize(meta)
"""
import re

from mdrender import md_to_plain

# 默认阈值：字符数（中英混排按字符计；约等于 4~6k token 量级）
DEFAULT_THRESHOLD = 6000
# 目标段落前后各取几段
DEFAULT_NEIGHBORS = 1
# 邻段最少字数（过短的段落多取几段才有信息量）
_MIN_NEIGHBOR_CHARS = 60
# 大纲最多列出多少个标题（防超长文档大纲本身爆量）
_MAX_OUTLINE_ITEMS = 120

_HEAD_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


# ---------------------------------------------------------------- 配置

def load_config(settings):
    """从 QSettings 读取上下文策略；缺省 / 非法值一律回落默认。"""
    threshold = DEFAULT_THRESHOLD
    neighbors = DEFAULT_NEIGHBORS
    try:
        v = settings.value("ai/ctx_threshold", DEFAULT_THRESHOLD)
        threshold = int(v)
    except (TypeError, ValueError):
        threshold = DEFAULT_THRESHOLD
    try:
        v = settings.value("ai/ctx_neighbors", DEFAULT_NEIGHBORS)
        neighbors = int(v)
    except (TypeError, ValueError):
        neighbors = DEFAULT_NEIGHBORS
    if threshold < 500:
        threshold = 500
    neighbors = max(0, min(5, neighbors))
    return {"threshold": threshold, "neighbors": neighbors}


def save_config(settings, threshold, neighbors):
    try:
        settings.setValue("ai/ctx_threshold", max(500, int(threshold)))
        settings.setValue("ai/ctx_neighbors", max(0, min(5, int(neighbors))))
        settings.sync()
    except Exception:      # noqa: BLE001 —— 配置写入失败不应影响主流程
        pass


# ---------------------------------------------------------------- 分词 / 估算

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def est_tokens(text):
    """粗略 token 估算：CJK 约 1 字 1 token，拉丁文按 4 字符 1 token。"""
    s = str(text or "")
    cjk = len(_CJK_RE.findall(s))
    words = _WORD_RE.findall(s)
    latin = sum(len(w) for w in words)
    other = max(0, len(s) - cjk - latin)
    return int(cjk + latin / 4.0 + other / 4.0)


# ---------------------------------------------------------------- 块切分

def split_blocks(md):
    """按空行切块，围栏代码块内部不切（整体作为一个块）。

    返回块文本列表（不含分隔空行）。空文档返回 []。
    """
    lines = str(md or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks, buf, fence = [], [], ""

    def _flush():
        if buf:
            txt = "\n".join(buf).strip("\n")
            if txt.strip():
                blocks.append(txt)
            buf.clear()

    for line in lines:
        s = line.strip()
        if fence:
            buf.append(line)
            if s and set(s) == {fence[0]} and len(s) >= len(fence):
                fence = ""
                _flush()
            continue
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            _flush()
            fence = m.group(1)
            buf.append(line)
            continue
        if not s:
            _flush()
            continue
        buf.append(line)
    _flush()
    return blocks


def build_outline(blocks):
    """提取标题大纲：[{level, title, block}]（block 为块下标）。"""
    out = []
    for i, b in enumerate(blocks):
        first = b.split("\n", 1)[0]
        m = _HEAD_RE.match(first)
        if m:
            out.append({"level": len(m.group(1)),
                        "title": m.group(2).strip(), "block": i})
            if len(out) >= _MAX_OUTLINE_ITEMS:
                break
    return out


def _norm(s):
    """归一：去掉 Markdown 符号与全部空白，用于目标段落定位。"""
    return re.sub(r"\s+", "", md_to_plain(s or ""))


def locate_block(blocks, target_text, caret_block=None):
    """定位目标段落下标。

    优先按 target_text 的**可见文本**匹配（忽略 Markdown 符号与空白差异），
    匹配不到时回落到光标所在块，再不行取 0。多次出现时优先取离
    caret_block 最近的一次（避免同名段落错位）。
    """
    tgt = _norm(target_text)
    hits = []
    if tgt:
        for i, b in enumerate(blocks):
            if tgt in _norm(b):
                hits.append(i)
    if hits:
        if caret_block is not None and caret_block >= 0:
            return min(hits, key=lambda i: abs(i - caret_block))
        return hits[0]
    if caret_block is not None and 0 <= caret_block < len(blocks):
        return caret_block
    return 0


def _neighbor_span(blocks, idx, neighbors):
    """以 idx 为中心向两侧扩展，直到覆盖至少 neighbors 段且字数达标。"""
    if not blocks:
        return 0, -1
    lo = max(0, idx - neighbors)
    hi = min(len(blocks) - 1, idx + neighbors)
    # 邻段太短则继续外扩（最多再扩 2 段，防爆量）
    extra = 0
    while extra < 2:
        span = "\n".join(blocks[lo:hi + 1])
        if len(span) >= _MIN_NEIGHBOR_CHARS or (lo == 0 and hi == len(blocks) - 1):
            break
        if lo > 0:
            lo -= 1
        elif hi < len(blocks) - 1:
            hi += 1
        else:
            break
        extra += 1
    return lo, hi


def _outline_text(outline, blocks, mark_total_hint=True):
    if not outline:
        return "（本文档没有 Markdown 标题）"
    lines = []
    for h in outline:
        indent = "  " * max(0, h["level"] - 1)
        lines.append("%s- H%d %s　〔第 %d 段〕"
                     % (indent, h["level"], h["title"], h["block"] + 1))
    return "\n".join(lines)


# ---------------------------------------------------------------- 主入口

def build_context(markdown, target_text="", caret_block=None,
                  threshold=None, neighbors=None, book=None):
    """构建送入模型的文档上下文。

    参数
      markdown     当前文档全文（书籍模式下为当前章节全文）
      target_text  用户选中的原文 / 提问所指向的片段（可为空）
      caret_block  光标所在块下标（可为 None）
      book         {"title": str, "toc": [(depth, title, path)], 
                    "chapter_path": str, "chapter_title": str} 或 None
    返回
      (context_text, meta)。meta 含 mode / chars_in / chars_out /
      tokens_in / tokens_out / saved_pct，供 UI 与日志展示。
    """
    md = str(markdown or "")
    total = len(md)

    if threshold is None or threshold <= 0:
        threshold = DEFAULT_THRESHOLD
    if neighbors is None:
        neighbors = DEFAULT_NEIGHBORS

    # 空文档 / 纯空白：不产生任何上下文（避免给模型一段无信息的壳）
    if not md.strip():
        return "", {"mode": "empty", "chars_in": 0, "chars_out": 0,
                    "tokens_in": 0, "tokens_out": 0, "saved_pct": 0,
                    "blocks": 0, "target_block": None, "chapter": ""}

    blocks = split_blocks(md)
    outline = build_outline(blocks)

    meta = {"mode": "full", "chars_in": total, "chars_out": 0,
            "tokens_in": est_tokens(md), "tokens_out": 0, "saved_pct": 0,
            "blocks": len(blocks), "target_block": None,
            "chapter": ""}

    # ---------------- 书籍模式 ----------------
    if book and (book.get("toc") or book.get("chapter_path")):
        idx = locate_block(blocks, target_text, caret_block)
        meta["target_block"] = idx
        toc = book.get("toc") or []
        title = book.get("title") or "（未命名书籍）"
        ch_title = book.get("chapter_title") or ""
        meta["chapter"] = ch_title

        toc_lines = []
        for depth, t, path in toc[:_MAX_OUTLINE_ITEMS]:
            mark = " ← 当前章节" if path and path == book.get("chapter_path") else ""
            toc_lines.append("%s- %s%s" % ("  " * max(0, int(depth)), t, mark))
        toc_txt = "\n".join(toc_lines) or "（目录为空）"

        if total <= threshold:
            meta["mode"] = "book-full"
            body = ("## 当前章节：%s\n\n%s" % (ch_title or "（未命名）", md))
        else:
            meta["mode"] = "book-oct"
            lo, hi = _neighbor_span(blocks, idx, neighbors)
            near = "\n\n".join(blocks[lo:hi + 1])
            body = ("## 当前章节：%s（本章 %d 字，超出阈值 %d，仅给本章大纲与目标段邻域）\n\n"
                    "### 本章大纲\n%s\n\n### 目标段落（第 %d 段，含前后邻段）\n%s"
                    % (ch_title or "（未命名）", total, threshold,
                       _outline_text(outline, blocks), idx + 1, near))

        ctx = ("[书籍上下文]\n书名：《%s》\n共 %d 个章节节点。\n\n"
               "## 完整目录\n%s\n\n%s\n[/书籍上下文]"
               % (title, len(toc), toc_txt, body))
        meta["chars_out"] = len(ctx)
        meta["tokens_out"] = est_tokens(ctx)
        meta["saved_pct"] = _saved(meta["tokens_in"], meta["tokens_out"])
        return ctx, meta

    # ---------------- 短文档：全文 ----------------
    if total <= threshold:
        meta["mode"] = "full"
        ctx = ("[文档上下文 · 全文]\n共 %d 字（未超阈值 %d），已提供完整内容。\n---\n%s\n---\n"
               "[/文档上下文]" % (total, threshold, md))
        meta["chars_out"] = len(ctx)
        meta["tokens_out"] = est_tokens(ctx)
        meta["saved_pct"] = _saved(meta["tokens_in"], meta["tokens_out"])
        return ctx, meta

    # ---------------- 长文档：标题 + 大纲 + 目标段邻域 ----------------
    idx = locate_block(blocks, target_text, caret_block)
    meta["mode"] = "outline"
    meta["target_block"] = idx
    lo, hi = _neighbor_span(blocks, idx, neighbors)

    near_parts = []
    for k in range(lo, hi + 1):
        tag = " ★目标段" if k == idx else ""
        near_parts.append("〔第 %d 段%s〕\n%s" % (k + 1, tag, blocks[k]))
    near = "\n\n".join(near_parts)

    heads = " > ".join(
        h["title"] for h in outline
        if h["block"] <= idx)[-200:] if outline else ""

    ctx = (
        "[文档上下文 · 大纲模式]\n"
        "全文 %d 字，超出阈值 %d。为节省 token，未提供全文；"
        "请基于下方「文档大纲」与「目标段落邻域」作答，"
        "不要臆造未被提供的内容。\n\n"
        "## 当前定位\n%s\n\n"
        "## 文档大纲（共 %d 个标题）\n%s\n\n"
        "## 目标段落（第 %d 段，含前后各 %d 段）\n%s\n"
        "[/文档上下文]"
        % (total, threshold,
           ("标题路径：" + heads) if heads else "（文档无标题层级）",
           len(outline), _outline_text(outline, blocks),
           idx + 1, neighbors, near))
    meta["chars_out"] = len(ctx)
    meta["tokens_out"] = est_tokens(ctx)
    meta["saved_pct"] = _saved(meta["tokens_in"], meta["tokens_out"])
    return ctx, meta


def _saved(t_in, t_out):
    if not t_in:
        return 0
    return max(0, int(round((t_in - t_out) * 100.0 / t_in)))


def summarize(meta):
    """一行人类可读摘要（用于状态条 / 日志）。"""
    if not meta:
        return ""
    mode = {"full": "全文", "outline": "大纲+邻段",
            "book-full": "书籍·整章", "book-oct": "书籍·目录+章节要点"}.get(
                meta.get("mode"), meta.get("mode") or "")
    return ("上下文：%s · %d 字 → %d 字（省 %d%%）"
            % (mode, meta.get("chars_in", 0), meta.get("chars_out", 0),
               meta.get("saved_pct", 0)))
