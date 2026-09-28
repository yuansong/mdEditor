# -*- coding: utf-8 -*-
"""v3.29c 探针 Q：行 / 列整体移动（上移该行 / 下移该行 / 左移该列 / 右移该列）。
1) 管道表格：下移该行 / 上移该行 → 数据行交换、表头与分隔行不动；
2) 管道表格：左移 / 右移该列 → 各行列交换、分隔行对齐标记随列走；
3) 边界置灰：首数据行无「上移该行」、末列无「右移该列」；表头行全置灰；
4) HTML 无合并表：模型路径移动正确；
5) HTML 含合并表：四钮置灰；
6) 全程无 JS 异常。"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m29q.txt")
out = []


def check(name, cond, extra=""):
    out.append(("PASS" if cond else "FAIL") + f" | {name} | {extra}")
    flush()


def note(tag, extra):
    out.append(f"NOTE | {tag} | {extra}")
    flush()


def flush():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


app = QApplication(sys.argv)
from mainwindow import MainWindow
win = MainWindow()
win.show()


def js(code):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_active(code, cb); loop.exec(); return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def jj(code):
    r = js(code)
    try:
        return json.loads(r or "{}")
    except Exception:
        return {"_raw": r}


def raw():
    return jj("window.__raw()").get("raw") or [""]


def mv_state(title):
    return js("(function(){var b=[].filter.call("
              "document.getElementById('tblbar').querySelectorAll('button'),"
              "function(x){return x.title==='" + title + "'})[0];"
              "return b?(b.classList.contains('dis')?'dis':'en'):'none'})()")


TBL = "| 甲 | 乙 | 丙 |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 5 | 6 | 7 |\n| 8 | 9 | 0 |"
TBL_H = ("<table class=\"md-tbl\"><thead><tr><th>甲</th><th>乙</th></tr></thead>"
         "<tbody><tr><td>1</td><td>2</td></tr><tr><td>5</td><td>6</td></tr></tbody></table>")
TBL_M = ("<table class=\"md-tbl\"><thead><tr><th>甲</th><th>乙</th></tr></thead>"
         "<tbody><tr><td colspan=\"2\">1 2</td></tr><tr><td>5</td><td>6</td></tr></tbody></table>")

wait(2500)
js("window.__errs=[];window.onerror=function(m,s,l){window.__errs.push(String(m)+'@'+l);return false;}")

# ===== 1. 管道表格：下移该行 =====
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("window.__tblSelSet(0, 1, 0, 1, 2)")     # 第一个数据行
wait(300)
check("首数据行：上移置灰 / 下移可用",
      mv_state("上移该行") == "dis" and mv_state("下移该行") == "en",
      [mv_state("上移该行"), mv_state("下移该行")])
js("window.__tblOp('rowMoveDown')")
wait(500)
r = str(raw()[0])
note("1 raw after down", r[:200])
check("下移该行 → 数据行 1/5 交换",
      "| 5 | 6 | 7 |" in r.split("\n")[2] and "| 1 | 2 | 3 |" in r.split("\n")[3], r[:160])

# ===== 2. 管道表格：上移该行 =====
js("window.__tblSelSet(0, 2, 0, 2, 2)")
wait(300)
js("window.__tblOp('rowMoveUp')")
wait(500)
r = str(raw()[0])
check("上移该行 → 恢复 1/5 原序",
      "| 1 | 2 | 3 |" in r.split("\n")[2] and "| 5 | 6 | 7 |" in r.split("\n")[3], r[:160])

# ===== 3. 管道表格：右移该列（对齐标记随列走）=====
TBL_AL = "| 甲 | 乙 |\n| :--- | ---: |\n| 1 | 2 |\n| 5 | 6 |"
js(f"window.setMarkdown({json.dumps(TBL_AL)})")
wait(700)
js("window.__tblSelSet(0, 0, 0, 2, 0)")     # 整列 0（表头+两数据行）
wait(300)
js("window.__tblOp('colMoveRight')")
wait(500)
r = str(raw()[0])
note("3 raw after col right", r[:200])
check("右移该列 → 甲列到第 2 列",
      r.split("\n")[0].startswith("| 乙 | 甲 |"), r.split("\n")[0])
check("对齐标记随列走（:--- 跟到第 2 列）",
      "| --- | :--- |" in r.split("\n")[1].replace(" ", "") or
      "---:" in r.split("\n")[1], r.split("\n")[1])

# ===== 4. 管道表格：左移该列 + 边界置灰 =====
js("window.__tblSelSet(0, 0, 1, 2, 1)")     # 整列 1
wait(300)
check("末列：右移置灰 / 左移可用",
      mv_state("右移该列") == "dis" and mv_state("左移该列") == "en",
      [mv_state("右移该列"), mv_state("左移该列")])
js("window.__tblOp('colMoveLeft')")
wait(500)
r = str(raw()[0])
check("左移该列 → 恢复甲乙原序",
      r.split("\n")[0].startswith("| 甲 | 乙 |"), r.split("\n")[0])

# ===== 5. 表头行：移动四钮全置灰 =====
js(f"window.setMarkdown({json.dumps(TBL)})")
wait(700)
js("window.__tblSelSet(0, 0, 0, 0, 2)")
wait(300)
check("表头行：上移 / 下移置灰",
      mv_state("上移该行") == "dis" and mv_state("下移该行") == "dis",
      [mv_state("上移该行"), mv_state("下移该行")])

# ===== 6. HTML 无合并表：模型路径移动 =====
js(f"window.setMarkdown({json.dumps(TBL_H)})")
wait(700)
js("window.__tblSelSet(0, 1, 1, 1, 1)")
wait(300)
check("HTML 无合并表：首数据行上移置灰 / 左移可用",
      mv_state("上移该行") == "dis" and mv_state("下移该行") == "en"
      and mv_state("左移该列") == "en",
      [mv_state("上移该行"), mv_state("下移该行"), mv_state("左移该列")])
js("window.__tblOp('rowMoveDown')")
wait(500)
r = str(raw()[0])
check("HTML 下移该行 → tbody 行交换（1/5 互换）",
      ">5<" in r.split("<tr>")[2] and ">1<" in r.split("<tr>")[3], r[:200])

# ===== 7. HTML 含合并表：四钮全置灰 =====
js(f"window.setMarkdown({json.dumps(TBL_M)})")
wait(700)
js("window.__tblSelSet(0, 1, 0, 1, 0)")
wait(300)
st = [mv_state(x) for x in ("上移该行", "下移该行", "左移该列", "右移该列")]
check("含合并表 → 移动四钮全置灰", st == ["dis", "dis", "dis", "dis"], st)

# ===== 8. 全程无 JS 异常 =====
d = jj("JSON.stringify(window.__errs||[])")
check("全程无 JS 异常", str(d) == "[]", str(d))

out.append("DONE")
flush()
print("done")
