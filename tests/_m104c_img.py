# -*- coding: utf-8 -*-
"""m104c 图片在源码模式 / 双屏模式下的表现（用户排查项 7）

验证：源码模式下图块形态、双屏预览侧是否渲染、右键/选中在锁定态的行为、切回写作态是否还原。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m104c_img.txt")
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

PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE"
       "hQGAhKmMIQAAAABJRU5ErkJggg==")
DOC = "前段\n\n![图甲](" + PNG + ")\n\n尾段"


def setmd(md, ms=780):
    js("window.setMarkdown(" + json.dumps(md) + ")")
    wait(ms)


def blkinfo():
    return jj("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
              "return JSON.stringify({n:bs.length,"
              "cls:bs.map(function(b){return b.className}),"
              "imgs:document.querySelectorAll('#editor img').length,"
              "raw:(function(){try{return JSON.parse(window.__raw()||'{}').raw||[]}catch(e){return []}})()})})()")


def dumpshape(tag):
    return jj("(function(){var bs=[].slice.call(document.querySelectorAll('#editor .blk'));"
              "var t=[];for(var k=0;k<bs.length;k++){t.push(bs[k].className+'::'+(bs[k].textContent||'').slice(0,40))}"
              "return JSON.stringify({tag:'" + tag + "',n:bs.length,shape:t,"
              "imgs:document.querySelectorAll('#editor img').length})})()")


note("========== 写作态基线 ==========")
setmd(DOC)
s = dumpshape("edit")
note("  edit=%s" % json.dumps(s, ensure_ascii=False)[:400])
check("编辑态：图片渲染为 img 且块非源码态", s.get("imgs") == 1, "shape=%s" % json.dumps(s, ensure_ascii=False)[:300])

note("========== 源码模式 ==========")
win._set_mode("src")
wait(1200)
s = dumpshape("src")
note("  src=%s" % json.dumps(s, ensure_ascii=False)[:500])
check("源码模式：图片块以源码文本呈现（非渲染图）",
      s.get("imgs") == 0 and any("raw-edit" in str(x) for x in s.get("shape", [])),
      "shape=%s" % json.dumps(s.get("shape"), ensure_ascii=False)[:300])
note("  源码模式右键是否可用（editorLocked）：%s" %
     js("(function(){var im=document.querySelector('#editor img');"
        "if(!im)return 'no-img';"
        "im.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}));"
        "var BM=document.getElementById('blkmenu');"
        "return BM?String(BM.classList.contains('show')):'no-bm'})()"))
wait(400)

note("========== 双屏模式 ==========")
win._set_mode("dual")
wait(1600)
s = dumpshape("dual-active")
note("  dual(活动视图)=%s" % json.dumps(s, ensure_ascii=False)[:500])
prev = jj("(function(){var v=document.querySelectorAll('img');"
          "return JSON.stringify({imgs:v.length,srcs:[].slice.call(v).map(function(i){return (i.getAttribute('src')||'').slice(0,24)})})})()")
note("  文档内 img 统计（含预览视图 WebView 需分别查询）=%s" % json.dumps(prev, ensure_ascii=False))
if hasattr(win, "_view_prev") and win._view_prev is not None:
    r = js_prev = None
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()
    QTimer.singleShot(15000, loop.quit)
    win._js_view(win._view_prev, "JSON.stringify({imgs:document.querySelectorAll('img').length,"
                                 "cap:(document.querySelector('figcaption')||{}).textContent||''})", cb)
    loop.exec()
    note("  预览视图=%s" % str(box["r"]))
    check("双屏模式预览侧：图片正常渲染",
          box["r"] and '"imgs":1' in str(box["r"]).replace(" ", ""), "prev=%s" % str(box["r"]))
else:
    note("  预览视图未创建（惰性），跳过")

note("========== 切回写作态 ==========")
win._set_mode("edit")
wait(1200)
s = dumpshape("back-edit")
note("  back=%s" % json.dumps(s, ensure_ascii=False)[:400])
check("切回写作态：图片恢复渲染且内容不漂移",
      s.get("imgs") == 1 and s.get("n") == 3, "shape=%s" % json.dumps(s, ensure_ascii=False)[:300])
g = jj("window.__raw()")
raw = []
try:
    raw = json.loads(js("window.__raw()") or "{}").get("raw") or []
except Exception:
    pass
check("往返后 raw 与初始一致（图片 src 未被改写）",
      len(raw) == 3 and raw[1].startswith("![图甲]("), "raw=%s" % json.dumps([x[:30] for x in raw], ensure_ascii=False))

log("")
log("========== 汇总：%d 断言，FAIL %d ==========" % (TOTAL[0], FAIL[0]))
for a in ABN:
    log("  ABN " + a)
