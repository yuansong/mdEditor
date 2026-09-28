# -*- coding: utf-8 -*-
"""m72 回归：v3.30.15 行整体移动 —— 合并区原子化。

覆盖：
  C1 合并区整体下移一格（合并格不拆、rowspan 保留）
  C2 合并区整体上移一格
  C3 跨合并区拖到末行
  C4 拖到首行
  C5 拖入合并区内部 → 自动修正到合法落点，不切穿合并区
  C6 选区含表头行 → 拒绝且模型不变（回滚）
  C7 移动后存储往返（重新载入仍然正确）
  C8 相邻上/下移回归（无合并表，行为不变）
  C9 管道表格行移动（无合并）不受影响
  C10 多次连续拖拽后结构审计始终干净
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m72.txt")
out = []
FAIL = [0]
TOTAL = [0]


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


def jj(code):
    try:
        return json.loads(js(code))
    except Exception as e:
        return {"err": "%s / %s" % (e, str(js(code))[:160])}


wait(3000)

# 无表头 HTML 表：4 行 4 列，内容带坐标便于追踪
TBODY = ('<table class="md-tbl">\n<tbody>\n'
         '<tr><td>r0c0</td><td>r0c1</td><td>r0c2</td><td>r0c3</td></tr>\n'
         '<tr><td>r1c0</td><td>r1c1</td><td>r1c2</td><td>r1c3</td></tr>\n'
         '<tr><td>r2c0</td><td>r2c1</td><td>r2c2</td><td>r2c3</td></tr>\n'
         '<tr><td>r3c0</td><td>r3c1</td><td>r3c2</td><td>r3c3</td></tr>\n'
         '</tbody>\n</table>')
# 带表头的 HTML 表
THEAD = ('<table class="md-tbl">\n<thead>\n'
         '<tr><th>h0</th><th>h1</th><th>h2</th></tr>\n</thead>\n<tbody>\n'
         '<tr><td>b0c0</td><td>b0c1</td><td>b0c2</td></tr>\n'
         '<tr><td>b1c0</td><td>b1c1</td><td>b1c2</td></tr>\n'
         '<tr><td>b2c0</td><td>b2c1</td><td>b2c2</td></tr>\n'
         '</tbody>\n</table>')
PIPE = ('| a | b | c |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |\n| 7 | 8 | 9 |')

AUDIT = "window.__tblAudit()"


def setmd(md):
    js("window.setMarkdown(%s)" % json.dumps(md))
    wait(900)


def sel(r0, c0, r1, c1):
    js("window.__tblSelSet(0,%d,%d,%d,%d)" % (r0, c0, r1, c1))
    wait(250)


def merge(r0, c0, r1, c1):
    sel(r0, c0, r1, c1)
    js("window.__tblOp('merge')")
    wait(800)


def spans(au):
    """合并格跨度多重集 [(r,c,rs,cs)] —— 验证「合并状态不被改写」"""
    return sorted([(c["r"], c["c"], c["rs"], c["cs"]) for c in au.get("cells", [])
                   if c["rs"] > 1 or c["cs"] > 1])


def rowtext(au, r):
    """第 r 行里归属该行的格内容（按列序）"""
    cs = [c for c in au.get("cells", []) if c["r"] == r]
    cs.sort(key=lambda x: x["c"])
    return [c["h"] for c in cs]


def audit_ok(tag):
    au = jj(AUDIT)
    check("%s 结构审计（无重叠/无空洞/无越界）" % tag, au.get("ok") is True,
          au.get("reason", ""))
    return au


# ==================== C1: 合并区整体下移一格 ====================
log("CASE C1 begin")
setmd(TBODY)
merge(1, 1, 2, 1)                        # 合并 (1,1)-(2,1) → rowspan=2
a0 = audit_ok("C1 合并后")
s0 = spans(a0)
check("C1 合并格为 rowspan=2 @r1c1", s0 == [(1, 1, 2, 1)], str(s0))
sel(1, 0, 1, 3)                          # 只选第 1 行 → 应自动并入合并区 [1,2]
# 目标 4 = 插到表尾（绝对插入点用「原表行号」语义：带落在原行 3 之后）
res = jj("window.__tblRowMove(1,1,4)")
log("  C1 move=%s" % json.dumps(res))
a1 = audit_ok("C1 移动后")
s1 = spans(a1)
check("C1 执行成功", res.get("ok") is True, str(res))
check("C1 移动带自动扩展为 [1,2]", res.get("br0") == 1 and res.get("br1") == 2,
      "br=%s,%s" % (res.get("br0"), res.get("br1")))
check("C1 合并格未被拆分（rs 仍为 2，随带下移）", s1 == [(2, 1, 2, 1)], str(s1))
check("C1 行序 = [0,3,1,2]",
      [rowtext(a1, i)[:1] for i in range(4)] ==
      [["r0c0"], ["r3c0"], ["r1c0"], ["r2c0"]],
      str([rowtext(a1, i)[:1] for i in range(4)]))
check("C1 存储含 rowspan=2", 'rowspan="2"' in (a1.get("raw") or ""),
      (a1.get("raw") or "")[:120])
log("CASE C1 end")

# ==================== C2: 合并区整体上移一格 ====================
log("CASE C2 begin")
setmd(TBODY)
merge(2, 1, 3, 1)
sel(2, 0, 2, 3)
res = jj("window.__tblRowMove(2,2,1)")   # 上移：目标绝对行号 1
log("  C2 move=%s" % json.dumps(res))
a2 = audit_ok("C2 移动后")
check("C2 执行成功", res.get("ok") is True, str(res))
check("C2 合并格上移且 rs 不变", spans(a2) == [(1, 1, 2, 1)], str(spans(a2)))
check("C2 行序 = [0,2,3,1]",
      [rowtext(a2, i)[:1] for i in range(4)] ==
      [["r0c0"], ["r2c0"], ["r3c0"], ["r1c0"]],
      str([rowtext(a2, i)[:1] for i in range(4)]))
log("CASE C2 end")

# ==================== C3: 跨合并区拖到末行 ====================
log("CASE C3 begin")
setmd(TBODY)
merge(0, 1, 1, 1)
sel(0, 0, 0, 3)
res = jj("window.__tblRowMove(0,0,4)")   # 拖到表尾（绝对插入点 4）
log("  C3 move=%s" % json.dumps(res))
a3 = audit_ok("C3 移动后")
check("C3 执行成功", res.get("ok") is True, str(res))
check("C3 合并区整体到末尾（r=2,rs=2）", spans(a3) == [(2, 1, 2, 1)], str(spans(a3)))
check("C3 末两行是原 0/1 行",
      [rowtext(a3, 2)[:1], rowtext(a3, 3)[:1]] == [["r0c0"], ["r1c0"]],
      str([rowtext(a3, i)[:1] for i in range(4)]))
log("CASE C3 end")

# ==================== C4: 拖到首行 ====================
log("CASE C4 begin")
setmd(TBODY)
merge(2, 2, 3, 2)
sel(2, 0, 2, 3)
res = jj("window.__tblRowMove(2,2,0)")   # 拖到最前
log("  C4 move=%s" % json.dumps(res))
a4 = audit_ok("C4 移动后")
check("C4 执行成功", res.get("ok") is True, str(res))
check("C4 合并区到首两行（r=0,rs=2）", spans(a4) == [(0, 2, 2, 1)], str(spans(a4)))
log("CASE C4 end")

# ==================== C5: 拖入合并区内部 → 自动修正 ====================
log("CASE C5 begin")
setmd(TBODY)
merge(0, 1, 1, 1)                        # 合并区占行 0-1
b5 = jj(AUDIT)
sel(3, 0, 3, 3)                          # 拖最后一行
res = jj("window.__tblRowMove(3,3,1)")   # 目标落在合并区内部（行 1 之前 → 会切穿）
log("  C5 move=%s" % json.dumps(res))
a5 = audit_ok("C5 移动后")
check("C5 执行成功（落点被修正）", res.get("ok") is True, str(res))
check("C5 合并格仍为 1 个 rowspan=2（未被切穿）",
      len(spans(a5)) == 1 and spans(a5)[0][2] == 2, str(spans(a5)))
check("C5 合并格总数不变", len(spans(a5)) == len(spans(b5)),
      "%d vs %d" % (len(spans(a5)), len(spans(b5))))
log("CASE C5 end")

# ==================== C6: 选区含表头行 → 拒绝 + 回滚 ====================
log("CASE C6 begin")
setmd(THEAD)
b6 = jj(AUDIT)
sel(0, 0, 0, 2)                          # 选表头行
res = jj("window.__tblRowMove(0,0,2)")
log("  C6 move=%s" % json.dumps(res))
a6 = audit_ok("C6 拒绝后")
check("C6 含表头 → 拒绝", res.get("ok") is False, str(res))
check("C6 拒绝原因可读", "表头" in (res.get("reason") or ""), str(res.get("reason")))
check("C6 拒绝后存储完全不变",
      (a6.get("raw") or "") == (b6.get("raw") or ""),
      "changed" if (a6.get("raw") or "") != (b6.get("raw") or "") else "same")
log("CASE C6 end")

# ==================== C7: 移动后存储往返 ====================
log("CASE C7 begin")
setmd(TBODY)
merge(1, 1, 2, 1)
sel(1, 0, 1, 3)
res = jj("window.__tblRowMove(1,1,4)")
a7 = jj(AUDIT)
setmd(a7.get("raw") or "")               # 重新载入
sel(0, 0, 0, 3)
a7b = audit_ok("C7 往返后")
check("C7 往返后合并格保持", spans(a7b) == spans(a7), "%s vs %s" % (spans(a7b), spans(a7)))
check("C7 往返后行内容一致",
      [rowtext(a7b, i)[:1] for i in range(a7b.get("rows", 0))] ==
      [rowtext(a7, i)[:1] for i in range(a7.get("rows", 0))],
      str([rowtext(a7b, i)[:1] for i in range(a7b.get("rows", 0))]))
log("CASE C7 end")

# ==================== C8: 相邻上 / 下移回归（无合并） ====================
log("CASE C8 begin")
setmd(TBODY)
sel(1, 0, 1, 3)
js("window.__tblOp('rowMoveDown')")
wait(800)
a8 = audit_ok("C8 下移后")
check("C8 下移 → [0,2,1,3]",
      [rowtext(a8, i)[:1] for i in range(4)] ==
      [["r0c0"], ["r2c0"], ["r1c0"], ["r3c0"]],
      str([rowtext(a8, i)[:1] for i in range(4)]))
sel(2, 0, 2, 3)
js("window.__tblOp('rowMoveUp')")
wait(800)
a8b = audit_ok("C8 上移后")
check("C8 上移 → 还原原序",
      [rowtext(a8b, i)[:1] for i in range(4)] ==
      [["r0c0"], ["r1c0"], ["r2c0"], ["r3c0"]],
      str([rowtext(a8b, i)[:1] for i in range(4)]))
log("CASE C8 end")

# ==================== C9: 管道表格行移动不受影响 ====================
log("CASE C9 begin")
setmd(PIPE)
sel(2, 0, 2, 2)
js("window.__tblOp('rowMoveUp')")
wait(800)
md9 = js("window.getMarkdown()")
log("  C9 md=%s" % str(md9).replace("\n", " | ")[:160])
ok9 = isinstance(md9, str) and md9.find("| 4 |") >= 0 and md9.find("| 1 |") >= 0 \
    and md9.find("| 4 |") < md9.find("| 1 |")
check("C9 管道表格上移生效（第 2 数据行上移）", ok9, str(md9)[:120])
log("CASE C9 end")

# ==================== C10: 连续多次拖拽后结构始终干净 ====================
log("CASE C10 begin")
setmd(TBODY)
merge(1, 1, 2, 1)
seq = [(1, 1, 4), (2, 2, 0), (0, 0, 3), (2, 2, 1)]
bad = []
for i, (r0, r1, t) in enumerate(seq):
    sel(r0, 0, r1, 3)
    rr = jj("window.__tblRowMove(%d,%d,%d)" % (r0, r1, t))
    au = jj(AUDIT)
    if au.get("ok") is not True:
        bad.append("step%d audit:%s" % (i, au.get("reason")))
    if len(spans(au)) != 1:
        bad.append("step%d spans=%s" % (i, spans(au)))
    log("  C10 step%d move=%s spans=%s" % (i, json.dumps(rr), spans(au)))
check("C10 连续 4 次拖拽结构始终合法、合并区始终 1 个", not bad, ";".join(bad) if bad else "ok")
log("CASE C10 end")

log("SUMMARY TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
os._exit(0)
