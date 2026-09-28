# -*- coding: utf-8 -*-
# v3.30.16 整表缩放不再摊平合并格
import io, os, sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
s = io.open(P, encoding="utf-8").read()
orig = s

PATCHES = []

# 1) 新增：缩放基线量取（列宽/行高，纯量测不改 DOM）+ 按固定基线等比缩放
OLD1 = """  /* v3.24：整表横向缩放 → 列宽等比缩放。
     之前只改 table.style.width：colgroup 里有固定像素列宽时表格缩不下去
     （列宽之和托住了表格），也没有「单元格跟着一起缩」的效果 */
  function scaleTableCols(tbl, newW) {"""
NEW1 = """  /* v3.30.16：整表缩放基线量取（合并格不摊平）。
     列宽：优先 colgroup 上的显式 px；缺失则取逻辑网格首行该列的单元格实测宽，
     跨列合并格按 cs 均分（与 ensureColgroup 同口径）。纯量测，不写 DOM，
     所以 mousedown 不会引起任何布局跳动。
     行高：取该行 tr 实测高；若该行被 rowspan 覆盖（tr 自身量不到高度），
     用覆盖格实测高 / rs 把高度摊回每一行 */
  function tblBaseColW(tbl) {
    var g = buildTableGrid(tbl), n = g.cols;
    if (!n) return [];
    var cg = tbl.querySelector('colgroup');
    var cols = cg ? cg.children : null;
    var ws = [];
    for (var k = 0; k < n; k++) {
      var w = 0;
      if (cols && cols[k]) {
        var wm = (cols[k].getAttribute('style') || '').match(/width\\s*:\\s*([\\d.]+)px/i);
        if (wm) w = parseFloat(wm[1]) || 0;
      }
      if (!w) {
        var ref = (g.grid[0] || [])[k];
        if (ref) { w = ref.el.getBoundingClientRect().width; if (ref.cs > 1) w = w / ref.cs; }
      }
      ws.push(Math.round(w) || 0);
    }
    return ws;
  }
  function tblBaseRowH(tbl) {
    var trs = tableRows(tbl), g = buildTableGrid(tbl), hs = [];
    for (var r = 0; r < trs.length; r++) {
      var h = trs[r].getBoundingClientRect().height, ref = null;
      for (var c = 0; c < (g.grid[r] || []).length; c++) { if (g.grid[r][c]) { ref = g.grid[r][c]; break; } }
      if (ref && ref.rs > 1) {
        var ch = ref.el.getBoundingClientRect().height / ref.rs;
        if (ch > h) h = ch;
      }
      hs.push(Math.max(1, Math.round(h)));
    }
    return hs;
  }
  /* v3.30.16：按固定基线等比缩放（基线只在 mousedown 量一次，拖拽期间不再逐帧
     实测，避免舍入误差累积；合并表与未合并表从此走同一条路径） */
  function applyTblScaleCols(tbl, base, newW) {
    if (!base || !base.length) { scaleTableCols(tbl, newW); return; }
    var total = 0;
    for (var i = 0; i < base.length; i++) total += base[i];
    if (!(total > 0)) { scaleTableCols(tbl, newW); return; }
    var cg = ensureColgroup(tbl);
    if (!cg || !cg.children.length) return;
    tbl.style.tableLayout = 'fixed';   // 固定布局：缩小不再被内容托住
    for (var k = 0; k < cg.children.length && k < base.length; k++)
      cg.children[k].style.width = Math.max(8, Math.round(base[k] * newW / total)) + 'px';
  }
  function applyTblScaleRows(tbl, base, newH) {
    if (!base || !base.length) { scaleTableRows(tbl, newH); return; }
    var total = 0;
    for (var i = 0; i < base.length; i++) total += base[i];
    if (!(total > 0)) { scaleTableRows(tbl, newH); return; }
    var trs = tableRows(tbl);
    for (var k = 0; k < trs.length && k < base.length; k++)
      tblSetRowH(trs[k], Math.max(12, Math.round(base[k] * newH / total)));
  }
  /* v3.24：整表横向缩放 → 列宽等比缩放。
     之前只改 table.style.width：colgroup 里有固定像素列宽时表格缩不下去
     （列宽之和托住了表格），也没有「单元格跟着一起缩」的效果 */
  function scaleTableCols(tbl, newW) {"""
