# -*- coding: utf-8 -*-
"""m91：m90 三项失败的定位与最小复现
  B9  块菜单边界置灰（markBlockMenuBoundary 疑似死代码）
  B12 脚注定义块上移后的渲染表现（是否暴露源码）
  D1  随机序列 step24 逐步重放，定位引入裸 ** 的那一步
"""
import json, os, random, sys
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m91.txt")
out = []
URL = "https://ex.com/doc"
QTEXT = "这是一段真实的引用内容包含中文字符与标点符号"


def log(s):
    out.append(str(s))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def note(s):
    log(str(s))


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
        return json.loads(js(code) or "{}")
    except Exception:
        return {"_raw": js(code)}


def setdoc(lines, ms=800):
    js("window.setMarkdown(" + json.dumps("\n\n".join(lines)) + ")")
    wait(ms)


def getraw():
    return jj("window.__raw()").get("raw") or []


def hover_blk(idx, ms=300):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
       "if(!b)return 'no-blk';var r=b.getBoundingClientRect();"
       "b.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,cancelable:true,"
       "clientX:r.left+20,clientY:r.top+8}));return 'ok'})()")
    wait(ms)


def click_handle(ms=350):
    js("(function(){var h=document.getElementById('blkhandle');if(!h)return 'no-h';"
       "h.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));return 'ok'})()")
    wait(ms)


def menu_items():
    return jj("(function(){var o=[];var m=document.querySelectorAll('#blkmenu .mi');"
              "for(var i=0;i<m.length;i++){o.push({act:m[i].getAttribute('data-act'),"
              "dis:m[i].classList.contains('dis'),title:m[i].title,lb:m[i].textContent.trim()});}"
              "return JSON.stringify(o)})()").get("items") if False else json.loads(
        js("(function(){var o=[];var m=document.querySelectorAll('#blkmenu .mi');"
           "for(var i=0;i<m.length;i++){o.push({act:m[i].getAttribute('data-act'),"
           "dis:m[i].classList.contains('dis'),title:m[i].title,lb:m[i].textContent.trim()});}"
           "return JSON.stringify(o)})()") or "[]")


def blk_dump(idx):
    return jj("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(idx) + "];"
              "if(!b)return JSON.stringify({err:'noblk'});"
              "return JSON.stringify({text:(b.textContent||''),"
              "html:b.innerHTML.substring(0,400)})})()")


def apply_block(act, idx, ms=450):
    js("window.__applyBlockAct(" + json.dumps(act) + "," + str(idx) + ")")
    wait(ms)


def sel_in(blk, sel, ms=250):
    js("(function(){var b=document.querySelectorAll('#editor .blk')[" + str(blk) + "];"
       "if(!b)return 'no-blk';var el=b.querySelector(" + json.dumps(sel) + ");"
       "if(!el)return 'no-el';var rg=document.createRange();rg.selectNodeContents(el);"
       "var s=window.getSelection();s.removeAllRanges();s.addRange(rg);"
       "document.dispatchEvent(new Event('selectionchange'));return 'ok'})()")
    wait(ms)


def fmt(act, ms=330):
    if act == "link":
        js("window.__applyFloat('link')")
        wait(ms)
        js("(function(){var i=document.getElementById('link-url');"
           "if(!i)return 'no-input';i.value=" + json.dumps(URL) + ";"
           "var b=document.getElementById('link-ok');"
           "if(!b)return 'no-btn';b.click();return 'ok'})()")
        wait(ms + 120)
        return
    js("window.__applyFloat(" + json.dumps(act) + ")")
    wait(ms)


wait(2500)

# ---------- B9：边界置灰 ----------
note("========== B9 边界置灰核查 ==========")
for label, doc, idx in [("唯一块", ["> " + QTEXT], 0),
                        ("首块", ["> " + QTEXT, "第二段内容"], 0),
                        ("末块", ["第一段内容", "> " + QTEXT], 1)]:
    setdoc(doc)
    hover_blk(idx)
    click_handle()
    items = menu_items()
    ups = [i for i in items if i.get("act") == "up"]
    dns = [i for i in items if i.get("act") == "down"]
    note("%s: up=%s down=%s" % (label,
                                json.dumps(ups, ensure_ascii=False),
                                json.dumps(dns, ensure_ascii=False)))

# ---------- B12：脚注定义块位置变化的渲染 ----------
note("========== B12 脚注定义块位置变化 ==========")
setdoc(["> 引用内含脚注标记[^1]的中文内容", "[^1]: 这是脚注定义的中文内容"])
note("初始 blk0=%s" % json.dumps(blk_dump(0), ensure_ascii=False))
note("初始 blk1=%s" % json.dumps(blk_dump(1), ensure_ascii=False))
apply_block("up", 1)
note("定义块上移后 raw=%s" % json.dumps(getraw(), ensure_ascii=False))
note("定义块上移后 blk0=%s" % json.dumps(blk_dump(0), ensure_ascii=False))
note("定义块上移后 blk1=%s" % json.dumps(blk_dump(1), ensure_ascii=False))

note("--- 补测：删除脚注定义块后，正文引用标记的表现 ---")
setdoc(["> 引用内含脚注标记[^1]的中文内容", "[^1]: 这是脚注定义的中文内容"])
apply_block("del", 1)
note("删除定义块后 raw=%s" % json.dumps(getraw(), ensure_ascii=False))
note("删除定义块后 blk0=%s" % json.dumps(blk_dump(0), ensure_ascii=False))
note("删除定义块后 blk1=%s" % json.dumps(blk_dump(1), ensure_ascii=False))

# ---------- D1：随机序列逐步重放 ----------
note("========== D1 随机序列逐步重放（seed=20260929）==========")
random.seed(20260929)
ACTS = ["bold", "italic", "strike", "mark", "code", "link", "clearfmt", "up", "down", "dup"]
DOC = ["# 中文标题示例", "正文段落这是一段正文内容", "> " + QTEXT, "结尾段落用于验证下移"]
setdoc(DOC)
for step in range(30):
    a = random.choice(ACTS)
    rawnow = getraw()
    qi = [k for k, x in enumerate(rawnow) if x.startswith("> ")]
    if not qi:
        note("step%02d act=%-8s 引用块丢失，中止" % (step, a))
        break
    idx = qi[0]
    if a in ("up", "down", "dup"):
        apply_block(a, idx, 450)
    else:
        sel_in(idx, "blockquote")
        fmt(a, 300)
    r2 = getraw()
    qi2 = [k for k, x in enumerate(r2) if x.startswith("> ")]
    if not qi2:
        note("step%02d act=%-8s 操作后引用块丢失 raw=%s" % (step, a, json.dumps(r2, ensure_ascii=False)))
        break
    d = blk_dump(qi2[0])
    t = d.get("text") or ""
    flag = ""
    for m in ["**", "==", "~~", "](", "[^"]:
        if m in t:
            flag += " [裸标记:%s]" % m
    note("step%02d act=%-8s idx=%d raw=%s text=%s%s" % (
        step, a, qi2[0], json.dumps(r2[qi2[0]], ensure_ascii=False),
        json.dumps(t, ensure_ascii=False), flag))
    if step >= 23 and step <= 26:
        note("        html=%s" % json.dumps(d.get("html", ""), ensure_ascii=False))

note("DONE")
