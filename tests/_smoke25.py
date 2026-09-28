# -*- coding: utf-8 -*-
"""v3.21 冒烟测试：P0 四项
  P0-1 图片落盘相对路径 / 内嵌 data URL 双模式（可配置）+ 迁移内嵌图片
  P0-2 状态栏字数统计与阅读时长
  P0-3 侧栏跨文件全文搜索
  P0-4 导出 docx / EPUB / PDF 书签（入口与调用链）
"""
import base64
import json
import os
import sys
import tempfile

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QEventLoop, QTimer, QSettings

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke25.txt")
results = []


def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(results))


app = QApplication(sys.argv)
from mainwindow import MainWindow  # noqa: E402
import sidebar as sbmod  # noqa: E402

# 前置：复位持久化设置（必须与主窗口同一存储、且在窗口创建前）
_st = QSettings("WorkBuddy", "WorkBuddyMarkdown")
_st.setValue("imageMode", "assets")
_st.setValue("pandocPath", "")
_st.setValue("outlineLevel", 3)
_st.setValue("fileListMode", "current")
_st.sync()

win = MainWindow()
win.show()


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


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


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

tmpdir = tempfile.mkdtemp(prefix="md25_")
docpath = os.path.join(tmpdir, "笔记.md")
with open(docpath, "w", encoding="utf-8") as f:
    f.write("# 笔记\n\n正文内容。\n")
png1 = os.path.join(tmpdir, "shot.png")
with open(png1, "wb") as f:
    f.write(PNG)

wait(2500)  # 等 QWebEngine 页面加载完成

# ================= 1) 默认图片模式 = assets =================
check("默认图片存放方式为 assets（相对路径）", win._image_mode == "assets", win._image_mode)
check("图片模式已下发到编辑器（默认 assets）",
      js("window.__imgMode") == "assets", js("window.__imgMode"))

# ================= 2) 相对路径插入 =================
win._load_path(docpath)
wait(1600)
check("测试文档已打开", os.path.abspath(win.file_path) == os.path.abspath(docpath), win.file_path)
check("文档目录已下发到编辑器（相对路径解析基础）",
      os.path.normcase(str(js("window.__docDir") or "")) == os.path.normcase(tmpdir),
      js("window.__docDir"))

win._insert_image_file(png1)
wait(900)
assets = os.path.join(tmpdir, "笔记.assets")
check("assets 目录已创建", os.path.isdir(assets), assets)
# v3.25：assets 文件名改为「5 位编号_名称」（00001_shot.png）
check("图片已落盘为文件（v3.25 编号名）",
      os.path.isfile(os.path.join(assets, "00001_shot.png")),
      os.listdir(assets) if os.path.isdir(assets) else "NO DIR")

md = js("window.getMarkdown()") or ""
check("Markdown 写入相对路径（不使用 data URL）",
      "](笔记.assets/00001_shot.png)" in md and "data:image" not in md, md[-120:])
check("相对路径已解析成绝对 file:// URL 供渲染",
      str(js("window.__resolveImgSrc('笔记.assets/00001_shot.png')")).startswith("file:///"),
      js("window.__resolveImgSrc('笔记.assets/00001_shot.png')"))
check("绝对 / data: / http(s) 路径不被改写",
      js("window.__resolveImgSrc('https://a.b/c.png')") == "https://a.b/c.png"
      and js("window.__resolveImgSrc('D:/x/y.png')") == "D:/x/y.png")

# ================= 3) 重复插入自动递增编号（v3.25：编号名天然不覆盖） =================
win._insert_image_file(png1)
wait(900)
names = sorted(os.listdir(assets))
check("重复插入自动递增编号（00002_shot.png，不覆盖）",
      "00002_shot.png" in names and "00001_shot.png" in names, names)

# ================= 4) 切换到 embed 模式 =================
win.set_image_mode("embed")
wait(500)
check("模式已切换为 embed 并持久化",
      win._image_mode == "embed" and str(win._settings.value("imageMode")) == "embed"
      and js("window.__imgMode") == "embed",
      f"{win._image_mode}/{win._settings.value('imageMode')}")
win._insert_image_file(png1)
wait(900)
md2 = js("window.getMarkdown()") or ""
check("embed 模式插入 data URL（不落盘）",
      "data:image/png;base64," in md2, md2[-90:])
check("embed 模式未新增文件", sorted(os.listdir(assets)) == names,
      sorted(os.listdir(assets)))

