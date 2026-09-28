# -*- coding: utf-8 -*-
"""v3.32 冒烟测试：结构性大项批次（#5 目录树 / #15 懒渲染 / #27 diff / #7/#8 大纲 / #18/#19 查找全部命中）。
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

# ================= #5 树形文件目录 =================
tmp = tempfile.mkdtemp(prefix="mded_tree_")
sub = os.path.join(tmp, "sub")
sub2 = os.path.join(tmp, "sub2")
os.makedirs(sub)
os.makedirs(sub2)
a_path = os.path.join(tmp, "a.md")
b_path = os.path.join(tmp, "b.md")
c_path = os.path.join(sub, "c.md")
for p, text in ((a_path, "# A 文档\n\n内容A"), (b_path, "# B 文档"), (c_path, "# C")):
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
with open(os.path.join(tmp, "note.txt"), "w", encoding="utf-8") as f:
    f.write("not md")
os.makedirs(os.path.join(tmp, "x.assets"), exist_ok=True)

sb = win._sidebar
sb.set_tree_root(tmp, persist=False)
wait(200)
tops = [sb.tree.topLevelItem(i).text(0) for i in range(sb.tree.topLevelItemCount())]
check("#5 根目录条目 = sub/sub2 + a.md + b.md + note.txt（.txt 在扩展名白名单，无 assets/隐藏）",
      len(tops) == 5 and all(any(k in t for t in tops) for k in ("sub", "a.md", "b.md", "note.txt")),
      str(tops))
check("#5 目录排前、文件排后", tops[0].find("sub") >= 0, str(tops))

# 懒加载展开
it_sub = None
for i in range(sb.tree.topLevelItemCount()):
    if "sub" in sb.tree.topLevelItem(i).text(0) and "sub2" not in sb.tree.topLevelItem(i).text(0):
        it_sub = sb.tree.topLevelItem(i)
        break
if it_sub is not None:
    it_sub.setExpanded(True)
    wait(300)
    kids = [it_sub.child(i).text(0) for i in range(it_sub.childCount())]
    check("#5 子目录懒加载展开出现 c.md", any("c.md" in k for k in kids), str(kids))
else:
    check("#5 子目录懒加载展开出现 c.md", False, "sub item not found")

# 空文件夹占位
it_sub2 = None
for i in range(sb.tree.topLevelItemCount()):
    if "sub2" in sb.tree.topLevelItem(i).text(0):
        it_sub2 = sb.tree.topLevelItem(i)
        break
if it_sub2 is not None:
    it_sub2.setExpanded(True)
    wait(300)
    kids2 = [it_sub2.child(i).text(0) for i in range(it_sub2.childCount())]
    check("#5 空文件夹显示占位", any("空文件夹" in k for k in kids2), str(kids2))
else:
    check("#5 空文件夹显示占位", False, "sub2 item not found")

# 当前文档高亮 + 跟随
win.open_file(a_path)
wait(1500)
sb.tree_follow(a_path)
wait(200)
bold_items = []


def walk_bold(item):
    for k in range(item.childCount()):
        c = item.child(k)
        if c.font(0).bold():
            bold_items.append(c.text(0))
        walk_bold(c)


walk_bold(sb.tree.invisibleRootItem())
check("#5 当前文档 a.md 加粗高亮", any("a.md" in t for t in bold_items), str(bold_items))

# 不存在根目录 → 清空提示
sb.set_tree_root(os.path.join(tmp, "不存在目录"), persist=False)
wait(200)
tops2 = [sb.tree.topLevelItem(i).text(0) for i in range(sb.tree.topLevelItemCount())]
check("#5 根目录不存在 → 提示占位", len(tops2) == 1 and "双击上方选择根目录" in tops2[0], str(tops2))
sb.set_tree_root(tmp, persist=False)

# recycle_path
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
check("#8 分节字数（A 节 10 / A1 节 6 / B 节 4）",
      [h.get("words") for h in ol] == [10, 6, 4], str([h.get("words") for h in ol]))
# 侧栏后缀
win._sidebar.set_outline(ol)
wait(200)
t0 = win._sidebar.outline.topLevelItem(0).text(0)
check("#8 大纲项显示分节字数后缀", "10 字" in t0, t0)

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
