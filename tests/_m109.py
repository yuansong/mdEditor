# -*- coding: utf-8 -*-
"""m109：单元格内插入列表的占位提示（CELL-LIST）
用户报告：表格单元格里插入列表会多出「列表项」提示文字，单元格外没有。
v3.37 修复：空格插入改为空 <li></li>（待办保留功能性 ☐ 标记、光标其后），
与外部列表插入行为对齐。
"""
import json, os, sys, time
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m109.txt")
LINES = []
def log(s): LINES.append(str(s))
def check(name, cond, extra=""):
    LINES.append(("PASS | " if cond else "FAIL | ") + name + ("" if cond else " | " + str(extra)[:400]))

def js(win, code, timeout=8000):
    res = {"v": None, "done": False}
    def cb(r):
        res["v"] = r; res["done"] = True
    win._js_active(code, cb)
    t0 = time.time()
    while not res["done"] and time.time() - t0 < timeout / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)
    return res["v"]

def wait(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000.0:
        QApplication.processEvents(); time.sleep(0.02)

def setmd(win, md):
    js(win, "window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(450)

def md0(win):
    return js(win, "window.getMarkdown()") or ""

CELL = r"""(function(){
  var tbl = document.querySelectorAll('#editor table')[0];
  if (!tbl) return '{}';
  return JSON.stringify({html: tbl.rows[%d].cells[%d].innerHTML,
                         txt: tbl.rows[%d].cells[%d].textContent});
})()"""

def cell_of(win, r, c):
    try:
        return json.loads(js(win, CELL % (r, c, r, c)) or "{}")
    except Exception:
        return {}

TYPE_IN = r"""(function(){
  var s = window.getSelection();
  if (!s.rangeCount) return 'NOSEL';
  document.execCommand('insertText', false, %s);
  return 'ok';
})()"""

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    wait(3000)
    for _ in range(20):
        if js(win, "!!window.setMarkdown"):
            break
        wait(500)

    TBL = "| 甲 | 乙 |\n| --- | --- |\n|  |  |\n| 已有文字 |  |"

    # ---------- A：空格插无序列表 ----------
    setmd(win, TBL)
    r = js(win, "window.__cellIns(0, 1, 0, '- ')")
    wait(450)
    cA = cell_of(win, 1, 0)   # tbl.rows[0]=表头；首个数据行=rows[1]
    log("[A] ret=%s html=%s raw=%s" % (r, json.dumps(cA.get("html"), ensure_ascii=False),
                                       json.dumps(md0(win), ensure_ascii=False)))
    check("A1 空格插无序列表：无占位提示文字",
          r == "OK" and "列表项" not in (cA.get("html") or "")
          and "<ul><li>" in (cA.get("html") or ""), json.dumps(cA, ensure_ascii=False))
    t = js(win, TYPE_IN % json.dumps("甲项"))
    wait(450)
    cA2 = cell_of(win, 1, 0)
    log("[A] 打字后 html=%s raw=%s" % (json.dumps(cA2.get("html"), ensure_ascii=False),
                                       json.dumps(md0(win), ensure_ascii=False)))
    check("A2 光标在空项内，输入直接落进列表项",
          "甲项" in (cA2.get("html") or "") and "列表项" not in (cA2.get("html") or ""),
          json.dumps(cA2, ensure_ascii=False))

    # ---------- B：空格插有序列表 ----------
    setmd(win, TBL)
    r = js(win, "window.__cellIns(0, 1, 1, '1. ')")
    wait(450)
    cB = cell_of(win, 1, 1)
    log("[B] ret=%s html=%s" % (r, json.dumps(cB.get("html"), ensure_ascii=False)))
    check("B1 空格插有序列表：无占位提示文字",
          r == "OK" and "列表项" not in (cB.get("html") or "")
          and "<ol><li>" in (cB.get("html") or ""), json.dumps(cB, ensure_ascii=False))

    # ---------- C：空格插待办 ----------
    setmd(win, TBL)
    r = js(win, "window.__cellIns(0, 1, 0, '- [ ] ')")
    wait(450)
    cC = cell_of(win, 1, 0)
    log("[C] ret=%s html=%s" % (r, json.dumps(cC.get("html"), ensure_ascii=False)))
    check("C1 空格插待办：只保留功能性 ☐ 标记（无「待办事项」提示文字）",
          r == "OK" and "待办事项" not in (cC.get("html") or "")
          and "☐" in (cC.get("html") or ""), json.dumps(cC, ensure_ascii=False))
    t = js(win, TYPE_IN % json.dumps("买牛奶"))
    wait(450)
    cC2 = cell_of(win, 1, 0)
    log("[C] 打字后 html=%s" % json.dumps(cC2.get("html"), ensure_ascii=False))
    check("C2 待办光标在 ☐ 之后，输入不吞标记",
          "☐" in (cC2.get("html") or "") and "买牛奶" in (cC2.get("html") or "")
          and "待办事项" not in (cC2.get("html") or ""), json.dumps(cC2, ensure_ascii=False))

    # ---------- D：格内有文字 → 逐行转 li（既有行为回归） ----------
    setmd(win, TBL)
    r = js(win, "window.__cellIns(0, 2, 0, '- ')")
    wait(450)
    cD = cell_of(win, 2, 0)
    log("[D] ret=%s html=%s" % (r, json.dumps(cD.get("html"), ensure_ascii=False)))
    check("D1 格内有文字仍逐行转 li（不丢内容、无占位文字）",
          r == "OK" and "已有文字" in (cD.get("html") or "") and "<li>已有文字</li>" in (cD.get("html") or "")
          and "列表项" not in (cD.get("html") or ""), json.dumps(cD, ensure_ascii=False))

    with io_open(OUT) as f:
        f.write("\n".join(LINES) + "\n")
    print("DONE m109")

def io_open(p):
    import io
    return io.open(p, "w", encoding="utf-8")

if __name__ == "__main__":
    main()
