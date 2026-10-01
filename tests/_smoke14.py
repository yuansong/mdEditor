# -*- coding: utf-8 -*-
"""v3.7 测试：侧栏对齐 / 块手柄修复 / 菜单排序 / 撤销重做按钮 / 清除格式 /
查找面板 / 快捷键设置 / 惰性视图。"""
import json
import sys
import time

sys.path.insert(0, r"E:\WorkBuddy\md-editor\src")
import os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke14.txt")

results = []

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import QEventLoop, QTimer, QSettings
from PySide6.QtGui import QKeySequence

app = QApplication.instance() or QApplication([])
from mainwindow import MainWindow

t0 = time.perf_counter()
win = MainWindow()
win.show()


def js(code):
    box = {}
    loop = QEventLoop()

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(10000, loop.quit)  # 超时保护
    win._js_active(code, cb)
    loop.exec()
    return box.get("r")


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def check(name, cond, detail=""):
    results.append(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))


# 等待编辑视图加载完成（同时统计"构造 -> 可编辑"耗时）
for _ in range(120):
    if win._vstate["edit"]["loaded"]:
        break
    wait(250)
startup_ms = int((time.perf_counter() - t0) * 1000)
check("edit view loaded", win._vstate["edit"]["loaded"], f"{startup_ms}ms")

# ---------- 1) 侧栏文件头左对齐（QPushButton 支持 text-align:left） ----------
fh = win._sidebar.file_header
check("file header is QPushButton", isinstance(fh, QPushButton), type(fh).__name__)
check("file header QSS left aligned", "text-align: left" in win._sidebar.styleSheet(), "")

# ---------- 2) 惰性双栏视图：启动后不应存在 ----------
check("dual views lazy (not created at startup)", win._view_src is None and win._view_prev is None,
      f"src={win._view_src}")

# ---------- 3) 菜单结构：文件/编辑/视图/设置/帮助，无格式 ----------
titles = [a.text().replace("&", "").split("(")[0] for a in win.menuBar().actions()]
check("menu order", titles == ["文件", "编辑", "视图", "设置", "帮助"], titles)
check("format menu removed", "格式" not in titles, titles)
# 格式命令仍作为隐藏动作存在（快捷键可用）
bold_act = win._shortcut_acts.get("加粗")
check("hidden format action kept", bold_act is not None and
      bold_act.shortcut().toString() == "Ctrl+B",
      bold_act.shortcut().toString() if bold_act else None)

# ---------- 4) 工具栏撤销 / 重做按钮 ----------
tips = [a.toolTip() for a in win._tool_tb.actions()]
check("toolbar undo", any("撤销" in t for t in tips), tips)
check("toolbar redo", any("重做" in t for t in tips), tips)

# ---------- 5) 快捷键设置对话框 ----------
from dialogs import ShortcutDialog
dlg = ShortcutDialog(win)
n_items = sum(dlg.tree.topLevelItem(i).childCount() for i in range(dlg.tree.topLevelItemCount()))
check("shortcut dialog populated", n_items >= 25, n_items)
# 修改快捷键 -> 生效并持久化 -> 恢复
win.apply_shortcut("加粗", QKeySequence("Ctrl+9"))
check("apply shortcut works", bold_act.shortcut().toString() == "Ctrl+9",
      bold_act.shortcut().toString())
saved = QSettings("WorkBuddy", "WorkBuddyMarkdown").value("shortcut/加粗")
check("shortcut persisted", isinstance(saved, str) and "Ctrl+9" in saved, saved)
win.apply_shortcut("加粗", QKeySequence("Ctrl+B"))
QSettings("WorkBuddy", "WorkBuddyMarkdown").remove("shortcut/加粗")
check("restore shortcut", bold_act.shortcut().toString() == "Ctrl+B",
      bold_act.shortcut().toString())
dlg.close()

wait(6000)  # 等待编辑器就绪后再做内核级测试

# ---------- 6) 块手柄不再"一碰就没" + 块菜单可操作 ----------
js("window.setMarkdown('第一段内容')")
wait(800)
r = js("""
(function(){
  var b=document.querySelector('.blk');
  b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:300,clientY:200}));
  var h=document.getElementById('blkhandle');
  if(h.style.display!=='flex') return 'NOT_SHOWN';
  /* 鼠标移到手柄上（target 为手柄本身）——修复点：不应被隐藏 */
  h.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:300,clientY:200}));
  if(h.style.display!=='flex') return 'HIDDEN_ON_HOVER';
  /* 打开块菜单 */
  h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
  var m=document.getElementById('blkmenu');
  return JSON.stringify({menu:m.classList.contains('show'),
    first:(m.querySelector('.mi')||{}).textContent||'',
    second:(m.querySelectorAll('.mi')[1]||{}).textContent||''});
})()
""")
d = json.loads(r or "{}")
check("block handle survives hover", d not in ("NOT_SHOWN", "HIDDEN_ON_HOVER"), r)
check("block menu opens", d.get("menu") is True, d)
check("block menu order (标题 first, 段落 second)",
      "标题" in (d.get("first") or "") and "段落" in (d.get("second") or ""), d)
