# -*- coding: utf-8 -*-
"""v3.48.27（FRAG-ONLY）探针：统一差异引擎 diffmerge + 三处对话框复用。

D1  line_key_raw / line_key_md（Markdown 容错：剥标记与空白 → 仅格式差异收敛 equal）
D2  word_ops：配对行字符级 opcodes / 一致 None / 超 WORD_MAX None
D3  build_hunks：equal/replace/delete/insert hunk 流
D4  build_rows：replace 1:1 行配对（del+add 共用词级 opcodes）/ delete→spacer / insert→spacer
D5  行输出规则（_mp_row_output 语义）：equal 恒输出含空行；
    (del,spacer) 默认取 B = 删行不残留空行；整行采用 A / B 可逆
D6  AIFragmentDialog 行级视图：4 行流 / 1 处差异 / 默认结果=AI 回复 / 词级 span
D7  MergeDialog 行级视图：默认=最新版本(B) / 整行采用可逆 / 手工编辑保留 / 按钮简化
D8  DiffDialog 引擎投影：行元组 (kl,tl,hl,kr,tr,hr) 格式保持 + 计数
D10 调色板：亮 / 暗两套齐全（仅差异文字着色，无 add_w/del_w 双档）
D11 选区合并：map_range / 块号不变式 / 词级对齐部分合并 / 删除行写回 / 双击快照
D12 v3.48.27 新语义：配对行无整行底色 / 结果默认黄底 / 片段来源着色（红/绿）
    / 整行完整合并来源色 / 右键菜单项（合并所选 + 全部采用，无恢复默认）
    / 双击无选区不动作 / 右键全部采用
"""
import sys, os
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("MDEDITOR_SKIP_DRAFT", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QPoint, Qt as _Qt
from PySide6.QtGui import QTextCursor

app = QApplication(sys.argv)

import diffmerge
from diffmerge import (line_key_raw, line_key_md, word_ops, build_hunks,
                       build_rows, WORD_MAX)

fails = []
out_lines = []
def check(name, cond, detail=""):
    ln = ("PASS " if cond else "FAIL ") + name + \
         ("  | " + str(detail) if detail else "")
    print(ln)
    out_lines.append(ln)
    if not cond:
        fails.append(name)

# ---------- D1：行键 ----------
check("D1_RAW_KEY", line_key_raw(" a b ") == " a b ")
check("D1_MD_KEY_FMT", line_key_md("**加粗** 文本") == line_key_md("加粗文本"),
      repr(line_key_md("**加粗** 文本")))
check("D1_MD_KEY_WS", line_key_md("a   b") == line_key_md("ab"))
check("D1_MD_KEY_EMPTY", line_key_md("") == "" and line_key_md(None) == "")

# ---------- D2：词级 opcodes ----------
ops = word_ops("The quick brown fox", "The quick red fox")
check("D2_WORD_OPS", ops is not None
      and any(t == "replace" for t, *_ in ops), ops)
check("D2_SAME_NONE", word_ops("abc", "abc") is None)
long_line = "x" * (WORD_MAX + 1)
check("D2_MAX_GUARD", word_ops(long_line, long_line + "y") is None)
cjk = word_ops("黑发不知勤学早", "白首方悔读书迟")
check("D2_CJK", cjk is not None and cjk[0][0] == "equal" or cjk is not None, cjk)

# ---------- D3：hunk 流 ----------
A = ["line1", "A-only", "common", "keep"]
B = ["line1", "B-new", "common", "keep"]
hunks = build_hunks(A, B)
kinds = [h["kind"] for h in hunks]
check("D3_HUNKS", kinds == ["equal", "replace", "equal"], kinds)
check("D3_HUNK_FIELDS", hunks[1]["a"] == ["A-only"] and hunks[1]["b"] == ["B-new"]
      and hunks[1]["ai"] == 1 and hunks[1]["bi"] == 1, hunks[1])
hd = build_hunks(["line1", "del-a", "common"], ["line1", "common"])
check("D3_DELETE_KIND", [h["kind"] for h in hd][1] == "delete")
hi = build_hunks(["line1", "common"], ["line1", "ins-a", "common"])
check("D3_INSERT_KIND", [h["kind"] for h in hi][1] == "insert")

# ---------- D4：行流 ----------
rows = build_rows(hunks)
check("D4_ROW_COUNT", len(rows) == 4, len(rows))
check("D4_REPLACE_PAIR", rows[1]["lk"] == "del" and rows[1]["rk"] == "add"
      and rows[1]["lt"] == "A-only" and rows[1]["rt"] == "B-new", rows[1])
check("D4_WORD_OPS_SHARED", rows[1]["lw"] is not None
      and rows[1]["lw"] is rows[1]["rw"])
check("D4_CTX_ROWS", rows[0]["lk"] == "ctx" and rows[0]["rk"] == "ctx"
      and rows[3]["rt"] == "keep")
rd = build_rows(hd)
check("D4_DELETE_SPACER", rd[1]["lk"] == "del" and rd[1]["rk"] == "spacer"
      and rd[1]["rt"] == "")
ri = build_rows(hi)
check("D4_INSERT_SPACER", ri[1]["lk"] == "spacer" and ri[1]["rk"] == "add"
      and ri[1]["lt"] == "")

# ---------- D5：行输出规则（借 AIFragmentDialog 实测 _mp_row_output） ----------
from ai_pane import AIFragmentDialog

class StubBridge:
    def replace_selection(self, *a, **k):
        pass
    def insert_at_caret(self, *a, **k):
        pass

ORIG = "\n".join(A)
REPLY = "\n".join(B)
dlg = AIFragmentDialog(None, StubBridge(), orig_text=ORIG, reply_text=REPLY)

# D5a：equal 行恒输出（含空行）—— 构造带空行的输入
d_empty = AIFragmentDialog(None, StubBridge(),
                           orig_text="a\n\nb", reply_text="a\n\nb")
check("D5_EQUAL_BLANK_KEPT", d_empty.get_result_text() == "a\n\nb",
      repr(d_empty.get_result_text()))
# D5b：(del,spacer) 默认取 B = 删行不残留空行
d_del = AIFragmentDialog(None, StubBridge(),
                         orig_text="line1\ndel-a\ncommon",
                         reply_text="line1\ncommon")
check("D5_DEL_DEFAULT_B", d_del.get_result_text() == "line1\ncommon",
      repr(d_del.get_result_text()))
d_del._mp_adopt("A", [1])
check("D5_DEL_ADOPT_A", d_del.get_result_text() == "line1\ndel-a\ncommon",
      repr(d_del.get_result_text()))
# D5c：(spacer,add) 整行采用左 = 删行；采用右 = 还原
d_ins = AIFragmentDialog(None, StubBridge(),
                         orig_text="line1\ncommon",
                         reply_text="line1\nins-a\ncommon")
d_ins._mp_adopt("A", d_ins._mp_all_rows())
check("D5_INS_ADOPT_A", d_ins.get_result_text() == "line1\ncommon",
      repr(d_ins.get_result_text()))
d_ins._mp_adopt("B", d_ins._mp_all_rows())
check("D5_INS_ADOPT_B", d_ins.get_result_text() == "line1\nins-a\ncommon",
      repr(d_ins.get_result_text()))

# ---------- D6：AIFragmentDialog 行级视图 ----------
rws = dlg._mp_rows
check("D6_FRAG_ROWS", len(rws) == 4 and rws[1]["lk"] == "del"
      and rws[1]["rk"] == "add", [(r["lk"], r["rk"]) for r in rws])
check("D6_FRAG_DEFAULT", dlg.get_result_text() == REPLY
      and rws[1].get("choice") is None, repr(dlg.get_result_text()))
check("D6_DIFF_FIRSTS", dlg._mp_diff_firsts == [1], dlg._mp_diff_firsts)
ha = dlg.pane_a.toHtml(); hb = dlg.pane_b.toHtml()
# v3.48.27：配对行只给词级 span 上色（深红/深绿），整行不再铺旧浅色底
# （toHtml 会把颜色规范化为小写，比较一律 casefold）
check("D6_WORD_SPAN_COLORS", "#f5c4b3" in ha.lower() and "#9fe1cb" in hb.lower())
check("D6_NO_LINE_BG", "#ffe5e5" not in ha.lower()
      and "#e6ffec" not in hb.lower())
dlg._mp_adopt("A", [1])
check("D6_CHECK_MARK", "\u2713" in dlg.pane_a.toHtml())

# ---------- D7：MergeDialog 行级视图 ----------
import dialogs

class FakeWin(QWidget):
    _theme = "light"
    def list_history(self, path):
        return []
    def apply_merged_text(self, t):
        return True

md = dialogs.MergeDialog(FakeWin())
md.show_merge("t", ORIG, REPLY, "快照A", "快照B")
check("D7_MERGE_DEFAULT", md.pane_merge.toPlainText().rstrip("\n") == REPLY,
      repr(md.pane_merge.toPlainText()))
check("D7_MERGE_ROWS", len(md._mp_rows) == 4
      and len(md._mp_diff_firsts) == 1)
di = md._mp_diff_firsts[0]
md._mp_adopt("A", [di])
check("D7_MERGE_ADOPT_A",
      md.pane_merge.toPlainText().rstrip("\n") == ORIG,
      repr(md.pane_merge.toPlainText()))
c = md.pane_merge.textCursor(); c.setPosition(0); c.insertText("X")
md._mp_adopt("B", [di])
check("D7_MERGE_MANUAL_KEPT",
      md.pane_merge.toPlainText().rstrip("\n") == "X" + REPLY,
      repr(md.pane_merge.toPlainText()))
# 界面简化：仅功能性按钮，无全部采用按钮（收进右键菜单）、无导航
check("D7_TAIL_BUTTONS", hasattr(md, "b_apply") and hasattr(md, "b_save")
      and not hasattr(md, "b_all_left") and not hasattr(md, "b_all_right")
      and not hasattr(md, "mp_btn_prev") and not hasattr(md, "mp_nav_lbl"))

# ---------- D8：DiffDialog 引擎投影 ----------
class FakeWin2(QWidget):
    _theme = "light"
    class _settings:      # DiffDialog.__init__ 只用 .value / .setValue
        @staticmethod
        def value(k, d=None):
            return d
        @staticmethod
        def setValue(k, v):
            pass
    def list_history(self, path):
        return []
    def apply_merged_text(self, t):
        return True

d0 = dialogs.DiffDialog(FakeWin2())
built, add, dele, same = d0._build_rows(A, B, "#F5C4B3", "#9FE1CB")
check("D8_DIFF_ROWS_FMT", len(built) == 4
      and all(len(t) == 6 for t in built), len(built))
check("D8_DIFF_COUNTS", add == 1 and dele == 1 and same == 3,
      (add, dele, same))
check("D8_DIFF_KINDS", built[1][0] == "del" and built[1][3] == "add"
      and isinstance(built[1][2], str) and "span" in built[1][2],
      (built[1][0], built[1][3], str(built[1][2])[:40]))
check("D8_CTX_NO_SPAN", built[0][2] is None and built[0][5] is None)


# ---------- D11：选区合并（v3.48.26 起） ----------
from diffmerge import map_range

def _select(pane, row, i1, i2):
    blk = pane.document().findBlockByNumber(row)
    c = pane.textCursor()
    c.setPosition(blk.position() + i1)
    c.setPosition(blk.position() + i2, QTextCursor.KeepAnchor)
    pane.setTextCursor(c)

def _bg_at(edit, pos):
    """结果框 pos 处字符的背景色（#rrggbb）或 None（无底色）。
    QTextCursor.charFormat() 取「光标前一字符」的格式 → 探测位取 pos+1。"""
    c = edit.textCursor()
    c.setPosition(pos + 1)
    b = c.charFormat().background()
    return b.color().name() if b.style() != _Qt.NoBrush else None

ops2 = word_ops("aXbYc", "a1b2c")
check("D11_MAP_RANGE", map_range(ops2, 1, 2) == (1, 2)
      and map_range(ops2, 3, 4) == (3, 4)
      and map_range(ops2, 0, 5) == (0, 5),
      (map_range(ops2, 1, 2), map_range(ops2, 3, 4), map_range(ops2, 0, 5)))

# 空行也产块（块号 = 行号不变式）
d_bl = AIFragmentDialog(None, StubBridge(), orig_text="a\n\nb",
                        reply_text="a\n\nb")
check("D11_BLOCK_INVARIANT", d_bl.pane_a.document().blockCount() == 3,
      d_bl.pane_a.document().blockCount())

# 词级对齐部分合并：A「aXbYc」B「a1b2c」，只取 A 的「X」→ 结果 aXb2c（Y 处仍取 B）
d_f = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                       reply_text="a1b2c")
_select(d_f.pane_a, 0, 1, 2)
sp = d_f._mp_frag_spans(d_f.pane_a, "A")
check("D11_SPANS", sp == [(0, 1, 2)], sp)
d_f._mp_frag_merge(sp, "A")
check("D11_FRAG_PARTIAL", d_f.get_result_text() == "aXb2c"
      and d_f._mp_rows[0].get("override") == "aXb2c",
      repr(d_f.get_result_text()))