# ================= 5) 未保存文档回退内嵌 =================
win.set_image_mode("assets")
wait(400)
win._add_doc(path=None, text="")
wait(1200)
check("未命名文档已激活（无路径）", not win.file_path, win.file_path)
win._insert_image_file(png1)
wait(900)
md3 = js("window.getMarkdown()") or ""
check("未保存文档时安全回退为内嵌 data URL",
      "data:image/png;base64," in md3, md3[-80:])

# ================= 6) 迁移内嵌图片 =================
win._load_path(docpath)
wait(1500)
big_b64 = base64.b64encode(PNG).decode()
embedded = (f"# 迁移测试\n\n![a](data:image/png;base64,{big_b64})\n\n"
            f"正文。\n\n![b](data:image/png;base64,{big_b64})\n")
js("window.setMarkdown(%s)" % json.dumps(embedded))
wait(800)
new_md, ok_n, bad_n = win._extract_embedded_images(embedded)
check("迁移：内嵌图片全部抽出", ok_n == 2 and bad_n == 0, f"ok={ok_n} bad={bad_n}")
check("迁移：路径替换为相对路径且无 data URL",
      "data:image" not in new_md and "笔记.assets/" in new_md,
      new_md.replace("\n", "\\n")[:130])
check("迁移：文件确实写入磁盘",
      os.path.isfile(os.path.join(assets, "a.png"))
      and os.path.isfile(os.path.join(assets, "b.png")),
      sorted(os.listdir(assets)))

# 迁移命令（走 QMessageBox，先打桩）
_orig_info, _orig_q = QMessageBox.information, QMessageBox.question
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Ok)
js("window.setMarkdown(%s)" % json.dumps(embedded))
wait(600)
win.migrate_embedded_images()
wait(1200)
saved = open(docpath, "r", encoding="utf-8").read()
check("迁移命令：文档已写回并瘦身",
      "data:image" not in saved and "笔记.assets/" in saved, saved.replace("\n", "\\n")[:120])
QMessageBox.information, QMessageBox.question = _orig_info, _orig_q

# ================= 7) 字数统计（P0-2） =================
js("window.setMarkdown('中文五个字\\n\\nHello world 12345, ok!\\n\\n> 引用一段')")
wait(900)
st = js("JSON.stringify(window.__stats)")
try:
    s = json.loads(st or "{}")
except ValueError:
    s = {}
check("stats 字段齐全（cjk/words/raw/digits/punct/paragraphs/lines/readMin）",
      all(k in s for k in ("chars", "cjk", "words", "raw", "digits", "punct",
                           "paragraphs", "lines", "readMin")), st)
# 文本：'中文五个字'(5) + 'Hello world 12345, ok!'(Hello/world/ok=3 词) + '引用一段'(4)
check("中文字符按字计（5+4=9）/ 英文按词计（Hello/world/ok=3）",
      s.get("cjk") == 9 and s.get("words") == 3, st)
check("纯数字不计入英文单词（12345）", s.get("digits") == 5 and s.get("words") == 3, st)
check("段落数与行数", s.get("paragraphs") == 3 and s.get("lines") == 5, st)
check("字数 = 中文字符 + 英文单词 且给出阅读时长",
      s.get("chars") == (s.get("cjk", 0) + s.get("words", 0)) and int(s.get("readMin", -1)) >= 0, st)
wait(600)
check("状态栏显示「字数 … · 约 … 分钟」",
      win._count.text().startswith("字数") and "约" in win._count.text()
      and "分钟" in win._count.text(), win._count.text())

# 统计详情弹窗（打桩，不应抛异常）
_box = {}
QMessageBox.information = staticmethod(lambda *a, **k: _box.update(txt=a[2] if len(a) > 2 else "") or QMessageBox.Ok)
win._show_stats_detail()
wait(200)
check("统计详情弹窗内容含各项指标",
      "字数" in _box.get("txt", "") and "段落" in _box.get("txt", "")
      and "阅读时长" in _box.get("txt", ""), _box.get("txt", "")[:90])
QMessageBox.information = _orig_info

# ================= 8) 跨文件搜索（P0-3） =================
sdir = tempfile.mkdtemp(prefix="md25s_")
with open(os.path.join(sdir, "alpha.md"), "w", encoding="utf-8") as f:
    f.write("# Alpha\n\nhello world\n\nHELLO again\n")
with open(os.path.join(sdir, "beta.txt"), "w", encoding="utf-8") as f:
    f.write("nothing here\n\nhello from beta\n")
