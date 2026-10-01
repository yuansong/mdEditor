# -*- coding: utf-8 -*-
"""m103c 列表：块菜单「转为 → 列表」子菜单在多行列表上的结构影响（二级走 mousedown，修正 _m103b R5）

源码依据：transformTo（9550-9552）case 'ul'/'ol'/'todo' = 前缀 + strip(raw)，
strip（9541）按 /gm 剥掉【所有行】的 marker → 多行列表转列表后可能只剩首行有 marker。
本探针用真实块菜单路径验证，并用渲染后果（可编辑 li 数）确认。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m103c_list.txt")
out = []
FAIL = [0]
TOTAL = [0]
ABN = []


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


wait(2800)


def rawof():
    try:
        return (json.loads(js("window.__raw()") or "{}").get("raw")) or []
    except Exception:
        return []


def setmd(md, ms=760):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def lstate():
    return jj("(function(){var lis=[].slice.call(document.querySelectorAll('#editor li'));"
              "return JSON.stringify({n:lis.length,"
              "lines:lis.map(function(l){return l.getAttribute('data-line')}),"
              "txt:lis.map(function(l){return (l.textContent||'').slice(0,30)})})})()")


def open_menu():
    js("window.openBlockMenu()")
    wait(560)


def sub_items():
    return jj("(function(){var S=document.getElementById('submenu');"
              "if(!S)return JSON.stringify({no:1});"
              "return JSON.stringify({show:S.classList.contains('show'),"
              "items:[].slice.call(S.querySelectorAll('.si')).map(function(s){return s.getAttribute('data-k')+':'+(s.querySelector('.lb')?s.querySelector('.lb').textContent:'')})})})()")


def pick_sub(k):
    js("(function(){var S=document.getElementById('submenu');"
       "var it=S&&S.querySelector('.si[data-k=\"" + str(k) + "\"]');"
       "if(!it)return 'no-si';"
       "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(620)


def open_list_sub():
    js("(function(){var BM=document.getElementById('blkmenu');"
       "var it=BM&&BM.querySelector('.mi[data-act=\"to-list\"]');"
       "if(!it)return 'no-item';"
       "it.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
       "it.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(520)


note("========== S1 三项无序列表 → 转为有序列表 ==========")
setmd("- 甲项\n- 乙项\n- 丙项")
open_menu()
bm = jj("(function(){var BM=document.getElementById('blkmenu');"
        "return JSON.stringify({show:BM.classList.contains('show'),"
        "items:[].slice.call(BM.querySelectorAll('.mi')).map(function(m){return m.getAttribute('data-act')})})})()")
note("  一级菜单=%s" % json.dumps(bm, ensure_ascii=False))
open_list_sub()
sb = sub_items()
note("  二级=%s" % json.dumps(sb, ensure_ascii=False))
pick_sub(1)          # 1 = 有序列表（BM_LIST_SUBS 顺序：无序 / 有序 / 待办）
g = rawof()
s = lstate()
note("  转有序后 raw=%s" % json.dumps(g, ensure_ascii=False))
note("  渲染 li=%s lines=%s txt=%s" % (s.get("n"), json.dumps(s.get("lines")), json.dumps(s.get("txt"), ensure_ascii=False)))
check("S1 三项列表「转为有序」后仍为 3 个独立可编辑项",
      s.get("n") == 3, "n=%s raw=%s" % (s.get("n"), json.dumps(g, ensure_ascii=False)))

note("========== S2 三项无序列表 → 转为待办事项 ==========")
setmd("- 甲项\n- 乙项\n- 丙项")
open_menu()
open_list_sub()
pick_sub(2)          # 2 = 待办事项
g = rawof()
s = lstate()
note("  转待办后 raw=%s" % json.dumps(g, ensure_ascii=False))
note("  渲染 li=%s cb=%s" % (s.get("n"), js("document.querySelectorAll('#editor li input[type=checkbox]').length")))
check("S2 三项列表「转为待办」后仍为 3 个独立可编辑项且都有 checkbox",
      s.get("n") == 3, "n=%s raw=%s" % (s.get("n"), json.dumps(g, ensure_ascii=False)))

note("========== S3 对照：多行段落 → 转为无序列表 ==========")
setmd("第一行\n第二行\n第三行")
open_menu()
open_list_sub()
pick_sub(0)
g = rawof()
s = lstate()
note("  段落转列表 raw=%s li=%s txt=%s" % (json.dumps(g, ensure_ascii=False), s.get("n"),
                                        json.dumps(s.get("txt"), ensure_ascii=False)))
check("S3 三行段落「转为无序列表」→ 三行各成一项（v3.38 LIST-6 修复：不再压成首项+延续行）",
      s.get("n") == 3, "n=%s raw=%s" % (s.get("n"), json.dumps(g, ensure_ascii=False)))

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