# 在片段合并结果基础上，再从 B 侧取回「1」→ 结果回 a1b2c
_select(d_f.pane_b, 0, 1, 2)
d_f._mp_frag_merge(d_f._mp_frag_spans(d_f.pane_b, "B"), "B")
check("D11_FRAG_B_BACK", d_f.get_result_text() == "a1b2c",
      repr(d_f.get_result_text()))
check("D11_PENCIL_MARK", "\u270e" in d_f.pane_a.toHtml())
# 整行采用清 override；采用另一侧可逆
d_f._mp_adopt("A", [0])
check("D11_ADOPT_CLEARS_OVERRIDE", d_f._mp_rows[0].get("override") is None
      and d_f.get_result_text() == "aXbYc",
      repr(d_f.get_result_text()))
d_f._mp_adopt("B", [0])
check("D11_ADOPT_B_BACK", d_f.get_result_text() == "a1b2c"
      and d_f._mp_rows[0].get("choice") == "B"
      and d_f._mp_rows[0].get("override") is None)

# 删除行片段合并：仅把所选文字写回该行
d_fd = AIFragmentDialog(None, StubBridge(),
                        orig_text="line1\ndel-a\ncommon",
                        reply_text="line1\ncommon")
_select(d_fd.pane_a, 1, 1, 4)     # "el-"
d_fd._mp_frag_merge(d_fd._mp_frag_spans(d_fd.pane_a, "A"), "A")
check("D11_FRAG_DELETED", d_fd.get_result_text() == "line1\nel-\ncommon",
      repr(d_fd.get_result_text()))

