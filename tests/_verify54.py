# -*- coding: utf-8 -*-
"""dist54 三重校验（第一重：SHA256 + 特征串 + 资产）"""
import hashlib, os, io

root = r"E:\WorkBuddy\md-editor"
src = os.path.join(root, "src", "editor.html")
dst = os.path.join(root, "dist54", "mdEditor", "_internal", "editor.html")
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

# v3.31.1 新增特征：必须命中
out.append("--- v3.31.1 feature strings (expect >=1) ---")
for fstr in ["isSepRow", "tblOpen", "管道表格分组补全",
             "Math.min(it.children.length - 1, +sub[id])"]:
    out.append("feat %-45s hits=%d" % (fstr, content.count(fstr)))

# v3.31.1 移除项：必须为 0
out.append("--- removed strings (expect 0) ---")
for fstr in ["标题 7", "case 'h7'", "#{1,7}", ".raw-edit.t-h7"]:
    out.append("gone %-45s hits=%d" % (fstr, content.count(fstr)))

# 既有稳定特征抽查
out.append("--- legacy spot checks ---")
for fstr in ["TBLADD_ZONE", "__lazyFlushAll", "reorderSections", "find-hit"]:
    out.append("feat %-45s hits=%d" % (fstr, content.count(fstr)))

for name in ["editor.html", "katex", "mermaid", "translations"]:
    p = os.path.join(root, "dist54", "mdEditor", "_internal", name)
    out.append("asset %-14s exists=%s" % (name, os.path.exists(p)))

with io.open(os.path.join(root, "tests", "_verify54.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
