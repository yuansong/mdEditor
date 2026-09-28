# -*- coding: utf-8 -*-
"""v3.30.18c 补丁：导出批次之 exporters.py（FN-2 / DL-5）
- FN-2：行内 `[^id]` 引用识别 → DOCX 上标 [id] / EPUB 上标链接；`[^id]: 定义`
  识别为独立块 → DOCX 标签段 / EPUB 带锚点定义段（不再按字面输出 [^1]）
- DL-5：`术语\\n: 定义` 定义列表识别 → DOCX 术语加粗 + 定义缩进段 /
  EPUB <dl><dt><dd>（不再输出字面冒号段落）
每处替换恰好命中 1 次，失败即中止。"""
import io, sys

P = r"E:\WorkBuddy\md-editor\src\exporters.py"
with io.open(P, "r", encoding="utf-8") as f:
    src = f.read()

def rep(old, new, tag):
    global src
    n = src.count(old)
    if n != 1:
        print("FAIL %s: match count = %d" % (tag, n))
        sys.exit(1)
    src = src.replace(old, new)
    print("ok", tag)

# ---------- 1. 正则：fnref 引用 / 脚注定义行 / 定义列表定义行 ----------
rep(r'''_IMG_ONLY = re.compile(r"^!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)$")''',
r'''_IMG_ONLY = re.compile(r"^!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)$")
# v3.30.18（FN-2 / DL-5）：脚注引用、脚注定义行、定义列表定义行
_FNREF = re.compile(r"\[\^([^\]\s]+)\]")
_FNDEF = re.compile(r"^\s{0,3}\[\^([^\]\s]+)\]:\s*(.*)$")
_DL_DEF = re.compile(r"^\s{0,3}:\s+(.*)$")''', "regex")

# ---------- 2. _INLINE 加 fnref 组（放在图片组之后、行内码之前） ----------
rep(r'''_INLINE = re.compile(
    r"(!\[[^\]]*\]\([^)]*\))"
    r"|(`[^`]+`)"''',
r'''_INLINE = re.compile(
    r"(!\[[^\]]*\]\([^)]*\))"
    r"|(\[\^[^\]\s]+\])"
    r"|(`[^`]+`)"''', "inline-fnref")

# ---------- 3. parse_blocks：fndef 块 + deflist 块 ----------
rep(r'''        m = _HEAD.match(line)
        if m:
            blocks.append({"kind": "heading", "level": len(m.group(1)), "text": m.group(2)})
            i += 1
            continue''',
r'''        m = _FNDEF.match(line)
        if m:
            # v3.30.18（FN-2）：脚注定义独立成块
            blocks.append({"kind": "fndef", "id": m.group(1), "text": m.group(2)})
            i += 1
            continue

        m = _HEAD.match(line)
        if m:
            blocks.append({"kind": "heading", "level": len(m.group(1)), "text": m.group(2)})
            i += 1
            continue''', "blocks-fndef")

rep(r'''        # 普通段落：合并连续非空行，遇到其它块起始则停止
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not any(r.match(lines[i]) for r in (
                _HEAD, _FENCE_OPEN, _QUOTE, _ULI, _OLI, _HR)):
            buf.append(lines[i])
            i += 1
        blocks.append({"kind": "para", "text": "\n".join(buf)})''',
r'''        # 普通段落：合并连续非空行，遇到其它块起始则停止
        # （v3.30.18（DL-5）：": 定义" 行视为定义列表组成部分，段落收集在此停住）
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not any(r.match(lines[i]) for r in (
                _HEAD, _FENCE_OPEN, _QUOTE, _ULI, _OLI, _HR, _DL_DEF)):
            buf.append(lines[i])
            i += 1
        if i < n and _DL_DEF.match(lines[i]) and buf:
            # v3.30.18（DL-5）：术语 + ": 定义"... → 定义列表块
            defs = []
            while i < n and _DL_DEF.match(lines[i]):
                defs.append(_DL_DEF.match(lines[i]).group(1).strip())
                i += 1
            blocks.append({"kind": "deflist",
                           "term": "\n".join(buf).strip(), "defs": defs})
            continue
        blocks.append({"kind": "para", "text": "\n".join(buf)})''', "blocks-deflist")