# 相同行选区 = 无动作
_select(d_bl.pane_a, 0, 0, 1)
d_bl._mp_frag_merge(d_bl._mp_frag_spans(d_bl.pane_a, "A"), "A")
check("D11_CTX_NOOP", d_bl.get_result_text() == "a\n\nb"
      and d_bl._mp_rows[0].get("override") is None)

# 双击路径：有按下时选区快照 = 仅合并所选
d_d = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                       reply_text="a1b2c")
blk0 = d_d.pane_a.document().findBlockByNumber(0)
d_d._mp_press_sel = (blk0.position() + 1, blk0.position() + 2)
d_d._mp_press_row = 0
from PySide6.QtGui import QMouseEvent, QContextMenuEvent
from PySide6.QtCore import QPointF, QEvent as _QE2
evd = QMouseEvent(_QE2.MouseButtonDblClick, QPointF(8.0, 4.0),
                  _Qt.LeftButton, _Qt.LeftButton, _Qt.NoModifier)
handled = d_d.eventFilter(d_d.pane_a.viewport(), evd)
check("D11_DBLCLICK_FRAG", handled is True
      and d_d.get_result_text() == "aXb2c", repr(d_d.get_result_text()))

# ---------- D10：调色板 ----------
pl = diffmerge._mp_palette("light"); pd = diffmerge._mp_palette("dark")
need = ("add", "del", "spacer", "unresolved",
        "bd_add", "bd_del", "bd_gray", "txt", "ctx")
