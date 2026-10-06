# -*- coding: utf-8 -*-
"""m118：v3.38 之六批验收（FMTB-5/6 + REFS-5 + OUT-3/4/5/6 + DIFF-1/2）

A 组 FMTB-5：横穿标记拒绝 / 全壳 toggle 保留 / clearfmt 豁免
B 组 FMTB-6：连打两次格式 + 立即撤销 → 单步回退
C 组 REFS-5：fnedit 末尾 ↓ 跳出
D 组 OUT-4：gotoHeading 文本校验（越界 index / 陈旧 index / 无 txt）
E 组 OUT-3：未命名清侧栏
F 组 OUT-5：会话记录与启动设置持久化
G 组 DIFF-1：词级 span / 300 护栏 / spacer / 布局切换 / QSettings 记忆
H 组 DIFF-2：两项互比（旧→新）
I 组 OUT-6：reorderSections 换序
结果：tests/_m118_batch.txt
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m118_batch.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m118_tmp.md")


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
        ABN.append(name + " || " + detail)
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def note(s):
    log("NOTE %s" % s)


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()

ST0 = {k: win._settings.value(k) for k in
       ("startupAction", "lastFile", "lastSidebarDir", "diff/layout")}


def js(code, timeout=15000):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(timeout, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def jj(code):
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


def setmd(md, ms=500):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def getraw():
    r = jj("window.__raw()")
    return r.get("raw", []) if isinstance(r, dict) else []


def toast():
    return js("window.takeToast()") or ""


def sel_nth(selector, idx, a, b, ms=260):
    js("(function(){var el=document.querySelectorAll(" + json.dumps(selector) + ")[" + str(idx) + "];"
       "if(!el)return 'no-el';"
       "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);"
       "var pos=0,sn=null,so=0,en=null,eo=0,n;"
       "while(n=w.nextNode()){var L=n.nodeValue.length;"
       "if(sn===null&&pos+L>=" + str(a) + "){sn=n;so=" + str(a) + "-pos;}"
       "if(pos+L>=" + str(b) + "){en=n;eo=" + str(b) + "-pos;break;}"
       "pos+=L;}"
       "if(!sn||!en)return 'no-range';"
       "var rg=document.createRange();rg.setStart(sn,so);rg.setEnd(en,eo);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def apply_act(action, ms=340):
    js("window.__applyFloat(" + json.dumps(action) + ")")
    wait(ms)


wait(2800)
js("window.setMarkdown('')")
wait(400)

# ============ A 组：FMTB-5 ============
note("========== A 组：FMTB-5 横穿标记守卫 ==========")
setmd("段落甲\n\n普通中*文*段落\n\n尾段")
# 选区构造 + apply + takeToast 原子执行（消除 poll 竞态 / 选区丢失）
t1 = js("(function(){var el=document.querySelectorAll('#editor p')[1];"
        "var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);"
        "var pos=0,sn=null,so=0,en=null,eo=0,n;"
        "while(n=w.nextNode()){var L=n.nodeValue.length;"
        "if(sn===null&&pos+L>=1){sn=n;so=1-pos;}"
        "if(pos+L>=4){en=n;eo=4-pos;break;}pos+=L;}"
        "var rg=document.createRange();rg.setStart(sn,so);rg.setEnd(en,eo);"
        "var s2=window.getSelection();s2.removeAllRanges();s2.addRange(rg);"
        "document.dispatchEvent(new Event('selectionchange'));"
        "window.__applyFloat('bold');"
        "return window.takeToast?window.takeToast():''})()") or ""
g = getraw()
check("A1 横穿标记 → 拒绝应用（raw 不变 + toast）",
      g[1] == "普通中*文*段落" and "横穿" in t1,
      "raw=%s toast=%s" % (json.dumps(g, ensure_ascii=False), t1))

setmd("普通**已加粗**尾")
sel_nth("#editor p", 0, 2, 5)          # 整壳内部「已加粗」（边界游程放行）
apply_act("bold")
g = getraw()
check("A2 全壳选区 → toggle 取消保留（FMT-5 语义不受守卫影响）",
      g == ["普通已加粗尾"],
      "raw=%s" % json.dumps(g, ensure_ascii=False))

setmd("普通中*文*段落")
sel_nth("#editor p", 0, 1, 4)
apply_act("clearfmt")
g = getraw()
check("A3 clearfmt 不受守卫拦（T× 仍可跨标记清除）",
      "*" not in "".join(g),
      "raw=%s" % json.dumps(g, ensure_ascii=False))

# ============ B 组：FMTB-6 ============
note("========== B 组：FMTB-6 防抖竞态 ==========")
setmd("甲乙")
sel_nth("#editor p", 0, 0, 1)
apply_act("bold", ms=120)              # 两操作间隔压进 350ms 防抖窗口
apply_act("highlite", ms=120)
g2 = getraw()
js("(function(){var t=document.activeElement||document.body;"
   "t.dispatchEvent(new KeyboardEvent('keydown',{key:'z',ctrlKey:true,bubbles:true,cancelable:true}));"
   "return 'ok'})()")
wait(500)
g1 = getraw()
check("B1 连打两次格式后撤销 → 单步回退（bold 保留、highlite 撤销）",
      any("**" in ln for ln in g1) and not any("==" in ln for ln in g1),
      "after2=%s after_undo=%s" % (json.dumps(g2, ensure_ascii=False), json.dumps(g1, ensure_ascii=False)))

# ============ C 组：REFS-5 ============
note("========== C 组：REFS-5 fnedit 方向键 ==========")
setmd("正文段落\n\n[^1]: 定义一内容\n\n[^2]: 定义二内容")
st = jj("(function(){var f=document.querySelectorAll('#editor .fnedit');"
        "if(f.length<2)return JSON.stringify({n:f.length});"
        "f[0].focus();var rg=document.createRange();rg.selectNodeContents(f[0]);rg.collapse(false);"
        "var s2=getSelection();s2.removeAllRanges();s2.addRange(rg);"
        "f[0].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));"
        "var ae=document.activeElement;"
        "return JSON.stringify({n:f.length,fnedit:!!(ae&&ae.classList&&ae.classList.contains('fnedit'))})})()")
check("C1 第一条定义末尾按 ↓ → 焦点跳出至第二条定义",
      st.get("n", 0) >= 2 and st.get("fnedit") is True,
      "st=%s" % json.dumps(st))

# ============ D 组：OUT-4 ============
note("========== D 组：OUT-4 gotoHeading 文本校验 ==========")
setmd("# 第一节\n\n段落甲\n\n## 第二节\n\n内容乙")


def flash_at(i):
    return jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(i) + "];"
              "return JSON.stringify({f:!!(b&&b.classList.contains('flash'))})})()").get("f")


js("window.gotoHeading(9,'第二节')")
wait(500)
check("D1 越界陈旧 index + 文本 → 按文本重查命中正确块", flash_at(2) is True,
      "flash2=%s" % flash_at(2))
wait(1800)
js("window.gotoHeading(0,'第二节')")
wait(500)
check("D2 陈旧 index(0) + 文本不符 → 重查命中块 2", flash_at(2) is True,
      "flash0=%s flash2=%s" % (flash_at(0), flash_at(2)))
wait(1800)
js("window.gotoHeading(0)")
wait(500)
check("D3 无 txt → 行为与旧版一致（index 直跳块 0）", flash_at(0) is True,
      "flash0=%s" % flash_at(0))

# ============ E 组：OUT-3 ============
note("========== E 组：OUT-3 未命名清侧栏 ==========")
with open(TMP, "w", encoding="utf-8") as f:
    f.write("# 临时\n\n内容\n")
win._sidebar.set_root(TMP)
check("E1 set_root 后 _cur_file 指向文件", win._sidebar._cur_file == TMP,
      "cur=%s" % win._sidebar._cur_file)
win._sidebar.clear_current_file()
check("E2 clear_current_file → 清 _cur_file + 取消列表高亮（保留目录）",
      win._sidebar._cur_file is None and win._sidebar.file_list.currentRow() == -1,
      "cur=%s row=%s" % (win._sidebar._cur_file, win._sidebar.file_list.currentRow()))

# ============ F 组：OUT-5 ============
note("========== F 组：OUT-5 会话恢复 ==========")
win.file_path = TMP
win._remember_last_session()
check("F1 _remember_last_session 写入 lastFile",
      win._settings.value("lastFile") == TMP,
      "v=%s" % win._settings.value("lastFile"))
win.set_startup_action("lastFileSide")
check("F2 set_startup_action 持久化 + 内存同步",
      win._settings.value("startupAction") == "lastFileSide"
      and win._startup_action == "lastFileSide",
      "v=%s" % win._settings.value("startupAction"))
win.set_startup_action("folder")
win.set_startup_folder(TMP)
check("F3 指定文件夹设置持久化",
      win._settings.value("startupAction") == "folder"
      and win._settings.value("startupFolder") == TMP,
      "a=%s f=%s" % (win._settings.value("startupAction"),
                     win._settings.value("startupFolder")))

# ============ G 组：DIFF-1 ============
note("========== G 组：DIFF-1 词级高亮 + 双栏 ==========")
from dialogs import DiffDialog
win._settings.setValue("diff/layout", "unified")
dlg = DiffDialog(win)
rows, add, dele, same = dlg._build_rows(["普通中文段落"], ["普通数字段落"], "#F5C4B3", "#9FE1CB")
check("G1 replace 配对行产出词级 span",
      rows[0][0] == "del" and rows[0][3] == "add"
      and "<span" in (rows[0][2] or "") and "<span" in (rows[0][5] or ""),
      "row0=%s" % json.dumps([rows[0][0], rows[0][2], rows[0][3], rows[0][5]]))
rows2, _a2, _d2, _s2 = dlg._build_rows(["甲" * 350], ["乙" * 350], "#F5C4B3", "#9FE1CB")
check("G2 超 300 字符护栏 → 退整行着色（无 span）",
      rows2[0][2] is None and rows2[0][5] is None, "")
rows3, _a3, _d3, _s3 = dlg._build_rows(["甲", "乙"], ["乙"], "#F5C4B3", "#9FE1CB")
check("G3 delete 块产出 spacer 行对", any(r[3] == "spacer" for r in rows3),
      "rows=%s" % json.dumps(rows3))
dlg.show_diff("测试", "甲\n乙\n丙", "甲\n乙2\n丙", "旧版", "新版")
check("G4 默认单栏（unified 视图可见、split 隐藏）",
      dlg.layout_box.currentData() == "unified" and dlg.view.isVisible()
      and dlg.split.isHidden(), "")
dlg.layout_box.setCurrentIndex(1)
check("G5 切双栏 → split 可见、左右行数恒等（含 spacer）",
      dlg.split.isVisible()
      and dlg.view_l.toPlainText().count("\n") == dlg.view_r.toPlainText().count("\n"),
      "l=%d r=%d" % (dlg.view_l.toPlainText().count("\n"),
                     dlg.view_r.toPlainText().count("\n")))
check("G6 布局选择写入 QSettings（diff/layout）",
      win._settings.value("diff/layout") == "split",
      "v=%s" % win._settings.value("diff/layout"))
dlg.layout_box.setCurrentIndex(0)
dlg.close()

# ============ H 组：DIFF-2 ============
note("========== H 组：DIFF-2 任意两版互比 ==========")
from dialogs import HistoryDialog
tdir = os.path.dirname(TMP)
fs = []
for k, txt in ((1, "v1\n"), (2, "v2\n"), (3, "v3\n")):
    fp = os.path.join(tdir, "_m118_snap%d.md" % k)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(txt)
    os.utime(fp, (1700000000 + k * 3600, 1700000000 + k * 3600))
    fs.append((fp, 1700000000 + k * 3600))
h = HistoryDialog(win)
h._cur_file = None
h._items = list(reversed(fs))          # 列表按时间倒序（最新在前）
h.listw.clear()
for fp, mt in h._items:
    import datetime as _dt
    h.listw.addItem(QListWidgetItem(_dt.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M:%S")))
h.listw.setCurrentRow(0)
check("H1 单选（默认预览态）→ 按钮禁用",
      not h.b_diff_two.isEnabled(), "")
h.listw.item(0).setSelected(True)
h.listw.item(2).setSelected(True)
check("H2 恰选两项 → 按钮启用",
      h.b_diff_two.isEnabled()
      and len(h.listw.selectedItems()) == 2, "")
h._diff_two()
dd = getattr(h, "_diff_dlg", None)
ok_h3 = False
if dd is not None and dd._rows is not None:
    texts_r = [r[4] for r in dd._rows]
    texts_l = [r[1] for r in dd._rows]
    ok_h3 = ("v3" in texts_r and "v1" in texts_l
             and dd._rows[0][4] == "v3")   # 旧(v1)→新(v3)
check("H3 对比按 mtime 旧→新（v1 在左 / v3 在右）", ok_h3,
      "rows=%s" % (json.dumps(dd._rows[:2]) if dd is not None and dd._rows else "none"))

# ============ I 组：OUT-6 ============
note("========== I 组：OUT-6 reorderSections ==========")
setmd("甲\n\n乙\n\n丙")
r = js("window.reorderSections('[[1,2],[0,1]]')")
g = getraw()
check("I1 换序生效（前两节互换）",
      r == "ok" and g[:2] == ["乙", "甲"],
      "r=%s raw=%s" % (r, json.dumps(g, ensure_ascii=False)))
win.reorder_sections([[1, 2], [0, 1]])   # 再换回来：乙甲丙 → 甲乙丙
wait(400)
check("I2 主窗口 reorder_sections 单视图路径无异常", getraw()[:2] == ["甲", "乙"],
      "raw=%s" % json.dumps(getraw(), ensure_ascii=False))

# ============ 清理 ============
note("========== 清理 QSettings ==========")
for k, v in ST0.items():
    if v is None:
        win._settings.remove(k)
    else:
        win._settings.setValue(k, v)
for k in range(1, 4):
    try:
        os.remove(os.path.join(os.path.dirname(TMP), "_m118_snap%d.md" % k))
    except OSError:
        pass
try:
    os.remove(TMP)
except OSError:
    pass
log("NOTE 清理完成（startupAction/lastFile/diff-layout 已还原）")

log("汇总 PASS=%d FAIL=%d" % (TOTAL[0] - FAIL[0], FAIL[0]))
print("TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
