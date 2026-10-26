# -*- coding: utf-8 -*-
"""v3.48.25 探针（MERGE-CORE 重构适配）：AI 片段替换对话框接入统一差异引擎。

N1  对话框构造 / 标题；旧 insert 模式 API 与旧段级 API 全部移除；
N2  行级行流（_mp_rows）：4 行 / 1 处差异 / (del,add) 1:1 配对；
N3  默认合并结果 = AI 回复全文（未裁决默认取 B）；
N4  双击/采纳左侧 → 结果该行原位替换为原文；✓ 标记；红绿底；
N5  手工编辑保留 + 采纳右侧原位替换；
N6  恢复默认（_mp_reset_rows）→ 回 AI 取舍；
N7  delete 型差异（仅原文有）默认删行不残留、采纳左侧后进结果；spacer 行结构；
N8  viewport 双击事件过滤 → 采纳该侧（eventFilter 经宿主转发）；
N9  右键菜单（假 QMenu）采用所选 / 恢复默认两分支；
N10 状态行文案（mp_stat）+ 未捕获原文选区警告；
N11 空回复保护（get_result_text 可空）；
N12 「显示思考过程」开关：结构 + _bubble_html 思考块显隐；
N13 pending 气泡带思考块（正在整理回答）；
N14 reasoning-only 气泡：警示 + 无插入锚点 + 有复制锚点；
N15 _on_done reasoning-only 兜底（text=reasoning、reasoning_only 标记、系统说明）；
N16 插入一键直达：_on_anchor insert → bridge.insert_at_caret 全文，无对话框；
N17 布局：状态条在底部输入区、对话区置顶；
N18 进度显示（tick/stats/pending）保持。
"""
import sys, os, time
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("MDEDITOR_SKIP_DRAFT", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QSplitter
from PySide6.QtGui import QMouseEvent, QContextMenuEvent
from PySide6.QtCore import QEvent, QPointF, Qt, QPoint
app = QApplication(sys.argv)

import ai_pane as _ap
import diffmerge as _dm
from ai_pane import AIFragmentDialog, AIPane

fails = []
out_lines = []
def check(name, cond, detail=""):
    ln = ("PASS " if cond else "FAIL ") + name + \
         ("  | " + str(detail) if detail else "")
    print(ln)
    out_lines.append(ln)
    if not cond:
        fails.append(name)

class StubBridge:
    def __init__(self):
        self.replaced = []
        self.inserted = []
    def replace_selection(self, text, cb=None, orig_text=""):
        self.replaced.append((text, orig_text))
        if cb:
            cb(True, "")
    def insert_at_caret(self, text, cb=None):
        self.inserted.append(text)
        if cb:
            cb(True, "")

ORIG = "line1\nA-only\ncommon\nkeep"
REPLY = "line1\nB-new\ncommon\nkeep"

# ---------- N1：构造与旧 API 移除 ----------
d1 = AIFragmentDialog(None, StubBridge(), orig_text=ORIG, reply_text=REPLY)
check("N1_TITLE", d1.windowTitle() == "AI 片段替换", d1.windowTitle())
check("N1_NO_INSERT_MODE_API",
      not any(hasattr(AIFragmentDialog, n) for n in
              ("_auto_locate", "_send_down", "_insert_ctx_html", "_sel_text")),
      "insert-mode API 已移除")
check("N1_NO_SELECT_BTN",
      not hasattr(AIFragmentDialog, "b_use_sel")
      and not hasattr(AIFragmentDialog, "b_adopt_sel"),
      "无「选中片段」按钮")
check("N1_NO_SEG_API",
      not any(hasattr(AIFragmentDialog, n) for n in
              ("_build_segs", "_segs", "_adopt", "_segs_from_event",
               "_reset_seg", "_stat")),
      "旧段级 API 已移除（统一走 diffmerge 行级）")
check("N1_KEY_MD", AIFragmentDialog.mp_key_fn is _dm.line_key_md)

# ---------- N2：行级行流 ----------
check("N2_ROWS", len(d1._mp_rows) == 4
      and d1._mp_rows[1]["lk"] == "del" and d1._mp_rows[1]["rk"] == "add"
      and d1._mp_rows[1]["lt"] == "A-only" and d1._mp_rows[1]["rt"] == "B-new",
      [(r["lk"], r["rk"]) for r in d1._mp_rows])
check("N2_DIFF_FIRSTS", d1._mp_diff_firsts == [1], d1._mp_diff_firsts)
DI = 1   # 差异行下标

# ---------- N3：默认结果 = AI 回复全文 ----------
check("N3_DEFAULT_IS_REPLY",
      d1.get_result_text() == REPLY, repr(d1.get_result_text()))
check("N3_UNRESOLVED", d1._mp_rows[DI].get("choice") is None)

# ---------- N4：整行采用左侧 → 该行原位替换为原文 + ✓ ----------
d1._mp_adopt("A", [DI])
check("N4_ADOPT_LEFT",
      d1.get_result_text() == ORIG, repr(d1.get_result_text()))
check("N4_CHOICE_A", d1._mp_rows[DI]["choice"] == "A")
check("N4_CHECK_MARK", "\u2713" in d1.pane_a.toHtml())
check("N4_SPAN_BG", "#f5c4b3" in d1.pane_a.toHtml().lower()
      and "#9fe1cb" in d1.pane_b.toHtml().lower())

# ---------- N5：手工编辑保留 + 采纳右侧 ----------
c = d1.pane_merge.textCursor()
c.setPosition(0)
c.insertText("X")
d1._mp_adopt("B", [DI])
check("N5_MANUAL_KEPT",
      d1.get_result_text() == "X" + REPLY, repr(d1.get_result_text()))

# ---------- N6：无「恢复默认」（v3.48.27 移除），整行采用可逆 ----------
check("N6_NO_RESET_API", not hasattr(AIFragmentDialog, "mp_reset_text")
      and not hasattr(d1, "mp_btn_prev") and not hasattr(d1, "b_all_left"))
d1._mp_adopt("A", [DI])
check("N6_ADOPT_REVERSIBLE",
      d1.get_result_text() == "X" + ORIG
      and d1._mp_rows[DI]["choice"] == "A",
      repr(d1.get_result_text()))

# ---------- N7：delete 型差异默认删行、采纳左侧后进结果；spacer 行结构 ----------
d2 = AIFragmentDialog(None, StubBridge(),
                      orig_text="line1\ndel-a\ncommon", reply_text="line1\ncommon")
check("N7_DELETE_DEFAULT_EXCLUDED",
      len(d2._mp_rows) == 3 and d2.get_result_text() == "line1\ncommon",
      repr(d2.get_result_text()))
check("N7_SPACER_ROW", d2._mp_rows[1]["lk"] == "del"
      and d2._mp_rows[1]["rk"] == "spacer" and d2._mp_rows[1]["rt"] == "",
      (d2._mp_rows[1]["lk"], d2._mp_rows[1]["rk"]))
d2._mp_adopt("A", [1])
check("N7_DELETE_ADOPT_LEFT",
      d2.get_result_text() == "line1\ndel-a\ncommon",
      repr(d2.get_result_text()))

# ---------- N8：viewport 双击（选区快照）→ 仅合并所选 ----------
d3 = AIFragmentDialog(None, StubBridge(), orig_text=ORIG, reply_text=REPLY)
blk_d = d3.pane_a.document().findBlockByNumber(1)
d3._mp_press_row = 1
d3._mp_press_sel = (blk_d.position(), blk_d.position() + len("A-only"))
ev = QMouseEvent(QEvent.MouseButtonDblClick, QPointF(8.0, 4.0),
                 Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
handled = d3.eventFilter(d3.pane_a.viewport(), ev)
check("N8_VIEWPORT_DBLCLICK", handled is True
      and d3.get_result_text() == ORIG, repr(d3.get_result_text()))

# ---------- N9：右键菜单两分支（假 QMenu，offscreen 下真菜单会挂起） ----------
# diffmerge._mp_ctx_menu 在函数体内 from PySide6.QtWidgets import QMenu，
# 故须补丁 PySide6.QtWidgets.QMenu 本体（调用时取到的是补丁后的属性）
import PySide6.QtWidgets as _QtW

# v3.48.27 菜单结构：[合并所选内容（有选区时）] + 全部采用左(原文) + 全部采用右(AI)；
# 「恢复默认」已移除。无选区时 acts = [全部采用左(原文), 全部采用右(AI)]。
class _FakeMenu:
    mode = "left"
    def __init__(self, *a):
        self._acts = []
    def addAction(self, t):
        self._acts.append(t)
        return t
    def exec(self, *a):
        return self._acts[0] if _FakeMenu.mode == "left" else self._acts[-1]

d4 = AIFragmentDialog(None, StubBridge(), orig_text=ORIG, reply_text=REPLY)
ctx_ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                           QPoint(1, 1), QPoint(1, 1))
_orig_qmenu = _QtW.QMenu
_captured = []
class _FakeMenuCap(_FakeMenu):
    def addAction(self, t):
        self._acts.append(t)
        _captured.append(t)
        return t
    def exec(self, *a):
        return None          # 仅捕获菜单项，不执行动作
_QtW.QMenu = _FakeMenuCap
try:
    h0 = d4.eventFilter(d4.pane_b.viewport(), ctx_ev)
    check("N9_CTX_ITEMS", h0 is True and _captured ==
          ["全部采用左(原文)", "全部采用右(AI)"], _captured)
    _QtW.QMenu = _FakeMenu
    _FakeMenu.mode = "left"
    h1 = d4.eventFilter(d4.pane_b.viewport(), ctx_ev)
    check("N9_CTX_ALL_LEFT", h1 is True
          and d4._mp_rows[DI]["choice"] == "A",
          "choice=%s" % d4._mp_rows[DI]["choice"])
    _FakeMenu.mode = "right"
    h2 = d4.eventFilter(d4.pane_a.viewport(), ctx_ev)
    check("N9_CTX_ALL_RIGHT", h2 is True
          and d4._mp_rows[DI]["choice"] == "B",
          "choice=%s" % d4._mp_rows[DI]["choice"])
    check("N9_NO_RESET_ITEM", all("恢复默认" not in t for t in _captured))
finally:
    _QtW.QMenu = _orig_qmenu

# ---------- N10：状态文案 ----------
check("N10_STAT", "相同 3 行" in d1.mp_stat.text()
      and "差异 1 处" in d1.mp_stat.text(), d1.mp_stat.text())
d5 = AIFragmentDialog(None, StubBridge(), orig_text="", reply_text=REPLY)
check("N10_NO_ORIG_WARN", "未捕获到原文选区" in d5.mp_stat.text(),
      d5.mp_stat.text())

# ---------- N11：空结果保护 ----------
d6 = AIFragmentDialog(None, StubBridge(), orig_text="", reply_text="")
check("N11_EMPTY_RESULT", d6.get_result_text().strip() == "",
      repr(d6.get_result_text()))

# ---------- N12/N13/N14/N15/N16/N18：AIPane 侧 ----------
class _BridgeStub:
    _settings = {}
    _mw = None
    def settings(self):
        return {}
    def connection_status(self):
        return {"level": "ok", "text": "已连接"}
    def open_connection(self):
        pass

pane = AIPane(_BridgeStub())
check("N12_THINK_BTN", pane._think_btn.isCheckable()
      and pane._show_think is False)
pane._on_think_toggled(True)
check("N12_THINK_ON", pane._show_think is True)
html_think = pane._bubble_html("assistant", "答案", "12:00", None, False,
                               False, "思考过程内容")
check("N12_THINK_BLOCK", "思考过程" in html_think, html_think[:60])
pane._on_think_toggled(False)
html_nothink = pane._bubble_html("assistant", "答案", "12:00", None, False,
                                 False, "思考过程内容")
check("N12_THINK_HIDDEN", "思考过程" not in html_nothink, html_nothink[:60])

# N13：pending 气泡带思考块
pane._on_think_toggled(True)
pane._stream_msg = {"role": "assistant", "text": "", "time": "12:00",
                    "pending": True, "reasoning": "正在思考…"}
html_pend = pane._bubble_html("assistant", "", "12:00", None, False, True,
                              "正在思考…")
check("N13_PENDING_THINK", "思考过程" in html_pend
      and "正在整理回答" in html_pend, html_pend[:80])
pane._stream_msg = None
pane._on_think_toggled(False)

# N14：reasoning_only 气泡
html_ro = pane._bubble_html("assistant", "思考即全部", "12:00", 0, True,
                            False, "", True)
check("N14_RO_WARN", "只返回了思考过程" in html_ro, html_ro[:80])
check("N14_RO_ANCHORS", "cmd://copy/0" in html_ro
      and "cmd://insert/0" not in html_ro
      and "cmd://fragreplace/0" not in html_ro, "")

# N15：_on_done reasoning-only 兜底
pane._stream_msg = {"role": "assistant", "text": "", "time": "12:00",
                    "pending": True}
pane._stream_reasoning = "完整的思考过程文本"
pane._on_done(True, "")
m_ro = [m for m in pane._render_msgs if m["role"] == "assistant"][-1]
check("N15_RO_FALLBACK", m_ro["text"] == "完整的思考过程文本"
      and m_ro.get("reasoning_only") is True,
      repr(m_ro.get("text"))[:40])
check("N15_RO_NOTE", pane._render_msgs[-1]["role"] == "system"
      and "只返回了思考过程" in pane._render_msgs[-1]["text"],
      pane._render_msgs[-1]["text"][:40])
check("N15_STREAM_CLEARED", pane._stream_msg is None)

# N16：插入一键直达
sb = StubBridge()
pane2 = AIPane(_BridgeStub())
pane2.bridge = sb
pane2._render_msgs = [{"role": "assistant", "text": "AI 回复全文",
                       "time": "12:00"}]
pane2._on_anchor("cmd://insert/0")
check("N16_INSERT_DIRECT", sb.inserted == ["AI 回复全文"], sb.inserted)
check("N16_INSERT_FEEDBACK", pane2._render_msgs[-1]["role"] == "system"
      and "Ctrl+Z" in pane2._render_msgs[-1]["text"],
      pane2._render_msgs[-1]["text"][:40])

# N17：布局 —— 状态条在底部输入区，对话区置顶
split = pane.findChild(QSplitter, "aiSplit")
bottom = pane._input.parent()
check("N17_CHAT_TOP", split is not None and split.indexOf(pane._chat) == 0)
check("N17_BOTTOM_SECOND", split.indexOf(bottom) == 1)
check("N17_STATUS_IN_BOTTOM", pane._status_text.parent() is bottom
      and pane._think_btn.parent() is bottom
      and pane._clear_btn.parent() is bottom)

# N18：进度显示保持
check("N18_TICK", pane._tick_timer.interval() == 500)
pane._stream_msg = {"role": "assistant", "text": "", "time": "12:00",
                    "pending": True}
pane._stream_t0 = time.monotonic() - 3.2
stats = pane._stream_stats_html("#888")
check("N18_STATS", "已等待 3s" in stats, stats)
pane._stream_msg["text"] = "一二三四五六七八九十"
stats2 = pane._stream_stats_html("#888")
check("N18_STATS_CHARS", "已收 10 字" in stats2 and "字/秒" in stats2, stats2)
html_pending = pane._bubble_html("assistant", "", "12:00", None, False, True)
check("N18_PENDING_DOTS", "正在回答" in html_pending, html_pending[:80])


# ---------- N19：片段级合并（v3.48.26 FRAG-MERGE） ----------
from PySide6.QtGui import QTextCursor

def _sel_af(pane, row, i1, i2):
    blk = pane.document().findBlockByNumber(row)
    c = pane.textCursor()
    c.setPosition(blk.position() + i1)
    c.setPosition(blk.position() + i2, QTextCursor.KeepAnchor)
    pane.setTextCursor(c)

d19 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                       reply_text="a1b2c")
_sel_af(d19.pane_a, 0, 1, 2)
d19._mp_frag_merge(d19._mp_frag_spans(d19.pane_a, "A"), "A")
check("N19_FRAG_PARTIAL", d19.get_result_text() == "aXb2c"
      and d19._mp_rows[0].get("override") == "aXb2c",
      repr(d19.get_result_text()))

