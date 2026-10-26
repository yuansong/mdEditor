# -*- coding: utf-8 -*-
"""v3.48.31 E2E 自测：AI 扩写 → 片段替换对比 → 人工选中合并（多轮）。

覆盖 M1~M9：
  M1 句级视图：原文/扩写各大段 → 行流按句拆开，差异行带精细化 opcodes
  M2 结果默认 = AI 回复全文（不含多余换行 —— 句级重建正确性）
  M3 选中右栏整句合并 → 结果不变（默认已是 B），改动行数为 0
  M4 选中左栏（原文）某句合并 → 结果该句被替换为原文句，其余保持 AI 文本
  M5 多并不同位置重复合并（3 轮）→ 叠加正确、非选区文字不受影响
  M6 回采：再把同一位置合并回 AI 文本 → 能回到 AI 全文（往返一致）
  M7 随机 20 轮抽查不变量：所选片段必在结果中；结构不变量保持
  M8 全部采用左 = 原文；全部采用右 = AI 回复（写回无多余换行）
  M9 history：反复切换（左→右→左）结果恒定，且不产生累积性失真

不变量（每轮检查）：
  · 所选片段 guard 必出现在结果中
  · 结果不得凭空产生连续换行 "\\n\\n"
  · 结果长度处于 [min(len A,len B), max] 合理区间（合并只做片段替换）
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

import diffmerge as D  # noqa: E402
from ai_pane import AIFragmentDialog  # noqa: E402

OUT = open(os.path.join(HERE, "_probe_expand_merge.txt"), "w",
           encoding="utf-8")
fails = []


def P(*a):
    OUT.write(" ".join(str(x) for x in a) + "\n")


def check(name, cond, detail=""):
    P(("PASS " if cond else "FAIL ") + name +
      ("  | " + str(detail) if detail else ""))
    if not cond:
        fails.append(name)


# 回归语料取自 tests/_fixture_expand.py（用户 2026-10-26 实测提供的扩写样本，
# 一字不得改），两处探针共用同一基线
from _fixture_expand import AI, ORIG  # noqa: E402


def invariants(tag, res):
    """结构不变量：无凭空双换行；长度合理。"""
    ok = True
    if "\n\n" in res:
        ok = False
        P("       [%s] 出现连续换行" % tag)
    if not (min(len(ORIG), len(AI)) - 5 <= len(res) <= max(len(ORIG), len(AI)) + 5):
        ok = False
        P("       [%s] 长度越界 len=%d" % (tag, len(res)))
    return ok


def single_region(new, old):
    """new 相对 old 的差异是否为**单一连续区间**（一次片段合并应有的形态）。

    注意：不能用「公共前后缀之和 ≈ 长度」判定（两侧长度不等时天然不成立），
    也不能用 difflib opcode 数量判定（部分相似会产生多段，实测 AI 405→结果
    351 时 difflib 给出多段）。**正确判据是按行核验**：一次合并只应让被选中
    那一句改变，其余行的输出文本必须与合并前逐字相同（见 M4_ROWWISE）。"""
    import difflib
    ops = difflib.SequenceMatcher(a=new, b=old, autojunk=False).get_opcodes()
    idx = [i for i, o in enumerate(ops) if o[0] != "equal"]
    if not idx:
        return True
    return idx[-1] - idx[0] + 1 == len(idx) and len(idx) <= 2


def row_outputs(dlg):
    """结果框按行流的各行输出文本（句级视图下同行的句间无分隔符）。"""
    outs = []
    for r in dlg._mp_rows:
        t, emits, _m = dlg._mp_row_output(r)
        if emits:
            outs.append(t)
    return outs


def lcp(a, b):
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return i


def lcs(a, b):
    i = 0
    while i < min(len(a), len(b)) and a[len(a) - 1 - i] == b[len(b) - 1 - i]:
        i += 1
    return i


def select_row_block(pane, row_idx, i1, i2):
    """在第 row_idx 个块内选中 [i1, i2)。"""
    blk = pane.document().findBlockByNumber(row_idx)
    cur = QTextCursor(pane.document())
    cur.setPosition(blk.position() + min(i1, blk.length() - 1))
    cur.setPosition(blk.position() + min(i2, blk.length() - 1),
                    QTextCursor.KeepAnchor)
    pane.setTextCursor(cur)


dlg = AIFragmentDialog(None, None, orig_text=ORIG, reply_text=AI)

# ---------- M1 句级视图 ----------
rows = dlg._mp_rows
diff_rows = [r for r in rows if D.TwoPaneMergeMixin._mp_adoptable(r)]
fine = [r for r in diff_rows if r["lw"]]
# v3.48.32：句级视图（mp_sent_view）默认关闭 —— 用户实测要求「对比框不要
# 手动按句号换行显示」。行流改回按原文行，精细化差异由行内 word_ops_deep
# 给出（见 M1_FINE_OPS）。断言由「≥4 行（各按句拆）」改为「按原文行显示」。
check("M1_SENT_SPLIT", len(rows) == 1,
      "行流 %d 行（按原文行显示，未按句号人工折行）" % len(rows))
check("M1_FINE_OPS", len(fine) >= 1,
      "带词级 opcodes 的差异行 %d 个" % len(fine))
check("M1_NO_WHOLE_LINE_COLOR", all(
    any(op[0] == "equal" for op in r["lw"]) for r in fine),
    "每个差异行都存在未被标色的相同文字（不再是整行通红）")

# ---------- M2 默认结果 == AI 全文（无多余换行） ----------
res0 = dlg.get_result_text()
check("M2_RESULT_IS_AI", res0 == AI, repr(res0[:60]))
check("M2_NO_EXTRA_NL", "\n" not in res0, "无多余换行")

# ---------- M3 选中右栏整句合并（默认已是 B） ----------
b_rows = [(i, r) for i, r in enumerate(rows)
          if r["rk"] == "add" and len(r["rt"]) > 8]
n3 = 0
if b_rows:
    i, r = b_rows[0]
    select_row_block(dlg.pane_b, i, 0, len(r["rt"]))
    spans = dlg._mp_frag_spans(dlg.pane_b, "B")
    n3 = dlg._mp_frag_merge(spans, "B") if spans else -1
    check("M3_MERGE_B_NOOP", spans is not None and n3 == 0,
          "spans=%s changed=%s（已是 AI 文本，无需改动）" % (spans, n3))
    check("M3_RESULT_UNCHANGED", dlg.get_result_text() == AI)

# ---------- M4 选中左栏某句合并 → 该句回到原文 ----------
a_rows = [(i, r) for i, r in enumerate(rows)
          if r["lk"] == "del" and len(r["lt"]) > 8]
# v3.48.32：同上，行级视图下原文只有 1 个差异行（整段 replace），
# 不再按句拆成多个差异句 → 阈值 ≥2 改为 ≥1。
check("M4_HAS_A_ROWS", len(a_rows) >= 1, "原文差异行 %d 个" % len(a_rows))
merged_target = None
if a_rows:
    # 行级判据（真正的不变量）：只有被选中那一句被替换，其余句逐字未动
    base_rows = row_outputs(dlg)
    check("M4_BASELINE_ROWS", "".join(base_rows) == AI,
          "合并前行输出拼接 == AI 全文")

    before_rows = row_outputs(dlg)
    i, r = a_rows[0]
    frag = r["lt"]
    select_row_block(dlg.pane_a, i, 0, len(frag))
    spans = dlg._mp_frag_spans(dlg.pane_a, "A")
    n4 = dlg._mp_frag_merge(spans, "A") if spans else -1
    res4 = dlg.get_result_text()
    after_rows = row_outputs(dlg)
    check("M4_CHANGED", n4 >= 1, "changed=%s" % n4)
    check("M4_FRAG_IN", frag in res4, repr(frag[:24]))
    check("M4_NO_EXTRA_NL", "\n" not in res4)
    check("M4_STRUCT", invariants("M4", res4))
    expect = list(before_rows)
    if 0 <= i < len(expect):
        expect[i] = frag
    check("M4_ROWWISE", after_rows == expect,
          "仅第 %d 句被替换：%s" % (i, after_rows == expect))
    check("M4_RESULT_EQ_ROWS", "".join(after_rows) == res4,
          "结果文本 == 各行输出按序拼接（无多余换行）")
    others = [k for k in range(len(after_rows)) if k != i]
    check("M4_OTHERS_INTACT",
          all(after_rows[k] == before_rows[k] for k in others
              if k < len(before_rows)),
          "未选中句逐字未动")
    merged_target = (i, frag)

# ---------- M5 多轮叠加 ----------
if a_rows and merged_target:
    for rnd in range(1, 4):
        i, r = a_rows[rnd % len(a_rows)]
        frag = r["lt"]
        select_row_block(dlg.pane_a, i, 0, len(frag))
        spans = dlg._mp_frag_spans(dlg.pane_a, "A")
        if not spans:
            continue
        before = dlg.get_result_text()
        n = dlg._mp_frag_merge(spans, "A")
        after = dlg.get_result_text()
        ok = invariants("M5.%d" % rnd, after)
        if n == 0:
            ok = ok and frag in before        # 已在结果中 → 幂等
        else:
            ok = ok and frag in after
        check("M5_ROUND_%d" % rnd, ok and frag in after,
              "changed=%s len=%d" % (n, len(after)))

# ---------- M6 回采（make back to AI） ----------
dlg2 = AIFragmentDialog(None, None, orig_text=ORIG, reply_text=AI)
rows2 = dlg2._mp_rows
a6 = [(i, r) for i, r in enumerate(rows2)
      if r["lk"] == "del" and len(r["lt"]) > 8]
if a6:
    i, r = a6[0]
    frag = r["lt"]
    select_row_block(dlg2.pane_a, i, 0, len(frag))
    sp = dlg2._mp_frag_spans(dlg2.pane_a, "A")
    dlg2._mp_frag_merge(sp, "A")
    mid = dlg2.get_result_text()
    # 回采：在结果里把该段再换成 AI 侧（右键「选中采用右」语义）
    sel_in_res = mid.find(frag)
    if sel_in_res >= 0:
        cur = QTextCursor(dlg2.pane_merge.document())
        cur.setPosition(sel_in_res)
        cur.setPosition(sel_in_res + len(frag), QTextCursor.KeepAnchor)
        dlg2.pane_merge.setTextCursor(cur)
        spansR = dlg2._mp_result_spans()
        if spansR:
            dlg2._mp_sel_adopt(spansR, "R", "B")
        res6 = dlg2.get_result_text()
        check("M6_ROUNDTRIP", res6 == AI,
              "回到 AI 全文：%s" % (res6 == AI))
    else:
        check("M6_ROUNDTRIP", False, "合并片段未落位")

# ---------- M7 随机 20 轮抽查 ----------
import random  # noqa: E402

random.seed(20261026)
bad = []
for step in range(20):
    d = AIFragmentDialog(None, None, orig_text=ORIG, reply_text=AI)
    rr = d._mp_rows
    cand = [(i, r) for i, r in enumerate(rr)
            if (r["lk"] == "del" or r["rk"] == "add") and len(r["lt"] or r["rt"]) > 8]
    if not cand:
        break
    i, r = random.choice(cand)
    side = "A" if r["lk"] == "del" else "B"
    pane = d.pane_a if side == "A" else d.pane_b
    frag = r["lt"] if side == "A" else r["rt"]
    select_row_block(pane, i, 0, len(frag))
    sp = d._mp_frag_spans(pane, side)
    if not sp:
        bad.append("step%d 无 span" % step)
        continue
    n = d._mp_frag_merge(sp, side)
    res = d.get_result_text()
    if frag not in res:
        bad.append("step%d 片段丢失" % step)
    if "\n\n" in res or "\n" in res:
        bad.append("step%d 出现换行" % step)
check("M7_RANDOM_20", not bad, bad[:5] or "20 轮全部通过")

# ---------- M8 全部采用左 / 右 ----------
d = AIFragmentDialog(None, None, orig_text=ORIG, reply_text=AI)
d._mp_adopt("A", d._mp_all_rows())
resA = d.get_result_text()
check("M8_ALL_LEFT", resA.replace("\n", "") == ORIG.replace("\n", ""),
      repr(resA[:40]))
d._mp_adopt("B", d._mp_all_rows())
resB = d.get_result_text()
check("M8_ALL_RIGHT", resB.replace("\n", "") == AI.replace("\n", ""),
      repr(resB[:40]))

# ---------- M9 反复切换恒定 ----------
for _ in range(3):
    d._mp_adopt("A", d._mp_all_rows())
    d._mp_adopt("B", d._mp_all_rows())
res9 = d.get_result_text()
check("M9_TOGGLE_STABLE", res9.replace("\n", "") == AI.replace("\n", ""),
      repr(res9[:40]))

P("")
P("FAIL_COUNT=%d" % len(fails))
P("VERDICT=" + ("PASSED" if not fails else "FAILED " + ",".join(fails)))
OUT.flush()
OUT.close()