check("D10_PALETTE", all(k in pl for k in need) and all(k in pd for k in need)
      and pl["add"] != pd["add"] and "add_w" not in pl and "del_w" not in pl)

# ---------- D12：v3.48.27 —— 差异仅标差异文字 / 来源着色 / 简化交互 ----------
# a) 配对行不铺整行底色，仅词级 span（D6 已验 HTML；此处验结果框着色语义）
d12 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                       reply_text="a1b2c")
p0 = d12._mp_row_cur[0].position()
check("D12_DEFAULT_SAME_NOBG", _bg_at(d12.pane_merge, p0) is None,
      _bg_at(d12.pane_merge, p0))
check("D12_DEFAULT_CONFLICT_YELLOW",
      _bg_at(d12.pane_merge, p0 + 1) == "#fff3cd",
      _bg_at(d12.pane_merge, p0 + 1))
# b) 片段合并自 A → 该片段红底，行内其余保持黄底（未合并部分）
# （QColor.name() 返回小写，期望值一律小写）
_select(d12.pane_a, 0, 1, 2)
_sp12 = d12._mp_frag_spans(d12.pane_a, "A")
d12._mp_frag_merge(_sp12, "A")
check("D12_FRAG_SRC_RED", _bg_at(d12.pane_merge, p0 + 1) == "#f5c4b3",
      _bg_at(d12.pane_merge, p0 + 1))
