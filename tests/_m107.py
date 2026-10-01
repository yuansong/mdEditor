# -*- coding: utf-8 -*-
"""m107：setMarkdown 文档替换后的「旧块挂起写回」定位（m89 G7b-0 FAIL 归因）

背景：m89 G7b-0 断言「setmd('正文段落') 后 raw 复位为 ['正文段落']」失败，实测拿到
      ['[^1]: '] —— 前一步刚用 / 菜单插入过**脚注定义**（v3.31.3 起插入后直接进入
      **渲染态编辑** focusRenderedBlock）。怀疑渲染态编辑器（fnedit / wysiwyg 块）
      在文档被 setMarkdown 整体替换后仍有挂起提交，把旧块文本写回**新文档**第 0 块。

本探针分三组对照，定位「是不是延时器 / 是不是 blur 触发」：
  T1 插入脚注定义 → 立刻 setmd("正文段落") → 采样 100ms / 1200ms / 3000ms
  T2 插入脚注定义 → **先 blur** → setmd("正文段落") → 采样
  T3 插入脚注定义 → 先等 2000ms 再 setmd("正文段落") → 采样
  T4 对照：普通 raw-edit 态（不插脚注定义）→ setmd → 采样（应为干净）
  T5 对照：插入「术语定义」（defl，渲染态）→ setmd → 采样
判定按本文件 _m107.txt 的 FAIL 计数。
"""
import json, os, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m107.txt")
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


def js(code, ms=15000):
    loop = QEventLoop()
    box = {"r": None}

    def cb(res):
        box["r"] = res
        loop.quit()

    QTimer.singleShot(ms, loop.quit)
    win._js_active(code, cb)
    loop.exec()
    return box["r"]


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def jj(code):
    try:
        return json.loads(js(code) or "{}")
    except Exception:
        return {"_raw": js(code)}


def setmd(md, ms=700):
    js("window.setMarkdown(" + json.dumps(md, ensure_ascii=False) + ")")
    wait(ms)


def raws():
    return jj("window.__raw()").get("raw") or []


def blur():
    js("(function(){if(document.activeElement&&document.activeElement.blur)"
       "document.activeElement.blur();return 'ok'})()")
    wait(200)


def slash_open():
    js("(function(){var el=document.querySelector('.raw-edit');"
       "if(!el) return 'no-raw';"
       "el.dispatchEvent(new KeyboardEvent('keydown',{key:'/',bubbles:true,cancelable:true}));"
       "return 'ok'})()")
    wait(300)


wait(2500)
log("m107 启动完成")

# ---------- T1：脚注定义 → 立刻 setmd ----------
slash_open_ok = True
setmd("")
slash_open()
r = js("window.__slashPick('refs', 1)")
wait(600)
log("T1 插入后 raw=" + json.dumps(raws(), ensure_ascii=False) + " pick=" + str(r))
setmd("正文段落", ms=400)
t1 = raws()
wait(1600)
t1b = raws()
wait(3000)
t1c = raws()
log("T1 采样 %s / %s / %s" % (json.dumps(t1, ensure_ascii=False),
                             json.dumps(t1b, ensure_ascii=False),
                             json.dumps(t1c, ensure_ascii=False)))
check("T1 脚注定义后立刻换文档：400ms 时新文档干净", t1 == ["正文段落"],
      json.dumps(t1, ensure_ascii=False))
check("T1 脚注定义后立刻换文档：5s 内仍干净（无延时写回）", t1c == ["正文段落"],
      json.dumps({"400ms": t1, "2s": t1b, "5s": t1c}, ensure_ascii=False))

# ---------- T2：脚注定义 → blur → setmd ----------
setmd("")
slash_open()
js("window.__slashPick('refs', 1)")
wait(600)
blur()
setmd("正文段落", ms=400)
t2 = raws()
wait(1600)
t2b = raws()
log("T2 采样 %s / %s" % (json.dumps(t2, ensure_ascii=False), json.dumps(t2b, ensure_ascii=False)))
check("T2 先 blur 再换文档：干净", t2 == ["正文段落"] and t2b == ["正文段落"],
      json.dumps({"400ms": t2, "2s": t2b}, ensure_ascii=False))

