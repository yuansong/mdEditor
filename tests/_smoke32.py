# -*- coding: utf-8 -*-
"""v3.32 冒烟测试：结构性大项批次（#5 侧栏文件管理（v3.31.2 目录页移除改版）/ #15 懒渲染 / #27 diff / #7/#8 大纲 / #18/#19 查找全部命中）。
输出：tests/_smoke32.txt
"""
import json
import os
import shutil
import sys
import tempfile

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke32.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


app = QApplication(sys.argv)
from mainwindow import MainWindow
from dialogs import HistoryDialog, DiffDialog

win = MainWindow()
# v3.38：复位 diff/layout（QSettings 跨运行持久，走双栏时单栏 view 不渲染）
win._settings.setValue("diff/layout", "unified")
win._settings.sync()
win.show()


def js(code):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def setmd(md):
    js(f"window.setMarkdown({json.dumps(md)})")
    wait(400)


wait(3000)
js("window.setSlashMenuConfig(null)")

# ================= #5（v3.31.2 改版：目录页整体移除，管理操作迁入文件页右键） =================
tmp = tempfile.mkdtemp(prefix="mded_tree_")
a_path = os.path.join(tmp, "a.md")
with open(a_path, "w", encoding="utf-8") as f:
    f.write("# A 文档\n\n内容A")

sb = win._sidebar
check("#5 目录页已移除：侧栏 2 页（文件 / 大纲）", sb.stack.count() == 2, sb.stack.count())
check("#5 目录页已移除：无 tree 控件 / 目录页签 / TAB_TREE",
      not hasattr(sb, "tree") and not hasattr(sb, "btn_tree") and not hasattr(sb, "TAB_TREE"),
      "sidebar cleaned")
check("#5 管理操作已迁入文件页：新建/新建文件夹/重命名/删除四方法就位",
      all(hasattr(sb, m) for m in ("_file_new_file", "_file_new_dir", "_file_rename", "_file_delete")),
      "menu ops present")

win.open_file(a_path)
wait(1500)
check("#5 文件页跟随当前文档（_cur_file/_cur_dir）",
      os.path.normcase(getattr(sb, "_cur_file", "") or "") == os.path.normcase(a_path)
      and os.path.normcase(getattr(sb, "_cur_dir", "") or "") == os.path.normcase(tmp),
      f"{getattr(sb, '_cur_file', None)} | {getattr(sb, '_cur_dir', None)}")

# recycle_path（文件页「删除（移入回收站）」使用的主窗口通道）
del_path = os.path.join(tmp, "delme.txt")
with open(del_path, "w", encoding="utf-8") as f:
    f.write("x")
rc = win.recycle_path(del_path)
check("#5 recycle_path 移入回收站", rc is True and not os.path.exists(del_path), f"rc={rc}")

# ================= #27 版本 diff =================
diff = DiffDialog(win)
diff.show_diff("测试对比", "第一行\n第二行\n第三行", "第一行\n第二行改\n第三行\n新增行", "旧", "新")
wait(200)
check("#27 diff 统计行", "新增 2 行" in diff.stat_lbl.text() and "删除 1 行" in diff.stat_lbl.text(),
      diff.stat_lbl.text())
check("#27 diff 内容渲染", "新增行" in diff.view.toPlainText() and "第二行改" in diff.view.toPlainText(),
      diff.view.toPlainText()[:60])
diff.show_diff("测试对比", "相同内容", "相同内容", "A", "B")
check("#27 内容一致提示", "内容一致" in diff.stat_lbl.text(), diff.stat_lbl.text())
diff.close()
hd = HistoryDialog(win)
check("#27 HistoryDialog 具备 diff 按钮",
      hasattr(hd, "b_diff_cur") and hasattr(hd, "b_diff_prev"), "ok")
hd.close()

# ================= #7/#8 大纲（end/words + 调序） =================
doc = "# A\n\np1\n\n## A1\n\np2\n\n# B\n\np3"
setmd(doc)
r = js("JSON.stringify(window.getOutline())")
ol = json.loads(r or "[]")
check("#8 getOutline 3 个标题", len(ol) == 3, r[:120])
check("#8 一级节 end=4", ol and ol[0].get("end") == 4, r[:160])
# v3.31.2（#2）：分节字数口径与状态栏对齐（中文按字/拉丁按词、剔围栏与行内码、标题剥 # 前缀）
# A 节 = A(1)+p1(1)+A1(1)+p2(1)；A1 节 = A1+p2；B 节 = B+p3
check("#8 分节字数新口径（A 节 4 / A1 节 2 / B 节 2）",
      [h.get("words") for h in ol] == [4, 2, 2], str([h.get("words") for h in ol]))