check("D12_REST_YELLOW", _bg_at(d12.pane_merge, p0 + 3) == "#fff3cd",
      _bg_at(d12.pane_merge, p0 + 3))
# c) 再从 B 取回「1」→ 整行恰为 B 完整文本 → 整行绿底（来源标识）
_select(d12.pane_b, 0, 1, 2)
d12._mp_frag_merge(d12._mp_frag_spans(d12.pane_b, "B"), "B")
check("D12_FULL_SRC_GREEN", _bg_at(d12.pane_merge, p0 + 1) == "#9fe1cb",
      _bg_at(d12.pane_merge, p0 + 1))
# d) 整行采用（选整行片段合并等价路径）→ 整行红底
d14 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                       reply_text="a1b2c")
d14._mp_adopt("A", [0])
check("D14_ADOPT_A_RED", _bg_at(d14.pane_merge, p0) == "#f5c4b3",
      _bg_at(d14.pane_merge, p0))

# e) 右键菜单项：有选区 = 合并所选内容 + 全部采用×2；无选区 = 仅全部采用×2
class _FakeMenu12:
    instances = []
    def __init__(self, *a, **k):
        self.acts = []
        _FakeMenu12.instances.append(self)
    def addAction(self, t):
        self.acts.append(t)
        return t
    def exec(self, *a, **k):
        return None

import PySide6.QtWidgets as _QW12
_orig_menu = _QW12.QMenu
_QW12.QMenu = _FakeMenu12
try:
    cev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                            QPoint(1, 1), QPoint(1, 1))
    d13 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                           reply_text="a1b2c")
    _select(d13.pane_a, 0, 1, 2)      # 有选区
    d13.eventFilter(d13.pane_a.viewport(), cev)
    t1 = _FakeMenu12.instances[-1].acts
    check("D12_CTX_WITH_SEL", t1 == ["合并所选内容", "选中采用（左）",
                                     "选中采用（右）", "全部采用左(原文)",
                                     "全部采用右(AI)"], t1)
    d13b = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                            reply_text="a1b2c")
    d13b.eventFilter(d13b.pane_b.viewport(), cev)   # 无选区
    t2 = _FakeMenu12.instances[-1].acts
    check("D12_CTX_NO_SEL", t2 == ["全部采用左(原文)", "全部采用右(AI)"], t2)
    # f) 右键「全部采用右」→ 整行采用 B、绿底
    class _FakeMenuExec:
        pick = 1
        def __init__(self, *a, **k):
            self.acts = []
        def addAction(self, t):
            self.acts.append(t)
            return t
        def exec(self, *a, **k):
            return self.acts[self.pick]
    _QW12.QMenu = _FakeMenuExec    # 第 3 项 = 全部采用右
    d15 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                           reply_text="a1b2c")
    d15.eventFilter(d15.pane_b.viewport(), cev)
    check("D12_CTX_ADOPT_ALL_B", d15.get_result_text() == "a1b2c"
          and d15._mp_rows[0].get("choice") == "B"
          and _bg_at(d15.pane_merge, p0) == "#9fe1cb",
          repr(d15.get_result_text()))
finally:
    _QW12.QMenu = _orig_menu

# g) 双击无选区 = 不动作（不整行采用）
d_d2 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                        reply_text="a1b2c")
d_d2._mp_press_sel = None
d_d2._mp_press_row = 0
h2 = d_d2.eventFilter(d_d2.pane_a.viewport(), evd)
check("D12_DBLCLICK_NOSEL_NOOP", h2 is not True
      and d_d2.get_result_text() == "a1b2c"
      and d_d2._mp_rows[0].get("choice") is None
      and d_d2._mp_rows[0].get("override") is None,
      repr(d_d2.get_result_text()))

# h) 右键无「恢复默认」
check("D12_NO_RESET_ITEM", all("恢复默认" not in t for t in (t1, t2)))


# ========== v3.48.28（LINK-3）：三框联动（选中 / 滚动） ==========
from PySide6.QtCore import QPoint as _QPoint13