os.makedirs(os.path.join(sdir, "sub", "deep"), exist_ok=True)
with open(os.path.join(sdir, "sub", "deep", "gamma.md"), "w", encoding="utf-8") as f:
    f.write("hello nested\n")
os.makedirs(os.path.join(sdir, "skipme.assets"), exist_ok=True)
with open(os.path.join(sdir, "skipme.assets", "x.md"), "w", encoding="utf-8") as f:
    f.write("hello should-be-skipped\n")

sb = win._sidebar
sb.set_root(sdir)
win.file_path = os.path.abspath(os.path.join(sdir, "alpha.md"))
check("搜索根目录取当前文档所在目录",
      os.path.normcase(win.search_root()) == os.path.normcase(sdir), win.search_root())

# v3.26：查找面板合并为单页；v3.31（#5）：侧栏新增「目录」页（共 3 个标签页）
check("侧栏标签页 = 文件 / 大纲 / 目录（3 个）", sb.stack.count() == 3, sb.stack.count())
check("侧栏不再有搜索面板 / show_search 入口",
      not hasattr(sb, "search_panel") and not hasattr(sb, "TAB_SEARCH")
      and not hasattr(sb, "show_search"), "sidebar cleaned")
win.show_search()
wait(400)
fd = win._find_dlg
sp = fd.search_panel
check("Ctrl+Shift+F 打开查找对话框且范围为「全局搜索」",
      fd.isVisible() and fd.scope_box.currentIndex() == fd.SCOPE_GLOBAL,
      fd.scope_box.currentIndex())
check("范围下拉含 全局搜索 / 当前文件 两项（置于搜索框前）",
      [fd.scope_box.itemText(0), fd.scope_box.itemText(1)] == ["全局搜索", "当前文件"],
      [fd.scope_box.itemText(0), fd.scope_box.itemText(1)])
check("v3.26 已移除区分大小写 / 正则复选框",
      not hasattr(sp, "search_cs") and not hasattr(sp, "search_re"), "removed")
check("搜索框旁有 ？ 正则帮助按钮",
      hasattr(fd, "help_btn") and fd.help_btn.text() == "?", fd.help_btn.text())

sp.run_with_query("hello")
wait(400)
tops = sp.search_tree.topLevelItemCount()
files_hit = sorted(sp.search_tree.topLevelItem(i).text(0).split("  (")[0]
                   for i in range(tops))
check("跨文件搜索命中 3 个文件（含子目录，跳过 .assets）",
      tops == 3 and "alpha.md" in files_hit and "beta.txt" in files_hit
      and "gamma.md" in files_hit, files_hit)
a_top = next(sp.search_tree.topLevelItem(i) for i in range(tops)
             if sp.search_tree.topLevelItem(i).text(0).startswith("alpha.md"))
check("固定不区分大小写：alpha.md 命中 2 处（hello / HELLO）",
      a_top.childCount() == 2 and "(2)" in a_top.text(0), a_top.text(0))

sp.run_with_query(r"hello\s+from")
wait(400)
check("默认支持正则搜索：仅命中 beta.txt",
      sp.search_tree.topLevelItemCount() == 1
      and sp.search_tree.topLevelItem(0).text(0).startswith("beta.txt"),
      sp.search_tree.topLevelItem(0).text(0) if sp.search_tree.topLevelItemCount() else "none")

sp.run_with_query(r"[unclosed")   # 非法正则 → 回退普通文本
wait(400)
check("非法正则回退为普通文本搜索（不报错）",
      sp.search_tree.topLevelItemCount() == 0 and "未找到" in sp.search_info.text(),
      sp.search_info.text())

sp.search_ext.setCurrentIndex(1)      # 仅 .md
sp.run_with_query("hello")
wait(400)
names_ext = [sp.search_tree.topLevelItem(i).text(0).split("  (")[0]
             for i in range(sp.search_tree.topLevelItemCount())]
check("扩展名筛选「仅 .md」排除 beta.txt",
      "beta.txt" not in names_ext and "alpha.md" in names_ext, names_ext)

sp.search_ext.setCurrentIndex(0)
sp.run_with_query("绝不存在的关键词XYZ")
wait(300)
check("无命中时给出提示", sp.search_tree.topLevelItemCount() == 0
      and "未找到" in sp.search_info.text(), sp.search_info.text())

# v3.29：范围切到「当前文件」→ 全局结果区与当前文件查找同页常显（不再互斥隐藏）
fd.scope_box.setCurrentIndex(fd.SCOPE_FILE)
wait(200)
check("切到「当前文件」：全局面板仍可见（同页合一）", sp.search_tree.isVisible(), sp.search_tree.isVisible())
check("切到「当前文件」：查找框获得焦点",
      fd.find_edit.hasFocus() or fd.find_edit.isActiveWindow(), fd.find_edit.hasFocus())