# ---------- 4. parse_inline：fnref token 分派 ----------
rep(r'''        tok = m.group(0)
        if m.group(1):                      # 图片
            im = _IMG_ONLY.match(tok)
            out.append({"image": im.group(2) if im else "", "alt": im.group(1) if im else ""})
        elif m.group(2):                    # 行内代码
            out.append({"text": tok[1:-1], "code": True})''',
r'''        tok = m.group(0)
        if m.group(1):                      # 图片
            im = _IMG_ONLY.match(tok)
            out.append({"image": im.group(2) if im else "", "alt": im.group(1) if im else ""})
        elif m.group(2):                    # 脚注引用 [^id]（v3.30.18 FN-2）
            out.append({"fnref": tok[2:-1]})
        elif m.group(3):                    # 行内代码
            out.append({"text": tok[1:-1], "code": True})''', "parse-fnref")

# 后续组号整体 +1（图片 1、fnref 2、code 3、bold 4、italic 5、strike 6、link 7、math 8）
rep(r'''        elif m.group(3):                    # 粗体
            out.append({"text": tok[2:-2], "bold": True})
        elif m.group(4):                    # 斜体
            out.append({"text": tok[1:-1], "italic": True})
        elif m.group(5):                    # 删除线
            out.append({"text": tok[2:-2], "strike": True})
        elif m.group(6):                    # 链接
            lb = re.match(r"\[([^\]]+)\]\(([^)]*)\)", tok)
            out.append({"text": lb.group(1) if lb else tok,
                        "link": (lb.group(2) if lb else "")})
        elif m.group(7):                    # 行内公式 $...$ → 去 $ 纯文本（MATH-2）
            out.append({"text": tok[1:-1]})''',
r'''        elif m.group(4):                    # 粗体
            out.append({"text": tok[2:-2], "bold": True})
        elif m.group(5):                    # 斜体
            out.append({"text": tok[1:-1], "italic": True})
        elif m.group(6):                    # 删除线
            out.append({"text": tok[2:-2], "strike": True})
        elif m.group(7):                    # 链接
            lb = re.match(r"\[([^\]]+)\]\(([^)]*)\)", tok)
            out.append({"text": lb.group(1) if lb else tok,
                        "link": (lb.group(2) if lb else "")})
        elif m.group(8):                    # 行内公式 $...$ → 去 $ 纯文本（MATH-2）
            out.append({"text": tok[1:-1]})''', "parse-groups")

# ---------- 5. plain_inline：fnref → [id]（降级纯文本） ----------
rep(r'''def plain_inline(text):
    """行内元素 → 纯文本（降级、图表源码等场景用）。"""
    parts = []
    for t in parse_inline(text):
        if t.get("image"):
            parts.append(t.get("alt") or "图片")
        else:
            parts.append(t.get("text") or "")
    return "".join(parts)''',
r'''def plain_inline(text):
    """行内元素 → 纯文本（降级、图表源码等场景用）。"""
    parts = []
    for t in parse_inline(text):
        if t.get("image"):
            parts.append(t.get("alt") or "图片")
        elif t.get("fnref"):
            parts.append("[" + t["fnref"] + "]")
        else:
            parts.append(t.get("text") or "")
    return "".join(parts)''', "plain-fnref")

# ---------- 6. DOCX：_add_runs 脚注上标 ----------
rep(r'''        r = paragraph.add_run(t.get("text") or "")
        r.bold = bool(t.get("bold"))
        r.italic = bool(t.get("italic")) or bool(t.get("link"))
        r.font.strike = bool(t.get("strike"))
        if t.get("code"):
            _run_font(r, _MONO_FONT)
        if t.get("link") and t.get("text"):
            r.font.underline = True
    return paragraph''',
r'''        if t.get("fnref"):
            # v3.30.18（FN-2）：脚注引用 → 上标 [id]（Word 原生脚注对象成本高，
            # 按「正文上标 [n] + 文末定义段」降级，语义不再按字面丢失）
            r2 = paragraph.add_run("[" + t["fnref"] + "]")
            r2.font.superscript = True
            continue
        r = paragraph.add_run(t.get("text") or "")
        r.bold = bool(t.get("bold"))
        r.italic = bool(t.get("italic")) or bool(t.get("link"))
        r.font.strike = bool(t.get("strike"))
        if t.get("code"):
            _run_font(r, _MONO_FONT)
        if t.get("link") and t.get("text"):
            r.font.underline = True
    return paragraph''', "docx-fnref")

