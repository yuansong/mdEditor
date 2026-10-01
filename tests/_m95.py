# -*- coding: utf-8 -*-
"""m95：v3.32 产品化批次功能探针
P1-1 模板 / P0-1 影子草稿 / P0-3 立即留档 / P0-7 归档 /
P0-4③ 导出自检 / P0-6① 版本比较 / P0-5 诊断信息
"""
import json, os, sys, tempfile, zipfile
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m95.txt")
out = []
def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))

RES = []
def check(name, cond, detail=""):
    RES.append(("PASS" if cond else "FAIL", name))
    log(("PASS | " if cond else "FAIL | ") + name + (" | " + str(detail)[:200] if detail else ""))

from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
app = QApplication(sys.argv)
os.environ["MDEDITOR_SKIP_DRAFT"] = "1"   # 模板段先禁用草稿，G2 段再恢复
from mainwindow import MainWindow
from config import DRAFT_DIR, APP_VERSION
win = MainWindow()
win.show()

def wait(ms):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def js(code, ms=15000):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(ms, loop.quit)
    win._js_active(code, cb); loop.exec()
    return box["r"]

def rawblocks():
    return json.loads(js("window.__raw()") or "{}").get("raw", [])

def open_slash(max_try=3):
    """打开斜杠菜单：Esc 清理 -> 空块 mousedown + '/' 键 -> 轮询菜单展开。"""
    for _ in range(max_try):
        js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
           "var el=document.querySelector('#editor .blk');if(!el) return 'NOBLK';"
           "el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
           "var t=document.querySelector('#editor .raw-edit')||el;"
           "t.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true}));return 't'})()")
        wait(400)
        if js("document.getElementById('slashmenu').classList.contains('show')") is True:
            return True
    return False

wait(6000)

# ---------- G1：P1-1 斜杠菜单「模板」一级项 ----------
js("window.setMarkdown('')")
wait(600)
opened = open_slash()
check("TPL-0 斜杠菜单可打开", opened, "")
r = js("(function(){try{return window.__slashPick('tpl', 4)}catch(e){return 'ERR:'+e.message}})()")   # v3.38（TPL-F）新默认序：索引 4 = 技术笔记
wait(600)
raw = rawblocks()
full = "\n\n".join(raw)
check("TPL-1 模板一级项 __slashPick('tpl',4) 成功", r == "OK", r)
check("TPL-2 技术笔记模板整组插入（多块 + 标题）",
      "# 技术笔记" in full and "## 背景" in full and len(raw) >= 6,
      "blocks=%d" % len(raw))
# 逐个验证 6 个子项可应用 + 关键内容
setmd = lambda md: js("window.setMarkdown(%s)" % json.dumps(md, ensure_ascii=False))
marks = {0: "议题与讨论", 1: "本周完成", 2: "功能需求", 3: "总体设计",
         4: "关键结论", 5: "项目概述", 6: "评审对象", 7: "摘要"}   # v3.38（TPL-F）新默认序
allok = True
det = []
for sub, mark in marks.items():
    setmd("")
    wait(300)
    if not open_slash():
        allok = False; det.append("%d:NOMENU" % sub); continue
    r = js("(function(){try{return window.__slashPick('tpl', %d)}catch(e){return 'ERR:'+e.message}})()" % sub)
    wait(500)
    f2 = "\n\n".join(rawblocks())
    if r != "OK" or mark not in f2:
        allok = False; det.append("%d:%s:%s" % (sub, r, f2[:40]))
check("TPL-3 模板 6 子项全部可插入（项目文档/周报/评审/论文/纪要）", allok, ";".join(det))

# ---------- G2：P0-1 影子草稿 ----------
os.environ.pop("MDEDITOR_SKIP_DRAFT", None)   # 恢复草稿功能
doc = {"path": None, "content": ""}
win._save_draft(doc, "草稿内容测试")
fp = doc.get("draft", "")
ok_written = bool(fp) and os.path.exists(fp) and open(fp, encoding="utf-8").read().startswith("草稿内容测试")
check("DRAFT-1 草稿落盘 drafts/ 目录", ok_written, fp)
ts = doc.get("draft_ts", 0)
win._save_draft(doc, "节流期内不应重写")
still_same = open(fp, encoding="utf-8").read().startswith("草稿内容测试")
check("DRAFT-2 10 秒节流（draft_ts 已设置且文件未变）",
      doc.get("draft_ts") == ts and still_same, "")
# 删除打桩：本环境 os.remove 需用户确认，改记录调用参数（语义断言）
_removed = []
_real_remove = os.remove
os.remove = lambda p: _removed.append(p)
try:
    win._remove_draft(doc)
finally:
    os.remove = _real_remove
check("DRAFT-3 删除草稿（尝试移除草稿文件 + 引用清空）",
      fp in _removed and not doc.get("draft") and not doc.get("draft_ts"), str(_removed))

# ---------- G3：P0-1 启动恢复（弹窗打桩为「恢复」） ----------
# 先隔离历史遗留草稿（此前崩溃运行残留），保证本段确定性
quarantine = os.path.join(tempfile.gettempdir(), "m95_drafts_quarantine")
os.makedirs(quarantine, exist_ok=True)
for name in os.listdir(DRAFT_DIR):
    if name.endswith(".md"):
        try:
            os.replace(os.path.join(DRAFT_DIR, name),
                       os.path.join(quarantine, name))
        except OSError:
            pass
d1 = os.path.join(DRAFT_DIR, "draft-test-a.md")
with open(d1, "w", encoding="utf-8") as f:
    f.write("# 恢复测试\n\n这是孤儿草稿。")
n_docs0 = len(win._docs)
_q = QMessageBox.question
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
try:
    win.check_draft_recovery()
