# -*- coding: utf-8 -*-
"""导出后端（离线可用）：Markdown → Word(.docx) / EPUB 3，以及 PDF 书签后处理。

设计原则
--------
1. **不强依赖外部工具**：本机装了 pandoc 时优先调用（转换质量最好）；
   未安装则用内置实现（python-docx / 标准库 zipfile）保证绿色便携版开箱可用。
2. **诚实的降级**：`` ```math `` 公式块与 `` ```mermaid `` 图表块无法在离线环境
   渲染成位图，导出时降级为「源码 + 标注」，而不是静默丢失。
3. 图片按 Markdown 中的相对路径相对**文档所在目录**解析；找不到则跳过该图。
"""
import base64
import html as _html
import logging
import os
import re
import shutil
import subprocess
import uuid
import zipfile

_log = logging.getLogger("mdEditor.export")

# ---------------------------------------------------------------- Markdown 解析

_HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")
_FENCE_OPEN = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([^\s`]*)\s*$")
_QUOTE = re.compile(r"^\s{0,3}>\s?(.*)$")
_ULI = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_OLI = re.compile(r"^(\s*)\d{1,9}[.)]\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")

# 行内元素：图片 / 行内代码 / 粗体 / 斜体 / 删除线 / 链接 / 行内公式
# （v3.30.11 MATH-2：行内 $...$ 识别后降级为去 $ 纯文本，DOCX/EPUB 不再出现
#   裸 $ 标记；护栏同 editor —— 内容首尾非空白、闭合 $ 后不跟字母/数字/$，
#   避免「价格 $5，再 $6」误判）
_INLINE = re.compile(
    r"(!\[[^\]]*\]\([^)]*\))"
    r"|(\[\^[^\]\s]+\])"
    r"|(`[^`]+`)"
    r"|(\*\*[^*]+\*\*|__[^_]+__)"
    r"|(\*[^*]+\*|_[^_]+_)"
    r"|(~~[^~]+~~)"
    r"|(\[[^\]]+\]\([^)]*\))"
    r"|(\$(?!\s)[^$\n]+?(?<!\s)\$(?![\w$]))"
)
_IMG_ONLY = re.compile(r"^!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)$")
# v3.30.18（FN-2 / DL-5）：脚注引用、脚注定义行、定义列表定义行
_FNREF = re.compile(r"\[\^([^\]\s]+)\]")
_FNDEF = re.compile(r"^\s{0,3}\[\^([^\]\s]+)\]:\s*(.*)$")
_DL_DEF = re.compile(r"^\s{0,3}:\s+(.*)$")


def _split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_blocks(md):
    """把 Markdown 切成结构化块列表（导出用，够用即可）。"""
    lines = (md or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        m = _FENCE_OPEN.match(line)
        if m:
            mark, lang = m.group(1)[0], (m.group(2) or "").strip().lower()
            i += 1
            buf = []
            while i < n and not re.match(r"^\s{0,3}" + re.escape(mark) + r"{3,}\s*$", lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1  # 跳过结束围栏
            blocks.append({"kind": "fence", "lang": lang, "text": "\n".join(buf)})
            continue

        m = _FNDEF.match(line)
        if m:
            # v3.30.18（FN-2）：脚注定义独立成块
            blocks.append({"kind": "fndef", "id": m.group(1), "text": m.group(2)})
            i += 1
            continue

        m = _HEAD.match(line)
        if m:
            blocks.append({"kind": "heading", "level": len(m.group(1)), "text": m.group(2)})
            i += 1
            continue

        if _HR.match(line):
            blocks.append({"kind": "hr"})
            i += 1
            continue

        # v3.30.19（MATH-6）：$$…$$ 块级公式 → 按公式源码块降级导出（渲染由
        # 编辑器 / pandoc 通道负责；内置导出与 ```math 同路径）
        m6 = re.match(r"^\s{0,3}\$\$(.*)$", line)
        if m6:
            first6 = m6.group(1)
            i += 1
            if first6.strip().endswith("$$"):
                blocks.append({"kind": "fence", "lang": "math",
                               "text": first6.strip()[:-2].strip()})
                continue
            buf6 = []
            if first6.strip():
                buf6.append(first6)
            while i < n and "$$" not in lines[i]:
                buf6.append(lines[i])
                i += 1
            if i < n:
                buf6.append(re.sub(r"\$\$.*$", "", lines[i]))
                i += 1
            blocks.append({"kind": "fence", "lang": "math",
                           "text": "\n".join(buf6).strip()})
            continue

        if "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            header = _split_row(line)
            aligns = _split_row(lines[i + 1])
            i += 2
            rows = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append(_split_row(lines[i]))
                i += 1
            blocks.append({"kind": "table", "header": header, "aligns": aligns, "rows": rows})
            continue

        if _QUOTE.match(line):
            buf = []
            while i < n and _QUOTE.match(lines[i]):
                buf.append(_QUOTE.match(lines[i]).group(1))
                i += 1
            blocks.append({"kind": "quote", "text": "\n".join(buf).strip()})
            continue

        mu, mo = _ULI.match(line), _OLI.match(line)
        if mu or mo:
            ordered = bool(mo)
            items = []
            while i < n:
                a, b = _ULI.match(lines[i]), _OLI.match(lines[i])
                if not (a or b) or bool(b) != ordered:
                    break
                mm = b or a
                items.append({"indent": len(mm.group(1)) // 2, "text": mm.group(2)})
                i += 1
            blocks.append({"kind": "list", "ordered": ordered, "items": items})
            continue

        # 普通段落：合并连续非空行，遇到其它块起始则停止
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
        blocks.append({"kind": "para", "text": "\n".join(buf)})
    return blocks


def parse_inline(text):
    """行内元素解析 → [{text, bold, italic, code, strike, link, image}]。"""
    out, pos = [], 0
    for m in _INLINE.finditer(text or ""):
        if m.start() > pos:
            out.append({"text": text[pos:m.start()]})
        tok = m.group(0)
        if m.group(1):                      # 图片
            im = _IMG_ONLY.match(tok)
            out.append({"image": im.group(2) if im else "", "alt": im.group(1) if im else ""})
        elif m.group(2):                    # 脚注引用 [^id]（v3.30.18 FN-2）
            out.append({"fnref": tok[2:-1]})
        elif m.group(3):                    # 行内代码
            out.append({"text": tok[1:-1], "code": True})
        elif m.group(4):                    # 粗体
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
            out.append({"text": tok[1:-1]})
        pos = m.end()
    if pos < len(text or ""):
        out.append({"text": text[pos:]})
    return out or [{"text": text or ""}]


def plain_inline(text):
    """行内元素 → 纯文本（降级、图表源码等场景用）。"""
    parts = []
    for t in parse_inline(text):
        if t.get("image"):
            parts.append(t.get("alt") or "图片")
        elif t.get("fnref"):
            parts.append("[" + t["fnref"] + "]")
        else:
            parts.append(t.get("text") or "")
    return "".join(parts)


# ---------------------------------------------------------------- Word (.docx)

_CJK_FONT = "微软雅黑"
_MONO_FONT = "Consolas"


def _set_style_font(style, name, size=None):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt
    style.font.name = name
    if size is not None:
        style.font.size = Pt(size)
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    rf.set(qn("w:eastAsia"), name)


def _run_font(run, name):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    rf.set(qn("w:eastAsia"), name)


def _shade(paragraph, fill):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    pr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def _add_runs(paragraph, text, base_dir, doc, allow_image=True):
    """把一行 Markdown 行内内容写进段落（图片单独成段）。"""
    from docx.shared import Inches
    for t in parse_inline(text):
        if t.get("image"):
            if not allow_image:
                continue
            p = _add_picture(doc, t["image"], base_dir, Inches(5.6))
            if p is None:
                r = paragraph.add_run(f"[图片：{t.get('alt') or os.path.basename(t['image'])}]")
                r.italic = True
            continue
        if t.get("fnref"):
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
    return paragraph


def _add_picture(doc, rel, base_dir, width):
    """按相对路径插入图片；文件不存在返回 None。"""
    if not rel or rel.startswith(("http://", "https://", "data:")):
        return None
    path = rel if os.path.isabs(rel) else os.path.join(base_dir or "", rel.replace("/", os.sep))
    if not os.path.isfile(path):
        return None
    try:
        p = doc.add_paragraph()
        p.alignment = 1  # 居中
        p.add_run().add_picture(path, width=width)
        return p
    except Exception:
        return None


def write_docx(md, out_path, base_dir="", title=None, mmd_png=None):
    """Markdown → .docx。返回 (是否成功, 提示信息)。

    v3.30.19（MMD-2）：mmd_png 为 {图表源码: PNG 路径} 映射（由 GUI 侧把已渲染
    SVG 位图化后传入）；命中时图表直接嵌 PNG，未命中回落「源码 + 标注」降级。
    """
    try:
        import docx
        from docx.shared import Inches, Pt, RGBColor
    except ImportError:
        return False, "缺少 python-docx，无法导出 Word（可安装 pandoc 或 pip install python-docx）"

    doc = docx.Document()
    _set_style_font(doc.styles["Normal"], _CJK_FONT, 10.5)
    for sname in ("List Bullet", "List Number", "Quote"):
        if sname in [s.name for s in doc.styles]:
            try:
                _set_style_font(doc.styles[sname], _CJK_FONT, 10.5)
            except Exception as e:   # v3.29d（B9）：记录而非静默吞掉
                _log.debug("docx 样式 %s 字体设置失败: %s", sname, e)

    for blk in parse_blocks(md):
        k = blk["kind"]
        if k == "heading":
            lvl = max(1, min(4, blk["level"]))
            h = doc.add_heading("", level=lvl)
            try:
                _set_style_font(doc.styles[f"Heading {lvl}"], _CJK_FONT)
            except Exception as e:   # v3.29d（B9）：记录而非静默吞掉
                _log.debug("docx 标题样式 Heading %s 字体设置失败: %s", lvl, e)
            _add_runs(h, blk["text"], base_dir, doc, allow_image=False)
        elif k == "para":
            p = doc.add_paragraph()
            _add_runs(p, blk["text"], base_dir, doc)
        elif k == "list":
            style = "List Number" if blk["ordered"] else "List Bullet"
            for it in blk["items"]:
                try:
                    p = doc.add_paragraph(style=style)
                except KeyError:
                    p = doc.add_paragraph()
                if it["indent"]:
                    p.paragraph_format.left_indent = Pt(18 * (it["indent"] + 1))
                _add_runs(p, it["text"], base_dir, doc)
        elif k == "quote":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            _add_runs(p, blk["text"], base_dir, doc)
            for r in p.runs:
                r.italic = True
                r.font.color.rgb = RGBColor(0x60, 0x60, 0x60)
        elif k == "fence":
            lang, code = blk["lang"], blk["text"]
            if lang == "mermaid" and mmd_png and mmd_png.get(code) \
                    and os.path.isfile(mmd_png[code]):
                # v3.30.19（MMD-2）：已位图化的图表直接嵌 PNG（2x 渲染，白底）
                try:
                    p = doc.add_paragraph()
                    p.alignment = 1  # 居中
                    p.add_run().add_picture(mmd_png[code], width=Inches(5.6))
                    continue
                except Exception as e2:
                    _log.debug("docx 图表 PNG 嵌入失败，回落源码降级: %s", e2)
            if lang == "mermaid":
                tip = doc.add_paragraph()
                _add_runs(tip, "［图表 · Mermaid 源码，请在 mdEditor 中查看渲染效果］", base_dir, doc)
                for r in tip.runs:
                    r.italic = True
                    r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
            elif lang == "math":
                tip = doc.add_paragraph()
                _add_runs(tip, "［公式 · LaTeX 源码］", base_dir, doc)
                for r in tip.runs:
                    r.italic = True
                    r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
            for ln in (code or "").split("\n"):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                _shade(p, "F4F5F7")
                r = p.add_run(ln if ln else " ")
                _run_font(r, _MONO_FONT)
                r.font.size = Pt(9.5)
        elif k == "table":
            header = blk["header"] or [""]
            cols = len(header)
            table = doc.add_table(rows=1, cols=cols)
            try:
                table.style = "Table Grid"
            except KeyError:
                pass
            for c, txt in enumerate(header):
                cell = table.rows[0].cells[c]
                cell.text = ""
                _add_runs(cell.paragraphs[0], txt, base_dir, doc, allow_image=False)
                for r in cell.paragraphs[0].runs:
                    r.bold = True
            for row in blk["rows"]:
                cells = table.add_row().cells
                for c in range(cols):
                    cells[c].text = ""
                    _add_runs(cells[c].paragraphs[0],
                              row[c] if c < len(row) else "", base_dir, doc, allow_image=False)
        elif k == "fndef":
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
        doc.save(out_path)
    except Exception as e:
        return False, f"写入 docx 失败：{e}"
    return True, f"已导出 Word · {out_path}"


# ---------------------------------------------------------------- EPUB 3

_EPUB_CSS = """body{font-family:"Microsoft YaHei","PingFang SC",serif;line-height:1.75;
margin:0 5%;word-wrap:break-word}
h1,h2,h3,h4{line-height:1.35;margin:1.4em 0 .6em}
h1{font-size:1.6em;border-bottom:1px solid #ddd;padding-bottom:.3em}
pre{background:#f5f6f8;padding:.8em;border-radius:6px;overflow-x:auto;font-size:.86em;
white-space:pre-wrap;word-break:break-all}
code{font-family:Consolas,Menlo,monospace;background:#f2f3f5;border-radius:3px;padding:0 .25em}
pre code{background:none;padding:0}
blockquote{border-left:4px solid #d0d7de;margin:1em 0;padding:.2em 1em;color:#57606a}
table{border-collapse:collapse;width:100%;margin:1em 0}
th,td{border:1px solid #d0d7de;padding:.4em .6em;text-align:left}
th{background:#f5f6f8}
img{max-width:100%;height:auto}
hr{border:none;border-top:1px solid #ddd;margin:1.6em 0}
.tip{color:#8a8a8a;font-style:italic}
sup.fnref a{text-decoration:none;font-size:.75em}
p.fndef{font-size:.88em;color:#444;margin:.3em 0}
dl dt{font-weight:700;margin-top:.6em}
dl dd{margin:0 0 .4em 1.6em}
"""

_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def _xesc(s):
    return "".join(_ESC.get(c, c) for c in str(s or ""))


def _xinline(text):
    out = []
    for t in parse_inline(text):
        if t.get("image"):
            out.append(f'<img src="images/{_xesc(_img_name(t["image"]))}" '
                       f'alt="{_xesc(t.get("alt") or "")}"/>')
            continue
        if t.get("fnref"):
            # v3.30.18（FN-2）：脚注引用 → 上标锚链接（跳到文末定义）
            fid = _xesc(t["fnref"])
            out.append(f'<sup class="fnref"><a href="#fn-{fid}">[{fid}]</a></sup>')
            continue
        s = _xesc(t.get("text") or "")
        if not s:
            continue
        if t.get("code"):
            s = f"<code>{s}</code>"
        if t.get("bold"):
            s = f"<strong>{s}</strong>"
        if t.get("italic"):
            s = f"<em>{s}</em>"
        if t.get("strike"):
            s = f"<del>{s}</del>"
        if t.get("link"):
            s = f'<a href="{_xesc(t["link"])}">{s}</a>'
        out.append(s)
    return "".join(out)


def _img_name(rel):
    return os.path.basename(str(rel).replace("\\", "/"))


def _blocks_to_xhtml(blocks, base_dir, images, mmd_png=None):
    """块列表 → XHTML 片段；顺带收集需要打包进 EPUB 的图片。

    v3.30.19（MMD-2）：mmd_png 命中的图表直接以 PNG 内嵌（随 EPUB 打包）。
    """
    out = []
    for blk in blocks:
        k = blk["kind"]
        if k == "heading":
            lvl = max(1, min(6, blk["level"]))
            out.append(f"<h{lvl}>{_xinline(blk['text'])}</h{lvl}>")
        elif k == "para":
            out.append(f"<p>{_xinline(blk['text'])}</p>")
        elif k == "list":
            tag = "ol" if blk["ordered"] else "ul"
            out.append(f"<{tag}>")
            for it in blk["items"]:
                out.append(f"<li>{_xinline(it['text'])}</li>")
            out.append(f"</{tag}>")
        elif k == "quote":
            out.append(f"<blockquote>{_xinline(blk['text'])}</blockquote>")
        elif k == "hr":
            out.append("<hr/>")
        elif k == "table":
            out.append("<table><thead><tr>")
            for c in blk["header"]:
                out.append(f"<th>{_xinline(c)}</th>")
            out.append("</tr></thead><tbody>")
            for row in blk["rows"]:
                out.append("<tr>")
                for c in range(len(blk["header"])):
                    out.append(f"<td>{_xinline(row[c] if c < len(row) else '')}</td>")
                out.append("</tr>")
            out.append("</tbody></table>")
        elif k == "fndef":
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
            if lang == "mermaid" and mmd_png and mmd_png.get(code) \
                    and os.path.isfile(mmd_png[code]):
                # v3.30.19（MMD-2）：图表 PNG 随 EPUB 打包内嵌
                img_name = f"mmd-{len(images) + 1}.png"
                images[img_name] = mmd_png[code]
                out.append(f'<p><img src="images/{img_name}" alt="图表"/></p>')
                continue
            if lang in ("mermaid", "math"):
                label = "图表（Mermaid 源码）" if lang == "mermaid" else "公式（LaTeX 源码）"
                out.append(f'<p class="tip">［{label}］</p>')
            out.append(f"<pre><code>{_xesc(code)}</code></pre>")
        # 收集图片
        if k in ("para", "quote", "heading"):
            for t in parse_inline(blk.get("text") or ""):
                if t.get("image"):
                    rel = str(t["image"])
                    if rel.startswith(("http://", "https://", "data:")):
                        continue
                    path = rel if os.path.isabs(rel) else os.path.join(
                        base_dir or "", rel.replace("/", os.sep))
                    if os.path.isfile(path):
                        images.setdefault(_img_name(rel), path)
    return "\n".join(out)


def write_epub(md, out_path, base_dir="", title=None, author="mdEditor", mmd_png=None):
    """Markdown → EPUB 3。返回 (是否成功, 提示信息)。（MMD-2：mmd_png 见 write_docx）"""
    blocks = parse_blocks(md)
    # 按一级标题分章（无 h1 则整篇一章）
    chapters, cur = [], []
    for b in blocks:
        if b["kind"] == "heading" and b["level"] == 1 and cur:
            chapters.append(cur)
            cur = []
        cur.append(b)
    if cur:
        chapters.append(cur)
    if not chapters:
        chapters = [[]]

    title = title or "未命名文档"
    images = {}
    bodies, toc = [], []
    for i, ch in enumerate(chapters, 1):
        head = next((b["text"] for b in ch
                     if b["kind"] == "heading" and b["level"] == 1), None)
        if i == 1 and len(chapters) == 1:
            head = head or title
        cname = f"chapter{i}.xhtml"
        ctitle = plain_inline(head) if head else f"第 {i} 章"
        toc.append((ctitle, cname))
        body = _blocks_to_xhtml(ch, base_dir, images, mmd_png=mmd_png)
        bodies.append((cname, ctitle, body))

    book_id = "urn:uuid:" + str(uuid.uuid4())
    manifest, spine, nav_items = [], [], []
    manifest.append('<item id="css" href="style.css" media-type="text/css"/>')
    manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                    'properties="nav"/>')
    for i, (cname, ctitle, _) in enumerate(bodies, 1):
        manifest.append(f'<item id="c{i}" href="{cname}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
        nav_items.append(f'<li><a href="{cname}">{_xesc(ctitle)}</a></li>')
    for n, rel in enumerate(sorted(images), 1):
        ext = os.path.splitext(rel)[1].lower().lstrip(".") or "png"
        mt = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
              "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp"}.get(ext, "image/png")
        manifest.append(f'<item id="img{n}" href="images/{_xesc(rel)}" media-type="{mt}"/>')

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{book_id}</dc:identifier>
    <dc:title>{_xesc(title)}</dc:title>
    <dc:language>zh-CN</dc:language>
    <dc:creator>{_xesc(author)}</dc:creator>
    <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
    {chr(10).join('  ' + m for m in manifest)}
  </manifest>
  <spine>
    {chr(10).join('  ' + s for s in spine)}
  </spine>
</package>
"""
    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>目录</title><link rel="stylesheet" href="style.css"/></head>
<body><nav epub:type="toc" id="toc"><h1>目录</h1><ol>
{chr(10).join(nav_items)}
</ol></nav></body></html>
"""
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf"
    media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    try:
        with zipfile.ZipFile(out_path, "w") as z:
            # mimetype 必须第一个写入且不压缩
            z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                       compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/container.xml", container, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/nav.xhtml", nav, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/style.css", _EPUB_CSS, zipfile.ZIP_DEFLATED)
            for cname, ctitle, body in bodies:
                page = (f'<?xml version="1.0" encoding="utf-8"?>\n'
                        f'<html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">\n'
                        f'<head><title>{_xesc(ctitle)}</title>'
                        f'<link rel="stylesheet" href="style.css"/></head>\n'
                        f'<body>\n{body}\n</body></html>\n')
                z.writestr(f"OEBPS/{cname}", page, zipfile.ZIP_DEFLATED)
            for rel, path in images.items():
                z.write(path, f"OEBPS/images/{rel}")
    except Exception as e:
        return False, f"写入 EPUB 失败：{e}"
    return True, f"已导出 EPUB（{len(bodies)} 章节 / {len(images)} 图）· {out_path}"


# ---------------------------------------------------------------- PDF 书签

def add_pdf_bookmarks(pdf_path, headings):
    """按标题层级写入 PDF 书签。

    printToPdf 无法直接产出大纲，这里用「标题文本检索定位页码」的启发式方案：
    依次在各页文本中查找标题文字，命中即把书签指向该页并保持层级嵌套。
    返回 (写入条数, 说明)。
    """
    heads = [h for h in (headings or []) if str(h.get("text") or "").strip()]
    if not heads:
        return 0, "无标题，未写入书签"
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return 0, "缺少 pypdf，未写入 PDF 书签"

    try:
        reader = PdfReader(pdf_path)
        pages = []
        for p in reader.pages:
            try:
                pages.append(re.sub(r"\s+", "", p.extract_text() or ""))
            except Exception:
                pages.append("")
        writer = PdfWriter(clone_from=pdf_path)
        parents, added, cursor = {}, 0, 0
        for h in heads:
            key = re.sub(r"\s+", "", str(h.get("text") or ""))
            page_no = None
            for idx in list(range(cursor, len(pages))) + list(range(0, cursor)):
                if key and key in pages[idx]:
                    page_no = idx
                    break
            if page_no is None:
                continue
            cursor = page_no
            lvl = max(1, int(h.get("level") or 1))
            parent = None
            for pl in range(lvl - 1, 0, -1):
                if pl in parents:
                    parent = parents[pl]
                    break
            try:
                item = writer.add_outline_item(str(h.get("text")), page_no, parent=parent)
            except Exception as e:   # v3.29d（B9）：记录而非静默吞掉
                _log.debug("PDF 书签添加失败（%s）: %s", h.get("text"), e)
                continue
            parents[lvl] = item
            for k in [k for k in parents if k > lvl]:
                del parents[k]
            added += 1
        if added == 0:
            return 0, "未能在 PDF 中定位标题页码，未写入书签"
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return added, f"已写入 {added} 条书签"
    except Exception as e:
        return 0, f"PDF 书签写入失败：{e}"


# ---------------------------------------------------------------- pandoc 通道

def find_pandoc(configured=""):
    """返回可用的 pandoc 可执行文件路径（未找到返回空串）。"""
    if configured:
        p = configured.strip().strip('"')
        if os.path.isfile(p):
            return p
        w = shutil.which(p)
        if w:
            return w
        return ""
    return shutil.which("pandoc") or ""


def pandoc_convert(pandoc, md, out_path, to, base_dir=""):
    """调用外部 pandoc 转换（docx / epub）。返回 (是否成功, 说明)。"""
    import tempfile
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".md", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(md or "")
        cmd = [pandoc, tmp, "-o", out_path, "--from", "gfm+tex_math_dollars",
               "--resource-path", base_dir or ".", "--standalone"]
        if to == "epub":
            cmd += ["--toc", "--toc-depth=3"]
        else:
            cmd += ["--toc", "--toc-depth=3"]
        r = subprocess.run(cmd, capture_output=True, timeout=180)
        if r.returncode != 0:
            return False, (r.stderr or b"").decode("utf-8", "replace")[-300:]
        return True, f"已用 pandoc 导出 · {out_path}"
    except Exception as e:
        return False, f"pandoc 调用失败：{e}"
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