class _FakeMenu19:
    log = []
    def __init__(self, *a):
        self.acts = []
    def addAction(self, t):
        self.acts.append(t)
        type(self).log.append(t)
        return t
    def exec(self, *a):
        return self.acts[0]

import PySide6.QtWidgets as _QtW19
_orig_qm19 = _QtW19.QMenu
_QtW19.QMenu = _FakeMenu19
try:
    # 有选区：首项 = 「合并所选内容」，选择后结果只替换对应区间
    _FakeMenu19.log = []
    d20 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                           reply_text="a1b2c")
    _sel_af(d20.pane_a, 0, 1, 2)
    ctx_ev19 = QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                                 QPoint(1, 1), QPoint(1, 1))
    h19 = d20.eventFilter(d20.pane_a.viewport(), ctx_ev19)
    check("N19_CTX_FRAG_ITEM", h19 is True
          and _FakeMenu19.log and _FakeMenu19.log[0] == "合并所选内容"
          and d20.get_result_text() == "aXb2c",
          (_FakeMenu19.log, repr(d20.get_result_text())))
    # 无选区：菜单无「合并所选内容」项，仅全部采用两项
    _FakeMenu19.log = []
    d21 = AIFragmentDialog(None, StubBridge(), orig_text="aXbYc",
                           reply_text="a1b2c")
    d21._mp_press_row = 0
    h20 = d21.eventFilter(d21.pane_b.viewport(), ctx_ev19)
    check("N19_CTX_NOSEL_NOITEM", h20 is True
          and _FakeMenu19.log
          and "合并所选内容" not in _FakeMenu19.log
          and _FakeMenu19.log[0].startswith("全部采用左"),
          _FakeMenu19.log)
finally:
    _QtW19.QMenu = _orig_qm19

print("FAIL_COUNT=%d" % len(fails))
print("RESULT=%s" % ("OK" if not fails else "FAIL:" + ",".join(fails)))
res = os.path.join(HERE, "_probe_aifrag.txt")
with open(res, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")
    f.write("FAIL_COUNT=%d\nRESULT=%s\n" % (len(fails),
            "OK" if not fails else "FAIL:" + ",".join(fails)))
