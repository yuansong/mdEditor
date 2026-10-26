# 探针：v3.48.27（FRAG-ONLY 适配）MergeDialog —— 统一差异引擎选区合并自测
# 覆盖：初始结果=最新版本(B) / 行级行流（1:1 配对 + 词级）/ 整行采用 A·B（原位替换）/
#       手工编辑不受采纳影响 / 差异仅标差异文字（词级 span，无整行底色）/
#       delete 行默认删行不残留 / viewport 双击事件（宿主 eventFilter 转发）/
#       相同行无底色 / 按钮收敛（无导航、无全部采用按钮）/ 双击快照选区合并 /
#       右键「合并所选内容」+「全部采用左/右」/ 双击无选区不动作
import sys, os, tempfile
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("MDEDITOR_SKIP_DRAFT", "1")

from PySide6.QtWidgets import QApplication, QWidget
app = QApplication(sys.argv)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import dialogs

fails = []
out_lines = []
def check(name, cond, extra=""):
    ln = "%s=%s%s" % (("PASS " if cond else "FAIL ") + name,
                      cond, (" | " + str(extra)) if extra else "")
    print(ln)
    out_lines.append(ln)
    if not cond:
        fails.append(name)

class FakeWin(QWidget):
    _theme = "light"
    def list_history(self, path):
        return []
    def apply_merged_text(self, t):
        return True

win = FakeWin()
dlg = dialogs.HistoryDialog(win)

fa = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
fa.write("line1\nA-only\ncommon\nkeep\n"); fa.close()
fb = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
fb.write("line1\nB-new\ncommon\nkeep\n"); fb.close()

dlg._cur_file = "demo.md"
dlg._items = [(fa.name, 1.0), (fb.name, 2.0)]
dlg.listw.addItem("快照A"); dlg.listw.addItem("快照B")
dlg.listw.item(0).setSelected(True)
dlg.listw.item(1).setSelected(True)
dlg._on_sel_changed()
dlg._merge_two()
md = getattr(dlg, "_merge_dlg", None)

if md is None:
    print("RESULT=FAIL: _merge_dlg not created")
    with open(os.path.join(HERE, "_probe_merge.txt"), "w", encoding="utf-8") as f:
        f.write("RESULT=FAIL: _merge_dlg not created\n")
    sys.exit(1)

check("DLG_VISIBLE", md.isVisible())
check("NO_SEG_API",
      not any(hasattr(dialogs.MergeDialog, n) for n in
              ("_build_segs", "_segs", "_adopt", "_segs_from_event",
               "_reset_seg")),
      "旧段级 API 已移除（统一走 diffmerge 行级）")

# 行流结构：ctx(line1) / (del A-only, add B-new) / ctx(common) / ctx(keep)
# / ctx("") —— 快照文件带尾随换行，两侧各多一个空行 ctx（引擎行为正确）
check("ROWS_STRUCTURE", len(md._mp_rows) == 5
      and md._mp_rows[1]["lk"] == "del" and md._mp_rows[1]["rk"] == "add"
      and len(md._mp_diff_firsts) == 1,
      [(r["lk"], r["rk"]) for r in md._mp_rows])
DI = md._mp_diff_firsts[0]

# 1) 初始结果 = 最新版本(B) 全文（未裁决默认取 B）
r0 = md.pane_merge.toPlainText()
check("INIT_IS_NEWEST", r0.rstrip("\n") == "line1\nB-new\ncommon\nkeep",
      repr(r0))
check("INIT_UNRESOLVED", md._mp_rows[DI]["choice"] is None)

# 2) 整行采用左侧（右键「全部采用左」对单行的等价路径）
md._mp_adopt("A", [DI])
r1 = md.pane_merge.toPlainText()
check("ADOPT_LEFT", r1.rstrip("\n") == "line1\nA-only\ncommon\nkeep", repr(r1))
check("CHOICE_A", md._mp_rows[DI]["choice"] == "A")

# 3) 手工编辑（首行头部加 X）后再采用右侧 → 手工内容保留 + 行替换正确
c = md.pane_merge.textCursor()
c.setPosition(0)
c.insertText("X")
md._mp_adopt("B", [DI])
r2 = md.pane_merge.toPlainText()
check("INPLACE_KEEP_MANUAL", r2.rstrip("\n") == "Xline1\nB-new\ncommon\nkeep",
      repr(r2))