# a) 左栏选 "X" → 右栏与结果框对应区间浅蓝高亮
d13 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                       reply_text="a1b2c")
_select(d13.pane_a, 0, 1, 2)
d13._mp_sync_selection("A")
exb = d13.pane_b.extraSelections()
exm = d13.pane_merge.extraSelections()
check("D13_SEL_SYNC_B", len(exb) == 1
      and exb[0].cursor.anchor() == 1 and exb[0].cursor.position() == 2,
      [(e.cursor.anchor(), e.cursor.position()) for e in exb])
check("D13_SEL_SYNC_R", len(exm) == 1
      and exm[0].cursor.anchor() == 1 and exm[0].cursor.position() == 2,
      [(e.cursor.anchor(), e.cursor.position()) for e in exm])

# b) 右栏选 "1"（反向映射）→ 左栏对应 "X"
_select(d13.pane_b, 0, 1, 2)
d13._mp_sync_selection("B")
exa = d13.pane_a.extraSelections()
check("D13_SEL_SYNC_A_REV", len(exa) == 1
      and exa[0].cursor.anchor() == 1 and exa[0].cursor.position() == 2,
      [(e.cursor.anchor(), e.cursor.position()) for e in exa])

# c) 清空选区 → 高亮清除
_select(d13.pane_b, 0, 0, 0)
d13._mp_sync_selection("B")
check("D13_SEL_CLEAR", d13.pane_a.extraSelections() == []
      and d13.pane_merge.extraSelections() == [])

# d) ctx 行选区映射（两侧文本一致 → 同偏移）
d13b = AIFragmentDialog(None, StubBridge(),
                        orig_text="head\nA-only\ntail",
                        reply_text="head\nB-new\ntail")
_select(d13b.pane_a, 0, 1, 3)   # "head" 行（ctx）
d13b._mp_sync_selection("A")
exb2 = d13b.pane_b.extraSelections()
check("D13_SEL_SYNC_CTX", len(exb2) == 1
      and exb2[0].cursor.anchor() == 1 and exb2[0].cursor.position() == 3,
      [(e.cursor.anchor(), e.cursor.position()) for e in exb2])

# e) 滚动联动：30 行文档，滚左栏 → 右栏 / 结果框首可见行一致
_lines_a = "\n".join("row-%02d" % i for i in range(30))
_lines_b = "\n".join(("row-%02d" % i) if i != 10 else "CHG-10"
                     for i in range(30))
d13c = AIFragmentDialog(None, StubBridge(), orig_text=_lines_a,
                        reply_text=_lines_b)


def _first_block(w):
    return w.cursorForPosition(_QPoint13(0, 0)).blockNumber()


d13c.show()
app.processEvents()
sb_a = d13c.pane_a.verticalScrollBar()
sb_a.setValue(sb_a.maximum())
app.processEvents()
check("D13_SCROLL_SYNC_B", _first_block(d13c.pane_b) >= 10,
      "first_b=%d" % _first_block(d13c.pane_b))
check("D13_SCROLL_SYNC_R", _first_block(d13c.pane_merge) >= 10,
      "first_r=%d" % _first_block(d13c.pane_merge))
sb_a.setValue(0)
app.processEvents()
check("D13_SCROLL_SYNC_BACK", _first_block(d13c.pane_b) <= 2
      and _first_block(d13c.pane_merge) <= 2,
      "first_b=%d first_r=%d" % (_first_block(d13c.pane_b),
                                 _first_block(d13c.pane_merge)))

# ========== v3.48.29（SEL-3WAY）：三框双向联动 / 占位行 / 选中采用 ==========
_a29 = "head\nX-old\nA-extra\ncommon"
_b29 = "head\nX-new\ncommon\nB-added"
d14 = AIFragmentDialog(None, StubBridge(), orig_text=_a29,
                       reply_text=_b29)
_pair29 = next(i for i, r in enumerate(d14._mp_rows)
               if r["lk"] == "del" and r["rk"] == "add")
_del29 = next(i for i, r in enumerate(d14._mp_rows)
              if r["lk"] == "del" and r["rk"] == "spacer")
_add29 = next(i for i, r in enumerate(d14._mp_rows)
              if r["lk"] == "spacer" and r["rk"] == "add")

# a) 结果框选区 → 左右栏联动（直接调用）
_select(d14.pane_merge, _pair29, 0, 4)     # "X-ne"
d14._mp_sync_selection("R")
exa = d14.pane_a.extraSelections()
exb = d14.pane_b.extraSelections()
check("D14_R_SYNC_A", len(exa) == 1 and exa[0].cursor.anchor() == 5
      and exa[0].cursor.position() == 10,
      [(e.cursor.anchor(), e.cursor.position()) for e in exa])
