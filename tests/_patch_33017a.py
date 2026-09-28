# -*- coding: utf-8 -*-
"""v3.30.17 任务1补丁：行高拖拽不再展开合并格（修复全合并表拖下边框被还原）。
每处替换断言恰好命中 1 次。"""
import io, sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
src = io.open(P, encoding="utf-8").read()
n = 0


def rep(old, new):
    global src, n
    c = src.count(old)
    assert c == 1, "match count=%d for: %s..." % (c, old[:80])
    src = src.replace(old, new)
    n += 1


# ---- E1: startTblRz 移除行高展开分支 ----
rep(
    """    /* v3.27：行 / 列边框拖拽同理——含合并格先临时展开，拖完重放。
       v3.30.12：展开销毁 colgroup → 展开后立即还原列宽（见 tblCaptureColW 注释），
       保证拖拽期间 / 落盘 colW 均为原列宽 ± 被拖列增量 */
    var rzMerges = null;
    /* v3.30.14：列宽拖拽不再展开合并格 —— colgroup 直接作用于列，合并格跨列宽度
       自动等于所跨列之和，无需拆开；而展开会整表重建 DOM（空内容表格的行高按默认
       重排 → 高度抽动、宽度一闪，即用户报告的「缩小/变高后还原、一闪而过」）。
       行高拖拽仍须展开（rowspan 需要拆开才能逐行设高） */
    if (hit.kind === 'row' && tblHasMergeDom(tbl)) {
      var cw0 = tblCaptureColW(tbl);
      var rh0 = tblCaptureRowH(tbl);   /* v3.30.14：行高同样要还原，否则整表塌缩 */
      var exp = tblExpandDom(idx, tbl);
      if (exp) {
        rzMerges = exp.merges;
        tblRestoreColW(tbl, cw0);
        /* 目标行也一并还原（skip=-1）：按下瞬间它同样会塌到 17px，
           后续 mousemove 会以还原后的值为起点重新设高 */
        tblRestoreRowH(tbl, rh0, -1);
      }
      rzDbg('START-RZ merge-path ' + rzTblId(tbl), { cw0: cw0, restored: rzTblState(tbl) });
    }
    /* v3.30.14：snap = 拖拽基线列宽（内部边线靠它在两列间转移宽度、总宽不变） */
    tblRz = { kind: hit.kind, index: hit.index, idx: idx, tbl: tbl, sx: x, sy: y, size: size, merges: rzMerges,
              snap: hit.kind === 'col' ? tblColSnap(tbl) : null,
              rowH0: hit.kind === 'row' ? rh0 : null };   /* v3.30.14：展开前自然行高 */
    rzDbg('START-RZ ' + rzTblId(tbl), { kind: hit.kind, index: hit.index, size: size, merges: rzMerges ? rzMerges.length : 0 });""",
    """    /* v3.30.14：snap = 拖拽基线列宽（内部边线靠它在两列间转移宽度、总宽不变） */
    /* v3.30.17：行高拖拽不再展开合并格（至此列宽 v3.30.14 / 行高 v3.30.17 /
       整表缩放 v3.30.16 三条路径全部不展开）—— 用户可见的水平边线必然是
       「某逻辑行的底边」：合并格只有最末行的底边可见（rowspan 覆盖的中间行
       没有可拖的线），对 trs[index] 直接设高，合并格高度 = 所跨各行之和自动
       跟随。此前行高路径 tblExpandDom 把整表重绘成规则网格，拖拽全程处于
       摊平态 —— 3×4 全合并表拖下边框「先还原成 12 格再拖」的根因（落盘虽会
       重放合并，但拖拽期间视觉上合并已丢失） */
    tblRz = { kind: hit.kind, index: hit.index, idx: idx, tbl: tbl, sx: x, sy: y, size: size,
              snap: hit.kind === 'col' ? tblColSnap(tbl) : null };
    rzDbg('START-RZ ' + rzTblId(tbl), { kind: hit.kind, index: hit.index, size: size });""")