PATCHES.append(("NEW-BASE-FUNC", OLD1, NEW1))

# 2) mousedown：去掉摊平，改量基线
OLD2 = """    /* v3.27：整表缩放含合并格时，先临时展开成规则网格再缩放，落盘时重放合并。
       v3.30.12：展开后还原 colgroup 列宽（否则等比缩放基线取到重分配后的
       实测宽，真实表格列宽被改写） */
    if (rzCtx.kind === 'table' && tblHasMergeDom(rzCtx.el)) {
      var cw0 = tblCaptureColW(rzCtx.el);
      var exp = tblExpandDom(rzCtx.idx, rzCtx.el);
      if (exp) {
        rzCtx.merges = exp.merges;
        tblRestoreColW(rzCtx.el, cw0);
        var r2 = rzCtx.el.getBoundingClientRect();
        rzCtx.sw = r2.width; rzCtx.sh = r2.height;
        rzDbg('RZMD merge-path ' + rzTblId(rzCtx.el), { cw0: cw0, sw: Math.round(rzCtx.sw), st: rzTblState(rzCtx.el) });
      }
    }"""
NEW2 = """    /* v3.30.16：整表缩放不再摊平合并格。
       v3.27 起为了拿「每列真实宽」先把合并格临时摊平成规则网格再缩放、落盘时重放，
       代价是拖拽全程表格都处于摊平态（用户看到的「先还原成 3×4 再拖」）。
       其实基线可以直接从逻辑网格量出来（见 tblBaseColW / tblBaseRowH）：
       列宽取 colgroup 显式值、缺则按合并格跨列均分；行高用「覆盖格实测高 / rowspan」
       把被跨越的行摊回来。全程不拆合并、不重放，合并状态与拖拽前完全一致 */
    if (rzCtx.kind === 'table') {
      rzCtx.baseW = tblBaseColW(rzCtx.el);
      rzCtx.baseH = tblBaseRowH(rzCtx.el);
      rzDbg('RZMD base ' + rzTblId(rzCtx.el), { bw: rzCtx.baseW, bh: rzCtx.baseH,
             sw: Math.round(rzCtx.sw), sh: Math.round(rzCtx.sh), st: rzTblState(rzCtx.el) });
    }"""
PATCHES.append(("MOUSEDOWN-BASE", OLD2, NEW2))

# 3) mousemove：横向缩放走基线
OLD3 = """        rzCtx.el.style.width = Math.round(w) + 'px';
        scaleTableCols(rzCtx.el, w);"""
NEW3 = """        rzCtx.el.style.width = Math.round(w) + 'px';
        applyTblScaleCols(rzCtx.el, rzCtx.baseW, w);"""
PATCHES.append(("MOVE-COLS", OLD3, NEW3))

# 4) mousemove：纵向缩放走基线
OLD4 = """        rzCtx.el.style.height = Math.round(ht) + 'px';
        scaleTableRows(rzCtx.el, ht);"""
NEW4 = """        rzCtx.el.style.height = Math.round(ht) + 'px';
        applyTblScaleRows(rzCtx.el, rzCtx.baseH, ht);"""
PATCHES.append(("MOVE-ROWS", OLD4, NEW4))

fails = []
for name, o, n in PATCHES:
    cnt = s.count(o)
    if cnt != 1:
        fails.append("%s hits=%d" % (name, cnt))
        continue
    s = s.replace(o, n, 1)

if fails:
    sys.stdout.write("FAILED: " + "; ".join(fails) + "\n")
    sys.exit(1)

io.open(P, "w", encoding="utf-8", newline="").write(s)
sys.stdout.write("OK patched %d, len %d -> %d\n" % (len(PATCHES), len(orig), len(s)))
