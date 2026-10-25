import os
# -*- coding: utf-8 -*-
import hashlib, os, io

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(root, "src", "editor.html")
dst = os.path.join(root, "dist53", "mdEditor", "_internal", "editor.html")
out = []

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

s1, s2 = sha(src), sha(dst)
out.append("SHA256 src = " + s1)
out.append("SHA256 dst = " + s2)
out.append("SHA256 match = " + str(s1 == s2))

with io.open(dst, "r", encoding="utf-8") as f:
    content = f.read()
feats = ["lineAwarePlain", "wysClickToRaw", "wysHasInlineRich", "copyTextToClipboard",
         "requestImgModeSwitch", "__imgStatusLabel", "_embed_local_images" in "x",
         "不支持跨行", "已阻止写入", "__rzPick", "TBLADD_ZONE"]
for fstr in ["lineAwarePlain", "wysClickToRaw", "wysHasInlineRich", "copyTextToClipboard",
             "requestImgModeSwitch", "__imgStatusLabel", "不支持跨行",
             "已阻止写入以免破坏围栏结构", "__rzPick", "TBLADD_ZONE", "max-height: 320px"]:
    out.append("feat %-30s hits=%d" % (fstr, content.count(fstr)))

for name in ["editor.html", "katex", "mermaid", "translations"]:
    p = os.path.join(root, "dist53", "mdEditor", "_internal", name)
    out.append("asset %-14s exists=%s" % (name, os.path.exists(p)))

with io.open(os.path.join(root, "tests", "_verify53.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
