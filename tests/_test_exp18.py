# -*- coding: utf-8 -*-
"""v3.30.18e：导出批次快速单测（FN-2 / DL-5 / IMG-2 嵌入逻辑）。"""
import io, os, sys, tempfile

sys.path.insert(0, r"E:\WorkBuddy\md-editor\src")
import exporters as ex

out = []
def check(name, cond, extra=""):
    out.append(("PASS " if cond else "FAIL ") + name + " | " + str(extra)[:200])

# 1. parse_blocks：fndef / deflist
md = "# T\n\n正文[^1]继续[^note]\n\n脚注[^2]引用\n\n[^1]: 说明一\n[^note]: 说明二\n\n术语\n: 定义A\n: 定义B\n"
blocks = ex.parse_blocks(md)
kinds = [b["kind"] for b in blocks]
check("fndef 块识别", kinds.count("fndef") == 2, kinds)
dl = [b for b in blocks if b["kind"] == "deflist"]
check("deflist 块识别", len(dl) == 1 and dl[0]["term"] == "术语"
      and dl[0]["defs"] == ["定义A", "定义B"], dl)

# 2. parse_inline：fnref token
toks = ex.parse_inline("前文[^1]后文")
check("fnref token", any(t.get("fnref") == "1" for t in toks), toks)
check("fnref 不再按字面", not any("[^1]" in (t.get("text") or "") for t in toks), toks)
check("plain_inline 降级 [1]", "[1]" in ex.plain_inline("前文[^1]后文"), ex.plain_inline("前文[^1]后文"))

# 3. DOCX 导出（含 fnref 上标 + fndef + deflist）
tmp = tempfile.mkdtemp()
docx_path = os.path.join(tmp, "t.docx")
ok, msg = ex.write_docx(md, docx_path, base_dir=tmp)
check("docx 导出成功", ok, msg)
if ok:
    import docx as _docx
    d = _docx.Document(docx_path)
    texts = [p.text for p in d.paragraphs]
    joined = "\n".join(texts)
    check("docx 脚注引用上标 [1]", "[1]" in joined and "[^1]" not in joined, texts)
    check("docx 脚注定义段", "[note] 说明二" in joined, texts)
    check("docx 术语加粗段", "术语" in joined and ": 定义A" not in joined and "定义A" in joined, texts)

# 4. EPUB 导出
epub_path = os.path.join(tmp, "t.epub")
ok2, msg2 = ex.write_epub(md, epub_path, base_dir=tmp)
check("epub 导出成功", ok2, msg2)
if ok2:
    import zipfile
    with zipfile.ZipFile(epub_path) as z:
        body = z.read("OEBPS/chapter1.xhtml").decode("utf-8")
    check("epub fnref sup 链接", '<sup class="fnref"><a href="#fn-1">[1]</a></sup>' in body, body[:200])
    check("epub fndef 锚点", 'id="fn-note"' in body and "说明二" in body, None)
    check("epub dl/dt/dd", "<dl>" in body and "<dt>" in body and "<dd>定义A</dd>" in body, None)
    check("epub 无字面 [^", "[^" not in body, None)

with io.open(r"E:\WorkBuddy\md-editor\tests\_exp18.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
