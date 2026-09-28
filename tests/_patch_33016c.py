# -*- coding: utf-8 -*-
# v3.30.16 表格「+」追加行 / 列（Word 风格：边框外侧感应区）
import io, sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
s = io.open(P, encoding="utf-8").read()
orig = s
PATCHES = []

# 1) CSS
OLD1 = """#imgview-bar button:hover { background: rgba(255,255,255,.24); }"""
NEW1 = OLD1 + """
/* v3.30.16 表格「+」追加行 / 列（Word 风格：边框外侧感应区） */
#tbladd { position: fixed; z-index: 9990; display: none; width: 22px; height: 22px;
  border-radius: 50%; border: 1px solid #c9d3e0; background: #fff; color: #0052d9;
  align-items: center; justify-content: center; font-size: 15px; line-height: 1;
  cursor: pointer; box-shadow: 0 1px 4px rgba(0, 0, 0, .18); user-select: none; }
#tbladd.show { display: flex; }
#tbladd:hover { background: #0052d9; border-color: #0052d9; color: #fff; }"""
PATCHES.append(("CSS-TBLADD", OLD1, NEW1))

# 2) DOM
OLD2 = """  <img id="imgview-img" alt="">
</div>"""
NEW2 = OLD2 + """
<div id="tbladd" data-dir="row" title="在表格末尾追加一行">+</div>"""
PATCHES.append(("DOM-TBLADD", OLD2, NEW2))