# 4) 差异仅标差异文字：对比框 HTML 含词级红/绿 span（小写），无旧整行浅底
ha = md.pane_a.toHtml(); hb = md.pane_b.toHtml()
check("WORD_SPAN_RED", "#f5c4b3" in ha.lower())
check("WORD_SPAN_GREEN", "#9fe1cb" in hb.lower())
check("NO_LINE_BG", "#ffe5e5" not in ha.lower()
      and "#e6ffec" not in hb.lower())
md._mp_adopt("A", [DI])
check("CHECK_MARK", "✓" in md.pane_a.toHtml())

# 5) delete 行（仅旧版有）默认删行不残留空行，初始结果仍=最新版本
md2 = dialogs.MergeDialog(win)
md2.show_merge("t", "line1\ndel-a\ncommon", "line1\ncommon", "A", "B")
check("DELETE_DEFAULT_EXCLUDED",
      len(md2._mp_rows) == 3
      and md2.pane_merge.toPlainText().rstrip("\n") == "line1\ncommon",
      repr(md2.pane_merge.toPlainText()))
# 整行采用左侧 delete 行 → 采纳进结果
md2._mp_adopt("A", [1])
check("DELETE_ADOPT_LEFT",
      md2.pane_merge.toPlainText().rstrip("\n") == "line1\ndel-a\ncommon",
      repr(md2.pane_merge.toPlainText()))

# 6) 事件经 viewport() 投递 + 宿主 eventFilter 转发 → 选中整行后双击 = 整行合并
from PySide6.QtCore import QPointF, QEvent, Qt as _Qt2
from PySide6.QtGui import QMouseEvent, QTextCursor
ev = QMouseEvent(QEvent.MouseButtonDblClick, QPointF(8.0, 4.0),
                 _Qt2.LeftButton, _Qt2.LeftButton, _Qt2.NoModifier)
md3 = dialogs.MergeDialog(win)
md3.show_merge("t3", "line1\nA-only\ncommon", "line1\nB-new\ncommon", "A", "B")
blk = md3.pane_a.document().findBlockByNumber(1)
md3._mp_press_row = 1
md3._mp_press_sel = (blk.position(), blk.position() + len("A-only"))
handled = md3.eventFilter(md3.pane_a.viewport(), ev)
check("VIEWPORT_DBLCLICK_MERGE_LINE", handled is True
      and "A-only" in md3.pane_merge.toPlainText()
      and "B-new" not in md3.pane_merge.toPlainText(),
      repr(md3.pane_merge.toPlainText()))

# 7) 相同行无底色、差异行有底色（setPlainText 先行，杜绝格式继承染色）
md4 = dialogs.MergeDialog(win)
md4.show_merge("t4", "line1\nA-only\ncommon", "line1\nB-new\ncommon", "A", "B")
doc4 = md4.pane_merge.document()
c_eq = md4.pane_merge.textCursor(); c_eq.setPosition(2)   # "line1" 中间（相同行）
bg_style_eq = c_eq.charFormat().background().style()
c_df = md4.pane_merge.textCursor()
c_df.setPosition(doc4.findBlockByNumber(1).position())  # 行首 'B'（冲突字）
bg_style_df = c_df.charFormat().background().style()
c_sm = md4.pane_merge.textCursor()
c_sm.setPosition(doc4.findBlockByNumber(1).position() + 2)  # 'n'（相同字）
bg_style_sm = c_sm.charFormat().background().style()
check("EQUAL_NO_BG", bg_style_eq == _Qt2.NoBrush, "style=%s" % bg_style_eq)
check("DIFF_HAS_BG", bg_style_df != _Qt2.NoBrush, "style=%s" % bg_style_df)
check("SAMECHAR_NO_BG", bg_style_sm == _Qt2.NoBrush,
      "style=%s" % bg_style_sm)

# 8) 按钮收敛：仅功能性按钮；无导航 / 无全部采用按钮（收进右键菜单）
check("TAIL_BUTTONS", hasattr(md4, "b_apply") and hasattr(md4, "b_save")
      and not hasattr(md4, "b_all_left") and not hasattr(md4, "b_all_right")
      and not hasattr(md4, "mp_btn_prev") and not hasattr(md4, "mp_nav_lbl")
      and not hasattr(dialogs.MergeDialog, "mp_reset_text"))


