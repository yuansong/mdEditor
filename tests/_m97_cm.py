import os
import io, sys
from markdown_it import MarkdownIt
md = MarkdownIt("default")
cases = [
    ("A-jiaocuo-S5", "# **~~已加粗**和普通~~"),
    ("B-nested-std", "# ~~**已加粗**和普通~~"),
    ("C-jiaocuo-cb", "# ~~**C~~**"),
    ("D-nested-std", "# ~~**C**~~"),
    ("E-jiaocuo-BoldStrike", "# **~~C~~**"),
]
lines = []
for name, src in cases:
    html = md.render(src)
    lines.append("%s => %s" % (name, html.strip()))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m97_cm2.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("OK")