# 3) JS：感应区 / 按钮定位 / 追加动作
OLD3 = """  /* ---------- v3.30.16 图片：大图预览（浮层「显示」）/ 复制图片到剪贴板 ---------- */"""
NEW3 = """  /* ---------- v3.30.16 表格「+」追加行 / 列（Word 风格） ----------
     触发：指针进入表格下边框 / 右边框外侧 TBLADD_ZONE(10px) 的感应带。
     保持：表格矩形 ∪ 感应带 ∪ 按钮自身（含 6px 缓冲）三者连成一片，
           指针在「表格 → 感应带 → 按钮」之间来回不会闪断 / 抖动。
     隐藏：指针移出上述区域、进入源码 / 分屏模式、正在拖拽缩放，
           或滚动导致锚点移出视口（不画到看不见的地方）。 */
  var TBLADD_ZONE = 10, TBLADD_BTN = 22;
  var TA = document.getElementById('tbladd');
  var tblAddCtx = null;                       // { idx, tbl, dir }
  function hideTblAdd() { if (TA) TA.classList.remove('show'); tblAddCtx = null; }
  function tblAddPlace(idx, tbl, r, dir) {
    if (!TA) return;
    var x, y;
    if (dir === 'row') { x = r.left + r.width / 2 - TBLADD_BTN / 2; y = r.bottom + 6; }
    else { x = r.right + 6; y = r.top + r.height / 2 - TBLADD_BTN / 2; }
    var vw = window.innerWidth || 0, vh = window.innerHeight || 0;
    if (vw && vh && (x < 0 || y < 0 || x + TBLADD_BTN > vw || y + TBLADD_BTN > vh)) { hideTblAdd(); return; }
    TA.style.left = Math.round(x) + 'px';
    TA.style.top = Math.round(y) + 'px';
    TA.title = dir === 'row' ? '在表格末尾追加一行' : '在表格末尾追加一列';
    TA.setAttribute('data-dir', dir);
    TA.classList.add('show');
  }
  function tblAddProbe(x, y) {
    if (!TA) return null;
    var tbls = ED.querySelectorAll('.b-table table');
    for (var i = 0; i < tbls.length; i++) {
      var t = tbls[i], r = t.getBoundingClientRect();
      if (!(r.width > 0) || !(r.height > 0)) continue;
      var inB = x >= r.left - 2 && x <= r.right + 2 && y > r.bottom && y <= r.bottom + TBLADD_ZONE;
      var inR = y >= r.top - 2 && y <= r.bottom + 2 && x > r.right && x <= r.right + TBLADD_ZONE;
      if (!inB && !inR) continue;
      var blk = t.closest('.blk');
      var idx = blk ? blockIndexOf(blk) : -1;
      if (idx < 0) continue;
      return { idx: idx, tbl: t, r: r, dir: inB ? 'row' : 'col' };
    }
    return null;
  }
  function tblAddHover(x, y) {
    if (!TA) return;
    if (editorLocked() || tblRz || rzCtx) { hideTblAdd(); return; }
    if (tblAddCtx && TA.classList.contains('show')) {
      var t0 = tblAddCtx.tbl;
      if (!t0 || !t0.isConnected) { hideTblAdd(); return; }
      var r0 = t0.getBoundingClientRect(), br = TA.getBoundingClientRect();
      var keep = (x >= r0.left - 2 && x <= r0.right + TBLADD_ZONE + 2 &&
                  y >= r0.top - 2 && y <= r0.bottom + TBLADD_ZONE + 2) ||
                 (x >= br.left - 6 && x <= br.right + 6 && y >= br.top - 6 && y <= br.bottom + 6);
      if (keep) { tblAddPlace(tblAddCtx.idx, t0, r0, tblAddCtx.dir); return; }
      hideTblAdd();
      return;
    }
    var hit = tblAddProbe(x, y);
    if (!hit) return;
    tblAddCtx = { idx: hit.idx, tbl: hit.tbl, dir: hit.dir };
    tblAddPlace(hit.idx, hit.tbl, hit.r, hit.dir);
  }
  function tblAddRefresh() {
    if (!tblAddCtx) return;
    var t = tblAddCtx.tbl;
    if (!t || !t.isConnected) { hideTblAdd(); return; }
    tblAddPlace(tblAddCtx.idx, t, t.getBoundingClientRect(), tblAddCtx.dir);
  }
  document.addEventListener('mousemove', function (e) { tblAddHover(e.clientX, e.clientY); });
  document.addEventListener('scroll', function () { tblAddRefresh(); }, true);
  if (window.addEventListener) window.addEventListener('resize', function () { tblAddRefresh(); });
  if (ED.addEventListener) ED.addEventListener('mouseleave', hideTblAdd);
  if (TA) {
    TA.addEventListener('mousedown', function (e) { e.preventDefault(); e.stopPropagation(); });
    TA.addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      var c = tblAddCtx;
      if (!c) return;
      var ok = c.dir === 'row' ? tblAppendRow(c.idx) : tblAppendCol(c.idx);
      if (!ok) { hideTblAdd(); return; }
      /* 追加后表格变长 / 变宽：按钮跟到新边框位置，可连续点击继续追加 */
      var nb = ED.children[c.idx] && ED.children[c.idx].querySelector('table');
      if (!nb) { hideTblAdd(); return; }
      tblAddCtx = { idx: c.idx, tbl: nb, dir: c.dir };
      tblAddPlace(c.idx, nb, nb.getBoundingClientRect(), c.dir);
    });
  }
  /* 末尾追加一行：列数与末行一致，行样式沿用末行，单元格样式按列沿用末行同列 */
  function tblAppendRow(idx) {
    var blk = ED.children[idx];
    var tbl = blk && blk.querySelector('table');
    if (!tbl) return false;
    if (blockInfo(state.raw[idx] || '').type === 'htable') {
      var m = tblModel(idx, tbl);
      if (!m) return false;
      var last = m.rows[m.rows.length - 1] || { style: '', cells: [] };
      var at = m.rows.length, nr = { style: last.style || '', cells: [] };
      for (var c = 0; c < m.cols; c++) {
        var src = null;
        for (var j = 0; j < last.cells.length; j++) if (last.cells[j].c === c) { src = last.cells[j]; break; }
        nr.cells.push({ html: '', rs: 1, cs: 1, style: src ? (src.style || '') : '',
                        head: false, r: at, c: c });
      }
      m.rows.push(nr);
      commitTblModel(m, {});
      return true;
    }
    /* 管道表格：数据行末尾追加一条空行（第 0/1 行是表头与分隔行） */
    var lines = String(state.raw[idx] || '').split('\\n');
    if (lines.length < 2) return false;
    var n = parseRowLine(lines[0]).length, cells = [];
    for (var k = 0; k < n; k++) cells.push('  ');
    lines.push(joinRow(cells));
    state.raw[idx] = lines.join('\\n');
    markDirty(); scheduleSnapshot(); rebuild();
    return true;
  }
  /* 末尾追加一列：行数不变，新列宽度沿用末列（有显式列宽时），表头行自动带 th */
  function tblAppendCol(idx) {
    var blk = ED.children[idx];
    var tbl = blk && blk.querySelector('table');
    if (!tbl) return false;
    if (blockInfo(state.raw[idx] || '').type === 'htable') {
      var m = tblModel(idx, tbl);
      if (!m) return false;
      var at = m.cols;
      for (var r = 0; r < m.rows.length; r++) {
        var row = m.rows[r];
        var lc = row.cells.length ? row.cells[row.cells.length - 1] : null;
        row.cells.push({ html: '', rs: 1, cs: 1, style: lc ? (lc.style || '') : '',
                         head: r < m.headRows, r: r, c: at });
      }
      if (m.colW.length) m.colW.push(m.colW[m.colW.length - 1] || '');
      m.cols++;
      commitTblModel(m, {});
      return true;
    }
    var lines = String(state.raw[idx] || '').split('\\n');
    if (lines.length < 2) return false;
    for (var i = 0; i < lines.length; i++) {
      var cs = parseRowLine(lines[i]);
      cs.push(i === 1 ? ' --- ' : '  ');
      lines[i] = joinRow(cs);
    }
    state.raw[idx] = lines.join('\\n');
    markDirty(); scheduleSnapshot(); rebuild();
    return true;
  }

""" + OLD3
PATCHES.append(("JS-TBLADD", OLD3, NEW3))