# ---------- v3.48.26/27：选区合并（FRAG-MERGE） ----------
from PySide6.QtGui import QContextMenuEvent

def _sel_rows(pane, row, i1, i2):
    blk = pane.document().findBlockByNumber(row)
    c = pane.textCursor()
    c.setPosition(blk.position() + i1)
    c.setPosition(blk.position() + i2, QTextCursor.KeepAnchor)
    pane.setTextCursor(c)

# 双击 + 按下时选区快照 = 仅合并所选内容（词级对齐）
md5 = dialogs.MergeDialog(win)
md5.show_merge("t5", "aXbYc", "a1b2c", "A", "B")
blk0 = md5.pane_a.document().findBlockByNumber(0)
_sel_rows(md5.pane_a, 0, 1, 2)
md5._mp_press_sel = (blk0.position() + 1, blk0.position() + 2)
md5._mp_press_row = 0
h5 = md5.eventFilter(md5.pane_a.viewport(), ev)
check("FRAG_DBLCLICK_WITH_SEL", h5 is True
      and md5.pane_merge.toPlainText().rstrip("\n") == "aXb2c",
      repr(md5.pane_merge.toPlainText()))

# 无选区双击 = 不动作（v3.48.27：不再整行采用，防误触）
md6 = dialogs.MergeDialog(win)
md6.show_merge("t6", "aXbYc", "a1b2c", "A", "B")
md6._mp_press_sel = None
md6._mp_press_row = 0
h6 = md6.eventFilter(md6.pane_a.viewport(), ev)
check("FRAG_NOSel_NOOP", h6 is not True
      and md6.pane_merge.toPlainText().rstrip("\n") == "a1b2c"
      and md6._mp_rows[0].get("choice") is None
      and md6._mp_rows[0].get("override") is None,
      repr(md6.pane_merge.toPlainText()))

# 右键菜单：有选区首项 = 「合并所选内容」；结果只替换对应区间
md7 = dialogs.MergeDialog(win)
md7.show_merge("t7", "aXbYc", "a1b2c", "A", "B")
_sel_rows(md7.pane_a, 0, 1, 2)

class _FakeMenu2:
    log = []
    def __init__(self, *a):
        self.acts = []
    def addAction(self, t):
        self.acts.append(t)
        type(self).log.append(t)
        return t
    def exec(self, *a):
        return self.acts[0]

import PySide6.QtWidgets as _QtW7
_orig_qm = _QtW7.QMenu
_QtW7.QMenu = _FakeMenu2
_FakeMenu2.log = []
try:
    from PySide6.QtCore import QPoint as _P7
    cev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                            _P7(1, 1), _P7(1, 1))
    h7 = md7.eventFilter(md7.pane_a.viewport(), cev)
    check("FRAG_CTX_FIRST_ITEM", h7 is True
          and _FakeMenu2.log and _FakeMenu2.log[0] == "合并所选内容"
          and md7.pane_merge.toPlainText().rstrip("\n") == "aXb2c",
          (_FakeMenu2.log, repr(md7.pane_merge.toPlainText())))

    # 右键「全部采用左」→ 所有差异行整行采用 A
    class _FakeMenuLeft:
        def __init__(self, *a):
            self.acts = []
        def addAction(self, t):
            self.acts.append(t)
            return t
        def exec(self, *a):
            return self.acts[0]     # 无选区菜单仅 2 项，第 1 项 = 全部采用左
    _QtW7.QMenu = _FakeMenuLeft
    md8 = dialogs.MergeDialog(win)
    md8.show_merge("t8", "aXbYc", "a1b2c", "A", "B")
    md8.eventFilter(md8.pane_a.viewport(), cev)
    check("CTX_ADOPT_ALL_LEFT", md8.pane_merge.toPlainText().rstrip("\n") == "aXbYc"
          and md8._mp_rows[0].get("choice") == "A",
          repr(md8.pane_merge.toPlainText()))
finally:
    _QtW7.QMenu = _orig_qm

print("FAIL_COUNT=%d" % len(fails))
print("RESULT=%s" % ("OK" if not fails else "FAIL:" + ",".join(fails)))
with open(os.path.join(HERE, "_probe_merge.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")
    f.write("FAIL_COUNT=%d\nRESULT=%s\n" % (len(fails),
            "OK" if not fails else "FAIL:" + ",".join(fails)))

for p in (fa.name, fb.name):
    try: os.unlink(p)
    except OSError: pass
