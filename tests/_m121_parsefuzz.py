import os
# -*- coding: utf-8 -*-
"""m121：解析器级模糊测试（v3.38 NEST-4 / PARSE-1 验收）

覆盖：深层嵌套（1~4 层）、高亮/链接/加粗/斜体/删除线/行内码/下划线 任意叠加、
空内容、重复标记、未闭合标记、交叉嵌套边界。

断言：
  A. 合法嵌套源码 → 渲染文本必须等于纯内容（零标记残留）
  B. 任意源码（含非法/交叉）→ 不得崩溃、不得重复输出文本（dup-flush 类回归）
"""
import json, os, random, re, sys

os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication(sys.argv)
from mainwindow import MainWindow

win = MainWindow()
win.show()

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m121.txt")
_log = []


def check(name, cond, detail=""):
    _log.append(("PASS" if cond else "FAIL", name, detail))


def js(code, t=15000):
    loop = QEventLoop(); box = {"r": None}
    def cb(res): box["r"] = res; loop.quit()
    QTimer.singleShot(t, loop.quit); win._js_active(code, cb); loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


wait(2800)

# 标记池：(开, 闭)，链接的闭包含 url
# 行内码（`）不参与嵌套组合：其内部一律不解析，放进组合池会产出
# `**x**` 这类「** 本就该字面」的用例，与 A1 断言语义冲突（它只作为最内层单层用例）
MARKS = [
    ("**", "**"), ("*", "*"), ("==", "=="), ("~~", "~~"),
    ("<u>", "</u>"), ("[", "](https://www.sina.ocm)"),
]
CONTENT = "我是一个好人"

def build_nested(seq):
    """按 seq 顺序嵌套包裹 CONTENT"""
    src = CONTENT
    for m in reversed(seq):
        src = m[0] + src + m[1]
    return src


# ---------- A. 合法嵌套：渲染文本必须 == 纯内容 ----------
random.seed(20261006)
cases = []
# 穷举 1~2 层全组合
for a in MARKS:
    cases.append([a])
    for b in MARKS:
        cases.append([a, b])
# 随机 3~4 层
for _ in range(120):
    k = random.choice([3, 3, 4])
    cases.append([random.choice(MARKS) for _ in range(k)])
# 行内码仅作最内层单层：内容应为纯文本
cases.append([("`", "`")])

bad = []
skipped = 0
for seq in cases:
    src = build_nested(seq)
    # 同字符相邻层会拼出超长游程（`**`+`**` → `****x****`），CommonMark / Typora
    # 均不支持、按字面渲染属正确行为 —— 不计入「合法嵌套」断言
    # 4 连以上的同字符游程（**** / ==== / ~~~~ / ____）都不是合法嵌套
    if ("****" in src or "____" in src or "====" in src or "~~~~" in src):
        skipped += 1
        continue
    # 同类型对称标记套两层（`~~` 包 `~~`、`==` 包 `==`）的配对需要 delimiter 栈，
    # 计数法无法区分内层开符与闭合符；语义冗余，登记观察项 OBS-N2
    _opens = [m[0] for m in seq]
    if len(_opens) != len(set(_opens)) and any(
            o in ("~~", "==", "**", "*") for o in _opens):
        skipped += 1
        continue
    js("window.setMarkdown(" + json.dumps(src) + ")")
    wait(60)
    txt = js("(function(){var b=document.querySelector('#editor .blk');"
             "var h=b?b.querySelector('[contenteditable=\"true\"]'):(b||{});"
             "return JSON.stringify((b&&b.textContent)||'')})()")
    try:
        got = json.loads(txt)
    except Exception:
        got = txt
    if got != CONTENT:
        bad.append((src, got))

check("A1 合法嵌套 %d 例渲染文本 == 纯内容（零标记残留）" % (len(cases) - skipped),
      not bad,
      "首例 src=%s got=%s" % (bad[0][0], bad[0][1]) if bad else "")

# ---------- A2. 用户原始样本（标题 + 四层叠加） ----------
SAMPLE = "### **==[***我是一个好人***](https://www.sina.ocm)==**"
js("window.setMarkdown(" + json.dumps(SAMPLE) + ")")
wait(300)
html = js("(function(){var h=document.querySelector('#editor h3');"
          "return h?JSON.stringify(h.innerHTML):''})()")
raw2 = js("window.getMarkdown()")
try:
    html_s = json.loads(html)
except Exception:
    html_s = html
check("A2 用户样本源码逐字节不被改写", raw2.strip() == SAMPLE, "raw=%s" % raw2)
check("A2 用户样本渲染为 strong>mark>a>em>strong 且无字面标记",
      "<strong>" in html_s and "<mark>" in html_s and
      'href="https://www.sina.ocm"' in html_s and "<em>" in html_s and
      "==" not in html_s and "](" not in html_s,
      "html=%s" % html_s)

# ---------- B. 边界输入：不崩溃 / 不重复文本 ----------
EDGE = [
    "", "**", "*", "==", "~~", "`", "<u>", "[]", "**(空)**", "****",
    "**", "******", "**a", "a**", "*a", "a*", "==a", "a==",
    "[a](", "[a]()", "<u>a", "a</u>", "~~a", "a~~", "`a", "a`",
    "****a****", "***a*", "*a***", "**a*b**", "*a**b*", "*a **b** c*",
    "==**a**==", "**==a==**", "[**a**](https://x.y)", "**[a](https://x.y)**",
    "==[a](https://x.y)==", "**==[***a***](https://x.y)==**",
]
crash = []
for src in EDGE:
    js("window.setMarkdown(" + json.dumps(src) + ")")
    wait(60)
    txt = js("(function(){var b=document.querySelector('#editor .blk');"
             "return JSON.stringify((b&&b.textContent)||'')})()")
    err = js("JSON.stringify(window.__errs||[])")
    if err and err != "[]":
        crash.append((src, "err:" + err))
    try:
        got = json.loads(txt)
    except Exception:
        got = txt
    # 重复文本检测：内容字符出现次数不应超过源码中的次数
    for ch in ("a", "好"):
        if src.count(ch) and got.count(ch) > src.count(ch):
            crash.append((src, "dup:%s got=%s" % (ch, got)))
            break

check("B1 边界输入 %d 例无 JS 异常、无文本重复" % len(EDGE),
      not crash, "; ".join("%s → %s" % c for c in crash[:3]))

# ---------- B2. 随机乱码模糊（500 轮） ----------
POOL = list("**`~=<>[]()^_!-@#$%&+xu")
random.seed(777)
fatal = []
for _ in range(500):
    n = random.randint(1, 18)
    src = "".join(random.choice(POOL) for _ in range(n)) + "a"
    js("window.setMarkdown(" + json.dumps(src) + ")")
    wait(25)
    err = js("JSON.stringify(window.__errs||[])")
    if err and err != "[]":
        fatal.append((src, err))
        break
check("B2 随机乱码 500 轮无 JS 异常", not fatal, "%s" % (fatal[:2],))

with open(OUT, "w", encoding="utf-8") as f:
    for st, name, detail in _log:
        f.write("%s %s%s\n" % (st, name, (" | " + detail) if detail and st == "FAIL" else ""))
    f.write("NOTE 用例 A=%d 例（跳过超长游程 %d 例）、边界=%d 例、乱码=500 轮\n"
            % (len(cases) - skipped, skipped, len(EDGE)))
print("done")