# 侧栏后缀（v3.31.2 #3：默认关，可开关切换）
win._sidebar.set_outline(ol)
wait(200)
t0 = win._sidebar.outline.topLevelItem(0).text(0)
check("#8 后缀默认不显示（outlineWords 默认关）", "字" not in t0, t0)
win.set_outline_words(True)
wait(200)
t0 = win._sidebar.outline.topLevelItem(0).text(0)
check("#8 开启后大纲项显示分节字数后缀", "4 字" in t0, t0)
win.set_outline_words(False)
wait(200)
t0 = win._sidebar.outline.topLevelItem(0).text(0)
check("#8 关闭后后缀即被剥离", "字" not in t0, t0)

# 拖拽调序（模拟 _on_outline_dropped 的数据通路：同级 [A, B] → [B, A]）
r = js(f"window.reorderSections({json.dumps(json.dumps([[4, 6], [0, 4]]))})")
check("#7 reorderSections [B,A] 返回 ok", r == "ok", r)
md_now = js("window.getMarkdown()")
check("#7 章节整段移动（B 到最前）", (md_now or "").startswith("# B"), (md_now or "")[:40])
check("#7 子节随父节移动", "## A1" in (md_now or "") and (md_now or "").index("# A") < (md_now or "").index("## A1"),
      (md_now or "")[:60])

r = js(f"window.reorderSections({json.dumps(json.dumps([[0, 3], [4, 6]]))})")
check("#7 不连续区间拒绝", r == "invalid", r)
r = js(f"window.reorderSections({json.dumps(json.dumps([[0, 9]]))})")
check("#7 越界区间拒绝", r == "invalid", r)

# ================= #18/#19 查找全部命中 =================
fdoc = "# 标题页\n\nalpha beta alpha\n\n- gamma 与 alpha\n\n带 alpha 的段落"
setmd(fdoc)
r = js("window.findAll('alpha', false, true, 500)")
d = json.loads(r or "{}")
check("#18 全部命中计数 = 4", d.get("count") == 4, r[:160])
check("#18 命中列表带预览", len(d.get("matches") or []) == 4 and "alpha" in d["matches"][0].get("prev", ""),
      str(d.get("matches", [])[:1]))
check("#18 CSS Custom Highlight 生效", d.get("hl") is True, f"hl={d.get('hl')}")
r = js("window.gotoMatch(0)")
check("#19 gotoMatch 跳转 ok", r == "ok", r)
r = js("window.findClearHits(); 'cleared'")
check("#18 清除高亮", r == "cleared", r)
r = js("window.findAll('[', false, true, 500)")
d = json.loads(r or "{}")
check("#18 非法正则回退不报错", isinstance(d.get("count"), int), r[:80])
r = js("window.findAll('不存在词xyz', false, true, 500)")
d = json.loads(r or "{}")
check("#18 无匹配返回 0", d.get("count") == 0 and d.get("matches") == [], r[:80])
# 源码模式路径（API：setSourceMode，与 mainwindow._on_loaded 同款）
js("window.setSourceMode(true)")
wait(400)
r = js("window.findAll('alpha', false, true, 500)")
d = json.loads(r or "{}")
check("#18 源码模式仍可统计（无高亮）", d.get("count") == 4 and d.get("hl") is False, r[:120])
js("window.setSourceMode(false)")
wait(400)

# ================= #15 超长文档懒渲染 =================
setmd("短文档\n\n第二段")
r = int(float(js("window.__lazyCount()") or "0"))
check("#15 短文档无懒渲染块", r == 0, f"count={r}")

big = "\n\n".join(f"段落{i}" for i in range(420)) + "\n\n```js\nvar x = 1;\n```"
setmd(big)
wait(800)
cnt = int(float(js("window.__lazyCount()") or "0"))
nblk = int(float(js("document.querySelectorAll('#editor > .blk').length") or "0"))
check("#15 长文档块数完整（421）", nblk == 421, f"blocks={nblk}")
check("#15 视口外块保留懒标记（0 < lazy < 421）", 0 < cnt < 421, f"lazy={cnt}")
check("#15 懒渲染块骨架仍在（fence 代码栏已构建）",
      int(float(js("document.querySelectorAll('#editor .codebar').length") or "0")) == 1,
      js("document.querySelectorAll('#editor .codebar').length"))
js("window.__lazyFlushAll()")
r = int(float(js("window.__lazyCount()") or "0"))
check("#15 flushAll 后无残留懒块", r == 0, f"count={r}")
check("#15 内容无损（getMarkdown 与原文一致）",
      (js("window.getMarkdown()") or "").replace("\r", "") == big.replace("\r", ""), "md ok")
# 二次 setMarkdown（小文档）恢复正常全量渲染
setmd("```js\nvar y = 2;\n```")
r = int(float(js("document.querySelectorAll('#editor .codebar').length") or "0"))
check("#15 小文档恢复正常构建", r == 1, f"codebar={r}")

# ================= 收尾 =================
try:
    diff.deleteLater()
    hd.deleteLater()
except Exception:
    pass
shutil.rmtree(tmp, ignore_errors=True)
setmd("")
check("收尾：编辑区清空", js("window.getMarkdown()") == "", "done")
flush()
print("SMOKE32 DONE")
