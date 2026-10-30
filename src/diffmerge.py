# -*- coding: utf-8 -*-
"""v3.48.28（LINK-3）：统一差异计算引擎 + 冲突字级着色 / 三框联动 / 选区合并。

三处功能复用同一套高精度差异与合并算法：
  · dialogs.DiffDialog       —— 历史版本对比（只读，单栏 / 双栏）
  · dialogs.MergeDialog      —— 历史版本合并
  · ai_pane.AIFragmentDialog —— AI 片段替换 / 整篇 AI 优化预览

v3.48.28 按用户实测反馈定稿的显示与交互语义：

  【差异显示】仅对**有差异的文字**加背景色，相同文字一律无底色：
    · 左栏差异文字红底、右栏绿底（配对行只给词级 span 上色，整行不铺
      底色；无词级 opcodes（超长 / 整行差异 / 空对侧）时整行即差异
      文字，退整行底色）；差异行保留左侧 3px 色条便于快速定位；
    · 下方合并结果：**只给冲突文字上色**（与另一侧逐字比较，不同处
      黄底 = 未合并冲突；两侧可见文本一致处不着色）；合并写入的内容
      按**来源方**着色（来自左侧红底 / 来自右侧绿底，字符级精确到
      片段）；整行被完整合并为某一侧时整行着该侧色。
  【三框联动】左 / 右对比栏与下方合并结果框：
    · 选中联动 —— 任一对比栏选中文字，另外两框中对应内容浅蓝底同步
      高亮（行流 + 字符级 diff 对齐映射）；
    · 滚动联动 —— 按首个可见行（块号）同步，三框行流一一对应。
  【合并交互】默认只合并用户选中的内容（可跨行）；「全部采用左 / 右」
    收敛进右键菜单（按钮移除）：
    · 对比栏选中文字后 **双击** 或 **右键「合并所选内容」** —— 经字符级
      diff（map_range）把所选区间对齐映射到结果文本原位替换，行内其余
      文字与其他行不动；
    · 右键「全部采用左（A）/ 全部采用右（B）」= 所有差异行整行采用该侧
      （整行着该侧来源色）；
    · 双击修复（v3.48.28）：无选区双击交回 Qt 执行默认「双击选词」
      （旧版恒吞事件导致双击选词失效）；双击合并无实际改动时状态行
      给出反馈，不再静默无响应；
    · 合并可反复叠加（基于最新结果重新对齐）。
  【界面】无导航按钮、无「恢复默认」；全部采用收进右键菜单——凡选中
    即合并，一种入口一种语义；仅保留状态行与子类功能性按钮
    （应用 / 另存为 / 取消 / 确认替换等）。

  ---------- 纯逻辑层（无 Qt 依赖，可直接单测） ----------
  line_key_raw(line)          原始行键（不做归一）
  line_key_md(line)           Markdown 容错行键（剥离标记与空白，可见文本归一）
  word_ops(old_ln, new_ln)    配对行字符级 opcodes（WORD_MAX 护栏，超长退整行）
  map_range(ops, i1, i2)      字符区间跨 opcodes 对齐映射（选区合并核心）
  build_hunks(a, b, key_fn)   行级 SequenceMatcher → hunk 流
  build_rows(hunks)           hunk → 左右对齐行流（replace 块 1:1 行配对）

  ---------- 视图层（TwoPaneMergeMixin） ----------
  每行一个渲染块（anchorAt 反查行号，块号恰与行流一致）；选区合并按行
  原位替换结果框（复用 v3.48.3 游标复位算法，手工编辑不受影响）。

行输出规则（merge 语义的关键细节）：
  · equal 行恒输出（即使该行是空行 —— 保空白行）；
  · 差异行默认输出 mp_default_side（恒 B / 最新）侧文本，仅当该侧在
    本行**真实存在**（kind != spacer）：对 (del, spacer) 行默认 = 删除
    该行（不残留空行）；override 存在时按 override 输出。
"""
import difflib
import re

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QTextCursor, QTextCharFormat
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSplitter,
                               QTextBrowser, QTextEdit, QVBoxLayout)

from mdrender import md_to_plain
from i18n import T  # v3.49.1（FIX-T）：国际化取词 T() 此前缺失导入，导致打包运行 NameError

WORD_MAX = 300          # 词级 diff 字符护栏：超长行退整行着色（沿用 DiffDialog 原值）
MAP_DIFF_MAX = 2000     # 区间映射的精确 diff 上限（仅合并/联动低频路径用；渲染仍走 WORD_MAX）

# v3.48.31（EXPAND-DIFF）：超 WORD_MAX 长行的「分层差异」参数 —— AI 扩写 /
# 改写场景下两侧是大段单行，直接退整行着色会让整段通红 / 通绿，看不到改动点
SEG_MAX = 6000          # 分层 diff 总长护栏：单侧超此长度退整行着色（保性能）
SEG_CHAR_MAX = 160      # 终端字符级 diff 护栏（子句组内；组内远小于 WORD_MAX）
SEG_MIN_EQ = 3          # 平滑阈值：≤N 字的 equal 锚点并入相邻差异（去椒盐碎片）
SEG_SMOOTH_MAX = 40     # 平滑上限：合并后差异段长不得超此值（防级联吞成整段）
SEG_CHAR_BUDGET = 250000    # 终端字符级 diff 的 len(a)*len(b) 成本预算
SEG_UNIT_BUDGET = 200000    # 单元级对齐的 len(ua)*len(ub) 成本预算

# v3.48.31（SENT-VIEW）：句级视图 —— 长行按句末标点拆为「句单愿」再比对
SENT_END_CHARS = "。！？；"     # 句末标点（不含 ASCII . ! ? —— 会误切 v3.48.31 / 小数）
SENT_CLOSERS = "\u201d\u2019）】」』》\"'"   # 句末标点后的收尾引号/括号，须并入前句
SENT_MIN_LEN = 24             # 短行不分句（标题 / 列表项通常短）
SENT_MAX_UNITS = 4000         # 单侧句单愿数上限，超出退原始行（超长文档保性能）
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")

# 层级递进分隔符：第 0 层句末标点 → 第 1 层子句标点（与 Markdown 语义无关）
_SEG_PATTERNS = [
    re.compile(r"([。！？!?；;\n])"),
    re.compile(r"([，,、：:])"),
]


# ================= 纯逻辑层 =================

def line_key_raw(line):
    """原始行键（不做归一）—— 历史版本对比 / 合并使用。"""
    return line


_MD_WS_RE = re.compile(r"\s+")


def line_key_md(line):
    """Markdown 容错行键：剥离标记与全部空白（可见文本归一）。

    渲染态选区文本不含 ** / ` / # 等标记，而 AI 回复通常带标记；直接逐字
    diff 会把「仅格式不同」的行全判为差异。按可见文本比较后格式差异收敛
    为 equal（结果输出统一取 B 侧，保留 AI 回复的 Markdown 格式）。"""
    return _MD_WS_RE.sub("", md_to_plain(line or ""))


def word_ops(old_ln, new_ln):
    """配对行的字符级 opcodes（[(tag, i1, i2, j1, j2)]）。

    超过 WORD_MAX 或两行一致时返回 None（退整行着色）。SequenceMatcher 按
    字符比较 + autojunk=False，对 CJK 逐字安全（v3.48.16 多光标同款结论）。"""
    old_ln, new_ln = str(old_ln), str(new_ln)
    if len(old_ln) > WORD_MAX or len(new_ln) > WORD_MAX:
        return None
    if old_ln == new_ln:
        return None
    sm = difflib.SequenceMatcher(a=old_ln, b=new_ln, autojunk=False)
    return sm.get_opcodes()


def word_ops_deep(old_ln, new_ln):
    """长文本（超 WORD_MAX）的分层差异：**句 → 子句 → 字符**三级递进。

    v3.48.31（EXPAND-DIFF）：AI 扩写 / 改写场景下两侧常是大段单行（实测
    原文 169 字 vs 扩写 405 字），远超 WORD_MAX 护栏 → word_ops 返回 None
    → 退整行着色，整段通红 / 通绿，用户看不到「到底改了哪里」。
    本函数的三层策略：

      · 第 0 层按句末标点（。！？；）切句做序列对齐，拿到稳定锚点；
      · 仍是 replace 的组按第 1 层子句标点（，、：）再切对齐；多单元改写
        组额外尝试「按句两两配对」（同行流 replace 的 1:1 语义），并与
        「整组拼接后递归」两路比较，取**差异总量更小**者（_ops_cost）；
      · 终端组（组内 ≤SEG_CHAR_MAX，远小于 WORD_MAX）才做字符级
        SequenceMatcher；最后用 _smooth_ops 吞掉 ≤SEG_MIN_EQ 字的极短
        equal 锚点 —— CJK 逐字 diff 的「椒盐碎片」（delete '墙' + equal
        '城' + insert '古'）合并为连续差异片段。

    返回 None 的情形与 word_ops 一致（两侧完全相同 / 超 SEG_MAX 护栏）；
    否则返回覆盖全文的行内坐标 opcodes，格式同 word_ops。"""
    old_ln, new_ln = str(old_ln), str(new_ln)
    if old_ln == new_ln:
        return None
    if max(len(old_ln), len(new_ln)) <= WORD_MAX:
        return word_ops(old_ln, new_ln)          # 短行：维持既有行为（探针 D2）
    if max(len(old_ln), len(new_ln)) > SEG_MAX:
        return None                              # 超长：旧「整行着色」兜底
    ops = _diff_text(old_ln, new_ln, 0)
    if not ops:
        return None
    return _smooth_ops(ops)


