# -*- coding: utf-8 -*-
"""v3.48.31 EXPAND-DIFF 验证：AI 扩写场景的分层差异质量 + 短行行为不变。

结果写 _expand_diff_check.out.txt（UTF-8），绕开 shell coreutils 损坏坑。
"""
import os
import sys
import time

sys.path.insert(0, r'E:\WorkBuddy\md-editor\src')

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "_expand_diff_check.out.txt")
_f = open(OUT, "w", encoding="utf-8")


def P(*a):
    _f.write(" ".join(str(x) for x in a) + "\n")


import diffmerge as D  # noqa: E402

# 回归语料取自 tests/_fixture_expand.py（用户 2026-10-26 实测提供的扩写样本，
# 一字不得改），与 _probe_expand_merge.py 共用同一基线
from _fixture_expand import AI as B, ORIG as A  # noqa: E402

fails = []


def check(name, cond, detail=""):
    P(("PASS " if cond else "FAIL ") + name + ("  | " + str(detail) if detail else ""))
    if not cond:
        fails.append(name)


P("=== E1 长段落分层差异（用户实证样本） ===")
P("A=%d 字, B=%d 字, WORD_MAX=%d" % (len(A), len(B), D.WORD_MAX))
P("[旧引擎] word_ops -> %s" % ("None(整行着色)" if D.word_ops(A, B) is None
                               else D.word_ops(A, B)))
t0 = time.time()
ops = D.word_ops_deep(A, B)
cost = (time.time() - t0) * 1000
check("E1_DEEP_NOT_NONE", ops is not None)
P("耗时 %.1f ms" % cost)
check("E1_COST_OK", cost < 300, "%.1fms" % cost)

# 覆盖率与不变量
check("E1_COVER_A", ops[0][1] == 0 and ops[-1][2] == len(A), (ops[0], ops[-1]))
check("E1_COVER_B", ops[0][3] == 0 and ops[-1][4] == len(B), (ops[0], ops[-1]))
mono = all(ops[i][2] == ops[i + 1][1] and ops[i][4] == ops[i + 1][3]
           for i in range(len(ops) - 1))
check("E1_MONOTONIC", mono, "相邻段首尾相接")

ndiff = sum(1 for t, *_ in ops if t != "equal")
frag = [o for o in ops if o[0] != "equal" and max(o[2] - o[1], o[4] - o[3]) <= 2]
P("差异段数 = %d / 总段数 = %d；≤2 字碎片数 = %d" % (ndiff, len(ops), len(frag)))
check("E1_NOT_WHOLE_LINE", ndiff > 1 and len(ops) > 1, "不再是整段一块")
check("E1_FEW_FRAGMENTS", len(frag) <= 2, len(frag))

# 着色覆盖率（左栏被标红字数 / 全文字数）—— 旧行为 100%
red = sum(o[2] - o[1] for o in ops if o[0] != "equal")
green = sum(o[4] - o[3] for o in ops if o[0] != "equal")
P("左栏着色 %d/%d = %.1f%%；右栏着色 %d/%d = %.1f%%"
  % (red, len(A), 100.0 * red / len(A), green, len(B), 100.0 * green / len(B)))
check("E1_LEFT_NOT_ALL_RED", red < len(A) * 0.75, "%.1f%%" % (100.0 * red / len(A)))

P("")
P("--- 差异明细（左栏红 = A 片段 / 右栏绿 = B 片段） ---")
for tag, i1, i2, j1, j2 in ops:
    if tag == "equal":
        continue
    P("  %-7s [-]%r  →  [+]%r" % (tag, A[i1:i2], B[j1:j2]))

P("")
P("--- 还原着色后的两栏（【】内为着色） ---")
la, lb = [], []
for tag, i1, i2, j1, j2 in ops:
    if tag == "equal":
        la.append(A[i1:i2])
        lb.append(B[j1:j2])
    else:
        la.append("【" + A[i1:i2] + "】")
        lb.append("【" + B[j1:j2] + "】")
P("左栏：%s" % "".join(la))
P("")
P("右栏：%s" % "".join(lb))

# ---- E2 短行行为不变（探针 D2 依赖） ----
P("")
P("=== E2 短行 / 护栏行为不变 ===")
check("E2_SAME_NONE", D.word_ops_deep("abc", "abc") is None)
check("E2_SHORT_DELEGATE", D.word_ops_deep("The quick brown fox", "The quick red fox")
      == D.word_ops("The quick brown fox", "The quick red fox"))
check("E2_CJK_SHORT", D.word_ops_deep("黑发不知勤学早", "白首方悔读书迟") is not None)
huge = "词" * (D.SEG_MAX + 1)
check("E2_SEG_GUARD", D.word_ops_deep(huge, huge + "尾") is None)

# ---- E3 纯删除 / 纯插入 / 整段重写 ----
P("")
P("=== E3 其它长文本形态 ===")
o_del = D.word_ops_deep(A + "额外结尾句。", A)
check("E3_LONG_DELETE", o_del is not None and any(t == "delete" for t, *_ in o_del),
      o_del)
o_ins = D.word_ops_deep(A, A + "额外结尾句。")
check("E3_LONG_INSERT", o_ins is not None and any(t == "insert" for t, *_ in o_ins),
      o_ins)
o_rw = D.word_ops_deep("甲" * 400, "乙" * 400)
check("E3_FULL_REWRITE", o_rw is not None and len(o_rw) == 1
      and o_rw[0][0] == "replace", o_rw)

# ---- E4 性能：大段落不卡 ----
P("")
P("=== E4 性能 ===")
big_a = "。".join("第%d句的内容包含若干汉字用于测试性能表现" % i for i in range(120))
big_b = big_a.replace("汉字", "方块字")
t0 = time.time()
o_big = D.word_ops_deep(big_a, big_b)
c2 = (time.time() - t0) * 1000
P("大段落 A=%d B=%d → %.1f ms, 段数=%d" % (len(big_a), len(big_b), c2,
                                          len(o_big) if o_big else 0))
check("E4_BIG_COST", c2 < 2000, "%.1fms" % c2)
check("E4_BIG_OK", o_big is not None and len(o_big) > 1)

P("")
P("FAIL_COUNT=%d" % len(fails))
P("VERDICT=" + ("PASSED" if not fails else "FAILED " + ",".join(fails)))
_f.flush()
_f.close()
print("OK", OUT)