# 点击"复制块" -> 块数 1 -> 2
js("(function(){var m=document.getElementById('blkmenu');"
   "var t=m.querySelector('[data-act=\"dup\"]');"
   "t.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "t.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'd'})()")
wait(500)
r = js("document.querySelectorAll('#editor .blk').length")
check("block menu dup works", r == 2, r)
r = js("(function(){return JSON.stringify({bm:document.getElementById('blkmenu').classList.contains('show')})})()")
check("block menu closed after act", json.loads(r or "{}").get("bm") is False, r)

# ---------- 7) 斜杠菜单排序 + 移除"正文段落" ----------
js("window.setMarkdown('')")
wait(800)
js("(function(){var el=document.querySelector('.blk');"
   "el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "var t=document.querySelector('.raw-edit')||el;"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true}));return 't'})()")
wait(300)
r = js("(function(){var m=document.getElementById('slashmenu');"
       "var lbs=[].map.call(m.querySelectorAll('.si .lb'),function(x){return x.textContent});"
       "return JSON.stringify(lbs)})()")
lbs = json.loads(r or "[]")
check("slash first is 标题", lbs and lbs[0] == "标题", lbs)
check("slash last is 公式（v3.9 移到最后）", lbs and lbs[-1] == "公式", lbs)
# v3.19 菜单顺序改为 标题/列表/表格/代码块/分割线/引用/图片/图表/公式
check("slash 引用 位于 分割线 之后、图片 之前",
      bool(lbs) and "引用" in lbs and lbs.index("分割线") < lbs.index("引用") < lbs.index("图片"), lbs)
check("slash no 正文段落", "正文段落" not in lbs, lbs)
# v3.30.3：移除 上标/下标；v3.31.3：脚注/定义列表合并为「脚注与定义」，位于 图表 之后；
# v3.32（P1-1）：新增「模板」位于 脚注与定义 之后、公式 之前
check("slash 含 脚注与定义/模板 且在 公式 之前（无上标/下标、无独立脚注/定义列表）",
      bool(lbs) and "脚注与定义" in lbs and "模板" in lbs and "上标 / 下标" not in lbs
      and "脚注" not in lbs and "定义列表" not in lbs
      and lbs.index("图表") < lbs.index("脚注与定义") < lbs.index("模板") < lbs.index("公式"), lbs)
js("(function(){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 'e'})()")

# ---------- 8) 行菜单：清除格式 ----------
js("window.setMarkdown('**已加粗**的文字')")
wait(800)
r = js("(function(){var st=document.querySelector('.blk strong');"
       "if(!st) return 'NO_STRONG';"
       "var tn=st.firstChild;var sel=getSelection();var range=document.createRange();"
       "range.setStart(tn,0);range.setEnd(tn,3);"
       "sel.removeAllRanges();sel.addRange(range);"
       "document.dispatchEvent(new Event('selectionchange'));return 'sel'})()")
wait(500)
r = js("(function(){var fb=document.getElementById('floatbar');"
       "var btns=[].map.call(fb.querySelectorAll('button'),function(b){return b.title});"
       "return JSON.stringify(btns)})()")
btns = json.loads(r or "[]")
check("floatbar no H button", "转为标题" not in btns, btns)
check("floatbar has 清除格式", "清除格式" in btns, btns)
js("(function(){var fb=document.getElementById('floatbar');"
   "var b=[].filter.call(fb.querySelectorAll('button'),function(x){return x.title==='清除格式'})[0];"
   "b.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));"
   "b.dispatchEvent(new MouseEvent('click',{bubbles:true}));return 'c'})()")
wait(500)
r = js("window.getMarkdown()")
check("clear format removes **", (r or "").strip() == "已加粗的文字", (r or "")[:40])

# ---------- 9) 查找 / 替换面板 ----------
win.show_find(False)
wait(300)
check("find dlg exists", hasattr(win, "_find_dlg"), "")
check("replace row hidden in find mode", not win._find_dlg.replace_row.isVisible(),
      win._find_dlg.replace_row.isVisible())
win.show_find(True)
wait(300)
check("replace row visible in replace mode", win._find_dlg.replace_row.isVisible(), "")
win._find_dlg.close()

# ---------- 10) 惰性视图：进入分屏后才创建 ----------
win._set_mode("dual")
for _ in range(60):
    if win._vstate["src"]["loaded"] and win._vstate["prev"]["loaded"]:
        break
    wait(250)
check("dual views created on demand", win._view_src is not None, "")
check("dual views loaded", win._vstate["src"]["loaded"] and win._vstate["prev"]["loaded"],
      f"src={win._vstate['src']['loaded']} prev={win._vstate['prev']['loaded']}")
r = js("document.body.innerText.length > 0")
check("dual src view has content", r is True, r)
win._set_mode("edit")
wait(500)

results.append(f"INFO startup(construct->editable) = {startup_ms}ms")

# 不调用 win.close()：未命名文档会弹"是否保存"对话框阻塞测试进程，直接强退
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("\n".join(results))
import os
os._exit(0)
