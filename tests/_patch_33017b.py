# -*- coding: utf-8 -*-
"""v3.30.17 任务2/3/4补丁：
  2) 表格标注入口迁至悬浮工具按钮（选中表格出现，含「标注」钮）
  3) 「+」按钮外框圆形 → 矩形（Word 风格）
  4) 图片操作重构：选中不出悬浮按钮条；右键菜单（图注/重置尺寸/存储项动态）；
     状态栏显示图片存储方式与文件名
每处替换断言恰好命中 1 次。"""
import io

n = 0


def patch(path, pairs):
    global n
    src = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        c = src.count(old)
        assert c == 1, "%s match count=%d for: %s..." % (path, c, old[:70])
        src = src.replace(old, new)
        n += 1
    io.open(path, "w", encoding="utf-8").write(src)


E = r"E:\WorkBuddy\md-editor\src\editor.html"
M = r"E:\WorkBuddy\md-editor\src\mainwindow.py"

# ================= 任务 3：「+」按钮矩形外框 =================
patch(E, [
    ("""/* v3.30.16 表格「+」追加行 / 列（Word 风格：边框外侧感应区） */
#tbladd { position: fixed; z-index: 9990; display: none; width: 22px; height: 22px;
  border-radius: 50%; border: 1px solid #c9d3e0; background: #fff; color: #0052d9;""",
     """/* v3.30.16 表格「+」追加行 / 列（Word 风格：边框外侧感应区）
   v3.30.17：外框由圆形改矩形（Word 同款方角小按钮） */
#tbladd { position: fixed; z-index: 9990; display: none; width: 22px; height: 22px;
  border-radius: 3px; border: 1px solid #c9d3e0; background: #fff; color: #0052d9;"""),
])