# ---------- T3：脚注定义 → 等 2s → setmd ----------
setmd("")
slash_open()
js("window.__slashPick('refs', 1)")
wait(2500)
setmd("正文段落", ms=400)
t3 = raws()
log("T3 采样 %s" % json.dumps(t3, ensure_ascii=False))
check("T3 插入后静置 2.5s 再换文档：干净", t3 == ["正文段落"],
      json.dumps(t3, ensure_ascii=False))

# ---------- T4：对照，普通 raw-edit 态 ----------
setmd("")
slash_open()
js("window.__slashPick('h2', null)")
wait(600)
setmd("正文段落", ms=400)
t4 = raws()
log("T4 采样 %s" % json.dumps(t4, ensure_ascii=False))
check("T4 对照（普通块插入）换文档干净", t4 == ["正文段落"],
      json.dumps(t4, ensure_ascii=False))

# ---------- T5：术语定义（defl，渲染态） ----------
setmd("")
slash_open()
js("window.__slashPick('defl', null)")
wait(600)
setmd("正文段落", ms=400)
t5 = raws()
wait(1600)
t5b = raws()
log("T5 采样 %s / %s" % (json.dumps(t5, ensure_ascii=False), json.dumps(t5b, ensure_ascii=False)))
check("T5 术语定义后换文档：干净", t5 == ["正文段落"] and t5b == ["正文段落"],
      json.dumps({"400ms": t5, "2s": t5b}, ensure_ascii=False))

# ---------- T6：脚注定义 + 换文档 + 再插脚注引用（m89 G7b 实际场景） ----------
setmd("正文段落", ms=600)
js("(function(){var p=document.querySelector('#editor .blk p');"
   "if(!p) return 'no-p'; p.focus(); var rg=document.createRange();"
   "rg.selectNodeContents(p); rg.collapse(false); var s=getSelection();"
   "s.removeAllRanges(); s.addRange(rg); return 'ok'})()")
wait(200)
js("window.cmd('footnote')")
wait(700)
t6 = raws()
log("T6 采样 %s" % json.dumps(t6, ensure_ascii=False))
check("T6 干净文档上插脚注引用 → [^1] 引用 + 文末空定义",
      t6 and t6[0].strip().endswith("[^1]") and any(x.strip() == "[^1]:" for x in t6[1:]),
      json.dumps(t6, ensure_ascii=False))

# ---------- T7：世代守卫不能误伤「正常失焦回写」（脚注定义） ----------
setmd("正文\n\n[^1]: 说明")
js("(function(){var f=document.querySelector('#editor .fnedit');"
   "if(!f) return 'no-fn'; f.focus(); var rg=document.createRange();"
   "rg.selectNodeContents(f); rg.collapse(false); var s=getSelection();"
   "s.removeAllRanges(); s.addRange(rg);"
   "document.execCommand('insertText', false, 'X'); return 'ok'})()")
wait(300)
blur()
wait(300)
t7 = raws()
log("T7 采样 %s" % json.dumps(t7, ensure_ascii=False))
check("T7 脚注定义正常失焦回写仍生效（世代守卫不误伤）",
      any("说明X" in x for x in t7), json.dumps(t7, ensure_ascii=False))

# ---------- T8：引用内代码块正常失焦回写（同一守卫的另一个落点） ----------
setmd("> ```js\n> var a = 1;\n> ```")
has_q = js("!!document.querySelector('#editor .qblk code')")
if has_q is True:
    js("(function(){var c=document.querySelector('#editor .qblk code');"
       "if(!c) return 'no-code'; c.focus(); var rg=document.createRange();"
       "rg.selectNodeContents(c); rg.collapse(false); var s=getSelection();"
       "s.removeAllRanges(); s.addRange(rg);"
       "document.execCommand('insertText', false, '\\nvar b = 2;'); return 'ok'})()")
    wait(300)
    blur()
    wait(400)
    t8 = raws()
    log("T8 采样 %s" % json.dumps(t8, ensure_ascii=False))
    check("T8 引用内代码块正常失焦回写仍生效（世代守卫不误伤）",
          any("var b = 2;" in x for x in t8), json.dumps(t8, ensure_ascii=False))
else:
    log("NOTE T8 未找到 .qblk code（跳过，不计入）")

log("NOTE TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
log("DONE TOTAL=%d FAIL=%d" % (TOTAL[0], FAIL[0]))
