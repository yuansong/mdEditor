# -*- coding: utf-8 -*-
"""v3.48.30（DRIFT-FIX）长行合并漂移验证（固化自 _dbg_drift.py）。

>300 字符长行（word_ops 300 护栏返回 None），difflib 直接算 opcodes 作
oracle，验证选区合并片段落位精确 + 二次合并幂等。
另覆盖 v3.48.30 根因：columnNumber() 是可视行内列（折行偏移），
positionInBlock() 才是逻辑块内列 —— 窄面板长行折行时选区列号必须精确。
结果：tests/_probe_drift.txt
"""
import io
import os
import sys

sys.path.insert(0, r"E:\WorkBuddy\md-editor\src")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("MDEDITOR_SKIP_DRAFT", "1")

from PySide6.QtCore import QSettings
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_probe_drift.txt")
out = []
FAIL = [0]
TOTAL = [0]


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    out.append("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


class Win(QWidget):
    _theme = "light"
    _settings = QSettings("mdEditor", "dbg")


def _run():
    import difflib

    import dialogs

    md = dialogs.MergeDialog(Win())
    # 长行 >300 字符（word_ops 护栏外）；"目标短语XYZ" 仅 A 有，
    # B 对应区域是"别的话"，两侧公共前后缀长度不同 → 钳制必然落错
    a_line = ("前缀" + "甲" * 150 + "目标短语XYZ" + "乙" * 150 + "收尾")
    b_line = ("开头" + "丙" * 160 + "别的话" + "丁" * 155 + "结束")
    A = "标题\n" + a_line + "\n尾行\n"
    B = "标题\n" + b_line + "\n尾行\n"
    md.show_merge("漂移验证", A, B, "A", "B")
    md.show()
    app.processEvents()
    pair = next(i for i, r in enumerate(md._mp_rows)
                if r["lk"] == "del" and r["rk"] == "add")

    i1 = a_line.find("目标短语XYZ")
    i2 = i1 + len("目标短语XYZ")
    frag = a_line[i1:i2]

    def set_sel(pane, row, c1, c2):
        blk = pane.document().findBlockByNumber(row)
        cur = QTextCursor(blk)
        cur.setPosition(blk.position() + c1)
        cur.setPosition(blk.position() + c2, QTextCursor.KeepAnchor)
        pane.setTextCursor(cur)

    # ① 选区 spans 列号精确（v3.48.30：positionInBlock 修可视行列偏移）
    set_sel(md.pane_a, pair, i1, i2)
    spans = md._mp_frag_spans(md.pane_a, "A")
    ok_spans = bool(spans) and spans[0] == (pair, i1, i2)
    check("D15_SPANS_COL", ok_spans,
          "spans=%s expect=(%d,%d,%d)" % (spans, pair, i1, i2))
    if ok_spans:
        check("D15_FRAG_TEXT", a_line[spans[0][1]:spans[0][2]] == frag, "")

    # oracle：difflib 直接算（引擎 word_ops 被 300 护栏挡掉，走 map_range_long）
    sm = difflib.SequenceMatcher(a=a_line, b=b_line, autojunk=False)
    j1, j2 = None, None
    seen = False
    for tag, x1, x2, y1, y2 in sm.get_opcodes():
        if x2 <= i1:
            continue
        if x1 >= i2:
            break
        if tag == "equal":
            s = y1 + max(i1, x1) - x1
            e = y1 + min(i2, x2) - x1
        else:
            s, e = y1, y2
        if not seen:
            j1 = s
            seen = True
        j2 = e
    expected = b_line[:j1] + frag + b_line[j2:]

    n = md._mp_frag_merge(spans, "A")
    app.processEvents()
    got = md.pane_merge.toPlainText().rstrip("\n")
    got_line = got.split("\n")[pair]
    check("D15_MERGE_NO_DRIFT", n == 1 and got_line == expected,
          "changed=%s" % n)

    # 二次合并同片段（override 重对齐路径）→ 幂等无改动
    set_sel(md.pane_a, pair, i1, i2)
    n2 = md._mp_frag_merge(md._mp_frag_spans(md.pane_a, "A"), "A")
    got2 = md.pane_merge.toPlainText().rstrip("\n")
    check("D15_REMERGE_IDEMPOTENT", n2 == 0 and got2 == got, "changed=%s" % n2)


try:
    _run()
except Exception:
    import traceback as _t
    out.append("FAIL D15_CRASH " + _t.format_exc().replace("\n", " | ")[:300])

with io.open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\nSUMMARY total=%d fail=%d\n" % (TOTAL[0], FAIL[0]))
os._exit(0)