# ---- E2: applyTblRz 行分支去掉 rowH0 ----
rep(
    "      tblSetRowH(tableRows(ctx.tbl)[ctx.index], val, ctx.rowH0 ? ctx.rowH0[ctx.index] : 0);",
    "      tblSetRowH(tableRows(ctx.tbl)[ctx.index], val, 0);")

# ---- E3: commitTblRz 去掉 data-rzkeep 特判 ----
rep(
    """    for (var r = 0; r < trs.length && r < m.rows.length; r++) {
      /* v3.30.14：拖拽期间临时还原的行高（data-rzkeep）不落盘 —— 那只是为了
         抵消「展开合并格 → 整表重绘 → 行高塌缩」，并非用户设定的行高 */
      if (r !== ctx.index && trs[r].getAttribute('data-rzkeep')) { m.rows[r].style = ''; continue; }
      var h = trs[r].style.height;""",
    """    for (var r = 0; r < trs.length && r < m.rows.length; r++) {
      var h = trs[r].style.height;""")

# ---- E4: commitTblRz 去掉重放 ----
rep(
    """    /* v3.27：拖拽前临时展开过合并格 → 落盘前重放 */
    if (ctx.merges && ctx.merges.length) replayTblMerges(m, ctx.merges);
    state.raw[idx] = tblModelToStorage(m);""",
    """    /* v3.30.17：行高拖拽不再展开合并格，落盘即所见（无需重放） */
    state.raw[idx] = tblModelToStorage(m);""")

# ---- E5: commitTblSize 去掉重放 + rzDbg merges 字段 ----
rep(
    """    rzDbg('COMMIT-SIZE in ' + rzTblId(tbl), { st: rzTblState(tbl), merges: ctx.merges ? ctx.merges.length : 0 });""",
    """    rzDbg('COMMIT-SIZE in ' + rzTblId(tbl), { st: rzTblState(tbl) });""")
rep(
    """    /* v3.27：整表缩放前临时展开过合并格 → 落盘前重放（合并格仍保留原跨度） */
    if (ctx.merges && ctx.merges.length) replayTblMerges(m, ctx.merges);
    state.raw[idx] = tblModelToStorage(m);""",
    """    /* v3.30.16：整表缩放不展开合并格，落盘即所见（无需重放） */
    state.raw[idx] = tblModelToStorage(m);""")

# ---- E6: 删除 collectTblMerges / expandTblModel / replayTblMerges / tblHasMergeDom / tblExpandDom ----
rep(
    """  /* v3.27：缩放前先展开合并格、缩放后重放合并——
     rowspan/colspan 参与等比缩放时行高列宽会被跨格撑乱，
     统一走「收集合并 → 展开成规则网格 → 缩放 → 重放合并」 */
  function collectTblMerges(m) {""",
    """  /* v3.30.17：合并格「先展开 → 缩放 → 重放」机制整体退役——列宽（v3.30.14）、
     行高（v3.30.17）、整表缩放（v3.30.16）三条路径均直接作用于逻辑网格，
     拖拽全程不摊平、落盘无需重放，合并状态从按下到落盘完全不变。
     （collectTblMerges / expandTblModel / replayTblMerges / tblHasMergeDom /
     tblExpandDom / tblCaptureColW / tblRestoreColW / tblCaptureRowH /
     tblRestoreRowH 已删除，勿恢复；行高压缩判定见 tblSetRowH 的 --rzs） */
  function __retiredExpandReplay() { /* removed */ }
  function _unused_collectTblMerges(m) {""")

# E6 剩余函数体不易整段精确匹配 → 用标记切割删除
start = src.index("function _unused_collectTblMerges(m) {")
end_marker = "  function tblModel(idx, tblEl) {"
end = src.index(end_marker)
src = src[:start] + src[end:]
n += 1

# ---- E7: 删除 tblCaptureColW / tblRestoreColW / tblCaptureRowH / tblRestoreRowH ----
cap_start = src.index("  function tblCaptureColW(tbl) {")
cap_end_marker = "  function ensureColgroup(tbl) {"
cap_end = src.index(cap_end_marker)
src = src[:cap_start] + src[cap_end:]
n += 1

io.open(P, "w", encoding="utf-8").write(src)
print("patched ok, %d replacements" % n)