check("D14_R_SYNC_B", len(exb) == 1 and exb[0].cursor.anchor() == 5
      and exb[0].cursor.position() == 9,
      [(e.cursor.anchor(), e.cursor.position()) for e in exb])

# b) 真实信号路径（selectionChanged → 0ms 去抖 flush）
_select(d14.pane_a, _pair29, 0, 5)
app.processEvents()
check("D14_REAL_SIGNAL", len(d14.pane_merge.extraSelections()) == 1
      and len(d14.pane_b.extraSelections()) == 1,
      (len(d14.pane_merge.extraSelections()),
       len(d14.pane_b.extraSelections())))

# c) 占位行高亮：A 独有行 → B 栏空白占位行 (0,1) 高亮；结果框无块不亮
_select(d14.pane_a, _del29, 0, 7)
d14._mp_sync_selection("A")
exb = d14.pane_b.extraSelections()
exm = d14.pane_merge.extraSelections()
check("D14_PLACEHOLDER_B", len(exb) == 1
      and exb[0].cursor.anchor() >= 0
      and exb[0].cursor.position() - exb[0].cursor.anchor() == 1,
      [(e.cursor.anchor(), e.cursor.position()) for e in exb])
check("D14_DELETED_NO_R", len(exm) == 0, len(exm))
# 反向：B 独有行 → A 栏占位高亮
_select(d14.pane_b, _add29, 0, 7)
d14._mp_sync_selection("B")
exa = d14.pane_a.extraSelections()
check("D14_PLACEHOLDER_A", len(exa) == 1
      and exa[0].cursor.position() - exa[0].cursor.anchor() == 1,
      [(e.cursor.anchor(), e.cursor.position()) for e in exa])


def _res29(d):
    return d.pane_merge.toPlainText().rstrip("\n")


# d) 选中采用（右）：A 侧 X-old 全行 → 结果变 X-new；改后与结果一致 → 0
_select(d14.pane_a, _pair29, 0, len("X-old"))
spans29 = d14._mp_frag_spans(d14.pane_a, "A")
check("D14_ADOPT_R_FIRST", d14._mp_sel_adopt(spans29, "A", "B") == 0
      and _res29(d14) == _b29, repr(_res29(d14)))   # 默认已是 B 侧 → 无改动
# e) 选中采用（左）：B 侧选区 → 取回 X-old
_select(d14.pane_b, _pair29, 0, len("X-new"))
check("D14_ADOPT_L", d14._mp_sel_adopt(
          d14._mp_frag_spans(d14.pane_b, "B"), "B", "A") == 1
      and _res29(d14) == "head\nX-old\ncommon\nB-added",
      repr(_res29(d14)))
# f) 删除语义：A 独有行「选中采用（右）」= 对侧无内容 → 从结果删除
d14b = AIFragmentDialog(None, StubBridge(), orig_text=_a29,
                        reply_text=_b29)
d14b._mp_adopt("A", [_pair29])          # 先整行采用 A → 结果含 X-old
d14b._mp_adopt("A", [_del29])           # A 独有行整行采用 → 结果含 A-extra
check("D14_PREP_ADOPT_A", _res29(d14b)
      == "head\nX-old\nA-extra\ncommon\nB-added", repr(_res29(d14b)))
_select(d14b.pane_a, _del29, 0, len("A-extra"))
check("D14_DELETE_VIA_EMPTY_SIDE", d14b._mp_sel_adopt(
          d14b._mp_frag_spans(d14b.pane_a, "A"), "A", "B") == 1
      and _res29(d14b) == "head\nX-old\ncommon\nB-added",
      repr(_res29(d14b)))
# g) 右键菜单有选区 5 项 / 无选区 2 项已在 D12 覆盖（D12_CTX_WITH_SEL）

print("FAIL_COUNT=%d" % len(fails))
print("RESULT=%s" % ("OK" if not fails else "FAIL:" + ",".join(fails)))
res = os.path.join(HERE, "_probe_diffmerge.txt")
with open(res, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")
    f.write("FAIL_COUNT=%d\nRESULT=%s\n" % (len(fails),
            "OK" if not fails else "FAIL:" + ",".join(fails)))
