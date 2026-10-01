# -*- coding: utf-8 -*-
"""删除 2026-09-29.md 中重复的 FMT-5 / HDR-1 段（63~74 行那份）。"""
import io, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                 "WorkBuddy", "2026-09-19-18-04-05", ".workbuddy", "memory",
                 "2026-09-29.md")
P = os.path.normpath(P)
s = io.open(P, encoding="utf-8").read()
marker = "## FMT-5（用户实测）：粗斜组合上按斜体不取消（`***C***` 再按 I 应回 `**C**`）"
first = s.find(marker)
second = s.find(marker, first + 1)
if second < 0:
    print("NO_DUP")
else:
    tail = "\n## 打包 dist55"
    t = s.find(tail, second)
    if t < 0:
        print("NO_TAIL_ANCHOR")
    else:
        s = s[:second] + s[t:]
        io.open(P, "w", encoding="utf-8").write(s)
        print("DEDUP_OK len=%d" % len(s))