def _char_ops(sa, sb):
    """字符级 opcodes（CJK 逐字安全；平滑统一在上层做）。"""
    if not sa and not sb:
        return []
    return [tuple(o) for o in
            difflib.SequenceMatcher(a=sa, b=sb, autojunk=False).get_opcodes()]


def _split_units(s, pat):
    """按分隔符切分并把分隔符并入前一段（所有段顺次拼接 == 原文）。

    re.split 带一个捕获组 → [文本, 分隔符, 文本, 分隔符, …]，故偶数下标是
    文本、奇数下标是分隔符。"""
    parts = pat.split(s)
    out, buf = [], ""
    for i, p in enumerate(parts):
        if i % 2:
            out.append(buf + p)
            buf = ""
        else:
            buf = p
    if buf:
        out.append(buf)
    return [x for x in out if x]


def _ops_cost(ops):
    """差异总量（两侧差异字符数之和）—— 越小说明对齐越贴合。"""
    c = 0
    for t, i1, i2, j1, j2 in ops:              # noqa: B007
        if t != "equal":
            c += (i2 - i1) + (j2 - j1)
    return c


def _diff_text(sa, sb, depth):
    """sa → sb 的字符空间 opcodes（分层递归）。返回 None = 无法细分。

    优先用「更粗的稳定锚点」层层收敛：短组直接字符级；本层能切出多个单元
    且对齐成本可接受则做单元级对齐；本层切不动就递进下一层；无层可进时
    成本可接受仍退字符级（保住粒度），否则 None 由调用方按整处改动处理。"""
    if not sa and not sb:
        return []
    if max(len(sa), len(sb)) <= SEG_CHAR_MAX:
        return _char_ops(sa, sb)
    if depth < len(_SEG_PATTERNS):
        ua = _split_units(sa, _SEG_PATTERNS[depth])
        ub = _split_units(sb, _SEG_PATTERNS[depth])
        if max(len(ua), len(ub)) > 1 and len(ua) * len(ub) <= SEG_UNIT_BUDGET:
            return _align_units(ua, ub, depth)
    if depth + 1 < len(_SEG_PATTERNS):
        return _diff_text(sa, sb, depth + 1)
    if len(sa) * len(sb) <= SEG_CHAR_BUDGET:
        return _char_ops(sa, sb)
    return None


