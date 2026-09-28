# -*- coding: utf-8 -*-
"""m76 回归：表格「+」追加行 / 列（v3.30.16 Word 风格）

场景：
  1 下边框外侧感应区 → 显示 row 按钮；位置在底边下方、水平居中
  2 点击 → 末尾追加一行（列数不变、每行列数一致）
  3 右边框外侧感应区 → 显示 col 按钮；点击 → 末尾追加一列（行数不变）
  4 指针移出感应区 → 自动隐藏
  5 指针移到按钮上 → 保持显示不闪烁；再移开 → 隐藏
  6 连续点击 → 连续追加
  7 空表格（单元格全空）→ 追加后结构仍完整
  8 管道表格 → 追加行 / 列
  9 滚动：按钮跟随表格；锚点移出视口则不显示
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m76.txt")
out = []
FAIL = [0]
TOTAL = [0]

HT = ('<table class="md-tbl">\n<tbody>\n'
      '<tr><td>a1</td><td>a2</td><td>a3</td></tr>\n'
      '<tr><td>b1</td><td>b2</td><td>b3</td></tr>\n'
      '</tbody>\n</table>')
HT_EMPTY = ('<table class="md-tbl">\n<tbody>\n'
            '<tr><td></td><td></td></tr>\n'
            '<tr><td></td><td></td></tr>\n'
            '</tbody>\n</table>')
PIPE = "| h1 | h2 |\n| --- | --- |\n| a | b |"


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def check(name, ok, detail=""):
    TOTAL[0] += 1
    if not ok:
        FAIL[0] += 1
    log("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


app = QApplication(sys.argv)
from mainwindow import MainWindow
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


def parse(s):
    try:
        return json.loads(s)
    except Exception:
        return {"err": str(s)[:160]}


wait(3000)

SHAPE = "window.__tblShape(%d)"
STATE = "window.__tblAddState()"


def shape(idx=1):
    return parse(js(SHAPE % idx))


def state():
    return parse(js(STATE))


def hover(x, y):
    return parse(js("window.__tblAddHover(%d,%d)" % (int(x), int(y))))


def hover_bottom(idx=1):
    r = shape(idx).get("rect", {})
    return hover((r["l"] + r["r"]) / 2.0, r["b"] + 5)


def hover_right(idx=1):
    r = shape(idx).get("rect", {})
    return hover(r["r"] + 5, (r["t"] + r["b"]) / 2.0)


def click():
    return parse(js("window.__tblAddClick()"))


def setdoc(md):
    js("window.setMarkdown(%s)" % json.dumps("X\n\n" + md))
    wait(1100)


# ---------- 1/2 下边框：追加行 ----------
setdoc(HT)
s0 = shape()
log("case1 shape0 = %s" % json.dumps(s0))
st = hover_bottom()
log("case1 hover-bottom = %s" % json.dumps(st))
r0 = s0["rect"]
check("1 下边框感应区显示按钮", st.get("show") is True and st.get("dir") == "row", json.dumps(st))
check("1b 按钮水平居中", abs((st.get("left", 0) + 11) - (r0["l"] + r0["r"]) / 2.0) <= 3,
      "btnMid=%s tblMid=%s" % (st.get("left", 0) + 11, (r0["l"] + r0["r"]) / 2.0))
check("1c 按钮在底边下方", st.get("top", 0) > r0["b"] and st.get("top", 0) - r0["b"] <= 12,
      "top=%s bottom=%s" % (st.get("top"), r0["b"]))

click()
wait(1000)
s1 = shape()
log("case2 shape1 = %s" % json.dumps(s1))
check("2 追加后行数 +1", s1.get("rows") == s0["rows"] + 1, "%s->%s" % (s0["rows"], s1.get("rows")))
check("2b 列数不变", s1.get("cells") == s0["cells"], "%s->%s" % (s0["cells"], s1.get("cells")))
check("2c 每行列数一致", s1.get("maxc") == s1.get("cells"), "maxc=%s first=%s" % (s1.get("maxc"), s1.get("cells")))
st1 = state()
check("2d 追加后按钮跟随到新底边", st1.get("show") is True and st1.get("top", 0) > st.get("top", 0),
      "%s->%s" % (st.get("top"), st1.get("top")))

# ---------- 3 右边框：追加列 ----------
setdoc(HT)
s0 = shape()
st = hover_right()
log("case3 hover-right = %s" % json.dumps(st))
check("3 右边框感应区显示按钮", st.get("show") is True and st.get("dir") == "col", json.dumps(st))
click()
wait(1000)
s1 = shape()
log("case3 shape1 = %s" % json.dumps(s1))
check("3b 追加后列数 +1", s1.get("cells") == s0["cells"] + 1, "%s->%s" % (s0["cells"], s1.get("cells")))
check("3c 行数不变", s1.get("rows") == s0["rows"], "%s->%s" % (s0["rows"], s1.get("rows")))

# ---------- 4 移出感应区隐藏 ----------
setdoc(HT)
hover_bottom()
r = shape()["rect"]
far = hover(r["r"] + 200, r["b"] + 200)
check("4 移出感应区后隐藏", far.get("show") is False, json.dumps(far))

# ---------- 5 移到按钮上保持显示 ----------
setdoc(HT)
st = hover_bottom()
bx, by = st.get("left", 0) + 11, st.get("top", 0) + 11
on = hover(bx, by)
check("5 指针移到按钮上保持显示", on.get("show") is True, json.dumps(on))
nudge = hover(bx + 2, by + 2)
check("5b 按钮上微移不抖动（仍显示且位置不变）",
      nudge.get("show") is True and nudge.get("left") == on.get("left") and nudge.get("top") == on.get("top"),
      json.dumps(nudge))
r = shape()["rect"]
away = hover(r["r"] + 300, r["b"] + 300)
check("5c 从按钮移开后隐藏", away.get("show") is False, json.dumps(away))

# ---------- 6 连续点击 ----------
setdoc(HT)
s0 = shape()
hover_bottom()
click()
wait(900)
click()
wait(900)
s2 = shape()
check("6 连续点击追加两行", s2.get("rows") == s0["rows"] + 2, "%s->%s" % (s0["rows"], s2.get("rows")))
check("6b 列数保持一致", s2.get("maxc") == s0["cells"], "maxc=%s" % s2.get("maxc"))

# ---------- 7 空表格 ----------
setdoc(HT_EMPTY)
s0 = shape()
hover_bottom()
click()
wait(1000)
s1 = shape()
check("7 空表格追加行", s1.get("rows") == s0["rows"] + 1, "%s->%s" % (s0["rows"], s1.get("rows")))
check("7b 空表格追加后列数一致", s1.get("maxc") == s1.get("cells") == s0["cells"], json.dumps(s1))
hover_right()
click()
wait(1000)
s2 = shape()
check("7c 空表格追加列", s2.get("cells") == s0["cells"] + 1, "%s->%s" % (s0["cells"], s2.get("cells")))
check("7d 空表格追加列后行数不变", s2.get("rows") == s1.get("rows"), json.dumps(s2))

# ---------- 8 管道表格 ----------
setdoc(PIPE)
s0 = shape()
log("case8 pipe shape0 = %s" % json.dumps(s0))
hover_bottom()
click()
wait(1000)
s1 = shape()
log("case8 pipe shape1 = %s" % json.dumps(s1))
check("8 管道表格追加行", s1.get("rows") == s0["rows"] + 1, "%s->%s" % (s0["rows"], s1.get("rows")))
check("8b 管道表格追加行后列数不变", s1.get("cells") == s0["cells"], json.dumps(s1))
hover_right()
click()
wait(1000)
s2 = shape()
log("case8 pipe shape2 = %s" % json.dumps(s2))
check("8c 管道表格追加列", s2.get("cells") == s1["cells"] + 1, "%s->%s" % (s1["cells"], s2.get("cells")))
check("8d 管道表格追加列后行数不变", s2.get("rows") == s1["rows"], json.dumps(s2))

# ---------- 9 滚动跟随 ----------
rows = []
for i in range(30):
    rows.append("<tr><td>r%dc1</td><td>r%dc2</td></tr>" % (i, i))
setdoc('<table class="md-tbl">\n<tbody>\n' + "\n".join(rows) + "\n</tbody>\n</table>")
wait(1200)
SCROLL = """(function(v){
  var ed=document.getElementById('editor');
  var t=(ed && ed.scrollHeight>ed.clientHeight+4)?ed:(document.scrollingElement||document.documentElement);
  if(v==='end') t.scrollTop=t.scrollHeight;
  else t.scrollTop=Math.max(0, t.scrollTop+v);
  document.dispatchEvent(new Event('scroll',{bubbles:true}));
  return JSON.stringify({scrollTop:Math.round(t.scrollTop), max:Math.round(t.scrollHeight-t.clientHeight)});
})('%s')"""
# 底边在视口外时按钮本就不该显示（没地方可点）
st_off = hover_bottom()
check("9a 底边在视口外时不显示", st_off.get("show") is False, json.dumps(st_off))
# 滚到底部让底边进入视口 → 按钮应出现在新的底边位置
js(SCROLL % "end")
wait(500)
st = hover_bottom()
log("case9 at-bottom = %s" % json.dumps(st))
check("9b 滚到底部后按钮出现", st.get("show") is True, json.dumps(st))
# 再上滚 150：表格整体下移，按钮应跟着下移（或移出视口隐藏）
js(SCROLL % "-150")
wait(400)
sc = parse(js("window.__tblAddState()"))
log("case9 after-scroll-up = %s" % json.dumps(sc))
moved = (sc.get("show") is False) or abs((sc.get("top", 0) - st.get("top", 0)) - 150) <= 40
check("9c 滚动后按钮跟随表格（位移≈滚动量）", moved,
      "top %s->%s show=%s" % (st.get("top"), sc.get("top"), sc.get("show")))

log("SUMMARY TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
os._exit(0)
