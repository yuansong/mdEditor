# -*- coding: utf-8 -*-
"""去重：清单内 FMT-5 被误插两处（§2.0 行内格式表 + §3.1 各块型遗留表），
保留 §2.0 的那一条，删除 §3.1 的副本（含「反而再套一层」字样）。"""
import io

P = r"E:\WorkBuddy\md-editor\docs\未实现BUG与优化清单-v3.30.11.md"
lines = io.open(P, encoding="utf-8").read().split("\n")
kept = []
removed = 0
for ln in lines:
    if ln.startswith("| **FMT-5**") and "反而再套一层" in ln:
        removed += 1
        continue
    kept.append(ln)
io.open(P, "w", encoding="utf-8").write("\n".join(kept))
print("removed=%d" % removed)