# ---------- 7. DOCX：write_docx 加 fndef / deflist 块渲染 ----------
rep(r'''        elif k == "hr":
            p = doc.add_paragraph()
            _shade(p, "DDDDDD")

    try:
        doc.save(out_path)''',
r'''        elif k == "fndef":
            # v3.30.18（FN-2）：脚注定义 → 文末标签段
            p = doc.add_paragraph()
            rlab = p.add_run("[" + blk["id"] + "]")
            rlab.bold = True
            p.add_run(" " + (blk["text"] or ""))
            for r in p.runs:
                r.font.size = Pt(9.5)
        elif k == "deflist":
            # v3.30.18（DL-5）：定义列表 → 术语加粗段 + 定义缩进段
            pt = doc.add_paragraph()
            rt = pt.add_run(plain_inline(blk.get("term") or ""))
            rt.bold = True
            for d in blk.get("defs") or []:
                pd = doc.add_paragraph()
                pd.paragraph_format.left_indent = Pt(18)
                _add_runs(pd, d, base_dir, doc)
        elif k == "hr":
            p = doc.add_paragraph()
            _shade(p, "DDDDDD")

    try:
        doc.save(out_path)''', "docx-blocks")

# ---------- 8. EPUB：_xinline 脚注上标链接 ----------
rep(r'''    for t in parse_inline(text):
        if t.get("image"):
            out.append(f'<img src="images/{_xesc(_img_name(t["image"]))}" '
                       f'alt="{_xesc(t.get("alt") or "")}"/>')
            continue
        s = _xesc(t.get("text") or "")''',
r'''    for t in parse_inline(text):
        if t.get("image"):
            out.append(f'<img src="images/{_xesc(_img_name(t["image"]))}" '
                       f'alt="{_xesc(t.get("alt") or "")}"/>')
            continue
        if t.get("fnref"):
            # v3.30.18（FN-2）：脚注引用 → 上标锚链接（跳到文末定义）
            fid = _xesc(t["fnref"])
            out.append(f'<sup class="fnref"><a href="#fn-{fid}">[{fid}]</a></sup>')
            continue
        s = _xesc(t.get("text") or "")''', "epub-fnref")

# ---------- 9. EPUB：_blocks_to_xhtml 加 fndef / deflist ----------
rep(r'''        elif k == "fence":
            lang, code = blk["lang"], blk["text"] or ""
            if lang in ("mermaid", "math"):
                label = "图表（Mermaid 源码）" if lang == "mermaid" else "公式（LaTeX 源码）"
                out.append(f'<p class="tip">［{label}］</p>')
            out.append(f"<pre><code>{_xesc(code)}</code></pre>")''',
r'''        elif k == "fndef":
            # v3.30.18（FN-2）：脚注定义 → 带锚点的定义段
            fid = _xesc(blk["id"])
            out.append(f'<p class="fndef" id="fn-{fid}">'
                       f'<strong>[{fid}]</strong> {_xinline(blk.get("text") or "")}</p>')
        elif k == "deflist":
            # v3.30.18（DL-5）：定义列表 → 原生 <dl>（阅读器保留语义）
            out.append("<dl>")
            out.append(f"<dt>{_xinline(blk.get('term') or '')}</dt>")
            for d in blk.get("defs") or []:
                out.append(f"<dd>{_xinline(d)}</dd>")
            out.append("</dl>")
        elif k == "fence":
            lang, code = blk["lang"], blk["text"] or ""
            if lang in ("mermaid", "math"):
                label = "图表（Mermaid 源码）" if lang == "mermaid" else "公式（LaTeX 源码）"
                out.append(f'<p class="tip">［{label}］</p>')
            out.append(f"<pre><code>{_xesc(code)}</code></pre>")''', "epub-blocks")

# ---------- 10. EPUB CSS：fnref / fndef 样式 ----------
rep(r'''.tip{color:#8a8a8a;font-style:italic}
"""''',
r'''.tip{color:#8a8a8a;font-style:italic}
sup.fnref a{text-decoration:none;font-size:.75em}
p.fndef{font-size:.88em;color:#444;margin:.3em 0}
dl dt{font-weight:700;margin-top:.6em}
dl dd{margin:0 0 .4em 1.6em}
"""''', "epub-css")

with io.open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("ALL PATCHED")