def _align_units(ua, ub, depth):
    """单元级对齐 → 字符空间 opcodes：replace 组递归进下一层。"""
    oa, ob = [0], [0]
    for x in ua:
        oa.append(oa[-1] + len(x))
    for x in ub:
        ob.append(ob[-1] + len(x))
    out = []
    sm = difflib.SequenceMatcher(a=ua, b=ub, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(("equal", oa[i1], oa[i2], ob[j1], ob[j2]))
            continue
        base_a, base_b = oa[i1], ob[j1]
        if tag == "insert":
            out.append(("insert", base_a, base_a, base_b, ob[j2]))
            continue
        if tag == "delete":
            out.append(("delete", base_a, oa[i2], base_b, base_b))
            continue
        su, sv = ua[i1:i2], ub[j1:j2]
        sub = None
        if len(su) > 1 and len(sv) > 1:
            # 多单元改写组（典型：每句都改了一点的大段改写）——两路候选
            # 择优：① 按位置两两配对（1:1 语义）② 整组拼接后继续分层
            cands = []
            p = _diff_pairs(su, sv, depth + 1)
            if p is not None:
                cands.append(p)
            q = _diff_text("".join(su), "".join(sv), depth + 1)
            if q is not None:
                cands.append(q)
            if cands:
                sub = min(cands, key=_ops_cost)
        if sub is None:
            sub = _diff_text("".join(su), "".join(sv), depth + 1)
        if sub is None:
            out.append(("replace", base_a, oa[i2], base_b, ob[j2]))
        else:
            for t2, x1, x2, y1, y2 in sub:
                out.append((t2, base_a + x1, base_a + x2,
                            base_b + y1, base_b + y2))
    return _merge_ops(out)


def _diff_pairs(ua, ub, depth):
    """按位置两两配对求差异（多单元被整体判为 replace 时的候选之一）。
    任一对无法细分即返回 None（交另一候选）。"""
    out, pa, pb = [], 0, 0
    for k in range(max(len(ua), len(ub))):
        sa = ua[k] if k < len(ua) else ""
        sb = ub[k] if k < len(ub) else ""
        sub = _diff_text(sa, sb, depth)
        if sub is None:
            return None
        for t, x1, x2, y1, y2 in sub:
            out.append((t, pa + x1, pa + x2, pb + y1, pb + y2))
        pa += len(sa)
        pb += len(sb)
    return _merge_ops(out)


def _jointag(i1, i2, j1, j2):
    if i2 <= i1:
        return "insert"
    if j2 <= j1:
        return "delete"
    return "replace"


def _smooth_ops(ops, min_eq=SEG_MIN_EQ, cap=SEG_SMOOTH_MAX):
    """吞掉两差异段之间 ≤min_eq 字的极短 equal 锚点（去椒盐），但合并后
    的差异段不得超过 cap —— 无上限时会级联吞并，把整段又合成一块 replace
    （等于「没有形成好的差异」，v3.48.31 首版实测即此坑）。"""
    out, k, n = [], 0, len(ops)
    while k < n:
        tag, i1, i2, j1, j2 = ops[k]
        if (tag == "equal" and out and out[-1][0] != "equal" and k + 1 < n
                and ops[k + 1][0] != "equal"
                and max(i2 - i1, j2 - j1) <= min_eq):
            ntag, nx2, ny2 = ops[k + 1][0], ops[k + 1][2], ops[k + 1][4]
            pt, px1, py1 = out[-1][0], out[-1][1], out[-1][3]
            if max(nx2 - px1, ny2 - py1) <= cap:
                out[-1] = (_jointag(px1, nx2, py1, ny2), px1, nx2, py1, ny2)
                k += 2
                continue
        out.append((tag, i1, i2, j1, j2))
        k += 1
    return _merge_ops(out)


def _merge_ops(ops):
    """顺序化清理：丢空段、归一化零长度侧的 tag、合并相邻同类段。

    **只重算非 equal 段的 tag**（开头的 Assume Bug：无条件重算会把 equal
    段也判成 replace，导致「相同的文字被当差异标红」—— v3.48.31 首版实测）。"""
    out = []
    for tag, i1, i2, j1, j2 in ops:
        if i2 <= i1 and j2 <= j1:
            continue
        if tag != "equal":
            tag = _jointag(i1, i2, j1, j2)
        if out:
            pt, px1, px2, py1, py2 = out[-1]
            if pt == tag and px2 == i1 and py2 == j1:
                out[-1] = (tag, px1, i2, py1, j2)
                continue
        out.append((tag, i1, i2, j1, j2))
    return out


def map_range(ops, i1, i2):
    """把一段文本上的字符区间 [i1, i2) 经字符级 opcodes 映射到另一段文本
    的对应区间（选区合并的核心）：equal 段按偏移 1:1 折算；
    replace/delete 段整体映射到对侧区间（选区落在改写区时替换整段对应
    区）；选区与任何 opcode 都不相交时贴靠最近边界（插入语义）。

    v3.48.32（MAP-EDGE）：源区间覆盖整段（i1<=0 且 i2>=源全长）时直接映射
    到目标全长。原循环对**贴边的 insert 段**无能为力——末尾 insert 的
    x1 == i2 被 `if x1 >= i2: break` 跳过（实测原文 169 字 vs 扩写 405 字，
    A[0,169) → B 只得 (0,354)，漏掉尾部 51 字「港湾。」式尾巴），开头贴边
    的 insert 同理。与 _mp_frag_merge 的 EDGE-INS 特判同源，此处在映射层
    修根，所有调用方（选区合并 / 选中采用 / 三框联动）一并受益。"""
    if ops:
        # ops 覆盖全文且单调（_probe_expand_diff_check 的 E1_MONOTONIC
        # 断言），末段 x2 = 源全长、y2 = 目标全长
        if i1 <= 0 and i2 >= ops[-1][2]:
            return 0, ops[-1][4]
    j1 = j2 = None
    seen = False
    for tag, x1, x2, y1, y2 in ops:
        if x2 <= i1:
            if not seen:
                j1 = y2          # 选区之前的右边界候选（随前扫持续更新）
            continue
        if x1 >= i2:
            break
        if tag == "equal":
            s = y1 + max(i1, x1) - x1
            e = y1 + min(i2, x2) - x1
        else:
            s, e = y1, y2
        if not seen:
            j1 = s               # 首个重叠 opcode 决定映射起点（覆盖边界候选）
            seen = True
        j2 = e
    if j1 is None:
        j1 = ops[-1][4] if ops else 0
    if j2 is None:
        j2 = j1
    return j1, j2


def map_range_long(st, txt, i1, i2):
    """长行（超出 word_ops 的 WORD_MAX 护栏，如 AI 回复整段单行）的区间
    映射——修复长段落合并漂移：旧退化方案按偏移钳制（源侧下标原样搬到
    目标文本），长行内容不同时合并片段必然落错位置。
    策略：≤ MAP_DIFF_MAX 字符直接用 difflib 精确 opcodes 对齐（复用
    map_range）——合并是用户点击触发的低频操作，可承受；更长时按长度
    比例估位 → 搜索片段原文取距估位最近的出现处；仍找不到（片段被
    对侧重写）退化为长度比例映射（均远优于位置钳制）。"""
    n, m = len(st), len(txt)
    if n and m and max(n, m) <= MAP_DIFF_MAX:
        ops = difflib.SequenceMatcher(a=st, b=txt,
                                      autojunk=False).get_opcodes()
        return map_range(ops, i1, i2)
    frag = st[i1:i2]
    if not frag:
        j = min(i1 * m // n, m) if n else 0
        return j, j
    guess = min(i1 * m // n, max(0, m - len(frag))) if n else 0
    best, best_d = None, None
    start = 0
    while True:
        idx = txt.find(frag, start)
        if idx < 0:
            break
        d = abs(idx - guess)
        if best_d is None or d < best_d:
            best, best_d = idx, d
            if d == 0:
                break
        start = idx + 1
    if best is not None:
        return best, best + len(frag)
    r1 = min(i1 * m // n, m) if n else 0
    r2 = min(i2 * m // n, m) if n else 0
    return min(r1, r2), max(r1, r2)


def build_hunks(a_lines, b_lines, key_fn=None):
    """行级差异 → hunk 列表（difflib opcodes 保序投影）。

    hunk = {"kind": "equal"|"replace"|"delete"|"insert",
            "a": [A 侧行...], "b": [B 侧行...], "ai": i1, "bi": j1}
    key_fn 可选：行归一键（如 line_key_md），equal 判定按归一键、
    内容保留两侧原始行。"""
    kf = key_fn or line_key_raw
    a_keys = [kf(l) for l in a_lines]
    b_keys = [kf(l) for l in b_lines]
    sm = difflib.SequenceMatcher(a=a_keys, b=b_keys, autojunk=False)
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        hunks.append({"kind": tag,
                      "a": list(a_lines[i1:i2]), "b": list(b_lines[j1:j2]),
                      "ai": i1, "bi": j1})
    return hunks


def split_sentences(text):
    """文本 → 句单愿列表 [(lineno, unit_text)]；同一原行内的多个单愿共享
    相同 lineno（重建结果时据此决定：句间无分隔、跨行才补 \\n）。

    v3.48.31（SENT-VIEW）保护规则（不切碎结构与不可切的内容）：
      · 围栏代码块（``` / ~~~）内的行原样保留；
      · 表格行（≥2 个 |）、短于 SENT_MIN_LEN 的行、无句末标点的行不分句；
      · 句末标点后紧跟的收尾引号 / 括号并入前句（避免下一句以 ” 开头）；
      · 单愿数超 SENT_MAX_UNITS → 退原始行（超长文档保性能）。"""
    lines = str(text or "").split("\n")
    units = []
    fence = False
    for li, raw in enumerate(lines):
        if _FENCE_RE.match(raw):
            fence = not fence
            units.append((li, raw))
            continue
        if (fence or len(raw) < SENT_MIN_LEN or raw.count("|") >= 2
                or not any(ch in SENT_END_CHARS for ch in raw)):
            units.append((li, raw))
            continue
        units.extend((li, u) for u in _split_line_sentences(raw))
    if len(units) > SENT_MAX_UNITS:
        return [(i, l) for i, l in enumerate(lines)]
    return units


def _split_line_sentences(line):
    """单行 → 若干句单愿（按句末标点切，收尾引号并入前句）。"""
    out, buf, i, n = [], "", 0, len(line)
    while i < n:
        ch = line[i]
        buf += ch
        if ch in SENT_END_CHARS:
            j = i + 1
            while j < n and line[j] in SENT_CLOSERS:
                buf += line[j]
                j += 1
            out.append(buf)
            buf = ""
            i = j
            continue
        i += 1
    if buf:
        out.append(buf)
    return out or [line]


def build_sent_rows(a_text, b_text, key_fn=None):
    """句级视图：文本 → 句单愿 → hunks → 行流，并给每行标注
      ai/bi：源侧单愿绝对下标（build_rows 提供）
      li  ：该行所属原行下标（决定重建时是否补换行）
      sep ：结果框重建时本行之后的分隔符（""=同原行内的句间，不换行；
            "\\n"=跨原行）—— 句单愿之间**绝不能**产生多余换行。"""
    a_units = split_sentences(a_text)
    b_units = split_sentences(b_text)
    a_lineno = [lineno for lineno, _u in a_units]
    b_lineno = [lineno for lineno, _u in b_units]
    hunks = build_hunks([u for _li, u in a_units],
                        [u for _li, u in b_units], key_fn=key_fn)
    rows = build_rows(hunks)
    for r in rows:
        ai, bi = r.get("ai"), r.get("bi")
        # ali / bli：**各侧自己的原行下标**。重建分隔符时必须在**同一侧**
        # 的坐标里比较（若混用两侧序号，插入行的行号恰与相邻 ctx 行的另一
        # 侧行号同值时会被误判为「同一行」而吞掉换行 —— 探针 D5_INS_ADOPT_B
        # 实测：line1 / ins-a / common 输出成 line1\nins-acommon）
        r["ali"] = a_lineno[ai] if (ai is not None and 0 <= ai < len(a_lineno)) else None
        r["bli"] = b_lineno[bi] if (bi is not None and 0 <= bi < len(b_lineno)) else None
        r["li"] = r["ali"] if r["ali"] is not None else r["bli"]
        r["sep"] = "\n"
    return rows


def build_rows(hunks):
    """hunks → 左右对齐行流。row = {
        lk/rk : "ctx"|"del"|"spacer" / "ctx"|"add"|"spacer"
        lt/rt : 该侧文本（spacer 侧为 ""）
        lw/rw : 词级 opcodes 或 None（仅 (del,add) 配对行有，两侧共用同一份）
        hunk  : 所属 hunk 下标；ri: hunk 内行序 }"""
    rows = []
    for hi, h in enumerate(hunks):
        kind = h["kind"]
        if kind == "equal":
            for k in range(len(h["a"])):
                rows.append({"lk": "ctx", "lt": h["a"][k], "lw": None,
                             "rk": "ctx", "rt": h["b"][k], "rw": None,
                             "hunk": hi, "ri": k,
                             "ai": h["ai"] + k, "bi": h["bi"] + k})
        elif kind == "replace":
            dl, al = h["a"], h["b"]
            for k in range(max(len(dl), len(al))):
                lt = dl[k] if k < len(dl) else ""
                rt = al[k] if k < len(al) else ""
                lk = "del" if k < len(dl) else "spacer"
                rk = "add" if k < len(al) else "spacer"
                # v3.48.31：配走上 word_ops_deep —— 超 WORD_MAX 的长段落
                # （AI 扩写典型场景）退化为分层差异（句/子句/字符 + 平滑），
                # 不再整行着色，短行行为不变
                wo = word_ops_deep(lt, rt) if (lk == "del" and rk == "add") else None
                rows.append({"lk": lk, "lt": lt, "lw": wo,
                             "rk": rk, "rt": rt, "rw": wo,
                             "hunk": hi, "ri": k,
                             "ai": h["ai"] + k if k < len(dl) else None,
                             "bi": h["bi"] + k if k < len(al) else None})
        elif kind == "delete":
            for k in range(len(h["a"])):
                rows.append({"lk": "del", "lt": h["a"][k], "lw": None,
                             "rk": "spacer", "rt": "", "rw": None,
                             "hunk": hi, "ri": k,
                             "ai": h["ai"] + k, "bi": None})
        else:   # insert
            for k in range(len(h["b"])):
                rows.append({"lk": "spacer", "lt": "", "lw": None,
                             "rk": "add", "rt": h["b"][k], "rw": None,
                             "hunk": hi, "ri": k,
                             "ai": None, "bi": h["bi"] + k})
    return rows


def esc_html(s):
    """HTML 转义（不替换空格 —— 视图层用 white-space:pre-wrap 保留空白）。"""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def subtract_ranges(intervals, holes):
    """从 (a, b) 区间集合里挖掉 holes 区间（结果框冲突着色用：来源片段
    区间优先于冲突黄，重叠处不重复着色）。返回互不重叠的新区间列表。"""
    holes = sorted(holes)
    out = []
    for a, b in intervals:
        if b <= a:
            continue
        cur = a
        for h1, h2 in holes:
            if h2 <= cur:
                continue
            if h1 >= b:
                break
            if h1 > cur:
                out.append((cur, min(h1, b)))
            cur = max(cur, h2)
            if cur >= b:
                break
        if cur < b:
            out.append((cur, b))
    return out


def _mp_palette(theme):
    """配色（亮 / 暗两套）：del/add 左红右绿（词级 span 与整行兜底同色），
    unresolved 黄（未合并冲突），sel 浅蓝（三框选中联动高亮）。"""
    dark = theme in ("dark", "night", "panda")
    if dark:
        return {"add": "#1e3b2a", "del": "#3f2222",
                "spacer": "#3a3f4b", "unresolved": "#4a4116",
                "bd_add": "#3fb950", "bd_del": "#f85149",
                "bd_gray": "#6e7681", "txt": "#e6edf3", "ctx": "#8b949e",
                "sel": "#1c3a5e"}
    return {"add": "#9FE1CB", "del": "#F5C4B3",
            "spacer": "#d1d5db", "unresolved": "#fff3cd",
            "bd_add": "#1a7f37", "bd_del": "#cf222e",
            "bd_gray": "#d0d7de", "txt": "#1f2328", "ctx": "#6b7280",
            "sel": "#B4D5FE"}


# ================= 视图层：TwoPaneMergeMixin =================

class TwoPaneMergeMixin:
    """冲突字级着色 + 三框联动 + 选区合并（mixin，宿主须是 QDialog）。

    子类约定：
      · 类属性钩子：mp_side_a_label / mp_side_b_label（列头）、
        mp_key_fn（行归一键）、mp_default_side（结果默认侧，恒 "B"）；
      · __init__ 里调 self._mp_build_ui(top_widgets=[...], result_hint="…")；
      · 展示时调 self._mp_load(a_text, b_text, theme=...)；
      · 覆写 self._mp_tail_buttons(brow) 追加自己的功能性按钮（取消 /
        确认替换、应用到当前文档 / 另存为 / 关闭等）；
      · eventFilter 里先问 self._mp_event_filter(obj, ev)。
    合并入口只有两个：对比栏选中文字后双击 / 右键「合并所选内容」。
    """

    mp_side_a_label = "左侧（A）"
    mp_side_b_label = "右侧（B）"
    mp_all_left_text = "全部采用左（A）"
    mp_all_right_text = "全部采用右（B）"
    mp_key_fn = staticmethod(line_key_raw)
    mp_default_side = "B"
    # v3.48.31：句级视图开关 —— **默认关闭**。用户实测要求：对比框里不要
    # 手动按句号换行显示（句单愿各占一行会割裂原文段落观感）。精细化差异
    # 由 word_ops_deep（EXPAND-DIFF）在**行内**给出，不依赖分行。
    mp_sent_view = False

    # ---------- UI 骨架 ----------
    def _mp_build_ui(self, top_widgets=None, result_hint=""):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(8)
        for w in (top_widgets or []):
            lay.addWidget(w)

        # 列头（与左右对比框对齐）
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        self.mp_lbl_a = QLabel(self.mp_side_a_label, self)
        self.mp_lbl_a.setObjectName("pageHint")
        self.mp_lbl_b = QLabel(self.mp_side_b_label, self)
        self.mp_lbl_b.setObjectName("pageHint")
        hdr.addWidget(self.mp_lbl_a, 1)
        hdr.addWidget(self.mp_lbl_b, 1)
        lay.addLayout(hdr)

        # 双栏对比框（QTextBrowser；鼠标 / 右键事件经 viewport() 投递 ——
        # QAbstractScrollArea 装在 pane 本体上收不到，v3.48.3 教训）
        self.pane_a = QTextBrowser(self)
        self.pane_a.setReadOnly(True)
        self.pane_a.setOpenLinks(False)
        self.pane_b = QTextBrowser(self)
        self.pane_b.setReadOnly(True)
        self.pane_b.setOpenLinks(False)
        self.pane_a.viewport().installEventFilter(self)
        self.pane_b.viewport().installEventFilter(self)
        top = QSplitter(Qt.Horizontal, self)
        top.setHandleWidth(6)
        top.setChildrenCollapsible(False)
        top.addWidget(self.pane_a)
        top.addWidget(self.pane_b)
        top.setStretchFactor(0, 1)
        top.setStretchFactor(1, 1)
        lay.addWidget(top, 3)

        # 状态行
        self.mp_stat = QLabel("", self)
        self.mp_stat.setObjectName("pageHint")
        self.mp_stat.setWordWrap(True)
        lay.addWidget(self.mp_stat)

        # 合并结果（可编辑）
        self.mp_result_hint = QLabel(result_hint, self)
        self.mp_result_hint.setObjectName("pageHint")
        self.mp_result_hint.setWordWrap(True)
        lay.addWidget(self.mp_result_hint)
        self.pane_merge = QTextEdit(self)
        self.pane_merge.setAcceptRichText(False)
        lay.addWidget(self.pane_merge, 2)

        # 按钮行：仅子类功能性按钮（应用 / 另存为 / 取消 / 确认替换等）
        brow = QHBoxLayout()
        self._mp_tail_buttons(brow)
        if brow.count():
            lay.addLayout(brow)
        else:
            brow.setParent(None)

        self._mp_rows = []
        self._mp_diff_firsts = []    # 每个非 equal hunk 首行的行号（统计用）
        self._mp_row_cur = []        # 各行起点游标（末位=文档尾哨兵）
        self._mp_press_row = None
        self._mp_press_sel = None
        self._mp_colors = _mp_palette("light")
        self._mp_busy = False        # 渲染 / 装载期间抑制联动信号
        self._mp_scroll_lock = False

        # 三框联动（v3.48.28）：滚动按首可见行同步；选中经行流 + 字符级
        # diff 映射后以 extraSelections 浅蓝高亮（不改文本与选区本身）
        for w in (self.pane_a, self.pane_b, self.pane_merge):
            w.verticalScrollBar().valueChanged.connect(
                lambda _v, _w=w: self._mp_sync_scroll(_w))
        # 选中联动（v3.48.29）：三框双向 —— 任意一框选中，另两框对应
        # 内容浅蓝高亮；拖选过程中 selectionChanged 高频触发，经 0ms
        # 单发定时器合并去抖
        self._mp_sel_pending = None
        self._mp_sel_timer = QTimer(self)
        self._mp_sel_timer.setSingleShot(True)
        self._mp_sel_timer.timeout.connect(self._mp_sel_flush)
        for _w, _s in ((self.pane_a, "A"), (self.pane_b, "B"),
                       (self.pane_merge, "R")):
            _w.selectionChanged.connect(
                lambda _s=_s: self._mp_queue_sel(_s))

    def _mp_tail_buttons(self, brow):
        """子类追加功能性按钮（brow.addStretch(1) 后放自己的按钮）。"""

    # ---------- 装载 ----------
    def _mp_set_labels(self, a_label, b_label):
        self.mp_lbl_a.setText(a_label or self.mp_side_a_label)
        self.mp_lbl_b.setText(b_label or self.mp_side_b_label)

    def _mp_load(self, a_text, b_text, theme="light"):
        self._mp_a = str(a_text or "")
        self._mp_b = str(b_text or "")
        self._mp_colors = _mp_palette(theme)
        # v3.48.31（SENT-VIEW）：句级行流 —— 长行按句末标点拆为句单愿后
        # 再比对（AI 扩写一大段时可逐句裁决）；mp_sent_view=False 退原始行
        # 默认 False（mp_sent_view）：对比框按原文行显示，不按句号人工折行
        self._mp_sent = bool(getattr(self, "mp_sent_view", False))
        if self._mp_sent:
            rows = build_sent_rows(self._mp_a, self._mp_b,
                                   key_fn=self.mp_key_fn)
        else:
            rows = build_rows(build_hunks(self._mp_a.split("\n"),
                                          self._mp_b.split("\n"),
                                          key_fn=self.mp_key_fn))
        for r in rows:
            r["choice"] = None       # 逐行裁决态（右键「全部采用」写入）
            r["override"] = None     # 该行合并结果（选区合并写入）
            r["frags"] = []          # override 内合并片段 [(j1, j2, side)]
        self._mp_rows = rows
        self._mp_calc_seps()
        self._mp_diff_firsts = []
        prev_hunk = -1
        for i, r in enumerate(rows):
            if r["hunk"] != prev_hunk:
                prev_hunk = r["hunk"]
                if r["lk"] != "ctx":
                    self._mp_diff_firsts.append(i)
        self._mp_render_panes()
        self._mp_refresh_result()
        self._mp_update_stat()

    def _mp_calc_seps(self):
        """按每行所属原行（li）算出写入结果时的分隔符：同一原行内的相邻句
        单愿之间 **不产出换行**（""），跨原行才补 "\\n"。

        只看当前会输出的行（emits），故「某句被删除」不会让前后两句粘成
        一段 —— 相邻输出行的 li 不同 ⇒ 仍按原行边界补换行。"""
        rows = self._mp_rows or []
        emit = [i for i, r in enumerate(rows) if self._mp_row_output(r)[1]]
        for pos, i in enumerate(emit):
            if pos + 1 >= len(emit):
                rows[i]["sep"] = "\n"
                break
            nxt = emit[pos + 1]
            a1, a2 = rows[i].get("ali"), rows[nxt].get("ali")
            b1, b2 = rows[i].get("bli"), rows[nxt].get("bli")
            if a1 is not None and a2 is not None:
                same = a1 == a2            # 两侧都在 A 中存在 → 用 A 坐标
            elif b1 is not None and b2 is not None:
                same = b1 == b2            # 否则用 B 坐标
            else:
                same = False               # 单方独有内容（增 / 删）→ 保持换行
            rows[i]["sep"] = "" if same else "\n"

    # ---------- 渲染 ----------
    def _mp_esc(self, s):
        return esc_html(s)

    def _mp_span_html(self, text, ops, side_key, hl_color):
        """按字符级 opcodes 生成带词级高亮的行 HTML（side_key: "a"|"b"）；
        ops 为 None 时退整行转义（调用方负责整行底色）。"""
        if not ops:
            return self._mp_esc(text)
        out = []
        for tag, i1, i2, j1, j2 in ops:
            s, e = (j1, j2) if side_key == "b" else (i1, i2)
            seg = self._mp_esc(text[s:e])
            out.append('<span style="background:%s;">%s</span>' % (hl_color, seg)
                       if tag != "equal" else seg)
        return "".join(out)

    def _mp_render_panes(self):
        """行级比较视图：每行一个渲染块（块号与行流下标一致）。**仅差异
        文字着底色**（左红 / 右绿）：配对行只给词级 span 上色、整行不铺
        底色；无词级 opcodes 时整行即差异文字，退整行底色。差异行保留
        左侧 3px 色条；有合并片段的行尾打 ✎。每行包 cmd://mp/{idx}/{side}
        锚点 + mpR{idx} 命名锚点（anchorAt 反查行号）。
        v3.48.28：重渲染前后保持滚动位置（setHtml 会归顶）；重渲染清空
        三框联动高亮；渲染期间置 _mp_busy 抑制联动信号。"""
        c = self._mp_colors
        sav = [w.verticalScrollBar().value()
               for w in (self.pane_a, self.pane_b)]
        self._mp_busy = True
        try:
            for side, pane in (("A", self.pane_a), ("B", self.pane_b)):
                parts = ['<div style="font-family:Consolas,monospace;'
                         'font-size:13px;line-height:1.5;">']
                for idx, r in enumerate(self._mp_rows):
                    href = ('href="cmd://mp/%d/%s" name="mpR%d"'
                            % (idx, side, idx))
                    anchor = ('<a %s style="text-decoration:none;color:%s;">%s</a>'
                              % (href, c["txt"], "%s"))
                    if side == "A":
                        kind, txt, wo = r["lk"], r["lt"], r["lw"]
                        chosen = (r.get("choice") == "A")
                    else:
                        kind, txt, wo = r["rk"], r["rt"], r["rw"]
                        chosen = (r.get("choice") == "B")
                    if kind == "ctx":
                        # 空文本行渲染 &nbsp; 占位 —— 空 div 不产块会使
                        # 「块号=行号」不变式失效（v3.48.26 实测 blockCount
                        # 掉行），片段级合并列号定位与块号回退定位均依赖之
                        body = anchor % (self._mp_esc(txt) if txt else "&nbsp;")
                        parts.append('<div style="padding:0 8px;margin:0;'
                                     'white-space:pre-wrap;">%s</div>' % body)
                        continue
                    if kind == "spacer":
                        parts.append(
                            '<div style="padding:0 8px;margin:0;'
                            'border-top:1px dashed %s;'
                            'border-bottom:1px dashed %s;'
                            'color:%s;white-space:pre-wrap;">%s</div>'
                            % (c["bd_gray"], c["bd_gray"], c["ctx"],
                               anchor % "&nbsp;"))
                        continue
                    bg = c["del"] if side == "A" else c["add"]
                    bd = c["bd_del"] if side == "A" else c["bd_add"]
                    body = self._mp_span_html(txt, wo,
                                              "a" if side == "A" else "b", bg)
                    if r.get("override") is not None:
                        body += (' <span style="color:%s;font-weight:bold;">✎</span>'
                                 % c["bd_add"])
                    elif chosen:
                        body += (' <span style="color:%s;font-weight:bold;">✓</span>'
                                 % c["bd_add"])
                    style = ('border-left:3px solid %s;' % bd
                             + ('background:%s;' % bg if not wo else ''))
                    parts.append(
                        '<div style="padding:0 8px;margin:0;%s'
                        'white-space:pre-wrap;">%s</div>' % (style,
                                                             anchor % body))
                parts.append("</div>")
                pane.setHtml("".join(parts))
            for w in (self.pane_a, self.pane_b, self.pane_merge):
                w.setExtraSelections([])
            for w, v in zip((self.pane_a, self.pane_b), sav):
                w.verticalScrollBar().setValue(v)
        finally:
            self._mp_busy = False

    # ---------- 位置 → 行号 ----------
    def _mp_row_from_pos(self, pane, pos):
        """viewport 坐标 → 行号：优先 anchorAt 反查 cmd://mp/{idx}/{side}；
        行级渲染下块号与行流下标一致，块号回退也精确可靠。"""
        try:
            href = pane.anchorAt(pos)
        except Exception:
            href = ""
        if href and href.startswith("cmd://mp/"):
            try:
                return int(href[len("cmd://mp/"):].split("/")[0])
            except (ValueError, IndexError):
                pass
        try:
            cur = pane.cursorForPosition(pos)
            blk = pane.document().findBlock(cur.position())
            i = blk.blockNumber()
            if 0 <= i < len(self._mp_rows):
                return i
        except Exception:
            pass
        return self._mp_press_row if self._mp_press_row is not None else 0

    # ---------- 选区合并（唯一合并入口） ----------
    def _mp_frag_spans(self, pane, side, sel=None):
        """对比栏选区 → [(行号, i1, i2)]（i1/i2 为该行 side 侧文本内的字符
        区间）。行级渲染下每行一个块、块号与行流下标一致，块内列号即行
        文本内偏移（✎ 追加在行尾，不影响前缀偏移）。
        sel=(start, end) 为文档位置（双击路径用按下瞬间的选区快照——press1
        会把 widget 选区塌陷）；None 取 pane 当前选区（右键不清选区）。
        无有效选区 / 未覆盖任何有字侧返回 None。"""
        if sel is None:
            cur = pane.textCursor()
            if not cur.hasSelection():
                return None
            s, e = cur.selectionStart(), cur.selectionEnd()
        else:
            s, e = sel
        doc = pane.document()
        c1 = QTextCursor(doc)
        c1.setPosition(min(s, e))
        c2 = QTextCursor(doc)
        c2.setPosition(max(s, e))
        b1, b2 = c1.blockNumber(), c2.blockNumber()
        n = len(self._mp_rows)
        if b1 >= n:
            return None
        spans = []
        for k in range(b1, min(b2, n - 1) + 1):
            r = self._mp_rows[k]
            st = r["lt"] if side == "A" else r["rt"]
            if (r["lk"] if side == "A" else r["rk"]) == "spacer" or not st:
                continue
            # positionInBlock()=逻辑块内列；columnNumber() 是可视行内列，
            # 长行折行后偏移错乱（v3.48.30 漂移根因），勿改回
            i1 = c1.positionInBlock() if k == b1 else 0
            i2 = c2.positionInBlock() if k == b2 else len(st)
            i1 = max(0, min(i1, len(st)))
            i2 = max(0, min(i2, len(st)))
            if i2 > i1:
                spans.append((k, i1, i2))
        return spans or None

    def _mp_frag_merge(self, spans, side):
        """选区合并：把所选文字按词级对齐（map_range）替换进结果框的
        对应区间，该行其余文字与其他行保持结果现状。每行生成 override
        文本原位写回（再次合并基于最新 override 重新对齐，可反复叠加）；
        合并片段按来源侧记录坐标（结果框按来源着色）。
        返回实际发生替换的行数（0 = 所选内容与结果一致，无需改动）。"""
        changed = []
        for k, i1, i2 in (spans or []):
            if not (0 <= k < len(self._mp_rows)):
                continue
            r = self._mp_rows[k]
            if not self._mp_adoptable(r):
                continue        # 相同行两侧一致，无需合并
            st = r["lt"] if side == "A" else r["rt"]
            if (r["lk"] if side == "A" else r["rk"]) == "spacer" or not st:
                continue
            frag = st[i1:i2]
            if not frag:
                continue
            ov = r.get("override")
            out_side = r.get("choice") or self.mp_default_side
            txt = ov if ov is not None else (
                r["lt"] if out_side == "A" else r["rt"])
            # v3.48.31（EDGE-INS）：**选中源侧整行 = 整行替换**。
            # map_range 只在 x1 < i2 时把插入段计入替换区，整行选中时目标侧
            # 行尾多出的插入段（如 B 比 A 多出的「港湾。」）恰好落在区间外
            # → 合并后结果与目标文本逐字相同，实测表现为「选择左边作为合并
            # 内容无效」。整行选中直接按整行替换，多余尾巴随之被清理。
            if i1 <= 0 and i2 >= len(st):
                j1, j2 = 0, len(txt)
            elif ov is not None:
                # 已有合并结果：以 override 为底重新对齐
                # v3.48.32（MAP-DEEP）：同上，超 WORD_MAX 走分层差异；
                # ov 与 st 分别来自不同侧时长度差极大（如结果已是原文
                # 169 字、源侧是扩写 405 字），旧引擎必返 None。
                ops = word_ops_deep(st, ov)
                if ops:
                    j1, j2 = map_range(ops, i1, i2)
                else:   # 超长（AI 长段落）/ 一致：比例估位+就近搜索映射
                    j1, j2 = map_range_long(st, ov, i1, i2)
            else:
                osk = r["lk"] if out_side == "A" else r["rk"]
                if osk == "spacer":
                    j1 = j2 = 0         # 行当前被删除：仅把片段写回该行
                elif out_side == side:
                    continue            # 片段已在结果中，无需动作
                else:
                    # 方向必须 st→txt，勿复用 r["lw"]
                    # v3.48.32（MAP-DEEP）：超 WORD_MAX（AI 长段落）旧引擎
                    # 返 None 退比例估位，与渲染层（word_ops_deep）口径不
                    # 一致 → 合并落位偏差；统一走分层差异。
                    ops = word_ops_deep(st, txt)
                    if ops:
                        j1, j2 = map_range(ops, i1, i2)
                    else:   # 超 SEG_MAX：比例估位+就近搜索，勿钳制
                        j1, j2 = map_range_long(st, txt, i1, i2)
            new = txt[:j1] + frag + txt[j2:]
            if new == txt:
                continue
            # 平移既有片段坐标（被本次替换覆盖的旧片段丢弃）
            d = len(frag) - (j2 - j1)
            frags = []
            for f1, f2, fs in r.get("frags") or []:
                if f2 <= j1:
                    frags.append((f1, f2, fs))
                elif f1 >= j2:
                    frags.append((f1 + d, f2 + d, fs))
            frags.append((j1, j1 + len(frag), side))
            r["override"] = new
            r["frags"] = frags
            changed.append(k)
        if changed:
            self._mp_render_panes()
            for k in changed:
                self._mp_replace_result_row(k)
            self._mp_update_stat()
        return len(changed)

    def _mp_sel_adopt(self, spans, sel_side, target_side):
        """右键「选中采用（左 / 右）」（v3.48.29）：把所选范围替换为指定
        侧的对应内容（可跨行、与所选侧无关）；指定侧该行无内容（spacer）
        = 从结果中删除所选对应文字（Beyond Compare 语义：取空侧 = 删除）。
        返回实际改动行数（0 = 与结果一致）。"""
        mapped, dels = [], []
        for k, i1, i2 in spans or []:
            if not (0 <= k < len(self._mp_rows)):
                continue
            if target_side == sel_side:
                mapped.append((k, i1, i2))
                continue
            m = self._mp_map_span(self._mp_rows[k], sel_side, i1, i2,
                                  target_side, placeholder=False)
            if m and m[1] > m[0]:
                mapped.append((k, m[0], m[1]))
                continue
            d = self._mp_map_span(self._mp_rows[k], sel_side, i1, i2, "R",
                                  placeholder=False)
            if d and d[1] > d[0]:
                dels.append((k, d[0], d[1]))
        changed = 0
        if mapped:
            changed += self._mp_frag_merge(mapped, target_side)
        if dels:
            changed += self._mp_frag_delete(dels)
        return changed

    def _mp_frag_delete(self, spans):
        """从结果框删除若干 (行号, j1, j2) 区间（j 为结果坐标）：写
        override，既有片段坐标平移（被删区间内的丢弃）。返回改动行数。"""
        changed = []
        for k, j1, j2 in spans or []:
            if not (0 <= k < len(self._mp_rows)):
                continue
            r = self._mp_rows[k]
            txt, emits, _m = self._mp_row_output(r)
            if not emits or not (0 <= j1 < j2 <= len(txt)):
                continue
            new = txt[:j1] + txt[j2:]
            if new == txt:
                continue
            d = -(j2 - j1)
            frags = []
            for f1, f2, fs in r.get("frags") or []:
                if f2 <= j1:
                    frags.append((f1, f2, fs))
                elif f1 >= j2:
                    frags.append((f1 + d, f2 + d, fs))
            r["override"] = new
            r["frags"] = frags
            changed.append(k)
        if changed:
            self._mp_render_panes()
            for k in changed:
                self._mp_replace_result_row(k)
            self._mp_update_stat()
        return len(changed)

    @staticmethod
    def _mp_adoptable(r):
        return not (r["lk"] == "ctx" and r["rk"] == "ctx")

    def _mp_all_rows(self):
        return [i for i, r in enumerate(self._mp_rows)
                if self._mp_adoptable(r)]

    # ---------- 整行裁决（右键「全部采用左 / 右」） ----------
    def _mp_adopt(self, side, row_idxs):
        """把 rows 中各行取舍置为 side，并按行原位替换结果框内容
        （游标随编辑自动平移，其余行的手工修改不受影响）；整行采用
        覆盖该行此前的选区合并结果。"""
        changed = []
        for k in (row_idxs or []):
            if not (0 <= k < len(self._mp_rows)):
                continue
            r = self._mp_rows[k]
            if not self._mp_adoptable(r):
                continue
            if r.get("choice") != side or r.get("override") is not None:
                r["choice"] = side
                r["override"] = None
                r["frags"] = []
                changed.append(k)
        if changed:
            self._mp_render_panes()
            for k in changed:
                self._mp_replace_result_row(k)
            self._mp_update_stat()

    # ---------- 结果框 ----------
    def _mp_insert_colored(self, cur, txt, marks):
        """在 cur（已定位行起点）处按 marks 分段 insertText 写入行文本 +
        换行。marks = [(f1, f2, key)]，key ∈ "unresolved"（黄）/"del"（红）/
        "add"（绿），区间互不重叠（冲突段已在 _mp_row_output 里扣除来源
        片段）；无 marks 的部分用空 fmt 显式写入（杜绝行间格式继承）。
        未显示的 QTextEdit 上 setCharFormat 实测一律不生效（v3.48.27
        探针实锤），着色必须走 insertText(text, fmt) 显式写入。"""
        c = self._mp_colors
        empty = QTextCharFormat()
        good = sorted((f1, f2, k) for f1, f2, k in (marks or [])
                      if 0 <= f1 < f2 <= len(txt))
        pos = 0
        for f1, f2, k in good:
            if f1 > pos:
                cur.insertText(txt[pos:f1], empty)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(c[k]))
            cur.insertText(txt[f1:f2], fmt)
            pos = f2
        if pos < len(txt):
            cur.insertText(txt[pos:], empty)
        cur.insertText("\n", empty)

    def _mp_row_output(self, r):
        """行的合并输出：(txt, emits, marks)。
        marks = [(f1, f2, key)]，key ∈ "unresolved"（黄=冲突未合并）/
        "del"（红=合并自左）/"add"（绿=合并自右），区间互不重叠。
        v3.48.28：结果框**只给冲突文字着色**，与另一侧相同的文字无底色：
          · equal 行恒输出（保空行），无任何底色；
          · choice=A/B（整行裁决）→ 整行即合并自该方，整行该侧来源色
            （该侧不存在 = 删除该行，emits=False）；
          · override（选区合并）→ 片段按来源色，其余部分与对侧逐字比较，
            不同处标黄（仍未合并），相同处不着色；
          · 未裁决行 → 输出默认侧文本，与对侧逐字比较，不同处标黄；
            两侧文本一致（仅格式差异，md 行键）时不着色；对侧为 spacer
            （本行单方独有）→ 整行黄。"""
        if r["lk"] == "ctx" and r["rk"] == "ctx":
            return r["rt"], True, []
        ov = r.get("override")
        if ov is not None:
            if ov == "":
                return "", False, []   # 删空整行 = 从结果移除（不残留空行）
            if ov == r["lt"] and r["lk"] == "del":
                return ov, True, [(0, len(ov), "del")]   # 整行合并自左侧
            if ov == r["rt"] and r["rk"] == "add":
                return ov, True, [(0, len(ov), "add")]   # 整行合并自右侧
            out_side = r.get("choice") or self.mp_default_side
            opp_k = r["rk"] if out_side == "A" else r["lk"]
            opp_t = r["rt"] if out_side == "A" else r["lt"]
            src = [(f1, f2, "del" if fs == "A" else "add")
                   for f1, f2, fs in (r.get("frags") or [])
                   if 0 <= f1 < f2 <= len(ov)]
            if opp_k == "spacer" or not opp_t:
                conf = [(0, len(ov))]         # 对侧无内容：整行冲突
            else:
                ops = word_ops(opp_t, ov)
                if ops is None:
                    conf = [] if opp_t == ov else [(0, len(ov))]
                else:
                    conf = [(y1, y2) for tag, _x1, _x2, y1, y2 in ops
                            if tag != "equal"]
            marks = [(f1, f2, "unresolved")
                     for f1, f2 in subtract_ranges(
                         conf, [(a, b) for a, b, _k in src])]
            return ov, True, src + marks
        side = r.get("choice") or self.mp_default_side
        sk = r["lk"] if side == "A" else r["rk"]
        txt = r["lt"] if side == "A" else r["rt"]
        if sk == "spacer":
            return txt, False, []             # 该侧不存在 = 删除该行
        if r.get("choice") is not None:
            return txt, True, [(0, len(txt),
                                "del" if side == "A" else "add")]
        ok = r["rk"] if side == "A" else r["lk"]
        ot = r["rt"] if side == "A" else r["lt"]
        if ok == "spacer" or not ot:
            return txt, True, [(0, len(txt), "unresolved")]
        if ot == txt:
            return txt, True, []              # 仅格式差异（md 行键）
        ops = r["rw"] if side == "B" else r["lw"]
        if ops is None:
            ops = word_ops(ot, txt)
        if ops is None:
            return txt, True, [(0, len(txt), "unresolved")]   # 超长退整行
        marks = [(y1, y2, "unresolved")
                 for tag, _x1, _x2, y1, y2 in ops if tag != "equal"]
        return txt, True, marks

    def _mp_replace_result_row(self, k):
        """按行原位替换结果框内容。QTextCursor 在插入点会被推着走（且被删
        区间内的游标收敛到区间起点），编辑后按旧位置显式复位所有行游标
        （v3.48.3 验证过的算法，从段级推广到行级）。行内容按 marks 分段
        insertText 着色（冲突黄 / 来源红绿，相同文字无底色）。"""
        if not (0 <= k < len(self._mp_rows)) or not self._mp_row_cur:
            return
        txt, emits, marks = self._mp_row_output(self._mp_rows[k])
        doc = self.pane_merge.document()
        old_pos = [cur.position() for cur in self._mp_row_cur]
        start = old_pos[k]
        end = (old_pos[k + 1] if k + 1 < len(self._mp_row_cur)
               else doc.characterCount())
        cur = QTextCursor(doc)
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        self._mp_busy = True
        try:
            if emits:
                self._mp_insert_colored(cur, txt, marks)
            else:
                cur.removeSelectedText()
        finally:
            self._mp_busy = False
        newlen = (len(txt) + 1) if emits else 0
        for j in range(k, len(self._mp_row_cur)):
            if j == k:
                self._mp_row_cur[j].setPosition(start)
            else:
                self._mp_row_cur[j].setPosition(
                    start + newlen + max(0, old_pos[j] - end))

    def _mp_refresh_result(self):
        """结果框按行流全量重建：equal 行原样（无底色），差异行只给冲突
        文字黄底（与对侧逐字比较），override 行按合并结果与片段来源着色。
        **必须逐行 insertText(txt+"\\n", fmt) 写入** —— setPlainText 之后
        setCharFormat 在未显示的 QTextEdit 上实测一律不生效（v3.48.27
        探针实锤）；显式空 fmt 亦可杜绝行间格式继承（v3.48.3 的担忧）。
        v3.48.28：重建前后保持滚动位置；期间置 _mp_busy 抑制联动。
        每行记录起点游标（末位=文档尾哨兵）。"""
        doc = self.pane_merge.document()
        sav = self.pane_merge.verticalScrollBar().value()
        self._mp_busy = True
        try:
            doc.clear()
            starts = []
            pos = 0
            for r in self._mp_rows:
                starts.append(pos)
                txt, emits, marks = self._mp_row_output(r)
                if emits:
                    cur = QTextCursor(doc)
                    cur.movePosition(QTextCursor.End)
                    self._mp_insert_colored(cur, txt, marks)
                    pos += len(txt) + 1
            self._mp_row_cur = []
            for p in starts:
                cc = QTextCursor(doc)
                cc.setPosition(min(p, doc.characterCount()))
                self._mp_row_cur.append(cc)
            cc = QTextCursor(doc)
            cc.movePosition(QTextCursor.End)
            self._mp_row_cur.append(cc)
            self.pane_merge.verticalScrollBar().setValue(sav)
        finally:
            self._mp_busy = False

    # ---------- 三框联动（v3.48.28） ----------
    @staticmethod
    def _mp_rev_ops(ops):
        """opcodes 方向反转（A→B 变 B→A，源/目标坐标互换）。"""
        return [(t, y1, y2, x1, x2) for t, x1, x2, y1, y2 in ops]

    def _mp_map_span(self, r, side, i1, i2, tside, placeholder=True):
        """把行 r 上 side 侧字符区间 [i1, i2) 映射到 tside（"A"/"B"/"R"，
        R = 合并结果）的对应区间。
        · 源侧为 spacer / 结果框中该行被删除 → None；
        · 目标侧为 spacer（本行无内容）且 placeholder=True → 返回 (0, 1)
          （高亮目标栏空白占位行的 &nbsp; 字符，Beyond Compare 式对位
          提示——「这行在这边没有内容」）；placeholder=False → None
          （「选中采用」语义：对侧无内容 = 删除）；
        · equal（含 md 行键仅格式差异）按偏移钳制；其余经字符级 diff
          对齐（map_range）。"""
        if side == "R":
            st, emits, _m = self._mp_row_output(r)
            if not emits:
                return None
        else:
            sk = r["lk"] if side == "A" else r["rk"]
            st = r["lt"] if side == "A" else r["rt"]
            if sk == "spacer" or not st:
                return None
        if tside == "R":
            txt, emits, _m = self._mp_row_output(r)
            if not emits:
                return None
        else:
            tk = r["lk"] if tside == "A" else r["rk"]
            txt = r["lt"] if tside == "A" else r["rt"]
            if tk == "spacer" or not txt:
                if placeholder:
                    return (0, 1)     # 空白占位行高亮
                return None
            if tside == side:
                return (i1, i2)
        if txt == st:
            return (min(i1, len(txt)), min(i2, len(txt)))
        if side == "A" and tside == "B":
            ops = r["lw"] or word_ops(st, txt)
        elif side == "B" and tside == "A":
            ops = self._mp_rev_ops(r["lw"]) if r["lw"] else word_ops(st, txt)
        else:       # ↔ R：源侧文本 ↔ 结果文本
            # v3.48.32（MAP-DEEP）：结果文本是合并产物，与 A/B 的比对同样
            # 可能超 word_ops 的 WORD_MAX 护栏（AI 长段落常见：实测结果
            # 169 字 vs 右栏 405 字）。口径必须与渲染层一致走 word_ops_deep
            # （短行时它内部委托 word_ops，短行行为不变），否则返回 None
            # 退 map_range_long 比例估位 → 映射与显示对不上。
            ops = word_ops_deep(st, txt)
        if ops:
            return map_range(ops, i1, i2)
        return map_range_long(st, txt, i1, i2)

    def _mp_queue_sel(self, side):
        """selectionChanged → 记录来源框并合并到 0ms 单发定时器
        （拖选过程中高频触发，逐次全量映射浪费且闪烁）。"""
        self._mp_sel_pending = side
        self._mp_sel_timer.start()

    def _mp_sel_flush(self):
        side = self._mp_sel_pending
        self._mp_sel_pending = None
        if side:
            try:
                self._mp_sync_selection(side)
            except Exception:       # noqa: BLE001 联动失败不影响主流程
                pass

    def _mp_result_blocks(self):
        """结果框块号 → 行流下标映射（被删除的行不输出、不占块；
        手工编辑增删行时以行流现状为准）。"""
        return [i for i, r in enumerate(self._mp_rows)
                if self._mp_row_output(r)[1]]

    def _mp_result_spans(self):
        """结果框选区 → [(行号, i1, i2)]（i1/i2 为该行输出文本内字符
        区间）。选区落在文档尾哨兵空块时贴靠最后一行。无有效选区返回
        None。"""
        cur = self.pane_merge.textCursor()
        if not cur.hasSelection():
            return None
        s, e = cur.selectionStart(), cur.selectionEnd()
        doc = self.pane_merge.document()
        blocks = self._mp_result_blocks()
        if not blocks:
            return None
        c1 = QTextCursor(doc)
        c1.setPosition(min(s, e))
        c2 = QTextCursor(doc)
        c2.setPosition(max(s, e))
        b1, b2 = c1.blockNumber(), c2.blockNumber()
        last = len(blocks) - 1
        spans = []
        for bi in range(min(b1, last), min(b2, last) + 1):
            k = blocks[bi]
            txt = self._mp_row_output(self._mp_rows[k])[0]
            i1 = c1.positionInBlock() if bi == b1 else 0
            i2 = c2.positionInBlock() if bi == b2 else len(txt)
            i1 = max(0, min(i1, len(txt)))
            i2 = max(0, min(i2, len(txt)))
            if i2 > i1:
                spans.append((k, i1, i2))
        return spans or None

    def _mp_sync_selection(self, side):
        """选中联动（v3.48.29 三框双向）：任一框（左 / 右 / 下方结果框）
        选中文字，另两框中对应内容浅蓝底同步高亮；对应行为空白占位
        （对侧 spacer）时高亮其空白占位行——Beyond Compare 式逐行对位
        （extraSelections 实现，不改文本与选区本身；清空选区即清除）。
        源框自身的残留联动高亮一并清除（其选区本身可见）。"""
        if self._mp_busy or not self._mp_rows or not self._mp_row_cur:
            return
        if side == "A":
            src = self.pane_a
            targets = (("B", self.pane_b), ("R", self.pane_merge))
        elif side == "B":
            src = self.pane_b
            targets = (("A", self.pane_a), ("R", self.pane_merge))
        else:
            src = self.pane_merge
            targets = (("A", self.pane_a), ("B", self.pane_b))
        try:
            spans = (self._mp_result_spans() if side == "R"
                     else self._mp_frag_spans(src, side))
        except Exception:           # noqa: BLE001
            spans = None
        try:
            src.setExtraSelections([])
        except Exception:           # noqa: BLE001
            pass
        for tside, w in targets:
            sels = []
            if spans:
                fmt = QTextCharFormat()
                fmt.setBackground(QColor(self._mp_colors["sel"]))
                for k, i1, i2 in spans:
                    if not (0 <= k < len(self._mp_rows)):
                        continue
                    m = self._mp_map_span(self._mp_rows[k], side,
                                          i1, i2, tside)
                    if not m:
                        continue
                    j1, j2 = m
                    if j2 <= j1:
                        continue
                    cur = QTextCursor(w.document())
                    if tside == "R":
                        base = self._mp_row_cur[k].position()
                        cur.setPosition(min(base + j1,
                                            w.document().characterCount()))
                        cur.setPosition(min(base + j2,
                                            w.document().characterCount()),
                                        QTextCursor.KeepAnchor)
                    else:
                        blk = w.document().findBlockByNumber(k)
                        cur.setPosition(blk.position() + j1)
                        cur.setPosition(blk.position() + j2,
                                        QTextCursor.KeepAnchor)
                    if cur.position() > cur.anchor():
                        es = QTextEdit.ExtraSelection()
                        es.cursor = cur
                        es.format = fmt
                        sels.append(es)
            w.setExtraSelections(sels)

    def _mp_sync_scroll(self, src):
        """三框滚动联动：按首个可见行（行流下标）同步——三框均为「每行
        一个渲染块」，按行同步比按比例更精确（长行自动换行时两侧行高
        不同，比例同步会越滚越歪）。
        v3.48.29：结果框中被删除的行不占块，块号 ↔ 行流下标经
        _mp_result_blocks 双向折算（源为结果框：块号→行号；目标为结果
        框：行号→最近存在行，越界取末行）。"""
        if self._mp_busy or self._mp_scroll_lock:
            return
        self._mp_scroll_lock = True
        try:
            cur = src.cursorForPosition(src.viewport().rect().topLeft())
            blk = cur.blockNumber()
            rblocks = None
            if src is self.pane_merge:
                rblocks = self._mp_result_blocks()
                if rblocks:
                    blk = rblocks[min(blk, len(rblocks) - 1)]
            for t in (self.pane_a, self.pane_b, self.pane_merge):
                if t is src:
                    continue
                try:
                    if t is self.pane_merge:
                        if rblocks is None:
                            rblocks = self._mp_result_blocks()
                        if not rblocks:
                            continue
                        row = rblocks[-1]
                        for rowi in rblocks:
                            if rowi >= blk:
                                row = rowi
                                break
                        cc = QTextCursor(self._mp_row_cur[row])
                    else:
                        doc = t.document()
                        b = doc.findBlockByNumber(
                            max(0, min(blk, doc.blockCount() - 1)))
                        cc = QTextCursor(b)
                    y = t.cursorRect(cc).top() + t.verticalScrollBar().value()
                except Exception:       # noqa: BLE001
                    continue
                sb = t.verticalScrollBar()
                sb.blockSignals(True)
                sb.setValue(int(max(0, min(y, sb.maximum()))))
                sb.blockSignals(False)
        finally:
            self._mp_scroll_lock = False

    # ---------- 状态行 ----------
    def _mp_stat_extra(self):
        """子类追加到状态行末尾的文案（如「未捕获到原文选区」警告）。"""
        return ""

    def _mp_update_stat(self):
        same = sum(1 for r in self._mp_rows if r["lk"] == "ctx")
        diff_hunks = len(self._mp_diff_firsts)
        diff_rows = sum(1 for r in self._mp_rows if self._mp_adoptable(r))
        merged = sum(1 for r in self._mp_rows
                     if r.get("choice") is not None
                     or r.get("override") is not None)
        if diff_hunks == 0:
            txt = "两个版本内容一致，无需合并。"
        else:
            txt = ("相同 %d 行 · 差异 %d 处（%d 行，已合并 %d 行）　—　"
                   "任意一框选中文字，另两框对应内容浅蓝高亮；双击或右键"
                   "「合并所选内容」仅合并所选，右键「选中采用（左/右）」"
                   "可把所选范围替换为另一侧对应内容。"
                   % (same, diff_hunks, diff_rows, merged))
        txt += self._mp_stat_extra()
        self.mp_stat.setText(txt)

    def _mp_flash(self, msg):
        """状态行临时反馈（2.5s 后恢复统计文案）——合并无实际改动时
        给出可见提示，杜绝「静默无响应」。"""
        self.mp_stat.setText(msg)
        QTimer.singleShot(2500, self._mp_update_stat)

    # ---------- 交互（事件过滤由子类 eventFilter 转发） ----------
    def _mp_ctx_menu(self, obj, side, ev):
        """右键菜单（v3.48.29）：有选区时「合并所选内容」（采用所选侧）
        +「选中采用（左）/（右）」（把所选范围替换为指定侧对应内容，
        指定侧无内容 = 删除）；末尾恒有「全部采用左 / 右」（所有差异行
        整行采用该侧）。"""
        gpos = (ev.globalPos() if hasattr(ev, "globalPos")
                else ev.globalPosition().toPoint())
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        spans = self._mp_frag_spans(obj, side)   # 右键不清选区，可直接读
        act_frag = (menu.addAction(T("合并所选内容", "Merge Selected Content")) if spans else None)
        act_sl = act_sr = None
        if spans:
            act_sl = menu.addAction(T("选中采用（左）", "Use Selected (Left)"))
            act_sr = menu.addAction(T("选中采用（右）", "Use Selected (Right)"))
        act_left = menu.addAction(self.mp_all_left_text)
        act_right = menu.addAction(self.mp_all_right_text)
        chosen = menu.exec(gpos)
        if act_frag is not None and chosen is act_frag:
            if not self._mp_frag_merge(spans, side):
                self._mp_flash("所选内容与合并结果一致，无需改动。")
        elif act_sl is not None and chosen is act_sl:
            if not self._mp_sel_adopt(spans, side, "A"):
                self._mp_flash("所选内容与合并结果一致，无需改动。")
        elif act_sr is not None and chosen is act_sr:
            if not self._mp_sel_adopt(spans, side, "B"):
                self._mp_flash("所选内容与合并结果一致，无需改动。")
        elif chosen is act_left:
            self._mp_adopt("A", self._mp_all_rows())
        elif chosen is act_right:
            self._mp_adopt("B", self._mp_all_rows())

    def _mp_event_filter(self, obj, ev):
        """选中文字后双击 = 仅合并所选；右键弹「合并所选内容」。
        v3.48.28 修复「双击经常无响应」：
        · 无选区双击不再吞事件（交回 Qt 执行默认「双击选词」，选词后
          再双击一次即合并该词 —— 旧版恒 return True 把 Qt 选词也吞掉，
          导致双击选词完全失效）；
        · 双击合并无实际改动（所选与结果一致）时交回 Qt 并给出状态行
          反馈，不再静默无响应；
        · 按下瞬间快照选区（press1 会塌陷 widget 选区）机制不变。
        返回 True 表示已处理；None 交回子类 super().eventFilter。"""
        pa, pb = self.pane_a.viewport(), self.pane_b.viewport()
        if obj is pa or obj is pb:
            side = "A" if obj is pa else "B"
            pane = self.pane_a if obj is pa else self.pane_b
            if (ev.type() == QEvent.MouseButtonPress
                    and ev.button() == Qt.LeftButton):
                self._mp_press_row = self._mp_row_from_pos(
                    pane, ev.position().toPoint())
                sel = pane.textCursor()
                self._mp_press_sel = (
                    (sel.selectionStart(), sel.selectionEnd())
                    if sel.hasSelection() else None)
                return False
            if (ev.type() == QEvent.MouseButtonDblClick
                    and ev.button() == Qt.LeftButton):
                sel = self._mp_press_sel
                self._mp_press_sel = None
                if sel is None:
                    cur = pane.textCursor()
                    if cur.hasSelection():
                        sel = (cur.selectionStart(), cur.selectionEnd())
                if sel:
                    spans = self._mp_frag_spans(pane, side, sel=sel)
                    if spans and self._mp_frag_merge(spans, side):
                        return True     # 实际合并发生：吞掉防止误选词
                    self._mp_flash("所选内容与合并结果一致，无需改动。")
                return None             # 其余情况交回 Qt（双击选词）
            if ev.type() == QEvent.ContextMenu:
                self._mp_ctx_menu(pane, side, ev)
                return True
        return None

    # ---------- 结果 ----------
    def _mp_get_result_text(self):
        """合并结果框当前内容（应用 / 保存 / 确认替换的来源）。

        v3.48.31（SENT-VIEW）：句级视图下每个句单愿在结果框占一个块，直接
        toPlainText 会让句与句之间多出 **本不属于原文** 的换行 —— 按行流上
        的 sep 重建（同原行的句间无分隔）。手工在结果框增删造成的行数与行
        流不符时退回旧语义（"\\n".join），保证手工编辑不丢。"""
        parts = self.pane_merge.toPlainText().split("\n")
        while parts and parts[-1] == "":
            parts.pop()
        emit = [r for r in (self._mp_rows or [])
                if self._mp_row_output(r)[1]]
        if getattr(self, "_mp_sent", False) and len(parts) == len(emit):
            out = []
            for ln, r in zip(parts, emit):
                out.append(ln)
                out.append(r.get("sep", "\n"))
            return "".join(out).rstrip("\n")
        return "\n".join(parts)