# 点击结果 → 打开文件并跳转
fd.scope_box.setCurrentIndex(fd.SCOPE_GLOBAL)
wait(200)
sp.run_with_query("hello from beta")
wait(400)
hit = sp.search_tree.topLevelItem(0).child(0)
sp._on_search_click(hit, 0)
wait(2600)
check("点击搜索结果打开对应文件",
      win.file_path and os.path.basename(win.file_path) == "beta.txt", win.file_path)
check("跳转请求已消费（无残留待跳转）",
      getattr(win, "_pending_goto", None) is None, getattr(win, "_pending_goto", None))
fd.close()

# ================= 9) 导出入口与调用链（P0-4） =================
acts = win._shortcut_acts
check("菜单动作已注册：导出 Word / EPUB / 迁移内嵌图片 / 在文件夹中搜索",
      all(k in acts for k in ("导出 Word (docx)…", "导出 EPUB…",
                              "迁移内嵌图片为文件…", "在文件夹中搜索…")),
      [k for k in acts if "导出" in k or "迁移" in k or "搜索" in k])
check("「在文件夹中搜索」默认快捷键 Ctrl+Shift+F",
      acts["在文件夹中搜索…"].shortcut().toString() == "Ctrl+Shift+F",
      acts["在文件夹中搜索…"].shortcut().toString())
check("PDF 导出改为「含书签」入口",
      any("含书签" in k for k in acts), [k for k in acts if "PDF" in k])

# 统计/大纲缓存供 PDF 书签使用
win._load_path(docpath)
wait(1500)
js("window.setMarkdown('# 第一章\\n\\n内容\\n\\n## 小节\\n\\n# 第二章\\n')")
wait(900)
win._poll()
wait(700)
check("大纲缓存已填充（PDF 书签数据源）",
      isinstance(win._outline_cache, list) and len(win._outline_cache) >= 3,
      win._outline_cache)

# 真实调用 docx/epub 写入（走 exporters，跳过文件对话框）
import exporters  # noqa: E402
md_now = js("window.getMarkdown()") or ""
d_ok, d_msg = exporters.write_docx(md_now, os.path.join(tmpdir, "o.docx"), tmpdir, "笔记")
e_ok, e_msg = exporters.write_epub(md_now, os.path.join(tmpdir, "o.epub"), tmpdir, "笔记")
check("导出 docx 调用链可用", d_ok and os.path.getsize(os.path.join(tmpdir, "o.docx")) > 4000, d_msg)
check("导出 EPUB 调用链可用", e_ok and os.path.getsize(os.path.join(tmpdir, "o.epub")) > 800, e_msg)

# ================= 10) 设置对话框同步 =================
from dialogs import SettingsDialog  # noqa: E402
dlg = SettingsDialog(win)
dlg.show()
wait(500)
check("设置→编辑器 有「图片存放方式」且与主窗口同步",
      dlg.image_mode_box.count() == 2
      and dlg.image_mode_box.currentData() == win._image_mode,
      dlg.image_mode_box.currentData())
check("设置→通用 有 pandoc 路径输入框",
      hasattr(dlg, "pandoc_edit") and dlg.pandoc_edit.text() == (win._pandoc_path or ""),
      dlg.pandoc_edit.text())
dlg.image_mode_box.setCurrentIndex(1)
wait(500)
check("设置里切换为 embed 即时生效",
      win._image_mode == "embed" and js("window.__imgMode") == "embed", win._image_mode)
dlg.image_mode_box.setCurrentIndex(0)
wait(400)
check("设置里切回 assets 即时生效", win._image_mode == "assets" and js("window.__imgMode") == "assets")
dlg.pandoc_edit.setText("")
dlg._on_pandoc_path()
check("pandoc 路径保存逻辑可用（留空=自动探测）",
      str(win._settings.value("pandocPath", "x")) == "", win._settings.value("pandocPath"))
dlg.close()

# 复原
win._settings.setValue("imageMode", "assets")
win._settings.setValue("pandocPath", "")
win._settings.sync()

total = len(results)
fails = sum(1 for r in results if r.startswith("FAIL"))
results.append(f"--- {total - fails} PASS / {fails} FAIL ---")
flush()
print(f"SMOKE25 DONE: {total - fails} PASS / {fails} FAIL")
