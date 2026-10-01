# -*- coding: utf-8 -*-
"""smoke33 FAIL 甄别探针 v2：每步打点 + 全局看门狗（120s 强制退出）。
输出：tests/_m33b_out.txt
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

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m33b_out.txt")
lines = []


def say(s):
    lines.append(s)
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


app = QApplication(sys.argv)

# 全局看门狗：120s 后强制退出，避免 runner 420s 超时
def _watchdog():
    say("WATCHDOG: 120s 强制退出（卡点见最后一条 STEP）")
    os._exit(9)


QTimer.singleShot(120000, _watchdog)

from mainwindow import MainWindow

say("STEP: 创建主窗口")
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
say("STEP: 初始化完成")
js("window.setSlashMenuConfig(null)")

# ---------- A. 转义管道表格 ----------
say("STEP: A setmd 表格")
setmd("列A\\|B | 列C\n| --- | --- |\n| 1 | 2 |")
info = js("""(function(){
  var b = document.querySelector('#editor > .blk');
  return JSON.stringify({tag: b ? b.tagName : null, cls: b ? b.className : null,
    hasTable: !!b.querySelector('table'), head: (b.textContent || '').slice(0, 40)});
})()""")
say("A 转义管道表格块形态: " + str(info))

# ---------- B. 标签切换：慢速基准 ----------
n0 = len(win._docs)
say("STEP: B 初始标签数=" + str(n0))
setmd("TAB0内容甲")
say("STEP: B setmd TAB0 完成")
win.new_file()
say("STEP: B new_file#1 返回")
wait(2500)
say("STEP: B wait2500#1 完成")
setmd("TAB1内容乙")
say("STEP: B setmd TAB1 完成")
win.new_file()
say("STEP: B new_file#2 返回")
wait(2500)
say("STEP: B wait2500#2 完成")
win._tabbar.setCurrentIndex(n0)
say("STEP: B setCurrentIndex(n0) 返回")
wait(2500)
say("STEP: B wait2500#3 完成")
md0 = js("window.getMarkdown()") or ""
say("B 慢速切回标签0: " + ("PASS 内容=" + md0[:20] if "TAB0内容甲" in md0 else "FAIL 内容=" + md0[:20]))
win._tabbar.setCurrentIndex(n0 + 1)
say("STEP: B setCurrentIndex(n0+1) 返回")
wait(2500)
md1 = js("window.getMarkdown()") or ""
say("B 慢速切到标签1: " + ("PASS 内容=" + md1[:20] if "TAB1内容乙" in md1 else "FAIL 内容=" + md1[:20]))

# ---------- C. 快速切换压力后是否卡死 ----------
say("STEP: C 压力开始")
for i in range(12):
    win._tabbar.setCurrentIndex(n0 + (i % 3))
    wait(60)
say("STEP: C 压力循环完成")
wait(2500)
win._tabbar.setCurrentIndex(n0)
wait(2500)
md0b = js("window.getMarkdown()") or ""
say("C 压力后慢速切回标签0: " + ("PASS 内容=" + md0b[:20] if "TAB0内容甲" in md0b else "FAIL 内容=" + md0b[:20]))
say("C _switching=" + str(getattr(win, "_switching", None)) + " _cur=" + str(getattr(win, "_cur", None)))

# ---------- D. 真实键入路径的自动保存 ----------
say("STEP: D 建临时文件")
tmp = tempfile.mkdtemp(prefix="mded_m33b_")
doc_path = os.path.join(tmp, "键入文档.md")
with open(doc_path, "w", encoding="utf-8") as f:
    f.write("v1 原始内容")
win.open_file(doc_path)
say("STEP: D open_file 返回")
wait(2500)
say("STEP: D wait2500 完成")
r1 = js("""(function(){
  var b = document.querySelector('#editor .blk');
  if (!b) return 'no-blk';
  b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
  b.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
  return 'clicked';
})()""")
say("STEP: D 点击=" + str(r1))
wait(600)
r2 = js("""(function(){
  var el = document.querySelector('#editor .blk.raw-edit') ||
           document.querySelector('#editor .blk[contenteditable="true"]');
  if (!el) return 'no-edit-el';
  el.focus();
  var sel = window.getSelection();
  var range = document.createRange();
  range.selectNodeContents(el);
  range.collapse(false);
  sel.removeAllRanges(); sel.addRange(range);
  document.execCommand('insertText', false, 'X键入');
  return 'inserted';
})()""")
say("STEP: D 插入=" + str(r2))
wait(3000)
with open(doc_path, "r", encoding="utf-8") as f:
    disk = f.read()
say("D 磁盘内容: " + repr(disk[:24]) + " 结尾=" + repr(disk[-3:]))
hist_dir = os.path.join(tmp, ".mdeditor-history", "键入文档.md")
snaps = os.listdir(hist_dir) if os.path.isdir(hist_dir) else []
say("D 版本快照数: " + str(len(snaps)))
say("D 自动保存判定: " + ("PASS" if "X键入" in disk else "FAIL 未落盘"))

# ---------- 收尾 ----------
shutil.rmtree(tmp, ignore_errors=True)
say("DONE")