finally:
    QMessageBox.question = _q
new_doc = win._docs[-1] if len(win._docs) > n_docs0 else {}
check("DRAFT-4 孤儿草稿恢复为新标签（内容 + 草稿关联）",
      len(win._docs) > n_docs0 and "恢复测试" in (new_doc.get("content") or "")
      and new_doc.get("draft") == d1, str(new_doc.get("draft")))
# 忽略分支 → .dismissed
d2 = os.path.join(DRAFT_DIR, "draft-test-b.md")
with open(d2, "w", encoding="utf-8") as f:
    f.write("另一份")
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
try:
    win.check_draft_recovery()
finally:
    QMessageBox.question = _q
check("DRAFT-5 忽略 → 草稿标记 .dismissed 不再打扰",
      not os.path.exists(d2) and os.path.exists(d2 + ".dismissed"), d2)
# 收尾隔离：d1 已恢复关联，test-b 已 .dismissed；把测试草稿全部改名隔离
# （本环境删除需确认，统一 rename 到隔离目录）
os.environ["MDEDITOR_SKIP_DRAFT"] = "1"
try: os.replace(d2 + ".dismissed", os.path.join(quarantine, "draft-test-b.md.dismissed"))
except OSError: pass
try:
    for name in os.listdir(DRAFT_DIR):
        if name.endswith(".md"):
            try:
                os.replace(os.path.join(DRAFT_DIR, name),
                           os.path.join(quarantine, name))
            except OSError:
                pass
except OSError:
    pass

# ---------- G4：P0-4③ 导出自检 ----------
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
try:
    ok1 = win._export_selfcheck("正文\n\n```math\nE=mc^2\n```\n\n```mermaid\nflowchart TD\nA-->B\n```", "docx")
    ok2 = win._export_selfcheck("只有正文", "docx")
    ok3 = win._export_selfcheck_remote(3)
finally:
    QMessageBox.question = _q
check("EXPORT-1 docx 自检：含公式/图表时询问且默认继续", ok1 is True, ok1)
check("EXPORT-2 纯文本不弹自检", ok2 is True, ok2)
check("EXPORT-3 网络图片自检", ok3 is True, ok3)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
try:
    ok4 = win._export_selfcheck("```math\nx\n```", "epub")
finally:
    QMessageBox.question = _q
check("EXPORT-4 自检可取消导出", ok4 is False, ok4)

# ---------- G5：P0-6① 版本比较 ----------
vg = MainWindow._ver_ge
check("VER-1 语义化版本比较",
      vg("3.33.0", "3.32.0") and not vg("3.31.9", "3.32.0")
      and vg("3.32", "3.32.0") and vg("4.0", "3.99.9"), "")

# ---------- G6：P0-5 诊断信息 ----------
# 探针不经 main() 启动，预置一份日志文件验证"最近日志"采集
from config import LOG_DIR
os.makedirs(LOG_DIR, exist_ok=True)
with open(os.path.join(LOG_DIR, "mdEditor.log"), "a", encoding="utf-8") as f:
    f.write("2026-09-30 01:00:00 INFO [mdEditor.app] 探针预置日志行\n")
win.copy_diagnostics()
clip = QApplication.clipboard().text()
check("DIAG-1 诊断信息含版本与日志段",
      ("mdEditor v" + APP_VERSION) in clip and "最近日志" in clip and "pandoc" in clip,
      clip[:80])

# ---------- G7：P0-7 工作区归档 ----------
tmp = tempfile.mkdtemp(prefix="mdarch")
with open(os.path.join(tmp, "a.md"), "w", encoding="utf-8") as f:
    f.write("# A")
os.makedirs(os.path.join(tmp, "assets"), exist_ok=True)
with open(os.path.join(tmp, "assets", "p.png"), "wb") as f:
    f.write(b"\x89PNG\r\n")
zpath = os.path.abspath(os.path.join(tmp, "..", "mdarch_out.zip"))
_q = QMessageBox.question; _i = QMessageBox.information
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
try:
    fd, md_path = tempfile.mkstemp(suffix=".md", dir=tmp); os.close(fd)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# A")
    win.file_path = md_path
    win._docs.append({"path": md_path, "content": "# A"})
    win._cur = len(win._docs) - 1
    _g = QFileDialog.getSaveFileName
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (zpath, ""))
    try:
        win.archive_workspace()
    finally:
        QFileDialog.getSaveFileName = _g
finally:
    QMessageBox.question = _q; QMessageBox.information = _i
names = zipfile.ZipFile(zpath).namelist() if os.path.exists(zpath) else []
check("ARCH-1 归档 zip 含 md 与 assets",
      os.path.exists(zpath) and any(n.endswith("a.md") for n in names)
      and any("assets/p.png" in n for n in names), str(names)[:160])
try: os.remove(zpath)
except OSError: pass

# ---------- G8：P0-3 立即留档（对有路径文档） ----------
tmp2 = tempfile.mkdtemp(prefix="mdsnap")
snap_md = os.path.join(tmp2, "doc.md")
with open(snap_md, "w", encoding="utf-8") as f:
    f.write("旧内容")
setmd("当前内容")
wait(400)
win.file_path = snap_md
if 0 <= win._cur < len(win._docs):
    win._docs[win._cur]["path"] = snap_md
win.manual_snapshot()
wait(900)
hd = win._history_dir(snap_md)
snaps = os.listdir(hd) if os.path.isdir(hd) else []
check("SNAP-1 立即留档生成快照文件", len(snaps) >= 1, str(snaps))

log("DONE count=%d pass=%d" % (
    len(RES), sum(1 for s, _ in RES if s == "PASS")))
log("SUMMARY " + json.dumps(RES, ensure_ascii=False))
print("DONE")