# ================= 任务 2：标注入口迁移 =================
patch(E, [
    # 右键菜单移除「表格标注（上方 / 下方）」
    ("""    /* —— 清空 / 标注 —— */
    mi(svgIcon('clr'), '清空内容', 'clear');
    mi(svgIcon('cap'), '表格标注（上方 / 下方）', 'cap');""",
     """    /* —— 清空（v3.30.17：「标注」入口迁至表格选中后的悬浮工具按钮 —— ） */
    mi(svgIcon('clr'), '清空内容', 'clear');"""),
    # openTblCaption 同时收掉悬浮按钮条
    ("""    if (TB) TB.classList.remove('show');
    openCapPop('tbl', idx, tbl.getBoundingClientRect(), cur, curTop);""",
     """    if (TB) TB.classList.remove('show');
    if (OB) OB.classList.remove('show');
    openCapPop('tbl', idx, tbl.getBoundingClientRect(), cur, curTop);"""),
    # selectTblFrame 挂悬浮按钮条
    ("""  function selectTblFrame(idx, tblEl) {
    if (!tblEl) return;
    clearObjSelClass();
    tblEl.classList.add('sel');
    objSel = { kind: 'table', idx: idx, el: tblEl };   // 表格只用缩放框，不加对象操作条
    showRzFrame(tblEl, 'table', idx);
  }""",
     """  function selectTblFrame(idx, tblEl) {
    if (!tblEl) return;
    clearObjSelClass();
    tblEl.classList.add('sel');
    objSel = { kind: 'table', idx: idx, el: tblEl };
    showRzFrame(tblEl, 'table', idx);
    /* v3.30.17：表格悬浮工具按钮 —— 「标注」自右键菜单迁至此处（上方 / 下方
       的选择保留在标注弹层里）。与图片 / 图表操作条同款样式，悬在表格上方 */
    buildObjbar('tbl', idx);
    var r = tblEl.getBoundingClientRect();
    placePop(OB, r.left, Math.max(6, r.top - 40));
  }"""),
    # buildObjbar：新增 tbl 分支；图片分支删除（操作收进右键菜单）
    ("""  function buildObjbar(kind, idx) {
    OB.innerHTML = '';
    var items = [
      ['图注', function () { editCaption(kind, idx); }, '添加 / 修改图注（可放在上方或下方）'],
      ['重置尺寸', function () { resetObjSize(kind, idx); }, '恢复原始尺寸']
    ];
    if (kind === 'mmd') {
      items.push(['源码', function () { openMmdEditor(ED.children[idx], idx); }, '编辑图表源码']);
      /* v3.25：图表保留删除按钮；图片块改用 DEL / Backspace 删除（见下方 keydown） */
      items.push(['删除', function () { deleteBlockAt(idx); hideObjSel(); }, '删除整块']);
    } else if (kind === 'img') {
      /* v3.29：按钮按当前存储状态动态显示；v3.29b：还需文档已保存（有 __docDir
         才能确定 assets 目录）——未保存文档只能内嵌，重命名 / 落盘按钮一律不显示，
         否则点了只会得到「请先保存文档」的报错 */
      var isrc = imgRawSrc(idx);
      var isData = /^data:/i.test(isrc);
      var isRemote = /^https?:/i.test(isrc);
      var isAbs = /^(?:[A-Za-z]:[\\/]|file:)/i.test(isrc);   // 绝对路径不依赖文档目录
      var isLocalImg = !!isrc && !isData && !isRemote;
      var canStore = !!window.__docDir || isAbs;
      /* v3.30.16：「显示」= 应用内大图预览，与存储状态无关，固定排在最前 */
      items.unshift(['显示', function () { openImgPreview(idx); },
        '显示图片（大图预览，点击任意处或 Esc 关闭）']);
      if (isLocalImg) {
        if (canStore) {
          items.unshift(['修改存储文件名', function () { openRenamePop(idx); }, '修改图片在 assets 文件夹中的存储文件名（含编号前缀）']);
          items.splice(1, 0, ['转化为内嵌存储', function () { requestImgModeSwitch(idx); },
            '把图片转为 data URL 内嵌进文档（原文件保留在 assets）']);
        }
      } else if (canStore) {
        items.splice(1, 0, ['转化为相对路径存储', function () { requestImgModeSwitch(idx); },
          '把图片落盘到「文档名.assets」文件夹并改为相对路径引用']);
      }
    }
    items.forEach(function (b) {""",
     """  function buildObjbar(kind, idx) {
    OB.innerHTML = '';
    var items;
    if (kind === 'tbl') {
      /* v3.30.17：表格悬浮工具按钮 —— 「标注」（上方 / 下方在弹层里选） */
      items = [['标注', function () { openTblCaption(idx); },
        '添加 / 修改表格标注（可放在上方或下方）']];
    } else {
      /* v3.30.17：图片不再使用悬浮按钮条（操作全部收进图片右键菜单），
         此分支只剩图表（mmd）—— 基础两项 + 源码 / 删除 */
      items = [
        ['图注', function () { editCaption(kind, idx); }, '添加 / 修改图注（可放在上方或下方）'],
        ['重置尺寸', function () { resetObjSize(kind, idx); }, '恢复原始尺寸'],
        ['源码', function () { openMmdEditor(ED.children[idx], idx); }, '编辑图表源码'],
        /* v3.25：图表保留删除按钮；图片块改用 DEL / Backspace 删除（见下方 keydown） */
        ['删除', function () { deleteBlockAt(idx); hideObjSel(); }, '删除整块']
      ];
    }
    items.forEach(function (b) {"""),
    # selectObj：图片不再建操作条
    ("""  function selectObj(kind, idx, el) {
    if (!el) { hideObjSel(); return; }
    clearObjSelClass();
    el.classList.add('sel');
    objSel = { kind: kind, idx: idx, el: el };
    showRzFrame(el, kind, idx);
    buildObjbar(kind, idx);
    var r = el.getBoundingClientRect();
    placePop(OB, r.left, Math.max(6, r.top - 40));
  }""",
     """  function selectObj(kind, idx, el) {
    if (!el) { hideObjSel(); return; }
    clearObjSelClass();
    el.classList.add('sel');
    objSel = { kind: kind, idx: idx, el: el };
    showRzFrame(el, kind, idx);
    /* v3.30.17：图片操作全部收进右键菜单 —— 选中只出蓝框，不再浮现按钮条；
       图表（mmd）保留悬浮按钮条 */
    if (kind === 'img') return;
    buildObjbar(kind, idx);
    var r = el.getBoundingClientRect();
    placePop(OB, r.left, Math.max(6, r.top - 40));
  }"""),
])

