# -*- coding: utf-8 -*-
"""v3.30.19 修复批：smoke31 首轮暴露的 5 处编辑器缺陷"""
import io, sys

P = r"E:\WorkBuddy\md-editor\src\editor.html"
src = io.open(P, encoding="utf-8").read()
fails = []
applied = []

def rep(tag, old, new, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        fails.append("%s: expect %d hit(s), got %d" % (tag, cnt, n))
        return
    src = src.replace(old, new)
    applied.append(tag)

# ---- F1/F2/F3：CODE-4 构建期 idx 提示（块未挂载时 blockIndexOf 取不到） ----
rep("f1-call", """    else if (inf.type === 'fence') enhanceFence(div);""",
"""    else if (inf.type === 'fence') enhanceFence(div, i);""")
rep("f2-sig", """  function enhanceFence(div) {""",
"""  function enhanceFence(div, idxHint) {""")
rep("f2-final", """      code.addEventListener('blur', function () { applyCodeEnhance(pre, false); });
    }
    applyCodeEnhance(pre, false);
  }""",
"""      code.addEventListener('blur', function () { applyCodeEnhance(pre, false); });
    }
    applyCodeEnhance(pre, false, idxHint);
  }""")
rep("f3-sig", """  function applyCodeEnhance(pre, editing) {
    if (!pre) return;
    var blk = pre.closest('.blk');
    var idx = blk ? blockIndexOf(blk) : -1;""",
"""  function applyCodeEnhance(pre, editing, idxHint) {
    if (!pre) return;
    var blk = pre.closest('.blk');
    /* idxHint：blockEl 构建期块尚未挂载（blockIndexOf 取不到），由 enhanceFence 传入 */
    var idx = idxHint != null ? idxHint : (blk ? blockIndexOf(blk) : -1);""")

# ---- F4：CODE-5 渲染层补的末尾换行不算用户尾空行 ----
rep("f4-trail", """    var trailC = (codeEl.textContent.match(/\\n*$/) || [''])[0].length;
    if (trailC > 2) trailC = 2;""",
"""    var mTrail = codeEl.textContent.match(/\\n*$/) || [''];
    var trailC = Math.max(0, mTrail[0].length - 1);   /* 渲染层补的最后一个换行不算用户内容 */
    if (trailC > 2) trailC = 2;""")

# ---- F5：CODE-6 选区末恰好落在行首时排除该行 ----
rep("f5-codeline", """      var sLine6 = codeText6.slice(0, offS6).split('\\n').length - 1;
      var eLine6 = codeText6.slice(0, offE6).split('\\n').length - 1;""",
"""      var sLine6 = codeText6.slice(0, offS6).split('\\n').length - 1;
      var eLine6 = codeText6.slice(0, offE6).split('\\n').length - 1;
      var preE6 = codeText6.slice(0, offE6);
      if (eLine6 > sLine6 && preE6.charAt(preE6.length - 1) === '\\n') eLine6--;   /* 选区末在该行行首 → 不含该行 */""")

# ---- F6：QUO-4 同款末行排除 ----
rep("f6-qline", """        var liS3 = qtxM.slice(0, lo3).split('\\n').length - 1;
        var liE3 = qtxM.slice(0, hi3).split('\\n').length - 1;""",
"""        var liS3 = qtxM.slice(0, lo3).split('\\n').length - 1;
        var liE3 = qtxM.slice(0, hi3).split('\\n').length - 1;
        var preH3 = qtxM.slice(0, hi3);
        if (liE3 > liS3 && preH3.charAt(preH3.length - 1) === '\\n') liE3--;   /* 选区末在该行行首 → 不含该行 */""")

# ---- F7：U1 nonEmpty 改走模块级 slashNonEmpty（slashState 会被 hidePops 清空） ----
rep("f7-decl", """  var popReanchor = null;   /* v3.30.19（U2）：锚定型浮层滚动重锚定回调 */""",
"""  var popReanchor = null;   /* v3.30.19（U2）：锚定型浮层滚动重锚定回调 */
  var slashNonEmpty = null;   /* v3.30.19（U1）：非空块触发的斜杠菜单标记 {idx}（hidePops 会清 slashState，故存模块级） */""")
rep("f7-trigger", """      e.preventDefault(); e.stopPropagation();
      openSlashAt(el);
      if (nonEmptyU1) { slashState.nonEmpty = true; slashState.anchorIdx = i; }
      return;""",
"""      e.preventDefault(); e.stopPropagation();
      openSlashAt(el);
      slashNonEmpty = nonEmptyU1 ? { idx: i } : null;
      return;""")
rep("f7-apply", """    /* v3.30.19（U1）：非空块行首触发的菜单 —— 叶子项在当前块之后插入新块，
       不覆盖当前块已有内容（空块路径仍是整块替换 item.t） */
    if (slashState && slashState.nonEmpty && !item.children &&
        item.menu !== 'tbl' && item.menu !== 'image' && item.menu !== 'code' &&
        !item.pick && !item.fn) {
      hidePops();
      commitEditSilent();
      var atU1 = Math.min((slashState.anchorIdx != null ? slashState.anchorIdx : state.editIdx) + 1,
        state.raw.length);
      var rawU1 = item.math != null ? '```math\\n' + item.math + '\\n```' : item.t;
      state.raw.splice(atU1, 0, rawU1);
      rebuild(); markDirty(); scheduleSnapshot();
      var infU1 = blockInfo(state.raw[atU1]);
      if (infU1.type === 'fence' && infU1.lang === 'mermaid') openMmdEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'fence' && infU1.lang === 'math') openMathEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'mathdl') openMathEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'fence') focusCodeBlock(atU1);
      else goToBlock(atU1, 'start');
      return;
    }""",
"""    /* v3.30.19（U1）：非空块行首触发的菜单 —— 叶子项在当前块之后插入新块，
       不覆盖当前块已有内容（空块路径仍是整块替换 item.t）。
       标记存模块级 slashNonEmpty：__slashPick 等路径先 hidePops 再 slashApply，
       slashState 已被清空 */
    if (slashNonEmpty && !item.children &&
        item.menu !== 'tbl' && item.menu !== 'image' && item.menu !== 'code' &&
        !item.pick && !item.fn) {
      var atU1 = Math.min(slashNonEmpty.idx + 1, state.raw.length);
      slashNonEmpty = null;   /* 消费一次即清 */
      hidePops();
      commitEditSilent();
      var rawU1 = item.math != null ? '```math\\n' + item.math + '\\n```' : item.t;
      state.raw.splice(atU1, 0, rawU1);
      rebuild(); markDirty(); scheduleSnapshot();
      var infU1 = blockInfo(state.raw[atU1]);
      if (infU1.type === 'fence' && infU1.lang === 'mermaid') openMmdEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'fence' && infU1.lang === 'math') openMathEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'mathdl') openMathEditor(ED.children[atU1], atU1);
      else if (infU1.type === 'fence') focusCodeBlock(atU1);
      else goToBlock(atU1, 'start');
      return;
    }""")

io.open(P, "w", encoding="utf-8", newline="").write(src)
print("APPLIED:", len(applied))
for t in applied: print("  +", t)
if fails:
    print("FAILED:", len(fails))
    for f in fails: print("  -", f)
    sys.exit(1)
print("ALL OK")
