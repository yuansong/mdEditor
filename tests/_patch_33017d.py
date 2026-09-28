# -*- coding: utf-8 -*-
"""v3.30.17 补丁 d：「标注」悬浮钮挂到真实点击选中路径 + 图片选中收掉 OB。"""
import io

E = r"E:\WorkBuddy\md-editor\src\editor.html"
src = io.open(E, encoding="utf-8").read()
n = 0


def rep(old, new):
    global src, n
    c = src.count(old)
    assert c == 1, "match=%d: %s..." % (c, old[:70])
    src = src.replace(old, new)
    n += 1


rep(
    """    applyTblSel(tblEl);
    tblPaintRC = { r: rc.r, c: rc.c };
    /* v3.26：拖选过程中隐藏悬浮工具栏，选完（mouseup）再出现，避免拖动抖动/遮挡 */
    TB.classList.remove('show');
    activePop = 'table';
  }, true);""",
    """    applyTblSel(tblEl);
    tblPaintRC = { r: rc.r, c: rc.c };
    /* v3.30.17：表格悬浮工具按钮 —— 点击选中表格即在表格上方浮现「标注」
       （自右键菜单迁入；上方 / 下方的选择在标注弹层里保留） */
    buildObjbar('tbl', idx);
    var tblR3 = tblEl.getBoundingClientRect();
    placePop(OB, tblR3.left, Math.max(6, tblR3.top - 40));
    /* v3.26：拖选过程中隐藏悬浮工具栏，选完（mouseup）再出现，避免拖动抖动/遮挡 */
    TB.classList.remove('show');
    activePop = 'table';
  }, true);""")

rep(
    """    if (kind === 'img') return;
    buildObjbar(kind, idx);""",
    """    if (kind === 'img') { if (OB) OB.classList.remove('show'); return; }
    buildObjbar(kind, idx);""")

io.open(E, "w", encoding="utf-8").write(src)
print("patched ok, %d replacements" % n)