# 4) 测试钩子
OLD4 = """  window.__objPick = function (kind, idx) {
    reselectObj(kind, idx);
    return OB ? OB.textContent : '';
  };"""
NEW4 = OLD4 + """
  /* v3.30.16 测试辅助：表格「+」按钮状态 / 模拟悬停与点击 */
  window.__tblAddState = function () {
    var el = document.getElementById('tbladd');
    return JSON.stringify({ show: !!(el && el.classList.contains('show')),
                            dir: el ? (el.getAttribute('data-dir') || '') : '',
                            left: el ? parseInt(el.style.left || '0', 10) : 0,
                            top: el ? parseInt(el.style.top || '0', 10) : 0,
                            idx: tblAddCtx ? tblAddCtx.idx : -1 });
  };
  window.__tblAddHover = function (x, y) {
    document.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x, clientY: y }));
    return window.__tblAddState();
  };
  window.__tblAddClick = function () {
    var el = document.getElementById('tbladd');
    if (!el) return 'nobtn';
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    return window.__tblAddState();
  };
  window.__tblShape = function (idx) {
    var blk = ED.children[idx];
    var t = blk && blk.querySelector('table');
    if (!t) return JSON.stringify({ err: 'notable' });
    var trs = t.querySelectorAll('tr');
    var maxc = 0;
    for (var k = 0; k < trs.length; k++) maxc = Math.max(maxc, trs[k].cells.length);
    var r = t.getBoundingClientRect();
    return JSON.stringify({ rows: trs.length, cells: trs[0] ? trs[0].cells.length : 0, maxc: maxc,
                            rect: { l: Math.round(r.left), t: Math.round(r.top),
                                    r: Math.round(r.right), b: Math.round(r.bottom) } });
  };"""
PATCHES.append(("HOOK-TBLADD", OLD4, NEW4))

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