# ================= 任务 4：图片右键菜单 + 状态栏 =================
patch(E, [
    # 右键图片先选中再弹菜单
    ("""      if (!blk.classList.contains('raw-edit') && specialBlockKind(bi)) {
        e.preventDefault();
        hidePops();
        showSpecialBlockMenuAt(bi, e.clientX, e.clientY);
        return;
      }""",
     """      if (!blk.classList.contains('raw-edit') && specialBlockKind(bi)) {
        e.preventDefault();
        hidePops();
        /* v3.30.17：右键图片 → 先选中（蓝框）再弹菜单，操作对象与所见一致 */
        var _imgT = e.target.closest ? e.target.closest('#editor img') : null;
        if (_imgT && blk.querySelector('img') === _imgT) selectObj('img', bi, _imgT);
        showSpecialBlockMenuAt(bi, e.clientX, e.clientY);
        return;
      }"""),
    # 图片分支菜单重构
    ("""    } else {
      if (SPEC_EDIT[kind]) {
        html += '<div class="mi" data-act="edit"><span style="width:18px;text-align:center">✎</span>' +
                SPEC_EDIT[kind] + '</div>';
        html += '<div class="sep"></div>';
      }
      /* v3.30.10（MMD-5）：图表块菜单补「复制块」（dup 为通用动作）；
         图片块维持 v3.24 决策不加复制块 */
      if (kind === 'chart')
        html += '<div class="mi" data-act="dup"><span style="width:18px;text-align:center">⧉</span>复制块</div>';
      /* v3.30.16：图片块右键「复制图片」—— 位图进剪贴板（可粘贴到微信 / Word），
         区别于「复制块」（在文档内复制一份） */
      if (kind === 'image')
        html += '<div class="mi" data-act="copyimg"><span style="width:18px;text-align:center">🖼</span>复制图片</div>';
      html += '<div class="mi" data-act="up"><span style="width:18px;text-align:center">⬆</span>上移</div>';""",
     """    } else if (kind === 'image') {
      /* v3.30.17：图片右键菜单（替代悬浮按钮条）—— 图注 / 重置尺寸恒显；
         存储项按当前存储方式动态显示：相对路径 → 转内嵌 + 修改图片名称；
         内嵌 / 网络 → 转相对路径。未保存文档（无 __docDir）且非绝对路径时
         不显示存储项（点了只会得到「请先保存文档」报错）。
         显示 / 复制图片 / 上移 / 下移 / 删除块保留 */
      html += '<div class="mi" data-act="edit"><span style="width:18px;text-align:center">✎</span>图注</div>';
      html += '<div class="mi" data-act="imgreset"><span style="width:18px;text-align:center">↺</span>重置尺寸</div>';
      var _isrc = imgRawSrc(idx), _isData = /^data:/i.test(_isrc), _isRemote = /^https?:/i.test(_isrc);
      var _isAbs = /^(?:[A-Za-z]:[\\\\/]|file:)/i.test(_isrc);
      var _canStore = !!window.__docDir || _isAbs;
      if (_isrc && !_isData && !_isRemote) {
        if (_canStore) {
          html += '<div class="mi" data-act="imgmode"><span style="width:18px;text-align:center">🔄</span>转化为内嵌式存储</div>';
          html += '<div class="mi" data-act="imgrename"><span style="width:18px;text-align:center">✏</span>修改图片名称</div>';
        }
      } else if (_canStore) {
        html += '<div class="mi" data-act="imgmode"><span style="width:18px;text-align:center">🔄</span>转化为相对路径存储</div>';
      }
      html += '<div class="sep"></div>';
      /* v3.30.16：「显示图片」= 应用内大图预览（Esc / 点遮罩关闭） */
      html += '<div class="mi" data-act="viewimg"><span style="width:18px;text-align:center">👁</span>显示图片</div>';
      /* v3.30.16：「复制图片」—— 位图进剪贴板（可粘贴到微信 / Word），
         区别于「复制块」（在文档内复制一份） */
      html += '<div class="mi" data-act="copyimg"><span style="width:18px;text-align:center">🖼</span>复制图片</div>';
      html += '<div class="sep"></div>';
      html += '<div class="mi" data-act="up"><span style="width:18px;text-align:center">⬆</span>上移</div>';
      html += '<div class="mi" data-act="down"><span style="width:18px;text-align:center">⬇</span>下移</div>';
      html += '<div class="sep"></div>';
      html += '<div class="mi danger" data-act="del"><span style="width:18px;text-align:center">🗑</span>删除块</div>';
    } else {
      if (SPEC_EDIT[kind]) {
        html += '<div class="mi" data-act="edit"><span style="width:18px;text-align:center">✎</span>' +
                SPEC_EDIT[kind] + '</div>';
        html += '<div class="sep"></div>';
      }
      /* v3.30.10（MMD-5）：图表块菜单补「复制块」（dup 为通用动作） */
      if (kind === 'chart')
        html += '<div class="mi" data-act="dup"><span style="width:18px;text-align:center">⧉</span>复制块</div>';
      html += '<div class="mi" data-act="up"><span style="width:18px;text-align:center">⬆</span>上移</div>';"""),
    # applyBlockAct 新动作
    ("""    /* v3.30.16：图片块「显示图片」—— 应用内大图预览 */
    if (act === 'viewimg') { hidePops(); openImgPreview(i); return; }""",
     """    /* v3.30.16：图片块「显示图片」—— 应用内大图预览 */
    if (act === 'viewimg') { hidePops(); openImgPreview(i); return; }
    /* v3.30.17：图片右键菜单 —— 重置尺寸 / 存储转换 / 修改图片名称 */
    if (act === 'imgreset') { hidePops(); resetObjSize('img', i); return; }
    if (act === 'imgmode') { hidePops(); requestImgModeSwitch(i); return; }
    if (act === 'imgrename') { hidePops(); openRenamePop(i); return; }"""),
    # 状态栏：imgStatusLabel + 自动化接口
    ("""  /* ---------- v3.25 图片存储操作：重命名 / 内嵌 ↔ 相对路径（经 Python 落盘） ---------- */
  function imgRawSrc(idx) {
    var spec = figFromRaw(state.raw[idx]);
    return spec ? spec.src : '';
  }""",
     """  /* ---------- v3.25 图片存储操作：重命名 / 内嵌 ↔ 相对路径（经 Python 落盘） ---------- */
  function imgRawSrc(idx) {
    var spec = figFromRaw(state.raw[idx]);
    return spec ? spec.src : '';
  }
  /* v3.30.17：状态栏图片描述（存储方式 + 存储文件名），随 getCaretLineCol 轮询回报 */
  function imgStatusLabel(idx) {
    var src = imgRawSrc(idx);
    if (!src) return '';
    if (/^data:/i.test(src)) return '图片 · 内嵌存储';
    if (/^https?:/i.test(src)) return '图片 · 网络图片';
    var k = Math.max(src.lastIndexOf('/'), src.lastIndexOf('\\\\'));
    var name = k >= 0 ? src.slice(k + 1) : src;
    try { name = decodeURIComponent(name); } catch (e2) {}
    var abs = /^(?:[A-Za-z]:[\\\\/]|file:)/i.test(src);
    return '图片 · ' + (abs ? '绝对路径存储' : '相对路径存储') + ' · ' + name;
  }
  window.__imgStatusLabel = function (idx) { return imgStatusLabel(idx); };"""),
    # getCaretLineCol：未编辑态回报图片选中状态
    ("""      var bi = state.editIdx;
      /* 注意：写作模式下 srcEl 恒为 null（仅源码模式才有值），
         此前误加了 !srcEl 判断导致行列永远不更新，只显示初始的 行1·列1 */
      if (bi < 0 || bi >= state.raw.length) return null;""",
     """      var bi = state.editIdx;
      /* 注意：写作模式下 srcEl 恒为 null（仅源码模式才有值），
         此前误加了 !srcEl 判断导致行列永远不更新，只显示初始的 行1·列1 */
      if (bi < 0 || bi >= state.raw.length) {
        /* v3.30.17：未在文字编辑态 —— 选中图片时回报存储方式 / 文件名（状态栏），
           未选中回报空（Python 清掉上一条的图片状态） */
        return JSON.stringify({ imgsel: 1,
          type: (objSel && objSel.kind === 'img') ? imgStatusLabel(objSel.idx) : '' });
      }"""),
])

# ---- mainwindow.py：_on_caret 处理 imgsel ----
patch(M, [
    ("""        if isinstance(data, dict) and data.get("line"):
            self._pos.setText(f"行 {int(data['line'])} · 列 {int(data.get('col', 1))}")
            # v3.30.10（HP-1）：当前块类型（标题 N / 表格 / 图表 / 公式 / 引用…）
            self._blktype.setText(data.get("type") or "")""",
     """        if isinstance(data, dict) and data.get("line"):
            self._pos.setText(f"行 {int(data['line'])} · 列 {int(data.get('col', 1))}")
            # v3.30.10（HP-1）：当前块类型（标题 N / 表格 / 图表 / 公式 / 引用…）
            self._blktype.setText(data.get("type") or "")
        elif isinstance(data, dict) and data.get("imgsel"):
            # v3.30.17：选中图片 → 状态栏显示存储方式 / 存储文件名；取消选中 → 清空
            self._blktype.setText(data.get("type") or "")"""),
])

print("patched ok, %d replacements" % n)
