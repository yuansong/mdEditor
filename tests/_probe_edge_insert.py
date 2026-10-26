# -*- coding: utf-8 -*-
"""v3.48.31 探针（EDGE-INS）：「选中左边整段合并」时，目标侧行尾多出的插入段
未被清理 —— 表现为「选择左边作为合并内容无效」。

用户实证样本：
  左 A = 这就是我的中国——…心灵归属的温暖
  右 B = 这就是我的中国——…心灵归属的温暖港湾。
选中 A 全文合并 → 期望结果 == A（多余「港湾。」被清理），实际仍为 B。
"""
import os
import sys

os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("MDEDITOR_SKIP_DRAFT", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtGui import QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from ai_pane import AIFragmentDialog  # noqa: E402

OUT = open(os.path.join(HERE, "_probe_edge_insert.txt"), "w", encoding="utf-8")
fails = []


def P(*a):
    OUT.write(" ".join(str(x) for x in a) + "\n")


def check(name, cond, detail=""):
    P(("PASS " if cond else "FAIL ") + name +
      ("  | " + str(detail) if detail else ""))
    if not cond:
        fails.append(name)


A = ("这就是我的中国——一个充满故事、激荡风云、正迈向伟大复兴的文化高地，"
     "也是每一个中国人心灵归属的温暖")
B = A + "港湾。"

P("A(%d) = %s" % (len(A), A))
P("B(%d) = %s" % (len(B), B))


def select_block(pane, row_idx, i1, i2):
    blk = pane.document().findBlockByNumber(row_idx)
    cur = QTextCursor(pane.document())
    cur.setPosition(blk.position() + min(i1, max(0, blk.length() - 1)))
    cur.setPosition(blk.position() + min(i2, max(0, blk.length() - 1)),
                    QTextCursor.KeepAnchor)
    pane.setTextCursor(cur)


def fresh():
    d = AIFragmentDialog(None, None, orig_text=A, reply_text=B)
    return d


# ---------- T1：选中左边全文 → 结果应等于 A（清理多余尾巴） ----------
d = fresh()
rows = d._mp_rows
P("行流 %d 行" % len(rows))
check("T1_BASELINE", d.get_result_text() == B, repr(d.get_result_text()[:60]))
ri = 0
select_block(d.pane_a, ri, 0, len(A))
spans = d._mp_frag_spans(d.pane_a, "A")
P("spans = %s" % (spans,))
if spans:
    n = d._mp_frag_merge(spans, "A")
    res = d.get_result_text()
    P("changed=%s result=%s" % (n, res))
    check("T1_MERGE_ALL_A", res == A,
          "期望 == A（多余「港湾。」被清理），实际=%r" % res[-8:])
else:
    check("T1_MERGE_ALL_A", False, "未取到选区 spans")

# ---------- T2：选中左边部分（非到行尾）→ 行尾插入段应保留 ----------
d2 = fresh()
mid_a, mid_b = 10, 20
select_block(d2.pane_a, 0, mid_a, mid_b)
sp2 = d2._mp_frag_spans(d2.pane_a, "A")
if sp2:
    n2 = d2._mp_frag_merge(sp2, "A")
    res2 = d2.get_result_text()
    # 部分合并不得连带删掉 B 行尾多出的「港湾。」
    check("T2_PARTIAL_KEEPS_TAIL", res2.endswith("港湾。"),
          "行尾多余内容应保留，实际=%r" % res2[-10:])
    # 且必须与 B 等长（替换等长片段）
    check("T2_PARTIAL_LEN", len(res2) == len(B),
          "len=%d 期望=%d" % (len(res2), len(B)))
else:
    check("T2_PARTIAL_KEEPS_TAIL", False, "未取到选区 spans")

# ---------- T3：选中右边全文合并（默认已是 B）→ 无改动 ----------
d3 = fresh()
select_block(d3.pane_b, 0, 0, len(B))
sp3 = d3._mp_frag_spans(d3.pane_b, "B")
n3 = d3._mp_frag_merge(sp3, "B") if sp3 else -1
check("T3_MERGE_B_NOOP", n3 == 0 and d3.get_result_text() == B,
      "changed=%s" % n3)

# ---------- T4：右键「全部采用左」→ 结果 == A ----------
d4 = fresh()
d4._mp_adopt("A", d4._mp_all_rows())
res4 = d4.get_result_text()
check("T4_ALL_LEFT", res4 == A, repr(res4[-10:]))

# ---------- T5：反向场景（A 比 B 多尾巴）选中 B 全文 → 结果 == B ----------
A2 = A + "港湾。"
B2 = A
d5 = AIFragmentDialog(None, None, orig_text=A2, reply_text=B2)
select_block(d5.pane_b, 0, 0, len(B2))
sp5 = d5._mp_frag_spans(d5.pane_b, "B")
if sp5:
    n5 = d5._mp_frag_merge(sp5, "B")
    res5 = d5.get_result_text()
    check("T5_MERGE_ALL_B", res5 == B2,
          "期望 == B（清理 A 多出的尾巴），实际=%r" % res5[-8:])
else:
    check("T5_MERGE_ALL_B", False, "未取到选区 spans")

P("")
P("FAIL_COUNT=%d" % len(fails))
P("VERDICT=" + ("PASSED" if not fails else "FAILED " + ",".join(fails)))
OUT.flush()
OUT.close()
